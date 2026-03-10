# OAuth2 Integration Architecture

> **Last verified against code: 2026-02-20**

## Overview

Custom OAuth2 implementation for connecting third-party services (Google, Slack, GitHub, Microsoft, Salesforce). Supports both platform-wide default credentials and per-organization custom credentials (hybrid model).

## Current Implementation: Custom OAuth Handler

### Why Custom?

- Full control over the OAuth flow
- No external dependencies
- Deep understanding of the mechanism
- Suitable for the current 5 OAuth providers

### Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                      OAuth2 Flow                                │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│  1. User clicks "Connect Google"                                │
│     │                                                           │
│     ▼                                                           │
│  2. Frontend calls: GET /api/oauth/google/authorize             │
│     │                                                           │
│     ▼                                                           │
│  3. Backend generates state token (secrets.token_urlsafe(32))   │
│     Stores state in memory (10-minute TTL)                      │
│     Returns: redirect URL to Google                             │
│     │                                                           │
│     ▼                                                           │
│  4. User authenticates with Google, grants permissions          │
│     │                                                           │
│     ▼                                                           │
│  5. Google redirects to: /api/oauth/google/callback?code=...    │
│     │                                                           │
│     ▼                                                           │
│  6. Backend validates state token (CSRF protection)             │
│     Exchanges code for tokens via POST to provider token URL    │
│     │                                                           │
│     ▼                                                           │
│  7. Fetches user info from provider's userinfo endpoint         │
│     │                                                           │
│     ▼                                                           │
│  8. Store tokens encrypted (Fernet) in memory + file            │
│     - access_token (short-lived, ~1 hour)                       │
│     - refresh_token (long-lived)                                │
│     - expires_at timestamp                                      │
│     - user_info (email, name from provider)                     │
│     │                                                           │
│     ▼                                                           │
│  9. Redirect user to success page                               │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
```

### Token Refresh Flow

```
┌─────────────────────────────────────────────────────────────────┐
│                    Token Refresh                                │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│  Before each API call (auto_refresh=True):                      │
│                                                                 │
│  1. Check if access_token expires within 5 minutes              │
│     (token_expiry_buffer_seconds = 300)                         │
│     │                                                           │
│     ├── No  → Use existing token                                │
│     │                                                           │
│     └── Yes → Has refresh_token?                                │
│               │                                                 │
│               ├── Yes → POST to provider token URL              │
│               │         with grant_type=refresh_token            │
│               │         Store new access_token + expires_at      │
│               │         Use new token                            │
│               │                                                 │
│               └── No  → Return existing token (may fail)        │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
```

### API Endpoints

```
GET  /api/oauth/providers                    — List available providers + connection status
GET  /api/oauth/{provider}/authorize         — Start OAuth flow (returns redirect URL)
GET  /api/oauth/{provider}/callback          — Handle OAuth callback (redirect-based)
GET  /api/oauth/{provider}/callback/json     — Handle OAuth callback (JSON response)
GET  /api/oauth/{provider}/status            — Get connection status for a provider
POST /api/oauth/{provider}/revoke            — Revoke/disconnect a provider
POST /api/oauth/{provider}/refresh           — Manually refresh token
GET  /api/oauth/{provider}/token             — Get current access token
```

Organization settings endpoints (hybrid config):
```
GET    /api/settings/oauth                        — List org OAuth configs
GET    /api/settings/oauth/{provider}             — Get provider config
POST   /api/settings/oauth/{provider}             — Save custom org config
DELETE /api/settings/oauth/{provider}             — Delete custom org config
GET    /api/settings/oauth/{provider}/redirect-uri — Get redirect URI for setup
```

### File Structure

```
backend/
├── api/
│   ├── oauth.py              # OAuth routes (303 lines)
│   └── oauth_settings.py     # Hybrid org config API (272 lines)
├── integrations/
│   └── oauth/
│       ├── __init__.py        # Module exports
│       ├── handler.py         # OAuthHandler — core flow logic (473 lines)
│       ├── providers.py       # OAuthProviderConfig & Registry (141 lines)
│       ├── tokens.py          # OAuthToken & OAuthTokenStorage (205 lines)
│       ├── org_config.py      # OrganizationOAuthConfig storage (175 lines)
│       └── configs/
│           ├── google.yaml    # Google Workspace
│           ├── slack.yaml     # Slack (bot + user tokens)
│           ├── github.yaml    # GitHub (repos, issues, PRs, orgs)
│           ├── microsoft.yaml # Microsoft 365 (Teams, OneDrive, Outlook)
│           └── salesforce.yaml # Salesforce (Sales Cloud, custom objects)
```

### Storage (Current: In-Memory + File)

**Tokens:** In-memory dict encrypted with Fernet, persisted to file.
- Default path: `/tmp/oauth_tokens.json` (configurable via `OAUTH_TOKEN_STORAGE_PATH`)
- Key format: `{org_id}:{provider}` → encrypted JSON blob

**State tokens:** In-memory dict with 10-minute TTL, no file persistence.
- Key: random state string → `OAuthState` object
- Cleaned up after validation

**Organization configs:** In-memory dict encrypted with Fernet, persisted to file.
- Default path: `/tmp/org_oauth_configs.json` (configurable via `ORG_OAUTH_CONFIG_STORAGE_PATH`)

**Known limitation:** Data is lost on restart if `/tmp` is cleared. For production, migrate to PostgreSQL. The original planned schema:

```sql
-- Future: OAuth tokens table
CREATE TABLE oauth_tokens (
    id UUID PRIMARY KEY,
    organization_id VARCHAR(255) NOT NULL,
    provider VARCHAR(50) NOT NULL,
    access_token_encrypted TEXT NOT NULL,
    refresh_token_encrypted TEXT,
    token_type VARCHAR(50) DEFAULT 'Bearer',
    expires_at TIMESTAMP,
    scopes TEXT[],
    user_info JSONB,
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW(),
    UNIQUE(organization_id, provider)
);

-- Future: OAuth state tokens (for CSRF protection)
CREATE TABLE oauth_states (
    state VARCHAR(255) PRIMARY KEY,
    organization_id VARCHAR(255) NOT NULL,
    provider VARCHAR(50) NOT NULL,
    redirect_uri TEXT,
    created_at TIMESTAMP DEFAULT NOW(),
    expires_at TIMESTAMP NOT NULL
);
```

### Hybrid Credential Resolution

Organizations can use platform-wide defaults OR provide their own OAuth credentials:

```
1. Check OrganizationOAuthConfig for this org + provider
   │
   ├── Exists & enabled → Use org's custom client_id/secret
   │
   └── Not found → Fall back to platform defaults
                    (YAML config + environment variables)
```

This is implemented in `handler.py` → `_get_effective_credentials()`.

### Provider Configuration (YAML)

```yaml
# configs/google.yaml
id: google
name: google
display_name: Google Workspace

oauth:
  authorization_url: https://accounts.google.com/o/oauth2/v2/auth
  token_url: https://oauth2.googleapis.com/token
  revoke_url: https://oauth2.googleapis.com/revoke
  userinfo_url: https://www.googleapis.com/oauth2/v2/userinfo

  default_scopes:
    - openid
    - email
    - profile
    - https://www.googleapis.com/auth/drive.readonly
    - https://www.googleapis.com/auth/spreadsheets
    - https://www.googleapis.com/auth/calendar.readonly

  # Credentials loaded from env vars at runtime
  client_id_env: GOOGLE_CLIENT_ID
  client_secret_env: GOOGLE_CLIENT_SECRET
```

### Environment Variables

```bash
# Provider credentials (per provider)
GOOGLE_CLIENT_ID=your-client-id.apps.googleusercontent.com
GOOGLE_CLIENT_SECRET=your-client-secret
SLACK_CLIENT_ID=your-slack-client-id
SLACK_CLIENT_SECRET=your-slack-client-secret
GITHUB_CLIENT_ID=your-github-client-id
GITHUB_CLIENT_SECRET=your-github-client-secret
MICROSOFT_CLIENT_ID=your-microsoft-client-id
MICROSOFT_CLIENT_SECRET=your-microsoft-client-secret
SALESFORCE_CLIENT_ID=your-salesforce-client-id
SALESFORCE_CLIENT_SECRET=your-salesforce-client-secret

# Encryption key for token storage (Fernet)
# Auto-generated in dev mode if not set (with warning)
OAUTH_ENCRYPTION_KEY=32-byte-base64-encoded-key

# Optional: custom storage paths
OAUTH_TOKEN_STORAGE_PATH=/path/to/oauth_tokens.json
ORG_OAUTH_CONFIG_STORAGE_PATH=/path/to/org_oauth_configs.json
```

### Token Encryption

Uses **Fernet** symmetric encryption from the `cryptography` library:
- Algorithm: AES-128-CBC + HMAC-SHA256 (Fernet standard)
- Key: URL-safe base64-encoded 32-byte key
- Both access tokens and refresh tokens are encrypted at rest
- Organization custom credentials are also encrypted

---

## Future Option: Nango Integration

### What is Nango?

[Nango](https://www.nango.dev/) is an open-source unified API for OAuth and integrations:
- 250+ pre-built OAuth providers
- Automatic token refresh
- Self-hosted or cloud
- MIT licensed

### When to Consider Nango

Switch to Nango when:
- Maintaining OAuth flows becomes a burden
- Token refresh issues occur frequently
- You want faster time-to-market for new integrations
- Community requests many new providers

### Nango Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                    With Nango                                   │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│  ┌──────────────┐      ┌──────────────┐      ┌──────────────┐  │
│  │   Frontend   │─────▶│    Nango     │─────▶│   Provider   │  │
│  │              │      │   Server     │      │ Google/Slack │  │
│  └──────────────┘      └──────────────┘      └──────────────┘  │
│                              │                                  │
│                              │ Stores tokens                    │
│                              │ Auto-refreshes                   │
│                              ▼                                  │
│                        ┌──────────────┐                         │
│                        │  Your API    │                         │
│                        │  GET /token  │◀── Always fresh         │
│                        └──────────────┘                         │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
```

### Comparison Table

| Feature | Custom OAuth (Current) | Nango |
|---------|------------------------|-------|
| Providers implemented | 5 | 250+ ready |
| Per provider setup | 30-60 min | 5 min |
| Token refresh | Implemented (auto) | Automatic |
| Maintenance | Us | Nango team |
| Self-hosted | Yes | Yes |
| Open source | Our code | MIT license |
| Vendor lock-in | None | Low (open-source) |

### Decision Log

| Date | Decision | Reason |
|------|----------|--------|
| 2026-01-11 | Start with custom OAuth | Learn the flow, no dependencies |
| 2026-02-20 | Still custom, 5 providers | Working well, not yet a maintenance burden |

---

## Implementation Status

### Completed
- [x] OAuth routes (`/api/oauth/{provider}/authorize`, `/callback`, `/callback/json`)
- [x] Token exchange logic
- [x] Fernet-encrypted token storage (in-memory + file)
- [x] Token refresh mechanism (auto + manual)
- [x] State-based CSRF protection (10-minute TTL)
- [x] User info fetching from provider
- [x] Google OAuth provider
- [x] Slack OAuth provider
- [x] GitHub OAuth provider
- [x] Microsoft OAuth provider
- [x] Salesforce OAuth provider
- [x] Hybrid credential resolution (platform defaults + org overrides)
- [x] Organization OAuth settings API
- [x] Frontend integration (ConnectIntegration.tsx)
- [x] Token revocation endpoint

### Known Limitations
- [ ] Token storage is in-memory + file (not PostgreSQL) — data lost if /tmp cleared
- [ ] State storage is in-memory only — not suitable for multi-instance deployment
- [ ] No rate limiting on OAuth endpoints
- [ ] No audit logging of OAuth operations

---

## Security Considerations

1. **State Parameter**: 256-bit random state token (`secrets.token_urlsafe(32)`) for CSRF protection
2. **Token Encryption**: Fernet (AES-128-CBC + HMAC-SHA256) at rest
3. **Scope Minimization**: Request only needed scopes per provider
4. **Token Rotation**: Auto-refresh 5 minutes before expiry
5. **Revocation**: Endpoint to revoke/disconnect providers
6. **Credential Isolation**: Per-organization credential storage
7. **Secret Masking**: Tokens masked in API responses

---

## References

- [OAuth 2.0 RFC](https://datatracker.ietf.org/doc/html/rfc6749)
- [Google OAuth 2.0](https://developers.google.com/identity/protocols/oauth2)
- [Slack OAuth](https://api.slack.com/authentication/oauth-v2)
- [GitHub OAuth](https://docs.github.com/en/apps/oauth-apps/building-oauth-apps/authorizing-oauth-apps)
- [Microsoft OAuth](https://learn.microsoft.com/en-us/entra/identity-platform/v2-oauth2-auth-code-flow)
- [Nango Documentation](https://docs.nango.dev/)
