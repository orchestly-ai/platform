"""Add Time-Travel Debugging tables

Revision ID: 008
Revises: 007
Create Date: 2025-12-17 14:00:00.000000

This migration adds complete Time-Travel Debugging infrastructure:
- Execution snapshots (state capture at every step)
- Execution timelines (organized navigation)
- Execution comparisons (side-by-side analysis)
- Execution replays (reproduce issues)

Competitive advantage: AgentOps has this - it's our answer to Pain Point #3: "Debugging Hell"
This is a CRITICAL feature for production AI agent debugging.
"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = '008'
down_revision: Union[str, None] = '007'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """
    Create Time-Travel Debugging tables.

    This enables:
    - Snapshot capture at every execution step
    - Timeline navigation (rewind/forward)
    - Execution comparison (A/B testing)
    - Execution replay (reproduce bugs)
    """

    # =========================================================================
    # EXECUTION_SNAPSHOTS TABLE
    # =========================================================================

    op.create_table(
        'execution_snapshots',
        sa.Column('snapshot_id', postgresql.UUID(as_uuid=True), primary_key=True),

        # Execution reference
        sa.Column('execution_id', postgresql.UUID(as_uuid=True), nullable=False, index=True),
        sa.Column('workflow_id', postgresql.UUID(as_uuid=True), nullable=False, index=True),
        sa.Column('organization_id', sa.String(255), nullable=False, index=True),

        # Snapshot metadata
        sa.Column('snapshot_type', sa.String(50), nullable=False),
        sa.Column('sequence_number', sa.Integer(), nullable=False),
        sa.Column('timestamp', sa.DateTime(), nullable=False, server_default=sa.text('now()')),

        # Node context (if snapshot is for a node)
        sa.Column('node_id', sa.String(255), nullable=True, index=True),
        sa.Column('node_type', sa.String(50), nullable=True),
        sa.Column('node_name', sa.String(255), nullable=True),

        # State capture
        sa.Column('input_state', postgresql.JSONB(), nullable=True),
        sa.Column('output_state', postgresql.JSONB(), nullable=True),
        sa.Column('variables', postgresql.JSONB(), nullable=True),
        sa.Column('context', postgresql.JSONB(), nullable=True),

        # Performance metrics
        sa.Column('duration_ms', sa.Float(), nullable=True),
        sa.Column('memory_usage_mb', sa.Float(), nullable=True),
        sa.Column('cpu_usage_percent', sa.Float(), nullable=True),

        # Cost tracking
        sa.Column('cost', sa.Float(), nullable=False, server_default='0.0'),
        sa.Column('tokens_used', sa.Integer(), nullable=True),

        # LLM-specific data (if applicable)
        sa.Column('llm_model', sa.String(100), nullable=True),
        sa.Column('llm_prompt', sa.Text(), nullable=True),
        sa.Column('llm_response', sa.Text(), nullable=True),
        sa.Column('llm_metadata', postgresql.JSONB(), nullable=True),

        # HTTP-specific data (if applicable)
        sa.Column('http_method', sa.String(10), nullable=True),
        sa.Column('http_url', sa.String(512), nullable=True),
        sa.Column('http_status_code', sa.Integer(), nullable=True),
        sa.Column('http_request', postgresql.JSONB(), nullable=True),
        sa.Column('http_response', postgresql.JSONB(), nullable=True),

        # Error information
        sa.Column('error_message', sa.Text(), nullable=True),
        sa.Column('error_type', sa.String(255), nullable=True),
        sa.Column('error_stack_trace', sa.Text(), nullable=True),

        # Metadata
        sa.Column('metadata', postgresql.JSONB(), nullable=True),
        sa.Column('tags', postgresql.ARRAY(sa.String()), nullable=True)
    )

    # Create indexes for execution_snapshots
    op.create_index('idx_snapshot_execution', 'execution_snapshots', ['execution_id'])
    op.create_index('idx_snapshot_workflow', 'execution_snapshots', ['workflow_id'])
    op.create_index('idx_snapshot_org', 'execution_snapshots', ['organization_id'])
    op.create_index('idx_snapshot_node', 'execution_snapshots', ['node_id'])
    op.create_index('idx_snapshot_sequence', 'execution_snapshots', ['execution_id', 'sequence_number'])
    op.create_index('idx_snapshot_timestamp', 'execution_snapshots', ['timestamp'])
    op.create_index('idx_snapshot_type', 'execution_snapshots', ['snapshot_type'])


    # =========================================================================
    # EXECUTION_TIMELINES TABLE
    # =========================================================================

    op.create_table(
        'execution_timelines',
        sa.Column('timeline_id', postgresql.UUID(as_uuid=True), primary_key=True),

        # Execution reference
        sa.Column('execution_id', postgresql.UUID(as_uuid=True), nullable=False, unique=True, index=True),
        sa.Column('workflow_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('organization_id', sa.String(255), nullable=False, index=True),

        # Timeline metadata
        sa.Column('total_snapshots', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('total_nodes', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('total_duration_ms', sa.Float(), nullable=False, server_default='0.0'),
        sa.Column('total_cost', sa.Float(), nullable=False, server_default='0.0'),

        # Timeline structure
        sa.Column('snapshot_ids', postgresql.ARRAY(postgresql.UUID(as_uuid=True)), nullable=False, server_default='{}'),
        sa.Column('node_sequence', postgresql.ARRAY(sa.String()), nullable=False, server_default='{}'),
        sa.Column('decision_points', postgresql.JSONB(), nullable=True),
        sa.Column('critical_path', postgresql.ARRAY(sa.String()), nullable=True),

        # Analysis results
        sa.Column('bottlenecks', postgresql.JSONB(), nullable=True),
        sa.Column('errors', postgresql.JSONB(), nullable=True),
        sa.Column('llm_calls', postgresql.JSONB(), nullable=True),

        # Timestamps
        sa.Column('started_at', sa.DateTime(), nullable=False),
        sa.Column('completed_at', sa.DateTime(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False, server_default=sa.text('now()'))
    )

    # Create indexes for execution_timelines
    op.create_index('idx_timeline_execution', 'execution_timelines', ['execution_id'])
    op.create_index('idx_timeline_org', 'execution_timelines', ['organization_id'])
    op.create_index('idx_timeline_started', 'execution_timelines', ['started_at'])


    # =========================================================================
    # EXECUTION_COMPARISONS TABLE
    # =========================================================================

    op.create_table(
        'execution_comparisons',
        sa.Column('comparison_id', postgresql.UUID(as_uuid=True), primary_key=True),

        # Organization
        sa.Column('organization_id', sa.String(255), nullable=False, index=True),

        # Executions being compared
        sa.Column('execution_a_id', postgresql.UUID(as_uuid=True), nullable=False, index=True),
        sa.Column('execution_b_id', postgresql.UUID(as_uuid=True), nullable=False, index=True),

        # Comparison metadata
        sa.Column('name', sa.String(255), nullable=True),
        sa.Column('description', sa.Text(), nullable=True),

        # Comparison results
        sa.Column('result', sa.String(50), nullable=False),
        sa.Column('differences', postgresql.JSONB(), nullable=False, server_default='{}'),
        sa.Column('node_by_node_diff', postgresql.JSONB(), nullable=True),

        # Metrics
        sa.Column('similarity_score', sa.Float(), nullable=True),
        sa.Column('cost_delta', sa.Float(), nullable=True),
        sa.Column('duration_delta_ms', sa.Float(), nullable=True),

        # Analysis
        sa.Column('root_cause', sa.Text(), nullable=True),
        sa.Column('recommendations', postgresql.ARRAY(sa.String()), nullable=True),

        # Metadata
        sa.Column('created_by', sa.String(255), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False, server_default=sa.text('now()'))
    )

    # Create indexes for execution_comparisons
    op.create_index('idx_comparison_org', 'execution_comparisons', ['organization_id'])
    op.create_index('idx_comparison_exec_a', 'execution_comparisons', ['execution_a_id'])
    op.create_index('idx_comparison_exec_b', 'execution_comparisons', ['execution_b_id'])
    op.create_index('idx_comparison_created', 'execution_comparisons', ['created_at'])


    # =========================================================================
    # EXECUTION_REPLAYS TABLE
    # =========================================================================

    op.create_table(
        'execution_replays',
        sa.Column('replay_id', postgresql.UUID(as_uuid=True), primary_key=True),

        # Organization
        sa.Column('organization_id', sa.String(255), nullable=False, index=True),

        # Source execution
        sa.Column('source_execution_id', postgresql.UUID(as_uuid=True), nullable=False, index=True),
        sa.Column('workflow_id', postgresql.UUID(as_uuid=True), nullable=False),

        # Replay configuration
        sa.Column('replay_mode', sa.String(50), nullable=False),
        sa.Column('input_modifications', postgresql.JSONB(), nullable=True),
        sa.Column('breakpoints', postgresql.ARRAY(sa.String()), nullable=True),
        sa.Column('skip_nodes', postgresql.ARRAY(sa.String()), nullable=True),

        # Replay result
        sa.Column('new_execution_id', postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column('status', sa.String(50), nullable=False, server_default='pending'),

        # Comparison with original
        sa.Column('matched_original', sa.Boolean(), nullable=True),
        sa.Column('differences_found', postgresql.JSONB(), nullable=True),

        # Metadata
        sa.Column('created_by', sa.String(255), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False, server_default=sa.text('now()')),
        sa.Column('started_at', sa.DateTime(), nullable=True),
        sa.Column('completed_at', sa.DateTime(), nullable=True)
    )

    # Create indexes for execution_replays
    op.create_index('idx_replay_org', 'execution_replays', ['organization_id'])
    op.create_index('idx_replay_source', 'execution_replays', ['source_execution_id'])
    op.create_index('idx_replay_created', 'execution_replays', ['created_at'])


def downgrade() -> None:
    """
    Rollback Time-Travel Debugging tables.

    Warning: This will delete all snapshot, timeline, comparison, and replay data.
    """

    # Drop execution_replays
    op.drop_index('idx_replay_created', table_name='execution_replays')
    op.drop_index('idx_replay_source', table_name='execution_replays')
    op.drop_index('idx_replay_org', table_name='execution_replays')
    op.drop_table('execution_replays')

    # Drop execution_comparisons
    op.drop_index('idx_comparison_created', table_name='execution_comparisons')
    op.drop_index('idx_comparison_exec_b', table_name='execution_comparisons')
    op.drop_index('idx_comparison_exec_a', table_name='execution_comparisons')
    op.drop_index('idx_comparison_org', table_name='execution_comparisons')
    op.drop_table('execution_comparisons')

    # Drop execution_timelines
    op.drop_index('idx_timeline_started', table_name='execution_timelines')
    op.drop_index('idx_timeline_org', table_name='execution_timelines')
    op.drop_index('idx_timeline_execution', table_name='execution_timelines')
    op.drop_table('execution_timelines')

    # Drop execution_snapshots
    op.drop_index('idx_snapshot_type', table_name='execution_snapshots')
    op.drop_index('idx_snapshot_timestamp', table_name='execution_snapshots')
    op.drop_index('idx_snapshot_sequence', table_name='execution_snapshots')
    op.drop_index('idx_snapshot_node', table_name='execution_snapshots')
    op.drop_index('idx_snapshot_org', table_name='execution_snapshots')
    op.drop_index('idx_snapshot_workflow', table_name='execution_snapshots')
    op.drop_index('idx_snapshot_execution', table_name='execution_snapshots')
    op.drop_table('execution_snapshots')
