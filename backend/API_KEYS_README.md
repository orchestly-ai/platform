# API Key Management System

## Overview

The API key management system provides secure, persistent storage of API keys in PostgreSQL with:

- **SHA-256 hashing** - Keys are never stored in plaintext
- **Key rotation** - Graceful key rotation with configurable grace periods
- **Rate limiting** - Per-second rate limits for each key
- **Monthly quotas** - Optional monthly request quotas
- **IP whitelisting** - Restrict keys to specific IP addresses
- **Permission scopes** - Fine-grained permission control
- **Expiration dates** - Optional key expiration
- **Audit trail** - Track creation, rotation, and revocation

## Architecture

### Database Schema

The `api_keys` table includes:

```sql
CREATE TABLE api_keys (
    id SERIAL PRIMARY KEY,
    organization_id VARCHAR(255) NOT NULL REFERENCES organizations(id),
    key_hash VARCHAR(64) NOT NULL UNIQUE,  -- SHA-256 hash
    key_prefix VARCHAR(12) NOT NULL,       -- "ao_live_abc1" for display
    name VARCHAR(255),
    permissions JSONB DEFAULT '[]',
    rate_limit_per_second INT DEFAULT 100,
    monthly_quota INT,
    ip_whitelist JSONB DEFAULT '[]',
    is_active BOOLEAN DEFAULT TRUE,
    last_used_at TIMESTAMP,
    expires_at TIMESTAMP,
    created_at TIMESTAMP DEFAULT NOW(),
    created_by VARCHAR(100),
    revoked_at TIMESTAMP,
    revoked_by VARCHAR(100),
    previous_key_hash VARCHAR(64),          -- For rotation grace period
    previous_key_expires_at TIMESTAMP
);
```

### Components

1. **APIKeyModel** (`database/models.py`)
   - SQLAlchemy ORM model
   - Defines schema and relationships
   - Uses UniversalJSON for PostgreSQL/SQLite compatibility

2. **APIKeyRepository** (`database/repositories.py`)
   - Data access layer
   - CRUD operations
   - Key verification with rotation support
   - Query methods for listing and filtering

3. **APIKeyService** (`services/api_key_service.py`)
   - Business logic layer
   - Secure key generation
   - SHA-256 hashing
   - Key rotation with grace period
   - Rate limit and IP whitelist management

## Usage

### Creating an API Key

```python
from services.api_key_service import APIKeyService

service = APIKeyService(db)

# Create a live API key
full_key, key_data = await service.create_key(
    organization_id="org_123",
    name="Production API Key",
    is_live=True,
    permissions=["read", "write"],
    rate_limit_per_second=100,
    monthly_quota=1000000,
    created_by="user_456"
)

# Save the full_key - it's only returned once!
print(f"Your API key: {full_key}")
# Output: ao_live_Xa9kL2mP4nQ8rT1wV5yZ3bC7dF6gH
```

### Verifying an API Key

```python
# Verify key
key_data = await service.verify_key(api_key)

if key_data:
    print(f"Valid key for org: {key_data['organization_id']}")
    print(f"Permissions: {key_data['permissions']}")
    print(f"Rate limit: {key_data['rate_limit_per_second']}/sec")
else:
    print("Invalid or expired key")

# Verify with IP whitelist check
key_data = await service.verify_key(api_key, ip_address="192.168.1.100")
```

### Rotating an API Key

```python
# Rotate key with 24-hour grace period
new_key, key_data = await service.rotate_key(
    key_id=123,
    is_live=True,
    grace_period_hours=24
)

print(f"New key: {new_key}")
print(f"Old key valid until: {key_data['previous_key_expires_at']}")

# During grace period, both old and new keys work
old_key_valid = await service.verify_key(old_key)  # ✅ Valid
new_key_valid = await service.verify_key(new_key)  # ✅ Valid

# After grace period expires, only new key works
```

### Listing API Keys

```python
# List active keys
keys = await service.list_keys(organization_id="org_123")

for key in keys:
    print(f"{key['name']}: {key['key_prefix']}...")

# List all keys including revoked
all_keys = await service.list_keys(
    organization_id="org_123",
    include_inactive=True
)
```

### Revoking an API Key

```python
# Revoke a key
success = await service.revoke_key(
    key_id=123,
    revoked_by="user_456"
)

# Revoked keys immediately fail verification
key_data = await service.verify_key(revoked_key)  # None
```

### Updating Rate Limits

```python
# Update rate limit
await service.update_rate_limit(
    key_id=123,
    rate_limit_per_second=200
)

# Update IP whitelist
await service.update_ip_whitelist(
    key_id=123,
    ip_whitelist=["192.168.1.100", "192.168.1.101"]
)
```

## Security Features

### SHA-256 Hashing

Keys are hashed using SHA-256 before storage:

```python
key_hash = hashlib.sha256(api_key.encode()).hexdigest()
```

The plaintext key is:
- Only shown once during creation
- Never stored in the database
- Never logged or transmitted insecurely

### Key Format

Keys follow this format:
- **Live keys**: `ao_live_<32 random chars>`
- **Test keys**: `ao_test_<32 random chars>`

Random portion uses `secrets.token_urlsafe()` for cryptographic strength.

### Key Rotation

Rotation process:
1. Generate new key with SHA-256 hash
2. Move current key hash to `previous_key_hash`
3. Set `previous_key_expires_at` to NOW + grace period
4. Update `key_hash` and `key_prefix` to new values

During grace period:
- Both old and new keys work
- Verification checks both `key_hash` and `previous_key_hash`
- After grace period, cleanup job removes old hash

### IP Whitelisting

When IP whitelist is configured:
- Empty list = all IPs allowed
- Non-empty list = only listed IPs allowed
- Verification fails if client IP not in whitelist

### Rate Limiting

Rate limits are stored per-key and can be enforced by:
- API gateway middleware
- Application-level rate limiting
- Redis-based distributed rate limiting

## Database Migration

The migration `20260114_1000_enhance_api_keys.py` adds:
- `rate_limit_per_second` - Rate limit (default: 100)
- `monthly_quota` - Monthly request quota
- `ip_whitelist` - JSONB array of allowed IPs
- `created_by` - User who created the key
- `revoked_by` - User who revoked the key
- `previous_key_hash` - For rotation grace period
- `previous_key_expires_at` - When old key expires

Run migration:
```bash
alembic upgrade head
```

## Testing

Run the demo script:
```bash
cd backend
export USE_SQLITE=true
python init_api_keys_sqlite.py  # Initialize tables
python demo_api_keys.py         # Run comprehensive demo
```

The demo covers:
1. Creating live, test, and expiring keys
2. Listing keys
3. Verifying keys with IP whitelist
4. Rotating keys with grace period
5. Updating rate limits and IP whitelist
6. Revoking keys
7. Cleanup of expired previous keys

## API Endpoints

Example FastAPI endpoints:

```python
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

router = APIRouter(prefix="/api/keys", tags=["API Keys"])

@router.post("/")
async def create_api_key(
    name: str,
    permissions: List[str],
    db: AsyncSession = Depends(get_db)
):
    service = APIKeyService(db)
    full_key, key_data = await service.create_key(
        organization_id=current_org_id,
        name=name,
        permissions=permissions,
        created_by=current_user_id
    )
    return {"key": full_key, "data": key_data}

@router.get("/")
async def list_api_keys(db: AsyncSession = Depends(get_db)):
    service = APIKeyService(db)
    keys = await service.list_keys(current_org_id)
    return {"keys": keys}

@router.post("/{key_id}/rotate")
async def rotate_api_key(
    key_id: int,
    db: AsyncSession = Depends(get_db)
):
    service = APIKeyService(db)
    new_key, key_data = await service.rotate_key(key_id)
    return {"key": new_key, "data": key_data}

@router.delete("/{key_id}")
async def revoke_api_key(
    key_id: int,
    db: AsyncSession = Depends(get_db)
):
    service = APIKeyService(db)
    await service.revoke_key(key_id, current_user_id)
    return {"success": True}
```

## Maintenance

### Cleanup Expired Previous Keys

Run periodically (e.g., daily cron job):

```python
service = APIKeyService(db)
cleaned = await service.cleanup_expired_previous_keys()
print(f"Cleaned up {cleaned} expired previous keys")
```

This removes old key hashes after the grace period expires, keeping the database clean.

## Implementation Files

- `backend/alembic/versions/20260114_1000_enhance_api_keys.py` - Database migration
- `backend/database/models.py` - APIKeyModel (lines 392-455)
- `backend/database/repositories.py` - APIKeyRepository (lines 847-1084)
- `backend/services/api_key_service.py` - APIKeyService
- `backend/demo_api_keys.py` - Comprehensive demo script

## Security Best Practices

1. **Never log full API keys** - Only log key prefixes
2. **Use HTTPS** - Always transmit keys over encrypted connections
3. **Rotate regularly** - Set up automatic rotation schedules
4. **Set expiration dates** - For temporary or contractor access
5. **Use IP whitelisting** - When client IPs are known
6. **Monitor usage** - Track last_used_at for anomaly detection
7. **Revoke compromised keys** - Immediate revocation on breach
8. **Use test keys for development** - Separate from production
9. **Implement rate limiting** - Prevent API abuse
10. **Audit key operations** - Track all creation, rotation, and revocation events
