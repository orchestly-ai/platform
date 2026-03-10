"""add sso saml authentication

Revision ID: 20251217_1100
Revises: 20251217_1000
Create Date: 2025-12-17 11:00:00.000000

Enterprise SSO/SAML authentication system.
Addresses sales blocker for enterprise deals (90% customer requirement).
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql
from datetime import datetime

# revision identifiers, used by Alembic.
revision = '20251217_1100'
down_revision = '20251217_1000'
branch_labels = None
depends_on = None


def upgrade():
    """Create SSO/SAML authentication tables"""

    # Create sso_configs table
    op.create_table(
        'sso_configs',
        sa.Column('config_id', postgresql.UUID(as_uuid=True), primary_key=True),

        # Organization
        sa.Column('organization_id', sa.String(255), nullable=False, unique=True),

        # Provider
        sa.Column('provider', sa.String(50), nullable=False),
        sa.Column('enabled', sa.Boolean(), nullable=False, default=True),

        # SAML Configuration
        sa.Column('saml_entity_id', sa.String(512), nullable=True),
        sa.Column('saml_sso_url', sa.String(512), nullable=True),
        sa.Column('saml_slo_url', sa.String(512), nullable=True),
        sa.Column('saml_x509_cert', sa.Text(), nullable=True),
        sa.Column('saml_binding', sa.String(100), nullable=True),

        # OAuth 2.0 / OIDC Configuration
        sa.Column('oauth_client_id', sa.String(255), nullable=True),
        sa.Column('oauth_client_secret', sa.String(512), nullable=True),  # Encrypted
        sa.Column('oauth_authorization_url', sa.String(512), nullable=True),
        sa.Column('oauth_token_url', sa.String(512), nullable=True),
        sa.Column('oauth_userinfo_url', sa.String(512), nullable=True),
        sa.Column('oauth_jwks_url', sa.String(512), nullable=True),
        sa.Column('oauth_scopes', postgresql.JSON(astext_type=sa.Text()), nullable=True),

        # Attribute Mapping
        sa.Column('attribute_mapping', postgresql.JSON(astext_type=sa.Text()), nullable=False, default=dict),

        # JIT User Provisioning
        sa.Column('jit_provisioning_enabled', sa.Boolean(), nullable=False, default=True),
        sa.Column('default_role', sa.String(100), nullable=True),

        # Session Settings
        sa.Column('session_timeout_minutes', sa.Integer(), nullable=False, default=480),
        sa.Column('require_mfa', sa.Boolean(), nullable=False, default=False),

        # Security
        sa.Column('require_signed_assertions', sa.Boolean(), nullable=False, default=True),
        sa.Column('require_encrypted_assertions', sa.Boolean(), nullable=False, default=False),

        # Metadata
        sa.Column('metadata', postgresql.JSON(astext_type=sa.Text()), nullable=True),

        # Timestamps
        sa.Column('created_at', sa.DateTime(), nullable=False, default=datetime.utcnow),
        sa.Column('updated_at', sa.DateTime(), nullable=False, default=datetime.utcnow),
        sa.Column('created_by', sa.String(255), nullable=True),

        # Foreign keys
        sa.ForeignKeyConstraint(['organization_id'], ['organizations.organization_id'], ondelete='CASCADE')
    )

    # Indexes for sso_configs
    op.create_index('idx_sso_org', 'sso_configs', ['organization_id'])
    op.create_index('idx_sso_enabled', 'sso_configs', ['enabled'])

    # Create sso_sessions table
    op.create_table(
        'sso_sessions',
        sa.Column('session_id', sa.String(255), primary_key=True),

        # User
        sa.Column('user_id', sa.String(255), nullable=False),
        sa.Column('organization_id', sa.String(255), nullable=False),

        # Provider
        sa.Column('provider', sa.String(50), nullable=False),

        # Session data
        sa.Column('name_id', sa.String(255), nullable=True),
        sa.Column('session_index', sa.String(255), nullable=True),

        # Tokens (for OAuth/OIDC)
        sa.Column('access_token', sa.Text(), nullable=True),  # Encrypted
        sa.Column('refresh_token', sa.Text(), nullable=True),  # Encrypted
        sa.Column('id_token', sa.Text(), nullable=True),  # JWT

        # Expiration
        sa.Column('expires_at', sa.DateTime(), nullable=False),

        # Metadata
        sa.Column('metadata', postgresql.JSON(astext_type=sa.Text()), nullable=True),

        # Timestamps
        sa.Column('created_at', sa.DateTime(), nullable=False, default=datetime.utcnow),
        sa.Column('last_activity', sa.DateTime(), nullable=False, default=datetime.utcnow),

        # Foreign keys
        sa.ForeignKeyConstraint(['user_id'], ['users.user_id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['organization_id'], ['organizations.organization_id'], ondelete='CASCADE')
    )

    # Indexes for sso_sessions
    op.create_index('idx_sso_session_user', 'sso_sessions', ['user_id'])
    op.create_index('idx_sso_session_org', 'sso_sessions', ['organization_id'])
    op.create_index('idx_sso_session_expires', 'sso_sessions', ['expires_at'])

    # Create saml_requests table
    op.create_table(
        'saml_requests',
        sa.Column('request_id', sa.String(255), primary_key=True),

        # Organization
        sa.Column('organization_id', sa.String(255), nullable=False),

        # Request data
        sa.Column('relay_state', sa.String(255), nullable=True),
        sa.Column('return_url', sa.String(512), nullable=False),

        # Expiration (requests expire after 5 minutes)
        sa.Column('expires_at', sa.DateTime(), nullable=False),

        # Timestamps
        sa.Column('created_at', sa.DateTime(), nullable=False, default=datetime.utcnow),

        # Foreign keys
        sa.ForeignKeyConstraint(['organization_id'], ['organizations.organization_id'], ondelete='CASCADE')
    )

    # Indexes for saml_requests
    op.create_index('idx_saml_request_org', 'saml_requests', ['organization_id'])
    op.create_index('idx_saml_request_expires', 'saml_requests', ['expires_at'])


def downgrade():
    """Drop SSO/SAML authentication tables"""
    op.drop_table('saml_requests')
    op.drop_table('sso_sessions')
    op.drop_table('sso_configs')
