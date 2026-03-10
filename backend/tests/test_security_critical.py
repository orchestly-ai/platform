"""
Security Regression Tests — Critical Fixes (C1–C7)

Tests to prevent re-introduction of critical security vulnerabilities
identified in the 2026-02-19 security audit.
"""

import os
import warnings

# Force SQLite mode for tests
os.environ["USE_SQLITE"] = "true"

import pytest
import secrets
from unittest.mock import patch, MagicMock
from uuid import uuid4


# ============================================================================
# C2: JWT Secret Key — must not have insecure default
# ============================================================================

class TestC2_JWTSecret:
    """Verify JWT_SECRET_KEY has no hardcoded insecure default."""

    def test_empty_secret_generates_random_in_dev(self):
        """Empty JWT_SECRET_KEY should auto-generate in development mode."""
        with patch.dict(os.environ, {
            "JWT_SECRET_KEY": "",
            "ENVIRONMENT": "development",
        }, clear=False):
            with warnings.catch_warnings(record=True) as w:
                warnings.simplefilter("always")
                from backend.shared.config import Settings
                s = Settings(
                    JWT_SECRET_KEY="",
                    ENVIRONMENT="development",
                )
                assert len(s.JWT_SECRET_KEY) >= 32
                assert any("auto-generated" in str(warning.message).lower() or
                          "ephemeral" in str(warning.message).lower()
                          for warning in w)

    def test_old_default_secret_rejected_in_production(self):
        """The old hardcoded default must be rejected in production."""
        from backend.shared.config import Settings
        with pytest.raises(ValueError, match="JWT_SECRET_KEY must be explicitly set"):
            Settings(
                JWT_SECRET_KEY="your-secret-key-change-in-production-min-32-chars",
                ENVIRONMENT="production",
            )

    def test_old_env_default_rejected_in_production(self):
        """The .env template default must also be rejected in production."""
        from backend.shared.config import Settings
        with pytest.raises(ValueError, match="JWT_SECRET_KEY must be explicitly set"):
            Settings(
                JWT_SECRET_KEY="your-secret-key-change-this-in-production",
                ENVIRONMENT="production",
            )

    def test_short_secret_warns(self):
        """Short JWT secrets should trigger a warning."""
        with warnings.catch_warnings(record=True) as w:
            warnings.simplefilter("always")
            from backend.shared.config import Settings
            s = Settings(
                JWT_SECRET_KEY="short-key-only-20chars!",
                ENVIRONMENT="development",
            )
            assert any("only" in str(warning.message).lower() and "chars" in str(warning.message).lower()
                      for warning in w)

    def test_strong_secret_no_warning(self):
        """A proper 48-char secret should not trigger warnings."""
        strong_secret = secrets.token_urlsafe(48)
        with warnings.catch_warnings(record=True) as w:
            warnings.simplefilter("always")
            from backend.shared.config import Settings
            s = Settings(
                JWT_SECRET_KEY=strong_secret,
                ENVIRONMENT="development",
            )
            jwt_warnings = [x for x in w if "JWT" in str(x.message)]
            assert len(jwt_warnings) == 0
            jwt_val = s.JWT_SECRET_KEY.get_secret_value() if hasattr(s.JWT_SECRET_KEY, 'get_secret_value') else s.JWT_SECRET_KEY
            assert jwt_val == strong_secret


# ============================================================================
# C3: BYOK Gateway — must use Fernet, not XOR
# ============================================================================

class TestC3_BYOKEncryption:
    """Verify BYOK KeyVault uses Fernet encryption, not XOR."""

    def test_encrypt_decrypt_roundtrip(self):
        """Fernet encrypt/decrypt must round-trip correctly."""
        from backend.shared.byok_gateway import KeyVault
        vault = KeyVault(encryption_key="test-secret-for-byok-vault")
        original = "sk-proj-abc123xyz789testkey"
        encrypted = vault.encrypt_key(original)
        decrypted = vault.decrypt_key(encrypted)
        assert decrypted == original

    def test_encrypted_output_is_not_plaintext(self):
        """Encrypted output must not contain the original key."""
        from backend.shared.byok_gateway import KeyVault
        vault = KeyVault(encryption_key="test-secret-for-byok-vault")
        original = "sk-proj-abc123xyz789testkey"
        encrypted = vault.encrypt_key(original)
        assert original not in encrypted

    def test_encrypted_output_is_fernet_token(self):
        """Encrypted output should be a valid Fernet token (starts with gAAAAA)."""
        from backend.shared.byok_gateway import KeyVault
        vault = KeyVault(encryption_key="test-secret-for-byok-vault")
        original = "sk-proj-abc123"
        encrypted = vault.encrypt_key(original)
        # Fernet tokens are base64-encoded and start with 'gAAAAA'
        assert encrypted.startswith("gAAAAA"), f"Expected Fernet token, got: {encrypted[:20]}"

    def test_different_keys_produce_different_ciphertext(self):
        """Different encryption keys must produce different ciphertext."""
        from backend.shared.byok_gateway import KeyVault
        vault1 = KeyVault(encryption_key="secret-key-one")
        vault2 = KeyVault(encryption_key="secret-key-two")
        original = "sk-proj-abc123"
        enc1 = vault1.encrypt_key(original)
        enc2 = vault2.encrypt_key(original)
        assert enc1 != enc2

    def test_wrong_key_fails_decrypt(self):
        """Decrypting with wrong key must fail."""
        from backend.shared.byok_gateway import KeyVault
        vault1 = KeyVault(encryption_key="correct-key")
        vault2 = KeyVault(encryption_key="wrong-key")
        original = "sk-proj-abc123"
        encrypted = vault1.encrypt_key(original)
        with pytest.raises(Exception):
            vault2.decrypt_key(encrypted)

    def test_no_xor_in_keyvault_source(self):
        """KeyVault source code must not contain XOR encryption."""
        import inspect
        from backend.shared.byok_gateway import KeyVault
        source = inspect.getsource(KeyVault)
        assert "^ ord(" not in source, "XOR encryption pattern found in KeyVault"
        assert "XOR" not in source.upper() or "not XOR" in source.lower(), "XOR reference in KeyVault"

    def test_ephemeral_key_warning_when_no_secret(self):
        """KeyVault without encryption secret should warn about ephemeral key."""
        with patch.dict(os.environ, {"BYOK_ENCRYPTION_SECRET": ""}, clear=False):
            with warnings.catch_warnings(record=True) as w:
                warnings.simplefilter("always")
                from backend.shared.byok_gateway import KeyVault
                vault = KeyVault()
                assert any("ephemeral" in str(warning.message).lower()
                          for warning in w)


# ============================================================================
# C3 integration: BYOKGateway register + retrieve round-trip
# ============================================================================

class TestC3_BYOKGatewayIntegration:
    """Integration test for BYOK key registration with Fernet encryption."""

    @pytest.mark.asyncio
    async def test_register_and_retrieve_key(self):
        """Registered key must be retrievable via decryption."""
        from backend.shared.byok_gateway import BYOKGateway, KeyProvider, reset_byok_gateway
        reset_byok_gateway()
        gateway = BYOKGateway(encryption_key="integration-test-secret")
        org_id = uuid4()
        original_key = "sk-proj-test123456789"

        registered = await gateway.register_key(
            org_id=org_id,
            provider=KeyProvider.OPENAI,
            api_key=original_key,
        )

        # Encrypted key should not contain original
        assert original_key not in registered.encrypted_key

        # Should be able to decrypt
        decrypted = await gateway.get_decrypted_key(registered.key_id)
        assert decrypted == original_key


# ============================================================================
# C4: Debug Mode Auth Bypass — must be removed
# ============================================================================

class TestC4_DebugAuthBypass:
    """Verify debug mode does not bypass authentication."""

    def test_verify_jwt_token_no_debug_bypass(self):
        """verify_jwt_token must not return admin user when no credentials in debug mode."""
        import inspect
        from backend.shared.auth import verify_jwt_token
        source = inspect.getsource(verify_jwt_token)
        assert "dev@localhost" not in source, "Debug bypass found in verify_jwt_token"
        assert "debug" not in source.lower() or "auth_type" in source.lower(), \
            "Debug bypass pattern found in verify_jwt_token"

    def test_get_current_user_no_debug_bypass(self):
        """get_current_user must not return debug user when no credentials."""
        import inspect
        from backend.shared.auth import get_current_user
        source = inspect.getsource(get_current_user)
        assert "dev@localhost" not in source, "Debug bypass found in get_current_user"
        assert "auth_type=\"debug\"" not in source, "Debug auth_type found in get_current_user"

    @pytest.mark.asyncio
    async def test_verify_jwt_rejects_no_credentials(self):
        """verify_jwt_token must raise 401 when no credentials provided."""
        from backend.shared.auth import verify_jwt_token
        from fastapi import HTTPException

        with pytest.raises(HTTPException) as exc_info:
            await verify_jwt_token(credentials=None)
        assert exc_info.value.status_code == 401

    @pytest.mark.asyncio
    async def test_get_current_user_rejects_no_auth(self):
        """get_current_user must raise 401 when no API key or JWT."""
        from backend.shared.auth import get_current_user
        from fastapi import HTTPException

        with pytest.raises(HTTPException) as exc_info:
            await get_current_user(api_key=None, credentials=None)
        assert exc_info.value.status_code == 401


# ============================================================================
# C5: RBAC Bypass — must not skip permission checks
# ============================================================================

class TestC5_RBACBypass:
    """Verify RBAC permissions are enforced regardless of environment."""

    def test_no_sqlite_bypass_in_requires_permission(self):
        """requires_permission must not skip checks for USE_SQLITE."""
        import inspect
        from backend.shared.rbac_service import requires_permission
        # Get the source of the decorator factory
        source = inspect.getsource(requires_permission)
        assert "_USE_SQLITE" not in source, "SQLite bypass found in requires_permission"
        assert "_DEVELOPMENT_MODE" not in source, "Development mode bypass found in requires_permission"

    def test_no_env_based_bypass_variables(self):
        """rbac_service module must not define bypass variables."""
        import inspect
        import backend.shared.rbac_service as rbac_mod
        source = inspect.getsource(rbac_mod)
        # These variables should no longer exist
        assert "_USE_SQLITE" not in source, "SQLite bypass variable still defined"
        assert "_DEVELOPMENT_MODE" not in source, "Development mode bypass variable still defined"


# ============================================================================
# C6: Admin Credentials — must not hardcode password
# ============================================================================

class TestC6_AdminCredentials:
    """Verify admin password is not hardcoded."""

    def test_no_hardcoded_admin123_in_main(self):
        """main.py must not contain hardcoded 'admin123' password."""
        import inspect
        from backend.api import main as main_mod
        source = inspect.getsource(main_mod)
        # "admin123" should not appear as a password value
        assert 'hash_password("admin123")' not in source, \
            "Hardcoded admin123 password found in main.py"
        assert "_hash_password(\"admin123\")" not in source, \
            "Hardcoded admin123 password found in main.py"

    def test_admin_password_from_env_or_random(self):
        """Admin seeding should read ADMIN_PASSWORD env var or generate random."""
        import inspect
        from backend.api import main as main_mod
        source = inspect.getsource(main_mod)
        assert "ADMIN_PASSWORD" in source, "ADMIN_PASSWORD env var not referenced in main.py"
        assert "token_urlsafe" in source, "Random password generation not found in main.py"


# ============================================================================
# C7: OAuth Client Secret Encryption
# ============================================================================

class TestC7_OAuthSecretEncryption:
    """Verify OAuth client secrets are encrypted before storage."""

    def test_sso_config_encrypts_client_secret(self):
        """SSO config creation must encrypt oauth_client_secret."""
        import inspect
        from backend.api import sso as sso_mod
        source = inspect.getsource(sso_mod)
        # Should use credential_manager to encrypt
        assert "credential_manager" in source.lower() or "cred_manager" in source.lower(), \
            "No encryption of oauth_client_secret in sso.py"
        assert "encrypt" in source, "No encrypt call found for oauth_client_secret"

    def test_sso_config_does_not_store_plaintext_secret(self):
        """SSO config must not pass raw oauth_client_secret to DB model."""
        import inspect
        from backend.api import sso as sso_mod
        source = inspect.getsource(sso_mod)
        # The old pattern: oauth_client_secret=request.oauth_client_secret
        assert "oauth_client_secret=request.oauth_client_secret" not in source, \
            "Plaintext oauth_client_secret being stored directly"


# ============================================================================
# C1: .gitignore — .env must be excluded from version control
# ============================================================================

class TestC1_GitignoreAndEnv:
    """Verify .env is gitignored and doesn't contain real secrets."""

    def test_gitignore_excludes_env(self):
        """The .gitignore file must exclude .env files."""
        gitignore_path = os.path.join(
            os.path.dirname(__file__), "..", "..", ".gitignore"
        )
        assert os.path.exists(gitignore_path), ".gitignore does not exist"
        with open(gitignore_path) as f:
            content = f.read()
        assert ".env" in content, ".env not in .gitignore"

    def test_env_file_no_real_groq_key(self):
        """The .env file must not contain a real Groq API key."""
        env_path = os.path.join(
            os.path.dirname(__file__), "..", "..", ".env"
        )
        if not os.path.exists(env_path):
            pytest.skip(".env file not present")
        with open(env_path) as f:
            content = f.read()
        # Real Groq keys start with gsk_ and are 56 chars
        for line in content.splitlines():
            if line.startswith("GROQ_API_KEY="):
                value = line.split("=", 1)[1].strip()
                assert not value.startswith("gsk_"), \
                    "Real Groq API key found in .env — it should be empty or a placeholder"

    def test_env_example_exists(self):
        """.env.example template should exist for developers."""
        example_path = os.path.join(
            os.path.dirname(__file__), "..", "..", ".env.example"
        )
        assert os.path.exists(example_path), ".env.example does not exist"
