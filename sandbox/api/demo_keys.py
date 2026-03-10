"""
Demo API Key Manager for Sandbox Environment

Manages demo API keys with:
- Automatic generation
- Expiration (24 hours by default)
- Usage tracking
- Tier management
"""

import secrets
import hashlib
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Dict, Optional, List
from enum import Enum


class KeyTier(Enum):
    """Demo API key tiers."""
    PLAYGROUND = "playground"  # Interactive playground, most limited
    DEMO = "demo"  # Standard demo tier
    TRIAL = "trial"  # Extended trial
    INVESTOR = "investor"  # Investor demo, higher limits


@dataclass
class DemoApiKey:
    """A demo API key with metadata."""
    key_id: str
    hashed_key: str
    tier: KeyTier
    created_at: datetime
    expires_at: datetime
    metadata: Dict = field(default_factory=dict)
    is_active: bool = True
    usage_count: int = 0
    last_used: Optional[datetime] = None

    def is_expired(self) -> bool:
        """Check if key is expired."""
        return datetime.utcnow() > self.expires_at

    def is_valid(self) -> bool:
        """Check if key is valid for use."""
        return self.is_active and not self.is_expired()


class DemoKeyManager:
    """
    Manager for demo API keys.

    Handles creation, validation, and cleanup of demo keys.
    """

    # Pre-defined demo keys for consistent demos
    PREDEFINED_KEYS = {
        "demo-key-xxx": {
            "tier": KeyTier.DEMO,
            "metadata": {"name": "Website Demo Key", "permanent": True},
            "ttl_hours": 24 * 365,  # 1 year for demo key
        },
        "playground-key-xxx": {
            "tier": KeyTier.PLAYGROUND,
            "metadata": {"name": "Playground Key", "permanent": True},
            "ttl_hours": 24 * 365,
        },
        "investor-demo-key": {
            "tier": KeyTier.INVESTOR,
            "metadata": {"name": "Investor Demo Key", "permanent": True},
            "ttl_hours": 24 * 365,
        },
    }

    def __init__(self, default_ttl_hours: int = 24):
        """
        Initialize the key manager.

        Args:
            default_ttl_hours: Default time-to-live for generated keys
        """
        self.default_ttl_hours = default_ttl_hours
        self._keys: Dict[str, DemoApiKey] = {}
        self._key_lookup: Dict[str, str] = {}  # raw_key -> key_id

        # Initialize predefined keys
        self._init_predefined_keys()

    def _init_predefined_keys(self):
        """Initialize predefined demo keys."""
        for raw_key, config in self.PREDEFINED_KEYS.items():
            key_id = f"demo_{secrets.token_hex(4)}"
            hashed = self._hash_key(raw_key)

            demo_key = DemoApiKey(
                key_id=key_id,
                hashed_key=hashed,
                tier=config["tier"],
                created_at=datetime.utcnow(),
                expires_at=datetime.utcnow() + timedelta(hours=config["ttl_hours"]),
                metadata=config["metadata"],
            )

            self._keys[key_id] = demo_key
            self._key_lookup[raw_key] = key_id

    def _hash_key(self, raw_key: str) -> str:
        """Hash an API key for storage."""
        return hashlib.sha256(raw_key.encode()).hexdigest()

    def create_key(
        self,
        tier: KeyTier = KeyTier.DEMO,
        ttl_hours: Optional[int] = None,
        metadata: Optional[Dict] = None,
    ) -> tuple:
        """
        Create a new demo API key.

        Args:
            tier: The tier for this key
            ttl_hours: Time-to-live in hours (default: 24)
            metadata: Optional metadata

        Returns:
            Tuple of (raw_key, DemoApiKey)
        """
        ttl = ttl_hours or self.default_ttl_hours

        # Generate unique key
        raw_key = f"demo_{secrets.token_urlsafe(24)}"
        key_id = f"demo_{secrets.token_hex(8)}"
        hashed = self._hash_key(raw_key)

        demo_key = DemoApiKey(
            key_id=key_id,
            hashed_key=hashed,
            tier=tier,
            created_at=datetime.utcnow(),
            expires_at=datetime.utcnow() + timedelta(hours=ttl),
            metadata=metadata or {},
        )

        self._keys[key_id] = demo_key
        self._key_lookup[raw_key] = key_id

        return (raw_key, demo_key)

    def validate_key(self, raw_key: str) -> Optional[DemoApiKey]:
        """
        Validate an API key.

        Args:
            raw_key: The raw API key to validate

        Returns:
            DemoApiKey if valid, None otherwise
        """
        key_id = self._key_lookup.get(raw_key)
        if not key_id:
            return None

        demo_key = self._keys.get(key_id)
        if not demo_key:
            return None

        if not demo_key.is_valid():
            return None

        # Update usage
        demo_key.usage_count += 1
        demo_key.last_used = datetime.utcnow()

        return demo_key

    def get_key_info(self, raw_key: str) -> Optional[Dict]:
        """Get info about an API key (for display)."""
        key_id = self._key_lookup.get(raw_key)
        if not key_id:
            return None

        demo_key = self._keys.get(key_id)
        if not demo_key:
            return None

        return {
            "key_id": demo_key.key_id,
            "tier": demo_key.tier.value,
            "created_at": demo_key.created_at.isoformat(),
            "expires_at": demo_key.expires_at.isoformat(),
            "is_active": demo_key.is_active,
            "is_expired": demo_key.is_expired(),
            "usage_count": demo_key.usage_count,
            "metadata": demo_key.metadata,
        }

    def revoke_key(self, key_id: str) -> bool:
        """Revoke an API key."""
        demo_key = self._keys.get(key_id)
        if not demo_key:
            return False

        demo_key.is_active = False
        return True

    def cleanup_expired(self) -> int:
        """
        Clean up expired keys.

        Returns:
            Number of keys removed
        """
        expired_ids = [
            key_id for key_id, key in self._keys.items()
            if key.is_expired() and not key.metadata.get("permanent", False)
        ]

        for key_id in expired_ids:
            # Remove from lookup
            for raw, kid in list(self._key_lookup.items()):
                if kid == key_id:
                    del self._key_lookup[raw]
                    break
            del self._keys[key_id]

        return len(expired_ids)

    def list_keys(self, include_expired: bool = False) -> List[Dict]:
        """List all keys."""
        keys = []
        for demo_key in self._keys.values():
            if not include_expired and demo_key.is_expired():
                continue
            keys.append({
                "key_id": demo_key.key_id,
                "tier": demo_key.tier.value,
                "is_active": demo_key.is_active,
                "is_expired": demo_key.is_expired(),
                "usage_count": demo_key.usage_count,
                "created_at": demo_key.created_at.isoformat(),
                "expires_at": demo_key.expires_at.isoformat(),
            })
        return keys

    def get_stats(self) -> Dict:
        """Get overall stats."""
        total = len(self._keys)
        active = sum(1 for k in self._keys.values() if k.is_valid())
        expired = sum(1 for k in self._keys.values() if k.is_expired())
        total_usage = sum(k.usage_count for k in self._keys.values())

        by_tier = {}
        for tier in KeyTier:
            by_tier[tier.value] = sum(
                1 for k in self._keys.values()
                if k.tier == tier and k.is_valid()
            )

        return {
            "total_keys": total,
            "active_keys": active,
            "expired_keys": expired,
            "total_usage": total_usage,
            "by_tier": by_tier,
        }


# Singleton
_demo_key_manager: Optional[DemoKeyManager] = None


def get_demo_key_manager() -> DemoKeyManager:
    """Get or create the demo key manager singleton."""
    global _demo_key_manager
    if _demo_key_manager is None:
        _demo_key_manager = DemoKeyManager()
    return _demo_key_manager
