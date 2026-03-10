"""
White-Label & Reseller Program Service - P2 Feature #4

Business logic for white-labeling and reseller management.

Key Features:
- Partner onboarding and management
- Custom branding configuration
- Customer tracking and attribution
- Commission calculation and payouts
- API key management for partners
- Partner portal resources
"""

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, and_, or_, desc
from typing import List, Optional, Dict, Any, Tuple
from datetime import datetime, timedelta
from decimal import Decimal
import hashlib
import secrets

from backend.shared.whitelabel_models import (
    Partner,
    WhiteLabelBranding,
    PartnerCustomer,
    Commission,
    PartnerApiKey,
    PartnerResource,
    PartnerCreate,
    PartnerUpdate,
    BrandingCreate,
    BrandingUpdate,
    CustomerCreate,
    ApiKeyCreate,
    PartnerStats,
    PartnerTier,
    PartnerStatus,
    BrandingStatus,
    CommissionStatus,
    BillingCycle,
)


class WhiteLabelService:
    """Service for white-label and reseller operations."""

    # ========================================================================
    # Partner Management
    # ========================================================================

    @staticmethod
    async def create_partner(
        db: AsyncSession,
        partner_data: PartnerCreate,
    ) -> Partner:
        """
        Create new partner account.

        Generates unique partner code and sets up initial tier.
        """
        # Generate unique partner code
        partner_code = WhiteLabelService._generate_partner_code(partner_data.company_name)

        # Ensure uniqueness
        counter = 1
        base_code = partner_code
        while True:
            stmt = select(Partner).where(Partner.partner_code == partner_code)
            result = await db.execute(stmt)
            if not result.scalar_one_or_none():
                break
            partner_code = f"{base_code}{counter}"
            counter += 1

        # Generate referral code
        referral_code = f"REF-{secrets.token_hex(4).upper()}"

        partner = Partner(
            company_name=partner_data.company_name,
            partner_code=partner_code,
            primary_contact_name=partner_data.primary_contact_name,
            primary_contact_email=partner_data.primary_contact_email,
            primary_contact_phone=partner_data.primary_contact_phone,
            website=partner_data.website,
            business_type=partner_data.business_type,
            address_line1=partner_data.address_line1,
            city=partner_data.city,
            state=partner_data.state,
            postal_code=partner_data.postal_code,
            country=partner_data.country,
            tier=PartnerTier.BASIC,
            status=PartnerStatus.PENDING,
            commission_rate=10.0,  # Default 10% for basic tier
            referral_code=referral_code,
        )

        db.add(partner)
        await db.commit()
        await db.refresh(partner)

        return partner

    @staticmethod
    def _generate_partner_code(company_name: str) -> str:
        """Generate partner code from company name."""
        # Take first letters of words, max 8 chars
        words = company_name.upper().split()
        code = "".join([w[0] for w in words if w])[:8]
        return code or "PARTNER"

    @staticmethod
    async def get_partner(
        db: AsyncSession,
        partner_id: int,
    ) -> Optional[Partner]:
        """Get partner by ID."""
        stmt = select(Partner).where(Partner.id == partner_id)
        result = await db.execute(stmt)
        return result.scalar_one_or_none()

    @staticmethod
    async def get_partner_by_code(
        db: AsyncSession,
        partner_code: str,
    ) -> Optional[Partner]:
        """Get partner by code."""
        stmt = select(Partner).where(Partner.partner_code == partner_code)
        result = await db.execute(stmt)
        return result.scalar_one_or_none()

    @staticmethod
    async def update_partner(
        db: AsyncSession,
        partner_id: int,
        partner_data: PartnerUpdate,
    ) -> Partner:
        """Update partner account."""
        partner = await WhiteLabelService.get_partner(db, partner_id)
        if not partner:
            raise ValueError(f"Partner {partner_id} not found")

        # Update fields
        if partner_data.company_name is not None:
            partner.company_name = partner_data.company_name
        if partner_data.primary_contact_name is not None:
            partner.primary_contact_name = partner_data.primary_contact_name
        if partner_data.primary_contact_email is not None:
            partner.primary_contact_email = partner_data.primary_contact_email
        if partner_data.primary_contact_phone is not None:
            partner.primary_contact_phone = partner_data.primary_contact_phone
        if partner_data.website is not None:
            partner.website = partner_data.website
        if partner_data.tier is not None:
            partner.tier = partner_data.tier
            # Update commission rate based on tier
            partner.commission_rate = WhiteLabelService._get_tier_commission_rate(partner_data.tier)
        if partner_data.status is not None:
            old_status = partner.status
            partner.status = partner_data.status
            if old_status != PartnerStatus.ACTIVE and partner_data.status == PartnerStatus.ACTIVE:
                partner.activated_at = datetime.utcnow()
            if partner_data.status == PartnerStatus.SUSPENDED:
                partner.suspended_at = datetime.utcnow()
        if partner_data.commission_rate is not None:
            partner.commission_rate = partner_data.commission_rate

        await db.commit()
        await db.refresh(partner)

        return partner

    @staticmethod
    def _get_tier_commission_rate(tier: PartnerTier) -> float:
        """Get default commission rate for tier."""
        rates = {
            PartnerTier.BASIC: 10.0,
            PartnerTier.SILVER: 15.0,
            PartnerTier.GOLD: 20.0,
            PartnerTier.PLATINUM: 25.0,
            PartnerTier.ENTERPRISE: 30.0,
        }
        return rates.get(tier, 10.0)

    @staticmethod
    async def list_partners(
        db: AsyncSession,
        status: Optional[PartnerStatus] = None,
        tier: Optional[PartnerTier] = None,
        limit: int = 50,
    ) -> List[Partner]:
        """List partners with filters."""
        stmt = select(Partner)

        if status:
            stmt = stmt.where(Partner.status == status)
        if tier:
            stmt = stmt.where(Partner.tier == tier)

        stmt = stmt.order_by(desc(Partner.created_at)).limit(limit)

        result = await db.execute(stmt)
        return result.scalars().all()

    # ========================================================================
    # Branding Management
    # ========================================================================

    @staticmethod
    async def create_branding(
        db: AsyncSession,
        partner_id: int,
        branding_data: BrandingCreate,
    ) -> WhiteLabelBranding:
        """Create custom branding for partner."""
        # Verify partner exists and is active
        partner = await WhiteLabelService.get_partner(db, partner_id)
        if not partner:
            raise ValueError(f"Partner {partner_id} not found")
        if partner.status != PartnerStatus.ACTIVE:
            raise ValueError("Partner must be active to configure branding")

        branding = WhiteLabelBranding(
            partner_id=partner_id,
            custom_domain=branding_data.custom_domain,
            company_name=branding_data.company_name,
            logo_url=branding_data.logo_url,
            favicon_url=branding_data.favicon_url,
            primary_color=branding_data.primary_color,
            secondary_color=branding_data.secondary_color,
            accent_color=branding_data.accent_color,
            support_email=branding_data.support_email,
            support_url=branding_data.support_url,
            privacy_policy_url=branding_data.privacy_policy_url,
            terms_of_service_url=branding_data.terms_of_service_url,
            status='draft',
        )

        db.add(branding)
        await db.commit()
        await db.refresh(branding)

        return branding

    @staticmethod
    async def update_branding(
        db: AsyncSession,
        branding_id: int,
        partner_id: int,
        branding_data: BrandingUpdate,
    ) -> WhiteLabelBranding:
        """Update branding configuration."""
        stmt = select(WhiteLabelBranding).where(
            and_(
                WhiteLabelBranding.id == branding_id,
                WhiteLabelBranding.partner_id == partner_id
            )
        )
        result = await db.execute(stmt)
        branding = result.scalar_one_or_none()

        if not branding:
            raise ValueError(f"Branding {branding_id} not found or access denied")

        # Update fields
        if branding_data.company_name is not None:
            branding.company_name = branding_data.company_name
        if branding_data.logo_url is not None:
            branding.logo_url = branding_data.logo_url
        if branding_data.favicon_url is not None:
            branding.favicon_url = branding_data.favicon_url
        if branding_data.primary_color is not None:
            branding.primary_color = branding_data.primary_color
        if branding_data.secondary_color is not None:
            branding.secondary_color = branding_data.secondary_color
        if branding_data.accent_color is not None:
            branding.accent_color = branding_data.accent_color
        if branding_data.support_email is not None:
            branding.support_email = branding_data.support_email
        if branding_data.custom_css is not None:
            branding.custom_css = branding_data.custom_css

        await db.commit()
        await db.refresh(branding)

        return branding

    @staticmethod
    async def get_branding_by_domain(
        db: AsyncSession,
        domain: str,
    ) -> Optional[WhiteLabelBranding]:
        """Get branding by custom domain."""
        stmt = select(WhiteLabelBranding).where(
            and_(
                WhiteLabelBranding.custom_domain == domain,
                WhiteLabelBranding.is_active == True,
                WhiteLabelBranding.status == 'approved'
            )
        )
        result = await db.execute(stmt)
        return result.scalar_one_or_none()

    @staticmethod
    async def activate_branding(
        db: AsyncSession,
        branding_id: int,
        approved_by: str,
    ) -> WhiteLabelBranding:
        """Approve and activate branding."""
        stmt = select(WhiteLabelBranding).where(WhiteLabelBranding.id == branding_id)
        result = await db.execute(stmt)
        branding = result.scalar_one_or_none()

        if not branding:
            raise ValueError(f"Branding {branding_id} not found")

        # Deactivate other brandings for same partner
        stmt = select(WhiteLabelBranding).where(
            and_(
                WhiteLabelBranding.partner_id == branding.partner_id,
                WhiteLabelBranding.id != branding_id,
                WhiteLabelBranding.is_active == True
            )
        )
        result = await db.execute(stmt)
        old_brandings = result.scalars().all()
        for old in old_brandings:
            old.is_active = False

        branding.status = 'approved'
        branding.is_active = True
        branding.approved_at = datetime.utcnow()
        branding.approved_by = approved_by

        await db.commit()
        await db.refresh(branding)

        return branding

    # ========================================================================
    # Customer Management
    # ========================================================================

    @staticmethod
    async def add_customer(
        db: AsyncSession,
        partner_id: int,
        customer_data: CustomerCreate,
    ) -> PartnerCustomer:
        """Add customer to partner account."""
        customer = PartnerCustomer(
            partner_id=partner_id,
            customer_email=customer_data.customer_email,
            customer_name=customer_data.customer_name,
            plan_name=customer_data.plan_name,
            billing_cycle=customer_data.billing_cycle,
            mrr_usd=customer_data.mrr_usd,
            referral_source=customer_data.referral_source,
            activated_at=datetime.utcnow(),
        )

        db.add(customer)

        # Update partner metrics
        partner = await WhiteLabelService.get_partner(db, partner_id)
        if partner:
            partner.total_customers += 1
            from decimal import Decimal
            partner.total_revenue_usd += Decimal(str(customer_data.mrr_usd))

        await db.commit()
        await db.refresh(customer)

        return customer

    @staticmethod
    async def list_partner_customers(
        db: AsyncSession,
        partner_id: int,
        active_only: bool = True,
    ) -> List[PartnerCustomer]:
        """List customers for partner."""
        stmt = select(PartnerCustomer).where(PartnerCustomer.partner_id == partner_id)

        if active_only:
            stmt = stmt.where(PartnerCustomer.is_active == True)

        stmt = stmt.order_by(desc(PartnerCustomer.created_at))

        result = await db.execute(stmt)
        return result.scalars().all()

    # ========================================================================
    # Commission Management
    # ========================================================================

    @staticmethod
    async def calculate_commission(
        db: AsyncSession,
        partner_id: int,
        period_start: datetime,
        period_end: datetime,
    ) -> Commission:
        """
        Calculate commission for period.

        Aggregates revenue from partner's customers for the period.
        """
        partner = await WhiteLabelService.get_partner(db, partner_id)
        if not partner:
            raise ValueError(f"Partner {partner_id} not found")

        # Get customers active during period
        stmt = select(PartnerCustomer).where(
            and_(
                PartnerCustomer.partner_id == partner_id,
                PartnerCustomer.is_active == True,
                PartnerCustomer.activated_at <= period_end
            )
        )
        result = await db.execute(stmt)
        customers = result.scalars().all()

        # Calculate revenue (for demo, using MRR * months in period)
        days_in_period = (period_end - period_start).days
        months_in_period = days_in_period / 30.0

        gross_revenue = sum(float(c.mrr_usd) * months_in_period for c in customers)
        commission_amount = gross_revenue * (partner.commission_rate / 100.0)

        # Create commission record
        commission = Commission(
            partner_id=partner_id,
            period_start=period_start,
            period_end=period_end,
            gross_revenue_usd=gross_revenue,
            commission_rate=partner.commission_rate,
            commission_amount_usd=commission_amount,
            customer_count=len(customers),
            transaction_count=len(customers),  # Simplified
            details={
                "customers": [
                    {
                        "email": c.customer_email,
                        "mrr": float(c.mrr_usd),
                        "revenue": float(c.mrr_usd) * months_in_period,
                    }
                    for c in customers
                ]
            },
            status='pending',
        )

        db.add(commission)

        # Update partner total commission
        partner.total_commission_usd += Decimal(str(commission_amount))

        await db.commit()
        await db.refresh(commission)

        return commission

    @staticmethod
    async def approve_commission(
        db: AsyncSession,
        commission_id: int,
    ) -> Commission:
        """Approve commission for payment."""
        stmt = select(Commission).where(Commission.id == commission_id)
        result = await db.execute(stmt)
        commission = result.scalar_one_or_none()

        if not commission:
            raise ValueError(f"Commission {commission_id} not found")

        commission.status = 'approved'

        await db.commit()
        await db.refresh(commission)

        return commission

    @staticmethod
    async def mark_commission_paid(
        db: AsyncSession,
        commission_id: int,
        payment_reference: str,
        payment_method: str,
    ) -> Commission:
        """Mark commission as paid."""
        stmt = select(Commission).where(Commission.id == commission_id)
        result = await db.execute(stmt)
        commission = result.scalar_one_or_none()

        if not commission:
            raise ValueError(f"Commission {commission_id} not found")

        commission.status = 'paid'
        commission.payment_date = datetime.utcnow()
        commission.payment_reference = payment_reference
        commission.payment_method = payment_method

        await db.commit()
        await db.refresh(commission)

        return commission

    @staticmethod
    async def list_commissions(
        db: AsyncSession,
        partner_id: int,
        status: Optional[CommissionStatus] = None,
    ) -> List[Commission]:
        """List commissions for partner."""
        stmt = select(Commission).where(Commission.partner_id == partner_id)

        if status:
            stmt = stmt.where(Commission.status == status)

        stmt = stmt.order_by(desc(Commission.period_start))

        result = await db.execute(stmt)
        return result.scalars().all()

    # ========================================================================
    # API Key Management
    # ========================================================================

    @staticmethod
    async def create_api_key(
        db: AsyncSession,
        partner_id: int,
        key_data: ApiKeyCreate,
    ) -> Tuple[PartnerApiKey, str]:
        """
        Create API key for partner.

        Returns (api_key_record, plaintext_key).
        """
        # Generate key
        key = f"pk_{secrets.token_urlsafe(32)}"
        key_hash = hashlib.sha256(key.encode()).hexdigest()
        key_prefix = key[:10]

        api_key = PartnerApiKey(
            partner_id=partner_id,
            key_name=key_data.key_name,
            key_hash=key_hash,
            key_prefix=key_prefix,
            scopes=key_data.scopes,
            expires_at=key_data.expires_at,
        )

        db.add(api_key)
        await db.commit()
        await db.refresh(api_key)

        return api_key, key

    @staticmethod
    async def verify_api_key(
        db: AsyncSession,
        key: str,
    ) -> Optional[PartnerApiKey]:
        """Verify and return API key."""
        key_hash = hashlib.sha256(key.encode()).hexdigest()

        stmt = select(PartnerApiKey).where(
            and_(
                PartnerApiKey.key_hash == key_hash,
                PartnerApiKey.is_active == True
            )
        )
        result = await db.execute(stmt)
        api_key = result.scalar_one_or_none()

        if api_key:
            # Check expiration
            if api_key.expires_at and api_key.expires_at < datetime.utcnow():
                return None

            # Update usage
            api_key.last_used_at = datetime.utcnow()
            api_key.usage_count += 1
            await db.commit()

        return api_key

    @staticmethod
    async def revoke_api_key(
        db: AsyncSession,
        key_id: int,
        partner_id: int,
    ) -> None:
        """Revoke API key."""
        stmt = select(PartnerApiKey).where(
            and_(
                PartnerApiKey.id == key_id,
                PartnerApiKey.partner_id == partner_id
            )
        )
        result = await db.execute(stmt)
        api_key = result.scalar_one_or_none()

        if not api_key:
            raise ValueError(f"API key {key_id} not found or access denied")

        api_key.is_active = False
        api_key.revoked_at = datetime.utcnow()

        await db.commit()

    # ========================================================================
    # Partner Statistics
    # ========================================================================

    @staticmethod
    async def get_partner_stats(
        db: AsyncSession,
        partner_id: int,
    ) -> PartnerStats:
        """Get partner statistics."""
        partner = await WhiteLabelService.get_partner(db, partner_id)
        if not partner:
            raise ValueError(f"Partner {partner_id} not found")

        # Count active customers
        stmt = select(func.count(PartnerCustomer.id)).where(
            and_(
                PartnerCustomer.partner_id == partner_id,
                PartnerCustomer.is_active == True
            )
        )
        result = await db.execute(stmt)
        active_customers = result.scalar() or 0

        # Count churned customers
        stmt = select(func.count(PartnerCustomer.id)).where(
            and_(
                PartnerCustomer.partner_id == partner_id,
                PartnerCustomer.churned_at.isnot(None)
            )
        )
        result = await db.execute(stmt)
        churned_customers = result.scalar() or 0

        # Calculate pending commission
        stmt = select(func.sum(Commission.commission_amount_usd)).where(
            and_(
                Commission.partner_id == partner_id,
                Commission.status.in_(['pending', 'approved'])
            )
        )
        result = await db.execute(stmt)
        pending_commission = float(result.scalar() or 0.0)

        # Calculate average customer value
        avg_customer_value = (
            float(partner.total_revenue_usd) / partner.total_customers
            if partner.total_customers > 0
            else 0.0
        )

        # Calculate retention rate
        retention_rate = (
            (active_customers / partner.total_customers) * 100
            if partner.total_customers > 0
            else 0.0
        )

        return PartnerStats(
            partner_id=partner_id,
            total_customers=partner.total_customers,
            active_customers=active_customers,
            churned_customers=churned_customers,
            total_revenue_usd=float(partner.total_revenue_usd),
            total_commission_usd=float(partner.total_commission_usd),
            pending_commission_usd=pending_commission,
            avg_customer_value_usd=avg_customer_value,
            customer_retention_rate=retention_rate,
        )
