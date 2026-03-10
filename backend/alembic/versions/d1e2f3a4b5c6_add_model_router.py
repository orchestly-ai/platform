"""Add comprehensive model router with enhanced routing strategies

Revision ID: d1e2f3a4b5c6
Revises: c3d4e5f6a7b8
Create Date: 2026-01-15 00:01:00.000000

This migration adds comprehensive model router tables for intelligent LLM routing
with health monitoring, cost optimization, and strategy configuration. It also
enhances the existing routing_strategies table with new fields.
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = 'd1e2f3a4b5c6'
down_revision = 'c3d4e5f6a7b8'
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Create model router tables and enhance routing strategies."""
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    existing_tables = inspector.get_table_names()

    # 1. Router Models - Define available LLM models with costs and capabilities
    if 'router_models' not in existing_tables:
        op.create_table(
            'router_models',
            sa.Column('id', sa.String(100), nullable=False, primary_key=True),
            sa.Column('organization_id', sa.String(100), nullable=False),
            sa.Column('provider', sa.String(50), nullable=False),
            sa.Column('model_name', sa.String(100), nullable=False),
            sa.Column('display_name', sa.String(255), nullable=True),
            sa.Column('is_enabled', sa.Boolean(), nullable=False, server_default='1'),
            sa.Column('cost_per_1k_input_tokens', sa.Float(), nullable=True),
            sa.Column('cost_per_1k_output_tokens', sa.Float(), nullable=True),
            sa.Column('max_tokens', sa.Integer(), nullable=True),
            sa.Column('supports_vision', sa.Boolean(), nullable=False, server_default='0'),
            sa.Column('supports_tools', sa.Boolean(), nullable=False, server_default='0'),
            sa.Column('quality_score', sa.Float(), nullable=False, server_default='0.8'),
            sa.Column('created_at', sa.DateTime(), nullable=False, server_default=sa.text('CURRENT_TIMESTAMP')),
            sa.Column('updated_at', sa.DateTime(), nullable=False, server_default=sa.text('CURRENT_TIMESTAMP')),
        )
        op.create_index('idx_router_models_org', 'router_models', ['organization_id'])
        op.create_index('idx_router_models_provider', 'router_models', ['provider'])
        op.create_index('idx_router_models_enabled', 'router_models', ['is_enabled'])

    # 2. Router Health Metrics - Track model performance and availability
    if 'router_health_metrics' not in existing_tables:
        op.create_table(
            'router_health_metrics',
            sa.Column('id', sa.String(100), nullable=False, primary_key=True),
            sa.Column('model_id', sa.String(100), nullable=False),
            sa.Column('timestamp', sa.DateTime(), nullable=False),
            sa.Column('latency_p50_ms', sa.Integer(), nullable=True),
            sa.Column('latency_p95_ms', sa.Integer(), nullable=True),
            sa.Column('latency_p99_ms', sa.Integer(), nullable=True),
            sa.Column('success_rate', sa.Float(), nullable=True),
            sa.Column('error_count', sa.Integer(), nullable=False, server_default='0'),
            sa.Column('request_count', sa.Integer(), nullable=False, server_default='0'),
            sa.Column('is_healthy', sa.Boolean(), nullable=False, server_default='1'),
            sa.Column('created_at', sa.DateTime(), nullable=False, server_default=sa.text('CURRENT_TIMESTAMP')),
        )
        op.create_index('idx_health_model_time', 'router_health_metrics', ['model_id', 'timestamp'])
        op.create_index('idx_health_timestamp', 'router_health_metrics', ['timestamp'])
        # Note: Foreign key to router_models added only if router_models exists
        if 'router_models' in existing_tables or 'router_models' in [t for t in inspector.get_table_names()]:
            try:
                op.create_foreign_key('fk_health_model', 'router_health_metrics', 'router_models', ['model_id'], ['id'])
            except:
                pass  # FK might already exist

    # 3. Enhanced Routing Strategies - Add new columns for scope and strategy type
    if 'routing_strategies' in existing_tables:
        existing_columns = [col['name'] for col in inspector.get_columns('routing_strategies')]

        # Add new columns if they don't exist
        if 'scope_type' not in existing_columns:
            op.add_column('routing_strategies', sa.Column('scope_type', sa.String(50), nullable=True, server_default='organization'))
        if 'scope_id' not in existing_columns:
            op.add_column('routing_strategies', sa.Column('scope_id', sa.String(100), nullable=True))
        if 'strategy_type' not in existing_columns:
            op.add_column('routing_strategies', sa.Column('strategy_type', sa.String(50), nullable=True))
        if 'fallback_strategy_id' not in existing_columns:
            op.add_column('routing_strategies', sa.Column('fallback_strategy_id', sa.String(100), nullable=True))
        if 'is_active' not in existing_columns:
            op.add_column('routing_strategies', sa.Column('is_active', sa.Boolean(), nullable=True, server_default='1'))

        # Drop old 'strategy' column if it exists (it conflicts with strategy_type)
        if 'strategy' in existing_columns:
            # First, migrate data from old 'strategy' to new 'strategy_type'
            try:
                op.execute("""
                    UPDATE routing_strategies
                    SET strategy_type = CASE
                        WHEN strategy = 'COST_OPTIMIZED' THEN 'cost'
                        WHEN strategy = 'LATENCY_OPTIMIZED' THEN 'latency'
                        WHEN strategy = 'BEST_AVAILABLE' THEN 'quality'
                        WHEN strategy = 'PRIMARY_WITH_BACKUP' THEN 'weighted_rr'
                        WHEN strategy = 'PRIMARY_ONLY' THEN 'cost'
                        ELSE 'cost'
                    END
                    WHERE strategy_type IS NULL
                """)
            except:
                pass  # Migration might fail if strategy_type doesn't exist

            # Now drop the old column
            op.drop_column('routing_strategies', 'strategy')

        # Create index if it doesn't exist
        existing_indexes = [idx['name'] for idx in inspector.get_indexes('routing_strategies')]
        if 'idx_routing_scope' not in existing_indexes:
            op.create_index('idx_routing_scope', 'routing_strategies', ['scope_type', 'scope_id'])
    else:
        # Create table from scratch if it doesn't exist
        op.create_table(
            'routing_strategies',
            sa.Column('id', sa.String(100), nullable=False, primary_key=True),
            sa.Column('organization_id', sa.String(100), nullable=False),
            sa.Column('scope_type', sa.String(50), nullable=False, server_default='organization'),
            sa.Column('scope_id', sa.String(100), nullable=True),
            sa.Column('strategy_type', sa.String(50), nullable=False),
            sa.Column('config', sa.Text(), nullable=True),
            sa.Column('fallback_strategy_id', sa.String(100), nullable=True),
            sa.Column('is_active', sa.Boolean(), nullable=False, server_default='1'),
            sa.Column('created_at', sa.DateTime(), nullable=False, server_default=sa.text('CURRENT_TIMESTAMP')),
            sa.Column('updated_at', sa.DateTime(), nullable=False, server_default=sa.text('CURRENT_TIMESTAMP')),
        )
        op.create_index('idx_routing_strategy_org', 'routing_strategies', ['organization_id'])
        op.create_index('idx_routing_scope', 'routing_strategies', ['scope_type', 'scope_id'])

    # 4. Strategy Model Weights - For weighted and priority routing
    if 'strategy_model_weights' not in existing_tables:
        op.create_table(
            'strategy_model_weights',
            sa.Column('id', sa.String(100), nullable=False, primary_key=True),
            sa.Column('strategy_id', sa.String(100), nullable=False),
            sa.Column('model_id', sa.String(100), nullable=False),
            sa.Column('weight', sa.Float(), nullable=False, server_default='1.0'),
            sa.Column('priority', sa.Integer(), nullable=False, server_default='0'),
            sa.Column('is_enabled', sa.Boolean(), nullable=False, server_default='1'),
            sa.Column('created_at', sa.DateTime(), nullable=False, server_default=sa.text('CURRENT_TIMESTAMP')),
        )
        op.create_index('idx_strategy_weights_strategy', 'strategy_model_weights', ['strategy_id'])
        op.create_index('idx_strategy_weights_model', 'strategy_model_weights', ['model_id'])

        # Add foreign keys only if referenced tables exist
        try:
            op.create_foreign_key('fk_weights_strategy', 'strategy_model_weights', 'routing_strategies', ['strategy_id'], ['id'])
        except:
            pass
        try:
            op.create_foreign_key('fk_weights_model', 'strategy_model_weights', 'router_models', ['model_id'], ['id'])
        except:
            pass


def downgrade() -> None:
    """Remove model router tables and enhanced routing strategy fields."""
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    existing_tables = inspector.get_table_names()

    # Drop tables in reverse order
    if 'strategy_model_weights' in existing_tables:
        op.drop_table('strategy_model_weights')

    if 'router_health_metrics' in existing_tables:
        op.drop_table('router_health_metrics')

    if 'router_models' in existing_tables:
        op.drop_table('router_models')

    # Remove enhanced columns from routing_strategies
    if 'routing_strategies' in existing_tables:
        existing_columns = [col['name'] for col in inspector.get_columns('routing_strategies')]

        # Add back old 'strategy' column
        if 'strategy' not in existing_columns:
            op.add_column('routing_strategies', sa.Column('strategy', sa.String(50), nullable=True))

        # Migrate data back
        try:
            op.execute("""
                UPDATE routing_strategies
                SET strategy = CASE
                    WHEN strategy_type = 'cost' THEN 'COST_OPTIMIZED'
                    WHEN strategy_type = 'latency' THEN 'LATENCY_OPTIMIZED'
                    WHEN strategy_type = 'quality' THEN 'BEST_AVAILABLE'
                    WHEN strategy_type = 'weighted_rr' THEN 'PRIMARY_WITH_BACKUP'
                    ELSE 'COST_OPTIMIZED'
                END
            """)
        except:
            pass

        # Drop new columns
        if 'scope_type' in existing_columns:
            op.drop_column('routing_strategies', 'scope_type')
        if 'scope_id' in existing_columns:
            op.drop_column('routing_strategies', 'scope_id')
        if 'strategy_type' in existing_columns:
            op.drop_column('routing_strategies', 'strategy_type')
        if 'fallback_strategy_id' in existing_columns:
            op.drop_column('routing_strategies', 'fallback_strategy_id')
        if 'is_active' in existing_columns:
            op.drop_column('routing_strategies', 'is_active')

        # Drop index
        try:
            op.drop_index('idx_routing_scope', table_name='routing_strategies')
        except:
            pass
