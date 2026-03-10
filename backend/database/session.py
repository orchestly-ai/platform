"""
Database Session Management

SQLAlchemy session configuration and database connection management.
"""

import os
from sqlalchemy import create_engine, event
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker
from sqlalchemy.orm import sessionmaker, declarative_base
from typing import AsyncGenerator

from backend.shared.config import get_settings


# Base class for all models
Base = declarative_base()

# Settings
settings = get_settings()

# Check if running in test mode (use SQLite)
USE_SQLITE = os.environ.get("USE_SQLITE", "").lower() in ("true", "1", "yes")

if USE_SQLITE:
    # Teach SQLite how to compile PostgreSQL-specific column types.
    # This allows Base.metadata.create_all to succeed with ALL models,
    # even those that use ARRAY, JSONB, INET, or PG_UUID columns.
    from sqlalchemy.dialects.sqlite.base import SQLiteTypeCompiler

    _orig_array = getattr(SQLiteTypeCompiler, "visit_ARRAY", None)
    if _orig_array is None:
        SQLiteTypeCompiler.visit_ARRAY = lambda self, type_, **kw: "JSON"

    _orig_jsonb = getattr(SQLiteTypeCompiler, "visit_JSONB", None)
    if _orig_jsonb is None:
        SQLiteTypeCompiler.visit_JSONB = lambda self, type_, **kw: "JSON"

    _orig_inet = getattr(SQLiteTypeCompiler, "visit_INET", None)
    if _orig_inet is None:
        SQLiteTypeCompiler.visit_INET = lambda self, type_, **kw: "VARCHAR(45)"

    # PostgreSQL UUID → VARCHAR(36) on SQLite
    _orig_uuid = getattr(SQLiteTypeCompiler, "visit_UUID", None)
    if _orig_uuid is None:
        SQLiteTypeCompiler.visit_UUID = lambda self, type_, **kw: "VARCHAR(36)"

    # Use SQLite for testing - works without PostgreSQL
    database_url = "sqlite+aiosqlite:///./test_workflow.db"
    engine = create_async_engine(
        database_url,
        echo=settings.DEBUG,
        # SQLite doesn't support pool_size, max_overflow, pool_pre_ping
    )
else:
    # Create async engine for PostgreSQL
    # Convert postgresql:// to postgresql+asyncpg://
    database_url = settings.DATABASE_URL.replace("postgresql://", "postgresql+asyncpg://")

    engine = create_async_engine(
        database_url,
        echo=settings.DEBUG,
        pool_size=10,
        max_overflow=20,
        pool_pre_ping=True,  # Verify connections before using
    )

# Async session factory
AsyncSessionLocal = async_sessionmaker(
    engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autocommit=False,
    autoflush=False,
)


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """
    Dependency for getting database session.

    Usage in FastAPI:
        @app.get("/items")
        async def get_items(db: AsyncSession = Depends(get_db)):
            result = await db.execute(select(Item))
            return result.scalars().all()
    """
    async with AsyncSessionLocal() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()


async def init_db():
    """Initialize database tables."""
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)


async def close_db():
    """Close database connections."""
    await engine.dispose()


async def reset_connection_pool():
    """
    Reset the connection pool to clear asyncpg prepared statement cache.

    This is needed when database schema changes (ALTER TABLE, ADD COLUMN)
    because asyncpg caches prepared statements with the old schema.
    """
    await engine.dispose()


# Compatibility alias for demos expecting SessionLocal
SessionLocal = AsyncSessionLocal

