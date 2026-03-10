"""
Authentication V2 - Using Core Auth Module

API key authentication for agent orchestration using core/auth.
"""
import sys
import os

# Add core to path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../../../..")))

from fastapi import Header, HTTPException, Depends
from typing import Optional
from uuid import UUID

from core.auth import get_auth_manager, AuthMethod
from backend.shared.config import get_settings


# Get auth manager
auth_manager = get_auth_manager()


# ============================================================================
# API Key Authentication
# ============================================================================

async def verify_api_key(api_key: str = Header(None, alias="X-API-Key")) -> dict:
    """
    Verify API key is valid using core/auth.

    Args:
        api_key: API key from X-API-Key header

    Returns:
        User context dict with user_id and permissions

    Raises:
        HTTPException: If API key is invalid
    """
    settings = get_settings()

    # For MVP, allow requests without API key in development
    if settings.DEBUG and not api_key:
        return {
            "user_id": "debug",
            "agent_id": None,
            "permissions": ["*"],
            "auth_method": "debug"
        }

    if not api_key:
        raise HTTPException(
            status_code=401,
            detail="Missing API key. Include X-API-Key header."
        )

    try:
        # Validate using core/auth
        user = await auth_manager.validate_api_key(api_key)

        if not user:
            raise HTTPException(
                status_code=401,
                detail="Invalid API key"
            )

        # Extract agent_id from metadata
        agent_id = user.get('metadata', {}).get('agent_id')

        return {
            "user_id": user['user_id'],
            "agent_id": agent_id,
            "permissions": user.get('permissions', []),
            "auth_method": "api_key"
        }

    except Exception as e:
        raise HTTPException(
            status_code=401,
            detail=f"Authentication failed: {str(e)}"
        )


async def verify_agent_access(
    agent_id: UUID,
    api_key: str = Header(None, alias="X-API-Key")
) -> dict:
    """
    Verify API key and check agent ownership.

    Args:
        agent_id: Agent ID to verify access for
        api_key: API key from header

    Returns:
        User context dict

    Raises:
        HTTPException: If not authorized
    """
    user = await verify_api_key(api_key)

    # Check if user owns this agent
    user_agent_id = user.get('agent_id')

    if user_agent_id and str(user_agent_id) != str(agent_id):
        # User has an agent ID but it doesn't match
        raise HTTPException(
            status_code=403,
            detail="Not authorized to access this agent"
        )

    # Admin users (no specific agent_id) can access all agents
    if user.get('user_id') == 'debug' or '*' in user.get('permissions', []):
        return user

    # If user has specific agent_id, must match
    if user_agent_id and str(user_agent_id) == str(agent_id):
        return user

    raise HTTPException(
        status_code=403,
        detail="Not authorized to access this agent"
    )


# ============================================================================
# API Key Management
# ============================================================================

async def create_agent_api_key(
    agent_id: UUID,
    agent_name: str,
    permissions: Optional[list] = None
) -> str:
    """
    Create API key for an agent using core/auth.

    Args:
        agent_id: Agent UUID
        agent_name: Agent name for identification
        permissions: Optional list of permissions

    Returns:
        API key string
    """
    # Create API key with agent metadata
    api_key = await auth_manager.create_api_key(
        user_id=str(agent_id),
        key_name=f"agent-{agent_name}",
        permissions=permissions or ["agent:*"],
        metadata={
            "agent_id": str(agent_id),
            "agent_name": agent_name,
            "created_for": "agent-orchestration"
        }
    )

    return api_key


async def revoke_agent_api_key(api_key: str) -> bool:
    """
    Revoke an agent's API key.

    Args:
        api_key: API key to revoke

    Returns:
        True if revoked successfully
    """
    return await auth_manager.revoke_api_key(api_key)


async def list_agent_api_keys(agent_id: UUID) -> list:
    """
    List all API keys for an agent.

    Args:
        agent_id: Agent UUID

    Returns:
        List of API key metadata (without actual keys)
    """
    # This would require adding a method to core/auth to list keys by user_id
    # For now, return empty list
    # TODO: Implement in core/auth
    return []


# ============================================================================
# Permission Checks
# ============================================================================

def has_permission(user: dict, permission: str) -> bool:
    """
    Check if user has a specific permission.

    Args:
        user: User context from verify_api_key
        permission: Permission string (e.g., "agent:create")

    Returns:
        True if user has permission
    """
    permissions = user.get('permissions', [])

    # Check for wildcard
    if '*' in permissions:
        return True

    # Check for exact match
    if permission in permissions:
        return True

    # Check for prefix match (e.g., "agent:*" matches "agent:create")
    permission_parts = permission.split(':')
    for perm in permissions:
        if perm.endswith(':*'):
            prefix = perm[:-2]
            if permission.startswith(prefix):
                return True

    return False


def require_permission(permission: str):
    """
    Dependency for requiring a specific permission.

    Usage:
        @app.post("/admin/endpoint")
        async def admin_endpoint(user: dict = Depends(require_permission("admin:*"))):
            ...
    """
    async def check_permission(user: dict = Depends(verify_api_key)):
        if not has_permission(user, permission):
            raise HTTPException(
                status_code=403,
                detail=f"Missing required permission: {permission}"
            )
        return user

    return check_permission
