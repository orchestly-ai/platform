"""
OAuth Token Storage

Encrypted storage for OAuth tokens with auto-refresh support.
"""

import os
import json
import base64
import hashlib
from datetime import datetime, timedelta
from dataclasses import dataclass, field, asdict
from typing import Dict, List, Optional, Any
from cryptography.fernet import Fernet

# Singleton instance
_token_storage: Optional["OAuthTokenStorage"] = None


@dataclass
class OAuthToken:
    """OAuth token with metadata."""

    organization_id: str
    provider: str
    access_token: str
    refresh_token: Optional[str] = None
    token_type: str = "Bearer"
    expires_at: Optional[datetime] = None
    scopes: List[str] = field(default_factory=list)
    user_info: Dict[str, Any] = field(default_factory=dict)
    created_at: datetime = field(default_factory=datetime.utcnow)
    updated_at: datetime = field(default_factory=datetime.utcnow)

    def is_expired(self, buffer_seconds: int = 300) -> bool:
        """Check if token is expired or will expire soon."""
        if self.expires_at is None:
            return False  # No expiry = doesn't expire
        return datetime.utcnow() >= (self.expires_at - timedelta(seconds=buffer_seconds))

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for storage."""
        data = asdict(self)
        # Convert datetimes to ISO strings
        if self.expires_at:
            data["expires_at"] = self.expires_at.isoformat()
        data["created_at"] = self.created_at.isoformat()
        data["updated_at"] = self.updated_at.isoformat()
        return data

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "OAuthToken":
        """Create from dictionary."""
        # Convert ISO strings back to datetimes
        if data.get("expires_at"):
            data["expires_at"] = datetime.fromisoformat(data["expires_at"])
        if data.get("created_at"):
            data["created_at"] = datetime.fromisoformat(data["created_at"])
        if data.get("updated_at"):
            data["updated_at"] = datetime.fromisoformat(data["updated_at"])
        return cls(**data)


class OAuthTokenStorage:
    """
    Encrypted storage for OAuth tokens.

    In production, this would use a database (PostgreSQL).
    For development, we use an in-memory store with optional file persistence.
    """

    def __init__(self, encryption_key: Optional[str] = None, storage_path: Optional[str] = None):
        # Get or generate encryption key
        self._encryption_key = encryption_key or os.environ.get("OAUTH_ENCRYPTION_KEY")
        if not self._encryption_key:
            # Generate a key for development (not secure for production!)
            self._encryption_key = base64.urlsafe_b64encode(os.urandom(32)).decode()
            print(f"Warning: Generated temporary OAuth encryption key. Set OAUTH_ENCRYPTION_KEY for production.")

        self._fernet = Fernet(self._encryption_key.encode() if isinstance(self._encryption_key, str) else self._encryption_key)

        # Storage path for file persistence
        self._storage_path = storage_path or os.environ.get("OAUTH_TOKEN_STORAGE_PATH")

        # In-memory token store: {org_id}:{provider} -> encrypted_data
        self._tokens: Dict[str, str] = {}

        # Load from file if exists
        self._load_from_file()

    def _get_key(self, organization_id: str, provider: str) -> str:
        """Generate storage key."""
        return f"{organization_id}:{provider}"

    def _encrypt(self, data: str) -> str:
        """Encrypt data."""
        return self._fernet.encrypt(data.encode()).decode()

    def _decrypt(self, encrypted_data: str) -> str:
        """Decrypt data."""
        return self._fernet.decrypt(encrypted_data.encode()).decode()

    def _load_from_file(self):
        """Load tokens from file if exists."""
        if not self._storage_path or not os.path.exists(self._storage_path):
            return

        try:
            with open(self._storage_path, 'r') as f:
                self._tokens = json.load(f)
        except Exception as e:
            print(f"Error loading OAuth tokens from file: {e}")

    def _save_to_file(self):
        """Save tokens to file if path configured."""
        if not self._storage_path:
            return

        try:
            os.makedirs(os.path.dirname(self._storage_path), exist_ok=True)
            with open(self._storage_path, 'w') as f:
                json.dump(self._tokens, f)
        except Exception as e:
            print(f"Error saving OAuth tokens to file: {e}")

    async def store(self, token: OAuthToken) -> None:
        """Store an OAuth token (encrypted)."""
        key = self._get_key(token.organization_id, token.provider)
        token.updated_at = datetime.utcnow()

        # Encrypt the token data
        token_json = json.dumps(token.to_dict())
        encrypted = self._encrypt(token_json)

        self._tokens[key] = encrypted
        self._save_to_file()

    async def get(self, organization_id: str, provider: str) -> Optional[OAuthToken]:
        """Get an OAuth token (decrypted)."""
        key = self._get_key(organization_id, provider)
        encrypted = self._tokens.get(key)

        if not encrypted:
            return None

        try:
            token_json = self._decrypt(encrypted)
            token_data = json.loads(token_json)
            return OAuthToken.from_dict(token_data)
        except Exception as e:
            print(f"Error decrypting OAuth token: {e}")
            return None

    async def delete(self, organization_id: str, provider: str) -> bool:
        """Delete an OAuth token."""
        key = self._get_key(organization_id, provider)
        if key in self._tokens:
            del self._tokens[key]
            self._save_to_file()
            return True
        return False

    async def list_tokens(self, organization_id: str) -> List[OAuthToken]:
        """List all tokens for an organization."""
        tokens = []
        prefix = f"{organization_id}:"

        for key, encrypted in self._tokens.items():
            if key.startswith(prefix):
                try:
                    token_json = self._decrypt(encrypted)
                    token_data = json.loads(token_json)
                    tokens.append(OAuthToken.from_dict(token_data))
                except Exception:
                    continue

        return tokens

    async def update_access_token(
        self,
        organization_id: str,
        provider: str,
        access_token: str,
        expires_at: Optional[datetime] = None
    ) -> bool:
        """Update just the access token (after refresh)."""
        token = await self.get(organization_id, provider)
        if not token:
            return False

        token.access_token = access_token
        if expires_at:
            token.expires_at = expires_at

        await self.store(token)
        return True


def get_token_storage() -> OAuthTokenStorage:
    """Get singleton token storage."""
    global _token_storage
    if _token_storage is None:
        _token_storage = OAuthTokenStorage()
    return _token_storage
