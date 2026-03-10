"""
Credential Manager

Secure storage and retrieval of integration credentials.
Supports encryption at rest and secure key management.

Security Features:
- Per-tenant salt derivation for key isolation
- Fernet symmetric encryption (AES-128-CBC with HMAC)
- PBKDF2-SHA256 key derivation (100,000 iterations)
- Automatic fallback for backward compatibility
"""

import os
import json
import base64
import hashlib
import secrets
from datetime import datetime
from typing import Any, Dict, Optional, List
from dataclasses import dataclass, field
from enum import Enum
import logging

# cryptography is a hard dependency — no fallback to base64
from cryptography.fernet import Fernet
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC

logger = logging.getLogger(__name__)


class CredentialType(Enum):
    """Types of credentials that can be stored."""
    LLM_API_KEY = "llm_api_key"
    OAUTH_TOKEN = "oauth_token"
    API_KEY = "api_key"
    WEBHOOK_SECRET = "webhook_secret"
    DATABASE_URL = "database_url"


@dataclass
class LLMCredential:
    """LLM API key credential with metadata."""
    provider: str  # openai, anthropic, groq, etc.
    api_key: str
    organization_id: str
    created_at: datetime = field(default_factory=datetime.utcnow)
    last_used_at: Optional[datetime] = None
    is_active: bool = True
    alias: Optional[str] = None  # e.g., "production", "development"

    def to_dict(self) -> Dict[str, Any]:
        return {
            "provider": self.provider,
            "api_key": self.api_key,
            "organization_id": self.organization_id,
            "created_at": self.created_at.isoformat(),
            "last_used_at": self.last_used_at.isoformat() if self.last_used_at else None,
            "is_active": self.is_active,
            "alias": self.alias,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "LLMCredential":
        return cls(
            provider=data["provider"],
            api_key=data["api_key"],
            organization_id=data["organization_id"],
            created_at=datetime.fromisoformat(data["created_at"]) if data.get("created_at") else datetime.utcnow(),
            last_used_at=datetime.fromisoformat(data["last_used_at"]) if data.get("last_used_at") else None,
            is_active=data.get("is_active", True),
            alias=data.get("alias"),
        )


class CredentialManager:
    """
    Manages secure storage of integration credentials.

    In production, this should:
    - Use a proper secrets manager (AWS Secrets Manager, HashiCorp Vault, etc.)
    - Encrypt credentials at rest
    - Support key rotation
    - Audit access to credentials

    For demo/development, we use Fernet symmetric encryption.
    """

    def __init__(self, encryption_key: Optional[str] = None):
        """
        Initialize credential manager.

        Args:
            encryption_key: Base64-encoded encryption key.
                           If not provided, uses CREDENTIAL_ENCRYPTION_KEY env var.
                           Falls back to a derived key from a secret.
        """
        self.encryption_key = encryption_key or os.environ.get("CREDENTIAL_ENCRYPTION_KEY")

        if self.encryption_key:
            self._fernet = Fernet(self.encryption_key.encode())
        else:
            # Derive key from a secret (for development only!)
            # In production, use a proper key management system
            secret = os.environ.get("CREDENTIAL_SECRET", "default-dev-secret-change-in-production")
            self._fernet = self._derive_key(secret)

    def _derive_key(self, secret: str, tenant_id: Optional[str] = None) -> Fernet:
        """
        Derive a Fernet key from a secret string with per-tenant salt.

        Args:
            secret: Base secret for key derivation
            tenant_id: Optional tenant/organization ID for key isolation

        Returns:
            Fernet instance for encryption/decryption
        """
        # Generate tenant-specific salt for key isolation
        # This ensures each tenant has a unique encryption key
        if tenant_id:
            salt = hashlib.sha256(f"agentorch:{tenant_id}".encode()).digest()
        else:
            # Fallback salt for backward compatibility
            salt = b"agentorch_credential_salt"

        kdf = PBKDF2HMAC(
            algorithm=hashes.SHA256(),
            length=32,
            salt=salt,
            iterations=100000,
        )
        key = base64.urlsafe_b64encode(kdf.derive(secret.encode()))
        return Fernet(key)

    def get_tenant_encryptor(self, tenant_id: str) -> "TenantCredentialManager":
        """
        Get a tenant-specific credential manager.

        Each tenant gets a unique encryption key derived from the base secret
        combined with their tenant ID. This provides key isolation between tenants.

        Args:
            tenant_id: Organization/tenant ID

        Returns:
            TenantCredentialManager instance
        """
        return TenantCredentialManager(self, tenant_id)

    def encrypt(self, credentials: Dict[str, Any]) -> str:
        """
        Encrypt credentials for storage.

        Args:
            credentials: Dictionary of credentials to encrypt

        Returns:
            Encrypted string that can be stored in database
        """
        json_str = json.dumps(credentials)
        encrypted = self._fernet.encrypt(json_str.encode())
        return encrypted.decode()

    def decrypt(self, encrypted_credentials: str) -> Dict[str, Any]:
        """
        Decrypt stored credentials.

        Args:
            encrypted_credentials: Encrypted credential string

        Returns:
            Decrypted credentials dictionary
        """
        if not encrypted_credentials:
            return {}

        try:
            decrypted = self._fernet.decrypt(encrypted_credentials.encode())
            return json.loads(decrypted.decode())
        except Exception as e:
            logger.error(f"Failed to decrypt credentials: {e}")
            raise

    def mask_sensitive(self, credentials: Dict[str, Any]) -> Dict[str, Any]:
        """
        Mask sensitive values for logging/display.

        Args:
            credentials: Credentials dictionary

        Returns:
            Dictionary with sensitive values masked
        """
        sensitive_keys = {
            "access_token", "refresh_token", "api_key", "secret",
            "password", "client_secret", "bot_token", "personal_access_token",
        }

        masked = {}
        for key, value in credentials.items():
            if key.lower() in sensitive_keys or any(s in key.lower() for s in ["token", "key", "secret", "password"]):
                if isinstance(value, str) and len(value) > 8:
                    masked[key] = value[:4] + "*" * (len(value) - 8) + value[-4:]
                else:
                    masked[key] = "****"
            else:
                masked[key] = value
        return masked

    def validate_oauth_tokens(self, credentials: Dict[str, Any]) -> bool:
        """
        Validate that OAuth tokens are present and not obviously invalid.

        Args:
            credentials: Credentials dictionary

        Returns:
            True if tokens appear valid
        """
        access_token = credentials.get("access_token")
        if not access_token:
            return False

        # Check if token looks valid (not empty, reasonable length)
        if len(access_token) < 10:
            return False

        # Check expiration if present
        expires_at = credentials.get("expires_at")
        if expires_at:
            if isinstance(expires_at, str):
                try:
                    expires_at = datetime.fromisoformat(expires_at.replace("Z", "+00:00"))
                except ValueError:
                    return False
            if isinstance(expires_at, datetime) and expires_at < datetime.utcnow():
                # Token is expired, but might be refreshable
                return credentials.get("refresh_token") is not None

        return True

    def validate_api_key(self, credentials: Dict[str, Any]) -> bool:
        """
        Validate that API key is present.

        Args:
            credentials: Credentials dictionary

        Returns:
            True if API key appears valid
        """
        api_key = (
            credentials.get("api_key")
            or credentials.get("bot_token")
            or credentials.get("personal_access_token")
        )
        return bool(api_key and len(api_key) >= 10)


# Singleton instance
_credential_manager: Optional[CredentialManager] = None


def get_credential_manager() -> CredentialManager:
    """Get the singleton credential manager instance."""
    global _credential_manager
    if _credential_manager is None:
        _credential_manager = CredentialManager()
    return _credential_manager


def encrypt_credentials(credentials: Dict[str, Any]) -> str:
    """Convenience function to encrypt credentials."""
    return get_credential_manager().encrypt(credentials)


def decrypt_credentials(encrypted: str) -> Dict[str, Any]:
    """Convenience function to decrypt credentials."""
    return get_credential_manager().decrypt(encrypted)


class TenantCredentialManager:
    """
    Tenant-specific credential manager with isolated encryption key.

    Each tenant has a unique encryption key derived from the base secret
    and their tenant ID. This ensures:
    - Key isolation between tenants
    - Compromised keys don't affect other tenants
    - Per-tenant key rotation possible
    """

    def __init__(self, base_manager: CredentialManager, tenant_id: str):
        """
        Initialize tenant-specific credential manager.

        Args:
            base_manager: Parent CredentialManager instance
            tenant_id: Organization/tenant ID
        """
        self.base_manager = base_manager
        self.tenant_id = tenant_id

        secret = os.environ.get("CREDENTIAL_SECRET", "default-dev-secret-change-in-production")
        self._fernet = base_manager._derive_key(secret, tenant_id)

    def encrypt(self, credentials: Dict[str, Any]) -> str:
        """Encrypt credentials with tenant-specific key."""
        json_str = json.dumps(credentials)
        encrypted = self._fernet.encrypt(json_str.encode())
        return encrypted.decode()

    def decrypt(self, encrypted_credentials: str) -> Dict[str, Any]:
        """Decrypt credentials with tenant-specific key."""
        if not encrypted_credentials:
            return {}

        try:
            decrypted = self._fernet.decrypt(encrypted_credentials.encode())
            return json.loads(decrypted.decode())
        except Exception as e:
            logger.error(f"Failed to decrypt credentials for tenant {self.tenant_id}: {e}")
            raise

    def store_llm_credential(self, credential: LLMCredential) -> str:
        """
        Store an LLM API key credential.

        Args:
            credential: LLMCredential to store

        Returns:
            Encrypted credential string for database storage
        """
        return self.encrypt(credential.to_dict())

    def retrieve_llm_credential(self, encrypted: str) -> Optional[LLMCredential]:
        """
        Retrieve an LLM API key credential.

        Args:
            encrypted: Encrypted credential string from database

        Returns:
            LLMCredential instance or None if decryption fails
        """
        data = self.decrypt(encrypted)
        if not data:
            return None
        try:
            return LLMCredential.from_dict(data)
        except Exception as e:
            logger.error(f"Failed to parse LLM credential: {e}")
            return None


class LLMCredentialStore:
    """
    In-memory store for LLM credentials with per-tenant isolation.

    For production, this should be backed by a database table.
    """

    def __init__(self):
        # tenant_id -> provider -> encrypted_credential
        self._credentials: Dict[str, Dict[str, str]] = {}
        self._manager = get_credential_manager()

    def store(self, tenant_id: str, provider: str, api_key: str, alias: Optional[str] = None) -> None:
        """
        Store an LLM API key for a tenant.

        Args:
            tenant_id: Organization/tenant ID
            provider: LLM provider (openai, anthropic, groq, etc.)
            api_key: API key value
            alias: Optional alias (e.g., "production", "development")
        """
        encryptor = self._manager.get_tenant_encryptor(tenant_id)
        credential = LLMCredential(
            provider=provider,
            api_key=api_key,
            organization_id=tenant_id,
            alias=alias,
        )
        encrypted = encryptor.store_llm_credential(credential)

        if tenant_id not in self._credentials:
            self._credentials[tenant_id] = {}
        self._credentials[tenant_id][provider] = encrypted

    def get(self, tenant_id: str, provider: str) -> Optional[str]:
        """
        Get an LLM API key for a tenant.

        Args:
            tenant_id: Organization/tenant ID
            provider: LLM provider

        Returns:
            API key string or None if not found
        """
        if tenant_id not in self._credentials:
            return None
        encrypted = self._credentials[tenant_id].get(provider)
        if not encrypted:
            return None

        encryptor = self._manager.get_tenant_encryptor(tenant_id)
        credential = encryptor.retrieve_llm_credential(encrypted)
        if credential and credential.is_active:
            return credential.api_key
        return None

    def list_providers(self, tenant_id: str) -> List[str]:
        """List LLM providers configured for a tenant."""
        if tenant_id not in self._credentials:
            return []
        return list(self._credentials[tenant_id].keys())

    def delete(self, tenant_id: str, provider: str) -> bool:
        """Delete an LLM credential for a tenant."""
        if tenant_id not in self._credentials:
            return False
        if provider in self._credentials[tenant_id]:
            del self._credentials[tenant_id][provider]
            return True
        return False


# Singleton LLM credential store
_llm_credential_store: Optional[LLMCredentialStore] = None


def get_llm_credential_store() -> LLMCredentialStore:
    """Get the singleton LLM credential store instance."""
    global _llm_credential_store
    if _llm_credential_store is None:
        _llm_credential_store = LLMCredentialStore()
    return _llm_credential_store
