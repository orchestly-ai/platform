"""
RBAC Service

Permission checking and enforcement with caching.
"""

from typing import Optional, List, Set, Dict, Any
from functools import wraps
import logging
from datetime import datetime, timedelta

from fastapi import HTTPException, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from sqlalchemy.orm import selectinload

from backend.shared.rbac_models import (
    Permission, ResourceType, AccessRequest, AccessResult,
    User, UserModel, RoleModel, OrganizationModel,
    SYSTEM_ROLES
)
from backend.shared.audit_logger import get_audit_logger
from backend.shared.audit_models import AuditEvent, AuditEventType, AuditSeverity

logger = logging.getLogger(__name__)


class RBACService:
    """
    Role-Based Access Control service.

    Features:
    - Permission checking
    - Role management
    - Organization isolation (multi-tenancy)
    - Permission caching
    - Audit logging
    """

    def __init__(self):
        self._permission_cache: Dict[str, tuple[Set[str], datetime]] = {}
        self._cache_ttl = timedelta(seconds=30)

    async def check_permission(
        self,
        user_id: str,
        permission: Permission,
        resource_type: Optional[ResourceType] = None,
        resource_id: Optional[str] = None,
        organization_id: Optional[str] = None,
        db: AsyncSession = None
    ) -> AccessResult:
        """
        Check if user has permission.

        Args:
            user_id: User ID
            permission: Required permission
            resource_type: Optional resource type for context
            resource_id: Optional specific resource ID
            organization_id: Optional organization ID for multi-tenancy
            db: Database session

        Returns:
            AccessResult with allowed=True/False
        """
        # Get user permissions (with caching)
        permissions = await self._get_user_permissions(user_id, db)

        # Check if user has the permission (wildcard "*" grants all permissions)
        allowed = "*" in permissions or permission.value in permissions

        if not allowed:
            logger.warning(f"Access denied: user={user_id}, permission={permission.value}")

            # Log security event
            if db:
                audit_logger = get_audit_logger()
                await audit_logger.log_security_event(
                    event_type=AuditEventType.SECURITY_ACCESS_DENIED,
                    description=f"User {user_id} denied {permission.value} on {resource_type}:{resource_id}",
                    severity=AuditSeverity.WARNING,
                    resource_type=resource_type.value if resource_type else None,
                    resource_id=resource_id,
                    metadata={
                        "required_permission": permission.value,
                        "user_id": user_id
                    },
                    db=db
                )

            return AccessResult(
                allowed=False,
                reason=f"Missing permission: {permission.value}",
                required_permission=permission
            )

        return AccessResult(allowed=True)

    async def require_permission(
        self,
        user_id: str,
        permission: Permission,
        resource_type: Optional[ResourceType] = None,
        resource_id: Optional[str] = None,
        db: AsyncSession = None
    ):
        """
        Require permission or raise HTTPException.

        Usage:
            await rbac.require_permission(user_id, Permission.AGENT_CREATE, db=db)
        """
        result = await self.check_permission(
            user_id, permission, resource_type, resource_id, db=db
        )

        if not result.allowed:
            raise HTTPException(
                status_code=403,
                detail=f"Forbidden: {result.reason}"
            )

    async def get_user(
        self,
        user_id: str,
        db: AsyncSession
    ) -> Optional[User]:
        """Get user with roles and permissions"""
        stmt = select(UserModel).where(
            UserModel.user_id == user_id
        ).options(selectinload(UserModel.roles))

        result = await db.execute(stmt)
        user_model = result.scalar_one_or_none()

        if not user_model:
            return None

        # Get all permissions from roles
        permissions = set()
        role_names = []
        for role in user_model.roles:
            role_names.append(role.name)
            permissions.update(role.permissions)

        # Grant wildcard permissions for admin users who may not have
        # RBAC roles assigned yet (e.g., seeded admin user with role column = "admin")
        if hasattr(user_model, 'role') and user_model.role == "admin" and not permissions:
            permissions.add("*")

        return User(
            user_id=user_model.user_id,
            email=user_model.email,
            full_name=user_model.full_name,
            organization_id=user_model.organization_id,
            roles=role_names,
            permissions=permissions,
            is_active=user_model.is_active,
            metadata=user_model.metadata
        )

    async def create_user(
        self,
        user_id: str,
        email: str,
        full_name: Optional[str],
        organization_id: str,
        assign_default_role: bool = True,
        db: AsyncSession = None
    ) -> User:
        """Create new user"""
        user_model = UserModel(
            user_id=user_id,
            email=email,
            full_name=full_name,
            organization_id=organization_id
        )

        db.add(user_model)

        # Assign default role
        if assign_default_role:
            stmt = select(RoleModel).where(
                RoleModel.is_default == True,
                RoleModel.organization_id == organization_id
            )
            result = await db.execute(stmt)
            default_role = result.scalar_one_or_none()

            if default_role:
                user_model.roles.append(default_role)

        await db.commit()
        await db.refresh(user_model, ["roles"])

        return await self.get_user(user_id, db)

    async def assign_role(
        self,
        user_id: str,
        role_name: str,
        assigned_by: str,
        db: AsyncSession
    ):
        """Assign role to user"""
        # Get user
        stmt = select(UserModel).where(UserModel.user_id == user_id)
        result = await db.execute(stmt)
        user = result.scalar_one_or_none()

        if not user:
            raise ValueError(f"User not found: {user_id}")

        # Get role
        stmt = select(RoleModel).where(
            RoleModel.name == role_name,
            RoleModel.organization_id == user.organization_id
        )
        result = await db.execute(stmt)
        role = result.scalar_one_or_none()

        if not role:
            raise ValueError(f"Role not found: {role_name}")

        # Assign role
        if role not in user.roles:
            user.roles.append(role)
            await db.commit()

            # Clear cache
            self._invalidate_user_cache(user_id)

            # Log audit event
            audit_logger = get_audit_logger()
            await audit_logger.log_resource_event(
                event_type=AuditEventType.USER_ROLE_CHANGED,
                action="assign_role",
                resource_type="user",
                resource_id=user_id,
                description=f"Assigned role {role_name} to user {user.email}",
                changes={"role_added": role_name},
                db=db
            )

    async def remove_role(
        self,
        user_id: str,
        role_name: str,
        db: AsyncSession
    ):
        """Remove role from user"""
        # Get user with roles
        stmt = select(UserModel).where(
            UserModel.user_id == user_id
        ).options(selectinload(UserModel.roles))
        result = await db.execute(stmt)
        user = result.scalar_one_or_none()

        if not user:
            raise ValueError(f"User not found: {user_id}")

        # Find and remove role
        role_to_remove = None
        for role in user.roles:
            if role.name == role_name:
                role_to_remove = role
                break

        if role_to_remove:
            user.roles.remove(role_to_remove)
            await db.commit()

            # Clear cache
            self._invalidate_user_cache(user_id)

            # Log audit event
            audit_logger = get_audit_logger()
            await audit_logger.log_resource_event(
                event_type=AuditEventType.USER_ROLE_CHANGED,
                action="remove_role",
                resource_type="user",
                resource_id=user_id,
                description=f"Removed role {role_name} from user {user.email}",
                changes={"role_removed": role_name},
                db=db
            )

    async def create_role(
        self,
        name: str,
        description: str,
        permissions: List[str],
        organization_id: Optional[str],
        created_by: str,
        db: AsyncSession
    ) -> RoleModel:
        """Create custom role"""
        role = RoleModel(
            name=name,
            description=description,
            permissions=permissions,
            organization_id=organization_id,
            is_system_role=False,
            created_by=created_by
        )

        db.add(role)
        await db.commit()
        await db.refresh(role)

        # Log audit event
        audit_logger = get_audit_logger()
        await audit_logger.log_resource_event(
            event_type=AuditEventType.USER_CREATED,
            action="create",
            resource_type="role",
            resource_id=str(role.role_id),
            description=f"Created role {name} with {len(permissions)} permissions",
            request_data={"permissions": permissions},
            db=db
        )

        return role

    async def _get_user_permissions(
        self,
        user_id: str,
        db: AsyncSession
    ) -> Set[str]:
        """Get user permissions with caching"""
        # Check cache
        if user_id in self._permission_cache:
            permissions, cached_at = self._permission_cache[user_id]
            if datetime.utcnow() - cached_at < self._cache_ttl:
                return permissions

        # Fetch from database
        user = await self.get_user(user_id, db)
        if not user:
            return set()

        permissions = user.permissions

        # Cache
        self._permission_cache[user_id] = (permissions, datetime.utcnow())

        return permissions

    def _invalidate_user_cache(self, user_id: str):
        """Invalidate permission cache for user"""
        if user_id in self._permission_cache:
            del self._permission_cache[user_id]


# Global RBAC service instance
_rbac_service: Optional[RBACService] = None


def get_rbac_service() -> RBACService:
    """Get the global RBAC service instance"""
    global _rbac_service
    if _rbac_service is None:
        _rbac_service = RBACService()
    return _rbac_service


# Dependency for FastAPI routes
async def get_current_user(
    user_id: str,  # From auth middleware
    db: AsyncSession
) -> User:
    """
    FastAPI dependency to get current user.

    Usage:
        @router.get("/protected")
        async def protected_route(
            user: User = Depends(get_current_user),
            db: AsyncSession = Depends(get_db)
        ):
            ...
    """
    rbac = get_rbac_service()
    user = await rbac.get_user(user_id, db)

    if not user:
        raise HTTPException(status_code=401, detail="User not found")

    if not user.is_active:
        raise HTTPException(status_code=403, detail="User account is inactive")

    return user


# Decorator for permission checking
def requires_permission(permission: Permission):
    """
    Decorator to require permission on route.

    Usage:
        @router.post("/agents")
        @requires_permission(Permission.AGENT_CREATE)
        async def create_agent(
            user: User = Depends(get_current_user),
            db: AsyncSession = Depends(get_db)
        ):
            ...
    """
    def decorator(func):
        @wraps(func)
        async def wrapper(*args, **kwargs):
            # Extract user and db from kwargs
            user = kwargs.get('user')
            db = kwargs.get('db')

            if not user or not db:
                raise ValueError("requires_permission decorator requires 'user' and 'db' dependencies")

            # Check permission
            rbac = get_rbac_service()
            await rbac.require_permission(user.user_id, permission, db=db)

            # Call original function
            return await func(*args, **kwargs)

        return wrapper
    return decorator
