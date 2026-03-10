"""add cost tracking tables

Revision ID: 20251217_1000
Revises: 20251217_0900
Create Date: 2025-12-17 10:00:00.000000

Cost tracking, forecasting, and budget management.
Addresses #2 production pain point: cost runaway ($10K+ surprise bills).
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql
from datetime import datetime

# revision identifiers, used by Alembic.
revision = '20251217_1000'
down_revision = '20251217_0900'
branch_labels = None
depends_on = None


def upgrade():
    """Create cost tracking tables"""

    # Create cost_events table (high-volume time-series data)
    op.create_table(
        'cost_events',
        sa.Column('event_id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('timestamp', sa.DateTime(), nullable=False),

        # Attribution
        sa.Column('organization_id', sa.String(255), nullable=False),
        sa.Column('user_id', sa.String(255), nullable=True),
        sa.Column('agent_id', postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column('task_id', postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column('workflow_id', postgresql.UUID(as_uuid=True), nullable=True),

        # Cost details
        sa.Column('category', sa.String(50), nullable=False),
        sa.Column('amount', sa.Float(), nullable=False),
        sa.Column('currency', sa.String(3), nullable=False, default='USD'),

        # Provider details (for LLM costs)
        sa.Column('provider', sa.String(50), nullable=True),
        sa.Column('model', sa.String(100), nullable=True),

        # Usage metrics
        sa.Column('input_tokens', sa.Integer(), nullable=True),
        sa.Column('output_tokens', sa.Integer(), nullable=True),
        sa.Column('total_tokens', sa.Integer(), nullable=True),

        # Metadata
        sa.Column('metadata', postgresql.JSON(astext_type=sa.Text()), nullable=True),

        # Foreign keys
        sa.ForeignKeyConstraint(['organization_id'], ['organizations.organization_id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['user_id'], ['users.user_id'], ondelete='SET NULL'),
        sa.ForeignKeyConstraint(['agent_id'], ['agents.agent_id'], ondelete='SET NULL'),
        sa.ForeignKeyConstraint(['task_id'], ['tasks.task_id'], ondelete='SET NULL'),
        sa.ForeignKeyConstraint(['workflow_id'], ['workflows.workflow_id'], ondelete='SET NULL')
    )

    # Indexes for time-series queries
    op.create_index('idx_cost_timestamp', 'cost_events', ['timestamp'])
    op.create_index('idx_cost_org_time', 'cost_events', ['organization_id', 'timestamp'])
    op.create_index('idx_cost_agent_time', 'cost_events', ['agent_id', 'timestamp'])
    op.create_index('idx_cost_task', 'cost_events', ['task_id'])
    op.create_index('idx_cost_workflow', 'cost_events', ['workflow_id'])
    op.create_index('idx_cost_category_time', 'cost_events', ['category', 'timestamp'])
    op.create_index('idx_cost_provider_time', 'cost_events', ['provider', 'timestamp'])
    op.create_index('idx_cost_user', 'cost_events', ['user_id'])

    # Create cost_aggregates table (pre-computed rollups)
    op.create_table(
        'cost_aggregates',
        sa.Column('aggregate_id', postgresql.UUID(as_uuid=True), primary_key=True),

        # Time period
        sa.Column('period', sa.String(20), nullable=False),
        sa.Column('period_start', sa.DateTime(), nullable=False),
        sa.Column('period_end', sa.DateTime(), nullable=False),

        # Attribution
        sa.Column('organization_id', sa.String(255), nullable=False),
        sa.Column('agent_id', postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column('category', sa.String(50), nullable=True),

        # Aggregated metrics
        sa.Column('total_cost', sa.Float(), nullable=False),
        sa.Column('event_count', sa.Integer(), nullable=False),
        sa.Column('avg_cost_per_event', sa.Float(), nullable=False),

        # Token usage
        sa.Column('total_input_tokens', sa.Integer(), nullable=True),
        sa.Column('total_output_tokens', sa.Integer(), nullable=True),
        sa.Column('total_tokens', sa.Integer(), nullable=True),

        # Breakdowns
        sa.Column('provider_breakdown', postgresql.JSON(astext_type=sa.Text()), nullable=True),
        sa.Column('model_breakdown', postgresql.JSON(astext_type=sa.Text()), nullable=True),

        # Timestamps
        sa.Column('created_at', sa.DateTime(), nullable=False, default=datetime.utcnow),

        # Foreign keys
        sa.ForeignKeyConstraint(['organization_id'], ['organizations.organization_id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['agent_id'], ['agents.agent_id'], ondelete='CASCADE')
    )

    # Indexes for aggregates
    op.create_index('idx_agg_period_start', 'cost_aggregates', ['period', 'period_start'])
    op.create_index('idx_agg_org_period', 'cost_aggregates', ['organization_id', 'period', 'period_start'])
    op.create_index('idx_agg_agent_period', 'cost_aggregates', ['agent_id', 'period_start'])

    # Create budgets table
    op.create_table(
        'budgets',
        sa.Column('budget_id', postgresql.UUID(as_uuid=True), primary_key=True),

        # Organization
        sa.Column('organization_id', sa.String(255), nullable=False),

        # Budget details
        sa.Column('name', sa.String(255), nullable=False),
        sa.Column('period', sa.String(20), nullable=False),
        sa.Column('amount', sa.Float(), nullable=False),
        sa.Column('currency', sa.String(3), nullable=False, default='USD'),

        # Scope
        sa.Column('scope_type', sa.String(50), nullable=True),
        sa.Column('scope_id', sa.String(255), nullable=True),

        # Alert thresholds (percentages)
        sa.Column('alert_threshold_info', sa.Float(), nullable=False, default=50.0),
        sa.Column('alert_threshold_warning', sa.Float(), nullable=False, default=75.0),
        sa.Column('alert_threshold_critical', sa.Float(), nullable=False, default=90.0),

        # Actions
        sa.Column('auto_disable_on_exceeded', sa.Boolean(), nullable=False, default=False),

        # Status
        sa.Column('is_active', sa.Boolean(), nullable=False, default=True),

        # Metadata
        sa.Column('metadata', postgresql.JSON(astext_type=sa.Text()), nullable=True),

        # Timestamps
        sa.Column('created_at', sa.DateTime(), nullable=False, default=datetime.utcnow),
        sa.Column('updated_at', sa.DateTime(), nullable=False, default=datetime.utcnow),
        sa.Column('created_by', sa.String(255), nullable=True),

        # Foreign keys
        sa.ForeignKeyConstraint(['organization_id'], ['organizations.organization_id'], ondelete='CASCADE')
    )

    # Indexes for budgets
    op.create_index('idx_budget_org', 'budgets', ['organization_id'])
    op.create_index('idx_budget_active', 'budgets', ['is_active'])
    op.create_index('idx_budget_scope', 'budgets', ['scope_type', 'scope_id'])

    # Create cost_forecasts table
    op.create_table(
        'cost_forecasts',
        sa.Column('forecast_id', postgresql.UUID(as_uuid=True), primary_key=True),

        # Organization
        sa.Column('organization_id', sa.String(255), nullable=False),

        # Forecast details
        sa.Column('forecast_date', sa.Date(), nullable=False),
        sa.Column('forecast_period_start', sa.Date(), nullable=False),
        sa.Column('forecast_period_end', sa.Date(), nullable=False),

        # Predictions
        sa.Column('predicted_cost', sa.Float(), nullable=False),
        sa.Column('confidence_lower', sa.Float(), nullable=False),
        sa.Column('confidence_upper', sa.Float(), nullable=False),
        sa.Column('confidence_interval', sa.Float(), nullable=False, default=95.0),

        # Scope
        sa.Column('scope_type', sa.String(50), nullable=True),
        sa.Column('scope_id', sa.String(255), nullable=True),

        # Model details
        sa.Column('model_type', sa.String(50), nullable=False),
        sa.Column('model_version', sa.String(50), nullable=False),
        sa.Column('training_data_points', sa.Integer(), nullable=False),

        # Anomalies
        sa.Column('anomalies_detected', postgresql.JSON(astext_type=sa.Text()), nullable=True),

        # Metadata
        sa.Column('metadata', postgresql.JSON(astext_type=sa.Text()), nullable=True),

        # Timestamps
        sa.Column('created_at', sa.DateTime(), nullable=False, default=datetime.utcnow),

        # Foreign keys
        sa.ForeignKeyConstraint(['organization_id'], ['organizations.organization_id'], ondelete='CASCADE')
    )

    # Indexes for forecasts
    op.create_index('idx_forecast_org_date', 'cost_forecasts', ['organization_id', 'forecast_date'])
    op.create_index('idx_forecast_period', 'cost_forecasts', ['forecast_period_start', 'forecast_period_end'])


def downgrade():
    """Drop cost tracking tables"""
    op.drop_table('cost_forecasts')
    op.drop_table('budgets')
    op.drop_table('cost_aggregates')
    op.drop_table('cost_events')
