"""
Security Regression Tests — HIGH Severity Fixes (H1–H12)

Tests to prevent re-introduction of high-severity security vulnerabilities
identified in the 2026-02-19 security audit.
"""

import os
import time
import inspect

# Force SQLite mode for tests
os.environ["USE_SQLITE"] = "true"

import pytest
from unittest.mock import patch, MagicMock, AsyncMock
from uuid import uuid4


# ============================================================================
# H1: Token Revocation Blacklist
# ============================================================================

class TestH1_TokenBlacklist:
    """Verify JWT tokens can be revoked via blacklist."""

    def test_blacklist_exists(self):
        """TokenBlacklist class must exist in auth module."""
        from backend.shared.auth import TokenBlacklist, get_token_blacklist
        bl = get_token_blacklist()
        assert isinstance(bl, TokenBlacklist)

    def test_add_and_check(self):
        """Blacklisted JTI must be detected."""
        from backend.shared.auth import TokenBlacklist
        bl = TokenBlacklist()
        jti = "test-jti-123"
        bl.add(jti, time.time() + 3600)
        assert bl.is_blacklisted(jti)

    def test_non_blacklisted_not_detected(self):
        """Non-blacklisted JTI must not be detected."""
        from backend.shared.auth import TokenBlacklist
        bl = TokenBlacklist()
        assert not bl.is_blacklisted("never-added")

    def test_expired_entries_cleaned(self):
        """Expired blacklist entries should be cleaned up."""
        from backend.shared.auth import TokenBlacklist
        bl = TokenBlacklist()
        bl.add("old-jti", time.time() - 10)  # already expired
        bl.add("trigger-cleanup", time.time() + 3600)
        # After cleanup, the expired entry should be gone
        assert not bl.is_blacklisted("old-jti")

    def test_jwt_contains_jti(self):
        """JWTs must contain a jti claim."""
        from backend.shared.auth import get_jwt_manager
        mgr = get_jwt_manager()
        token = mgr.create_dashboard_token("user-1", "test@example.com", "admin")
        payload = mgr.verify_token(token)
        assert "jti" in payload, "JWT missing jti claim"
        assert len(payload["jti"]) > 10

    def test_blacklisted_token_rejected(self):
        """A blacklisted token must be rejected by verify_token."""
        from backend.shared.auth import get_jwt_manager, get_token_blacklist
        mgr = get_jwt_manager()
        token = mgr.create_dashboard_token("user-1", "test@example.com", "admin")
        payload = mgr.verify_token(token)
        assert payload is not None

        # Blacklist it
        bl = get_token_blacklist()
        bl.add(payload["jti"], payload["exp"])

        # Should now be rejected
        assert mgr.verify_token(token) is None


# ============================================================================
# H2: Login Rate Limiting and Account Lockout
# ============================================================================

class TestH2_LoginRateLimiting:
    """Verify login rate limiting and account lockout."""

    def test_rate_limiter_class_exists(self):
        """LoginRateLimiter must exist in auth API."""
        from backend.api.auth import LoginRateLimiter
        rl = LoginRateLimiter()
        assert rl.MAX_ATTEMPTS == 5
        assert rl.LOCKOUT_SECONDS == 900

    def test_lockout_after_max_failures(self):
        """Account must lock after MAX_ATTEMPTS failures."""
        from backend.api.auth import LoginRateLimiter
        from fastapi import HTTPException
        rl = LoginRateLimiter()
        email = "test-lockout@example.com"

        for _ in range(5):
            rl.record_attempt(email, success=False)

        with pytest.raises(HTTPException) as exc_info:
            rl.check_rate_limit(email)
        assert exc_info.value.status_code == 429

    def test_successful_login_doesnt_lock(self):
        """Successful logins should not trigger lockout."""
        from backend.api.auth import LoginRateLimiter
        rl = LoginRateLimiter()
        email = "good-user@example.com"

        for _ in range(10):
            rl.record_attempt(email, success=True)

        # Should not raise
        rl.check_rate_limit(email)

    def test_login_endpoint_integrates_rate_limiter(self):
        """Login endpoint source must reference rate limiter."""
        from backend.api import auth as auth_mod
        source = inspect.getsource(auth_mod.login)
        assert "check_rate_limit" in source, "Login endpoint missing rate limit check"
        assert "record_attempt" in source, "Login endpoint missing attempt recording"


# ============================================================================
# H3+H4: SAML Validation and CSRF on SSO Callbacks
# ============================================================================

class TestH3_SAMLValidation:
    """Verify SAML response validation."""

    def test_saml_callback_validates_signature(self):
        """SAML handler must check for signature presence."""
        source = inspect.getsource(
            __import__("backend.shared.sso_service", fromlist=["SSOService"]).SSOService._handle_saml_callback
        )
        assert "signature" in source.lower(), "SAML callback missing signature validation"

    def test_saml_callback_requires_x509_cert(self):
        """SAML handler must require x509 certificate for verification."""
        source = inspect.getsource(
            __import__("backend.shared.sso_service", fromlist=["SSOService"]).SSOService._handle_saml_callback
        )
        assert "x509_cert" in source, "SAML callback not checking x509 certificate"


class TestH4_OAuthCSRF:
    """Verify CSRF protection on OAuth callbacks."""

    def test_oauth_callback_validates_state(self):
        """OAuth callback must validate the state parameter."""
        source = inspect.getsource(
            __import__("backend.shared.sso_service", fromlist=["SSOService"]).SSOService._handle_oauth_callback
        )
        assert "state" in source.lower(), "OAuth callback missing state validation"
        assert "csrf" in source.lower() or "stored" in source.lower(), \
            "OAuth callback not validating state against stored value"


# ============================================================================
# H5: No shell=True in subprocess calls
# ============================================================================

class TestH5_NoShellTrue:
    """Verify subprocess calls do not use shell=True."""

    def _has_shell_true_in_code(self, content: str) -> bool:
        """Check if shell=True appears in actual code (not comments/docstrings)."""
        import ast
        try:
            tree = ast.parse(content)
            for node in ast.walk(tree):
                if isinstance(node, ast.keyword) and node.arg == "shell":
                    if isinstance(node.value, ast.Constant) and node.value.value is True:
                        return True
            return False
        except SyntaxError:
            # Fallback: simple heuristic
            for line in content.splitlines():
                stripped = line.strip()
                if stripped.startswith("#") or stripped.startswith('"""'):
                    continue
                if "shell=True" in stripped:
                    return True
            return False

    def test_check_db_setup_no_shell(self):
        """check_db_setup.py must not use shell=True in code."""
        source_path = os.path.join(
            os.path.dirname(__file__), "..", "check_db_setup.py"
        )
        if os.path.exists(source_path):
            with open(source_path) as f:
                content = f.read()
            assert not self._has_shell_true_in_code(content), "shell=True found in check_db_setup.py"

    def test_fix_alembic_heads_no_shell(self):
        """fix_alembic_heads.py must not use shell=True in code."""
        source_path = os.path.join(
            os.path.dirname(__file__), "..", "fix_alembic_heads.py"
        )
        if os.path.exists(source_path):
            with open(source_path) as f:
                content = f.read()
            assert not self._has_shell_true_in_code(content), "shell=True found in fix_alembic_heads.py"


# ============================================================================
# H6: MCP Server Command Allowlist
# ============================================================================

class TestH6_MCPAllowlist:
    """Verify MCP server command allowlist."""

    def test_stdio_transport_has_allowlist(self):
        """StdioTransport must define ALLOWED_COMMANDS."""
        from backend.shared.mcp_service import StdioTransport
        assert hasattr(StdioTransport, "ALLOWED_COMMANDS")
        assert len(StdioTransport.ALLOWED_COMMANDS) > 0

    def test_common_commands_in_allowlist(self):
        """Common safe MCP commands must be in the allowlist."""
        from backend.shared.mcp_service import StdioTransport
        for cmd in ("node", "npx", "python", "python3", "uvx"):
            assert cmd in StdioTransport.ALLOWED_COMMANDS, f"{cmd} missing from allowlist"

    def test_dangerous_commands_not_in_allowlist(self):
        """Dangerous commands must not be in the allowlist."""
        from backend.shared.mcp_service import StdioTransport
        for cmd in ("bash", "sh", "curl", "wget", "rm", "cat", "eval"):
            assert cmd not in StdioTransport.ALLOWED_COMMANDS, f"{cmd} should not be in allowlist"

    def test_connect_validates_command(self):
        """StdioTransport.connect must validate command against allowlist."""
        source = inspect.getsource(
            __import__("backend.shared.mcp_service", fromlist=["StdioTransport"]).StdioTransport.connect
        )
        assert "ALLOWED_COMMANDS" in source, "connect() does not check ALLOWED_COMMANDS"


# ============================================================================
# H7+H8: SSRF Protection
# ============================================================================

class TestH7H8_SSRFProtection:
    """Verify SSRF protection in URL validation."""

    def test_url_validator_module_exists(self):
        """url_validator module must exist."""
        from backend.shared.url_validator import validate_url
        assert callable(validate_url)

    def test_blocks_localhost(self):
        """Must block localhost URLs."""
        from backend.shared.url_validator import validate_url
        for url in ("http://localhost/admin", "http://127.0.0.1/secret", "http://0.0.0.0/"):
            with pytest.raises(ValueError, match="localhost|Blocked"):
                validate_url(url)

    def test_blocks_metadata_endpoints(self):
        """Must block cloud metadata endpoints."""
        from backend.shared.url_validator import validate_url
        with pytest.raises(ValueError, match="metadata|Blocked"):
            validate_url("http://169.254.169.254/latest/meta-data/")

    def test_blocks_file_scheme(self):
        """Must block file:// URLs."""
        from backend.shared.url_validator import validate_url
        with pytest.raises(ValueError, match="scheme"):
            validate_url("file:///etc/passwd")

    def test_allows_public_urls(self):
        """Must allow legitimate public URLs."""
        from backend.shared.url_validator import validate_url
        # Should not raise
        result = validate_url("https://api.github.com/repos")
        assert result == "https://api.github.com/repos"

    def test_webhook_processor_uses_validator(self):
        """Webhook processor _send_http must use url_validator."""
        from backend.webhooks.processor import WebhookProcessor
        source = inspect.getsource(WebhookProcessor._send_http)
        assert "validate_url" in source, "Webhook processor not using SSRF protection"

    def test_http_executor_uses_validator(self):
        """HTTP executor must use url_validator."""
        from backend.integrations.http_executor import HttpActionExecutor
        source = inspect.getsource(HttpActionExecutor._execute_single)
        assert "validate_url" in source, "HTTP executor not using SSRF protection"


# ============================================================================
# H9: HSTS Header
# ============================================================================

class TestH9_HSTSHeader:
    """Verify HSTS header is set."""

    def test_security_headers_include_hsts(self):
        """SecurityHeadersMiddleware must set Strict-Transport-Security."""
        from backend.api import main as main_mod
        source = inspect.getsource(main_mod)
        assert "Strict-Transport-Security" in source, "HSTS header not found in main.py"
        assert "max-age=" in source, "HSTS max-age not configured"


# ============================================================================
# H10: Restrictive CORS
# ============================================================================

class TestH10_CORS:
    """Verify CORS is not wildcard."""

    def test_cors_not_wildcard_methods(self):
        """CORS must not use wildcard methods."""
        from backend.api import main as main_mod
        source = inspect.getsource(main_mod)
        # Find the CORSMiddleware section - allow_methods should not be ["*"]
        assert 'allow_methods=["*"]' not in source, "CORS still using wildcard methods"

    def test_cors_not_wildcard_headers(self):
        """CORS must not use wildcard headers."""
        from backend.api import main as main_mod
        source = inspect.getsource(main_mod)
        assert 'allow_headers=["*"]' not in source, "CORS still using wildcard headers"


# ============================================================================
# H11: Cryptography is a Hard Dependency
# ============================================================================

class TestH11_CryptographyHardDep:
    """Verify cryptography is imported directly, not conditionally."""

    def test_no_has_cryptography_flag(self):
        """credential_manager must not have HAS_CRYPTOGRAPHY conditional."""
        import backend.shared.credential_manager as cm_mod
        source = inspect.getsource(cm_mod)
        assert "HAS_CRYPTOGRAPHY" not in source, "HAS_CRYPTOGRAPHY flag still present"

    def test_no_base64_fallback_in_encrypt(self):
        """CredentialManager.encrypt must not fall back to base64."""
        from backend.shared.credential_manager import CredentialManager
        source = inspect.getsource(CredentialManager.encrypt)
        assert "base64" not in source, "base64 fallback still in encrypt()"

    def test_no_base64_fallback_in_decrypt(self):
        """CredentialManager.decrypt must not fall back to base64."""
        from backend.shared.credential_manager import CredentialManager
        source = inspect.getsource(CredentialManager.decrypt)
        assert "base64" not in source, "base64 fallback still in decrypt()"

    def test_fernet_import_is_direct(self):
        """Fernet must be imported directly, not in try/except."""
        import backend.shared.credential_manager as cm_mod
        source = inspect.getsource(cm_mod)
        # Should have a direct import, not wrapped in try
        lines = source.split("\n")
        for i, line in enumerate(lines):
            if "from cryptography.fernet import Fernet" in line:
                # Check it's NOT inside a try block
                for j in range(max(0, i-3), i):
                    assert "try:" not in lines[j], "Fernet import is still conditional"
                break

    def test_encrypt_decrypt_roundtrip(self):
        """Encryption/decryption must round-trip correctly."""
        from backend.shared.credential_manager import CredentialManager
        mgr = CredentialManager(encryption_key=None)
        data = {"api_key": "sk-test-123", "secret": "hunter2"}
        encrypted = mgr.encrypt(data)
        decrypted = mgr.decrypt(encrypted)
        assert decrypted == data


# ============================================================================
# H12: Password Complexity Requirements
# ============================================================================

class TestH12_PasswordComplexity:
    """Verify password complexity enforcement."""

    def test_register_requires_12_chars(self):
        """RegisterRequest must require 12+ character passwords."""
        from backend.api.auth import RegisterRequest
        from pydantic import ValidationError
        with pytest.raises(ValidationError):
            RegisterRequest(
                email="test@example.com",
                password="Short1aB",  # 8 chars, too short
                name="Test User"
            )

    def test_register_requires_uppercase(self):
        """RegisterRequest must require uppercase letter."""
        from backend.api.auth import RegisterRequest
        from pydantic import ValidationError
        with pytest.raises(ValidationError):
            RegisterRequest(
                email="test@example.com",
                password="alllowercase1234",  # no uppercase
                name="Test User"
            )

    def test_register_requires_lowercase(self):
        """RegisterRequest must require lowercase letter."""
        from backend.api.auth import RegisterRequest
        from pydantic import ValidationError
        with pytest.raises(ValidationError):
            RegisterRequest(
                email="test@example.com",
                password="ALLUPPERCASE1234",  # no lowercase
                name="Test User"
            )

    def test_register_requires_digit(self):
        """RegisterRequest must require at least one digit."""
        from backend.api.auth import RegisterRequest
        from pydantic import ValidationError
        with pytest.raises(ValidationError):
            RegisterRequest(
                email="test@example.com",
                password="NoDigitsHereABC",  # no digit
                name="Test User"
            )

    def test_valid_password_accepted(self):
        """A password meeting all requirements must be accepted."""
        from backend.api.auth import RegisterRequest
        req = RegisterRequest(
            email="test@example.com",
            password="StrongPass123!",
            name="Test User"
        )
        assert req.password == "StrongPass123!"

    def test_change_password_also_validated(self):
        """ChangePasswordRequest must also enforce complexity."""
        from backend.api.auth import ChangePasswordRequest
        from pydantic import ValidationError
        with pytest.raises(ValidationError):
            ChangePasswordRequest(
                current_password="old",
                new_password="weak"
            )
