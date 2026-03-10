"""Add RAG BYOD tables

Revision ID: c3d4e5f6a7b8
Revises: b2c3d4e5f6a7
Create Date: 2026-01-13 09:00:00.000000

Adds tables for BYOD (Bring Your Own Data) RAG system:
- rag_connector_configs: Store configurations for customer's document stores
- rag_document_index: Track indexed documents
- rag_query_history: Query analytics
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = 'c3d4e5f6a7b8'
down_revision = 'b2c3d4e5f6a7'
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

    # Create rag_connector_configs table
    op.create_table(
        'rag_connector_configs',
        sa.Column('config_id', uuid_type, primary_key=True),
        sa.Column('organization_id', sa.String(255), nullable=False),
        sa.Column('provider_type', sa.String(50), nullable=False),
        sa.Column('name', sa.String(255), nullable=False),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('connection_config', sa.JSON(), nullable=False),
        sa.Column('chunking_strategy', sa.String(50), nullable=False, server_default='recursive'),
        sa.Column('chunk_size', sa.Integer(), nullable=False, server_default='1000'),
        sa.Column('chunk_overlap', sa.Integer(), nullable=False, server_default='200'),
        sa.Column('memory_provider_id', uuid_type, nullable=True),
        sa.Column('embedding_provider', sa.String(50), nullable=True),
        sa.Column('embedding_model', sa.String(100), nullable=True),
        sa.Column('sync_enabled', sa.Boolean(), nullable=False, server_default='false'),
        sa.Column('sync_interval_hours', sa.Integer(), nullable=True),
        sa.Column('last_sync_at', sa.DateTime(), nullable=True),
        sa.Column('last_sync_status', sa.String(50), nullable=True),
        sa.Column('last_sync_documents', sa.Integer(), nullable=True),
        sa.Column('is_active', sa.Boolean(), nullable=False, server_default='true'),
        sa.Column('is_default', sa.Boolean(), nullable=False, server_default='false'),
        sa.Column('health_status', sa.String(50), nullable=True),
        sa.Column('last_health_check', sa.DateTime(), nullable=True),
        sa.Column('total_documents', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('total_chunks', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('total_queries', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('tags', json_type, nullable=True),
        sa.Column('extra_metadata', sa.JSON(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.Column('created_by', sa.String(255), nullable=True),
    )

    # Create indexes for rag_connector_configs
    op.create_index('idx_rag_connector_org', 'rag_connector_configs', ['organization_id'])
    op.create_index('idx_rag_connector_type', 'rag_connector_configs', ['provider_type'])
    op.create_index('idx_rag_connector_active', 'rag_connector_configs', ['is_active'])
    op.create_index('idx_rag_connector_default', 'rag_connector_configs', ['organization_id', 'is_default'])

    # Create rag_document_index table
    op.create_table(
        'rag_document_index',
        sa.Column('document_id', uuid_type, primary_key=True),
        sa.Column('organization_id', sa.String(255), nullable=False),
        sa.Column('connector_id', uuid_type, nullable=False),
        sa.Column('source_id', sa.String(500), nullable=False),
        sa.Column('source_path', sa.String(1000), nullable=True),
        sa.Column('source_type', sa.String(50), nullable=False),
        sa.Column('title', sa.String(500), nullable=True),
        sa.Column('content_hash', sa.String(64), nullable=True),
        sa.Column('size_bytes', sa.Integer(), nullable=True),
        sa.Column('chunk_count', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('indexed_at', sa.DateTime(), nullable=True),
        sa.Column('index_status', sa.String(50), nullable=False, server_default='pending'),
        sa.Column('index_error', sa.Text(), nullable=True),
        sa.Column('source_modified_at', sa.DateTime(), nullable=True),
        sa.Column('last_checked_at', sa.DateTime(), nullable=True),
        sa.Column('needs_reindex', sa.Boolean(), nullable=False, server_default='false'),
        sa.Column('source_metadata', sa.JSON(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime(), nullable=False, server_default=sa.func.now()),
    )

    # Create indexes for rag_document_index
    op.create_index('idx_doc_index_org', 'rag_document_index', ['organization_id'])
    op.create_index('idx_doc_index_connector', 'rag_document_index', ['connector_id'])
    op.create_index('idx_doc_index_source', 'rag_document_index', ['connector_id', 'source_id'])
    op.create_index('idx_doc_index_status', 'rag_document_index', ['index_status'])
    op.create_index('idx_doc_index_reindex', 'rag_document_index', ['needs_reindex'])

    # Create rag_query_history table
    op.create_table(
        'rag_query_history',
        sa.Column('query_id', uuid_type, primary_key=True),
        sa.Column('organization_id', sa.String(255), nullable=False),
        sa.Column('connector_id', uuid_type, nullable=True),
        sa.Column('query_text', sa.Text(), nullable=False),
        sa.Column('query_type', sa.String(50), nullable=False, server_default='similarity'),
        sa.Column('results_count', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('top_score', sa.Float(), nullable=True),
        sa.Column('avg_score', sa.Float(), nullable=True),
        sa.Column('latency_ms', sa.Float(), nullable=True),
        sa.Column('workflow_execution_id', uuid_type, nullable=True),
        sa.Column('agent_id', sa.String(255), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False, server_default=sa.func.now()),
    )

    # Create indexes for rag_query_history
    op.create_index('idx_rag_query_org', 'rag_query_history', ['organization_id'])
    op.create_index('idx_rag_query_connector', 'rag_query_history', ['connector_id'])
    op.create_index('idx_rag_query_time', 'rag_query_history', ['created_at'])


def downgrade() -> None:
    # Drop indexes first
    op.drop_index('idx_rag_query_time', table_name='rag_query_history')
    op.drop_index('idx_rag_query_connector', table_name='rag_query_history')
    op.drop_index('idx_rag_query_org', table_name='rag_query_history')

    op.drop_index('idx_doc_index_reindex', table_name='rag_document_index')
    op.drop_index('idx_doc_index_status', table_name='rag_document_index')
    op.drop_index('idx_doc_index_source', table_name='rag_document_index')
    op.drop_index('idx_doc_index_connector', table_name='rag_document_index')
    op.drop_index('idx_doc_index_org', table_name='rag_document_index')

    op.drop_index('idx_rag_connector_default', table_name='rag_connector_configs')
    op.drop_index('idx_rag_connector_active', table_name='rag_connector_configs')
    op.drop_index('idx_rag_connector_type', table_name='rag_connector_configs')
    op.drop_index('idx_rag_connector_org', table_name='rag_connector_configs')

    # Drop tables
    op.drop_table('rag_query_history')
    op.drop_table('rag_document_index')
    op.drop_table('rag_connector_configs')
