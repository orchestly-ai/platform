"""
Organization OAuth Configuration Storage

Stores per-organization OAuth app credentials (Client ID + Secret)
for the hybrid approach where:
- Free users use platform defaults
- Enterprise users can configure their own OAuth apps
"""

import os
import json
from datetime import datetime
from dataclasses import dataclass, field, asdict
from typing import Dict, Optional, List
from cryptography.fernet import Fernet

# Singleton instance
_org_oauth_config_storage: Optional["OrganizationOAuthConfigStorage"] = None


@dataclass
class OrganizationOAuthConfig:
    """OAuth app configuration for an organization."""

    organization_id: str
    provider: str
    client_id: str
    client_secret: str  # Will be encrypted at rest
    custom_scopes: Optional[List[str]] = None  # Override default scopes
    enabled: bool = True
    created_at: datetime = field(default_factory=datetime.utcnow)
    updated_at: datetime = field(default_factory=datetime.utcnow)

    def to_dict(self) -> Dict:
        """Convert to dictionary."""
        data = asdict(self)
        data["created_at"] = self.created_at.isoformat()
        data["updated_at"] = self.updated_at.isoformat()
        return data

    @classmethod
    def from_dict(cls, data: Dict) -> "OrganizationOAuthConfig":
        """Create from dictionary."""
        if data.get("created_at"):
            data["created_at"] = datetime.fromisoformat(data["created_at"])
        if data.get("updated_at"):
            data["updated_at"] = datetime.fromisoformat(data["updated_at"])
        return cls(**data)


class OrganizationOAuthConfigStorage:
    """
    Storage for organization-specific OAuth configurations.

    In production, this would use a database.
    For development, uses in-memory with optional file persistence.
    """

    def __init__(self, encryption_key: Optional[str] = None, storage_path: Optional[str] = None):
        # Get or generate encryption key
        self._encryption_key = encryption_key or os.environ.get("OAUTH_ENCRYPTION_KEY")
        if not self._encryption_key:
            import base64
            self._encryption_key = base64.urlsafe_b64encode(os.urandom(32)).decode()

        self._fernet = Fernet(
            self._encryption_key.encode()
            if isinstance(self._encryption_key, str)
            else self._encryption_key
        )

        # Storage path for file persistence
        self._storage_path = storage_path or os.environ.get(
            "ORG_OAUTH_CONFIG_STORAGE_PATH",
            "/tmp/org_oauth_configs.json"
        )

        # In-memory store: {org_id}:{provider} -> config
        self._configs: Dict[str, str] = {}  # Encrypted

        self._load_from_file()

    def _get_key(self, organization_id: str, provider: str) -> str:
        return f"{organization_id}:{provider}"

    def _encrypt(self, data: str) -> str:
        return self._fernet.encrypt(data.encode()).decode()

    def _decrypt(self, encrypted_data: str) -> str:
        return self._fernet.decrypt(encrypted_data.encode()).decode()

    def _load_from_file(self):
        if not self._storage_path or not os.path.exists(self._storage_path):
            return
        try:
            with open(self._storage_path, 'r') as f:
                self._configs = json.load(f)
        except Exception as e:
            print(f"Error loading org OAuth configs: {e}")

    def _save_to_file(self):
        if not self._storage_path:
            return
        try:
            os.makedirs(os.path.dirname(self._storage_path), exist_ok=True)
            with open(self._storage_path, 'w') as f:
                json.dump(self._configs, f)
        except Exception as e:
            print(f"Error saving org OAuth configs: {e}")

    async def save(self, config: OrganizationOAuthConfig) -> None:
        """Save organization OAuth config (encrypted)."""
        key = self._get_key(config.organization_id, config.provider)
        config.updated_at = datetime.utcnow()

        config_json = json.dumps(config.to_dict())
        encrypted = self._encrypt(config_json)

        self._configs[key] = encrypted
        self._save_to_file()

    async def get(self, organization_id: str, provider: str) -> Optional[OrganizationOAuthConfig]:
        """Get organization OAuth config (decrypted)."""
        key = self._get_key(organization_id, provider)
        encrypted = self._configs.get(key)

        if not encrypted:
            return None

        try:
            config_json = self._decrypt(encrypted)
            config_data = json.loads(config_json)
            return OrganizationOAuthConfig.from_dict(config_data)
        except Exception as e:
            print(f"Error decrypting org OAuth config: {e}")
            return None

    async def delete(self, organization_id: str, provider: str) -> bool:
        """Delete organization OAuth config."""
        key = self._get_key(organization_id, provider)
        if key in self._configs:
            del self._configs[key]
            self._save_to_file()
            return True
        return False

    async def list_for_org(self, organization_id: str) -> List[OrganizationOAuthConfig]:
        """List all OAuth configs for an organization."""
        configs = []
        prefix = f"{organization_id}:"

        for key, encrypted in self._configs.items():
            if key.startswith(prefix):
                try:
                    config_json = self._decrypt(encrypted)
                    config_data = json.loads(config_json)
                    configs.append(OrganizationOAuthConfig.from_dict(config_data))
                except Exception:
                    continue

        return configs

    async def has_custom_config(self, organization_id: str, provider: str) -> bool:
        """Check if organization has custom OAuth config."""
        config = await self.get(organization_id, provider)
        return config is not None and config.enabled


def get_org_oauth_config_storage() -> OrganizationOAuthConfigStorage:
    """Get singleton organization OAuth config storage."""
    global _org_oauth_config_storage
    if _org_oauth_config_storage is None:
        _org_oauth_config_storage = OrganizationOAuthConfigStorage()
    return _org_oauth_config_storage
