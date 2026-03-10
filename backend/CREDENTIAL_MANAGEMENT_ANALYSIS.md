# Credential & API Key Management Analysis
## Agent Orchestration Platform - Orchestly

### Executive Summary

The Agent Orchestration Platform has **HYBRID credential management**:
- **Integration Credentials**: Encrypted storage at rest (Fernet encryption)
- **LLM Provider Keys**: Environment variables only
- **Customer BYOK Keys**: Encrypted Fernet storage + usage tracking
- **Platform API Keys**: SHA-256 hashed (never stored in plaintext)

**Key Finding**: There is **NO per-tenant credential isolation** - all credentials are stored in one database with organization_id only as segregation.

---

## Current State: Three Credential Storage Mechanisms

### 1. INTEGRATION CREDENTIALS (User-Provided API Keys & OAuth Tokens)

**Storage Model**: Database (PostgreSQL/SQLite) with Fernet Encryption

**Location**: 
- Models: `/backend/shared/integration_models.py` (line 177) - `IntegrationInstallationModel`
- Manager: `/backend/shared/credential_manager.py`
- Executor: `/backend/shared/integration_executor.py`

**Schema** (IntegrationInstallationModel):
```python
class IntegrationInstallationModel(Base):
    installation_id = Column(UUID, primary_key=True)
    integration_id = Column(UUID, ForeignKey)
    organization_id = Column(String(255))  # MULTI-TENANT KEY
    
    # ---- CREDENTIAL STORAGE ----
    auth_credentials = Column(JSONB, nullable=True)  # Encrypted or dict
    configuration = Column(JSONB, nullable=True)
    
    # Status tracking
    is_healthy = Column(Boolean, default=True)
    last_health_check_at = Column(DateTime)
```

**Encryption Details** (credential_manager.py):
- **Algorithm**: Fernet (symmetric encryption from cryptography library)
- **Key Derivation**: PBKDF2-HMAC-SHA256
- **Key Sources** (in priority order):
  1. `CREDENTIAL_ENCRYPTION_KEY` env var (base64-encoded)
  2. `CREDENTIAL_SECRET` env var (derived via PBKDF2)
  3. Fallback: `"default-dev-secret-change-in-production"` (DEV ONLY - INSECURE)
- **Salt**: Static `b"agentorch_credential_salt"` (NOT per-credential - SECURITY ISSUE)
- **Iterations**: 100,000

```python
# From credential_manager.py
def encrypt(self, credentials: Dict[str, Any]) -> str:
    json_str = json.dumps(credentials)
    encrypted = self._fernet.encrypt(json_str.encode())
    return encrypted.decode()

def decrypt(self, encrypted_credentials: str) -> Dict[str, Any]:
    decrypted = self._fernet.decrypt(encrypted_credentials.encode())
    return json.loads(decrypted.decode())
```

**Fallback for Unencrypted Creds**: Base64 encoding (degraded mode if cryptography library missing)

**Supported Auth Types** (integrations/schema.py):
- `API_KEY` - Direct API keys (Stripe, SendGrid, etc.)
- `BOT_TOKEN` - Bot tokens (Slack, Discord, etc.)
- `OAUTH2` - OAuth 2.0 tokens (stored via Nango or custom)
- `BASIC_AUTH` - Username/password
- `BEARER_TOKEN` - Bearer tokens

**Who Retrieves Them**:
- `IntegrationExecutor._get_credentials()` (line 483)
- Decrypts on every integration action execution
- No caching (re-decrypt on each use)

**Multi-Tenant Isolation**: 
- ✅ Segregated by `organization_id` in database
- ⚠️ NO encryption key per tenant (shared encryption key)
- ⚠️ If encryption key is compromised, ALL credentials exposed

---

### 2. LLM PROVIDER API KEYS (OpenAI, Anthropic, Google, DeepSeek, Groq)

**Storage Model**: Environment Variables ONLY

**Location**: `/backend/shared/llm_clients.py`

**Current Implementation**:
```python
class OpenAIClient(BaseLLMClient):
    def _get_default_api_key(self) -> Optional[str]:
        key = os.getenv("OPENAI_API_KEY")
        return key if key else None

class AnthropicClient(BaseLLMClient):
    def _get_default_api_key(self) -> Optional[str]:
        key = os.getenv("ANTHROPIC_API_KEY")
        return key if key else None
```

**Supported Providers** (all use env vars):
- `OPENAI_API_KEY` → OpenAI (GPT-4, GPT-4o, etc.)
- `ANTHROPIC_API_KEY` → Anthropic (Claude)
- `GOOGLE_API_KEY` → Google (Gemini)
- `DEEPSEEK_API_KEY` → DeepSeek
- `GROQ_API_KEY` → Groq
- `AZURE_OPENAI_API_KEY` + `AZURE_OPENAI_ENDPOINT` → Azure OpenAI

**No Per-Tenant Support**: 
- ❌ Single global API key per provider
- ❌ Cannot isolate costs per customer
- ❌ One compromised key = all customers affected

**Configuration**: `/backend/shared/config.py` (Settings class)
```python
class Settings(BaseSettings):
    OPENAI_API_KEY: Optional[str] = None
    ANTHROPIC_API_KEY: Optional[str] = None
    GOOGLE_API_KEY: Optional[str] = None
    # ... etc
```

---

### 3. CUSTOMER-MANAGED KEYS (BYOK - Bring Your Own Key)

**Storage Model**: Database with Fernet Encryption + Usage Tracking

**Location**: `/backend/shared/byok_gateway.py`

**Features**:
- ✅ Customer provides their own API keys
- ✅ Keys encrypted with Fernet before storage
- ✅ Hourly usage tracking in `UsageBucket`
- ✅ Rate limit prediction & pre-throttling
- ✅ Cost transparency reports
- ✅ Key validation & health monitoring

**Data Classes**:
```python
@dataclass
class CustomerAPIKey:
    key_id: UUID
    org_id: UUID
    provider: KeyProvider  # openai, anthropic, deepseek, google
    encrypted_key: str     # Fernet-encrypted
    key_prefix: str        # "sk-proj-abc..." for display
    tier: CustomerTier     # Rate limits & pricing
    status: KeyStatus      # active, expired, rate_limited, invalid
    last_used_at: datetime
    
@dataclass
class UsageBucket:
    period_start: datetime
    period_end: datetime
    requests_count: int
    tokens_input: int
    tokens_output: int
    estimated_cost: float
    rate_limit_hits: int
```

**Encryption**: Uses same Fernet approach as integrations
```python
encrypted = self.vault.encrypt_key(api_key)
prefix = self.vault.get_key_prefix(api_key)
```

**Design Note**: Comments mention production would use "AWS KMS, HashiCorp Vault, or similar"

---

### 4. PLATFORM API KEYS (For Programmatic Access)

**Storage Model**: Database with SHA-256 Hashing

**Location**: `/backend/database/models.py` (line 566) - `APIKeyModel`

**Schema**:
```python
class APIKeyModel(Base):
    __tablename__ = "api_keys"
    
    id = Column(Integer, primary_key=True)
    organization_id = Column(String(255), ForeignKey)
    
    # KEY INFO - NEVER STORED IN PLAINTEXT
    name = Column(String(255))
    key_prefix = Column(String(20))           # "ao_live_abc1..."
    key_hash = Column(String(64), unique=True)  # SHA-256
    
    # PERMISSIONS & QUOTAS
    permissions = Column(JSON, default=list)
    rate_limit_per_second = Column(Integer, default=100)
    monthly_quota = Column(Integer)
    ip_whitelist = Column(JSON, default=list)
    
    # STATUS & AUDIT
    is_active = Column(Boolean, default=True)
    created_by = Column(String(100))
    expires_at = Column(DateTime)
    last_used_at = Column(DateTime)
    revoked_at = Column(DateTime)
    revoked_by = Column(String(100))
    
    # KEY ROTATION (Graceful)
    previous_key_hash = Column(String(64))         # Old key during grace period
    previous_key_expires_at = Column(DateTime)     # When old key stops working
```

**Key Format**: 
- **Live**: `ao_live_<32 random chars>`
- **Test**: `ao_test_<32 random chars>`

**Hashing**:
```python
key_hash = hashlib.sha256(api_key.encode()).hexdigest()
```

**Features** (API_KEYS_README.md):
- ✅ Key rotation with grace period
- ✅ Rate limiting per key
- ✅ Monthly quotas
- ✅ IP whitelisting
- ✅ Audit trail (created_by, revoked_by)
- ✅ Automatic cleanup of expired keys

**Security**: Full key only shown once at creation time

---

## OAuth Token Management

**Provider**: Nango (Hybrid Abstraction)

**Location**: `/backend/shared/connection_provider.py` + `/backend/integrations/oauth/`

**Nango-Supported Integrations**:
- discord, slack, google, github, notion
- salesforce, hubspot, jira, asana, trello
- dropbox, box, microsoft, zoom, calendly
- stripe, quickbooks, xero, shopify, zendesk

**Configuration** (environment):
- `NANGO_SECRET_KEY` - Backend authentication
- `NANGO_PUBLIC_KEY` - Frontend SDK

**Flow**:
1. Frontend calls Nango SDK with public key
2. User authenticates on Nango's hosted auth page
3. Nango handles token storage & encryption
4. Backend retrieves tokens via API

```python
class NangoProvider(ConnectionProvider):
    def __init__(self, secret_key: Optional[str] = None):
        self.secret_key = secret_key or os.environ.get("NANGO_SECRET_KEY")
        self.public_key = public_key or os.environ.get("NANGO_PUBLIC_KEY")
    
    async def get_credentials(self, integration_id: str, user_id: str) -> Optional[Credentials]:
        # Call Nango API to fetch tokens
        async with session.get(
            f"{self.base_url}/connection/{user_id}",
            headers={"Authorization": f"Bearer {self.secret_key}"},
            params={"provider_config_key": integration_id}
        ) as response:
            data = await response.json()
            return Credentials(
                auth_type=AuthType.OAUTH2,
                access_token=data["credentials"]["access_token"],
                refresh_token=data["credentials"]["refresh_token"],
                expires_at=...
            )
```

---

## SECURITY ANALYSIS

### ✅ Strengths

1. **Fernet Encryption for Integration Credentials**
   - Symmetric encryption (secure)
   - PBKDF2 key derivation
   - 100,000 iterations (good KDF strength)
   - Automatic versioning in tokens

2. **API Key Hashing**
   - SHA-256 (one-way)
   - Never stores plaintext keys
   - Supports key rotation

3. **Multi-Tenant Awareness**
   - `organization_id` on all credential models
   - Enforced at query level

4. **OAuth Abstraction**
   - Delegated to Nango (industry standard)
   - Automatic token refresh
   - Centralized token storage

---

### ⚠️ CRITICAL ISSUES

#### 1. **Static Salt in Encryption** 
**Severity**: HIGH

```python
# credential_manager.py line 70
salt = b"agentorch_credential_salt"  # Same for ALL credentials!
```

**Impact**: 
- Rainbow table attacks possible
- No per-credential uniqueness
- If one credential is cracked, pattern known for all

**Fix**: Use per-credential random salt (stored with encrypted value)

#### 2. **Shared Encryption Key Across All Tenants**
**Severity**: HIGH

- Single `CREDENTIAL_ENCRYPTION_KEY` for all organizations
- If key compromised → all customer credentials exposed
- No key rotation mechanism

**Fix**: 
- Key per organization or customer
- Implement key rotation
- Use AWS KMS / HashiCorp Vault

#### 3. **Fallback Insecure Default**
**Severity**: MEDIUM-HIGH

```python
# credential_manager.py line 58
secret = os.environ.get("CREDENTIAL_SECRET", 
    "default-dev-secret-change-in-production")
```

**Impact**: If `CREDENTIAL_SECRET` env var not set, uses hardcoded default
- Easily guessable
- All instances use same key

#### 4. **No Per-Tenant LLM API Keys**
**Severity**: MEDIUM

- All customers share same OpenAI/Anthropic keys
- Cost cannot be isolated per customer
- One customer can exhaust quota for all others
- One compromised key affects all customers

**Fix**: Store customer keys encrypted per integration_installation

#### 5. **No Encryption Key Rotation**
**Severity**: MEDIUM

- No mechanism to re-encrypt with new key
- Key compromise is permanent (must delete all creds)

#### 6. **Credentials Not Rotated on Access**
**Severity**: LOW-MEDIUM

- Credentials decrypted on memory without zeroization
- Python string objects remain in memory

#### 7. **Unencrypted Database Storage (Legacy Path)**
**Severity**: MEDIUM

```python
# integration_executor.py line 509
installation.auth_credentials = credentials  # Stored as dict, not encrypted!
```

Sometimes credentials stored as unencrypted dict instead of encrypted string

---

## Database Model Summary

| Model | Credential Storage | Encryption | Multi-Tenant | Notes |
|-------|-------------------|------------|--------------|-------|
| IntegrationInstallationModel | auth_credentials (JSONB) | Fernet | By org_id | 177 integrations supported |
| CloudAccount | credentials_encrypted (Text) | Fernet | By account_id | AWS/Azure/GCP deployment |
| APIKeyModel | key_hash (String) | SHA-256 | By org_id | Platform access, not stored plaintext |
| CustomerAPIKey (BYOK) | encrypted_key | Fernet | Per org/provider | Usage tracking included |
| LLM Providers | Environment vars | NONE | GLOBAL | Single key for all tenants |

---

## Configuration Files

**Environment Variables** (`/backend/shared/config.py`):

```python
# LLM Keys (GLOBAL - NOT TENANT-SPECIFIC)
OPENAI_API_KEY
ANTHROPIC_API_KEY
GOOGLE_API_KEY
DEEPSEEK_API_KEY
GROQ_API_KEY
AZURE_OPENAI_API_KEY
AZURE_OPENAI_ENDPOINT

# Database
POSTGRES_USER, POSTGRES_PASSWORD, POSTGRES_HOST, etc.
USE_SQLITE  # For dev

# Encryption
CREDENTIAL_ENCRYPTION_KEY  # Base64-encoded Fernet key
CREDENTIAL_SECRET  # Alternative (derived via PBKDF2)

# OAuth
NANGO_SECRET_KEY
NANGO_PUBLIC_KEY

# Redis
REDIS_HOST, REDIS_PASSWORD, etc.

# JWT
JWT_SECRET_KEY
JWT_ALGORITHM
JWT_ACCESS_TOKEN_EXPIRE_MINUTES

# API Gateway
API_KEY_HEADER (default: "X-API-Key")
API_KEY_LENGTH (default: 32)

# Rate Limiting
RATE_LIMIT_ENABLED
RATE_LIMIT_REQUESTS_PER_MINUTE
RATE_LIMIT_REQUESTS_PER_HOUR
```

---

## Migration Path (Planned)

**Comment in byok_gateway.py**:
```python
"""
In production, this would use AWS KMS, HashiCorp Vault, or similar.
"""
```

**Indicates planned migration**:
1. Current: Fernet symmetric keys
2. Future: AWS KMS, HashiCorp Vault, or similar

---

## Integration Credential Flow

### Example: Slack Integration

1. **User connects Slack**:
   - POST `/api/connections/slack/connect`
   - Payload: `{ credentials: { bot_token: "xoxb-..." } }`

2. **Credential Manager Encrypts**:
   ```python
   encrypted = encrypt_credentials({
       "bot_token": "xoxb-123456789",
       "team_id": "T123456"
   })
   ```

3. **Stored in Database**:
   ```sql
   INSERT INTO integration_installations (
       organization_id, integration_id, auth_credentials, ...
   ) VALUES (
       'org_abc', 'slack_uuid',
       'gAAAAABme2-NfXYZ...'  -- Encrypted blob
   )
   ```

4. **On Action Execution**:
   ```python
   installation = db.query(IntegrationInstallationModel)...
   credentials = decrypt_credentials(installation.auth_credentials)
   slack = SlackIntegration(credentials=credentials)
   await slack.execute_action("send_message", params)
   ```

5. **Within SlackIntegration**:
   - Uses `credentials["bot_token"]` to call Slack API
   - Never logged or exposed

---

## Per-Tenant Credential Isolation: MISSING

**Current State**:
- ✅ Organization segregation in database schema
- ✅ Encryption at rest
- ❌ **SHARED ENCRYPTION KEY** across all orgs
- ❌ **SHARED LLM API KEYS** for all customers
- ❌ **NO KEY DERIVATION PER TENANT**

**If Encryption Key Compromised**:
- All integration credentials for ALL organizations decrypted
- All customer BYOK keys exposed

**Recommendation**: 
- Implement per-tenant or per-organization key derivation
- Or use external key management (KMS)

---

## Recommendations for Healthcare Agent

### Immediate (Week 1)

1. **Document current encryption scheme**
   - Update architecture diagrams
   - Document limitations

2. **Implement per-tenant salt**
   ```python
   salt = hashlib.sha256(f"{org_id}:{credential_id}".encode()).digest()[:16]
   ```

3. **Environment variable validation**
   - Fail startup if `CREDENTIAL_ENCRYPTION_KEY` not set
   - Remove fallback to hardcoded default

### Short-term (Week 2-3)

4. **Implement tenant-specific LLM keys**
   - Create `CustomerLLMKey` model
   - Store encrypted per customer
   - Support quota isolation

5. **Key rotation mechanism**
   - Version encryption keys
   - Support re-encryption
   - Gradual migration process

### Medium-term (Week 4+)

6. **Integrate with AWS KMS or HashiCorp Vault**
   - Replace Fernet with KMS
   - Centralized key management
   - Audit logging of key access

7. **Implement key versioning**
   - Support multiple active keys
   - Gradual key rotation
   - Audit trail

8. **Add credential lifecycle management**
   - Automatic rotation
   - Expiration policies
   - Breach response procedures

---

## Files to Review for Healthcare Compliance

1. `/backend/shared/credential_manager.py` - Main credential handling
2. `/backend/database/models.py` - IntegrationInstallationModel schema
3. `/backend/shared/integration_executor.py` - How credentials are used
4. `/backend/shared/byok_gateway.py` - Customer key management
5. `/backend/shared/llm_clients.py` - LLM key configuration
6. `/backend/shared/config.py` - Environment variable schema
7. `/backend/integrations/oauth/tokens.py` - OAuth token storage

---

## Audit Trail

**Available**:
- API Key creation, rotation, revocation
- Team member invitations
- User role changes

**NOT Available**:
- Credential access logs (who accessed which credential)
- Encryption/decryption event logs
- Key usage audit trail

**Recommendation**: Add audit table for credential access

---

