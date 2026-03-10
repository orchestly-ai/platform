"""
Demo: API Key Management

Demonstrates the API key management system with:
- Key creation with secure generation
- SHA-256 hashing for secure storage
- Key verification
- Key rotation with grace period
- Rate limiting and IP whitelisting
- List and revoke operations
"""

import asyncio
import sys
from datetime import datetime, timedelta
from pathlib import Path

# Add parent directory to path so backend.* imports work
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from backend.database.session import AsyncSessionLocal, init_db
from backend.services.api_key_service import APIKeyService
from backend.shared.rbac_models import OrganizationModel
from sqlalchemy import text


async def main():
    """Run API key management demo."""
    print("🔐 API Key Management Demo")
    print("=" * 80)

    # Initialize database tables
    print("\n🔧 Initializing database...")
    await init_db()
    print("✅ Database initialized\n")

    # Ensure default organization exists
    async with AsyncSessionLocal() as db:
        try:
            result = await db.execute(
                text("SELECT organization_id FROM organizations WHERE organization_id = 'default-org'")
            )
            if not result.scalar_one_or_none():
                # Create default organization
                await db.execute(text("""
                    INSERT INTO organizations (organization_id, name, slug, plan, max_users, max_agents, enabled_features, is_active, created_at, updated_at)
                    VALUES ('default-org', 'Default Organization', 'default-org', 'enterprise', 100, 100, '[]', true, NOW(), NOW())
                """))
                await db.commit()
                print("✅ Created default organization\n")
        except Exception as e:
            print(f"⚠️  Organization setup: {e}\n")

    async with AsyncSessionLocal() as db:
        service = APIKeyService(db)

        # Test organization
        org_id = "default-org"
        user_id = "user_1"

        print("\n1️⃣  Creating API Keys")
        print("-" * 80)

        # Create live key
        live_key, live_key_data = await service.create_key(
            organization_id=org_id,
            name="Production API Key",
            is_live=True,
            permissions=["read", "write"],
            rate_limit_per_second=100,
            monthly_quota=1000000,
            created_by=user_id
        )
        print(f"✅ Created live key: {live_key}")
        print(f"   Prefix: {live_key_data['key_prefix']}")
        print(f"   Rate limit: {live_key_data['rate_limit_per_second']}/sec")
        print(f"   Monthly quota: {live_key_data['monthly_quota']:,}")

        # Create test key with IP whitelist
        test_key, test_key_data = await service.create_key(
            organization_id=org_id,
            name="Test API Key",
            is_live=False,
            permissions=["read"],
            rate_limit_per_second=10,
            ip_whitelist=["127.0.0.1", "192.168.1.100"],
            created_by=user_id
        )
        print(f"\n✅ Created test key: {test_key}")
        print(f"   Prefix: {test_key_data['key_prefix']}")
        print(f"   IP whitelist: {test_key_data['ip_whitelist']}")

        # Create expiring key
        expiring_key, expiring_key_data = await service.create_key(
            organization_id=org_id,
            name="Temporary API Key",
            is_live=True,
            permissions=["read"],
            rate_limit_per_second=50,
            expires_at=datetime.utcnow() + timedelta(days=30),
            created_by=user_id
        )
        print(f"\n✅ Created expiring key: {expiring_key}")
        print(f"   Expires: {expiring_key_data['expires_at']}")

        print("\n2️⃣  Listing API Keys")
        print("-" * 80)

        keys = await service.list_keys(org_id)
        print(f"Found {len(keys)} active keys:")
        for key in keys:
            print(f"  • {key['name']}")
            print(f"    Prefix: {key['key_prefix']}")
            print(f"    Created: {key['created_at']}")
            print(f"    Permissions: {', '.join(key['permissions'])}")

        print("\n3️⃣  Verifying API Keys")
        print("-" * 80)

        # Verify live key (should succeed)
        verified = await service.verify_key(live_key)
        if verified:
            print(f"✅ Live key verified successfully")
            print(f"   Organization: {verified['organization_id']}")
            print(f"   Permissions: {verified['permissions']}")
        else:
            print("❌ Live key verification failed")

        # Verify test key with allowed IP (should succeed)
        verified = await service.verify_key(test_key, ip_address="127.0.0.1")
        if verified:
            print(f"\n✅ Test key verified with allowed IP")
        else:
            print("\n❌ Test key verification with allowed IP failed")

        # Verify test key with disallowed IP (should fail)
        verified = await service.verify_key(test_key, ip_address="10.0.0.1")
        if verified:
            print("❌ Test key verified with disallowed IP (should have failed!)")
        else:
            print("✅ Test key correctly rejected for disallowed IP")

        # Verify invalid key (should fail)
        verified = await service.verify_key("ao_live_invalid_key_12345678")
        if verified:
            print("\n❌ Invalid key verified (should have failed!)")
        else:
            print("\n✅ Invalid key correctly rejected")

        print("\n4️⃣  Key Rotation with Grace Period")
        print("-" * 80)

        print(f"Original key: {live_key}")

        # Rotate the key (24-hour grace period)
        new_key, rotated_data = await service.rotate_key(
            key_id=live_key_data["id"],
            is_live=True,
            grace_period_hours=24
        )
        print(f"✅ Key rotated successfully")
        print(f"   New key: {new_key}")
        print(f"   New prefix: {rotated_data['key_prefix']}")
        print(f"   Has previous key: {rotated_data['has_previous_key']}")
        print(f"   Previous key expires: {rotated_data['previous_key_expires_at']}")

        # Verify old key still works during grace period
        verified = await service.verify_key(live_key)
        if verified:
            print(f"\n✅ Old key still valid during grace period")
        else:
            print("\n❌ Old key should still be valid during grace period!")

        # Verify new key works
        verified = await service.verify_key(new_key)
        if verified:
            print("✅ New key is valid")
        else:
            print("❌ New key should be valid!")

        print("\n5️⃣  Updating Rate Limits")
        print("-" * 80)

        success = await service.update_rate_limit(
            key_id=test_key_data["id"],
            rate_limit_per_second=20
        )
        if success:
            print(f"✅ Updated rate limit from 10/sec to 20/sec")

        # Verify update
        updated_key = await service.get_key(test_key_data["id"])
        print(f"   New rate limit: {updated_key['rate_limit_per_second']}/sec")

        print("\n6️⃣  Updating IP Whitelist")
        print("-" * 80)

        success = await service.update_ip_whitelist(
            key_id=test_key_data["id"],
            ip_whitelist=["127.0.0.1", "192.168.1.100", "192.168.1.101"]
        )
        if success:
            print(f"✅ Updated IP whitelist")

        # Verify update
        updated_key = await service.get_key(test_key_data["id"])
        print(f"   New whitelist: {updated_key['ip_whitelist']}")

        print("\n7️⃣  Revoking API Key")
        print("-" * 80)

        success = await service.revoke_key(
            key_id=expiring_key_data["id"],
            revoked_by=user_id
        )
        if success:
            print(f"✅ Revoked key: {expiring_key_data['name']}")

        # Verify revoked key doesn't work
        verified = await service.verify_key(expiring_key)
        if verified:
            print("❌ Revoked key should not be valid!")
        else:
            print("✅ Revoked key correctly rejected")

        # List keys including inactive
        print("\n8️⃣  Listing All Keys (including inactive)")
        print("-" * 80)

        all_keys = await service.list_keys(org_id, include_inactive=True)
        print(f"Found {len(all_keys)} total keys:")
        for key in all_keys:
            status = "🟢 Active" if key["is_active"] else "🔴 Revoked"
            print(f"  {status} {key['name']}")
            print(f"    Prefix: {key['key_prefix']}")
            if key["revoked_at"]:
                print(f"    Revoked: {key['revoked_at']}")

        print("\n9️⃣  Cleanup Expired Previous Keys")
        print("-" * 80)

        # This would normally be run as a periodic cleanup job
        cleaned = await service.cleanup_expired_previous_keys()
        print(f"Cleaned up {cleaned} expired previous keys")
        print("(Grace periods haven't expired yet, so nothing to clean)")

        print("\n" + "=" * 80)
        print("✅ API Key Management Demo Complete!")
        print("\n📊 Summary:")
        print(f"  • Created 3 API keys (live, test, expiring)")
        print(f"  • Verified key authentication with IP whitelisting")
        print(f"  • Rotated key with 24-hour grace period")
        print(f"  • Updated rate limits and IP whitelist")
        print(f"  • Revoked expired key")
        print("\n🔐 Security Features:")
        print(f"  • SHA-256 hashing (never store plaintext)")
        print(f"  • Key rotation with grace period")
        print(f"  • Rate limiting per second")
        print(f"  • Monthly quotas")
        print(f"  • IP whitelisting")
        print(f"  • Permission scopes")
        print(f"  • Expiration dates")


if __name__ == "__main__":
    asyncio.run(main())
