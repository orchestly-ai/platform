"""add analytics dashboard

Revision ID: 20251219_0400
Revises: 20251219_0300
Create Date: 2025-12-19 04:00:00.000000

P2 Feature #1: Advanced Analytics & BI Dashboard
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = '20251219_0400'
down_revision = '20251219_0300'

def upgrade() -> None:
    # Note: Enum types are created automatically by SQLAlchemy when tables are created
    # (since create_type=False is NOT set, enums will be created on first use)

    # Dashboards
    op.create_table(
        'dashboards',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('name', sa.String(length=255), nullable=False),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('dashboard_type', sa.Enum('custom', 'template', 'system', name='dashboardtype'), server_default='custom', nullable=False),
        sa.Column('created_by', sa.String(length=255), nullable=False),
        sa.Column('organization_id', sa.Integer(), nullable=True),
        sa.Column('layout', postgresql.JSON(astext_type=sa.Text()), server_default='{}', nullable=True),
        sa.Column('is_public', sa.Boolean(), server_default='false', nullable=False),
        sa.Column('is_default', sa.Boolean(), server_default='false', nullable=False),
        sa.Column('shared_with_users', postgresql.JSON(astext_type=sa.Text()), server_default='[]', nullable=True),
        sa.Column('shared_with_teams', postgresql.JSON(astext_type=sa.Text()), server_default='[]', nullable=True),
        sa.Column('extra_metadata', postgresql.JSON(astext_type=sa.Text()), server_default='{}', nullable=True),
        sa.Column('tags', postgresql.JSON(astext_type=sa.Text()), server_default='[]', nullable=True),
        sa.Column('created_at', sa.TIMESTAMP(), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.TIMESTAMP(), server_default=sa.text('now()'), nullable=True),
        sa.Column('last_viewed_at', sa.TIMESTAMP(), nullable=True),
        sa.Column('view_count', sa.Integer(), server_default='0', nullable=True),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index('ix_dashboard_name', 'dashboards', ['name'])
    op.create_index('ix_dashboard_created_by', 'dashboards', ['created_by'])
    op.create_index('ix_dashboard_org', 'dashboards', ['organization_id'])
    op.create_index('ix_dashboard_type', 'dashboards', ['dashboard_type'])
    op.create_index('ix_dashboard_created', 'dashboards', ['created_at'])
    op.create_index('ix_dashboard_owner', 'dashboards', ['created_by', 'organization_id'])
    op.create_index('ix_dashboard_type_public', 'dashboards', ['dashboard_type', 'is_public'])

    # Dashboard Widgets
    op.create_table(
        'dashboard_widgets',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('dashboard_id', sa.Integer(), nullable=False),
        sa.Column('title', sa.String(length=255), nullable=False),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('widget_type', sa.Enum('line_chart', 'bar_chart', 'pie_chart', 'area_chart',
            'scatter_plot', 'heatmap', 'table', 'metric_card', 'gauge', 'funnel', name='widgettype'), nullable=False),
        sa.Column('position_x', sa.Integer(), server_default='0', nullable=True),
        sa.Column('position_y', sa.Integer(), server_default='0', nullable=True),
        sa.Column('width', sa.Integer(), server_default='4', nullable=True),
        sa.Column('height', sa.Integer(), server_default='3', nullable=True),
        sa.Column('metric_type', sa.Enum('workflow_success_rate', 'workflow_duration', 'task_completion_time',
            'agent_response_time', 'total_cost', 'cost_per_workflow', 'cost_per_agent',
            'llm_cost_by_provider', 'workflow_executions', 'active_users', 'api_requests',
            'agent_invocations', 'error_rate', 'retry_rate', 'approval_time',
            'ab_test_performance', 'roi', 'time_saved', 'automation_rate', name='dashboardmetrictype'), nullable=False),
        sa.Column('aggregation_type', sa.Enum('sum', 'avg', 'min', 'max', 'count', 'p50', 'p95', 'p99', name='aggregationtype'), server_default='avg', nullable=True),
        sa.Column('time_granularity', sa.Enum('minute', 'hour', 'day', 'week', 'month', 'quarter', 'year', name='timegranularity'), server_default='day', nullable=True),
        sa.Column('filters', postgresql.JSON(astext_type=sa.Text()), server_default='{}', nullable=True),
        sa.Column('time_range_days', sa.Integer(), server_default='30', nullable=True),
        sa.Column('config', postgresql.JSON(astext_type=sa.Text()), server_default='{}', nullable=True),
        sa.Column('cached_data', postgresql.JSON(astext_type=sa.Text()), server_default='{}', nullable=True),
        sa.Column('cache_updated_at', sa.TIMESTAMP(), nullable=True),
        sa.Column('created_at', sa.TIMESTAMP(), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.TIMESTAMP(), server_default=sa.text('now()'), nullable=True),
        sa.ForeignKeyConstraint(['dashboard_id'], ['dashboards.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index('ix_widget_dashboard', 'dashboard_widgets', ['dashboard_id'])
    op.create_index('ix_widget_type', 'dashboard_widgets', ['widget_type'])
    op.create_index('ix_widget_metric', 'dashboard_widgets', ['metric_type'])
    op.create_index('ix_widget_dashboard_type', 'dashboard_widgets', ['dashboard_id', 'widget_type'])

    # Metric Snapshots
    op.create_table(
        'metric_snapshots',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('metric_type', sa.Enum('workflow_success_rate', 'workflow_duration', 'task_completion_time',
            'agent_response_time', 'total_cost', 'cost_per_workflow', 'cost_per_agent',
            'llm_cost_by_provider', 'workflow_executions', 'active_users', 'api_requests',
            'agent_invocations', 'error_rate', 'retry_rate', 'approval_time',
            'ab_test_performance', 'roi', 'time_saved', 'automation_rate', name='dashboardmetrictype'), nullable=False),
        sa.Column('organization_id', sa.Integer(), nullable=True),
        sa.Column('workflow_id', sa.Integer(), nullable=True),
        sa.Column('agent_id', sa.Integer(), nullable=True),
        sa.Column('user_id', sa.String(length=255), nullable=True),
        sa.Column('timestamp', sa.TIMESTAMP(), nullable=False),
        sa.Column('granularity', sa.Enum('minute', 'hour', 'day', 'week', 'month', 'quarter', 'year', name='timegranularity'), nullable=False),
        sa.Column('value_numeric', sa.Numeric(precision=20, scale=6), nullable=True),
        sa.Column('value_json', postgresql.JSON(astext_type=sa.Text()), nullable=True),
        sa.Column('extra_metadata', postgresql.JSON(astext_type=sa.Text()), server_default='{}', nullable=True),
        sa.Column('created_at', sa.TIMESTAMP(), server_default=sa.text('now()'), nullable=False),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index('ix_metric_type', 'metric_snapshots', ['metric_type'])
    op.create_index('ix_metric_timestamp', 'metric_snapshots', ['timestamp'])
    op.create_index('ix_metric_granularity', 'metric_snapshots', ['granularity'])
    op.create_index('ix_metric_org', 'metric_snapshots', ['organization_id'])
    op.create_index('ix_metric_workflow', 'metric_snapshots', ['workflow_id'])
    op.create_index('ix_metric_agent', 'metric_snapshots', ['agent_id'])
    op.create_index('ix_metric_user', 'metric_snapshots', ['user_id'])
    op.create_index('ix_metric_created', 'metric_snapshots', ['created_at'])
    op.create_index('ix_metric_type_time', 'metric_snapshots', ['metric_type', 'timestamp', 'granularity'])
    op.create_index('ix_metric_org_time', 'metric_snapshots', ['organization_id', 'timestamp'])

    # Reports
    op.create_table(
        'reports',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('name', sa.String(length=255), nullable=False),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('created_by', sa.String(length=255), nullable=False),
        sa.Column('organization_id', sa.Integer(), nullable=True),
        sa.Column('report_type', sa.String(length=100), nullable=False),
        sa.Column('metrics', postgresql.JSON(astext_type=sa.Text()), server_default='[]', nullable=True),
        sa.Column('filters', postgresql.JSON(astext_type=sa.Text()), server_default='{}', nullable=True),
        sa.Column('time_range_days', sa.Integer(), server_default='30', nullable=True),
        sa.Column('format', sa.Enum('pdf', 'csv', 'excel', 'json', name='reportformat'), server_default='pdf', nullable=False),
        sa.Column('schedule', sa.Enum('none', 'daily', 'weekly', 'monthly', 'quarterly', name='reportschedule'), server_default='none', nullable=False),
        sa.Column('next_run_at', sa.TIMESTAMP(), nullable=True),
        sa.Column('recipients', postgresql.JSON(astext_type=sa.Text()), server_default='[]', nullable=True),
        sa.Column('is_active', sa.Boolean(), server_default='true', nullable=False),
        sa.Column('created_at', sa.TIMESTAMP(), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.TIMESTAMP(), server_default=sa.text('now()'), nullable=True),
        sa.Column('last_generated_at', sa.TIMESTAMP(), nullable=True),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index('ix_report_name', 'reports', ['name'])
    op.create_index('ix_report_created_by', 'reports', ['created_by'])
    op.create_index('ix_report_org', 'reports', ['organization_id'])
    op.create_index('ix_report_type', 'reports', ['report_type'])
    op.create_index('ix_report_schedule', 'reports', ['schedule'])
    op.create_index('ix_report_next_run', 'reports', ['next_run_at'])
    op.create_index('ix_report_created', 'reports', ['created_at'])
    op.create_index('ix_report_owner', 'reports', ['created_by', 'organization_id'])
    op.create_index('ix_report_sched_run', 'reports', ['schedule', 'next_run_at', 'is_active'])

    # Report Executions
    op.create_table(
        'report_executions',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('report_id', sa.Integer(), nullable=False),
        sa.Column('status', sa.String(length=50), nullable=False),
        sa.Column('started_at', sa.TIMESTAMP(), server_default=sa.text('now()'), nullable=False),
        sa.Column('completed_at', sa.TIMESTAMP(), nullable=True),
        sa.Column('output_url', sa.String(length=500), nullable=True),
        sa.Column('output_size_bytes', sa.Integer(), nullable=True),
        sa.Column('error_message', sa.Text(), nullable=True),
        sa.Column('rows_processed', sa.Integer(), server_default='0', nullable=True),
        sa.Column('generation_time_ms', sa.Integer(), nullable=True),
        sa.Column('created_at', sa.TIMESTAMP(), server_default=sa.text('now()'), nullable=False),
        sa.ForeignKeyConstraint(['report_id'], ['reports.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index('ix_exec_report', 'report_executions', ['report_id'])
    op.create_index('ix_exec_status', 'report_executions', ['status'])
    op.create_index('ix_exec_started', 'report_executions', ['started_at'])
    op.create_index('ix_exec_created', 'report_executions', ['created_at'])
    op.create_index('ix_exec_report_status', 'report_executions', ['report_id', 'status'])

    # Custom Metrics
    op.create_table(
        'custom_metrics',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('name', sa.String(length=255), nullable=False),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('created_by', sa.String(length=255), nullable=False),
        sa.Column('organization_id', sa.Integer(), nullable=True),
        sa.Column('formula', sa.Text(), nullable=False),
        sa.Column('base_metrics', postgresql.JSON(astext_type=sa.Text()), server_default='[]', nullable=True),
        sa.Column('unit', sa.String(length=50), nullable=True),
        sa.Column('format_string', sa.String(length=100), nullable=True),
        sa.Column('is_public', sa.Boolean(), server_default='false', nullable=False),
        sa.Column('created_at', sa.TIMESTAMP(), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.TIMESTAMP(), server_default=sa.text('now()'), nullable=True),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index('ix_custom_metric_name', 'custom_metrics', ['name'])
    op.create_index('ix_custom_metric_created_by', 'custom_metrics', ['created_by'])
    op.create_index('ix_custom_metric_org', 'custom_metrics', ['organization_id'])
    op.create_index('ix_custom_metric_created', 'custom_metrics', ['created_at'])
    op.create_index('ix_custom_metric_owner', 'custom_metrics', ['created_by', 'organization_id'])

def downgrade() -> None:
    op.drop_table('custom_metrics')
    op.drop_table('report_executions')
    op.drop_table('reports')
    op.drop_table('metric_snapshots')
    op.drop_table('dashboard_widgets')
    op.drop_table('dashboards')

    # Drop enum types
    sa.Enum(name='reportschedule').drop(op.get_bind(), checkfirst=True)
    sa.Enum(name='reportformat').drop(op.get_bind(), checkfirst=True)
    sa.Enum(name='timegranularity').drop(op.get_bind(), checkfirst=True)
    sa.Enum(name='aggregationtype').drop(op.get_bind(), checkfirst=True)
    sa.Enum(name='dashboardmetrictype').drop(op.get_bind(), checkfirst=True)
    sa.Enum(name='widgettype').drop(op.get_bind(), checkfirst=True)
    sa.Enum(name='dashboardtype').drop(op.get_bind(), checkfirst=True)
