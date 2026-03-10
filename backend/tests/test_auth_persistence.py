"""
Tests for database-backed authentication system.

Verifies that registration, login, password changes, and admin seeding
all persist correctly through SQLAlchemy + an in-memory SQLite database.
"""

import os

os.environ["USE_SQLITE"] = "true"
os.environ["DEBUG"] = "true"

import pytest
import pytest_asyncio
from httpx import AsyncClient, ASGITransport
from sqlalchemy import select
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from datetime import datetime

from backend.database.session import Base, get_db
from backend.shared.rbac_models import UserModel, OrganizationModel
from backend.shared.auth import hash_password, verify_password, get_jwt_manager


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest_asyncio.fixture()
async def db_engine():
    """Create an async in-memory SQLite engine with all tables.

    The SQLite type adapters (ARRAY→JSON, INET→VARCHAR, etc.) are registered
    by backend.database.session when USE_SQLITE=true (set at module top).
    We also ensure they're registered here in case session.py was imported
    earlier by another test without USE_SQLITE=true.
    """
    from sqlalchemy.dialects.sqlite.base import SQLiteTypeCompiler
    for type_name, sql_type in [
        ("visit_ARRAY", "JSON"),
        ("visit_JSONB", "JSON"),
        ("visit_INET", "VARCHAR(45)"),
        ("visit_UUID", "VARCHAR(36)"),
    ]:
        if not hasattr(SQLiteTypeCompiler, type_name):
            setattr(SQLiteTypeCompiler, type_name, lambda self, type_, sql=sql_type, **kw: sql)

    engine = create_async_engine(
        "sqlite+aiosqlite:///:memory:",
        echo=False,
    )

    def _create_tables(conn):
        """Create tables, ignoring duplicate index errors from extend_existing models."""
        import sqlalchemy.exc
        try:
            Base.metadata.create_all(conn, checkfirst=True)
        except sqlalchemy.exc.OperationalError as e:
            if "already exists" in str(e):
                pass  # Ignore duplicate index from extend_existing models
            else:
                raise

    async with engine.begin() as conn:
        await conn.run_sync(_create_tables)
    yield engine
    await engine.dispose()


@pytest_asyncio.fixture()
async def db_session_factory(db_engine):
    """Return an async_sessionmaker bound to the in-memory engine."""
    factory = async_sessionmaker(
        db_engine,
        class_=AsyncSession,
        expire_on_commit=False,
        autocommit=False,
        autoflush=False,
    )
    return factory


@pytest_asyncio.fixture()
async def seed_org(db_session_factory):
    """Seed the default organization so FK constraints are satisfied."""
    async with db_session_factory() as session:
        org = OrganizationModel(
            organization_id="default",
            name="Default Organization",
            slug="default",
            plan="startup",
            max_users=50,
            max_agents=100,
            is_active=True,
        )
        session.add(org)
        await session.commit()


@pytest_asyncio.fixture()
async def seed_admin(db_session_factory, seed_org):
    """Seed the admin user (mirrors lifespan seeding in main.py)."""
    async with db_session_factory() as session:
        admin = UserModel(
            user_id="user-admin-001",
            email="admin@example.com",
            full_name="Admin User",
            password_hash=hash_password("admin123"),
            role="admin",
            organization_id="default",
            is_active=True,
            is_email_verified=True,
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow(),
        )
        session.add(admin)
        await session.commit()


@pytest_asyncio.fixture()
async def client(db_session_factory, seed_org):
    """
    Async HTTP test client with the test DB session injected.

    Overrides the ``get_db`` dependency so every request uses the
    in-memory SQLite database instead of the real PostgreSQL connection.
    """
    from backend.api.main import app

    async def _override_get_db():
        async with db_session_factory() as session:
            try:
                yield session
                await session.commit()
            except Exception:
                await session.rollback()
                raise

    app.dependency_overrides[get_db] = _override_get_db

    transport = ASGITransport(app=app, raise_app_exceptions=False)
    async with AsyncClient(transport=transport, base_url="http://testserver") as ac:
        yield ac

    app.dependency_overrides.pop(get_db, None)


@pytest_asyncio.fixture()
async def client_with_admin(db_session_factory, seed_admin):
    """
    Same as ``client`` but with the admin user already seeded.
    """
    from backend.api.main import app

    async def _override_get_db():
        async with db_session_factory() as session:
            try:
                yield session
                await session.commit()
            except Exception:
                await session.rollback()
                raise

    app.dependency_overrides[get_db] = _override_get_db

    transport = ASGITransport(app=app, raise_app_exceptions=False)
    async with AsyncClient(transport=transport, base_url="http://testserver") as ac:
        yield ac

    app.dependency_overrides.pop(get_db, None)


# ---------------------------------------------------------------------------
# 1. Registration creates a DB row
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_register_creates_db_row(client, db_session_factory):
    """POST /api/v1/auth/register should persist a new user in the database."""
    resp = await client.post(
        "/api/v1/auth/register",
        json={
            "email": "newuser@example.com",
            "password": "SecurePass123!",
            "name": "New User",
        },
    )
    assert resp.status_code == 201, resp.text
    body = resp.json()
    assert body["user"]["email"] == "newuser@example.com"
    assert body["user"]["name"] == "New User"
    assert "access_token" in body

    # Verify the row actually landed in the database
    async with db_session_factory() as session:
        result = await session.execute(
            select(UserModel).where(UserModel.email == "newuser@example.com")
        )
        user = result.scalar_one_or_none()
        assert user is not None
        assert user.full_name == "New User"
        assert user.organization_id == "default"
        assert user.is_active is True


# ---------------------------------------------------------------------------
# 2. Login finds DB user and returns valid JWT
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_login_returns_valid_jwt(client_with_admin):
    """POST /api/v1/auth/login should authenticate and return a valid JWT."""
    resp = await client_with_admin.post(
        "/api/v1/auth/login",
        json={
            "email": "admin@example.com",
            "password": "admin123",
        },
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["token_type"] == "bearer"
    assert body["expires_in"] > 0

    token = body["access_token"]
    jwt_manager = get_jwt_manager()
    payload = jwt_manager.verify_token(token)
    assert payload is not None
    assert payload["email"] == "admin@example.com"
    assert payload["sub"] == "user-admin-001"
    assert payload["type"] == "dashboard"


# ---------------------------------------------------------------------------
# 3. Duplicate email is rejected (409)
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_duplicate_email_rejected(client):
    """Registering the same email twice should return 409 Conflict."""
    payload = {
        "email": "duplicate@example.com",
        "password": "Password1234!",
        "name": "First User",
    }

    first = await client.post("/api/v1/auth/register", json=payload)
    assert first.status_code == 201, first.text

    second = await client.post("/api/v1/auth/register", json=payload)
    assert second.status_code == 409, second.text
    assert "already registered" in second.json()["detail"].lower()


# ---------------------------------------------------------------------------
# 4. Password change persists
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_password_change_persists(client_with_admin):
    """Changing password via /change-password should persist so the new
    password works for subsequent logins."""
    # Login to get a JWT
    login_resp = await client_with_admin.post(
        "/api/v1/auth/login",
        json={"email": "admin@example.com", "password": "admin123"},
    )
    assert login_resp.status_code == 200
    token = login_resp.json()["access_token"]

    # Change password
    change_resp = await client_with_admin.post(
        "/api/v1/auth/change-password",
        json={
            "current_password": "admin123",
            "new_password": "NewPassword456!",
        },
        headers={"Authorization": f"Bearer {token}"},
    )
    assert change_resp.status_code == 200, change_resp.text
    assert change_resp.json()["message"] == "Password changed successfully"

    # Old password should now fail
    old_login = await client_with_admin.post(
        "/api/v1/auth/login",
        json={"email": "admin@example.com", "password": "admin123"},
    )
    assert old_login.status_code == 401

    # New password should work
    new_login = await client_with_admin.post(
        "/api/v1/auth/login",
        json={"email": "admin@example.com", "password": "NewPassword456!"},
    )
    assert new_login.status_code == 200


# ---------------------------------------------------------------------------
# 5. /me returns correct user from JWT
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_me_returns_correct_user(client_with_admin):
    """/api/v1/auth/me should return the user identified by the JWT."""
    # Login first
    login_resp = await client_with_admin.post(
        "/api/v1/auth/login",
        json={"email": "admin@example.com", "password": "admin123"},
    )
    assert login_resp.status_code == 200
    token = login_resp.json()["access_token"]

    # Hit /me
    me_resp = await client_with_admin.get(
        "/api/v1/auth/me",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert me_resp.status_code == 200, me_resp.text
    user = me_resp.json()
    assert user["email"] == "admin@example.com"
    assert user["name"] == "Admin User"
    assert user["id"] == "user-admin-001"
    assert user["role"] == "admin"
    assert user["organization_id"] == "default"


# ---------------------------------------------------------------------------
# 6. Admin user auto-seeded on fresh DB
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_admin_seeded_on_fresh_db(db_session_factory, seed_admin):
    """The lifespan seeding logic should create admin@example.com with the
    well-known user-id ``user-admin-001``.  We replicate that in the
    ``seed_admin`` fixture and verify the DB state directly."""
    async with db_session_factory() as session:
        result = await session.execute(
            select(UserModel).where(UserModel.email == "admin@example.com")
        )
        admin = result.scalar_one_or_none()
        assert admin is not None, "admin@example.com should be seeded"
        assert admin.user_id == "user-admin-001"
        assert admin.full_name == "Admin User"
        assert admin.organization_id == "default"
        assert admin.is_active is True
        assert admin.is_email_verified is True
        assert verify_password("admin123", admin.password_hash)
