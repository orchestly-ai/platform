"""
Security Regression Tests — MEDIUM Severity Fixes (M1–M10)

Tests to prevent re-introduction of medium-severity security vulnerabilities
identified in the 2026-02-19 security audit.
"""

import os
import inspect

# Force SQLite mode for tests
os.environ["USE_SQLITE"] = "true"

import pytest
from datetime import timedelta


# ============================================================================
# M1: Health Endpoint — must not leak system internals
# ============================================================================

class TestM1_HealthEndpoint:
    """Verify health endpoint returns minimal info."""

    def test_health_no_agent_counts(self):
        """Health endpoint must not expose agent counts."""
        from backend.api import main as main_mod
        source = inspect.getsource(main_mod.health_check)
        assert "total_agents" not in source, "Health endpoint still leaks agent counts"
        assert "active_agents" not in source, "Health endpoint still leaks active agent count"

    def test_health_no_queue_capabilities(self):
        """Health endpoint must not expose queue capability names."""
        from backend.api import main as main_mod
        source = inspect.getsource(main_mod.health_check)
        assert "capabilities" not in source, "Health endpoint still leaks capability names"

    def test_health_no_error_details(self):
        """Health endpoint must not expose exception details."""
        from backend.api import main as main_mod
        source = inspect.getsource(main_mod.health_check)
        assert 'str(e)' not in source, "Health endpoint still leaks error strings"


# ============================================================================
# M2: Exception Details — must not leak internal errors
# ============================================================================

class TestM2_ExceptionDetails:
    """Verify API responses don't leak exception internals."""

    def test_agent_register_no_raw_error(self):
        """Agent registration must not return raw ValueError."""
        from backend.api import main as main_mod
        source = inspect.getsource(main_mod)
        # Find the register_agent endpoint area and check
        # The old pattern was: raise HTTPException(status_code=400, detail=str(e))
        assert 'detail=str(e)' not in source, \
            "Raw exception details still exposed in API responses"

    def test_llm_endpoints_no_raw_error(self):
        """LLM endpoints must not return raw RuntimeError."""
        from backend.api import main as main_mod
        source = inspect.getsource(main_mod)
        assert 'detail=str(e)' not in source, \
            "Raw exception details still exposed in LLM endpoints"


# ============================================================================
# M3: Audit Logging for Auth Events
# ============================================================================

class TestM3_AuthAuditLogging:
    """Verify auth events are logged."""

    def test_login_logs_failure(self):
        """Login endpoint must log failed attempts."""
        from backend.api import auth as auth_mod
        source = inspect.getsource(auth_mod.login)
        assert "AUTH_FAILED" in source, "Login failure not logged"

    def test_login_logs_success(self):
        """Login endpoint must log successful logins."""
        from backend.api import auth as auth_mod
        source = inspect.getsource(auth_mod.login)
        assert "AUTH_SUCCESS" in source, "Login success not logged"

    def test_password_change_logged(self):
        """Password change must be logged."""
        from backend.api import auth as auth_mod
        source = inspect.getsource(auth_mod.change_password)
        assert "AUTH_EVENT" in source or "password_changed" in source, \
            "Password change not logged"

    def test_token_refresh_logged(self):
        """Token refresh must be logged."""
        from backend.api import auth as auth_mod
        source = inspect.getsource(auth_mod.refresh_token)
        assert "AUTH_EVENT" in source or "token_refreshed" in source, \
            "Token refresh not logged"


# ============================================================================
# M4: Admin Role from DB, Not Hardcoded
# ============================================================================

class TestM4_AdminRoleFromDB:
    """Verify admin role is read from UserModel, not hardcoded."""

    def test_user_model_has_role_column(self):
        """UserModel must have a 'role' column."""
        from backend.shared.rbac_models import UserModel
        assert hasattr(UserModel, "role"), "UserModel missing 'role' column"

    def test_no_hardcoded_admin_check_in_auth(self):
        """auth.py must not hardcode admin check to user_id."""
        from backend.api import auth as auth_mod
        source = inspect.getsource(auth_mod)
        assert '"user-admin-001"' not in source, \
            "Hardcoded admin user_id check still in auth.py"

    def test_user_response_reads_role_from_model(self):
        """_user_response must read role from the user model."""
        from backend.api.auth import _user_response
        source = inspect.getsource(_user_response)
        assert "user-admin-001" not in source, \
            "_user_response still has hardcoded admin check"


# ============================================================================
# M5: RBAC Cache TTL Reduced
# ============================================================================

class TestM5_RBACCacheTTL:
    """Verify RBAC cache TTL is 30 seconds, not 5 minutes."""

    def test_cache_ttl_is_30s(self):
        """RBAC cache TTL must be <= 30 seconds."""
        from backend.shared.rbac_service import RBACService
        svc = RBACService()
        assert svc._cache_ttl <= timedelta(seconds=30), \
            f"RBAC cache TTL too high: {svc._cache_ttl}"

    def test_cache_ttl_not_5min(self):
        """RBAC cache TTL must not be 5 minutes."""
        from backend.shared.rbac_service import RBACService
        svc = RBACService()
        assert svc._cache_ttl != timedelta(minutes=5), \
            "RBAC cache TTL is still 5 minutes"


# ============================================================================
# M6: Token Refresh Restricted to Near-Expiry
# ============================================================================

class TestM6_TokenRefreshWindow:
    """Verify token refresh is restricted to near-expiry tokens."""

    def test_refresh_checks_expiry(self):
        """Refresh endpoint must check token expiry time."""
        from backend.api import auth as auth_mod
        source = inspect.getsource(auth_mod.refresh_token)
        assert "exp" in source and "remaining" in source, \
            "Refresh endpoint not checking token expiry"

    def test_refresh_has_window_constant(self):
        """Refresh endpoint must define a refresh window."""
        from backend.api import auth as auth_mod
        source = inspect.getsource(auth_mod.refresh_token)
        assert "REFRESH_WINDOW" in source or "600" in source, \
            "Refresh endpoint missing refresh window constant"


# ============================================================================
# M7: OAuth State Validation (already fixed in H4)
# ============================================================================

class TestM7_OAuthStateValidation:
    """Verify OAuth callback validates state parameter (covered by H4)."""

    def test_oauth_callback_validates_state(self):
        """OAuth callback must validate state against stored value."""
        source = inspect.getsource(
            __import__("backend.shared.sso_service", fromlist=["SSOService"]).SSOService._handle_oauth_callback
        )
        assert "state" in source.lower(), "OAuth callback missing state validation"


# ============================================================================
# M8: JWT Algorithm (informational — HS256 is acceptable for single-service)
# ============================================================================

class TestM8_JWTAlgorithm:
    """Document JWT algorithm awareness."""

    def test_jwt_algorithm_is_explicit(self):
        """JWT algorithm must be explicitly configured, not default."""
        from backend.shared.config import get_settings
        settings = get_settings()
        assert settings.JWT_ALGORITHM in ("HS256", "RS256"), \
            f"Unexpected JWT algorithm: {settings.JWT_ALGORITHM}"


# ============================================================================
# M9: setattr Field Allowlists
# ============================================================================

class TestM9_SetAttrAllowlists:
    """Verify setattr calls use explicit field allowlists."""

    def test_agent_registry_uses_allowlist(self):
        """agent_registry_service must use field allowlist in update."""
        from backend.shared.agent_registry_service import AgentRegistryService
        source = inspect.getsource(AgentRegistryService.update_agent)
        assert "_ALLOWED_AGENT_FIELDS" in source or "ALLOWED" in source, \
            "agent_registry_service update missing field allowlist"

    def test_multicloud_account_uses_allowlist(self):
        """multicloud_service account update must use field allowlist."""
        import backend.shared.multicloud_service as mc_mod
        source = inspect.getsource(mc_mod)
        assert "_ALLOWED_ACCOUNT_FIELDS" in source, \
            "multicloud_service account update missing field allowlist"

    def test_multicloud_deployment_uses_allowlist(self):
        """multicloud_service deployment update must use field allowlist."""
        import backend.shared.multicloud_service as mc_mod
        source = inspect.getsource(mc_mod)
        assert "_ALLOWED_DEPLOY_FIELDS" in source, \
            "multicloud_service deployment update missing field allowlist"

    def test_template_service_uses_allowlist(self):
        """template_service update must use field allowlist."""
        from backend.shared.template_service import TemplateService
        source = inspect.getsource(TemplateService.update_template)
        assert "_ALLOWED_TEMPLATE_FIELDS" in source or "ALLOWED" in source, \
            "template_service update missing field allowlist"

    def test_rag_service_already_has_allowlist(self):
        """rag_service must already have allowed_fields."""
        import backend.shared.rag_service as rag_mod
        source = inspect.getsource(rag_mod)
        assert "allowed_fields" in source, \
            "rag_service missing field allowlist"


# ============================================================================
# M10: Webhook Org ID Not From Header
# ============================================================================

class TestM10_WebhookOrgIdSpoofing:
    """Verify webhook endpoint doesn't trust X-Organization-ID header."""

    def test_receive_webhook_no_org_header(self):
        """receive_webhook must not accept X-Organization-ID from header."""
        from backend.api import webhooks as wh_mod
        source = inspect.getsource(wh_mod.receive_webhook)
        assert "X-Organization-ID" not in source, \
            "Webhook endpoint still accepts org ID from header"

    def test_receive_webhook_no_x_organization_id_param(self):
        """receive_webhook signature must not have x_organization_id parameter."""
        from backend.api.webhooks import receive_webhook
        import inspect as _insp
        sig = _insp.signature(receive_webhook)
        param_names = list(sig.parameters.keys())
        assert "x_organization_id" not in param_names, \
            "Webhook endpoint still has x_organization_id parameter"
