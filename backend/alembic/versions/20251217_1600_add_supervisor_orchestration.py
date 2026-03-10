"""Add Supervisor Orchestration tables

Revision ID: 009
Revises: 008
Create Date: 2025-12-17 16:00:00.000000

This migration adds complete Supervisor Orchestration infrastructure:
- Supervisor configurations (orchestration mode, routing strategy)
- Supervisor executions (task decomposition, agent assignments)
- Agent registry (capabilities, specializations, performance tracking)
- Task assignments (routing decisions, execution tracking)

Competitive advantage: Matches AWS Agent Squad + Microsoft AutoGen patterns.
This solves complex multi-agent orchestration needs.
"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = '009'
down_revision: Union[str, None] = '008'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """
    Create Supervisor Orchestration tables.

    This enables:
    - Multi-agent coordination with 6 orchestration modes
    - Intelligent routing with 6 strategies
    - Task decomposition
    - Group chat mode (AutoGen pattern)
    - Agent capability matching
    """

    # =========================================================================
    # SUPERVISOR_CONFIGS TABLE
    # =========================================================================

    op.create_table(
        'supervisor_configs',
        sa.Column('config_id', postgresql.UUID(as_uuid=True), primary_key=True),

        # Organization
        sa.Column('organization_id', sa.String(255), nullable=False, index=True),

        # Basic info
        sa.Column('name', sa.String(255), nullable=False),
        sa.Column('description', sa.Text(), nullable=True),

        # Orchestration mode
        sa.Column('mode', sa.String(50), nullable=False),
        sa.Column('routing_strategy', sa.String(50), nullable=False, server_default='capability_match'),

        # Agent pool
        sa.Column('agent_pool', postgresql.ARRAY(sa.String()), nullable=False, server_default='{}'),
        sa.Column('agent_capabilities', postgresql.JSONB(), nullable=True),

        # Supervisor behavior
        sa.Column('max_agents_concurrent', sa.Integer(), nullable=False, server_default='3'),
        sa.Column('max_conversation_turns', sa.Integer(), nullable=True),
        sa.Column('timeout_seconds', sa.Integer(), nullable=False, server_default='300'),

        # LLM configuration for supervisor
        sa.Column('llm_model', sa.String(100), nullable=True),
        sa.Column('llm_temperature', sa.Float(), nullable=True, server_default='0.7'),
        sa.Column('llm_system_prompt', sa.Text(), nullable=True),

        # Routing rules
        sa.Column('routing_rules', postgresql.JSONB(), nullable=True),

        # Task decomposition
        sa.Column('auto_decompose_tasks', sa.Boolean(), nullable=False, server_default='true'),
        sa.Column('decomposition_prompt', sa.Text(), nullable=True),

        # Metadata
        sa.Column('is_active', sa.Boolean(), nullable=False, server_default='true'),
        sa.Column('created_by', sa.String(255), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False, server_default=sa.text('now()')),
        sa.Column('updated_at', sa.DateTime(), nullable=False, server_default=sa.text('now()'))
    )

    # Create indexes for supervisor_configs
    op.create_index('idx_supervisor_config_org', 'supervisor_configs', ['organization_id'])
    op.create_index('idx_supervisor_config_active', 'supervisor_configs', ['is_active'])


    # =========================================================================
    # SUPERVISOR_EXECUTIONS TABLE
    # =========================================================================

    op.create_table(
        'supervisor_executions',
        sa.Column('execution_id', postgresql.UUID(as_uuid=True), primary_key=True),

        # References
        sa.Column('config_id', postgresql.UUID(as_uuid=True), nullable=False, index=True),
        sa.Column('workflow_execution_id', postgresql.UUID(as_uuid=True), nullable=True, index=True),
        sa.Column('organization_id', sa.String(255), nullable=False, index=True),

        # Execution metadata
        sa.Column('status', sa.String(50), nullable=False, server_default='pending'),
        sa.Column('mode', sa.String(50), nullable=False),

        # Input/Output
        sa.Column('input_task', sa.Text(), nullable=False),
        sa.Column('output_result', postgresql.JSONB(), nullable=True),

        # Task decomposition
        sa.Column('subtasks', postgresql.JSONB(), nullable=True),
        sa.Column('agent_assignments', postgresql.JSONB(), nullable=True),

        # Conversation history (for group chat mode)
        sa.Column('conversation_history', postgresql.JSONB(), nullable=True),

        # Routing decisions
        sa.Column('routing_decisions', postgresql.JSONB(), nullable=True),

        # Performance metrics
        sa.Column('total_agents_used', sa.Integer(), nullable=True),
        sa.Column('total_turns', sa.Integer(), nullable=True),
        sa.Column('duration_ms', sa.Float(), nullable=True),

        # Cost tracking
        sa.Column('total_cost', sa.Float(), nullable=False, server_default='0.0'),
        sa.Column('cost_by_agent', postgresql.JSONB(), nullable=True),

        # Timestamps
        sa.Column('started_at', sa.DateTime(), nullable=True),
        sa.Column('completed_at', sa.DateTime(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False, server_default=sa.text('now()')),

        # Error handling
        sa.Column('error_message', sa.Text(), nullable=True),
        sa.Column('failed_tasks', postgresql.JSONB(), nullable=True),

        # Metadata
        sa.Column('metadata', postgresql.JSONB(), nullable=True)
    )

    # Create indexes for supervisor_executions
    op.create_index('idx_supervisor_exec_config', 'supervisor_executions', ['config_id'])
    op.create_index('idx_supervisor_exec_workflow', 'supervisor_executions', ['workflow_execution_id'])
    op.create_index('idx_supervisor_exec_org', 'supervisor_executions', ['organization_id'])
    op.create_index('idx_supervisor_exec_status', 'supervisor_executions', ['status'])
    op.create_index('idx_supervisor_exec_created', 'supervisor_executions', ['created_at'])


    # =========================================================================
    # AGENT_REGISTRY TABLE
    # =========================================================================

    op.create_table(
        'agent_registry',
        sa.Column('agent_id', sa.String(255), primary_key=True),

        # Organization
        sa.Column('organization_id', sa.String(255), nullable=False, index=True),

        # Basic info
        sa.Column('name', sa.String(255), nullable=False),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('role', sa.String(50), nullable=False),

        # Capabilities
        sa.Column('capabilities', postgresql.ARRAY(sa.String()), nullable=True),
        sa.Column('specialization', sa.String(255), nullable=True),

        # Configuration
        sa.Column('agent_type', sa.String(50), nullable=True),
        sa.Column('llm_model', sa.String(100), nullable=True),
        sa.Column('system_prompt', sa.Text(), nullable=True),
        sa.Column('tools', postgresql.ARRAY(sa.String()), nullable=True),

        # Performance constraints
        sa.Column('max_concurrent_tasks', sa.Integer(), nullable=False, server_default='5'),
        sa.Column('average_duration_ms', sa.Float(), nullable=True),
        sa.Column('average_cost_per_task', sa.Float(), nullable=True),

        # Availability
        sa.Column('is_active', sa.Boolean(), nullable=False, server_default='true'),
        sa.Column('current_load', sa.Integer(), nullable=False, server_default='0'),

        # Statistics
        sa.Column('total_tasks_completed', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('total_tasks_failed', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('success_rate', sa.Float(), nullable=True),
        sa.Column('average_rating', sa.Float(), nullable=True),

        # Metadata
        sa.Column('created_by', sa.String(255), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False, server_default=sa.text('now()')),
        sa.Column('updated_at', sa.DateTime(), nullable=False, server_default=sa.text('now()'))
    )

    # Create indexes for agent_registry
    op.create_index('idx_agent_registry_org', 'agent_registry', ['organization_id'])
    op.create_index('idx_agent_registry_role', 'agent_registry', ['role'])
    op.create_index('idx_agent_registry_active', 'agent_registry', ['is_active'])
    # op.create_index('idx_agent_registry_capabilities', 'agent_registry', ['capabilities'], postgresql_using='gin'  # GIN index disabled - requires JSONB type)


    # =========================================================================
    # TASK_ASSIGNMENTS TABLE
    # =========================================================================

    op.create_table(
        'task_assignments',
        sa.Column('assignment_id', postgresql.UUID(as_uuid=True), primary_key=True),

        # References
        sa.Column('execution_id', postgresql.UUID(as_uuid=True), nullable=False, index=True),
        sa.Column('agent_id', sa.String(255), nullable=False, index=True),
        sa.Column('organization_id', sa.String(255), nullable=False, index=True),

        # Task details
        sa.Column('task_id', sa.String(255), nullable=False),
        sa.Column('task_description', sa.Text(), nullable=False),
        sa.Column('task_type', sa.String(100), nullable=True),
        sa.Column('priority', sa.Integer(), nullable=False, server_default='0'),

        # Status
        sa.Column('status', sa.String(50), nullable=False, server_default='pending'),

        # Input/Output
        sa.Column('input_data', postgresql.JSONB(), nullable=True),
        sa.Column('output_data', postgresql.JSONB(), nullable=True),

        # Dependencies
        sa.Column('depends_on', postgresql.ARRAY(sa.String()), nullable=True),
        sa.Column('blocks', postgresql.ARRAY(sa.String()), nullable=True),

        # Assignment metadata
        sa.Column('assigned_at', sa.DateTime(), nullable=True),
        sa.Column('assigned_by', sa.String(50), nullable=True),
        sa.Column('routing_reason', sa.Text(), nullable=True),

        # Execution
        sa.Column('started_at', sa.DateTime(), nullable=True),
        sa.Column('completed_at', sa.DateTime(), nullable=True),
        sa.Column('duration_ms', sa.Float(), nullable=True),

        # Cost
        sa.Column('cost', sa.Float(), nullable=False, server_default='0.0'),
        sa.Column('tokens_used', sa.Integer(), nullable=True),

        # Error handling
        sa.Column('retry_count', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('max_retries', sa.Integer(), nullable=False, server_default='3'),
        sa.Column('error_message', sa.Text(), nullable=True),

        # Quality metrics
        sa.Column('confidence_score', sa.Float(), nullable=True),
        sa.Column('validation_status', sa.String(50), nullable=True),

        # Metadata
        sa.Column('metadata', postgresql.JSONB(), nullable=True)
    )

    # Create indexes for task_assignments
    op.create_index('idx_task_assignment_exec', 'task_assignments', ['execution_id'])
    op.create_index('idx_task_assignment_agent', 'task_assignments', ['agent_id'])
    op.create_index('idx_task_assignment_org', 'task_assignments', ['organization_id'])
    op.create_index('idx_task_assignment_status', 'task_assignments', ['status'])
    op.create_index('idx_task_assignment_task_id', 'task_assignments', ['task_id'])


def downgrade() -> None:
    """
    Rollback Supervisor Orchestration tables.

    Warning: This will delete all supervisor configurations, executions,
    agent registry, and task assignments.
    """

    # Drop task_assignments
    op.drop_index('idx_task_assignment_task_id', table_name='task_assignments')
    op.drop_index('idx_task_assignment_status', table_name='task_assignments')
    op.drop_index('idx_task_assignment_org', table_name='task_assignments')
    op.drop_index('idx_task_assignment_agent', table_name='task_assignments')
    op.drop_index('idx_task_assignment_exec', table_name='task_assignments')
    op.drop_table('task_assignments')

    # Drop agent_registry
    op.drop_index('idx_agent_registry_capabilities', table_name='agent_registry')
    op.drop_index('idx_agent_registry_active', table_name='agent_registry')
    op.drop_index('idx_agent_registry_role', table_name='agent_registry')
    op.drop_index('idx_agent_registry_org', table_name='agent_registry')
    op.drop_table('agent_registry')

    # Drop supervisor_executions
    op.drop_index('idx_supervisor_exec_created', table_name='supervisor_executions')
    op.drop_index('idx_supervisor_exec_status', table_name='supervisor_executions')
    op.drop_index('idx_supervisor_exec_org', table_name='supervisor_executions')
    op.drop_index('idx_supervisor_exec_workflow', table_name='supervisor_executions')
    op.drop_index('idx_supervisor_exec_config', table_name='supervisor_executions')
    op.drop_table('supervisor_executions')

    # Drop supervisor_configs
    op.drop_index('idx_supervisor_config_active', table_name='supervisor_configs')
    op.drop_index('idx_supervisor_config_org', table_name='supervisor_configs')
    op.drop_table('supervisor_configs')
