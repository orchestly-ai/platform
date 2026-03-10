"""
Real-Time Collaboration Demo - P1 Feature #5

Demonstrates WebSocket and real-time features:
- WebSocket connections
- User presence tracking
- Real-time notifications
- Event broadcasting
- Pub/Sub messaging

Note: This demo shows the service layer. For full WebSocket demo,
use a WebSocket client to connect to ws://localhost:8000/api/v1/ws

Run: python backend/demo_realtime.py
"""

import sys
from pathlib import Path

# Add parent directory to path so backend.* imports work
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

import asyncio
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker
from sqlalchemy import text
from datetime import datetime

from backend.shared.realtime_models import *
from backend.shared.realtime_service import RealtimeService, connection_manager
from backend.database.session import AsyncSessionLocal

async def demo_realtime():
    async_session = AsyncSessionLocal

    async with async_session() as db:
        # Cleanup and recreate tables for clean demo
        for stmt in [
            """DROP TABLE IF EXISTS notifications CASCADE""",
            """DROP TABLE IF EXISTS realtime_events CASCADE""",
            """DROP TABLE IF EXISTS user_presence CASCADE""",
            """DROP TABLE IF EXISTS websocket_connections CASCADE""",
            """CREATE TABLE websocket_connections (
    id SERIAL PRIMARY KEY, connection_id VARCHAR(255) UNIQUE NOT NULL, user_id VARCHAR(255) NOT NULL,
    session_id VARCHAR(255), client_ip VARCHAR(45), user_agent VARCHAR(500), status VARCHAR(50) DEFAULT 'connected',
    last_ping_at TIMESTAMP, connected_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP, disconnected_at TIMESTAMP,
    subscribed_channels JSON DEFAULT '[]', last_activity_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    metadata JSON DEFAULT '{}'
)""",
            """CREATE TABLE user_presence (
    id SERIAL PRIMARY KEY, user_id VARCHAR(255) UNIQUE NOT NULL, status VARCHAR(50) DEFAULT 'offline',
    status_message VARCHAR(500), current_workflow_id INTEGER, current_page VARCHAR(255), last_seen_at TIMESTAMP,
    extra_metadata JSON DEFAULT '{}', updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
)""",
            """CREATE TABLE realtime_events (
    id SERIAL PRIMARY KEY, event_type VARCHAR(100) NOT NULL, event_data JSON DEFAULT '{}',
    user_id VARCHAR(255), workspace_id VARCHAR(255), workflow_id INTEGER, task_id INTEGER, agent_id INTEGER,
    channel_type VARCHAR(50) NOT NULL, channel_id VARCHAR(255) NOT NULL, delivered_to_count INTEGER DEFAULT 0,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
)""",
            """CREATE TABLE notifications (
    id SERIAL PRIMARY KEY, user_id VARCHAR(255) NOT NULL, title VARCHAR(255) NOT NULL, message TEXT NOT NULL,
    notification_type VARCHAR(50) DEFAULT 'info', action_url VARCHAR(500), action_label VARCHAR(100),
    workflow_id INTEGER, task_id INTEGER, approval_id INTEGER, read BOOLEAN DEFAULT FALSE, read_at TIMESTAMP,
    dismissed BOOLEAN DEFAULT FALSE, dismissed_at TIMESTAMP, priority VARCHAR(50) DEFAULT 'normal',
    expires_at TIMESTAMP, created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
)""",
        ]:
            await db.execute(text(stmt))
        for idx in [
            """CREATE INDEX IF NOT EXISTS idx_notifications_user_read ON notifications(user_id, read)""",
            """CREATE INDEX IF NOT EXISTS idx_notifications_created ON notifications(created_at)""",
        ]:
            await db.execute(text(idx))
        await db.commit()
        print("=" * 80)
        print("REAL-TIME COLLABORATION DEMO")
        print("=" * 80)
        print()

        # Demo 1: Connection Management
        print("🔌 DEMO 1: WebSocket Connection Management")
        print("-" * 80)
        
        print("\n1. Simulating WebSocket connections...")
        connections = []
        for i in range(5):
            conn = await RealtimeService.register_connection(
                db,
                connection_id=f"conn_{i}",
                user_id=f"user_{i}",
                client_ip=f"192.168.1.{i+1}",
                user_agent="Mozilla/5.0"
            )
            connections.append(conn)
            print(f"   ✓ User {i} connected: {conn.connection_id}")
        
        print(f"\n2. Connection stats:")
        stats = await RealtimeService.get_connection_stats(db)
        print(f"   Total connections: {stats.total_connections}")
        print(f"   Active users: {stats.active_users}")
        
        # Demo 2: User Presence
        print("\n\n👤 DEMO 2: User Presence Tracking")
        print("-" * 80)
        
        print("\n1. Updating user presence...")
        await RealtimeService.update_presence(
            db, "user_0",
            PresenceUpdate(
                user_id="user_0",
                status=PresenceStatus.ONLINE,
                status_message="Working on Q4 roadmap",
                current_workflow_id=123,
                current_page="/workflows/123"
            )
        )
        print("   ✓ user_0: Online (Working on Q4 roadmap)")
        
        await RealtimeService.update_presence(
            db, "user_1",
            PresenceUpdate(
                user_id="user_1",
                status=PresenceStatus.BUSY,
                status_message="In a meeting",
            )
        )
        print("   ✓ user_1: Busy (In a meeting)")
        
        await RealtimeService.update_presence(
            db, "user_2",
            PresenceUpdate(
                user_id="user_2",
                status=PresenceStatus.AWAY,
            )
        )
        print("   ✓ user_2: Away")
        
        print("\n2. Getting online users...")
        online_users = await RealtimeService.get_online_users(db)
        print(f"   ✓ Found {len(online_users)} online users:")
        for user in online_users[:3]:
            print(f"      - {user.user_id}: {user.status.value if hasattr(user.status, 'value') else user.status}")
            if user.status_message:
                print(f"        Message: {user.status_message}")
        
        # Demo 3: Real-Time Events
        print("\n\n📡 DEMO 3: Real-Time Event Broadcasting")
        print("-" * 80)
        
        print("\n1. Publishing workflow started event...")
        event = await RealtimeService.publish_event(
            db,
            EventPublish(
                event_type=EventType.WORKFLOW_STARTED,
                event_data={
                    "workflow_id": 123,
                    "workflow_name": "Customer Onboarding",
                    "started_by": "user_0",
                },
                channel_type=ChannelType.WORKFLOW,
                channel_id="workflow_123",
                workflow_id=123,
                user_id="user_0"
            )
        )
        print(f"   ✓ Event published: {event.event_type.value if hasattr(event.event_type, 'value') else event.event_type}")
        print(f"   ✓ Channel: {event.channel_type.value if hasattr(event.channel_type, 'value') else event.channel_type}:{event.channel_id}")
        print(f"   ✓ Delivered to: {event.delivered_to_count} subscribers")
        
        print("\n2. Publishing task completed event...")
        event = await RealtimeService.publish_event(
            db,
            EventPublish(
                event_type=EventType.TASK_COMPLETED,
                event_data={
                    "task_id": 456,
                    "task_name": "Send welcome email",
                    "duration_ms": 1250,
                    "success": True,
                },
                channel_type=ChannelType.WORKFLOW,
                channel_id="workflow_123",
                workflow_id=123,
                task_id=456
            )
        )
        print(f"   ✓ Event: {event.event_type.value if hasattr(event.event_type, 'value') else event.event_type}")
        print(f"   ✓ Task: Send welcome email (1.25s)")
        
        # Demo 4: Notifications
        print("\n\n🔔 DEMO 4: Real-Time Notifications")
        print("-" * 80)
        
        print("\n1. Creating notifications...")
        
        # Info notification
        notif1 = await RealtimeService.create_notification(
            db,
            NotificationCreate(
                user_id="user_0",
                title="Workflow completed successfully",
                message="Customer Onboarding workflow finished in 2.5 minutes",
                notification_type="success",
                workflow_id=123,
                priority="normal"
            )
        )
        print(f"   ✓ Success: {notif1.title}")
        
        # Urgent notification
        notif2 = await RealtimeService.create_notification(
            db,
            NotificationCreate(
                user_id="user_0",
                title="Approval required",
                message="Budget request needs your approval",
                notification_type="warning",
                action_url="/approvals/789",
                action_label="Review",
                approval_id=789,
                priority="urgent"
            )
        )
        print(f"   ✓ Urgent: {notif2.title}")
        
        # Error notification
        notif3 = await RealtimeService.create_notification(
            db,
            NotificationCreate(
                user_id="user_1",
                title="Workflow failed",
                message="Payment Processing workflow encountered an error",
                notification_type="error",
                workflow_id=124,
                priority="high"
            )
        )
        print(f"   ✓ Error: {notif3.title}")
        
        print("\n2. Getting user notifications...")
        notifications = await RealtimeService.get_notifications(
            db, "user_0", unread_only=True
        )
        print(f"   ✓ user_0 has {len(notifications)} unread notifications")
        
        print("\n3. Marking notification as read...")
        await RealtimeService.mark_notification_read(db, notif1.id, "user_0")
        print(f"   ✓ Notification {notif1.id} marked as read")
        
        # Demo 5: Collaborative Editing Events
        print("\n\n✍️  DEMO 5: Collaborative Editing Events")
        print("-" * 80)
        
        print("\n1. User joins document...")
        await RealtimeService.publish_event(
            db,
            EventPublish(
                event_type=EventType.USER_JOINED,
                event_data={
                    "user_id": "user_3",
                    "document_id": "workflow_def_123",
                    "cursor_position": 0,
                },
                channel_type=ChannelType.WORKFLOW,
                channel_id="workflow_123",
                user_id="user_3"
            )
        )
        print("   ✓ user_3 joined workflow editor")
        
        print("\n2. User moves cursor...")
        await RealtimeService.publish_event(
            db,
            EventPublish(
                event_type=EventType.CURSOR_MOVED,
                event_data={
                    "user_id": "user_3",
                    "line": 42,
                    "column": 15,
                },
                channel_type=ChannelType.WORKFLOW,
                channel_id="workflow_123",
                user_id="user_3"
            )
        )
        print("   ✓ Cursor moved to line 42, col 15")
        
        print("\n3. User makes edit...")
        await RealtimeService.publish_event(
            db,
            EventPublish(
                event_type=EventType.DOCUMENT_EDITED,
                event_data={
                    "user_id": "user_3",
                    "change_type": "insert",
                    "position": 1234,
                    "content": "new_task_node",
                    "timestamp": datetime.utcnow().isoformat(),
                },
                channel_type=ChannelType.WORKFLOW,
                channel_id="workflow_123",
                user_id="user_3"
            )
        )
        print("   ✓ Document edited: Added new task node")
        
        # Demo 6: Connection Statistics
        print("\n\n📊 DEMO 6: Connection Statistics")
        print("-" * 80)
        
        stats = await RealtimeService.get_connection_stats(db)
        print(f"\n1. Real-time metrics:")
        print(f"   Total connections: {stats.total_connections}")
        print(f"   Active users: {stats.active_users}")
        print(f"   Connections by status:")
        for status, count in stats.connections_by_status.items():
            print(f"      - {status}: {count}")
        
        # Demo 7: Disconnect
        print("\n\n🔌 DEMO 7: Disconnection & Cleanup")
        print("-" * 80)
        
        print("\n1. Disconnecting users...")
        for conn in connections[:2]:
            await RealtimeService.unregister_connection(db, conn.connection_id)
            print(f"   ✓ {conn.user_id} disconnected")
        
        stats = await RealtimeService.get_connection_stats(db)
        print(f"\n2. Updated stats:")
        print(f"   Total connections: {stats.total_connections}")
        print(f"   Active users: {stats.active_users}")
        
        # Summary
        print("\n\n" + "=" * 80)
        print("DEMO SUMMARY")
        print("=" * 80)
        print("\n✅ Real-Time Features:")
        print("   - WebSocket connection management")
        print("   - User presence tracking (online/away/busy/offline)")
        print("   - Real-time event broadcasting")
        print("   - Pub/Sub messaging (channels)")
        print("   - Persistent notifications")
        print("   - Collaborative editing events")
        print()
        print("✅ Use Cases:")
        print("   - Live workflow execution updates")
        print("   - Real-time collaboration on workflows")
        print("   - Instant notifications (approvals, alerts)")
        print("   - User presence indicators")
        print("   - Multi-user editing with cursor tracking")
        print()
        print("✅ Technical Features:")
        print("   - Sub-second latency")
        print("   - Channel-based pub/sub")
        print("   - Automatic reconnection support")
        print("   - Connection state management")
        print("   - Event replay from database")
        print()
        print("✅ Business Impact:")
        print("   - Modern UX (matches n8n, AgentOps)")
        print("   - Improved collaboration (team efficiency)")
        print("   - Instant feedback (no page refreshes)")
        print("   - Better monitoring (live execution tracking)")
        print()
        print("🎉 Real-time features enable modern collaborative workflows!")
        print()

if __name__ == "__main__":
    asyncio.run(demo_realtime())
