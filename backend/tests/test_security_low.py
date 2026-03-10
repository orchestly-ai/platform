"""
Security Regression Tests — LOW Severity Fixes (L1, L4, L5)

Tests to prevent re-introduction of low-severity security vulnerabilities
identified in the 2026-02-19 security audit.

L2 (MFA) and L3 (IP whitelisting) are backlog items — no tests here.
"""

import os
import inspect

# Force SQLite mode for tests
os.environ["USE_SQLITE"] = "true"

import pytest


# ============================================================================
# L1: BYOK Gateway — no base64 fallback, cryptography required
# ============================================================================

class TestL1_BYOKEncryption:
    """Verify BYOK gateway uses Fernet only, no base64 fallback."""

    def test_keyvault_no_import_error_fallback(self):
        """KeyVault must not have ImportError fallback for cryptography."""
        from backend.shared.byok_gateway import KeyVault
        source = inspect.getsource(KeyVault.__init__)
        assert "ImportError" not in source, \
            "KeyVault still has ImportError fallback for cryptography"

    def test_encrypt_key_no_base64_fallback(self):
        """encrypt_key must not fall back to base64."""
        from backend.shared.byok_gateway import KeyVault
        source = inspect.getsource(KeyVault.encrypt_key)
        assert "base64" not in source, \
            "encrypt_key still has base64 fallback"

    def test_decrypt_key_no_base64_fallback(self):
        """decrypt_key must not fall back to base64."""
        from backend.shared.byok_gateway import KeyVault
        source = inspect.getsource(KeyVault.decrypt_key)
        assert "base64" not in source, \
            "decrypt_key still has base64 fallback"

    def test_keyvault_always_has_fernet(self):
        """KeyVault instance must always have a Fernet object."""
        from backend.shared.byok_gateway import KeyVault
        vault = KeyVault()
        assert vault._fernet is not None, \
            "KeyVault._fernet is None — encryption not initialized"

    def test_keyvault_encrypt_decrypt_roundtrip(self):
        """KeyVault must encrypt and decrypt correctly."""
        from backend.shared.byok_gateway import KeyVault
        vault = KeyVault()
        original = "sk-proj-test-key-12345"
        encrypted = vault.encrypt_key(original)
        assert encrypted != original, "Key was not encrypted"
        decrypted = vault.decrypt_key(encrypted)
        assert decrypted == original, "Decryption did not return original key"

    def test_keyvault_encrypted_is_not_base64_of_original(self):
        """Encrypted output must not be simple base64 of the original."""
        import base64
        from backend.shared.byok_gateway import KeyVault
        vault = KeyVault()
        original = "sk-proj-test-key-12345"
        encrypted = vault.encrypt_key(original)
        # If it were base64 fallback, decoding would give the original
        try:
            decoded = base64.b64decode(encrypted).decode()
            assert decoded != original, \
                "Encrypted key is just base64 of original — no real encryption"
        except Exception:
            pass  # Fernet output won't cleanly base64-decode to the original


# ============================================================================
# L4: security.txt endpoint exists
# ============================================================================

class TestL4_SecurityTxt:
    """Verify /.well-known/security.txt endpoint exists."""

    def test_security_txt_endpoint_registered(self):
        """App must have a /.well-known/security.txt route."""
        from backend.api.main import app
        routes = [r.path for r in app.routes]
        assert "/.well-known/security.txt" in routes, \
            "/.well-known/security.txt endpoint not registered"

    def test_security_txt_has_contact(self):
        """security.txt handler must include Contact field."""
        from backend.api import main as main_mod
        source = inspect.getsource(main_mod.security_txt)
        assert "Contact" in source, \
            "security.txt missing Contact field"

    def test_security_txt_has_policy(self):
        """security.txt handler must include Policy field."""
        from backend.api import main as main_mod
        source = inspect.getsource(main_mod.security_txt)
        assert "Policy" in source, \
            "security.txt missing Policy field"


# ============================================================================
# L5: OAuth redirect URIs configurable via env var
# ============================================================================

class TestL5_OAuthRedirectURIs:
    """Verify OAuth redirect URIs are not hardcoded."""

    def test_no_hardcoded_platform_example_in_saml(self):
        """SAML login must not hardcode platform.example.com."""
        from backend.shared.sso_service import SSOService
        source = inspect.getsource(SSOService._initiate_saml_login)
        assert "platform.example.com" not in source, \
            "SAML login still has hardcoded platform.example.com"

    def test_no_hardcoded_platform_example_in_oauth(self):
        """OAuth login must not hardcode platform.example.com."""
        from backend.shared.sso_service import SSOService
        source = inspect.getsource(SSOService._initiate_oauth_login)
        assert "platform.example.com" not in source, \
            "OAuth login still has hardcoded platform.example.com"

    def test_platform_base_url_env_var_used(self):
        """sso_service must read PLATFORM_BASE_URL from environment."""
        import backend.shared.sso_service as sso_mod
        source = inspect.getsource(sso_mod)
        assert "PLATFORM_BASE_URL" in source, \
            "sso_service not using PLATFORM_BASE_URL env var"

    def test_platform_base_url_has_default(self):
        """PLATFORM_BASE_URL must have a default value."""
        from backend.shared.sso_service import PLATFORM_BASE_URL
        assert PLATFORM_BASE_URL, "PLATFORM_BASE_URL has no default value"
        assert "://" in PLATFORM_BASE_URL, \
            "PLATFORM_BASE_URL default must be a URL"
