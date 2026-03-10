# Hybrid OAuth System

> **CONFIDENTIAL - INTERNAL USE ONLY**
>
> This document describes our proprietary hybrid OAuth architecture.

## Overview

The Hybrid OAuth System is a key differentiator that allows customers to:
1. Start immediately with platform-managed OAuth apps
2. Seamlessly migrate to their own OAuth credentials
3. Mix platform and custom credentials per provider

**Why this matters:** Competitors require customers to create OAuth apps before using integrations. We provide instant onboarding with upgrade path.

## Architecture

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                         OAuth Request Flow                                   │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                              │
│  Customer App                                                                │
│       │                                                                      │
│       ▼                                                                      │
│  ┌─────────────────────────────────────────────────────────────────────┐   │
│  │                    OAuth Manager Service                             │   │
│  │  ┌─────────────────────────────────────────────────────────────┐   │   │
│  │  │  1. Lookup OrganizationOAuthConfig for (org_id, provider)   │   │   │
│  │  └─────────────────────────────────────────────────────────────┘   │   │
│  │                              │                                      │   │
│  │              ┌───────────────┴───────────────┐                     │   │
│  │              ▼                               ▼                     │   │
│  │  ┌─────────────────────────┐   ┌─────────────────────────┐        │   │
│  │  │   Custom Config Found   │   │   No Custom Config      │        │   │
│  │  │   Use customer's app    │   │   Use platform defaults │        │   │
│  │  │   credentials           │   │   from YAML configs     │        │   │
│  │  └───────────┬─────────────┘   └───────────┬─────────────┘        │   │
│  │              │                               │                     │   │
│  │              └───────────────┬───────────────┘                     │   │
│  │                              ▼                                      │   │
│  │  ┌─────────────────────────────────────────────────────────────┐   │   │
│  │  │  2. Build OAuth URL with selected credentials               │   │   │
│  │  │     - client_id (custom or platform)                        │   │   │
│  │  │     - redirect_uri (always platform URL)                    │   │
│  │  │     - scopes (custom or provider defaults)                  │   │   │
│  │  └─────────────────────────────────────────────────────────────┘   │   │
│  │                              │                                      │   │
│  │                              ▼                                      │   │
│  │  ┌─────────────────────────────────────────────────────────────┐   │   │
│  │  │  3. Handle callback                                          │   │   │
│  │  │     - Exchange code using same credentials                  │   │   │
│  │  │     - Store tokens in IntegrationCredentials                │   │   │
│  │  └─────────────────────────────────────────────────────────────┘   │   │
│  └─────────────────────────────────────────────────────────────────────┘   │
│                                                                              │
└─────────────────────────────────────────────────────────────────────────────┘
```

## Data Model

### Platform OAuth Configs (YAML)

```yaml
# backend/integrations/oauth/configs/google.yaml
name: Google
provider_id: google
auth_url: https://accounts.google.com/o/oauth2/v2/auth
token_url: https://oauth2.googleapis.com/token

# Platform-managed credentials (encrypted in production)
platform_client_id: ${GOOGLE_PLATFORM_CLIENT_ID}
platform_client_secret: ${GOOGLE_PLATFORM_CLIENT_SECRET}

scopes:
  default:
    - openid
    - email
    - profile
  calendar:
    - https://www.googleapis.com/auth/calendar
  drive:
    - https://www.googleapis.com/auth/drive.readonly
```

### Organization OAuth Configs (Database)

```sql
CREATE TABLE organization_oauth_config (
    id SERIAL PRIMARY KEY,
    organization_id VARCHAR(255) NOT NULL,
    provider VARCHAR(50) NOT NULL,
    client_id VARCHAR(512) NOT NULL,           -- Encrypted
    client_secret VARCHAR(512) NOT NULL,        -- Encrypted
    custom_scopes TEXT[],                       -- Optional override
    redirect_uri_override VARCHAR(512),         -- Usually NULL
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW(),
    created_by VARCHAR(255) NOT NULL,

    UNIQUE(organization_id, provider)
);
```

## Credential Resolution Algorithm

```python
def get_oauth_credentials(org_id: str, provider: str) -> OAuthCredentials:
    """
    Resolve OAuth credentials for an organization.

    Priority:
    1. Organization-specific custom config (if exists)
    2. Platform-managed defaults
    """
    # Check for custom config
    custom_config = db.query(OrganizationOAuthConfig).filter(
        OrganizationOAuthConfig.organization_id == org_id,
        OrganizationOAuthConfig.provider == provider
    ).first()

    if custom_config:
        return OAuthCredentials(
            client_id=decrypt(custom_config.client_id),
            client_secret=decrypt(custom_config.client_secret),
            scopes=custom_config.custom_scopes or get_default_scopes(provider),
            source="organization_config"
        )

    # Fall back to platform defaults
    platform_config = load_provider_config(provider)
    return OAuthCredentials(
        client_id=platform_config.platform_client_id,
        client_secret=platform_config.platform_client_secret,
        scopes=platform_config.scopes["default"],
        source="platform_default"
    )
```

## Security Considerations

### Secret Storage

```python
# All secrets encrypted at rest using organization-specific keys
class EncryptedCredentialStore:
    def store_client_secret(self, org_id: str, provider: str, secret: str):
        key = derive_key(org_id, MASTER_KEY)
        encrypted = encrypt_aes256(secret, key)
        # Store encrypted value

    def retrieve_client_secret(self, org_id: str, provider: str) -> str:
        key = derive_key(org_id, MASTER_KEY)
        encrypted = fetch_from_db(org_id, provider)
        return decrypt_aes256(encrypted, key)
```

### Redirect URI Security

```python
# Only platform-controlled redirect URIs allowed
ALLOWED_REDIRECT_PATTERNS = [
    "https://{tenant}.ourplatform.com/oauth/callback",
    "https://api.ourplatform.com/oauth/callback/{provider}",
]

def validate_redirect_uri(uri: str) -> bool:
    """Never allow custom redirect URIs to prevent token theft."""
    return any(matches_pattern(uri, pattern) for pattern in ALLOWED_REDIRECT_PATTERNS)
```

## Migration Path

### Step 1: Customer Using Platform App
```
Customer → Platform OAuth App → Provider
         (our client_id)
```

### Step 2: Customer Creates Own App
```
1. Customer creates OAuth app in provider console
2. Customer adds their client_id/secret in our Settings UI
3. We store encrypted in OrganizationOAuthConfig
```

### Step 3: Seamless Switch
```
Customer → Customer's OAuth App → Provider
         (their client_id)

No token migration needed - new connections use new app,
existing tokens continue working until refreshed.
```

## API Endpoints (Internal)

```http
# Get OAuth config for organization
GET /internal/api/v1/oauth/config/{org_id}/{provider}

# Update OAuth config (called by Settings UI)
PUT /api/settings/oauth/{provider}
Authorization: Bearer <org_token>
{
    "client_id": "customer-client-id",
    "client_secret": "customer-secret",
    "custom_scopes": ["scope1", "scope2"]
}

# Check if using platform or custom credentials
GET /api/settings/oauth/{provider}/status
Response:
{
    "provider": "google",
    "using_custom_credentials": true,
    "client_id_masked": "1234...5678",
    "scopes": ["email", "calendar"]
}
```

## Files

| Component | Location |
|-----------|----------|
| OAuth Manager | `backend/integrations/oauth/manager.py` |
| Provider Configs | `backend/integrations/oauth/configs/*.yaml` |
| Credential Store | `backend/integrations/oauth/credential_store.py` |
| Settings API | `backend/api/settings.py` |
| Dashboard UI | `dashboard/src/pages/Settings.tsx` |
