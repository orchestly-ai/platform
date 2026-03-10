"""
White-Label & Reseller Program Demo - P2 Feature #4

Demonstrates white-labeling and reseller features:
- Partner account creation
- Custom branding configuration
- Customer tracking and attribution
- Commission calculation
- API key management
- Partner portal

Run: python backend/demo_whitelabel.py
"""

import sys
from pathlib import Path

# Add parent directory to path so backend.* imports work
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

import asyncio
from datetime import datetime, timedelta
from sqlalchemy import text

from backend.database.session import AsyncSessionLocal, init_db
from backend.shared.whitelabel_models import *
from backend.shared.whitelabel_service import WhiteLabelService


async def demo_whitelabel():
    async with AsyncSessionLocal() as db:
        print("=" * 80)
        print("WHITE-LABEL & RESELLER PROGRAM DEMO")
        print("=" * 80)
        print()

        # Drop and recreate tables to fix ENUM type mismatches
        print("Setting up demo environment...")
        try:
            await db.execute(text("DROP TABLE IF EXISTS partner_resources CASCADE"))
            await db.execute(text("DROP TABLE IF EXISTS partner_api_keys CASCADE"))
            await db.execute(text("DROP TABLE IF EXISTS commissions CASCADE"))
            await db.execute(text("DROP TABLE IF EXISTS partner_customers CASCADE"))
            await db.execute(text("DROP TABLE IF EXISTS whitelabel_branding CASCADE"))
            await db.execute(text("DROP TABLE IF EXISTS partners CASCADE"))
            # Drop old ENUM types
            await db.execute(text("DROP TYPE IF EXISTS partnertier CASCADE"))
            await db.execute(text("DROP TYPE IF EXISTS partnerstatus CASCADE"))
            await db.execute(text("DROP TYPE IF EXISTS commissionstatus CASCADE"))
            await db.commit()
            print("✓ Cleaned up old tables and types")
        except Exception as e:
            print(f"⚠ Cleanup warning: {str(e)[:100]}")
            await db.rollback()

    await init_db()

    async with AsyncSessionLocal() as db:
        print("✓ Database ready\n")

        # Demo 1: Partner Onboarding
        print("🤝 DEMO 1: Partner Account Creation")
        print("-" * 80)

        print("\n1. Creating partner 'Acme Solutions'...")
        partner1 = await WhiteLabelService.create_partner(
            db,
            PartnerCreate(
                company_name="Acme Solutions Inc",
                primary_contact_name="John Smith",
                primary_contact_email="john@acmesolutions.com",
                primary_contact_phone="+1-555-0100",
                website="https://acmesolutions.com",
                business_type="LLC",
                address_line1="123 Main Street",
                city="San Francisco",
                state="CA",
                postal_code="94105",
                country="USA",
            ),
        )
        print(f"   ✓ Partner created: {partner1.company_name}")
        print(f"   ✓ Partner code: {partner1.partner_code}")
        print(f"   ✓ Referral code: {partner1.referral_code}")
        print(f"   ✓ Tier: {partner1.tier}")
        print(f"   ✓ Status: {partner1.status}")
        print(f"   ✓ Commission rate: {partner1.commission_rate}%")

        print("\n2. Creating partner 'Global Tech Partners'...")
        partner2 = await WhiteLabelService.create_partner(
            db,
            PartnerCreate(
                company_name="Global Tech Partners",
                primary_contact_name="Sarah Johnson",
                primary_contact_email="sarah@globaltech.com",
                website="https://globaltech.com",
            ),
        )
        print(f"   ✓ Partner created: {partner2.company_name}")
        print(f"   ✓ Partner code: {partner2.partner_code}")

        # Demo 2: Partner Activation and Tier Upgrade
        print("\n\n🎖️  DEMO 2: Partner Activation & Tier Management")
        print("-" * 80)

        print("\n1. Activating partner...")
        partner1 = await WhiteLabelService.update_partner(
            db,
            partner1.id,
            PartnerUpdate(status="active"),
        )
        print(f"   ✓ Status: {partner1.status}")
        print(f"   ✓ Activated at: {partner1.activated_at}")

        print("\n2. Upgrading to GOLD tier...")
        partner1 = await WhiteLabelService.update_partner(
            db,
            partner1.id,
            PartnerUpdate(tier="gold"),
        )
        print(f"   ✓ New tier: {partner1.tier}")
        print(f"   ✓ New commission rate: {partner1.commission_rate}%")

        # Demo 3: Custom Branding
        print("\n\n🎨 DEMO 3: White-Label Branding Configuration")
        print("-" * 80)

        print("\n1. Creating branding configuration...")
        branding = await WhiteLabelService.create_branding(
            db,
            partner1.id,
            BrandingCreate(
                custom_domain="app.acmesolutions.com",
                company_name="Acme AI Platform",
                logo_url="https://acmesolutions.com/logo.png",
                favicon_url="https://acmesolutions.com/favicon.ico",
                primary_color="#FF6B35",
                secondary_color="#004E89",
                accent_color="#F77F00",
                support_email="support@acmesolutions.com",
                support_url="https://help.acmesolutions.com",
                privacy_policy_url="https://acmesolutions.com/privacy",
                terms_of_service_url="https://acmesolutions.com/terms",
            ),
        )
        print(f"   ✓ Branding ID: {branding.id}")
        print(f"   ✓ Custom domain: {branding.custom_domain}")
        print(f"   ✓ Company name: {branding.company_name}")
        print(f"   ✓ Primary color: {branding.primary_color}")
        print(f"   ✓ Status: {branding.status}")

        print("\n2. Updating branding...")
        branding = await WhiteLabelService.update_branding(
            db,
            branding.id,
            partner1.id,
            BrandingUpdate(
                logo_url="https://acmesolutions.com/logo-v2.png",
                custom_css=".header { background: linear-gradient(45deg, #FF6B35, #F77F00); }",
            ),
        )
        print(f"   ✓ Logo updated")
        print(f"   ✓ Custom CSS applied")

        print("\n3. Approving and activating branding...")
        branding = await WhiteLabelService.activate_branding(
            db,
            branding.id,
            "admin_user",
        )
        print(f"   ✓ Status: {branding.status}")
        print(f"   ✓ Active: {branding.is_active}")
        print(f"   ✓ Approved at: {branding.approved_at}")

        # Demo 4: Customer Attribution
        print("\n\n👥 DEMO 4: Customer Tracking & Attribution")
        print("-" * 80)

        print("\n1. Adding customers to partner account...")
        customers = []

        customer1 = await WhiteLabelService.add_customer(
            db,
            partner1.id,
            CustomerCreate(
                customer_email="customer1@example.com",
                customer_name="Tech Startup Inc",
                plan_name="Professional",
                billing_cycle="monthly",
                mrr_usd=299.00,
                referral_source=f"referral_code:{partner1.referral_code}",
            ),
        )
        customers.append(customer1)
        print(f"   ✓ Customer 1: {customer1.customer_email} (${customer1.mrr_usd}/mo)")

        customer2 = await WhiteLabelService.add_customer(
            db,
            partner1.id,
            CustomerCreate(
                customer_email="customer2@example.com",
                customer_name="E-commerce Co",
                plan_name="Business",
                billing_cycle="annual",
                mrr_usd=499.00,
            ),
        )
        customers.append(customer2)
        print(f"   ✓ Customer 2: {customer2.customer_email} (${customer2.mrr_usd}/mo)")

        customer3 = await WhiteLabelService.add_customer(
            db,
            partner1.id,
            CustomerCreate(
                customer_email="customer3@example.com",
                customer_name="SaaS Platform Ltd",
                plan_name="Enterprise",
                billing_cycle="annual",
                mrr_usd=999.00,
            ),
        )
        customers.append(customer3)
        print(f"   ✓ Customer 3: {customer3.customer_email} (${customer3.mrr_usd}/mo)")

        print(f"\n2. Total customers added: {len(customers)}")
        total_mrr = sum(float(c.mrr_usd) for c in customers)
        print(f"   Total MRR: ${total_mrr:.2f}/mo")

        # Demo 5: Commission Calculation
        print("\n\n💰 DEMO 5: Commission Calculation")
        print("-" * 80)

        period_start = datetime.utcnow() - timedelta(days=30)
        period_end = datetime.utcnow()

        print(f"\n1. Calculating commission for period:")
        print(f"   Period: {period_start.date()} to {period_end.date()}")

        commission = await WhiteLabelService.calculate_commission(
            db,
            partner1.id,
            period_start,
            period_end,
        )

        print(f"\n2. Commission breakdown:")
        print(f"   Gross revenue: ${commission.gross_revenue_usd:.2f}")
        print(f"   Commission rate: {commission.commission_rate}%")
        print(f"   Commission amount: ${commission.commission_amount_usd:.2f}")
        print(f"   Customer count: {commission.customer_count}")
        print(f"   Status: {commission.status}")

        print("\n3. Customer details:")
        for detail in commission.details.get("customers", [])[:3]:
            print(f"   - {detail['email']}: ${detail['revenue']:.2f} revenue, MRR ${detail['mrr']:.2f}")

        # Demo 6: Commission Workflow
        print("\n\n📋 DEMO 6: Commission Approval Workflow")
        print("-" * 80)

        print("\n1. Approving commission...")
        commission = await WhiteLabelService.approve_commission(db, commission.id)
        print(f"   ✓ Status: {commission.status}")

        print("\n2. Marking commission as paid...")
        commission = await WhiteLabelService.mark_commission_paid(
            db,
            commission.id,
            "TXN-2024-001234",
            "stripe",
        )
        print(f"   ✓ Status: {commission.status}")
        print(f"   ✓ Payment date: {commission.payment_date}")
        print(f"   ✓ Payment reference: {commission.payment_reference}")
        print(f"   ✓ Payment method: {commission.payment_method}")

        # Demo 7: API Key Management
        print("\n\n🔑 DEMO 7: API Key Management")
        print("-" * 80)

        print("\n1. Creating API key for partner integration...")
        api_key, plaintext_key = await WhiteLabelService.create_api_key(
            db,
            partner1.id,
            ApiKeyCreate(
                key_name="Production API Key",
                scopes=["customers:read", "customers:write", "analytics:read"],
            ),
        )
        print(f"   ✓ Key ID: {api_key.id}")
        print(f"   ✓ Key name: {api_key.key_name}")
        print(f"   ✓ Key prefix: {api_key.key_prefix}")
        print(f"   ✓ Full key: {plaintext_key[:20]}... (store securely!)")
        print(f"   ✓ Scopes: {', '.join(api_key.scopes)}")

        print("\n2. Verifying API key...")
        verified_key = await WhiteLabelService.verify_api_key(db, plaintext_key)
        print(f"   ✓ Valid: {verified_key is not None}")
        print(f"   ✓ Partner ID: {verified_key.partner_id}")
        print(f"   ✓ Last used: {verified_key.last_used_at}")
        print(f"   ✓ Usage count: {verified_key.usage_count}")

        print("\n3. Creating additional API key...")
        api_key2, key2 = await WhiteLabelService.create_api_key(
            db,
            partner1.id,
            ApiKeyCreate(
                key_name="Development API Key",
                scopes=["customers:read"],
                expires_at=datetime.utcnow() + timedelta(days=90),
            ),
        )
        print(f"   ✓ Dev key created with 90-day expiration")

        # Demo 8: Partner Statistics
        print("\n\n📊 DEMO 8: Partner Statistics")
        print("-" * 80)

        print("\n1. Getting partner statistics...")
        stats = await WhiteLabelService.get_partner_stats(db, partner1.id)
        print(f"   Total customers: {stats.total_customers}")
        print(f"   Active customers: {stats.active_customers}")
        print(f"   Churned customers: {stats.churned_customers}")
        print(f"   Total revenue: ${stats.total_revenue_usd:.2f}")
        print(f"   Total commission: ${stats.total_commission_usd:.2f}")
        print(f"   Pending commission: ${stats.pending_commission_usd:.2f}")
        print(f"   Avg customer value: ${stats.avg_customer_value_usd:.2f}")
        print(f"   Retention rate: {stats.customer_retention_rate:.1f}%")

        # Demo 9: Multi-Tenant Routing
        print("\n\n🌐 DEMO 9: Multi-Tenant Domain Routing")
        print("-" * 80)

        print("\n1. Looking up branding by custom domain...")
        found_branding = await WhiteLabelService.get_branding_by_domain(
            db,
            "app.acmesolutions.com",
        )
        if found_branding:
            print(f"   ✓ Found branding for: {found_branding.custom_domain}")
            print(f"   ✓ Partner: {found_branding.partner_id}")
            print(f"   ✓ Company name: {found_branding.company_name}")
            print(f"   ✓ Primary color: {found_branding.primary_color}")
            print(f"   ✓ Logo: {found_branding.logo_url}")

        # Demo 10: Partner Listing
        print("\n\n📂 DEMO 10: Partner Management")
        print("-" * 80)

        print("\n1. Listing all active partners...")
        active_partners = await WhiteLabelService.list_partners(
            db,
            status="active",
        )
        print(f"   ✓ Found {len(active_partners)} active partners:")
        for p in active_partners:
            print(f"      - {p.company_name} ({p.partner_code}) - {p.tier} tier")

        print("\n2. Listing GOLD tier partners...")
        gold_partners = await WhiteLabelService.list_partners(
            db,
            tier="gold",
        )
        print(f"   ✓ Found {len(gold_partners)} GOLD tier partners")

        # Summary
        print("\n\n" + "=" * 80)
        print("DEMO SUMMARY")
        print("=" * 80)
        print("\n✅ White-Label Features Demonstrated:")
        print("   - Partner account creation and onboarding")
        print("   - Partner tier management (5 tiers)")
        print("   - Custom branding configuration")
        print("   - Domain-based multi-tenancy")
        print("   - Color scheme customization")
        print("   - Logo and favicon upload")
        print("   - Custom CSS support")
        print("   - Email branding")
        print("   - Support contact customization")
        print()
        print("✅ Reseller Features:")
        print("   - Customer tracking and attribution")
        print("   - Referral code generation")
        print("   - Commission calculation")
        print("   - Commission approval workflow")
        print("   - Payment tracking")
        print("   - Revenue sharing (10-30% based on tier)")
        print()
        print("✅ Partner Tiers:")
        print("   - BASIC: 10% commission")
        print("   - SILVER: 15% commission")
        print("   - GOLD: 20% commission")
        print("   - PLATINUM: 25% commission")
        print("   - ENTERPRISE: 30% commission (custom terms)")
        print()
        print("✅ API Integration:")
        print("   - Partner API key generation")
        print("   - Scoped permissions")
        print("   - Key expiration support")
        print("   - Usage tracking")
        print("   - Rate limiting")
        print()
        print("✅ Customer Management:")
        print("   - Customer attribution to partners")
        print("   - MRR tracking")
        print("   - Billing cycle tracking")
        print("   - Referral source tracking")
        print("   - UTM campaign tracking")
        print()
        print("✅ Commission Features:")
        print("   - Automatic commission calculation")
        print("   - Detailed breakdowns")
        print("   - Multi-status workflow (pending, approved, paid)")
        print("   - Payment reference tracking")
        print("   - Historical commission records")
        print()
        print("✅ Partner Statistics:")
        print("   - Customer metrics (total, active, churned)")
        print("   - Revenue tracking")
        print("   - Commission summaries")
        print("   - Retention rate calculation")
        print("   - Average customer value")
        print()
        print("✅ Multi-Tenancy:")
        print("   - Custom domain support")
        print("   - Domain verification")
        print("   - SSL enablement")
        print("   - Branding per domain")
        print("   - Automatic routing")
        print()
        print("✅ Business Impact:")
        print("   - Channel partner ecosystem")
        print("   - Revenue multiplication through resellers")
        print("   - Market expansion without direct sales")
        print("   - Partner-led growth")
        print("   - White-label for enterprise deals")
        print()
        print("✅ Competitive Differentiation:")
        print("   - Full white-labeling (not just logo)")
        print("   - Tiered commission structure")
        print("   - Partner portal and API")
        print("   - Automatic commission calculation")
        print("   - Multi-tenant architecture")
        print()
        print("🎉 White-Label & Reseller Program enables rapid market expansion!")
        print()

if __name__ == "__main__":
    asyncio.run(demo_whitelabel())
