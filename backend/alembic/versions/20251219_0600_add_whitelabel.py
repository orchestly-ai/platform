"""add whitelabel reseller

Revision ID: 20251219_0600
Revises: 20251219_0500
Create Date: 2025-12-19 06:00:00.000000

P2 Feature #4: White-Label & Reseller Program
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = '20251219_0600'
down_revision = '20251219_0500'

def upgrade() -> None:
    # Create ENUM types
    op.execute("CREATE TYPE partnertier AS ENUM ('basic', 'silver', 'gold', 'platinum', 'enterprise')")
    op.execute("CREATE TYPE partnerstatus AS ENUM ('pending', 'active', 'suspended', 'terminated')")
    op.execute("CREATE TYPE brandingstatus AS ENUM ('draft', 'pending_review', 'approved', 'rejected')")
    op.execute("CREATE TYPE commissionstatus AS ENUM ('pending', 'approved', 'paid', 'disputed')")
    op.execute("CREATE TYPE billingcycle AS ENUM ('monthly', 'quarterly', 'annual')")

    # Partners table
    op.execute("""
    CREATE TABLE partners (
        id SERIAL PRIMARY KEY,
        company_name VARCHAR(255) NOT NULL,
        partner_code VARCHAR(50) UNIQUE NOT NULL,
        primary_contact_name VARCHAR(255) NOT NULL,
        primary_contact_email VARCHAR(255) NOT NULL,
        primary_contact_phone VARCHAR(50),
        address_line1 VARCHAR(255),
        address_line2 VARCHAR(255),
        city VARCHAR(100),
        state VARCHAR(100),
        postal_code VARCHAR(20),
        country VARCHAR(100),
        tax_id VARCHAR(100),
        business_type VARCHAR(100),
        website VARCHAR(500),
        tier partnertier DEFAULT 'basic' NOT NULL,
        status partnerstatus DEFAULT 'pending' NOT NULL,
        commission_rate FLOAT DEFAULT 10.0 NOT NULL,
        custom_commission_rules JSON DEFAULT '{}',
        billing_email VARCHAR(255),
        payment_method VARCHAR(50),
        payment_details JSON DEFAULT '{}',
        referral_code VARCHAR(50) UNIQUE,
        total_customers INTEGER DEFAULT 0,
        total_revenue_usd NUMERIC(20, 2) DEFAULT 0.0,
        total_commission_usd NUMERIC(20, 2) DEFAULT 0.0,
        contract_start_date TIMESTAMP,
        contract_end_date TIMESTAMP,
        terms_accepted_at TIMESTAMP,
        created_at TIMESTAMP DEFAULT now() NOT NULL,
        updated_at TIMESTAMP DEFAULT now(),
        activated_at TIMESTAMP,
        suspended_at TIMESTAMP
    )
    """)
    op.execute("CREATE INDEX ix_partner_company ON partners(company_name)")
    op.execute("CREATE INDEX ix_partner_code ON partners(partner_code)")
    op.execute("CREATE INDEX ix_partner_email ON partners(primary_contact_email)")
    op.execute("CREATE INDEX ix_partner_referral ON partners(referral_code)")
    op.execute("CREATE INDEX ix_partner_tier ON partners(tier)")
    op.execute("CREATE INDEX ix_partner_status ON partners(status)")
    op.execute("CREATE INDEX ix_partner_created ON partners(created_at)")
    op.execute("CREATE INDEX ix_partner_tier_status ON partners(tier, status)")

    # White Label Branding table
    op.execute("""
    CREATE TABLE whitelabel_branding (
        id SERIAL PRIMARY KEY,
        partner_id INTEGER NOT NULL REFERENCES partners(id) ON DELETE CASCADE,
        custom_domain VARCHAR(255) UNIQUE,
        domain_verified BOOLEAN DEFAULT FALSE NOT NULL,
        ssl_enabled BOOLEAN DEFAULT FALSE NOT NULL,
        company_name VARCHAR(255) NOT NULL,
        logo_url VARCHAR(500),
        favicon_url VARCHAR(500),
        primary_color VARCHAR(7),
        secondary_color VARCHAR(7),
        accent_color VARCHAR(7),
        background_color VARCHAR(7),
        text_color VARCHAR(7),
        custom_css TEXT,
        email_from_name VARCHAR(255),
        email_from_address VARCHAR(255),
        email_logo_url VARCHAR(500),
        email_footer TEXT,
        support_email VARCHAR(255),
        support_phone VARCHAR(50),
        support_url VARCHAR(500),
        privacy_policy_url VARCHAR(500),
        terms_of_service_url VARCHAR(500),
        social_links JSON DEFAULT '{}',
        status brandingstatus DEFAULT 'draft' NOT NULL,
        is_active BOOLEAN DEFAULT FALSE NOT NULL,
        metadata JSON DEFAULT '{}',
        created_at TIMESTAMP DEFAULT now() NOT NULL,
        updated_at TIMESTAMP DEFAULT now(),
        approved_at TIMESTAMP,
        approved_by VARCHAR(255)
    )
    """)
    op.execute("CREATE INDEX ix_branding_partner ON whitelabel_branding(partner_id)")
    op.execute("CREATE INDEX ix_branding_domain ON whitelabel_branding(custom_domain)")
    op.execute("CREATE INDEX ix_branding_status ON whitelabel_branding(status)")
    op.execute("CREATE INDEX ix_branding_active ON whitelabel_branding(is_active)")
    op.execute("CREATE INDEX ix_branding_partner_status ON whitelabel_branding(partner_id, status)")

    # Partner Customers table
    op.execute("""
    CREATE TABLE partner_customers (
        id SERIAL PRIMARY KEY,
        partner_id INTEGER NOT NULL REFERENCES partners(id) ON DELETE CASCADE,
        customer_email VARCHAR(255) NOT NULL,
        customer_name VARCHAR(255),
        organization_id INTEGER,
        plan_name VARCHAR(100),
        billing_cycle billingcycle,
        mrr_usd NUMERIC(20, 2) DEFAULT 0.0,
        is_active BOOLEAN DEFAULT TRUE NOT NULL,
        referral_source VARCHAR(255),
        utm_campaign VARCHAR(255),
        utm_source VARCHAR(255),
        utm_medium VARCHAR(255),
        created_at TIMESTAMP DEFAULT now() NOT NULL,
        activated_at TIMESTAMP,
        churned_at TIMESTAMP
    )
    """)
    op.execute("CREATE INDEX ix_customer_partner ON partner_customers(partner_id)")
    op.execute("CREATE INDEX ix_customer_email ON partner_customers(customer_email)")
    op.execute("CREATE INDEX ix_customer_org ON partner_customers(organization_id)")
    op.execute("CREATE INDEX ix_customer_active ON partner_customers(is_active)")
    op.execute("CREATE INDEX ix_customer_created ON partner_customers(created_at)")
    op.execute("CREATE INDEX ix_customer_partner_active ON partner_customers(partner_id, is_active)")
    op.execute("CREATE INDEX ix_customer_partner_email ON partner_customers(partner_id, customer_email)")

    # Commissions table
    op.execute("""
    CREATE TABLE commissions (
        id SERIAL PRIMARY KEY,
        partner_id INTEGER NOT NULL REFERENCES partners(id) ON DELETE CASCADE,
        period_start TIMESTAMP NOT NULL,
        period_end TIMESTAMP NOT NULL,
        gross_revenue_usd NUMERIC(20, 2) NOT NULL,
        commission_rate FLOAT NOT NULL,
        commission_amount_usd NUMERIC(20, 2) NOT NULL,
        customer_count INTEGER DEFAULT 0,
        transaction_count INTEGER DEFAULT 0,
        details JSON DEFAULT '{}',
        status commissionstatus DEFAULT 'pending' NOT NULL,
        payment_date TIMESTAMP,
        payment_reference VARCHAR(255),
        payment_method VARCHAR(50),
        notes TEXT,
        created_at TIMESTAMP DEFAULT now() NOT NULL,
        updated_at TIMESTAMP DEFAULT now()
    )
    """)
    op.execute("CREATE INDEX ix_commission_partner ON commissions(partner_id)")
    op.execute("CREATE INDEX ix_commission_period_start ON commissions(period_start)")
    op.execute("CREATE INDEX ix_commission_period_end ON commissions(period_end)")
    op.execute("CREATE INDEX ix_commission_status ON commissions(status)")
    op.execute("CREATE INDEX ix_commission_created ON commissions(created_at)")
    op.execute("CREATE INDEX ix_commission_partner_period ON commissions(partner_id, period_start, period_end)")
    op.execute("CREATE INDEX ix_commission_status_date ON commissions(status, payment_date)")

    # Partner API Keys table
    op.execute("""
    CREATE TABLE partner_api_keys (
        id SERIAL PRIMARY KEY,
        partner_id INTEGER NOT NULL REFERENCES partners(id) ON DELETE CASCADE,
        key_name VARCHAR(255) NOT NULL,
        key_hash VARCHAR(255) UNIQUE NOT NULL,
        key_prefix VARCHAR(20) NOT NULL,
        scopes JSON DEFAULT '[]',
        rate_limit_per_minute INTEGER DEFAULT 60,
        rate_limit_per_hour INTEGER DEFAULT 1000,
        is_active BOOLEAN DEFAULT TRUE NOT NULL,
        last_used_at TIMESTAMP,
        usage_count INTEGER DEFAULT 0,
        created_at TIMESTAMP DEFAULT now() NOT NULL,
        expires_at TIMESTAMP,
        revoked_at TIMESTAMP
    )
    """)
    op.execute("CREATE INDEX ix_api_key_partner ON partner_api_keys(partner_id)")
    op.execute("CREATE INDEX ix_api_key_hash ON partner_api_keys(key_hash)")
    op.execute("CREATE INDEX ix_api_key_active ON partner_api_keys(is_active)")
    op.execute("CREATE INDEX ix_api_key_created ON partner_api_keys(created_at)")
    op.execute("CREATE INDEX ix_api_key_expires ON partner_api_keys(expires_at)")
    op.execute("CREATE INDEX ix_api_key_partner_active ON partner_api_keys(partner_id, is_active)")

    # Partner Resources table
    op.execute("""
    CREATE TABLE partner_resources (
        id SERIAL PRIMARY KEY,
        title VARCHAR(255) NOT NULL,
        description TEXT,
        resource_type VARCHAR(50) NOT NULL,
        file_url VARCHAR(500),
        file_size_bytes INTEGER,
        file_type VARCHAR(50),
        visibility VARCHAR(50) DEFAULT 'all_partners' NOT NULL,
        required_tier partnertier,
        tags JSON DEFAULT '[]',
        category VARCHAR(100),
        download_count INTEGER DEFAULT 0,
        view_count INTEGER DEFAULT 0,
        created_at TIMESTAMP DEFAULT now() NOT NULL,
        updated_at TIMESTAMP DEFAULT now(),
        created_by VARCHAR(255) NOT NULL
    )
    """)
    op.execute("CREATE INDEX ix_resource_title ON partner_resources(title)")
    op.execute("CREATE INDEX ix_resource_type ON partner_resources(resource_type)")
    op.execute("CREATE INDEX ix_resource_created ON partner_resources(created_at)")
    op.execute("CREATE INDEX ix_resource_type_tier ON partner_resources(resource_type, required_tier)")

def downgrade() -> None:
    op.drop_table('partner_resources')
    op.drop_table('partner_api_keys')
    op.drop_table('commissions')
    op.drop_table('partner_customers')
    op.drop_table('whitelabel_branding')
    op.drop_table('partners')
    op.execute('DROP TYPE IF EXISTS partnertier')
    op.execute('DROP TYPE IF EXISTS partnerstatus')
    op.execute('DROP TYPE IF EXISTS brandingstatus')
    op.execute('DROP TYPE IF EXISTS commissionstatus')
    op.execute('DROP TYPE IF EXISTS billingcycle')
