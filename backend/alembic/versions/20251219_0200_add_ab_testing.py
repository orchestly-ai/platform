"""add ab testing

Revision ID: 20251219_0200
Revises: 20251219_0100
Create Date: 2025-12-19 02:00:00.000000

P1 Feature #4: A/B Testing

Scientific experimentation for workflow optimization with statistical analysis.
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = '20251219_0200'
down_revision = '20251219_0100'
branch_labels = None
depends_on = None

def upgrade() -> None:
    # Note: Enum types are created automatically by SQLAlchemy when tables are created
    # (since create_type=False is NOT set, the default is True which creates the type)
    # So we don't manually create them here

    # Create ab_experiments table
    op.create_table(
        'ab_experiments',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('name', sa.String(length=255), nullable=False),
        sa.Column('slug', sa.String(length=255), nullable=False),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('agent_id', sa.Integer(), nullable=True),
        sa.Column('workflow_id', sa.Integer(), nullable=True),
        sa.Column('task_type', sa.String(length=100), nullable=True),
        sa.Column('organization_id', sa.Integer(), nullable=True),
        sa.Column('created_by_user_id', sa.String(length=255), nullable=False),
        sa.Column('traffic_split_strategy', sa.Enum('random', 'weighted', 'user_hash', 'round_robin', name='trafficsplit', create_type=False), server_default='random'),
        sa.Column('total_traffic_percentage', sa.Float(), server_default='100.0'),
        sa.Column('hypothesis', sa.Text(), nullable=True),
        sa.Column('success_criteria', postgresql.JSON(astext_type=sa.Text()), server_default='{}'),
        sa.Column('minimum_sample_size', sa.Integer(), server_default='100'),
        sa.Column('confidence_level', sa.Float(), server_default='0.95'),
        sa.Column('minimum_effect_size', sa.Float(), server_default='0.05'),
        sa.Column('winner_selection_criteria', sa.Enum('highest_success_rate', 'lowest_latency', 'lowest_cost', 'highest_satisfaction', 'composite_score', name='winnercriteria', create_type=False), server_default='composite_score'),
        sa.Column('winner_variant_id', sa.Integer(), nullable=True),
        sa.Column('winner_confidence', sa.Float(), nullable=True),
        sa.Column('status', sa.Enum('draft', 'running', 'paused', 'completed', 'cancelled', name='experimentstatus', create_type=False), nullable=False, server_default='draft'),
        sa.Column('started_at', sa.DateTime(), nullable=True),
        sa.Column('completed_at', sa.DateTime(), nullable=True),
        sa.Column('scheduled_end_date', sa.DateTime(), nullable=True),
        sa.Column('total_samples', sa.Integer(), server_default='0'),
        sa.Column('is_statistically_significant', sa.Boolean(), server_default='false'),
        sa.Column('p_value', sa.Float(), nullable=True),
        sa.Column('auto_promote_winner', sa.Boolean(), server_default='false'),
        sa.Column('promoted_at', sa.DateTime(), nullable=True),
        sa.Column('tags', postgresql.JSON(astext_type=sa.Text()), server_default='[]'),
        sa.Column('extra_metadata', postgresql.JSON(astext_type=sa.Text()), server_default='{}'),
        sa.Column('created_at', sa.DateTime(), nullable=False, server_default=sa.text('now()')),
        sa.Column('updated_at', sa.DateTime(), server_default=sa.text('now()')),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('slug')
    )
    op.create_index('ix_ab_exp_slug', 'ab_experiments', ['slug'])
    op.create_index('ix_ab_exp_org', 'ab_experiments', ['organization_id'])
    op.create_index('ix_ab_exp_status', 'ab_experiments', ['status'])

    # Create ab_variants table
    op.create_table(
        'ab_variants',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('experiment_id', sa.Integer(), nullable=False),
        sa.Column('name', sa.String(length=255), nullable=False),
        sa.Column('variant_key', sa.String(length=100), nullable=False),
        sa.Column('variant_type', sa.Enum('control', 'treatment', name='varianttype', create_type=False), nullable=False, server_default='treatment'),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('config', postgresql.JSON(astext_type=sa.Text()), server_default='{}'),
        sa.Column('traffic_percentage', sa.Float(), nullable=False),
        sa.Column('agent_config_id', sa.Integer(), nullable=True),
        sa.Column('workflow_definition', postgresql.JSON(astext_type=sa.Text()), nullable=True),
        sa.Column('prompt_template', sa.Text(), nullable=True),
        sa.Column('model_name', sa.String(length=255), nullable=True),
        sa.Column('sample_count', sa.Integer(), server_default='0'),
        sa.Column('success_count', sa.Integer(), server_default='0'),
        sa.Column('error_count', sa.Integer(), server_default='0'),
        sa.Column('total_latency_ms', sa.Float(), server_default='0.0'),
        sa.Column('total_cost', sa.Float(), server_default='0.0'),
        sa.Column('success_rate', sa.Float(), server_default='0.0'),
        sa.Column('avg_latency_ms', sa.Float(), server_default='0.0'),
        sa.Column('avg_cost', sa.Float(), server_default='0.0'),
        sa.Column('error_rate', sa.Float(), server_default='0.0'),
        sa.Column('is_active', sa.Boolean(), nullable=False, server_default='true'),
        sa.Column('is_winner', sa.Boolean(), server_default='false'),
        sa.Column('created_at', sa.DateTime(), nullable=False, server_default=sa.text('now()')),
        sa.Column('updated_at', sa.DateTime(), server_default=sa.text('now()')),
        sa.ForeignKeyConstraint(['experiment_id'], ['ab_experiments.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('experiment_id', 'variant_key')
    )
    op.create_index('ix_ab_var_exp', 'ab_variants', ['experiment_id'])

    # Create ab_assignments table
    op.create_table(
        'ab_assignments',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('experiment_id', sa.Integer(), nullable=False),
        sa.Column('variant_id', sa.Integer(), nullable=False),
        sa.Column('user_id', sa.String(length=255), nullable=True),
        sa.Column('session_id', sa.String(length=255), nullable=True),
        sa.Column('execution_id', sa.Integer(), nullable=True),
        sa.Column('assignment_hash', sa.String(length=64), nullable=True),
        sa.Column('assignment_reason', sa.String(length=100), nullable=True),
        sa.Column('completed', sa.Boolean(), nullable=False, server_default='false'),
        sa.Column('success', sa.Boolean(), nullable=True),
        sa.Column('latency_ms', sa.Float(), nullable=True),
        sa.Column('cost', sa.Float(), nullable=True),
        sa.Column('error_message', sa.Text(), nullable=True),
        sa.Column('custom_metrics', postgresql.JSON(astext_type=sa.Text()), server_default='{}'),
        sa.Column('assigned_at', sa.DateTime(), nullable=False, server_default=sa.text('now()')),
        sa.Column('completed_at', sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(['experiment_id'], ['ab_experiments.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['variant_id'], ['ab_variants.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index('ix_ab_asgn_exp', 'ab_assignments', ['experiment_id'])
    op.create_index('ix_ab_asgn_var', 'ab_assignments', ['variant_id'])
    op.create_index('ix_ab_asgn_user', 'ab_assignments', ['user_id'])

    # Create ab_metrics table
    op.create_table(
        'ab_metrics',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('experiment_id', sa.Integer(), nullable=False),
        sa.Column('variant_id', sa.Integer(), nullable=False),
        sa.Column('assignment_id', sa.Integer(), nullable=True),
        sa.Column('metric_type', sa.Enum('success_rate', 'latency', 'cost', 'error_rate', 'user_satisfaction', 'custom', name='metrictype', create_type=False), nullable=False),
        sa.Column('metric_name', sa.String(length=255), nullable=False),
        sa.Column('metric_value', sa.Float(), nullable=False),
        sa.Column('metric_unit', sa.String(length=50), nullable=True),
        sa.Column('context', postgresql.JSON(astext_type=sa.Text()), server_default='{}'),
        sa.Column('recorded_at', sa.DateTime(), nullable=False, server_default=sa.text('now()')),
        sa.ForeignKeyConstraint(['experiment_id'], ['ab_experiments.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['variant_id'], ['ab_variants.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['assignment_id'], ['ab_assignments.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index('ix_ab_met_exp', 'ab_metrics', ['experiment_id'])
    op.create_index('ix_ab_met_var', 'ab_metrics', ['variant_id'])

def downgrade() -> None:
    op.drop_table('ab_metrics')
    op.drop_table('ab_assignments')
    op.drop_table('ab_variants')
    op.drop_table('ab_experiments')
    op.execute('DROP TYPE IF EXISTS experimentstatus')
    op.execute('DROP TYPE IF EXISTS varianttype')
    op.execute('DROP TYPE IF EXISTS trafficsplit')
    op.execute('DROP TYPE IF EXISTS metrictype')
    op.execute('DROP TYPE IF EXISTS winnercriteria')
