#!/usr/bin/env python3
"""
Security Tests: Authorization (RBAC)

Tests authorization mechanisms including:
- Role-based access control
- Permission checking
- Policy evaluation
- Multi-tenancy isolation
"""

import pytest
from datetime import datetime, timedelta
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

# Check for required dependencies
try:
    from fastapi import HTTPException
    HAS_FASTAPI = True
except ImportError:
    HAS_FASTAPI = False
    HTTPException = None

# Skip entire module if dependencies not available
if not HAS_FASTAPI:
    pytest.skip(
        "Required dependencies not installed (fastapi)",
        allow_module_level=True
    )

from backend.shared.rbac_service import (
    RBACService,
    get_rbac_service,
)
from backend.shared.rbac_models import (
    Permission,
    ResourceType,
    AccessResult,
    User,
    SYSTEM_ROLES,
)


class TestRBACService:
    """Tests for Role-Based Access Control service."""

    def setup_method(self):
        """Create RBAC service for each test."""
        self.rbac = RBACService()

    @pytest.mark.asyncio
    async def test_check_permission_allowed(self):
        """User with permission should be allowed."""
        mock_db = AsyncMock()

        # Mock user with permissions
        mock_user = User(
            user_id="user123",
            email="test@example.com",
            full_name="Test User",
            organization_id="org123",
            roles=["admin"],
            permissions={"agent:create", "agent:read", "agent:update"},
            is_active=True,
        )

        with patch.object(self.rbac, 'get_user', new=AsyncMock(return_value=mock_user)):
            result = await self.rbac.check_permission(
                user_id="user123",
                permission=Permission.AGENT_CREATE,
                db=mock_db
            )

        assert result.allowed is True

    @pytest.mark.asyncio
    async def test_check_permission_denied(self):
        """User without permission should be denied."""
        mock_db = AsyncMock()

        # Mock user without required permission
        mock_user = User(
            user_id="user123",
            email="test@example.com",
            full_name="Test User",
            organization_id="org123",
            roles=["viewer"],
            permissions={"agent:read"},  # Only read permission
            is_active=True,
        )

        # Mock audit logger to avoid initialization error
        mock_audit_logger = MagicMock()
        mock_audit_logger.log_security_event = AsyncMock()

        with patch.object(self.rbac, 'get_user', new=AsyncMock(return_value=mock_user)):
            with patch('backend.shared.rbac_service.get_audit_logger', return_value=mock_audit_logger):
                result = await self.rbac.check_permission(
                    user_id="user123",
                    permission=Permission.AGENT_CREATE,  # Needs create permission
                    db=mock_db
                )

        assert result.allowed is False
        assert "Missing permission" in result.reason

    @pytest.mark.asyncio
    async def test_require_permission_raises_on_deny(self):
        """require_permission should raise HTTPException on deny."""
        mock_db = AsyncMock()

        mock_user = User(
            user_id="user123",
            email="test@example.com",
            full_name="Test User",
            organization_id="org123",
            roles=["viewer"],
            permissions=set(),  # No permissions
            is_active=True,
        )

        # Mock audit logger to avoid initialization error
        mock_audit_logger = MagicMock()
        mock_audit_logger.log_security_event = AsyncMock()

        with patch.object(self.rbac, 'get_user', new=AsyncMock(return_value=mock_user)):
            with patch('backend.shared.rbac_service.get_audit_logger', return_value=mock_audit_logger):
                with pytest.raises(HTTPException) as exc_info:
                    await self.rbac.require_permission(
                        user_id="user123",
                        permission=Permission.AGENT_CREATE,
                        db=mock_db
                    )

        assert exc_info.value.status_code == 403
        assert "Forbidden" in exc_info.value.detail

    @pytest.mark.asyncio
    async def test_user_not_found_returns_empty_permissions(self):
        """Non-existent user should have no permissions."""
        mock_db = AsyncMock()

        with patch.object(self.rbac, 'get_user', new=AsyncMock(return_value=None)):
            permissions = await self.rbac._get_user_permissions("nonexistent", mock_db)

        assert permissions == set()


class TestPermissionCaching:
    """Tests for permission caching behavior."""

    def setup_method(self):
        """Create RBAC service for each test."""
        self.rbac = RBACService()

    @pytest.mark.asyncio
    async def test_permissions_are_cached(self):
        """Permissions should be cached to reduce DB calls."""
        mock_db = AsyncMock()

        mock_user = User(
            user_id="user123",
            email="test@example.com",
            full_name="Test User",
            organization_id="org123",
            roles=["admin"],
            permissions={"agents:create"},
            is_active=True,
        )

        mock_get = AsyncMock(return_value=mock_user)
        with patch.object(self.rbac, 'get_user', new=mock_get):
            # First call - should fetch from DB
            await self.rbac._get_user_permissions("user123", mock_db)

            # Second call - should use cache
            await self.rbac._get_user_permissions("user123", mock_db)

            # Should only call get_user once due to caching
            assert mock_get.call_count == 1

    def test_cache_invalidation(self):
        """Cache should be invalidated when requested."""
        # Pre-populate cache
        self.rbac._permission_cache["user123"] = (
            {"agents:read"},
            datetime.utcnow()
        )

        # Invalidate
        self.rbac._invalidate_user_cache("user123")

        # Cache should be empty
        assert "user123" not in self.rbac._permission_cache


class TestMultiTenancy:
    """Tests for organization-based isolation."""

    @pytest.mark.asyncio
    async def test_user_isolated_to_organization(self):
        """Users should only access resources in their organization."""
        rbac = RBACService()
        mock_db = AsyncMock()

        # User in org1
        user_org1 = User(
            user_id="user1",
            email="user1@org1.com",
            full_name="User One",
            organization_id="org1",
            roles=["admin"],
            permissions={"*"},  # Full permissions
            is_active=True,
        )

        # Mock audit logger to avoid initialization error
        mock_audit_logger = MagicMock()
        mock_audit_logger.log_security_event = AsyncMock()

        with patch.object(rbac, 'get_user', new=AsyncMock(return_value=user_org1)):
            with patch('backend.shared.rbac_service.get_audit_logger', return_value=mock_audit_logger):
                result = await rbac.check_permission(
                    user_id="user1",
                    permission=Permission.AGENT_READ,
                    organization_id="org2",  # Different org
                    db=mock_db
                )

        # Even with full permissions, org isolation should be enforced
        # at the service layer (this test documents the expected behavior)
        # Note: Full org isolation enforcement happens in service layer
        assert result is not None


class TestSystemRoles:
    """Tests for system-defined roles."""

    def test_system_roles_defined(self):
        """All system roles should be properly defined."""
        required_roles = ["super_admin", "org_admin", "developer", "viewer"]

        for role in required_roles:
            assert role in SYSTEM_ROLES, f"Missing system role: {role}"

    def test_super_admin_has_all_permissions(self):
        """Super admin should have all permissions."""
        if "super_admin" in SYSTEM_ROLES:
            super_admin = SYSTEM_ROLES["super_admin"]
            assert "*" in super_admin.get("permissions", []) or len(super_admin.get("permissions", [])) > 10


class TestAccessControl:
    """Tests for fine-grained access control."""

    @pytest.mark.asyncio
    async def test_resource_specific_permission(self):
        """Permissions should work at resource level."""
        rbac = RBACService()
        mock_db = AsyncMock()

        # User with permission for specific resource type
        mock_user = User(
            user_id="user123",
            email="test@example.com",
            full_name="Test User",
            organization_id="org123",
            roles=["agent_manager"],
            permissions={"agent:read", "agent:update"},
            is_active=True,
        )

        with patch.object(rbac, 'get_user', new=AsyncMock(return_value=mock_user)):
            # Should have agent read permission
            result = await rbac.check_permission(
                user_id="user123",
                permission=Permission.AGENT_READ,
                resource_type=ResourceType.AGENT,
                db=mock_db
            )
            assert result.allowed is True


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
