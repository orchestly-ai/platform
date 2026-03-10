"""Add Prompt Registry tables

Revision ID: d4e5f6a7b8c9
Revises: c3d4e5f6a7b8
Create Date: 2026-01-14 00:01:00.000000

Adds tables for Prompt Registry with versioning support:
- prompt_templates: Store prompt metadata
- prompt_versions: Version control for prompts
- prompt_usage_stats: Track usage analytics
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = 'd4e5f6a7b8c9'
down_revision = 'c3d4e5f6a7b8'
branch_labels = None
depends_on = None


def table_exists(table_name):
    """Check if a table exists."""
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    return table_name in inspector.get_table_names()


def index_exists(table_name, index_name):
    """Check if an index exists on a table."""
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    indexes = [idx['name'] for idx in inspector.get_indexes(table_name)]
    return index_name in indexes


def upgrade() -> None:
    # Detect database type
    bind = op.get_bind()
    is_sqlite = bind.dialect.name == 'sqlite'

    # Use appropriate UUID and JSON types
    if is_sqlite:
        uuid_type = sa.String(36)
        json_type = sa.JSON()
    else:
        uuid_type = postgresql.UUID(as_uuid=True)
        json_type = postgresql.JSONB(astext_type=sa.Text())

    # Create prompt_templates table (idempotent)
    if table_exists('prompt_templates'):
        return  # All tables already exist, skip migration

    op.create_table(
        'prompt_templates',
        sa.Column('id', uuid_type, nullable=False),
        sa.Column('organization_id', uuid_type, nullable=False),
        sa.Column('name', sa.String(length=255), nullable=False),
        sa.Column('slug', sa.String(length=255), nullable=False),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('category', sa.String(length=100), nullable=True),
        sa.Column('default_version_id', uuid_type, nullable=True),
        sa.Column('is_active', sa.Boolean(), nullable=False, server_default='true'),
        sa.Column('created_at', sa.DateTime(), nullable=False, server_default=sa.text('CURRENT_TIMESTAMP')),
        sa.Column('updated_at', sa.DateTime(), nullable=False, server_default=sa.text('CURRENT_TIMESTAMP')),
        sa.Column('created_by', uuid_type, nullable=True),
        sa.PrimaryKeyConstraint('id')
    )

    # Create indexes for prompt_templates
    op.create_index('idx_prompt_template_org_slug', 'prompt_templates', ['organization_id', 'slug'], unique=True)
    op.create_index('idx_prompt_template_category', 'prompt_templates', ['category'])
    op.create_index('idx_prompt_template_active', 'prompt_templates', ['is_active'])

    # Create prompt_versions table
    op.create_table(
        'prompt_versions',
        sa.Column('id', uuid_type, nullable=False),
        sa.Column('template_id', uuid_type, nullable=False),
        sa.Column('version', sa.String(length=50), nullable=False),
        sa.Column('content', sa.Text(), nullable=False),
        sa.Column('variables', json_type, nullable=False, server_default='[]'),
        sa.Column('model_hint', sa.String(length=100), nullable=True),
        sa.Column('extra_metadata', json_type, nullable=True, server_default='{}'),
        sa.Column('is_published', sa.Boolean(), nullable=False, server_default='false'),
        sa.Column('published_at', sa.DateTime(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False, server_default=sa.text('CURRENT_TIMESTAMP')),
        sa.Column('created_by', uuid_type, nullable=True),
        sa.ForeignKeyConstraint(['template_id'], ['prompt_templates.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
    )

    # Create indexes for prompt_versions
    op.create_index('idx_prompt_version_template_id', 'prompt_versions', ['template_id'])
    op.create_index('idx_prompt_version_template_version', 'prompt_versions', ['template_id', 'version'], unique=True)
    op.create_index('idx_prompt_version_published', 'prompt_versions', ['is_published'])

    # Create prompt_usage_stats table
    op.create_table(
        'prompt_usage_stats',
        sa.Column('id', uuid_type, nullable=False),
        sa.Column('version_id', uuid_type, nullable=False),
        sa.Column('date', sa.Date(), nullable=False),
        sa.Column('invocations', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('avg_latency_ms', sa.Float(), nullable=True),
        sa.Column('avg_tokens', sa.Integer(), nullable=True),
        sa.Column('success_rate', sa.Float(), nullable=True),
        sa.ForeignKeyConstraint(['version_id'], ['prompt_versions.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
    )

    # Create indexes for prompt_usage_stats
    op.create_index('idx_prompt_usage_version_id', 'prompt_usage_stats', ['version_id'])
    op.create_index('idx_prompt_usage_version_date', 'prompt_usage_stats', ['version_id', 'date'], unique=True)


def downgrade() -> None:
    # Drop tables in reverse order (idempotent)
    if table_exists('prompt_usage_stats'):
        op.drop_table('prompt_usage_stats')
    if table_exists('prompt_versions'):
        op.drop_table('prompt_versions')
    if table_exists('prompt_templates'):
        op.drop_table('prompt_templates')
