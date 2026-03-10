"""
Real-Time Collaboration Service - P1 Feature #5

Business logic for WebSocket connections, presence, and pub/sub messaging.

Key Features:
- WebSocket connection management
- Pub/Sub messaging system
- User presence tracking
- Real-time event broadcasting
- Notification delivery
"""

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, and_, or_
from typing import List, Optional, Dict, Any, Set
from datetime import datetime, timedelta
import asyncio
import json

from backend.shared.realtime_models import (
    WebSocketConnection,
    UserPresence,
    RealtimeEvent,
    Notification,
    PresenceUpdate,
    NotificationCreate,
    SubscribeRequest,
    EventPublish,
    ConnectionStats,
    ConnectionStatus,
    PresenceStatus,
    EventType,
    ChannelType,
)


class ConnectionManager:
    """
    Manages active WebSocket connections.

    In-memory registry of active connections for fast message routing.
    """

    def __init__(self):
        # connection_id -> WebSocket
        self.active_connections: Dict[str, Any] = {}
        # user_id -> Set[connection_id]
        self.user_connections: Dict[str, Set[str]] = {}
        # channel_id -> Set[connection_id]
        self.channel_subscriptions: Dict[str, Set[str]] = {}

    async def connect(self, connection_id: str, websocket: Any, user_id: str):
        """Register new connection."""
        self.active_connections[connection_id] = websocket

        if user_id not in self.user_connections:
            self.user_connections[user_id] = set()
        self.user_connections[user_id].add(connection_id)

    async def disconnect(self, connection_id: str, user_id: Optional[str] = None):
        """Remove connection."""
        if connection_id in self.active_connections:
            del self.active_connections[connection_id]

        if user_id and user_id in self.user_connections:
            self.user_connections[user_id].discard(connection_id)
            if not self.user_connections[user_id]:
                del self.user_connections[user_id]

        # Remove from all channel subscriptions
        for subscribers in self.channel_subscriptions.values():
            subscribers.discard(connection_id)

    async def subscribe(self, connection_id: str, channel: str):
        """Subscribe connection to channel."""
        if channel not in self.channel_subscriptions:
            self.channel_subscriptions[channel] = set()
        self.channel_subscriptions[channel].add(connection_id)

    async def unsubscribe(self, connection_id: str, channel: str):
        """Unsubscribe connection from channel."""
        if channel in self.channel_subscriptions:
            self.channel_subscriptions[channel].discard(connection_id)

    async def send_personal_message(self, message: Dict[str, Any], connection_id: str):
        """Send message to specific connection."""
        if connection_id in self.active_connections:
            websocket = self.active_connections[connection_id]
            try:
                await websocket.send_text(json.dumps(message))
            except Exception:
                # Connection closed, remove it
                await self.disconnect(connection_id)

    async def broadcast_to_user(self, message: Dict[str, Any], user_id: str):
        """Send message to all connections of a user."""
        if user_id in self.user_connections:
            tasks = []
            for connection_id in self.user_connections[user_id]:
                tasks.append(self.send_personal_message(message, connection_id))
            await asyncio.gather(*tasks, return_exceptions=True)

    async def broadcast_to_channel(self, message: Dict[str, Any], channel: str):
        """Send message to all subscribers of a channel."""
        if channel in self.channel_subscriptions:
            tasks = []
            for connection_id in self.channel_subscriptions[channel]:
                tasks.append(self.send_personal_message(message, connection_id))
            await asyncio.gather(*tasks, return_exceptions=True)

    def get_connection_count(self) -> int:
        """Get total active connections."""
        return len(self.active_connections)

    def get_online_users(self) -> List[str]:
        """Get list of users with active connections."""
        return list(self.user_connections.keys())

    def is_user_online(self, user_id: str) -> bool:
        """Check if user has any active connections."""
        return user_id in self.user_connections and len(self.user_connections[user_id]) > 0


# Global connection manager instance
connection_manager = ConnectionManager()


class RealtimeService:
    """Service for real-time collaboration features."""

    @staticmethod
    async def register_connection(
        db: AsyncSession,
        connection_id: str,
        user_id: str,
        session_id: Optional[str] = None,
        client_ip: Optional[str] = None,
        user_agent: Optional[str] = None,
    ) -> WebSocketConnection:
        """
        Register new WebSocket connection in database.

        Args:
            db: Database session
            connection_id: Unique connection ID
            user_id: User ID
            session_id: Session ID
            client_ip: Client IP address
            user_agent: User agent string

        Returns:
            Created connection record
        """
        connection = WebSocketConnection(
            connection_id=connection_id,
            user_id=user_id,
            session_id=session_id,
            client_ip=client_ip,
            user_agent=user_agent,
            status=ConnectionStatus.CONNECTED,
        )

        db.add(connection)
        await db.commit()
        await db.refresh(connection)

        # Update user presence to online
        await RealtimeService.update_presence(
            db,
            user_id,
            PresenceUpdate(user_id=user_id, status=PresenceStatus.ONLINE.value if hasattr(PresenceStatus.ONLINE, 'value') else 'online'),
        )

        return connection

    @staticmethod
    async def unregister_connection(
        db: AsyncSession,
        connection_id: str,
    ) -> None:
        """Mark connection as disconnected."""
        stmt = select(WebSocketConnection).where(
            WebSocketConnection.connection_id == connection_id
        )
        result = await db.execute(stmt)
        connection = result.scalar_one_or_none()

        if connection:
            connection.status = ConnectionStatus.DISCONNECTED
            connection.disconnected_at = datetime.utcnow()

            # Check if user has other connections
            stmt = select(func.count(WebSocketConnection.id)).where(
                and_(
                    WebSocketConnection.user_id == connection.user_id,
                    WebSocketConnection.status == ConnectionStatus.CONNECTED,
                    WebSocketConnection.connection_id != connection_id
                )
            )
            result = await db.execute(stmt)
            other_connections = result.scalar()

            # If no other connections, mark user offline
            if other_connections == 0:
                await RealtimeService.update_presence(
                    db,
                    connection.user_id,
                    PresenceUpdate(
                        user_id=connection.user_id,
                        status=PresenceStatus.OFFLINE.value if hasattr(PresenceStatus.OFFLINE, 'value') else 'offline'
                    ),
                )

            await db.commit()

    @staticmethod
    async def update_activity(
        db: AsyncSession,
        connection_id: str,
    ) -> None:
        """Update last activity timestamp for connection."""
        stmt = select(WebSocketConnection).where(
            WebSocketConnection.connection_id == connection_id
        )
        result = await db.execute(stmt)
        connection = result.scalar_one_or_none()

        if connection:
            connection.last_activity_at = datetime.utcnow()
            await db.commit()

    @staticmethod
    async def update_presence(
        db: AsyncSession,
        user_id: str,
        presence_data: PresenceUpdate,
    ) -> UserPresence:
        """
        Update user presence.

        Args:
            db: Database session
            user_id: User ID
            presence_data: Presence update data

        Returns:
            Updated presence record
        """
        # Get or create presence
        stmt = select(UserPresence).where(UserPresence.user_id == user_id)
        result = await db.execute(stmt)
        presence = result.scalar_one_or_none()

        if not presence:
            presence = UserPresence(user_id=user_id)
            db.add(presence)

        # Update fields
        presence.status = presence_data.status
        presence.status_message = presence_data.status_message
        presence.current_workflow_id = presence_data.current_workflow_id
        presence.current_page = presence_data.current_page
        presence.last_seen_at = datetime.utcnow()

        await db.commit()
        await db.refresh(presence)

        # Broadcast presence change
        await RealtimeService.publish_event(
            db,
            EventPublish(
                event_type=(EventType.USER_JOINED.value if hasattr(EventType.USER_JOINED, 'value') else 'USER_JOINED') if (presence_data.status == 'online' or presence_data.status == PresenceStatus.ONLINE or (hasattr(presence_data.status, 'value') and presence_data.status.value == 'online')) else (EventType.USER_LEFT.value if hasattr(EventType.USER_LEFT, 'value') else 'USER_LEFT'),
                event_data={
                    "user_id": user_id,
                    "status": presence_data.status.value if hasattr(presence_data.status, 'value') else presence_data.status,
                    "status_message": presence_data.status_message,
                },
                channel_type=ChannelType.ORGANIZATION.value if hasattr(ChannelType.ORGANIZATION, 'value') else 'ORGANIZATION',
                channel_id=f"org_1",  # Would be dynamic
                user_id=user_id,
            ),
        )

        return presence

    @staticmethod
    async def get_online_users(
        db: AsyncSession,
        organization_id: Optional[int] = None,
    ) -> List[UserPresence]:
        """Get list of online users."""
        stmt = select(UserPresence).where(
            UserPresence.status.in_(['online', 'away', 'busy'])
        )

        # In production, filter by organization
        # if organization_id:
        #     stmt = stmt.join(User).where(User.organization_id == organization_id)

        result = await db.execute(stmt)
        return result.scalars().all()

    @staticmethod
    async def publish_event(
        db: AsyncSession,
        event_data: EventPublish,
    ) -> RealtimeEvent:
        """
        Publish real-time event.

        Saves event to database and broadcasts to subscribers.

        Args:
            db: Database session
            event_data: Event to publish

        Returns:
            Created event record
        """
        # Create event record
        event = RealtimeEvent(
            event_type=event_data.event_type,
            event_data=event_data.event_data,
            user_id=event_data.user_id,
            workflow_id=event_data.workflow_id,
            task_id=event_data.task_id,
            channel_type=event_data.channel_type,
            channel_id=event_data.channel_id,
        )

        db.add(event)
        await db.commit()
        await db.refresh(event)

        # Broadcast to channel
        channel_name = f"{event_data.channel_type.value}:{event_data.channel_id}"
        message = {
            "type": "event",
            "event_type": event_data.event_type.value,
            "data": event_data.event_data,
            "timestamp": datetime.utcnow().isoformat(),
        }

        await connection_manager.broadcast_to_channel(message, channel_name)

        # Count deliveries
        if channel_name in connection_manager.channel_subscriptions:
            event.delivered_to_count = len(connection_manager.channel_subscriptions[channel_name])
            await db.commit()

        return event

    @staticmethod
    async def create_notification(
        db: AsyncSession,
        notification_data: NotificationCreate,
    ) -> Notification:
        """
        Create notification for user.

        Args:
            db: Database session
            notification_data: Notification details

        Returns:
            Created notification
        """
        notification = Notification(
            user_id=notification_data.user_id,
            title=notification_data.title,
            message=notification_data.message,
            notification_type=notification_data.notification_type,
            action_url=notification_data.action_url,
            action_label=notification_data.action_label,
            workflow_id=notification_data.workflow_id,
            task_id=notification_data.task_id,
            approval_id=notification_data.approval_id,
            priority=notification_data.priority,
            expires_at=notification_data.expires_at,
        )

        db.add(notification)
        await db.commit()
        await db.refresh(notification)

        # Send real-time notification if user is online
        if connection_manager.is_user_online(notification_data.user_id):
            message = {
                "type": "notification",
                "data": {
                    "id": notification.id,
                    "title": notification.title,
                    "message": notification.message,
                    "notification_type": notification.notification_type,
                    "action_url": notification.action_url,
                    "action_label": notification.action_label,
                    "priority": notification.priority,
                },
                "timestamp": datetime.utcnow().isoformat(),
            }
            await connection_manager.broadcast_to_user(message, notification_data.user_id)

        return notification

    @staticmethod
    async def get_notifications(
        db: AsyncSession,
        user_id: str,
        unread_only: bool = False,
        limit: int = 50,
    ) -> List[Notification]:
        """Get notifications for user."""
        stmt = select(Notification).where(
            and_(
                Notification.user_id == user_id,
                Notification.dismissed == False
            )
        )

        if unread_only:
            stmt = stmt.where(Notification.read == False)

        stmt = stmt.order_by(Notification.created_at.desc()).limit(limit)

        result = await db.execute(stmt)
        return result.scalars().all()

    @staticmethod
    async def mark_notification_read(
        db: AsyncSession,
        notification_id: int,
        user_id: str,
    ) -> Notification:
        """Mark notification as read."""
        stmt = select(Notification).where(
            and_(
                Notification.id == notification_id,
                Notification.user_id == user_id
            )
        )
        result = await db.execute(stmt)
        notification = result.scalar_one_or_none()

        if not notification:
            raise ValueError(f"Notification {notification_id} not found")

        notification.read = True
        notification.read_at = datetime.utcnow()

        await db.commit()
        await db.refresh(notification)

        return notification

    @staticmethod
    async def get_connection_stats(db: AsyncSession) -> ConnectionStats:
        """Get WebSocket connection statistics."""
        # Get total connections
        stmt = select(func.count(WebSocketConnection.id)).where(
            WebSocketConnection.status == ConnectionStatus.CONNECTED
        )
        result = await db.execute(stmt)
        total_connections = result.scalar()

        # Get connections by status
        stmt = select(
            WebSocketConnection.status,
            func.count(WebSocketConnection.id)
        ).group_by(WebSocketConnection.status)
        result = await db.execute(stmt)
        connections_by_status = {(status.value if hasattr(status, 'value') else status): count for status, count in result}

        # Get active users from connection manager
        users_online = connection_manager.get_online_users()

        return ConnectionStats(
            total_connections=total_connections or 0,
            active_users=len(users_online),
            connections_by_status=connections_by_status,
            users_online=users_online,
        )
