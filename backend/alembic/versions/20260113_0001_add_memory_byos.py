"""Add memory BYOS tables

Revision ID: b2c3d4e5f6a7
Revises: a1b2c3d4e5f6
Create Date: 2026-01-13 08:00:00.000000

Adds tables for BYOS (Bring Your Own Storage) memory system:
- memory_provider_configs: Store configurations for customer's vector DBs
- agent_memory_namespaces: Organize memories by agent/user/session
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = 'b2c3d4e5f6a7'
down_revision = 'a1b2c3d4e5f6'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Detect database type
    bind = op.get_bind()
    is_sqlite = bind.dialect.name == 'sqlite'

    # Use appropriate UUID type
    if is_sqlite:
        uuid_type = sa.String(36)
        json_type = sa.JSON()
    else:
        uuid_type = postgresql.UUID(as_uuid=True)
        json_type = postgresql.JSONB()

    # Create memory_provider_configs table
    op.create_table(
        'memory_provider_configs',
        sa.Column('config_id', uuid_type, primary_key=True),
        sa.Column('organization_id', sa.String(255), nullable=False),
        sa.Column('provider_type', sa.String(50), nullable=False),
        sa.Column('name', sa.String(255), nullable=False),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('connection_config', sa.JSON(), nullable=False),
        sa.Column('embedding_provider', sa.String(50), nullable=False, server_default='openai'),
        sa.Column('embedding_model', sa.String(100), nullable=False, server_default='text-embedding-3-small'),
        sa.Column('embedding_dimensions', sa.Integer(), nullable=False, server_default='1536'),
        sa.Column('is_active', sa.Boolean(), nullable=False, server_default='true'),
        sa.Column('is_default', sa.Boolean(), nullable=False, server_default='false'),
        sa.Column('last_health_check', sa.DateTime(), nullable=True),
        sa.Column('health_status', sa.String(50), nullable=True),
        sa.Column('total_memories', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('total_queries', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('tags', json_type, nullable=True),
        sa.Column('extra_metadata', sa.JSON(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.Column('created_by', sa.String(255), nullable=True),
    )

    # Create indexes for memory_provider_configs
    op.create_index('idx_memory_provider_org', 'memory_provider_configs', ['organization_id'])
    op.create_index('idx_memory_provider_type', 'memory_provider_configs', ['provider_type'])
    op.create_index('idx_memory_provider_active', 'memory_provider_configs', ['is_active'])
    op.create_index('idx_memory_provider_default', 'memory_provider_configs', ['organization_id', 'is_default'])

    # Create agent_memory_namespaces table
    op.create_table(
        'agent_memory_namespaces',
        sa.Column('namespace_id', uuid_type, primary_key=True),
        sa.Column('organization_id', sa.String(255), nullable=False),
        sa.Column('provider_config_id', uuid_type, nullable=False),
        sa.Column('namespace', sa.String(255), nullable=False),
        sa.Column('namespace_type', sa.String(50), nullable=False),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('memory_types', sa.JSON(), nullable=False, server_default='["long_term"]'),
        sa.Column('retention_days', sa.Integer(), nullable=True),
        sa.Column('max_memories', sa.Integer(), nullable=True),
        sa.Column('memory_count', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('last_accessed', sa.DateTime(), nullable=True),
        sa.Column('extra_metadata', sa.JSON(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime(), nullable=False, server_default=sa.func.now()),
    )

    # Create indexes for agent_memory_namespaces
    op.create_index('idx_namespace_org', 'agent_memory_namespaces', ['organization_id'])
    op.create_index('idx_namespace_provider', 'agent_memory_namespaces', ['provider_config_id'])
    op.create_index('idx_namespace_name', 'agent_memory_namespaces', ['organization_id', 'namespace'])


def downgrade() -> None:
    # Drop indexes first
    op.drop_index('idx_namespace_name', table_name='agent_memory_namespaces')
    op.drop_index('idx_namespace_provider', table_name='agent_memory_namespaces')
    op.drop_index('idx_namespace_org', table_name='agent_memory_namespaces')

    op.drop_index('idx_memory_provider_default', table_name='memory_provider_configs')
    op.drop_index('idx_memory_provider_active', table_name='memory_provider_configs')
    op.drop_index('idx_memory_provider_type', table_name='memory_provider_configs')
    op.drop_index('idx_memory_provider_org', table_name='memory_provider_configs')

    # Drop tables
    op.drop_table('agent_memory_namespaces')
    op.drop_table('memory_provider_configs')
