"""add agent marketplace

Revision ID: 20251219_0500
Revises: 20251219_0400
Create Date: 2025-12-19 05:00:00.000000

P2 Feature #3: Agent Marketplace
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = '20251219_0500'
down_revision = '20251219_0400'

def upgrade() -> None:
    # Enum types will be created automatically by SQLAlchemy when tables are created

    # Marketplace Agents table
    op.create_table(
        'marketplace_agents',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('name', sa.String(length=255), nullable=False),
        sa.Column('slug', sa.String(length=255), nullable=False),
        sa.Column('tagline', sa.String(length=500), nullable=False),
        sa.Column('description', sa.Text(), nullable=False),
        sa.Column('publisher_id', sa.String(length=255), nullable=False),
        sa.Column('publisher_name', sa.String(length=255), nullable=False),
        sa.Column('publisher_organization_id', sa.Integer(), nullable=True),
        sa.Column('category', sa.Enum('data_processing', 'customer_service', 'sales_automation', 'marketing', 'hr_recruiting', 'finance_accounting', 'legal', 'engineering', 'analytics', 'integration', 'communication', 'productivity', 'other', name='agentcategory'), nullable=False),
        sa.Column('tags', postgresql.JSON(astext_type=sa.Text()), nullable=True, server_default='[]'),
        sa.Column('visibility', sa.Enum('public', 'private', 'organization', 'unlisted', name='agentvisibility'), nullable=False, server_default='public'),
        sa.Column('pricing', sa.Enum('free', 'freemium', 'paid', 'enterprise', name='agentpricing'), nullable=False, server_default='free'),
        sa.Column('price_usd', sa.Float(), nullable=True),
        sa.Column('agent_config', postgresql.JSON(astext_type=sa.Text()), nullable=False),
        sa.Column('required_integrations', postgresql.JSON(astext_type=sa.Text()), nullable=True, server_default='[]'),
        sa.Column('required_capabilities', postgresql.JSON(astext_type=sa.Text()), nullable=True, server_default='[]'),
        sa.Column('icon_url', sa.String(length=500), nullable=True),
        sa.Column('screenshots', postgresql.JSON(astext_type=sa.Text()), nullable=True, server_default='[]'),
        sa.Column('video_url', sa.String(length=500), nullable=True),
        sa.Column('documentation_url', sa.String(length=500), nullable=True),
        sa.Column('github_url', sa.String(length=500), nullable=True),
        sa.Column('support_url', sa.String(length=500), nullable=True),
        sa.Column('version', sa.String(length=50), nullable=False),
        sa.Column('changelog', sa.Text(), nullable=True),
        sa.Column('is_verified', sa.Boolean(), nullable=False, server_default='false'),
        sa.Column('is_featured', sa.Boolean(), nullable=False, server_default='false'),
        sa.Column('install_count', sa.Integer(), nullable=True, server_default='0'),
        sa.Column('rating_avg', sa.Float(), nullable=True, server_default='0.0'),
        sa.Column('rating_count', sa.Integer(), nullable=True, server_default='0'),
        sa.Column('is_active', sa.Boolean(), nullable=False, server_default='true'),
        sa.Column('is_deprecated', sa.Boolean(), nullable=False, server_default='false'),
        sa.Column('created_at', sa.TIMESTAMP(), nullable=False, server_default=sa.text('now()')),
        sa.Column('updated_at', sa.TIMESTAMP(), nullable=True, server_default=sa.text('now()')),
        sa.Column('published_at', sa.TIMESTAMP(), nullable=True),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('slug')
    )
    op.create_index('ix_marketplace_name', 'marketplace_agents', ['name'])
    op.create_index('ix_marketplace_slug', 'marketplace_agents', ['slug'])
    op.create_index('ix_marketplace_publisher', 'marketplace_agents', ['publisher_id'])
    op.create_index('ix_marketplace_pub_org', 'marketplace_agents', ['publisher_organization_id'])
    op.create_index('ix_marketplace_category', 'marketplace_agents', ['category'])
    op.create_index('ix_marketplace_visibility', 'marketplace_agents', ['visibility'])
    op.create_index('ix_marketplace_pricing', 'marketplace_agents', ['pricing'])
    op.create_index('ix_marketplace_version', 'marketplace_agents', ['version'])
    op.create_index('ix_marketplace_verified', 'marketplace_agents', ['is_verified'])
    op.create_index('ix_marketplace_featured', 'marketplace_agents', ['is_featured'])
    op.create_index('ix_marketplace_installs', 'marketplace_agents', ['install_count'])
    op.create_index('ix_marketplace_rating', 'marketplace_agents', ['rating_avg'])
    op.create_index('ix_marketplace_active', 'marketplace_agents', ['is_active'])
    op.create_index('ix_marketplace_created', 'marketplace_agents', ['created_at'])
    op.create_index('ix_marketplace_published', 'marketplace_agents', ['published_at'])
    op.create_index('ix_marketplace_category_rating', 'marketplace_agents', ['category', 'rating_avg'])
    op.create_index('ix_marketplace_featured_rating', 'marketplace_agents', ['is_featured', 'rating_avg'])
    op.create_index('ix_marketplace_search', 'marketplace_agents', ['name', 'category', 'visibility'])

    # Agent Versions table
    op.create_table(
        'agent_versions',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('agent_id', sa.Integer(), nullable=False),
        sa.Column('version', sa.String(length=50), nullable=False),
        sa.Column('release_notes', sa.Text(), nullable=True),
        sa.Column('agent_config', postgresql.JSON(astext_type=sa.Text()), nullable=False),
        sa.Column('min_platform_version', sa.String(length=50), nullable=True),
        sa.Column('breaking_changes', sa.Boolean(), nullable=False, server_default='false'),
        sa.Column('is_latest', sa.Boolean(), nullable=False, server_default='false'),
        sa.Column('is_stable', sa.Boolean(), nullable=False, server_default='true'),
        sa.Column('created_at', sa.TIMESTAMP(), nullable=False, server_default=sa.text('now()')),
        sa.Column('created_by', sa.String(length=255), nullable=False),
        sa.ForeignKeyConstraint(['agent_id'], ['marketplace_agents.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('agent_id', 'version', name='uq_agent_version')
    )
    op.create_index('ix_version_agent', 'agent_versions', ['agent_id'])
    op.create_index('ix_version_number', 'agent_versions', ['version'])
    op.create_index('ix_version_latest', 'agent_versions', ['is_latest'])
    op.create_index('ix_version_created', 'agent_versions', ['created_at'])
    op.create_index('ix_version_agent_latest', 'agent_versions', ['agent_id', 'is_latest'])

    # Agent Installations table
    op.create_table(
        'agent_installations',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('agent_id', sa.Integer(), nullable=False),
        sa.Column('version', sa.String(length=50), nullable=False),
        sa.Column('user_id', sa.String(length=255), nullable=False),
        sa.Column('organization_id', sa.Integer(), nullable=True),
        sa.Column('status', sa.Enum('pending', 'installing', 'installed', 'failed', 'uninstalled', name='installationstatus'), nullable=False, server_default='pending'),
        sa.Column('installed_agent_id', sa.Integer(), nullable=True),
        sa.Column('config_overrides', postgresql.JSON(astext_type=sa.Text()), nullable=True, server_default='{}'),
        sa.Column('error_message', sa.Text(), nullable=True),
        sa.Column('last_used_at', sa.TIMESTAMP(), nullable=True),
        sa.Column('usage_count', sa.Integer(), nullable=True, server_default='0'),
        sa.Column('auto_update', sa.Boolean(), nullable=False, server_default='true'),
        sa.Column('installed_at', sa.TIMESTAMP(), nullable=False, server_default=sa.text('now()')),
        sa.Column('uninstalled_at', sa.TIMESTAMP(), nullable=True),
        sa.Column('updated_at', sa.TIMESTAMP(), nullable=True, server_default=sa.text('now()')),
        sa.ForeignKeyConstraint(['agent_id'], ['marketplace_agents.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index('ix_install_agent', 'agent_installations', ['agent_id'])
    op.create_index('ix_install_user', 'agent_installations', ['user_id'])
    op.create_index('ix_install_org', 'agent_installations', ['organization_id'])
    op.create_index('ix_install_status', 'agent_installations', ['status'])
    op.create_index('ix_install_installed_agent', 'agent_installations', ['installed_agent_id'])
    op.create_index('ix_install_last_used', 'agent_installations', ['last_used_at'])
    op.create_index('ix_install_installed', 'agent_installations', ['installed_at'])
    op.create_index('ix_install_user_agent', 'agent_installations', ['user_id', 'agent_id'])
    op.create_index('ix_install_org_agent', 'agent_installations', ['organization_id', 'agent_id'])

    # Agent Reviews table
    op.create_table(
        'agent_reviews',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('agent_id', sa.Integer(), nullable=False),
        sa.Column('user_id', sa.String(length=255), nullable=False),
        sa.Column('user_name', sa.String(length=255), nullable=False),
        sa.Column('organization_id', sa.Integer(), nullable=True),
        sa.Column('rating', sa.Integer(), nullable=False),
        sa.Column('title', sa.String(length=255), nullable=True),
        sa.Column('review_text', sa.Text(), nullable=True),
        sa.Column('version', sa.String(length=50), nullable=True),
        sa.Column('status', sa.Enum('pending', 'approved', 'rejected', 'flagged', name='reviewstatus'), nullable=False, server_default='pending'),
        sa.Column('moderation_notes', sa.Text(), nullable=True),
        sa.Column('helpful_count', sa.Integer(), nullable=True, server_default='0'),
        sa.Column('unhelpful_count', sa.Integer(), nullable=True, server_default='0'),
        sa.Column('publisher_response', sa.Text(), nullable=True),
        sa.Column('publisher_response_at', sa.TIMESTAMP(), nullable=True),
        sa.Column('created_at', sa.TIMESTAMP(), nullable=False, server_default=sa.text('now()')),
        sa.Column('updated_at', sa.TIMESTAMP(), nullable=True, server_default=sa.text('now()')),
        sa.ForeignKeyConstraint(['agent_id'], ['marketplace_agents.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('agent_id', 'user_id', name='uq_agent_user_review')
    )
    op.create_index('ix_review_agent', 'agent_reviews', ['agent_id'])
    op.create_index('ix_review_user', 'agent_reviews', ['user_id'])
    op.create_index('ix_review_rating', 'agent_reviews', ['rating'])
    op.create_index('ix_review_status', 'agent_reviews', ['status'])
    op.create_index('ix_review_created', 'agent_reviews', ['created_at'])
    op.create_index('ix_review_agent_rating', 'agent_reviews', ['agent_id', 'rating'])

    # Agent Collections table
    op.create_table(
        'agent_collections',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('name', sa.String(length=255), nullable=False),
        sa.Column('slug', sa.String(length=255), nullable=False),
        sa.Column('description', sa.Text(), nullable=False),
        sa.Column('created_by', sa.String(length=255), nullable=False),
        sa.Column('is_official', sa.Boolean(), nullable=False, server_default='false'),
        sa.Column('agent_ids', postgresql.JSON(astext_type=sa.Text()), nullable=True, server_default='[]'),
        sa.Column('cover_image_url', sa.String(length=500), nullable=True),
        sa.Column('is_public', sa.Boolean(), nullable=False, server_default='true'),
        sa.Column('is_featured', sa.Boolean(), nullable=False, server_default='false'),
        sa.Column('install_count', sa.Integer(), nullable=True, server_default='0'),
        sa.Column('created_at', sa.TIMESTAMP(), nullable=False, server_default=sa.text('now()')),
        sa.Column('updated_at', sa.TIMESTAMP(), nullable=True, server_default=sa.text('now()')),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('slug')
    )
    op.create_index('ix_collection_name', 'agent_collections', ['name'])
    op.create_index('ix_collection_slug', 'agent_collections', ['slug'])
    op.create_index('ix_collection_created_by', 'agent_collections', ['created_by'])
    op.create_index('ix_collection_official', 'agent_collections', ['is_official'])
    op.create_index('ix_collection_featured', 'agent_collections', ['is_featured'])
    op.create_index('ix_collection_created', 'agent_collections', ['created_at'])
    op.create_index('ix_collection_featured_installs', 'agent_collections', ['is_featured', 'install_count'])

    # Agent Analytics table
    op.create_table(
        'agent_analytics',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('marketplace_agent_id', sa.Integer(), nullable=False),
        sa.Column('installation_id', sa.Integer(), nullable=True),
        sa.Column('date', sa.TIMESTAMP(), nullable=False),
        sa.Column('executions', sa.Integer(), nullable=True, server_default='0'),
        sa.Column('success_count', sa.Integer(), nullable=True, server_default='0'),
        sa.Column('failure_count', sa.Integer(), nullable=True, server_default='0'),
        sa.Column('avg_duration_seconds', sa.Float(), nullable=True, server_default='0.0'),
        sa.Column('total_cost_usd', sa.Float(), nullable=True, server_default='0.0'),
        sa.Column('positive_feedback', sa.Integer(), nullable=True, server_default='0'),
        sa.Column('negative_feedback', sa.Integer(), nullable=True, server_default='0'),
        sa.Column('created_at', sa.TIMESTAMP(), nullable=False, server_default=sa.text('now()')),
        sa.ForeignKeyConstraint(['marketplace_agent_id'], ['marketplace_agents.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['installation_id'], ['agent_installations.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index('ix_analytics_marketplace_agent', 'agent_analytics', ['marketplace_agent_id'])
    op.create_index('ix_analytics_installation', 'agent_analytics', ['installation_id'])
    op.create_index('ix_analytics_date', 'agent_analytics', ['date'])
    op.create_index('ix_analytics_agent_date', 'agent_analytics', ['marketplace_agent_id', 'date'])
    op.create_index('ix_analytics_install_date', 'agent_analytics', ['installation_id', 'date'])

def downgrade() -> None:
    op.drop_table('agent_analytics')
    op.drop_table('agent_collections')
    op.drop_table('agent_reviews')
    op.drop_table('agent_installations')
    op.drop_table('agent_versions')
    op.drop_table('marketplace_agents')
    op.execute('DROP TYPE IF EXISTS agentvisibility')
    op.execute('DROP TYPE IF EXISTS agentcategory')
    op.execute('DROP TYPE IF EXISTS agentpricing')
    op.execute('DROP TYPE IF EXISTS installationstatus')
    op.execute('DROP TYPE IF EXISTS reviewstatus')
