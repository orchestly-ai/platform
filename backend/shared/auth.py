"""
Authentication and Authorization Module

Provides API key authentication for agents and JWT authentication for dashboard users.
Includes multi-tenancy support with organization validation.
"""

import secrets
import threading
import time
from dataclasses import dataclass
from datetime import datetime, timedelta
from functools import wraps
from typing import Optional, Callable, Any
from uuid import UUID, uuid4

import jwt
import bcrypt
from fastapi import HTTPException, Security, status, Depends, Query
from fastapi.security import APIKeyHeader, HTTPBearer, HTTPAuthorizationCredentials

from backend.shared.config import get_settings


# ============================================================================
# User Context (Multi-Tenancy)
# ============================================================================

@dataclass
class AuthenticatedUser:
    """
    Authenticated user context with organization binding.

    Used for multi-tenancy enforcement across all API endpoints.
    """
    user_id: str
    email: str
    organization_id: str
    roles: list[str]
    auth_type: str  # "jwt" or "api_key"
    agent_id: Optional[UUID] = None  # Set if authenticated via API key


# ============================================================================
# Configuration
# ============================================================================

settings = get_settings()

# Security schemes
api_key_header = APIKeyHeader(name="X-API-Key", auto_error=False)
bearer_scheme = HTTPBearer(auto_error=False)


# ============================================================================
# API Key Management
# ============================================================================

@dataclass
class APIKeyInfo:
    """Information associated with an API key."""
    agent_id: UUID
    organization_id: str
    created_at: datetime
    last_used: datetime


class APIKeyManager:
    """
    Manages API keys for agent authentication.

    In production, store keys in database with proper encryption.
    Keys are bound to organizations for multi-tenancy isolation.
    """

    def __init__(self):
        """Initialize API key manager."""
        # In-memory storage for MVP (use Redis/DB in production)
        self._api_keys: dict[str, APIKeyInfo] = {}  # key -> APIKeyInfo
        self._agent_keys: dict[UUID, str] = {}  # agent_id -> key

    def generate_api_key(self, agent_id: UUID, organization_id: str) -> str:
        """
        Generate new API key for agent.

        Args:
            agent_id: Agent ID
            organization_id: Organization ID (for multi-tenancy)

        Returns:
            API key string
        """
        # Generate cryptographically secure random key
        api_key = f"sk-{secrets.token_urlsafe(32)}"

        # Store mapping with organization binding
        self._api_keys[api_key] = APIKeyInfo(
            agent_id=agent_id,
            organization_id=organization_id,
            created_at=datetime.utcnow(),
            last_used=datetime.utcnow(),
        )
        self._agent_keys[agent_id] = api_key

        return api_key

    def validate_api_key(self, api_key: str) -> Optional[APIKeyInfo]:
        """
        Validate API key and return associated info including organization.

        Args:
            api_key: API key to validate

        Returns:
            APIKeyInfo if valid, None otherwise
        """
        if api_key not in self._api_keys:
            return None

        # Update last used timestamp
        key_info = self._api_keys[api_key]
        self._api_keys[api_key] = APIKeyInfo(
            agent_id=key_info.agent_id,
            organization_id=key_info.organization_id,
            created_at=key_info.created_at,
            last_used=datetime.utcnow(),
        )

        return self._api_keys[api_key]

    def get_agent_id(self, api_key: str) -> Optional[UUID]:
        """
        Get agent ID for API key (backwards compatibility).

        Args:
            api_key: API key to validate

        Returns:
            Agent ID if valid, None otherwise
        """
        key_info = self.validate_api_key(api_key)
        return key_info.agent_id if key_info else None

    def revoke_api_key(self, agent_id: UUID) -> None:
        """
        Revoke API key for agent.

        Args:
            agent_id: Agent ID
        """
        if agent_id in self._agent_keys:
            api_key = self._agent_keys[agent_id]
            del self._api_keys[api_key]
            del self._agent_keys[agent_id]

    def get_api_key_for_agent(self, agent_id: UUID) -> Optional[str]:
        """
        Get API key for agent.

        Args:
            agent_id: Agent ID

        Returns:
            API key if exists
        """
        return self._agent_keys.get(agent_id)


# Global API key manager instance
_api_key_manager: Optional[APIKeyManager] = None


def get_api_key_manager() -> APIKeyManager:
    """Get or create global API key manager instance."""
    global _api_key_manager
    if _api_key_manager is None:
        _api_key_manager = APIKeyManager()
    return _api_key_manager


# ============================================================================
# JWT Token Management
# ============================================================================

class JWTManager:
    """
    Manages JWT tokens for dashboard authentication.
    """

    def __init__(self):
        """Initialize JWT manager."""
        self.secret_key = settings.JWT_SECRET_KEY
        self.algorithm = settings.JWT_ALGORITHM
        self.access_token_expire_minutes = settings.JWT_ACCESS_TOKEN_EXPIRE_MINUTES

    def create_access_token(
        self,
        data: dict,
        expires_delta: Optional[timedelta] = None
    ) -> str:
        """
        Create JWT access token.

        Args:
            data: Data to encode in token
            expires_delta: Token expiration time

        Returns:
            JWT token string
        """
        to_encode = data.copy()

        if expires_delta:
            expire = datetime.utcnow() + expires_delta
        else:
            expire = datetime.utcnow() + timedelta(minutes=self.access_token_expire_minutes)

        to_encode.update({"exp": expire, "jti": str(uuid4())})

        encoded_jwt = jwt.encode(to_encode, self.secret_key, algorithm=self.algorithm)
        return encoded_jwt

    def verify_token(self, token: str) -> Optional[dict]:
        """
        Verify and decode JWT token.

        Args:
            token: JWT token string

        Returns:
            Decoded token data if valid, None otherwise
        """
        try:
            payload = jwt.decode(token, self.secret_key, algorithms=[self.algorithm])
            # Check blacklist
            jti = payload.get("jti")
            if jti and _token_blacklist.is_blacklisted(jti):
                return None
            return payload
        except jwt.ExpiredSignatureError:
            return None
        except jwt.InvalidSignatureError:
            return None
        except jwt.DecodeError:
            return None
        except jwt.InvalidTokenError:
            return None
        except Exception:
            # Catch any other JWT-related exceptions
            return None

    def create_dashboard_token(
        self,
        user_id: str,
        email: str,
        role: str = "admin"
    ) -> str:
        """
        Create JWT token for dashboard user.

        Args:
            user_id: User ID
            email: User email
            role: User role (admin, viewer, etc)

        Returns:
            JWT token
        """
        data = {
            "sub": user_id,
            "email": email,
            "role": role,
            "type": "dashboard",
        }
        return self.create_access_token(data)


# Global JWT manager instance
_jwt_manager: Optional[JWTManager] = None


def get_jwt_manager() -> JWTManager:
    """Get or create global JWT manager instance."""
    global _jwt_manager
    if _jwt_manager is None:
        _jwt_manager = JWTManager()
    return _jwt_manager


# ============================================================================
# Token Blacklist (for logout / revocation)
# ============================================================================

class TokenBlacklist:
    """
    In-memory JWT token blacklist.

    Tracks revoked token JTIs so they cannot be reused after logout.
    Expired entries are periodically cleaned up.
    """

    def __init__(self):
        # jti -> expiry timestamp
        self._blacklisted: dict[str, float] = {}
        self._lock = threading.Lock()

    def add(self, jti: str, exp: float) -> None:
        """Blacklist a token JTI until its expiry time."""
        with self._lock:
            self._blacklisted[jti] = exp
            self._cleanup()

    def is_blacklisted(self, jti: str) -> bool:
        """Check if a token JTI has been revoked."""
        with self._lock:
            return jti in self._blacklisted

    def _cleanup(self) -> None:
        """Remove expired entries to prevent unbounded growth."""
        now = time.time()
        expired = [jti for jti, exp in self._blacklisted.items() if exp < now]
        for jti in expired:
            del self._blacklisted[jti]


_token_blacklist = TokenBlacklist()


def get_token_blacklist() -> TokenBlacklist:
    """Get the global token blacklist."""
    return _token_blacklist


# ============================================================================
# FastAPI Dependencies
# ============================================================================

async def verify_api_key(
    api_key: Optional[str] = Security(api_key_header)
) -> AuthenticatedUser:
    """
    Verify API key from request header.

    Args:
        api_key: API key from X-API-Key header

    Returns:
        AuthenticatedUser with organization context

    Raises:
        HTTPException: If API key is invalid
    """
    if not api_key:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="API key required",
            headers={"WWW-Authenticate": "ApiKey"},
        )

    manager = get_api_key_manager()
    key_info = manager.validate_api_key(api_key)

    if not key_info:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid API key",
            headers={"WWW-Authenticate": "ApiKey"},
        )

    return AuthenticatedUser(
        user_id=str(key_info.agent_id),
        email=f"agent-{key_info.agent_id}@system",
        organization_id=key_info.organization_id,
        roles=["agent"],
        auth_type="api_key",
        agent_id=key_info.agent_id,
    )


async def verify_api_key_agent_id(
    api_key: Optional[str] = Security(api_key_header)
) -> UUID:
    """
    Verify API key and return just the agent ID (backwards compatibility).

    Args:
        api_key: API key from X-API-Key header

    Returns:
        Agent ID

    Raises:
        HTTPException: If API key is invalid
    """
    user = await verify_api_key(api_key)
    return user.agent_id


async def verify_jwt_token(
    credentials: Optional[HTTPAuthorizationCredentials] = Security(bearer_scheme)
) -> dict:
    """
    Verify JWT token from request header.

    Args:
        credentials: Bearer token credentials

    Returns:
        Token payload

    Raises:
        HTTPException: If token is invalid (in production)
    """
    if not credentials:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication required",
            headers={"WWW-Authenticate": "Bearer"},
        )

    manager = get_jwt_manager()
    payload = manager.verify_token(credentials.credentials)

    if not payload:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token",
            headers={"WWW-Authenticate": "Bearer"},
        )

    return payload


async def verify_dashboard_access(
    token_payload: dict = Security(verify_jwt_token)
) -> dict:
    """
    Verify dashboard access from JWT token.

    Args:
        token_payload: Decoded JWT payload

    Returns:
        User information

    Raises:
        HTTPException: If not authorized for dashboard
    """
    if token_payload.get("type") != "dashboard":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not authorized for dashboard access",
        )

    return token_payload


# ============================================================================
# Password Hashing Utilities
# ============================================================================

def hash_password(password: str) -> str:
    """
    Hash password using bcrypt.

    Bcrypt has a 72-byte password limit. Passwords are automatically
    truncated to 72 bytes before hashing.

    Args:
        password: Plain text password

    Returns:
        Hashed password (as string)
    """
    # Truncate to 72 bytes to comply with bcrypt limit
    password_bytes = password.encode('utf-8')[:72]

    # Generate salt and hash
    salt = bcrypt.gensalt()
    hashed = bcrypt.hashpw(password_bytes, salt)

    # Return as string for storage
    return hashed.decode('utf-8')


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """
    Verify password against hash.

    Bcrypt has a 72-byte password limit. Passwords are automatically
    truncated to 72 bytes to match the hashing behavior.

    Args:
        plain_password: Plain text password
        hashed_password: Hashed password (as string)

    Returns:
        True if password matches
    """
    # Truncate to 72 bytes to match hashing behavior
    password_bytes = plain_password.encode('utf-8')[:72]
    hashed_bytes = hashed_password.encode('utf-8')

    # Verify password
    return bcrypt.checkpw(password_bytes, hashed_bytes)


# ============================================================================
# Organization-based Rate Limiting
# ============================================================================

class RateLimiter:
    """
    Rate limiter for API endpoints.

    Implements token bucket algorithm per organization.
    """

    def __init__(self):
        """Initialize rate limiter."""
        # org_id -> {tokens, last_refill}
        self._buckets = {}

        # Rate limits (requests per minute)
        self._limits = {
            "startup": 100,  # 100 req/min
            "growth": 500,   # 500 req/min
            "enterprise": 2000,  # 2000 req/min
        }

    async def check_rate_limit(
        self,
        org_id: str,
        tier: str = "startup"
    ) -> bool:
        """
        Check if request is within rate limit.

        Args:
            org_id: Organization ID
            tier: Organization tier (startup, growth, enterprise)

        Returns:
            True if within limit, False if exceeded
        """
        now = datetime.utcnow()
        limit = self._limits.get(tier, 100)

        if org_id not in self._buckets:
            # Initialize bucket
            self._buckets[org_id] = {
                "tokens": limit,
                "last_refill": now,
            }

        bucket = self._buckets[org_id]

        # Refill tokens based on elapsed time
        elapsed = (now - bucket["last_refill"]).total_seconds()
        refill_amount = (elapsed / 60.0) * limit  # tokens per minute
        bucket["tokens"] = min(limit, bucket["tokens"] + refill_amount)
        bucket["last_refill"] = now

        # Check if tokens available
        if bucket["tokens"] >= 1:
            bucket["tokens"] -= 1
            return True

        return False


# Global rate limiter instance
_rate_limiter: Optional[RateLimiter] = None


def get_rate_limiter() -> RateLimiter:
    """Get or create global rate limiter instance."""
    global _rate_limiter
    if _rate_limiter is None:
        _rate_limiter = RateLimiter()
    return _rate_limiter


# ============================================================================
# Organization Validation (Multi-Tenancy Enforcement)
# ============================================================================

async def get_current_user(
    api_key: Optional[str] = Security(api_key_header),
    credentials: Optional[HTTPAuthorizationCredentials] = Security(bearer_scheme)
) -> AuthenticatedUser:
    """
    Get current authenticated user from either API key or JWT token.

    Tries API key first, then JWT token. Returns AuthenticatedUser with
    organization context for multi-tenancy enforcement.

    Args:
        api_key: API key from X-API-Key header
        credentials: Bearer token credentials

    Returns:
        AuthenticatedUser with organization context

    Raises:
        HTTPException: If neither authentication method succeeds
    """
    # Try API key first
    if api_key:
        manager = get_api_key_manager()
        key_info = manager.validate_api_key(api_key)
        if key_info:
            return AuthenticatedUser(
                user_id=str(key_info.agent_id),
                email=f"agent-{key_info.agent_id}@system",
                organization_id=key_info.organization_id,
                roles=["agent"],
                auth_type="api_key",
                agent_id=key_info.agent_id,
            )

    # Try JWT token
    if credentials:
        manager = get_jwt_manager()
        payload = manager.verify_token(credentials.credentials)
        if payload:
            org_id = payload.get("org_id", payload.get("organization_id", "default"))
            return AuthenticatedUser(
                user_id=payload.get("sub", payload.get("user_id", "unknown")),
                email=payload.get("email", "unknown@unknown"),
                organization_id=org_id,
                roles=payload.get("roles", [payload.get("role", "user")]),
                auth_type="jwt",
            )

    raise HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Authentication required",
        headers={"WWW-Authenticate": "Bearer, ApiKey"},
    )


def validate_organization(
    organization_id: str,
    user: AuthenticatedUser,
) -> None:
    """
    Validate that the user belongs to the requested organization.

    This is the core multi-tenancy enforcement function. Call this
    in any route that accepts organization_id as a parameter.

    Args:
        organization_id: Requested organization ID
        user: Authenticated user

    Raises:
        HTTPException: If user doesn't belong to the organization
    """
    if user.organization_id != organization_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"Access denied: You do not have access to organization '{organization_id}'",
        )


class OrganizationValidator:
    """
    Dependency class for organization validation.

    Use as a FastAPI dependency to automatically validate organization access.

    Example:
        @router.get("/agents")
        async def list_agents(
            organization_id: str = Query(...),
            _: None = Depends(OrganizationValidator()),
            user: AuthenticatedUser = Depends(get_current_user),
        ):
            # User's organization is validated automatically
            pass
    """

    async def __call__(
        self,
        organization_id: str = Query(..., description="Organization ID"),
        user: AuthenticatedUser = Depends(get_current_user),
    ) -> AuthenticatedUser:
        """
        Validate organization access and return authenticated user.

        Args:
            organization_id: Requested organization ID from query params
            user: Authenticated user

        Returns:
            AuthenticatedUser if validation passes

        Raises:
            HTTPException: If user doesn't belong to the organization
        """
        validate_organization(organization_id, user)
        return user


# Convenience instance for use as dependency
require_organization = OrganizationValidator()


# ============================================================================
# Convenience Dependencies for Common Use Cases
# ============================================================================

async def get_current_user_id(
    user: AuthenticatedUser = Depends(get_current_user)
) -> str:
    """
    Get the current user's ID.

    Convenience dependency for routes that only need the user ID.
    """
    return user.user_id


async def get_current_organization_id(
    user: AuthenticatedUser = Depends(get_current_user)
) -> str:
    """
    Get the current user's organization ID.

    This is the primary dependency for multi-tenancy enforcement.
    All queries should filter by this organization_id.

    Returns:
        Organization ID string
    """
    return user.organization_id
