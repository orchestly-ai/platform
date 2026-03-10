"""
White-Label & Reseller Program API - P2 Feature #4

REST API for partner and white-label management.

Endpoints:

Partner Management:
- POST   /api/v1/partners                     - Create partner account
- GET    /api/v1/partners                     - List partners (admin)
- GET    /api/v1/partners/{id}                - Get partner details
- PUT    /api/v1/partners/{id}                - Update partner
- GET    /api/v1/partners/{id}/stats          - Get partner statistics

Branding:
- POST   /api/v1/partners/{id}/branding       - Create branding config
- GET    /api/v1/partners/{id}/branding       - Get branding config
- PUT    /api/v1/branding/{id}                - Update branding
- POST   /api/v1/branding/{id}/activate       - Activate branding
- GET    /api/v1/branding/by-domain/{domain}  - Get branding by domain

Customers:
- POST   /api/v1/partners/{id}/customers      - Add customer
- GET    /api/v1/partners/{id}/customers      - List customers

Commissions:
- POST   /api/v1/partners/{id}/commissions/calculate - Calculate commission
- GET    /api/v1/partners/{id}/commissions    - List commissions
- POST   /api/v1/commissions/{id}/approve     - Approve commission
- POST   /api/v1/commissions/{id}/pay         - Mark as paid

API Keys:
- POST   /api/v1/partners/{id}/api-keys       - Create API key
- GET    /api/v1/partners/{id}/api-keys       - List API keys
- DELETE /api/v1/api-keys/{id}                - Revoke API key
"""

from fastapi import APIRouter, Depends, HTTPException, Query, Header, status
from sqlalchemy.ext.asyncio import AsyncSession
from typing import List, Optional
from datetime import datetime, timedelta

from backend.database.session import get_db
from backend.shared.whitelabel_models import (
    PartnerCreate,
    PartnerUpdate,
    PartnerResponse,
    BrandingCreate,
    BrandingUpdate,
    BrandingResponse,
    CustomerCreate,
    CustomerResponse,
    CommissionResponse,
    ApiKeyCreate,
    ApiKeyResponse,
    PartnerStats,
    PartnerStatus,
    PartnerTier,
    CommissionStatus,
)
from backend.shared.whitelabel_service import WhiteLabelService
from backend.shared.auth import get_current_user_id


router = APIRouter(prefix="/api/v1", tags=["whitelabel"])


async def get_current_partner_id(
    x_partner_key: Optional[str] = Header(None),
    db: AsyncSession = Depends(get_db),
) -> Optional[int]:
    """Get partner ID from API key header."""
    if not x_partner_key:
        return None

    api_key = await WhiteLabelService.verify_api_key(db, x_partner_key)
    if api_key:
        return api_key.partner_id
    return None


# ============================================================================
# Partner Management
# ============================================================================

@router.post("/partners", response_model=PartnerResponse, status_code=status.HTTP_201_CREATED)
async def create_partner(
    partner_data: PartnerCreate,
    db: AsyncSession = Depends(get_db),
):
    """
    Create new partner account.

    Generates unique partner code and referral code.
    Starts in PENDING status for approval.
    """
    partner = await WhiteLabelService.create_partner(db, partner_data)
    return partner


@router.get("/partners", response_model=List[PartnerResponse])
async def list_partners(
    status: Optional[PartnerStatus] = Query(None),
    tier: Optional[PartnerTier] = Query(None),
    limit: int = Query(50, ge=1, le=200),
    db: AsyncSession = Depends(get_db),
    user_id: str = Depends(get_current_user_id),
):
    """
    List partners (admin only).

    Filter by status and tier.
    """
    partners = await WhiteLabelService.list_partners(db, status, tier, limit)
    return partners


@router.get("/partners/{partner_id}", response_model=PartnerResponse)
async def get_partner(
    partner_id: int,
    db: AsyncSession = Depends(get_db),
):
    """
    Get partner details.

    Returns partner account information.
    """
    partner = await WhiteLabelService.get_partner(db, partner_id)
    if not partner:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Partner not found",
        )
    return partner


@router.put("/partners/{partner_id}", response_model=PartnerResponse)
async def update_partner(
    partner_id: int,
    partner_data: PartnerUpdate,
    db: AsyncSession = Depends(get_db),
    user_id: str = Depends(get_current_user_id),
):
    """
    Update partner account (admin only).

    Can update tier, status, commission rate.
    """
    try:
        partner = await WhiteLabelService.update_partner(db, partner_id, partner_data)
        return partner
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e),
        )


@router.get("/partners/{partner_id}/stats", response_model=PartnerStats)
async def get_partner_stats(
    partner_id: int,
    db: AsyncSession = Depends(get_db),
):
    """
    Get partner statistics.

    Returns:
    - Customer counts (total, active, churned)
    - Revenue and commission metrics
    - Retention rate
    """
    try:
        stats = await WhiteLabelService.get_partner_stats(db, partner_id)
        return stats
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e),
        )


# ============================================================================
# Branding Management
# ============================================================================

@router.post("/partners/{partner_id}/branding", response_model=BrandingResponse, status_code=status.HTTP_201_CREATED)
async def create_branding(
    partner_id: int,
    branding_data: BrandingCreate,
    db: AsyncSession = Depends(get_db),
):
    """
    Create white-label branding configuration.

    Configure custom domain, logo, colors, etc.
    Partner must be ACTIVE to create branding.
    """
    try:
        branding = await WhiteLabelService.create_branding(db, partner_id, branding_data)
        return branding
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )


@router.get("/partners/{partner_id}/branding")
async def get_partner_branding(
    partner_id: int,
    db: AsyncSession = Depends(get_db),
):
    """
    Get partner's branding configurations.

    Returns all branding configs (active and inactive).
    """
    from backend.shared.whitelabel_models import WhiteLabelBranding
    from sqlalchemy import select

    stmt = select(WhiteLabelBranding).where(
        WhiteLabelBranding.partner_id == partner_id
    )
    result = await db.execute(stmt)
    brandings = result.scalars().all()

    return brandings


@router.put("/branding/{branding_id}", response_model=BrandingResponse)
async def update_branding(
    branding_id: int,
    branding_data: BrandingUpdate,
    db: AsyncSession = Depends(get_db),
    partner_id: Optional[int] = Depends(get_current_partner_id),
):
    """
    Update branding configuration.

    Partner can only update their own branding.
    """
    if not partner_id:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Partner authentication required",
        )

    try:
        branding = await WhiteLabelService.update_branding(
            db, branding_id, partner_id, branding_data
        )
        return branding
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e),
        )


@router.post("/branding/{branding_id}/activate", response_model=BrandingResponse)
async def activate_branding(
    branding_id: int,
    db: AsyncSession = Depends(get_db),
    user_id: str = Depends(get_current_user_id),
):
    """
    Approve and activate branding (admin only).

    Deactivates any other active brandings for same partner.
    """
    try:
        branding = await WhiteLabelService.activate_branding(db, branding_id, user_id)
        return branding
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e),
        )


@router.get("/branding/by-domain/{domain}", response_model=BrandingResponse)
async def get_branding_by_domain(
    domain: str,
    db: AsyncSession = Depends(get_db),
):
    """
    Get branding by custom domain.

    Used for multi-tenant routing based on domain.
    """
    branding = await WhiteLabelService.get_branding_by_domain(db, domain)
    if not branding:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Branding not found for domain",
        )
    return branding


# ============================================================================
# Customer Management
# ============================================================================

@router.post("/partners/{partner_id}/customers", response_model=CustomerResponse, status_code=status.HTTP_201_CREATED)
async def add_customer(
    partner_id: int,
    customer_data: CustomerCreate,
    db: AsyncSession = Depends(get_db),
):
    """
    Add customer to partner account.

    Tracks customer attribution and revenue.
    """
    customer = await WhiteLabelService.add_customer(db, partner_id, customer_data)
    return customer


@router.get("/partners/{partner_id}/customers", response_model=List[CustomerResponse])
async def list_customers(
    partner_id: int,
    active_only: bool = Query(True),
    db: AsyncSession = Depends(get_db),
):
    """
    List partner's customers.

    Filter by active/all customers.
    """
    customers = await WhiteLabelService.list_partner_customers(
        db, partner_id, active_only
    )
    return customers


# ============================================================================
# Commission Management
# ============================================================================

@router.post("/partners/{partner_id}/commissions/calculate", response_model=CommissionResponse)
async def calculate_commission(
    partner_id: int,
    period_start: datetime = Query(..., description="Period start date"),
    period_end: datetime = Query(..., description="Period end date"),
    db: AsyncSession = Depends(get_db),
):
    """
    Calculate commission for period.

    Aggregates revenue from partner's customers.
    Creates commission record in PENDING status.
    """
    try:
        commission = await WhiteLabelService.calculate_commission(
            db, partner_id, period_start, period_end
        )
        return commission
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e),
        )


@router.get("/partners/{partner_id}/commissions", response_model=List[CommissionResponse])
async def list_commissions(
    partner_id: int,
    status: Optional[CommissionStatus] = Query(None),
    db: AsyncSession = Depends(get_db),
):
    """
    List partner's commissions.

    Filter by status (pending, approved, paid).
    """
    commissions = await WhiteLabelService.list_commissions(db, partner_id, status)
    return commissions


@router.post("/commissions/{commission_id}/approve", response_model=CommissionResponse)
async def approve_commission(
    commission_id: int,
    db: AsyncSession = Depends(get_db),
    user_id: str = Depends(get_current_user_id),
):
    """
    Approve commission for payment (admin only).

    Moves commission from PENDING to APPROVED status.
    """
    try:
        commission = await WhiteLabelService.approve_commission(db, commission_id)
        return commission
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e),
        )


@router.post("/commissions/{commission_id}/pay", response_model=CommissionResponse)
async def mark_commission_paid(
    commission_id: int,
    payment_reference: str = Query(..., description="Payment reference/transaction ID"),
    payment_method: str = Query(..., description="Payment method (stripe, wire, check)"),
    db: AsyncSession = Depends(get_db),
    user_id: str = Depends(get_current_user_id),
):
    """
    Mark commission as paid (admin only).

    Records payment details and updates status to PAID.
    """
    try:
        commission = await WhiteLabelService.mark_commission_paid(
            db, commission_id, payment_reference, payment_method
        )
        return commission
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e),
        )


# ============================================================================
# API Key Management
# ============================================================================

@router.post("/partners/{partner_id}/api-keys")
async def create_api_key(
    partner_id: int,
    key_data: ApiKeyCreate,
    db: AsyncSession = Depends(get_db),
):
    """
    Create API key for partner.

    Returns the key only once - must be stored securely.
    Key format: pk_<random_string>
    """
    api_key, plaintext_key = await WhiteLabelService.create_api_key(
        db, partner_id, key_data
    )

    return {
        "id": api_key.id,
        "key_name": api_key.key_name,
        "key": plaintext_key,  # Only returned once!
        "key_prefix": api_key.key_prefix,
        "scopes": api_key.scopes,
        "expires_at": api_key.expires_at,
        "created_at": api_key.created_at,
    }


@router.get("/partners/{partner_id}/api-keys", response_model=List[ApiKeyResponse])
async def list_api_keys(
    partner_id: int,
    db: AsyncSession = Depends(get_db),
):
    """
    List partner's API keys.

    Does not return the actual keys, only metadata.
    """
    from backend.shared.whitelabel_models import PartnerApiKey
    from sqlalchemy import select

    stmt = select(PartnerApiKey).where(
        PartnerApiKey.partner_id == partner_id
    ).order_by(PartnerApiKey.created_at.desc())

    result = await db.execute(stmt)
    api_keys = result.scalars().all()

    return api_keys


@router.delete("/api-keys/{key_id}", status_code=status.HTTP_204_NO_CONTENT)
async def revoke_api_key(
    key_id: int,
    db: AsyncSession = Depends(get_db),
    partner_id: Optional[int] = Depends(get_current_partner_id),
):
    """
    Revoke API key.

    Partner can only revoke their own keys.
    """
    if not partner_id:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Partner authentication required",
        )

    try:
        await WhiteLabelService.revoke_api_key(db, key_id, partner_id)
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e),
        )
