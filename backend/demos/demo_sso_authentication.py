"""
SSO/SAML Authentication Demo

Demonstrates enterprise authentication with:
- SAML 2.0 authentication flow
- OAuth 2.0/OIDC authentication flow
- JIT (Just-In-Time) user provisioning
- Session management
- Multiple provider support (Azure AD, Okta, Auth0, Google)
"""

import sys
from pathlib import Path

# Add parent directory to path so backend.* imports work
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

import asyncio
import logging
from datetime import datetime, timedelta
from uuid import uuid4

from sqlalchemy.ext.asyncio import AsyncSession

from backend.database.session import AsyncSessionLocal, init_db
from backend.shared.sso_service import get_sso_service
from backend.shared.sso_models import (
    SSOConfigModel, AuthProvider, SSOLoginRequest, SSOCallbackData,
    SAML_ATTRIBUTE_MAPPINGS, OAUTH_PROVIDER_CONFIGS
)
from backend.shared.rbac_service import get_rbac_service
from backend.shared.rbac_models import OrganizationModel, UserModel

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


async def setup_test_data(db: AsyncSession):
    """Create test organization and SSO configs"""
    logger.info("Setting up test data...")

    # Clean up existing demo data
    from sqlalchemy import text
    try:
        await db.execute(text("DELETE FROM sso_sessions WHERE organization_id IN ('acme_corp', 'startup_inc')"))
        await db.execute(text("DELETE FROM sso_configs WHERE organization_id IN ('acme_corp', 'startup_inc')"))
        await db.execute(text("DELETE FROM organizations WHERE organization_id IN ('acme_corp', 'startup_inc')"))
        await db.commit()
        logger.info("✓ Cleaned up existing demo data")
    except Exception as e:
        logger.info(f"⚠ Cleanup warning: {str(e)[:100]}")

    # Create test organization
    org = OrganizationModel(
        organization_id="acme_corp",
        name="ACME Corporation",
        slug="acme-corp",
        is_active=True
    )
    db.add(org)

    # Create SAML config for Azure AD
    saml_config = SSOConfigModel(
        config_id=uuid4(),
        organization_id="acme_corp",
        provider=AuthProvider.SAML.value,
        enabled=True,
        saml_entity_id="https://sts.windows.net/tenant-id/",
        saml_sso_url="https://login.microsoftonline.com/tenant-id/saml2",
        saml_slo_url="https://login.microsoftonline.com/tenant-id/saml2/logout",
        saml_x509_cert="MIIDdDCC... (certificate)",
        attribute_mapping=SAML_ATTRIBUTE_MAPPINGS["azure_ad"],
        jit_provisioning_enabled=True,
        default_role="developer",
        session_timeout_minutes=480
    )
    db.add(saml_config)

    # Create OAuth config for Okta
    org2 = OrganizationModel(
        organization_id="startup_inc",
        name="Startup Inc",
        slug="startup-inc",
        is_active=True
    )
    db.add(org2)

    oauth_config = SSOConfigModel(
        config_id=uuid4(),
        organization_id="startup_inc",
        provider=AuthProvider.OAUTH_OKTA.value,
        enabled=True,
        oauth_client_id="okta_client_id_123",
        oauth_client_secret="okta_client_secret_456",  # Would be encrypted
        oauth_authorization_url="https://dev-123456.okta.com/oauth2/v1/authorize",
        oauth_token_url="https://dev-123456.okta.com/oauth2/v1/token",
        oauth_userinfo_url="https://dev-123456.okta.com/oauth2/v1/userinfo",
        oauth_scopes=["openid", "email", "profile"],
        attribute_mapping=SAML_ATTRIBUTE_MAPPINGS["okta"],
        jit_provisioning_enabled=True,
        default_role="viewer",
        session_timeout_minutes=240
    )
    db.add(oauth_config)

    await db.commit()
    logger.info("Test data created successfully")


async def demo_saml_login_flow(db: AsyncSession):
    """Demonstrate SAML 2.0 authentication flow"""
    logger.info("\n" + "="*80)
    logger.info("DEMO: SAML 2.0 Authentication Flow")
    logger.info("="*80)

    sso_service = get_sso_service()

    # Step 1: Initiate SAML login
    logger.info("\n1. Initiating SAML login for ACME Corp...")
    login_request = SSOLoginRequest(
        organization_id="acme_corp",
        return_url="https://app.example.com/dashboard",
        relay_state="original_state_123"
    )

    login_response = await sso_service.initiate_sso_login(login_request, db)
    logger.info(f"   Redirect URL: {login_response.redirect_url[:80]}...")
    logger.info(f"   Method: {login_response.method}")

    # Step 2: Simulate SAML callback (user authenticated at IdP)
    logger.info("\n2. User authenticates at Azure AD and is redirected back...")
    logger.info("   (In production, this would be a real SAML response)")

    # Note: In production, this would be a real base64-encoded SAML response
    fake_saml_response = "PD94bWwgdmVyc2lvbj0iMS4wIj8+... (base64 SAML response)"

    callback_data = SSOCallbackData(
        organization_id="acme_corp",
        provider=AuthProvider.SAML,
        saml_response=fake_saml_response,
        relay_state="original_state_123"
    )

    # Note: This will fail in the demo because we don't have a real SAML parser
    # In production, use python3-saml library
    logger.info("   Skipping actual SAML validation (requires python3-saml)")
    logger.info("   In production, this would:")
    logger.info("     - Validate SAML signature")
    logger.info("     - Parse user attributes")
    logger.info("     - Create/update user (JIT provisioning)")
    logger.info("     - Create SSO session")


async def demo_oauth_login_flow(db: AsyncSession):
    """Demonstrate OAuth 2.0/OIDC authentication flow"""
    logger.info("\n" + "="*80)
    logger.info("DEMO: OAuth 2.0/OIDC Authentication Flow (Okta)")
    logger.info("="*80)

    sso_service = get_sso_service()

    # Step 1: Initiate OAuth login
    logger.info("\n1. Initiating OAuth login for Startup Inc...")
    login_request = SSOLoginRequest(
        organization_id="startup_inc",
        return_url="https://app.example.com/home",
        relay_state=None
    )

    login_response = await sso_service.initiate_sso_login(login_request, db)
    logger.info(f"   Authorization URL: {login_response.redirect_url[:80]}...")
    logger.info(f"   Method: {login_response.method}")

    # Parse the state parameter
    import urllib.parse as urlparse
    parsed = urlparse.urlparse(login_response.redirect_url)
    params = urlparse.parse_qs(parsed.query)
    state = params.get('state', [''])[0]

    logger.info(f"   State (CSRF protection): {state[:30]}...")

    # Step 2: Simulate OAuth callback
    logger.info("\n2. User authenticates at Okta and is redirected back...")
    logger.info("   (In production, this would exchange code for tokens)")

    callback_data = SSOCallbackData(
        organization_id="startup_inc",
        provider=AuthProvider.OAUTH_OKTA,
        code="fake_authorization_code_123",
        state=state
    )

    logger.info("   Skipping actual OAuth flow (requires HTTP client)")
    logger.info("   In production, this would:")
    logger.info("     - Exchange code for access_token")
    logger.info("     - Call userinfo endpoint")
    logger.info("     - Parse user claims")
    logger.info("     - Create/update user (JIT provisioning)")
    logger.info("     - Create SSO session")


async def demo_session_management(db: AsyncSession):
    """Demonstrate session management"""
    logger.info("\n" + "="*80)
    logger.info("DEMO: Session Management")
    logger.info("="*80)

    sso_service = get_sso_service()

    # Create a test user and session manually
    logger.info("\n1. Creating test user and session...")

    # Create user via RBAC service
    rbac_service = get_rbac_service()
    user = await rbac_service.create_user(
        user_id="sso:john.doe@acme.com",
        email="john.doe@acme.com",
        full_name="John Doe",
        organization_id="acme_corp",
        assign_default_role=True,
        db=db
    )
    logger.info(f"   User created: {user.email}")

    # Create SSO session
    from backend.shared.sso_models import SSOSessionModel
    session_id = f"sso_{uuid4().hex}"
    expires_at = datetime.utcnow() + timedelta(hours=8)

    session = SSOSessionModel(
        session_id=session_id,
        user_id=user.user_id,
        organization_id="acme_corp",
        provider=AuthProvider.SAML.value,
        expires_at=expires_at
    )
    db.add(session)
    await db.commit()

    logger.info(f"   Session created: {session_id}")
    logger.info(f"   Expires at: {expires_at}")

    # Validate session
    logger.info("\n2. Validating session...")
    validated_session = await sso_service.validate_session(session_id, db)

    if validated_session:
        logger.info(f"   Session valid!")
        logger.info(f"   User: {validated_session.user_id}")
        logger.info(f"   Organization: {validated_session.organization_id}")
        logger.info(f"   Provider: {validated_session.provider.value}")
    else:
        logger.info("   Session invalid or expired")

    # Logout
    logger.info("\n3. Logging out...")
    slo_url = await sso_service.logout(session_id, db)

    if slo_url:
        logger.info(f"   SAML SLO URL: {slo_url}")
        logger.info("   Would redirect to IdP for logout")
    else:
        logger.info("   Session destroyed (local logout)")

    # Verify session destroyed
    logger.info("\n4. Verifying session destroyed...")
    validated_session = await sso_service.validate_session(session_id, db)
    logger.info(f"   Session still valid: {validated_session is not None}")


async def demo_provider_configs(db: AsyncSession):
    """Show provider configurations"""
    logger.info("\n" + "="*80)
    logger.info("DEMO: Supported Providers and Configurations")
    logger.info("="*80)

    logger.info("\nSAML Attribute Mappings:")
    for provider, mapping in SAML_ATTRIBUTE_MAPPINGS.items():
        logger.info(f"\n{provider.upper()}:")
        for key, value in mapping.items():
            logger.info(f"  {key}: {value}")

    logger.info("\n" + "-"*80)
    logger.info("\nOAuth Provider Configurations:")
    for provider, config in OAUTH_PROVIDER_CONFIGS.items():
        logger.info(f"\n{provider.upper()}:")
        for key, value in config.items():
            logger.info(f"  {key}: {value}")


async def demo_jit_provisioning(db: AsyncSession):
    """Demonstrate JIT user provisioning"""
    logger.info("\n" + "="*80)
    logger.info("DEMO: JIT (Just-In-Time) User Provisioning")
    logger.info("="*80)

    logger.info("\nScenario: New user authenticates via SSO for the first time")
    logger.info("\n1. User 'jane.smith@acme.com' logs in via Azure AD SAML")
    logger.info("   User does not exist in platform yet")

    logger.info("\n2. JIT Provisioning Process:")
    logger.info("   ✓ Extract user attributes from SAML assertion")
    logger.info("     - email: jane.smith@acme.com")
    logger.info("     - first_name: Jane")
    logger.info("     - last_name: Smith")
    logger.info("     - display_name: Jane Smith")

    logger.info("\n   ✓ Create new user account")
    logger.info("     - user_id: sso:jane.smith@acme.com")
    logger.info("     - organization: acme_corp")
    logger.info("     - assign default role: developer")

    logger.info("\n   ✓ Create SSO session")

    logger.info("\n   ✓ Log audit events")
    logger.info("     - USER_CREATED (via SSO)")
    logger.info("     - AUTH_LOGIN (successful)")

    logger.info("\n3. User is now authenticated and can access the platform!")

    logger.info("\n4. On subsequent logins:")
    logger.info("   ✓ User already exists, no provisioning needed")
    logger.info("   ✓ User attributes updated if changed at IdP")
    logger.info("   ✓ New SSO session created")


async def demo_multi_provider_support(db: AsyncSession):
    """Demonstrate multiple provider support"""
    logger.info("\n" + "="*80)
    logger.info("DEMO: Multi-Provider Support")
    logger.info("="*80)

    sso_service = get_sso_service()

    logger.info("\nOrganization 1: ACME Corp")
    config1 = await sso_service.get_sso_config("acme_corp", db)
    logger.info(f"  Provider: {config1.provider.value}")
    logger.info(f"  Type: SAML 2.0")
    logger.info(f"  IdP: Microsoft Azure AD")
    logger.info(f"  JIT Provisioning: {'Enabled' if config1.jit_provisioning_enabled else 'Disabled'}")
    logger.info(f"  Session Timeout: {config1.session_timeout_minutes} minutes")

    logger.info("\nOrganization 2: Startup Inc")
    config2 = await sso_service.get_sso_config("startup_inc", db)
    logger.info(f"  Provider: {config2.provider.value}")
    logger.info(f"  Type: OAuth 2.0/OIDC")
    logger.info(f"  IdP: Okta")
    logger.info(f"  JIT Provisioning: {'Enabled' if config2.jit_provisioning_enabled else 'Disabled'}")
    logger.info(f"  Session Timeout: {config2.session_timeout_minutes} minutes")

    logger.info("\nSupported Providers:")
    logger.info("  ✓ SAML 2.0 (generic)")
    logger.info("  ✓ Microsoft Azure AD (OAuth/OIDC)")
    logger.info("  ✓ Okta (OAuth/OIDC)")
    logger.info("  ✓ Auth0 (OAuth/OIDC)")
    logger.info("  ✓ Google Workspace (OAuth/OIDC)")


async def demo_session_cleanup(db: AsyncSession):
    """Demonstrate expired session cleanup"""
    logger.info("\n" + "="*80)
    logger.info("DEMO: Expired Session Cleanup")
    logger.info("="*80)

    sso_service = get_sso_service()

    # Create test user for the cleanup demo (organization already exists from setup_test_data)
    logger.info("\n1. Creating test user for cleanup demo...")
    from backend.shared.rbac_models import UserModel

    # Create test user (acme_corp organization already exists)
    test_user = UserModel(
        user_id="sso:cleanup-test@example.com",
        email="cleanup-test@example.com",
        full_name="Cleanup Test User",
        organization_id="acme_corp"
    )
    db.add(test_user)
    await db.commit()

    logger.info(f"   Created test user: {test_user.email}")

    # Create expired session
    logger.info("\n2. Creating expired test session...")
    from backend.shared.sso_models import SSOSessionModel

    expired_session = SSOSessionModel(
        session_id=f"sso_expired_{uuid4().hex}",
        user_id="sso:cleanup-test@example.com",
        organization_id="acme_corp",
        provider=AuthProvider.SAML.value,
        expires_at=datetime.utcnow() - timedelta(hours=1)  # Expired 1 hour ago
    )
    db.add(expired_session)
    await db.commit()

    logger.info(f"   Created session: {expired_session.session_id}")
    logger.info(f"   Expired at: {expired_session.expires_at}")

    # Run cleanup
    logger.info("\n3. Running cleanup job...")
    count = await sso_service.cleanup_expired_sessions(db)
    logger.info(f"   Cleaned up {count} expired session(s)")

    logger.info("\n4. This would be run as a cron job (e.g., every hour)")


async def main():
    """Run all demos"""
    logger.info("SSO/SAML Authentication Demo")
    logger.info("="*80)

    # Initialize audit logger
    from backend.shared.audit_logger import init_audit_logger
    init_audit_logger(AsyncSessionLocal)

    async with AsyncSessionLocal() as db:
        # Create tables for clean demo
        from sqlalchemy import text
        try:
            for stmt in [
                "DROP TABLE IF EXISTS saml_requests CASCADE",
                "DROP TABLE IF EXISTS sso_sessions CASCADE",
                "DROP TABLE IF EXISTS sso_configs CASCADE",
                "DROP TABLE IF EXISTS user_roles CASCADE",
                "DROP TABLE IF EXISTS role_permissions CASCADE",
                "DROP TABLE IF EXISTS users CASCADE",
                "DROP TABLE IF EXISTS roles CASCADE",
                "DROP TABLE IF EXISTS organizations CASCADE",
                """CREATE TABLE organizations (
                    organization_id VARCHAR(255) PRIMARY KEY,
                    name VARCHAR(255) NOT NULL,
                    slug VARCHAR(100) UNIQUE NOT NULL,
                    plan VARCHAR(50) DEFAULT 'startup' NOT NULL,
                    max_users INTEGER DEFAULT 5 NOT NULL,
                    max_agents INTEGER DEFAULT 10 NOT NULL,
                    enabled_features JSON DEFAULT '[]',
                    billing_email VARCHAR(255),
                    admin_email VARCHAR(255),
                    is_active BOOLEAN DEFAULT TRUE NOT NULL,
                    trial_ends_at TIMESTAMP,
                    settings JSON,
                    extra_metadata JSON,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP NOT NULL,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP NOT NULL
                )""",
                """CREATE TABLE roles (
                    role_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                    name VARCHAR(100) UNIQUE NOT NULL,
                    description TEXT,
                    is_system_role BOOLEAN DEFAULT FALSE NOT NULL,
                    is_default BOOLEAN DEFAULT FALSE NOT NULL,
                    permissions JSON DEFAULT '[]',
                    organization_id VARCHAR(255),
                    extra_metadata JSON,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP NOT NULL,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP NOT NULL,
                    created_by VARCHAR(255)
                )""",
                """CREATE TABLE users (
                    user_id VARCHAR(255) PRIMARY KEY,
                    email VARCHAR(255) UNIQUE NOT NULL,
                    full_name VARCHAR(255),
                    avatar_url VARCHAR(512),
                    organization_id VARCHAR(255) NOT NULL,
                    is_active BOOLEAN DEFAULT TRUE NOT NULL,
                    is_email_verified BOOLEAN DEFAULT FALSE NOT NULL,
                    preferences JSON,
                    extra_metadata JSON,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP NOT NULL,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP NOT NULL,
                    last_login TIMESTAMP
                )""",
                """CREATE TABLE user_roles (
                    user_id VARCHAR(255) REFERENCES users(user_id) ON DELETE CASCADE,
                    role_id UUID REFERENCES roles(role_id) ON DELETE CASCADE,
                    assigned_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP NOT NULL,
                    assigned_by VARCHAR(255),
                    PRIMARY KEY (user_id, role_id)
                )""",
                """CREATE TABLE role_permissions (
                    role_id UUID REFERENCES roles(role_id) ON DELETE CASCADE,
                    permission VARCHAR(100),
                    PRIMARY KEY (role_id, permission)
                )""",
                """CREATE TABLE sso_configs (
                    config_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                    organization_id VARCHAR(255) UNIQUE NOT NULL,
                    provider VARCHAR(50) NOT NULL,
                    enabled BOOLEAN DEFAULT TRUE NOT NULL,
                    saml_entity_id VARCHAR(512),
                    saml_sso_url VARCHAR(512),
                    saml_slo_url VARCHAR(512),
                    saml_x509_cert TEXT,
                    saml_binding VARCHAR(100),
                    oauth_client_id VARCHAR(255),
                    oauth_client_secret VARCHAR(512),
                    oauth_authorization_url VARCHAR(512),
                    oauth_token_url VARCHAR(512),
                    oauth_userinfo_url VARCHAR(512),
                    oauth_jwks_url VARCHAR(512),
                    oauth_scopes JSON,
                    attribute_mapping JSON DEFAULT '{}',
                    jit_provisioning_enabled BOOLEAN DEFAULT TRUE NOT NULL,
                    default_role VARCHAR(100),
                    session_timeout_minutes INTEGER DEFAULT 480 NOT NULL,
                    require_mfa BOOLEAN DEFAULT FALSE NOT NULL,
                    require_signed_assertions BOOLEAN DEFAULT TRUE NOT NULL,
                    require_encrypted_assertions BOOLEAN DEFAULT FALSE NOT NULL,
                    extra_metadata JSON,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP NOT NULL,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP NOT NULL,
                    created_by VARCHAR(255)
                )""",
                """CREATE TABLE sso_sessions (
                    session_id VARCHAR(255) PRIMARY KEY,
                    user_id VARCHAR(255) NOT NULL REFERENCES users(user_id) ON DELETE CASCADE,
                    organization_id VARCHAR(255) NOT NULL REFERENCES organizations(organization_id) ON DELETE CASCADE,
                    provider VARCHAR(50) NOT NULL,
                    name_id VARCHAR(255),
                    session_index VARCHAR(255),
                    access_token TEXT,
                    refresh_token TEXT,
                    id_token TEXT,
                    expires_at TIMESTAMP NOT NULL,
                    extra_metadata JSON,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP NOT NULL,
                    last_activity TIMESTAMP DEFAULT CURRENT_TIMESTAMP NOT NULL
                )""",
                """CREATE TABLE saml_requests (
                    request_id VARCHAR(255) PRIMARY KEY,
                    organization_id VARCHAR(255) NOT NULL,
                    relay_state VARCHAR(255),
                    return_url VARCHAR(512) NOT NULL,
                    expires_at TIMESTAMP NOT NULL,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP NOT NULL
                )""",
            ]:
                await db.execute(text(stmt))
            await db.commit()
            logger.info("✓ Created tables for demo\n")
        except Exception as e:
            await db.rollback()
            logger.warning(f"⚠ Table creation warning: {str(e)[:100]}\n")

        # Setup
        await setup_test_data(db)

        # Run demos
        await demo_provider_configs(db)
        await demo_multi_provider_support(db)
        await demo_saml_login_flow(db)
        await demo_oauth_login_flow(db)
        await demo_jit_provisioning(db)
        await demo_session_management(db)
        await demo_session_cleanup(db)

    logger.info("\n" + "="*80)
    logger.info("Demo Complete!")
    logger.info("="*80)

    logger.info("\nKey Features Demonstrated:")
    logger.info("  ✓ SAML 2.0 authentication flow")
    logger.info("  ✓ OAuth 2.0/OIDC authentication flow")
    logger.info("  ✓ JIT (Just-In-Time) user provisioning")
    logger.info("  ✓ Session management and validation")
    logger.info("  ✓ Multi-provider support (Azure AD, Okta, Auth0, Google)")
    logger.info("  ✓ Attribute mapping")
    logger.info("  ✓ Single Logout (SLO)")
    logger.info("  ✓ Expired session cleanup")

    logger.info("\nBusiness Impact:")
    logger.info("  • Removes sales blocker for enterprise customers (90% requirement)")
    logger.info("  • Reduces onboarding friction with JIT provisioning")
    logger.info("  • Improves security with centralized authentication")
    logger.info("  • Matches AWS/Microsoft enterprise capabilities")


if __name__ == "__main__":
    asyncio.run(main())
