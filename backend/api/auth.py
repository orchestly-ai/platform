"""
Authentication API Endpoints

Provides login, register, and user management for dashboard authentication.
Users are stored in the database (UserModel) for persistence across restarts.
"""

import logging
import time
from collections import defaultdict
from datetime import datetime
from typing import Optional
from uuid import uuid4

import re

from fastapi import APIRouter, Depends, HTTPException, Request, status

logger = logging.getLogger(__name__)
from pydantic import BaseModel, EmailStr, Field, field_validator
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.database.session import get_db
from backend.shared.auth import (
    get_jwt_manager,
    hash_password,
    verify_password,
    verify_jwt_token,
)
from backend.shared.rbac_models import UserModel, OrganizationModel
from backend.shared.plan_enforcement import enforce_user_limit

router = APIRouter(prefix="/api/v1/auth", tags=["Authentication"])


# ============================================================================
# Login Rate Limiting & Account Lockout
# ============================================================================

class LoginRateLimiter:
    """Per-email rate limiting and account lockout for login attempts."""

    MAX_ATTEMPTS = 5           # max failed attempts before lockout
    LOCKOUT_SECONDS = 900      # 15-minute lockout
    WINDOW_SECONDS = 300       # 5-minute sliding window for attempt tracking

    def __init__(self):
        # email -> list of (timestamp, success) tuples
        self._attempts: dict[str, list[tuple[float, bool]]] = defaultdict(list)

    def _cleanup(self, email: str) -> None:
        """Remove expired attempts outside the window."""
        cutoff = time.monotonic() - self.WINDOW_SECONDS
        self._attempts[email] = [
            (ts, ok) for ts, ok in self._attempts[email] if ts > cutoff
        ]

    def check_rate_limit(self, email: str) -> None:
        """Raise 429 if the email is locked out or rate-limited."""
        self._cleanup(email)
        failures = [ts for ts, ok in self._attempts[email] if not ok]
        if len(failures) >= self.MAX_ATTEMPTS:
            oldest_fail = failures[-self.MAX_ATTEMPTS]
            lockout_until = oldest_fail + self.LOCKOUT_SECONDS
            remaining = lockout_until - time.monotonic()
            if remaining > 0:
                raise HTTPException(
                    status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                    detail=f"Account temporarily locked. Try again in {int(remaining)} seconds.",
                    headers={"Retry-After": str(int(remaining))},
                )

    def record_attempt(self, email: str, success: bool) -> None:
        """Record a login attempt."""
        self._attempts[email].append((time.monotonic(), success))


_login_rate_limiter = LoginRateLimiter()


# ============================================================================
# Request/Response Models
# ============================================================================

class LoginRequest(BaseModel):
    """Login request"""
    email: EmailStr
    password: str = Field(..., min_length=6)


class LoginResponse(BaseModel):
    """Login response"""
    access_token: str
    token_type: str = "bearer"
    expires_in: int  # seconds
    user: "UserResponse"


def _validate_password_complexity(password: str) -> str:
    """Validate password meets complexity requirements."""
    if len(password) < 12:
        raise ValueError("Password must be at least 12 characters long")
    if not re.search(r"[A-Z]", password):
        raise ValueError("Password must contain at least one uppercase letter")
    if not re.search(r"[a-z]", password):
        raise ValueError("Password must contain at least one lowercase letter")
    if not re.search(r"\d", password):
        raise ValueError("Password must contain at least one digit")
    return password


class RegisterRequest(BaseModel):
    """Registration request"""
    email: EmailStr
    password: str = Field(..., min_length=12)
    name: str = Field(..., min_length=2, max_length=100)
    organization_id: Optional[str] = "default"

    @field_validator("password")
    @classmethod
    def check_password_complexity(cls, v: str) -> str:
        return _validate_password_complexity(v)


class RegisterResponse(BaseModel):
    """Registration response"""
    user: "UserResponse"
    access_token: str
    token_type: str = "bearer"


class UserResponse(BaseModel):
    """User information response"""
    id: str
    email: str
    name: str
    role: str
    organization_id: str
    preferences: Optional[dict] = None


class UserUpdateRequest(BaseModel):
    """User update request"""
    name: Optional[str] = None
    current_password: Optional[str] = None
    new_password: Optional[str] = None
    preferences: Optional[dict] = None


class ChangePasswordRequest(BaseModel):
    """Password change request"""
    current_password: str
    new_password: str = Field(..., min_length=12)

    @field_validator("new_password")
    @classmethod
    def check_password_complexity(cls, v: str) -> str:
        return _validate_password_complexity(v)


# Update forward references
LoginResponse.model_rebuild()
RegisterResponse.model_rebuild()


# ============================================================================
# Helper: build UserResponse from UserModel
# ============================================================================

def _user_response(user: UserModel) -> UserResponse:
    """Convert a UserModel row to a UserResponse."""
    return UserResponse(
        id=user.user_id,
        email=user.email,
        name=user.full_name or "",
        role=getattr(user, "role", None) or "user",
        organization_id=user.organization_id,
        preferences=user.preferences,
    )


# ============================================================================
# Authentication Endpoints
# ============================================================================

@router.post("/login", response_model=LoginResponse)
async def login(request: LoginRequest, db: AsyncSession = Depends(get_db)):
    """
    Authenticate user and return JWT token.

    Returns access token for dashboard authentication.
    """
    email = request.email.lower()

    # Check rate limit / lockout before doing any work
    _login_rate_limiter.check_rate_limit(email)

    # Look up user in DB
    result = await db.execute(
        select(UserModel).where(UserModel.email == email)
    )
    user = result.scalar_one_or_none()

    if not user or not user.password_hash:
        _login_rate_limiter.record_attempt(email, success=False)
        logger.warning(f"AUTH_FAILED login email={email} reason=user_not_found")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password",
            headers={"WWW-Authenticate": "Bearer"},
        )

    # Verify password
    if not verify_password(request.password, user.password_hash):
        _login_rate_limiter.record_attempt(email, success=False)
        logger.warning(f"AUTH_FAILED login email={email} reason=bad_password")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password",
            headers={"WWW-Authenticate": "Bearer"},
        )

    # Successful login — clear failure history
    _login_rate_limiter.record_attempt(email, success=True)
    logger.info(f"AUTH_SUCCESS login email={email} user_id={user.user_id}")

    # Update last_login
    user.last_login = datetime.utcnow()
    await db.flush()

    # Create JWT token
    jwt_manager = get_jwt_manager()
    role = getattr(user, "role", None) or "user"
    token = jwt_manager.create_dashboard_token(
        user_id=user.user_id,
        email=user.email,
        role=role,
    )

    return LoginResponse(
        access_token=token,
        token_type="bearer",
        expires_in=jwt_manager.access_token_expire_minutes * 60,
        user=_user_response(user),
    )


@router.post("/register", response_model=RegisterResponse, status_code=status.HTTP_201_CREATED)
async def register(request: RegisterRequest, db: AsyncSession = Depends(get_db)):
    """
    Register new user account.

    Creates user and returns access token.
    """
    email = request.email.lower()
    target_org = request.organization_id or "default"

    # Enforce plan user limit
    await enforce_user_limit(target_org, db)

    # Check if user exists
    result = await db.execute(
        select(UserModel).where(UserModel.email == email)
    )
    if result.scalar_one_or_none():
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Email already registered",
        )

    # Create user
    user_id = f"user-{uuid4().hex[:8]}"
    user = UserModel(
        user_id=user_id,
        email=email,
        full_name=request.name,
        password_hash=hash_password(request.password),
        organization_id=request.organization_id or "default",
        is_active=True,
        is_email_verified=False,
        created_at=datetime.utcnow(),
        updated_at=datetime.utcnow(),
    )
    db.add(user)
    await db.flush()
    await db.commit()

    # Create JWT token
    jwt_manager = get_jwt_manager()
    token = jwt_manager.create_dashboard_token(
        user_id=user.user_id,
        email=user.email,
        role="user",
    )

    return RegisterResponse(
        user=_user_response(user),
        access_token=token,
        token_type="bearer",
    )


@router.get("/me", response_model=UserResponse)
async def get_current_user(
    token_payload: dict = Depends(verify_jwt_token),
    db: AsyncSession = Depends(get_db),
):
    """
    Get current authenticated user.

    Requires valid JWT token.
    """
    email = token_payload.get("email")
    if not email:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found",
        )

    result = await db.execute(
        select(UserModel).where(UserModel.email == email)
    )
    user = result.scalar_one_or_none()

    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found",
        )

    return _user_response(user)


@router.put("/me", response_model=UserResponse)
async def update_current_user(
    request: UserUpdateRequest,
    token_payload: dict = Depends(verify_jwt_token),
    db: AsyncSession = Depends(get_db),
):
    """
    Update current user profile.

    Requires valid JWT token.
    """
    email = token_payload.get("email")
    if not email:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found",
        )

    result = await db.execute(
        select(UserModel).where(UserModel.email == email)
    )
    user = result.scalar_one_or_none()

    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found",
        )

    # Update name if provided
    if request.name:
        user.full_name = request.name

    # Update preferences if provided
    if request.preferences is not None:
        user.preferences = request.preferences

    # Update password if provided
    if request.new_password:
        if not request.current_password:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Current password required to change password",
            )

        if not user.password_hash or not verify_password(request.current_password, user.password_hash):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Current password is incorrect",
            )

        user.password_hash = hash_password(request.new_password)

    user.updated_at = datetime.utcnow()
    await db.flush()

    return _user_response(user)


@router.post("/change-password")
async def change_password(
    request: ChangePasswordRequest,
    token_payload: dict = Depends(verify_jwt_token),
    db: AsyncSession = Depends(get_db),
):
    """
    Change user password.

    Requires valid JWT token and current password.
    """
    email = token_payload.get("email")
    if not email:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found",
        )

    result = await db.execute(
        select(UserModel).where(UserModel.email == email)
    )
    user = result.scalar_one_or_none()

    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found",
        )

    # Verify current password
    if not user.password_hash or not verify_password(request.current_password, user.password_hash):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Current password is incorrect",
        )

    # Update password
    user.password_hash = hash_password(request.new_password)
    user.updated_at = datetime.utcnow()
    await db.flush()

    logger.info(f"AUTH_EVENT password_changed email={email}")
    return {"message": "Password changed successfully"}


@router.post("/logout")
async def logout(token_payload: dict = Depends(verify_jwt_token)):
    """
    Logout user and blacklist the current token.
    """
    from backend.shared.auth import get_token_blacklist
    jti = token_payload.get("jti")
    exp = token_payload.get("exp", 0)
    if jti:
        get_token_blacklist().add(jti, exp)
    return {"message": "Logged out successfully"}


@router.post("/refresh")
async def refresh_token(
    token_payload: dict = Depends(verify_jwt_token),
    db: AsyncSession = Depends(get_db),
):
    """
    Refresh access token.

    Only allows refresh within the last 10 minutes of token life
    to prevent indefinite token extension from compromised tokens.
    """
    # Check that token is within the refresh window (last 10 min of expiry)
    import time as _time
    exp = token_payload.get("exp", 0)
    remaining = exp - _time.time()
    REFRESH_WINDOW_SECONDS = 600  # 10 minutes
    if remaining > REFRESH_WINDOW_SECONDS:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Token refresh only allowed within {REFRESH_WINDOW_SECONDS // 60} minutes of expiry",
        )

    email = token_payload.get("email")
    if not email:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found",
        )

    result = await db.execute(
        select(UserModel).where(UserModel.email == email)
    )
    user = result.scalar_one_or_none()

    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found",
        )

    # Create new token
    jwt_manager = get_jwt_manager()
    role = getattr(user, "role", None) or "user"
    token = jwt_manager.create_dashboard_token(
        user_id=user.user_id,
        email=user.email,
        role=role,
    )

    logger.info(f"AUTH_EVENT token_refreshed email={email}")
    return {
        "access_token": token,
        "token_type": "bearer",
        "expires_in": jwt_manager.access_token_expire_minutes * 60,
    }
