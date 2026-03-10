"""add hitl workflows

Revision ID: 20251219_0100
Revises: 20251218_2100
Create Date: 2025-12-19 01:00:00.000000

P1 Feature #4: Human-in-the-Loop Workflows

Creates tables for approval workflows and human review:
- approval_requests: Approval requests requiring human decision
- approval_responses: Individual approval/rejection decisions
- approval_notifications: Multi-channel notifications
- approval_escalations: Escalation history
- approval_templates: Reusable approval templates
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = '20251219_0100'
down_revision = '20251218_2100'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Create approval_requests table
    op.create_table(
        'approval_requests',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('workflow_execution_id', sa.Integer(), nullable=False),
        sa.Column('task_id', sa.Integer(), nullable=True),
        sa.Column('node_id', sa.String(length=255), nullable=False),
        sa.Column('title', sa.String(length=500), nullable=False),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('context', postgresql.JSON(astext_type=sa.Text()), server_default='{}'),
        sa.Column('requested_by_user_id', sa.String(length=255), nullable=False),
        sa.Column('organization_id', sa.Integer(), nullable=True),
        sa.Column('required_approvers', postgresql.JSON(astext_type=sa.Text()), server_default='[]'),
        sa.Column('required_approval_count', sa.Integer(), server_default='1'),
        sa.Column('priority', sa.Enum(
            'low', 'medium', 'high', 'critical',
            name='approvalpriority'
        ), server_default='medium'),
        sa.Column('timeout_seconds', sa.Integer(), nullable=True),
        sa.Column('timeout_action', sa.String(length=50), nullable=True),
        sa.Column('expires_at', sa.DateTime(), nullable=True),
        sa.Column('status', sa.Enum(
            'pending', 'approved', 'rejected', 'timeout_approved',
            'timeout_rejected', 'escalated', 'cancelled',
            name='approvalstatus'
        ), server_default='pending', nullable=False),
        sa.Column('approved_by_user_id', sa.String(length=255), nullable=True),
        sa.Column('approved_at', sa.DateTime(), nullable=True),
        sa.Column('rejection_reason', sa.Text(), nullable=True),
        sa.Column('response_time_seconds', sa.Float(), nullable=True),
        sa.Column('escalation_level', sa.Integer(), server_default='0'),
        sa.Column('escalated_to_user_id', sa.String(length=255), nullable=True),
        sa.Column('escalated_at', sa.DateTime(), nullable=True),
        sa.Column('created_at', sa.DateTime(), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(), server_default=sa.text('now()')),
        sa.PrimaryKeyConstraint('id')
    )

    # Create indexes for approval_requests
    op.create_index('ix_approval_requests_id', 'approval_requests', ['id'])
    op.create_index('ix_approval_requests_workflow_execution_id', 'approval_requests', ['workflow_execution_id'])
    op.create_index('ix_approval_requests_task_id', 'approval_requests', ['task_id'])
    op.create_index('ix_approval_requests_requested_by_user_id', 'approval_requests', ['requested_by_user_id'])
    op.create_index('ix_approval_requests_organization_id', 'approval_requests', ['organization_id'])
    op.create_index('ix_approval_requests_priority', 'approval_requests', ['priority'])
    op.create_index('ix_approval_requests_expires_at', 'approval_requests', ['expires_at'])
    op.create_index('ix_approval_requests_status', 'approval_requests', ['status'])
    op.create_index('ix_approval_requests_approved_by_user_id', 'approval_requests', ['approved_by_user_id'])
    op.create_index('ix_approval_requests_escalated_to_user_id', 'approval_requests', ['escalated_to_user_id'])
    op.create_index('ix_approval_requests_created_at', 'approval_requests', ['created_at'])
    op.create_index('ix_approval_requests_status_priority', 'approval_requests', ['status', 'priority'])
    op.create_index('ix_approval_requests_org_status', 'approval_requests', ['organization_id', 'status'])

    # Create approval_responses table
    op.create_table(
        'approval_responses',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('request_id', sa.Integer(), nullable=False),
        sa.Column('approver_user_id', sa.String(length=255), nullable=False),
        sa.Column('approver_email', sa.String(length=500), nullable=True),
        sa.Column('decision', sa.String(length=50), nullable=False),
        sa.Column('comment', sa.Text(), nullable=True),
        sa.Column('response_time_seconds', sa.Float(), nullable=True),
        sa.Column('ip_address', sa.String(length=50), nullable=True),
        sa.Column('user_agent', sa.String(length=500), nullable=True),
        sa.Column('created_at', sa.DateTime(), server_default=sa.text('now()'), nullable=False),
        sa.ForeignKeyConstraint(['request_id'], ['approval_requests.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
    )

    # Create indexes for approval_responses
    op.create_index('ix_approval_responses_id', 'approval_responses', ['id'])
    op.create_index('ix_approval_responses_request_id', 'approval_responses', ['request_id'])
    op.create_index('ix_approval_responses_approver_user_id', 'approval_responses', ['approver_user_id'])
    op.create_index('ix_approval_responses_created_at', 'approval_responses', ['created_at'])
    op.create_index('ix_approval_responses_request_approver', 'approval_responses', ['request_id', 'approver_user_id'])

    # Create approval_notifications table
    op.create_table(
        'approval_notifications',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('request_id', sa.Integer(), nullable=False),
        sa.Column('recipient_user_id', sa.String(length=255), nullable=False),
        sa.Column('recipient_email', sa.String(length=500), nullable=True),
        sa.Column('recipient_phone', sa.String(length=50), nullable=True),
        sa.Column('recipient_slack_id', sa.String(length=255), nullable=True),
        sa.Column('channel', sa.Enum(
            'email', 'slack', 'sms', 'webhook', 'in_app',
            name='notificationchannel'
        ), nullable=False),
        sa.Column('sent', sa.Boolean(), server_default='false', nullable=False),
        sa.Column('sent_at', sa.DateTime(), nullable=True),
        sa.Column('delivery_status', sa.String(length=50), nullable=True),
        sa.Column('error_message', sa.Text(), nullable=True),
        sa.Column('external_id', sa.String(length=500), nullable=True),
        sa.Column('metadata', postgresql.JSON(astext_type=sa.Text()), server_default='{}'),
        sa.Column('created_at', sa.DateTime(), server_default=sa.text('now()'), nullable=False),
        sa.ForeignKeyConstraint(['request_id'], ['approval_requests.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
    )

    # Create indexes for approval_notifications
    op.create_index('ix_approval_notifications_id', 'approval_notifications', ['id'])
    op.create_index('ix_approval_notifications_request_id', 'approval_notifications', ['request_id'])
    op.create_index('ix_approval_notifications_recipient_user_id', 'approval_notifications', ['recipient_user_id'])
    op.create_index('ix_approval_notifications_channel', 'approval_notifications', ['channel'])
    op.create_index('ix_approval_notifications_sent', 'approval_notifications', ['sent'])
    op.create_index('ix_approval_notifications_created_at', 'approval_notifications', ['created_at'])
    op.create_index('ix_approval_notifications_request_channel', 'approval_notifications', ['request_id', 'channel'])
    op.create_index('ix_approval_notifications_status', 'approval_notifications', ['sent', 'delivery_status'])

    # Create approval_escalations table
    op.create_table(
        'approval_escalations',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('request_id', sa.Integer(), nullable=False),
        sa.Column('level', sa.Integer(), nullable=False),
        sa.Column('trigger', sa.Enum(
            'timeout', 'rejection', 'no_response', 'manual',
            name='escalationtrigger'
        ), nullable=False),
        sa.Column('trigger_time', sa.DateTime(), nullable=False),
        sa.Column('escalated_to_user_id', sa.String(length=255), nullable=False),
        sa.Column('escalated_by_user_id', sa.String(length=255), nullable=True),
        sa.Column('resolved', sa.Boolean(), server_default='false', nullable=False),
        sa.Column('resolved_at', sa.DateTime(), nullable=True),
        sa.Column('notes', sa.Text(), nullable=True),
        sa.Column('metadata', postgresql.JSON(astext_type=sa.Text()), server_default='{}'),
        sa.Column('created_at', sa.DateTime(), server_default=sa.text('now()'), nullable=False),
        sa.ForeignKeyConstraint(['request_id'], ['approval_requests.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
    )

    # Create indexes for approval_escalations
    op.create_index('ix_approval_escalations_id', 'approval_escalations', ['id'])
    op.create_index('ix_approval_escalations_request_id', 'approval_escalations', ['request_id'])
    op.create_index('ix_approval_escalations_trigger', 'approval_escalations', ['trigger'])
    op.create_index('ix_approval_escalations_escalated_to_user_id', 'approval_escalations', ['escalated_to_user_id'])
    op.create_index('ix_approval_escalations_resolved', 'approval_escalations', ['resolved'])
    op.create_index('ix_approval_escalations_created_at', 'approval_escalations', ['created_at'])
    op.create_index('ix_approval_escalations_request_level', 'approval_escalations', ['request_id', 'level'])
    op.create_index('ix_approval_escalations_trigger_date', 'approval_escalations', ['trigger', 'created_at'])

    # Create approval_templates table
    op.create_table(
        'approval_templates',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('name', sa.String(length=255), nullable=False),
        sa.Column('slug', sa.String(length=255), nullable=False),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('organization_id', sa.Integer(), nullable=True),
        sa.Column('created_by_user_id', sa.String(length=255), nullable=False),
        sa.Column('default_approvers', postgresql.JSON(astext_type=sa.Text()), server_default='[]'),
        sa.Column('required_approval_count', sa.Integer(), server_default='1'),
        sa.Column('timeout_seconds', sa.Integer(), nullable=True),
        sa.Column('timeout_action', sa.String(length=50), nullable=True),
        sa.Column('escalation_enabled', sa.Boolean(), server_default='false'),
        sa.Column('escalation_chain', postgresql.JSON(astext_type=sa.Text()), server_default='[]'),
        sa.Column('escalation_timeout_seconds', sa.Integer(), nullable=True),
        sa.Column('notification_channels', postgresql.JSON(astext_type=sa.Text()), server_default='[]'),
        sa.Column('notification_template', postgresql.JSON(astext_type=sa.Text()), server_default='{}'),
        sa.Column('category', sa.String(length=100), nullable=True),
        sa.Column('tags', postgresql.JSON(astext_type=sa.Text()), server_default='[]'),
        sa.Column('is_active', sa.Boolean(), server_default='true', nullable=False),
        sa.Column('usage_count', sa.Integer(), server_default='0'),
        sa.Column('created_at', sa.DateTime(), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(), server_default=sa.text('now()')),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('slug', name='uq_approval_template_slug')
    )

    # Create indexes for approval_templates
    op.create_index('ix_approval_templates_id', 'approval_templates', ['id'])
    op.create_index('ix_approval_templates_slug', 'approval_templates', ['slug'], unique=True)
    op.create_index('ix_approval_templates_organization_id', 'approval_templates', ['organization_id'])
    op.create_index('ix_approval_templates_category', 'approval_templates', ['category'])
    op.create_index('ix_approval_templates_is_active', 'approval_templates', ['is_active'])
    op.create_index('ix_approval_templates_org_active', 'approval_templates', ['organization_id', 'is_active'])


def downgrade() -> None:
    # Drop tables in reverse order
    op.drop_table('approval_templates')
    op.drop_table('approval_escalations')
    op.drop_table('approval_notifications')
    op.drop_table('approval_responses')
    op.drop_table('approval_requests')

    # Drop enums
    op.execute('DROP TYPE IF EXISTS approvalpriority')
    op.execute('DROP TYPE IF EXISTS approvalstatus')
    op.execute('DROP TYPE IF EXISTS notificationchannel')
    op.execute('DROP TYPE IF EXISTS escalationtrigger')
