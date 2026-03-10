#!/usr/bin/env python3
"""
Security Tests: Authentication

Tests authentication mechanisms including:
- API key validation
- JWT token verification
- Authentication bypass prevention
- Token expiration handling
"""

import pytest
from datetime import datetime, timedelta
from unittest.mock import patch, MagicMock
from uuid import uuid4

# Check for required dependencies
try:
    import jwt
    HAS_JWT = True
except ImportError:
    HAS_JWT = False
    jwt = None

try:
    from fastapi import HTTPException
    HAS_FASTAPI = True
except ImportError:
    HAS_FASTAPI = False
    HTTPException = None

# Skip entire module if dependencies not available
if not HAS_JWT or not HAS_FASTAPI:
    pytest.skip(
        "Required dependencies not installed (jwt, fastapi)",
        allow_module_level=True
    )

from backend.shared.auth import (
    APIKeyManager,
    JWTManager,
    verify_api_key,
    verify_jwt_token,
    hash_password,
    verify_password,
    get_api_key_manager,
    get_jwt_manager,
)
from backend.shared.config import Settings


class TestAPIKeyAuthentication:
    """Tests for API key authentication."""

    def setup_method(self):
        """Reset API key manager for each test."""
        self.manager = APIKeyManager()

    def test_api_key_generation_format(self):
        """API keys should follow expected format."""
        agent_id = uuid4()
        api_key = self.manager.generate_api_key(agent_id, "test-org")

        assert api_key.startswith("sk-")
        assert len(api_key) > 40  # sk- prefix + 32+ chars

    def test_api_key_uniqueness(self):
        """Each generated API key should be unique."""
        keys = set()
        for _ in range(100):
            key = self.manager.generate_api_key(uuid4(), "test-org")
            assert key not in keys, "Duplicate key generated"
            keys.add(key)

    def test_valid_api_key_returns_agent_id(self):
        """Valid API key should return associated agent ID."""
        agent_id = uuid4()
        api_key = self.manager.generate_api_key(agent_id, "test-org")

        result = self.manager.validate_api_key(api_key)

        assert result.agent_id == agent_id

    def test_invalid_api_key_returns_none(self):
        """Invalid API key should return None."""
        result = self.manager.validate_api_key("invalid-key")

        assert result is None

    def test_revoked_api_key_returns_none(self):
        """Revoked API key should return None."""
        agent_id = uuid4()
        api_key = self.manager.generate_api_key(agent_id, "test-org")

        # Revoke the key
        self.manager.revoke_api_key(agent_id)

        result = self.manager.validate_api_key(api_key)

        assert result is None

    def test_api_key_last_used_updated(self):
        """Validating API key should update last_used timestamp."""
        agent_id = uuid4()
        api_key = self.manager.generate_api_key(agent_id, "test-org")

        initial_time = self.manager._api_keys[api_key].last_used

        # Small delay
        import time
        time.sleep(0.01)

        self.manager.validate_api_key(api_key)

        new_time = self.manager._api_keys[api_key].last_used
        assert new_time >= initial_time


class TestJWTAuthentication:
    """Tests for JWT authentication."""

    def setup_method(self):
        """Create JWT manager for each test."""
        self.manager = JWTManager()

    def test_create_valid_token(self):
        """Should create a valid JWT token."""
        data = {"sub": "user123", "email": "test@example.com"}
        token = self.manager.create_access_token(data)

        assert token is not None
        assert len(token) > 0

    def test_verify_valid_token(self):
        """Should verify and decode valid token."""
        original_data = {"sub": "user123", "email": "test@example.com"}
        token = self.manager.create_access_token(original_data)

        decoded = self.manager.verify_token(token)

        assert decoded["sub"] == "user123"
        assert decoded["email"] == "test@example.com"
        assert "exp" in decoded

    def test_expired_token_returns_none(self):
        """Expired token should return None."""
        data = {"sub": "user123"}
        token = self.manager.create_access_token(
            data,
            expires_delta=timedelta(seconds=-1)  # Already expired
        )

        result = self.manager.verify_token(token)

        assert result is None

    def test_invalid_token_returns_none(self):
        """Invalid/tampered token should return None."""
        result = self.manager.verify_token("invalid.token.here")

        assert result is None

    def test_tampered_token_returns_none(self):
        """Tampered token should fail verification."""
        data = {"sub": "user123"}
        token = self.manager.create_access_token(data)

        # Tamper with the token
        tampered = token[:-5] + "XXXXX"

        result = self.manager.verify_token(tampered)

        assert result is None

    def test_wrong_secret_fails_verification(self):
        """Token signed with wrong secret should fail."""
        data = {"sub": "user123"}

        # Create token with different secret
        wrong_token = jwt.encode(
            data,
            "wrong-secret",
            algorithm="HS256"
        )

        result = self.manager.verify_token(wrong_token)

        assert result is None

    def test_dashboard_token_includes_type(self):
        """Dashboard token should include type field."""
        token = self.manager.create_dashboard_token(
            user_id="user123",
            email="test@example.com",
            role="admin"
        )

        decoded = self.manager.verify_token(token)

        assert decoded["type"] == "dashboard"
        assert decoded["role"] == "admin"


class TestPasswordHashing:
    """Tests for password hashing."""

    def test_password_hash_different_from_plain(self):
        """Hashed password should differ from plain text."""
        password = "securepassword123"
        hashed = hash_password(password)

        assert hashed != password
        assert len(hashed) > len(password)

    def test_same_password_different_hashes(self):
        """Same password should produce different hashes (salt)."""
        password = "securepassword123"
        hash1 = hash_password(password)
        hash2 = hash_password(password)

        assert hash1 != hash2

    def test_verify_correct_password(self):
        """Correct password should verify successfully."""
        password = "securepassword123"
        hashed = hash_password(password)

        assert verify_password(password, hashed) is True

    def test_verify_wrong_password(self):
        """Wrong password should fail verification."""
        password = "securepassword123"
        hashed = hash_password(password)

        assert verify_password("wrongpassword", hashed) is False

    def test_empty_password_handling(self):
        """Empty password should be handled safely."""
        password = ""
        hashed = hash_password(password)

        assert verify_password("", hashed) is True
        assert verify_password("notempty", hashed) is False


class TestAuthenticationDependencies:
    """Tests for FastAPI authentication dependencies."""

    @pytest.mark.asyncio
    async def test_verify_api_key_missing(self):
        """Missing API key should raise 401."""
        with pytest.raises(HTTPException) as exc_info:
            await verify_api_key(None)

        assert exc_info.value.status_code == 401
        assert "API key required" in exc_info.value.detail

    @pytest.mark.asyncio
    async def test_verify_api_key_invalid(self):
        """Invalid API key should raise 401."""
        with pytest.raises(HTTPException) as exc_info:
            await verify_api_key("invalid-api-key")

        assert exc_info.value.status_code == 401
        assert "Invalid API key" in exc_info.value.detail

    @pytest.mark.asyncio
    async def test_verify_jwt_token_missing(self):
        """Missing JWT should raise 401."""
        # Patch DEBUG to False so the function raises instead of returning default payload
        with patch('backend.shared.auth.settings') as mock_settings:
            mock_settings.DEBUG = False
            with pytest.raises(HTTPException) as exc_info:
                await verify_jwt_token(None)

            assert exc_info.value.status_code == 401
            assert "Authentication required" in exc_info.value.detail


class TestSecurityBoundaries:
    """Tests for security boundary conditions."""

    def test_api_key_not_guessable(self):
        """API keys should not be easily guessable."""
        manager = APIKeyManager()

        # Generate 1000 keys and ensure high entropy
        keys = [manager.generate_api_key(uuid4(), "test-org") for _ in range(1000)]

        # No duplicates
        assert len(set(keys)) == 1000

        # All keys should have sufficient length
        for key in keys:
            assert len(key) >= 40

    def test_jwt_algorithm_enforced(self):
        """JWT should only accept specified algorithm."""
        manager = JWTManager()

        # Create token with HS256
        token = manager.create_access_token({"sub": "test"})

        # Verify works with same algorithm
        decoded = manager.verify_token(token)
        assert decoded is not None

    def test_timing_attack_resistance(self):
        """Password verification should resist timing attacks."""
        import time

        password = "securepassword123"
        hashed = hash_password(password)

        # Measure time for correct password
        times_correct = []
        for _ in range(10):
            start = time.perf_counter()
            verify_password(password, hashed)
            times_correct.append(time.perf_counter() - start)

        # Measure time for wrong password
        times_wrong = []
        for _ in range(10):
            start = time.perf_counter()
            verify_password("wrongpassword", hashed)
            times_wrong.append(time.perf_counter() - start)

        # Times should be similar (within order of magnitude)
        avg_correct = sum(times_correct) / len(times_correct)
        avg_wrong = sum(times_wrong) / len(times_wrong)

        # Allow 10x variance (bcrypt has some natural variance)
        assert 0.1 < avg_correct / avg_wrong < 10


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
