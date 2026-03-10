"""
Integration Registry

Loads and manages integration configurations from YAML files.
Provides lookup and validation for integrations.
"""

import os
import logging
from pathlib import Path
from typing import Dict, List, Optional, Set
import yaml

from .schema import (
    IntegrationConfig,
    IntegrationCategory,
    AuthType,
    ActionConfig,
    ActionType,
)

logger = logging.getLogger(__name__)


class IntegrationRegistry:
    """
    Registry for declarative integration configurations.

    Loads integrations from YAML files and provides lookup/filtering.

    Usage:
        registry = IntegrationRegistry()
        registry.load_from_directory("backend/integrations/configs")

        discord = registry.get("discord")
        ai_integrations = registry.get_by_category(IntegrationCategory.AI)
    """

    def __init__(self):
        self._integrations: Dict[str, IntegrationConfig] = {}
        self._loaded_files: Set[str] = set()

    def load_from_directory(self, directory: str) -> int:
        """
        Load all YAML integration configs from a directory.

        Args:
            directory: Path to directory containing YAML files

        Returns:
            Number of integrations loaded
        """
        dir_path = Path(directory)
        if not dir_path.exists():
            logger.warning(f"Integration config directory not found: {directory}")
            return 0

        loaded = 0
        for file_path in dir_path.glob("*.yaml"):
            try:
                self.load_from_file(str(file_path))
                loaded += 1
            except Exception as e:
                logger.error(f"Failed to load integration from {file_path}: {e}")

        # Also load .yml files
        for file_path in dir_path.glob("*.yml"):
            try:
                self.load_from_file(str(file_path))
                loaded += 1
            except Exception as e:
                logger.error(f"Failed to load integration from {file_path}: {e}")

        logger.info(f"Loaded {loaded} integrations from {directory}")
        return loaded

    def load_from_file(self, file_path: str) -> IntegrationConfig:
        """
        Load a single integration config from a YAML file.

        Args:
            file_path: Path to YAML file

        Returns:
            Loaded IntegrationConfig
        """
        if file_path in self._loaded_files:
            logger.debug(f"Skipping already loaded file: {file_path}")
            return self._integrations[self._get_id_from_file(file_path)]

        with open(file_path, 'r') as f:
            data = yaml.safe_load(f)

        # Parse and validate config
        config = self._parse_config(data)

        # Register
        self._integrations[config.id] = config
        self._loaded_files.add(file_path)

        logger.debug(f"Loaded integration: {config.id} from {file_path}")
        return config

    def load_from_dict(self, data: Dict) -> IntegrationConfig:
        """
        Load an integration from a dictionary (useful for testing).

        Args:
            data: Integration config as dictionary

        Returns:
            Loaded IntegrationConfig
        """
        config = self._parse_config(data)
        self._integrations[config.id] = config
        return config

    def _parse_config(self, data: Dict) -> IntegrationConfig:
        """Parse and validate integration config data."""
        # Handle nested action configs
        if 'actions' in data and isinstance(data['actions'], dict):
            actions = {}
            for action_name, action_data in data['actions'].items():
                if isinstance(action_data, dict):
                    # Ensure action has a name
                    action_data['name'] = action_name

                    # Handle HTTP config shorthand
                    if 'url' in action_data and 'http' not in action_data:
                        action_data['http'] = {
                            'method': action_data.pop('method', 'POST'),
                            'url': action_data.pop('url'),
                            'headers': action_data.pop('headers', {}),
                            'body': action_data.pop('body', None),
                            'query_params': action_data.pop('query_params', None),
                        }
                        action_data['type'] = 'http'

                    # Handle SDK config shorthand
                    if 'handler' in action_data and 'sdk' not in action_data:
                        action_data['sdk'] = {
                            'handler': action_data.pop('handler'),
                        }
                        action_data['type'] = 'sdk'

                    actions[action_name] = ActionConfig(**action_data)
            data['actions'] = actions

        # Handle nested trigger configs
        if 'triggers' in data and isinstance(data['triggers'], dict):
            triggers = {}
            for trigger_name, trigger_data in data['triggers'].items():
                if isinstance(trigger_data, dict):
                    trigger_data['name'] = trigger_name
                    from .schema import TriggerConfig
                    triggers[trigger_name] = TriggerConfig(**trigger_data)
            data['triggers'] = triggers

        return IntegrationConfig(**data)

    def _get_id_from_file(self, file_path: str) -> str:
        """Extract integration ID from file path."""
        return Path(file_path).stem

    # ============ Lookup Methods ============

    def get(self, integration_id: str) -> Optional[IntegrationConfig]:
        """Get an integration by ID. Auto-reloads configs on cache miss."""
        result = self._integrations.get(integration_id)
        if result is None:
            # Reload from disk in case new YAML files were added
            default_dir = os.path.join(os.path.dirname(__file__), "configs")
            if os.path.exists(default_dir):
                self.load_from_directory(default_dir)
            result = self._integrations.get(integration_id)
        return result

    def get_all(self) -> List[IntegrationConfig]:
        """Get all registered integrations."""
        return list(self._integrations.values())

    def get_enabled(self) -> List[IntegrationConfig]:
        """Get all enabled integrations."""
        return [i for i in self._integrations.values() if i.is_enabled]

    def get_by_category(self, category: IntegrationCategory) -> List[IntegrationConfig]:
        """Get integrations by category."""
        return [i for i in self._integrations.values() if i.category == category]

    def get_by_auth_type(self, auth_type: AuthType) -> List[IntegrationConfig]:
        """Get integrations by authentication type."""
        return [i for i in self._integrations.values() if i.auth.type == auth_type]

    def get_oauth_integrations(self) -> List[IntegrationConfig]:
        """Get all OAuth-based integrations."""
        return self.get_by_auth_type(AuthType.OAUTH2)

    def get_api_key_integrations(self) -> List[IntegrationConfig]:
        """Get all API key-based integrations."""
        return [
            i for i in self._integrations.values()
            if i.auth.type in (AuthType.API_KEY, AuthType.BOT_TOKEN)
        ]

    def exists(self, integration_id: str) -> bool:
        """Check if an integration exists."""
        return integration_id in self._integrations

    def get_action(self, integration_id: str, action_name: str) -> Optional[ActionConfig]:
        """Get a specific action from an integration."""
        integration = self.get(integration_id)
        if integration:
            return integration.get_action(action_name)
        return None

    # ============ Registration Methods ============

    def register(self, config: IntegrationConfig) -> None:
        """Register an integration config directly."""
        self._integrations[config.id] = config

    def unregister(self, integration_id: str) -> bool:
        """Unregister an integration."""
        if integration_id in self._integrations:
            del self._integrations[integration_id]
            return True
        return False

    def clear(self) -> None:
        """Clear all registered integrations."""
        self._integrations.clear()
        self._loaded_files.clear()

    # ============ Serialization ============

    def to_list(self) -> List[Dict]:
        """
        Export all integrations as a list of dicts.
        Useful for API responses.
        """
        return [
            {
                "id": i.id,
                "name": i.name,
                "display_name": i.display_name,
                "description": i.description,
                "category": i.category.value,
                "icon_url": i.icon_url,
                "auth_type": i.auth.type.value,
                "requires_oauth": i.requires_oauth,
                "is_enabled": i.is_enabled,
                "actions": list(i.actions.keys()),
                "triggers": list(i.triggers.keys()),
            }
            for i in self._integrations.values()
        ]


# ============ Singleton Instance ============

_registry: Optional[IntegrationRegistry] = None


def get_integration_registry() -> IntegrationRegistry:
    """Get the global integration registry instance."""
    global _registry
    if _registry is None:
        _registry = IntegrationRegistry()
        # Auto-load from default directory
        default_dir = os.path.join(
            os.path.dirname(__file__),
            "configs"
        )
        if os.path.exists(default_dir):
            _registry.load_from_directory(default_dir)
    return _registry


def reload_integrations() -> int:
    """Reload all integrations from config files."""
    global _registry
    if _registry:
        _registry.clear()
    _registry = IntegrationRegistry()
    default_dir = os.path.join(
        os.path.dirname(__file__),
        "configs"
    )
    return _registry.load_from_directory(default_dir)
