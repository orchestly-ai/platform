"""add realtime websocket

Revision ID: 20251219_0300
Revises: 20251219_0200
Create Date: 2025-12-19 03:00:00.000000

P1 Feature #5: Real-Time Collaboration (WebSocket)
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = '20251219_0300'
down_revision = '20251219_0200'

def upgrade() -> None:
    # Create websocket_connections table
    op.create_table(
        'websocket_connections',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('connection_id', sa.String(length=255), nullable=False),
        sa.Column('user_id', sa.String(length=255), nullable=False),
        sa.Column('session_id', sa.String(length=255), nullable=True),
        sa.Column('client_ip', sa.String(length=50), nullable=True),
        sa.Column('user_agent', sa.String(length=500), nullable=True),
        sa.Column('status', sa.Enum('connected', 'disconnected', 'idle', name='connectionstatus', create_type=False), nullable=False, server_default='connected'),
        sa.Column('subscribed_channels', postgresql.JSON(astext_type=sa.Text()), server_default='[]'),
        sa.Column('last_activity_at', sa.DateTime(), nullable=False, server_default=sa.text('now()')),
        sa.Column('connected_at', sa.DateTime(), nullable=False, server_default=sa.text('now()')),
        sa.Column('disconnected_at', sa.DateTime(), nullable=True),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('connection_id')
    )
    op.create_index('ix_ws_conn_id', 'websocket_connections', ['connection_id'])
    op.create_index('ix_ws_user', 'websocket_connections', ['user_id'])
    op.create_index('ix_ws_status', 'websocket_connections', ['status'])

    # Create user_presence table
    op.create_table(
        'user_presence',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('user_id', sa.String(length=255), nullable=False),
        sa.Column('status', sa.Enum('online', 'away', 'busy', 'offline', name='presencestatus', create_type=False), nullable=False, server_default='offline'),
        sa.Column('status_message', sa.String(length=500), nullable=True),
        sa.Column('current_workflow_id', sa.Integer(), nullable=True),
        sa.Column('current_page', sa.String(length=255), nullable=True),
        sa.Column('last_seen_at', sa.DateTime(), nullable=False, server_default=sa.text('now()')),
        sa.Column('updated_at', sa.DateTime(), server_default=sa.text('now()')),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('user_id')
    )
    op.create_index('ix_presence_user', 'user_presence', ['user_id'])
    op.create_index('ix_presence_status', 'user_presence', ['status'])

    # Create realtime_events table
    op.create_table(
        'realtime_events',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('event_type', sa.Enum(
            'workflow_started', 'workflow_completed', 'workflow_failed', 'workflow_paused',
            'task_started', 'task_completed', 'task_failed', 'agent_status_changed',
            'user_joined', 'user_left', 'cursor_moved', 'selection_changed', 'document_edited',
            'approval_request', 'alert', 'message', 'system_notification',
            name='eventtype', create_type=False
        ), nullable=False),
        sa.Column('event_data', postgresql.JSON(astext_type=sa.Text()), server_default='{}'),
        sa.Column('user_id', sa.String(length=255), nullable=True),
        sa.Column('workflow_id', sa.Integer(), nullable=True),
        sa.Column('task_id', sa.Integer(), nullable=True),
        sa.Column('agent_id', sa.Integer(), nullable=True),
        sa.Column('channel_type', sa.Enum('workflow', 'organization', 'user', 'agent', 'global', name='channeltype', create_type=False), nullable=False),
        sa.Column('channel_id', sa.String(length=255), nullable=False),
        sa.Column('delivered_to_count', sa.Integer(), server_default='0'),
        sa.Column('created_at', sa.DateTime(), nullable=False, server_default=sa.text('now()')),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index('ix_rt_event_type', 'realtime_events', ['event_type'])
    op.create_index('ix_rt_channel', 'realtime_events', ['channel_type', 'channel_id'])
    op.create_index('ix_rt_created', 'realtime_events', ['created_at'])

    # Create notifications table
    op.create_table(
        'notifications',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('user_id', sa.String(length=255), nullable=False),
        sa.Column('title', sa.String(length=500), nullable=False),
        sa.Column('message', sa.Text(), nullable=True),
        sa.Column('notification_type', sa.String(length=50), nullable=False),
        sa.Column('action_url', sa.String(length=500), nullable=True),
        sa.Column('action_label', sa.String(length=100), nullable=True),
        sa.Column('workflow_id', sa.Integer(), nullable=True),
        sa.Column('task_id', sa.Integer(), nullable=True),
        sa.Column('approval_id', sa.Integer(), nullable=True),
        sa.Column('read', sa.Boolean(), nullable=False, server_default='false'),
        sa.Column('read_at', sa.DateTime(), nullable=True),
        sa.Column('dismissed', sa.Boolean(), nullable=False, server_default='false'),
        sa.Column('dismissed_at', sa.DateTime(), nullable=True),
        sa.Column('priority', sa.String(length=20), nullable=False, server_default='normal'),
        sa.Column('expires_at', sa.DateTime(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False, server_default=sa.text('now()')),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index('ix_notif_user', 'notifications', ['user_id'])
    op.create_index('ix_notif_read', 'notifications', ['read'])
    op.create_index('ix_notif_created', 'notifications', ['created_at'])

def downgrade() -> None:
    op.drop_table('notifications')
    op.drop_table('realtime_events')
    op.drop_table('user_presence')
    op.drop_table('websocket_connections')
    op.execute('DROP TYPE IF EXISTS connectionstatus')
    op.execute('DROP TYPE IF EXISTS presencestatus')
    op.execute('DROP TYPE IF EXISTS eventtype')
    op.execute('DROP TYPE IF EXISTS channeltype')
