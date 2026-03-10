"""
API Key Service

Provides business logic for API key management including:
- Key generation with secure random tokens
- SHA-256 hashing for secure storage
- Key verification with rotation support
- Rate limiting and quota management
- IP whitelisting
"""

import hashlib
import secrets
from datetime import datetime, timedelta
from typing import List, Optional, Dict, Tuple

from sqlalchemy.ext.asyncio import AsyncSession

from backend.database.repositories import APIKeyRepository


class APIKeyService:
    """
    Service for API key management.

    Handles key generation, verification, rotation, and security.
    """

    # Key format: ao_live_<32 random chars> or ao_test_<32 random chars>
    KEY_PREFIX_LIVE = "ao_live_"
    KEY_PREFIX_TEST = "ao_test_"
    KEY_LENGTH = 32  # Random part length

    def __init__(self, db: AsyncSession):
        self.db = db
        self.repository = APIKeyRepository(db)

    @staticmethod
    def generate_key(is_live: bool = True) -> Tuple[str, str, str]:
        """
        Generate a new API key.

        Args:
            is_live: True for live key, False for test key

        Returns:
            Tuple of (full_key, key_hash, key_prefix)
            - full_key: The complete key to show user (ONLY shown once)
            - key_hash: SHA-256 hash to store in database
            - key_prefix: First 12 chars for display
        """
        prefix = APIKeyService.KEY_PREFIX_LIVE if is_live else APIKeyService.KEY_PREFIX_TEST
        random_part = secrets.token_urlsafe(APIKeyService.KEY_LENGTH)[:APIKeyService.KEY_LENGTH]
        full_key = f"{prefix}{random_part}"

        # Hash the key for storage
        key_hash = hashlib.sha256(full_key.encode()).hexdigest()

        # Prefix for display (e.g., "ao_live_abc1")
        key_prefix = full_key[:12]

        return full_key, key_hash, key_prefix

    @staticmethod
    def hash_key(key: str) -> str:
        """
        Hash an API key with SHA-256.

        Args:
            key: The API key to hash

        Returns:
            SHA-256 hash
        """
        return hashlib.sha256(key.encode()).hexdigest()

    async def create_key(
        self,
        organization_id: str,
        name: str,
        is_live: bool = True,
        permissions: Optional[List[str]] = None,
        rate_limit_per_second: int = 100,
        monthly_quota: Optional[int] = None,
        ip_whitelist: Optional[List[str]] = None,
        expires_at: Optional[datetime] = None,
        created_by: Optional[str] = None
    ) -> Tuple[str, Dict]:
        """
        Create a new API key.

        Args:
            organization_id: Organization ID
            name: Descriptive name for the key
            is_live: True for live key, False for test key
            permissions: List of permission strings
            rate_limit_per_second: Rate limit (default: 100)
            monthly_quota: Monthly request quota (None = unlimited)
            ip_whitelist: List of allowed IP addresses (None = all allowed)
            expires_at: Expiration timestamp
            created_by: User ID who created the key

        Returns:
            Tuple of (full_key, key_dict)
            - full_key: The complete key (ONLY returned once, never stored)
            - key_dict: Dictionary with key metadata
        """
        # Generate key
        full_key, key_hash, key_prefix = self.generate_key(is_live)

        # Create in database
        key_id = await self.repository.create(
            organization_id=organization_id,
            name=name,
            key_hash=key_hash,
            key_prefix=key_prefix,
            permissions=permissions,
            rate_limit_per_second=rate_limit_per_second,
            monthly_quota=monthly_quota,
            ip_whitelist=ip_whitelist,
            expires_at=expires_at,
            created_by=created_by
        )

        await self.db.commit()

        # Get created key
        api_key = await self.repository.get_by_id(key_id)
        key_dict = self.repository._to_dict(api_key)

        return full_key, key_dict

    async def verify_key(
        self,
        key: str,
        ip_address: Optional[str] = None
    ) -> Optional[Dict]:
        """
        Verify an API key.

        Checks:
        1. Key hash matches (current or previous during rotation)
        2. Key is active
        3. Key has not expired
        4. IP address is whitelisted (if whitelist configured)

        Args:
            key: The API key to verify
            ip_address: Client IP address for whitelist check

        Returns:
            Dict with key details if valid, None otherwise
        """
        key_hash = self.hash_key(key)

        # Verify key
        key_data = await self.repository.verify_key(key_hash)

        if not key_data:
            return None

        # Check IP whitelist if configured
        if key_data.get("ip_whitelist") and len(key_data["ip_whitelist"]) > 0:
            if not ip_address or ip_address not in key_data["ip_whitelist"]:
                return None

        await self.db.commit()

        return key_data

    async def list_keys(
        self,
        organization_id: str,
        include_inactive: bool = False,
        limit: int = 100,
        offset: int = 0
    ) -> List[Dict]:
        """
        List API keys for organization.

        Args:
            organization_id: Organization ID
            include_inactive: Include inactive/revoked keys
            limit: Maximum results
            offset: Offset for pagination

        Returns:
            List of API key dicts
        """
        return await self.repository.list_by_organization(
            organization_id=organization_id,
            include_inactive=include_inactive,
            limit=limit,
            offset=offset
        )

    async def get_key(self, key_id: int) -> Optional[Dict]:
        """
        Get API key by ID.

        Args:
            key_id: API key ID

        Returns:
            API key dict or None
        """
        api_key = await self.repository.get_by_id(key_id)
        if not api_key:
            return None

        return self.repository._to_dict(api_key)

    async def revoke_key(self, key_id: int, revoked_by: Optional[str] = None) -> bool:
        """
        Revoke an API key.

        Args:
            key_id: API key ID
            revoked_by: User ID who revoked the key

        Returns:
            True if revoked successfully
        """
        success = await self.repository.revoke(key_id, revoked_by)
        await self.db.commit()
        return success

    async def rotate_key(
        self,
        key_id: int,
        is_live: bool = True,
        grace_period_hours: int = 24
    ) -> Tuple[str, Dict]:
        """
        Rotate an API key with grace period.

        Generates a new key and moves the old key to previous_key_hash.
        The old key remains valid for the grace period.

        Args:
            key_id: API key ID to rotate
            is_live: True for live key, False for test key
            grace_period_hours: Hours to keep old key valid (default: 24)

        Returns:
            Tuple of (new_full_key, key_dict)
            - new_full_key: The new complete key (ONLY returned once)
            - key_dict: Updated key metadata

        Raises:
            ValueError: If key not found
        """
        # Get current key
        api_key = await self.repository.get_by_id(key_id)
        if not api_key:
            raise ValueError(f"API key {key_id} not found")

        # Generate new key
        new_full_key, new_key_hash, new_key_prefix = self.generate_key(is_live)

        # Rotate the key
        success = await self.repository.rotate(
            key_id=key_id,
            new_key_hash=new_key_hash,
            new_key_prefix=new_key_prefix,
            grace_period_hours=grace_period_hours
        )

        if not success:
            raise ValueError(f"Failed to rotate API key {key_id}")

        await self.db.commit()

        # Get updated key
        updated_key = await self.repository.get_by_id(key_id)
        key_dict = self.repository._to_dict(updated_key)

        return new_full_key, key_dict

    async def update_rate_limit(self, key_id: int, rate_limit_per_second: int) -> bool:
        """
        Update rate limit for API key.

        Args:
            key_id: API key ID
            rate_limit_per_second: New rate limit

        Returns:
            True if updated successfully
        """
        success = await self.repository.update_rate_limit(key_id, rate_limit_per_second)
        await self.db.commit()
        return success

    async def update_ip_whitelist(self, key_id: int, ip_whitelist: List[str]) -> bool:
        """
        Update IP whitelist for API key.

        Args:
            key_id: API key ID
            ip_whitelist: List of allowed IP addresses

        Returns:
            True if updated successfully
        """
        success = await self.repository.update_ip_whitelist(key_id, ip_whitelist)
        await self.db.commit()
        return success

    async def cleanup_expired_previous_keys(self) -> int:
        """
        Clean up expired previous keys (for rotation grace period).

        Sets previous_key_hash and previous_key_expires_at to NULL for keys
        where the grace period has expired.

        Returns:
            Number of keys cleaned up
        """
        from sqlalchemy import update
        from backend.database.models import APIKeyModel

        now = datetime.utcnow()

        result = await self.db.execute(
            update(APIKeyModel)
            .where(
                APIKeyModel.previous_key_hash.is_not(None),
                APIKeyModel.previous_key_expires_at <= now
            )
            .values(
                previous_key_hash=None,
                previous_key_expires_at=None
            )
        )

        await self.db.commit()
        return result.rowcount
