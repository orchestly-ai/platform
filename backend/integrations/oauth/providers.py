"""
OAuth Provider Configuration

Loads OAuth provider configs from YAML files and provides
access to OAuth endpoints and settings.
"""

import os
import yaml
from pathlib import Path
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Any

# Singleton instance
_provider_registry: Optional["OAuthProviderRegistry"] = None


@dataclass
class OAuthProviderConfig:
    """Configuration for an OAuth provider."""

    id: str
    name: str
    display_name: str
    description: str
    icon_url: str

    # OAuth endpoints
    authorization_url: str
    token_url: str
    revoke_url: Optional[str]
    userinfo_url: Optional[str]

    # Credentials (loaded from env)
    client_id: str
    client_secret: str

    # Scopes
    default_scopes: List[str] = field(default_factory=list)
    user_scopes: List[str] = field(default_factory=list)

    # Extra parameters for authorization
    extra_params: Dict[str, str] = field(default_factory=dict)
    extra_headers: Dict[str, str] = field(default_factory=dict)

    # Token settings
    token_expiry_buffer_seconds: int = 300

    @classmethod
    def from_yaml(cls, yaml_path: Path) -> "OAuthProviderConfig":
        """Load provider config from YAML file."""
        with open(yaml_path) as f:
            data = yaml.safe_load(f)

        oauth = data.get("oauth", {})

        # Load credentials from environment
        client_id_env = oauth.get("client_id_env", "")
        client_secret_env = oauth.get("client_secret_env", "")

        client_id = os.environ.get(client_id_env, "")
        client_secret = os.environ.get(client_secret_env, "")

        return cls(
            id=data.get("id", yaml_path.stem),
            name=data.get("name", yaml_path.stem),
            display_name=data.get("display_name", yaml_path.stem),
            description=data.get("description", ""),
            icon_url=data.get("icon_url", ""),
            # OAuth endpoints
            authorization_url=oauth.get("authorization_url", ""),
            token_url=oauth.get("token_url", ""),
            revoke_url=oauth.get("revoke_url"),
            userinfo_url=oauth.get("userinfo_url"),
            # Credentials
            client_id=client_id,
            client_secret=client_secret,
            # Scopes
            default_scopes=oauth.get("default_scopes", []),
            user_scopes=oauth.get("user_scopes", []),
            # Extra params
            extra_params=oauth.get("extra_params", {}),
            extra_headers=oauth.get("extra_headers", {}),
            # Token settings
            token_expiry_buffer_seconds=oauth.get("token_expiry_buffer_seconds", 300),
        )

    def is_configured(self) -> bool:
        """Check if provider has valid credentials."""
        return bool(self.client_id and self.client_secret)


class OAuthProviderRegistry:
    """Registry of OAuth providers loaded from YAML configs."""

    def __init__(self, configs_dir: Optional[Path] = None):
        self.configs_dir = configs_dir or self._default_configs_dir()
        self._providers: Dict[str, OAuthProviderConfig] = {}
        self._load_providers()

    def _default_configs_dir(self) -> Path:
        """Get default configs directory."""
        return Path(__file__).parent / "configs"

    def _load_providers(self):
        """Load all provider configs from YAML files."""
        if not self.configs_dir.exists():
            return

        for yaml_file in self.configs_dir.glob("*.yaml"):
            try:
                config = OAuthProviderConfig.from_yaml(yaml_file)
                self._providers[config.id] = config
            except Exception as e:
                print(f"Error loading OAuth config {yaml_file}: {e}")

    def get(self, provider_id: str) -> Optional[OAuthProviderConfig]:
        """Get provider config by ID."""
        return self._providers.get(provider_id)

    def list_providers(self) -> List[OAuthProviderConfig]:
        """List all available providers."""
        return list(self._providers.values())

    def list_configured_providers(self) -> List[OAuthProviderConfig]:
        """List providers with valid credentials."""
        return [p for p in self._providers.values() if p.is_configured()]

    def reload(self):
        """Reload all provider configs."""
        self._providers.clear()
        self._load_providers()


def get_oauth_provider_registry() -> OAuthProviderRegistry:
    """Get singleton OAuth provider registry."""
    global _provider_registry
    if _provider_registry is None:
        _provider_registry = OAuthProviderRegistry()
    return _provider_registry
