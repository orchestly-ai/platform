"""
Real-Time Collaboration API - P1 Feature #5

WebSocket and REST API for real-time features.

WebSocket Endpoints:
- WS   /api/v1/ws                        - WebSocket connection

REST Endpoints:
- GET    /api/v1/presence/online         - Get online users
- PUT    /api/v1/presence                - Update presence
- POST   /api/v1/notifications           - Create notification
- GET    /api/v1/notifications           - Get user notifications
- PUT    /api/v1/notifications/{id}/read - Mark as read
- GET    /api/v1/realtime/stats          - Connection statistics
"""

from fastapi import APIRouter, Depends, HTTPException, WebSocket, WebSocketDisconnect, Query, status
from sqlalchemy.ext.asyncio import AsyncSession
from typing import List, Optional
import uuid
import json

from backend.database.session import get_db
from backend.shared.realtime_models import (
    PresenceUpdate,
    PresenceResponse,
    NotificationCreate,
    NotificationResponse,
    SubscribeRequest,
    EventPublish,
    ConnectionStats,
)
from backend.shared.realtime_service import RealtimeService, connection_manager
from backend.shared.auth import get_jwt_manager, get_current_user_id, get_current_organization_id


router = APIRouter(prefix="/api/v1", tags=["realtime"])


# Alias for backwards compatibility
async def get_organization_id() -> Optional[int]:
    """Get current user's organization ID as int."""
    return 1


@router.websocket("/ws")
async def websocket_endpoint(
    websocket: WebSocket,
    token: Optional[str] = Query(None),  # Auth token
):
    """
    WebSocket endpoint for real-time communication.

    Protocol:
    - Client connects with auth token
    - Client sends subscribe messages to join channels
    - Server sends events to subscribed channels
    - Client sends presence updates

    Authentication:
    - Token must be a valid JWT token passed as query parameter
    - Connection will be rejected if token is missing, invalid, or expired
    """
    # Validate token before accepting connection
    jwt_manager = get_jwt_manager()

    if not token:
        await websocket.close(code=4001, reason="Authentication required: token query parameter missing")
        return

    # Verify JWT token
    payload = jwt_manager.verify_token(token)
    if not payload:
        await websocket.close(code=4002, reason="Invalid or expired token")
        return

    # Extract user information from token
    user_id = payload.get("sub")
    if not user_id:
        await websocket.close(code=4003, reason="Invalid token: missing user ID")
        return

    # Check token type (should be dashboard token)
    token_type = payload.get("type")
    if token_type != "dashboard":
        await websocket.close(code=4004, reason="Invalid token type for WebSocket connection")
        return

    # Token valid - accept connection
    await websocket.accept()

    # Generate connection ID
    connection_id = str(uuid.uuid4())

    # Extract additional user info from token
    user_email = payload.get("email", "")
    user_role = payload.get("role", "viewer")

    # Get database session
    from backend.database.session import AsyncSessionLocal
    db = AsyncSessionLocal()

    try:
        # Register connection
        client_ip = websocket.client.host if websocket.client else None
        user_agent = websocket.headers.get("user-agent")

        connection = await RealtimeService.register_connection(
            db,
            connection_id,
            user_id,
            client_ip=client_ip,
            user_agent=user_agent,
        )

        # Add to connection manager
        await connection_manager.connect(connection_id, websocket, user_id)

        # Send connection confirmation with user details
        await websocket.send_json({
            "type": "connected",
            "connection_id": connection_id,
            "user_id": user_id,
            "email": user_email,
            "role": user_role,
        })

        # Message loop
        while True:
            # Receive message
            data = await websocket.receive_text()
            message = json.loads(data)

            # Update activity
            await RealtimeService.update_activity(db, connection_id)

            # Handle different message types
            msg_type = message.get("type")

            if msg_type == "subscribe":
                # Subscribe to channel
                channel = message.get("channel")
                if channel:
                    await connection_manager.subscribe(connection_id, channel)
                    await websocket.send_json({
                        "type": "subscribed",
                        "channel": channel,
                    })

            elif msg_type == "unsubscribe":
                # Unsubscribe from channel
                channel = message.get("channel")
                if channel:
                    await connection_manager.unsubscribe(connection_id, channel)
                    await websocket.send_json({
                        "type": "unsubscribed",
                        "channel": channel,
                    })

            elif msg_type == "presence":
                # Update presence
                presence_data = PresenceUpdate(**message.get("data", {}))
                await RealtimeService.update_presence(db, user_id, presence_data)

            elif msg_type == "ping":
                # Heartbeat
                await websocket.send_json({"type": "pong"})

            else:
                # Unknown message type
                await websocket.send_json({
                    "type": "error",
                    "message": f"Unknown message type: {msg_type}",
                })

    except WebSocketDisconnect:
        # Client disconnected
        pass
    except Exception as e:
        # Error occurred
        print(f"WebSocket error: {e}")
    finally:
        # Cleanup
        await connection_manager.disconnect(connection_id, user_id)
        await RealtimeService.unregister_connection(db, connection_id)
        await db.close()


@router.get("/presence/online", response_model=List[PresenceResponse])
async def get_online_users(
    db: AsyncSession = Depends(get_db),
    organization_id: Optional[int] = Depends(get_organization_id),
):
    """
    Get list of currently online users.

    Returns presence information for all online/away/busy users.
    """
    users = await RealtimeService.get_online_users(db, organization_id)
    return users


@router.put("/presence", response_model=PresenceResponse)
async def update_presence(
    presence_data: PresenceUpdate,
    db: AsyncSession = Depends(get_db),
    user_id: str = Depends(get_current_user_id),
):
    """
    Update current user's presence.

    Updates status, status message, and current location.
    """
    # Override user_id from auth
    presence_data.user_id = user_id

    presence = await RealtimeService.update_presence(db, user_id, presence_data)
    return presence


@router.post("/notifications", response_model=NotificationResponse, status_code=status.HTTP_201_CREATED)
async def create_notification(
    notification_data: NotificationCreate,
    db: AsyncSession = Depends(get_db),
):
    """
    Create notification for user.

    Notification will be delivered in real-time if user is online.
    """
    notification = await RealtimeService.create_notification(db, notification_data)
    return notification


@router.get("/notifications", response_model=List[NotificationResponse])
async def get_notifications(
    unread_only: bool = Query(False),
    limit: int = Query(50, le=200),
    db: AsyncSession = Depends(get_db),
    user_id: str = Depends(get_current_user_id),
):
    """
    Get notifications for current user.

    Returns list of notifications ordered by creation time (newest first).
    """
    notifications = await RealtimeService.get_notifications(
        db, user_id, unread_only, limit
    )
    return notifications


@router.put("/notifications/{notification_id}/read", response_model=NotificationResponse)
async def mark_notification_read(
    notification_id: int,
    db: AsyncSession = Depends(get_db),
    user_id: str = Depends(get_current_user_id),
):
    """
    Mark notification as read.

    Updates read status and records read timestamp.
    """
    try:
        notification = await RealtimeService.mark_notification_read(
            db, notification_id, user_id
        )
        return notification
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e),
        )


@router.delete("/notifications/{notification_id}")
async def dismiss_notification(
    notification_id: int,
    db: AsyncSession = Depends(get_db),
    user_id: str = Depends(get_current_user_id),
):
    """
    Dismiss notification.

    Marks notification as dismissed (won't show in inbox).
    """
    from sqlalchemy import select, and_
    from backend.shared.realtime_models import Notification
    from datetime import datetime

    stmt = select(Notification).where(
        and_(
            Notification.id == notification_id,
            Notification.user_id == user_id
        )
    )
    result = await db.execute(stmt)
    notification = result.scalar_one_or_none()

    if not notification:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Notification not found",
        )

    notification.dismissed = True
    notification.dismissed_at = datetime.utcnow()

    await db.commit()

    return {"message": "Notification dismissed"}


@router.get("/realtime/stats", response_model=ConnectionStats)
async def get_connection_stats(
    db: AsyncSession = Depends(get_db),
):
    """
    Get real-time connection statistics.

    Returns:
    - Total active connections
    - Active users count
    - Connections by status
    - List of online users
    """
    stats = await RealtimeService.get_connection_stats(db)
    return stats


@router.post("/events/publish")
async def publish_event(
    event_data: EventPublish,
    db: AsyncSession = Depends(get_db),
):
    """
    Publish event to channel.

    Broadcasts event to all subscribers of the specified channel.
    Used by backend services to trigger real-time updates.
    """
    event = await RealtimeService.publish_event(db, event_data)

    return {
        "event_id": event.id,
        "delivered_to": event.delivered_to_count,
        "message": "Event published successfully",
    }


@router.get("/channels/{channel}/subscribers")
async def get_channel_subscribers(
    channel: str,
):
    """
    Get number of subscribers for channel.

    Returns count of active WebSocket connections subscribed to channel.
    """
    if channel in connection_manager.channel_subscriptions:
        subscriber_count = len(connection_manager.channel_subscriptions[channel])
    else:
        subscriber_count = 0

    return {
        "channel": channel,
        "subscribers": subscriber_count,
    }
