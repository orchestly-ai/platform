"""
Plan Enforcement Dependencies

FastAPI dependencies for enforcing free/paid tier limits:
- User count limits per organization plan
- Agent count limits per organization plan
- Feature gating for paid-only features
- Enterprise license gating for enterprise-only features
"""

import logging
from typing import Callable

from fastapi import Depends, HTTPException
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from backend.database.session import get_db
from backend.shared.rbac_models import OrganizationModel, UserModel, PAID_FEATURES, ENTERPRISE_FEATURES

# Import enterprise license check with graceful fallback
# When the ee/ package is not present (e.g. Apache-only distribution),
# enterprise features are simply disabled.
try:
    from ee.license import has_enterprise_license
except ImportError:
    def has_enterprise_license() -> bool:
        return False

logger = logging.getLogger(__name__)


async def _get_org(org_id: str, db: AsyncSession) -> OrganizationModel:
    """Fetch organization or raise 404."""
    result = await db.execute(
        select(OrganizationModel).where(OrganizationModel.organization_id == org_id)
    )
    org = result.scalar_one_or_none()
    if not org:
        raise HTTPException(status_code=404, detail="Organization not found")
    return org


async def enforce_user_limit(org_id: str, db: AsyncSession) -> None:
    """
    Raise 403 if the organization has reached its max_users limit.

    Usage in routes:
        @router.post("/register")
        async def register(
            ...,
            db: AsyncSession = Depends(get_db),
        ):
            await enforce_user_limit("default", db)
            ...
    """
    org = await _get_org(org_id, db)

    result = await db.execute(
        select(func.count(UserModel.user_id)).where(
            UserModel.organization_id == org_id
        )
    )
    user_count = result.scalar() or 0

    if user_count >= org.max_users:
        raise HTTPException(
            status_code=403,
            detail={
                "error": "plan_limit_reached",
                "message": f"Your plan ({org.plan}) allows a maximum of {org.max_users} user(s). Upgrade to add more.",
                "limit": "max_users",
                "current": user_count,
                "max": org.max_users,
                "plan": org.plan,
            },
        )


async def enforce_agent_limit(org_id: str, db: AsyncSession) -> None:
    """
    Raise 403 if the organization has reached its max_agents limit.

    Counts agents from the agents table scoped to the organization.
    """
    org = await _get_org(org_id, db)

    # Import here to avoid circular imports — AgentModel lives in database.models
    from backend.database.models import AgentModel

    result = await db.execute(
        select(func.count(AgentModel.agent_id)).where(
            AgentModel.organization_id == org_id
        )
    )
    agent_count = result.scalar() or 0

    if agent_count >= org.max_agents:
        raise HTTPException(
            status_code=403,
            detail={
                "error": "plan_limit_reached",
                "message": f"Your plan ({org.plan}) allows a maximum of {org.max_agents} agent(s). Upgrade to add more.",
                "limit": "max_agents",
                "current": agent_count,
                "max": org.max_agents,
                "plan": org.plan,
            },
        )


async def enforce_feature(feature_name: str, org_id: str, db: AsyncSession) -> None:
    """
    Raise 403 if the requested feature is not enabled.

    Logic:
    - If the feature is NOT in ENTERPRISE_FEATURES, it's free — always allow.
    - If the feature IS in ENTERPRISE_FEATURES, check the enterprise license.

    Usage in routes:
        @router.get("/team")
        async def list_team(...):
            await enforce_feature("team_management", org_id, db)
            ...
    """
    # Free features are always available
    if feature_name not in ENTERPRISE_FEATURES:
        return

    # Enterprise features require an active license
    if not has_enterprise_license():
        raise HTTPException(
            status_code=403,
            detail={
                "error": "enterprise_required",
                "message": f"The '{feature_name}' feature requires an Orchestly Enterprise license.",
                "feature": feature_name,
            },
        )


def enforce_enterprise_feature(feature_name: str) -> None:
    """
    Raise 403 if the enterprise license is not active.

    This is a synchronous, non-DB check — it only verifies that the
    ORCHESTLY_LICENSE_KEY environment variable contains a valid key.

    Usage in routes:
        @router.get("/sso/config")
        async def get_sso_config(...):
            enforce_enterprise_feature("sso_saml")
            ...
    """
    if feature_name not in ENTERPRISE_FEATURES:
        logger.warning("enforce_enterprise_feature called with unknown feature: %s", feature_name)

    if not has_enterprise_license():
        raise HTTPException(
            status_code=403,
            detail={
                "error": "enterprise_required",
                "message": f"The '{feature_name}' feature requires an Orchestly Enterprise license. "
                           "Set ORCHESTLY_LICENSE_KEY to activate enterprise features.",
                "feature": feature_name,
            },
        )
