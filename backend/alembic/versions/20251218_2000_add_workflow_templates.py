"""add workflow templates

Revision ID: 20251218_2000
Revises: 20251218_1000
Create Date: 2025-12-18 20:00:00.000000

P1 Feature #2: Workflow Templates

Creates tables for workflow template marketplace:
- workflow_templates: Main template catalog
- template_versions: Version control
- template_ratings: User ratings and reviews
- template_favorites: User favorites
- template_usage_logs: Usage analytics
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = '20251218_2000'
down_revision = '20251218_1000'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Drop workflow_templates if it exists from migration 007 (simpler version)
    # Migration 007 created a basic version, this migration creates the complete version
    conn = op.get_bind()
    result = conn.execute(sa.text("""
        SELECT table_name
        FROM information_schema.tables
        WHERE table_name='workflow_templates'
    """))
    if result.fetchone():
        # Drop existing indexes first
        try:
            op.drop_index('idx_template_use_count', table_name='workflow_templates')
            op.drop_index('idx_template_featured', table_name='workflow_templates')
            op.drop_index('idx_template_public', table_name='workflow_templates')
            op.drop_index('idx_template_category', table_name='workflow_templates')
        except:
            pass
        # Drop the table
        op.drop_table('workflow_templates')

    # Create workflow_templates table
    op.create_table(
        'workflow_templates',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('name', sa.String(length=255), nullable=False),
        sa.Column('slug', sa.String(length=255), nullable=False),
        sa.Column('description', sa.Text(), nullable=False),
        sa.Column('category', sa.Enum(
            'sales', 'marketing', 'customer_support', 'devops', 'data_processing',
            'finance', 'hr', 'legal', 'operations', 'analytics', 'security',
            'automation', 'integration', 'other',
            name='templatecategory'
        ), nullable=False),
        sa.Column('tags', postgresql.JSON(astext_type=sa.Text()), server_default='[]'),
        sa.Column('difficulty', sa.Enum(
            'beginner', 'intermediate', 'advanced', 'expert',
            name='templatedifficulty'
        ), server_default='beginner'),
        sa.Column('created_by_user_id', sa.String(length=255), nullable=True),
        sa.Column('organization_id', sa.Integer(), nullable=True),
        sa.Column('visibility', sa.Enum(
            'private', 'organization', 'public', 'verified',
            name='templatevisibility'
        ), server_default='private'),
        sa.Column('workflow_definition', postgresql.JSON(astext_type=sa.Text()), nullable=False),
        sa.Column('parameters', postgresql.JSON(astext_type=sa.Text()), server_default='{}'),
        sa.Column('required_integrations', postgresql.JSON(astext_type=sa.Text()), server_default='[]'),
        sa.Column('icon', sa.String(length=255), nullable=True),
        sa.Column('cover_image_url', sa.String(length=500), nullable=True),
        sa.Column('documentation', sa.Text(), nullable=True),
        sa.Column('use_cases', postgresql.JSON(astext_type=sa.Text()), server_default='[]'),
        sa.Column('usage_count', sa.Integer(), server_default='0'),
        sa.Column('view_count', sa.Integer(), server_default='0'),
        sa.Column('favorite_count', sa.Integer(), server_default='0'),
        sa.Column('average_rating', sa.Float(), server_default='0.0'),
        sa.Column('rating_count', sa.Integer(), server_default='0'),
        sa.Column('is_verified', sa.Boolean(), server_default='false'),
        sa.Column('verified_at', sa.DateTime(), nullable=True),
        sa.Column('verified_by_user_id', sa.String(length=255), nullable=True),
        sa.Column('current_version_id', sa.Integer(), nullable=True),
        sa.Column('version_count', sa.Integer(), server_default='1'),
        sa.Column('is_active', sa.Boolean(), server_default='true'),
        sa.Column('is_featured', sa.Boolean(), server_default='false'),
        sa.Column('created_at', sa.DateTime(), server_default=sa.text('now()')),
        sa.Column('updated_at', sa.DateTime(), server_default=sa.text('now()')),
        sa.Column('published_at', sa.DateTime(), nullable=True),
        # Note: No foreign key to organizations since organization_id is a string in this migration but organizations.organization_id might be UUID
        # sa.ForeignKeyConstraint(['organization_id'], ['organizations.organization_id'], ),
        sa.PrimaryKeyConstraint('id')
    )

    # Create indexes for workflow_templates
    op.create_index('ix_workflow_templates_id', 'workflow_templates', ['id'])
    op.create_index('ix_workflow_templates_name', 'workflow_templates', ['name'])
    op.create_index('ix_workflow_templates_slug', 'workflow_templates', ['slug'], unique=True)
    op.create_index('ix_workflow_templates_category', 'workflow_templates', ['category'])
    op.create_index('ix_workflow_templates_created_by_user_id', 'workflow_templates', ['created_by_user_id'])
    op.create_index('ix_workflow_templates_organization_id', 'workflow_templates', ['organization_id'])
    op.create_index('ix_workflow_templates_visibility', 'workflow_templates', ['visibility'])
    op.create_index('ix_workflow_templates_usage_count', 'workflow_templates', ['usage_count'])
    op.create_index('ix_workflow_templates_favorite_count', 'workflow_templates', ['favorite_count'])
    op.create_index('ix_workflow_templates_average_rating', 'workflow_templates', ['average_rating'])
    op.create_index('ix_workflow_templates_is_verified', 'workflow_templates', ['is_verified'])
    op.create_index('ix_workflow_templates_is_active', 'workflow_templates', ['is_active'])
    op.create_index('ix_workflow_templates_is_featured', 'workflow_templates', ['is_featured'])
    op.create_index('ix_workflow_templates_created_at', 'workflow_templates', ['created_at'])
    op.create_index('ix_workflow_templates_published_at', 'workflow_templates', ['published_at'])

    # Composite indexes for common queries
    op.create_index('ix_templates_category_visibility', 'workflow_templates', ['category', 'visibility'])
    op.create_index('ix_templates_featured_active', 'workflow_templates', ['is_featured', 'is_active'])
    op.create_index('ix_templates_verified_active', 'workflow_templates', ['is_verified', 'is_active'])

    # Create template_versions table
    op.create_table(
        'template_versions',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('template_id', sa.Integer(), nullable=False),
        sa.Column('version', sa.String(length=50), nullable=False),
        sa.Column('version_number', sa.Integer(), nullable=False),
        sa.Column('workflow_definition', postgresql.JSON(astext_type=sa.Text()), nullable=False),
        sa.Column('parameters', postgresql.JSON(astext_type=sa.Text()), server_default='{}'),
        sa.Column('required_integrations', postgresql.JSON(astext_type=sa.Text()), server_default='[]'),
        sa.Column('changelog', sa.Text(), nullable=True),
        sa.Column('breaking_changes', sa.Boolean(), server_default='false'),
        sa.Column('created_by_user_id', sa.String(length=255), nullable=False),
        sa.Column('created_at', sa.DateTime(), server_default=sa.text('now()')),
        sa.Column('is_active', sa.Boolean(), server_default='true'),
        sa.ForeignKeyConstraint(['template_id'], ['workflow_templates.id'], ),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('template_id', 'version', name='uq_template_version')
    )

    # Create indexes for template_versions
    op.create_index('ix_template_versions_id', 'template_versions', ['id'])
    op.create_index('ix_template_versions_template_id', 'template_versions', ['template_id'])
    op.create_index('ix_template_versions_created_at', 'template_versions', ['created_at'])
    op.create_index('ix_template_versions_template_id_version', 'template_versions', ['template_id', 'version_number'])

    # Add foreign key for current_version_id (after template_versions exists)
    op.create_foreign_key(
        'fk_workflow_templates_current_version',
        'workflow_templates',
        'template_versions',
        ['current_version_id'],
        ['id']
    )

    # Create template_ratings table
    op.create_table(
        'template_ratings',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('template_id', sa.Integer(), nullable=False),
        sa.Column('user_id', sa.String(length=255), nullable=False),
        sa.Column('rating', sa.Integer(), nullable=False),
        sa.Column('review', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(), server_default=sa.text('now()')),
        sa.Column('updated_at', sa.DateTime(), server_default=sa.text('now()')),
        sa.ForeignKeyConstraint(['template_id'], ['workflow_templates.id'], ),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('template_id', 'user_id', name='uq_template_user_rating')
    )

    # Create indexes for template_ratings
    op.create_index('ix_template_ratings_id', 'template_ratings', ['id'])
    op.create_index('ix_template_ratings_template_id', 'template_ratings', ['template_id'])
    op.create_index('ix_template_ratings_user_id', 'template_ratings', ['user_id'])
    op.create_index('ix_template_ratings_template_rating', 'template_ratings', ['template_id', 'rating'])

    # Create template_favorites table
    op.create_table(
        'template_favorites',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('template_id', sa.Integer(), nullable=False),
        sa.Column('user_id', sa.String(length=255), nullable=False),
        sa.Column('created_at', sa.DateTime(), server_default=sa.text('now()')),
        sa.ForeignKeyConstraint(['template_id'], ['workflow_templates.id'], ),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('template_id', 'user_id', name='uq_template_user_favorite')
    )

    # Create indexes for template_favorites
    op.create_index('ix_template_favorites_id', 'template_favorites', ['id'])
    op.create_index('ix_template_favorites_template_id', 'template_favorites', ['template_id'])
    op.create_index('ix_template_favorites_user_id', 'template_favorites', ['user_id'])

    # Create template_usage_logs table
    op.create_table(
        'template_usage_logs',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('template_id', sa.Integer(), nullable=False),
        sa.Column('version_id', sa.Integer(), nullable=True),
        sa.Column('user_id', sa.String(length=255), nullable=False),
        sa.Column('organization_id', sa.Integer(), nullable=True),
        sa.Column('action', sa.String(length=50), nullable=False),
        sa.Column('workflow_id', sa.Integer(), nullable=True),
        sa.Column('created_at', sa.DateTime(), server_default=sa.text('now()')),
        sa.ForeignKeyConstraint(['template_id'], ['workflow_templates.id'], ),
        sa.ForeignKeyConstraint(['version_id'], ['template_versions.id'], ),
        sa.PrimaryKeyConstraint('id')
    )

    # Create indexes for template_usage_logs
    op.create_index('ix_template_usage_logs_id', 'template_usage_logs', ['id'])
    op.create_index('ix_template_usage_logs_template_id', 'template_usage_logs', ['template_id'])
    op.create_index('ix_template_usage_logs_version_id', 'template_usage_logs', ['version_id'])
    op.create_index('ix_template_usage_logs_user_id', 'template_usage_logs', ['user_id'])
    op.create_index('ix_template_usage_logs_organization_id', 'template_usage_logs', ['organization_id'])
    op.create_index('ix_template_usage_logs_created_at', 'template_usage_logs', ['created_at'])
    op.create_index('ix_template_usage_template_action', 'template_usage_logs', ['template_id', 'action'])


def downgrade() -> None:
    # Drop tables in reverse order
    op.drop_table('template_usage_logs')
    op.drop_table('template_favorites')
    op.drop_table('template_ratings')

    # Drop foreign key first
    op.drop_constraint('fk_workflow_templates_current_version', 'workflow_templates', type_='foreignkey')

    op.drop_table('template_versions')
    op.drop_table('workflow_templates')

    # Drop enums
    op.execute('DROP TYPE IF EXISTS templatecategory')
    op.execute('DROP TYPE IF EXISTS templatedifficulty')
    op.execute('DROP TYPE IF EXISTS templatevisibility')
