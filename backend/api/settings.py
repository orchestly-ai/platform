"""
Settings API Router

Provides endpoints for:
- Team member management (invite, update role, remove)
- API key management (create, revoke, list)
- Organization settings

Now with database persistence!
"""

from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel, EmailStr
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_
from typing import List, Optional
from datetime import datetime, timedelta
import secrets
import hashlib

from backend.database.session import get_db
from backend.database.models import TeamMemberModel, APIKeyModel
from backend.shared.rbac_models import OrganizationModel
from backend.shared.plan_enforcement import enforce_user_limit, enforce_feature

router = APIRouter(prefix="/api/v1/settings", tags=["settings"])


# ============================================================================
# Request/Response Models
# ============================================================================

class TeamMemberInvite(BaseModel):
    email: EmailStr
    name: Optional[str] = None
    role: str = "member"  # admin, member, viewer


class TeamMemberUpdate(BaseModel):
    name: Optional[str] = None
    role: Optional[str] = None


class TeamMemberResponse(BaseModel):
    id: int
    email: str
    name: Optional[str]
    role: str
    status: str
    joined_at: Optional[str]
    last_seen_at: Optional[str]

    class Config:
        from_attributes = True


class APIKeyCreate(BaseModel):
    name: str
    permissions: Optional[List[str]] = None
    expires_in_days: Optional[int] = None


class APIKeyResponse(BaseModel):
    id: int
    name: str
    key_prefix: str
    permissions: Optional[List[str]]
    created_at: str
    expires_at: Optional[str]
    last_used_at: Optional[str]
    is_active: bool

    class Config:
        from_attributes = True


class APIKeyCreated(APIKeyResponse):
    key: str  # Full key - only returned on creation


class OrganizationSettings(BaseModel):
    name: Optional[str] = None
    logo_url: Optional[str] = None
    settings: Optional[dict] = None


# Helper functions
async def get_organization_id() -> str:
    """Get current user's organization ID. For now, return default org."""
    return "default"


# ============================================================================
# Team Member Endpoints
# ============================================================================

@router.get("/team", response_model=List[TeamMemberResponse])
async def list_team_members(
    db: AsyncSession = Depends(get_db),
    organization_id: str = Depends(get_organization_id),
):
    """List all team members in the organization."""
    await enforce_feature("team_management", organization_id, db)

    stmt = select(TeamMemberModel).where(TeamMemberModel.organization_id == organization_id)
    result = await db.execute(stmt)
    members = result.scalars().all()

    return [
        TeamMemberResponse(
            id=m.id,
            email=m.email,
            name=m.name,
            role=m.role,
            status=m.status,
            joined_at=m.joined_at.isoformat() if m.joined_at else None,
            last_seen_at=m.last_seen_at.isoformat() if m.last_seen_at else None,
        )
        for m in members
    ]


@router.post("/team", response_model=TeamMemberResponse)
async def invite_team_member(
    invite: TeamMemberInvite,
    db: AsyncSession = Depends(get_db),
    organization_id: str = Depends(get_organization_id),
):
    """Invite a new team member."""
    await enforce_user_limit(organization_id, db)

    # Check if email already exists
    stmt = select(TeamMemberModel).where(TeamMemberModel.email == invite.email)
    result = await db.execute(stmt)
    existing = result.scalar_one_or_none()

    if existing:
        raise HTTPException(status_code=400, detail="Email already exists")

    # Create new member
    member = TeamMemberModel(
        organization_id=organization_id,
        user_id=f"user_{secrets.token_hex(8)}",
        email=invite.email,
        name=invite.name,
        role=invite.role,
        status="invited",
        invited_at=datetime.utcnow(),
    )
    db.add(member)
    await db.commit()
    await db.refresh(member)

    return TeamMemberResponse(
        id=member.id,
        email=member.email,
        name=member.name,
        role=member.role,
        status=member.status,
        joined_at=member.joined_at.isoformat() if member.joined_at else None,
        last_seen_at=member.last_seen_at.isoformat() if member.last_seen_at else None,
    )


@router.put("/team/{member_id}", response_model=TeamMemberResponse)
async def update_team_member(
    member_id: int,
    update: TeamMemberUpdate,
    db: AsyncSession = Depends(get_db),
):
    """Update a team member's role or name."""
    stmt = select(TeamMemberModel).where(TeamMemberModel.id == member_id)
    result = await db.execute(stmt)
    member = result.scalar_one_or_none()

    if not member:
        raise HTTPException(status_code=404, detail="Team member not found")

    if update.name is not None:
        member.name = update.name
    if update.role is not None:
        member.role = update.role

    await db.commit()
    await db.refresh(member)

    return TeamMemberResponse(
        id=member.id,
        email=member.email,
        name=member.name,
        role=member.role,
        status=member.status,
        joined_at=member.joined_at.isoformat() if member.joined_at else None,
        last_seen_at=member.last_seen_at.isoformat() if member.last_seen_at else None,
    )


@router.delete("/team/{member_id}")
async def remove_team_member(
    member_id: int,
    db: AsyncSession = Depends(get_db),
    organization_id: str = Depends(get_organization_id),
):
    """Remove a team member from the organization."""
    # Get member
    stmt = select(TeamMemberModel).where(
        and_(
            TeamMemberModel.id == member_id,
            TeamMemberModel.organization_id == organization_id,
        )
    )
    result = await db.execute(stmt)
    member = result.scalar_one_or_none()

    if not member:
        raise HTTPException(status_code=404, detail="Team member not found")

    # Check if trying to remove last admin
    if member.role == "admin":
        stmt = select(TeamMemberModel).where(
            and_(
                TeamMemberModel.organization_id == organization_id,
                TeamMemberModel.role == "admin",
            )
        )
        result = await db.execute(stmt)
        admin_count = len(result.scalars().all())

        if admin_count <= 1:
            raise HTTPException(status_code=400, detail="Cannot remove the last admin")

    # Delete member
    await db.delete(member)
    await db.commit()

    return {"message": "Team member removed"}


# ============================================================================
# API Key Endpoints
# ============================================================================

@router.get("/api-keys", response_model=List[APIKeyResponse])
async def list_api_keys(
    db: AsyncSession = Depends(get_db),
    organization_id: str = Depends(get_organization_id),
):
    """List all API keys for the organization."""
    stmt = select(APIKeyModel).where(
        and_(
            APIKeyModel.organization_id == organization_id,
            APIKeyModel.is_active == True,
        )
    )
    result = await db.execute(stmt)
    api_keys = result.scalars().all()

    return [
        APIKeyResponse(
            id=k.id,
            name=k.name,
            key_prefix=k.key_prefix,
            permissions=k.permissions,
            created_at=k.created_at.isoformat(),
            expires_at=k.expires_at.isoformat() if k.expires_at else None,
            last_used_at=k.last_used_at.isoformat() if k.last_used_at else None,
            is_active=k.is_active,
        )
        for k in api_keys
    ]


@router.post("/api-keys", response_model=APIKeyCreated)
async def create_api_key(
    request: APIKeyCreate,
    db: AsyncSession = Depends(get_db),
    organization_id: str = Depends(get_organization_id),
):
    """Create a new API key."""
    await enforce_feature("api_keys", organization_id, db)

    # Generate key
    key = f"ak_{secrets.token_urlsafe(32)}"
    key_prefix = key[:12] + "..."
    key_hash = hashlib.sha256(key.encode()).hexdigest()

    # Calculate expiry
    expires_at = None
    if request.expires_in_days:
        expires_at = datetime.utcnow() + timedelta(days=request.expires_in_days)

    # Create API key
    api_key = APIKeyModel(
        organization_id=organization_id,
        name=request.name,
        key_prefix=key_prefix,
        key_hash=key_hash,
        permissions=request.permissions,
        is_active=True,
        created_at=datetime.utcnow(),
        expires_at=expires_at,
    )
    db.add(api_key)
    await db.commit()
    await db.refresh(api_key)

    # Also add to the global VALID_API_KEYS set used by auth (if available)
    try:
        from backend.api.main import VALID_API_KEYS
        VALID_API_KEYS.add(key)
    except (ImportError, AttributeError):
        pass

    return APIKeyCreated(
        id=api_key.id,
        name=api_key.name,
        key=key,  # Only return full key on creation
        key_prefix=api_key.key_prefix,
        permissions=api_key.permissions,
        created_at=api_key.created_at.isoformat(),
        expires_at=api_key.expires_at.isoformat() if api_key.expires_at else None,
        last_used_at=api_key.last_used_at.isoformat() if api_key.last_used_at else None,
        is_active=api_key.is_active,
    )


@router.delete("/api-keys/{key_id}")
async def revoke_api_key(
    key_id: int,
    db: AsyncSession = Depends(get_db),
    organization_id: str = Depends(get_organization_id),
):
    """Revoke an API key."""
    stmt = select(APIKeyModel).where(
        and_(
            APIKeyModel.id == key_id,
            APIKeyModel.organization_id == organization_id,
        )
    )
    result = await db.execute(stmt)
    api_key = result.scalar_one_or_none()

    if not api_key:
        raise HTTPException(status_code=404, detail="API key not found")

    api_key.is_active = False
    api_key.revoked_at = datetime.utcnow()

    await db.commit()

    return {"message": "API key revoked"}


# ============================================================================
# Organization Endpoints
# ============================================================================

@router.get("/organization")
async def get_organization(
    db: AsyncSession = Depends(get_db),
    organization_id: str = Depends(get_organization_id),
):
    """Get organization details."""
    stmt = select(OrganizationModel).where(OrganizationModel.organization_id == organization_id)
    result = await db.execute(stmt)
    org = result.scalar_one_or_none()

    if not org:
        raise HTTPException(status_code=404, detail="Organization not found")

    return {
        "id": org.organization_id,
        "name": org.name,
        "slug": org.slug,
        "plan": org.plan,
        "max_users": org.max_users,
        "max_agents": org.max_agents,
        "enabled_features": org.enabled_features or [],
        "settings": org.settings,
    }


@router.put("/organization")
async def update_organization(
    settings: OrganizationSettings,
    db: AsyncSession = Depends(get_db),
    organization_id: str = Depends(get_organization_id),
):
    """Update organization settings."""
    stmt = select(OrganizationModel).where(OrganizationModel.organization_id == organization_id)
    result = await db.execute(stmt)
    org = result.scalar_one_or_none()

    if not org:
        raise HTTPException(status_code=404, detail="Organization not found")

    if settings.name is not None:
        org.name = settings.name
    if settings.settings is not None:
        org.settings = settings.settings

    await db.commit()
    await db.refresh(org)

    return {
        "id": org.organization_id,
        "name": org.name,
        "slug": org.slug,
        "plan": org.plan,
        "settings": org.settings,
    }


# ============================================================================
# General Settings Endpoint
# ============================================================================

@router.get("")
async def get_settings(
    db: AsyncSession = Depends(get_db),
    organization_id: str = Depends(get_organization_id),
):
    """Get all settings (organization + computed values)."""
    stmt = select(OrganizationModel).where(OrganizationModel.organization_id == organization_id)
    result = await db.execute(stmt)
    org = result.scalar_one_or_none()

    if not org:
        raise HTTPException(status_code=404, detail="Organization not found")

    return {
        "organization": {
            "id": org.organization_id,
            "name": org.name,
            "slug": org.slug,
            "plan": org.plan,
        },
        "settings": org.settings,
    }


# ============================================================================
# API Key Validation Endpoint
# ============================================================================

from fastapi import Header

@router.post("/api-keys/verify")
async def verify_api_key(
    db: AsyncSession = Depends(get_db),
    x_api_key: str = Header(..., alias="X-API-Key"),
):
    """
    Verify an API key is valid.

    Returns 200 with key info if valid, 401 if invalid.
    Used by client applications to test their API key configuration.
    """
    if not x_api_key:
        raise HTTPException(status_code=401, detail="API key required")

    # Hash the provided key
    key_hash = hashlib.sha256(x_api_key.encode()).hexdigest()

    # Look up the key by hash
    stmt = select(APIKeyModel).where(
        and_(
            APIKeyModel.key_hash == key_hash,
            APIKeyModel.is_active == True,
        )
    )
    result = await db.execute(stmt)
    api_key = result.scalar_one_or_none()

    if not api_key:
        raise HTTPException(status_code=401, detail="Invalid API key")

    # Check if expired
    if api_key.expires_at and api_key.expires_at < datetime.utcnow():
        raise HTTPException(status_code=401, detail="API key has expired")

    # Update last used timestamp
    api_key.last_used_at = datetime.utcnow()
    await db.commit()

    return {
        "valid": True,
        "key_name": api_key.name,
        "organization_id": api_key.organization_id,
        "permissions": api_key.permissions,
    }


@router.put("")
async def update_settings(
    settings: dict,
    db: AsyncSession = Depends(get_db),
    organization_id: str = Depends(get_organization_id),
):
    """Update general settings."""
    stmt = select(OrganizationModel).where(OrganizationModel.organization_id == organization_id)
    result = await db.execute(stmt)
    org = result.scalar_one_or_none()

    if not org:
        raise HTTPException(status_code=404, detail="Organization not found")

    # Merge settings
    current_settings = org.settings or {}
    org.settings = {**current_settings, **settings}

    await db.commit()

    return {"success": True, "message": "Settings updated"}
