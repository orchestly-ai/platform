"""
Alert Manager - Manages alerts and notifications for the orchestration platform.
"""

import asyncio
import os
import smtplib
import logging
from datetime import datetime, timedelta, timezone
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from typing import Dict, List, Optional, Callable
from uuid import UUID, uuid4
from enum import Enum

from backend.shared.config import get_settings
from backend.observer.metrics_collector import get_collector

logger = logging.getLogger(__name__)


class AlertSeverity(str, Enum):
    """Alert severity levels."""
    INFO = "info"
    WARNING = "warning"
    CRITICAL = "critical"


class AlertState(str, Enum):
    """Alert states."""
    ACTIVE = "active"
    ACKNOWLEDGED = "acknowledged"
    RESOLVED = "resolved"


class Alert:
    """Represents an alert."""

    def __init__(
        self,
        alert_type: str,
        severity: AlertSeverity,
        message: str,
        metadata: Optional[Dict] = None,
        organization_id: Optional[str] = None,
    ):
        self.alert_id = uuid4()
        self.alert_type = alert_type
        self.severity = severity
        self.message = message
        self.metadata = metadata or {}
        self.organization_id = organization_id
        self.state = AlertState.ACTIVE
        self.created_at = datetime.now(timezone.utc)
        self.acknowledged_at: Optional[datetime] = None
        self.resolved_at: Optional[datetime] = None

    def to_dict(self) -> Dict:
        """Convert alert to dictionary."""
        return {
            "alert_id": str(self.alert_id),
            "alert_type": self.alert_type,
            "severity": self.severity.value,
            "message": self.message,
            "metadata": self.metadata,
            "organization_id": self.organization_id,
            "state": self.state.value,
            "created_at": self.created_at.isoformat(),
            "acknowledged_at": self.acknowledged_at.isoformat() if self.acknowledged_at else None,
            "resolved_at": self.resolved_at.isoformat() if self.resolved_at else None,
        }


class AlertManager:
    """
    Manages alerts and notifications.

    Features:
    - Alert detection and creation
    - Alert deduplication
    - Alert lifecycle management
    - Notification dispatch
    - Alert history
    """

    def __init__(self):
        """Initialize alert manager."""
        self.settings = get_settings()
        self.collector = get_collector()

        # Active alerts (keyed by alert_type + metadata signature)
        self.active_alerts: Dict[str, Alert] = {}

        # Alert history (last 1000 alerts)
        self.alert_history: List[Alert] = []
        self.max_history = 1000

        # Notification handlers
        self.notification_handlers: List[Callable] = []

        # Alert cooldown (prevent spam)
        self.alert_cooldowns: Dict[str, datetime] = {}
        self.cooldown_seconds = 300  # 5 minutes

    def _get_alert_key(self, alert_type: str, metadata: Dict) -> str:
        """
        Generate unique key for alert deduplication.

        Args:
            alert_type: Alert type
            metadata: Alert metadata

        Returns:
            Alert key string
        """
        # Create signature from metadata
        sig_parts = [alert_type]

        if "capability" in metadata:
            sig_parts.append(f"cap:{metadata['capability']}")
        if "agent_id" in metadata:
            sig_parts.append(f"agent:{metadata['agent_id']}")

        return "|".join(sig_parts)

    def _is_in_cooldown(self, alert_key: str) -> bool:
        """
        Check if alert is in cooldown period.

        Args:
            alert_key: Alert key

        Returns:
            True if in cooldown
        """
        if alert_key not in self.alert_cooldowns:
            return False

        last_alert_time = self.alert_cooldowns[alert_key]
        elapsed = (datetime.now(timezone.utc) - last_alert_time).total_seconds()

        return elapsed < self.cooldown_seconds

    async def check_and_create_alerts(self) -> List[Alert]:
        """
        Check for alert conditions and create new alerts.

        Returns:
            List of newly created alerts
        """
        # Get alert conditions from collector
        alert_conditions = await self.collector.check_alerts()

        new_alerts = []

        for condition in alert_conditions:
            alert_type = condition["type"]
            severity = AlertSeverity(condition["severity"])
            message = condition["message"]

            # Extract metadata
            metadata = {k: v for k, v in condition.items() if k not in ["type", "severity", "message"]}

            # Check for existing active alert
            alert_key = self._get_alert_key(alert_type, metadata)

            # Skip if in cooldown
            if self._is_in_cooldown(alert_key):
                continue

            # Check if alert already exists
            if alert_key in self.active_alerts:
                # Update existing alert
                existing_alert = self.active_alerts[alert_key]
                existing_alert.metadata.update(metadata)
                continue

            # Create new alert
            alert = Alert(
                alert_type=alert_type,
                severity=severity,
                message=message,
                metadata=metadata
            )

            # Store alert
            self.active_alerts[alert_key] = alert
            self.alert_history.append(alert)

            # Trim history
            if len(self.alert_history) > self.max_history:
                self.alert_history = self.alert_history[-self.max_history:]

            # Set cooldown
            self.alert_cooldowns[alert_key] = datetime.now(timezone.utc)

            # Dispatch notifications
            await self._dispatch_notifications(alert)

            new_alerts.append(alert)

            print(f"🚨 Alert created: {alert.severity.value.upper()}")
            print(f"   Type: {alert.alert_type}")
            print(f"   Message: {alert.message}")

        return new_alerts

    async def _dispatch_notifications(self, alert: Alert) -> None:
        """
        Dispatch alert to notification handlers.

        Args:
            alert: Alert to dispatch
        """
        for handler in self.notification_handlers:
            try:
                await handler(alert)
            except Exception as e:
                print(f"⚠️  Notification handler failed: {e}")

    def register_notification_handler(self, handler: Callable) -> None:
        """
        Register a notification handler.

        Args:
            handler: Async function that receives Alert objects
        """
        self.notification_handlers.append(handler)
        print(f"📢 Registered notification handler: {handler.__name__}")

    async def acknowledge_alert(self, alert_id: UUID) -> bool:
        """
        Acknowledge an alert.

        Args:
            alert_id: Alert ID

        Returns:
            True if acknowledged
        """
        for alert_key, alert in self.active_alerts.items():
            if alert.alert_id == alert_id:
                alert.state = AlertState.ACKNOWLEDGED
                alert.acknowledged_at = datetime.now(timezone.utc)

                print(f"✅ Alert {alert_id} acknowledged")
                return True

        return False

    async def resolve_alert(self, alert_id: UUID) -> bool:
        """
        Resolve an alert.

        Args:
            alert_id: Alert ID

        Returns:
            True if resolved
        """
        for alert_key, alert in list(self.active_alerts.items()):
            if alert.alert_id == alert_id:
                alert.state = AlertState.RESOLVED
                alert.resolved_at = datetime.now(timezone.utc)

                # Remove from active alerts
                del self.active_alerts[alert_key]

                print(f"✅ Alert {alert_id} resolved")
                return True

        return False

    async def auto_resolve_alerts(self) -> int:
        """
        Automatically resolve alerts whose conditions are no longer present.

        Returns:
            Number of alerts resolved
        """
        # Get current alert conditions
        current_conditions = await self.collector.check_alerts()

        # Build set of current alert keys
        current_keys = set()
        for condition in current_conditions:
            alert_type = condition["type"]
            metadata = {k: v for k, v in condition.items() if k not in ["type", "severity", "message"]}
            alert_key = self._get_alert_key(alert_type, metadata)
            current_keys.add(alert_key)

        # Resolve alerts not in current conditions
        resolved_count = 0
        for alert_key in list(self.active_alerts.keys()):
            if alert_key not in current_keys:
                alert = self.active_alerts[alert_key]
                await self.resolve_alert(alert.alert_id)
                resolved_count += 1

        if resolved_count > 0:
            print(f"✅ Auto-resolved {resolved_count} alerts")

        return resolved_count

    def get_active_alerts(
        self,
        severity: Optional[AlertSeverity] = None,
        alert_type: Optional[str] = None,
        organization_id: Optional[str] = None,
    ) -> List[Alert]:
        """
        Get active alerts, optionally filtered by organization.

        Args:
            severity: Filter by severity (optional)
            alert_type: Filter by type (optional)
            organization_id: Filter by organization (optional)

        Returns:
            List of active alerts
        """
        alerts = list(self.active_alerts.values())

        if organization_id:
            alerts = [a for a in alerts if a.organization_id == organization_id]

        if severity:
            alerts = [a for a in alerts if a.severity == severity]

        if alert_type:
            alerts = [a for a in alerts if a.alert_type == alert_type]

        return alerts

    def get_alert_history(
        self,
        hours: int = 24,
        severity: Optional[AlertSeverity] = None,
        organization_id: Optional[str] = None,
    ) -> List[Alert]:
        """
        Get alert history, optionally filtered by organization.

        Args:
            hours: Look back period in hours
            severity: Filter by severity (optional)
            organization_id: Filter by organization (optional)

        Returns:
            List of historical alerts
        """
        cutoff_time = datetime.now(timezone.utc) - timedelta(hours=hours)

        alerts = [
            a for a in self.alert_history
            if a.created_at >= cutoff_time
        ]

        if organization_id:
            alerts = [a for a in alerts if a.organization_id == organization_id]

        if severity:
            alerts = [a for a in alerts if a.severity == severity]

        return alerts

    def get_alert_stats(self) -> Dict:
        """
        Get alert statistics.

        Returns:
            Alert statistics
        """
        active_alerts = list(self.active_alerts.values())
        history_24h = self.get_alert_history(hours=24)

        return {
            "active": {
                "total": len(active_alerts),
                "critical": len([a for a in active_alerts if a.severity == AlertSeverity.CRITICAL]),
                "warning": len([a for a in active_alerts if a.severity == AlertSeverity.WARNING]),
                "info": len([a for a in active_alerts if a.severity == AlertSeverity.INFO]),
            },
            "last_24h": {
                "total": len(history_24h),
                "critical": len([a for a in history_24h if a.severity == AlertSeverity.CRITICAL]),
                "warning": len([a for a in history_24h if a.severity == AlertSeverity.WARNING]),
                "info": len([a for a in history_24h if a.severity == AlertSeverity.INFO]),
            }
        }

    async def run_monitoring_loop(self, interval_seconds: int = 30) -> None:
        """
        Run continuous monitoring loop.

        Args:
            interval_seconds: Check interval
        """
        print(f"🔍 Starting alert monitoring loop (interval: {interval_seconds}s)")

        while True:
            try:
                # Check for new alerts
                await self.check_and_create_alerts()

                # Auto-resolve cleared alerts
                await self.auto_resolve_alerts()

                # Wait for next check
                await asyncio.sleep(interval_seconds)

            except Exception as e:
                print(f"⚠️  Error in monitoring loop: {e}")
                await asyncio.sleep(interval_seconds)


# Global alert manager instance
_alert_manager: Optional[AlertManager] = None


def get_alert_manager() -> AlertManager:
    """Get or create global alert manager instance."""
    global _alert_manager
    if _alert_manager is None:
        _alert_manager = AlertManager()
    return _alert_manager


# Example notification handlers

async def console_notification_handler(alert: Alert) -> None:
    """
    Simple console notification handler.

    Args:
        alert: Alert to handle
    """
    print(f"\n{'='*60}")
    print(f"ALERT: {alert.severity.value.upper()}")
    print(f"Type: {alert.alert_type}")
    print(f"Message: {alert.message}")
    print(f"Time: {alert.created_at.isoformat()}")
    if alert.metadata:
        print(f"Metadata: {alert.metadata}")
    print(f"{'='*60}\n")


async def slack_notification_handler(alert: Alert) -> None:
    """
    Slack notification handler using incoming webhooks.

    Requires SLACK_WEBHOOK_URL environment variable to be set.

    Args:
        alert: Alert to handle
    """
    webhook_url = os.environ.get("SLACK_WEBHOOK_URL")

    if not webhook_url:
        logger.warning("SLACK_WEBHOOK_URL not configured, skipping Slack notification")
        print(f"📤 Would send Slack notification for alert: {alert.alert_id}")
        return

    try:
        import httpx

        # Map severity to Slack color
        severity_colors = {
            AlertSeverity.INFO: "#36a64f",      # Green
            AlertSeverity.WARNING: "#ffcc00",   # Yellow
            AlertSeverity.CRITICAL: "#ff0000",  # Red
        }

        # Build Slack message payload
        payload = {
            "attachments": [
                {
                    "color": severity_colors.get(alert.severity, "#808080"),
                    "title": f"🚨 Alert: {alert.alert_type}",
                    "text": alert.message,
                    "fields": [
                        {
                            "title": "Severity",
                            "value": alert.severity.value.upper(),
                            "short": True
                        },
                        {
                            "title": "State",
                            "value": alert.state.value,
                            "short": True
                        },
                        {
                            "title": "Alert ID",
                            "value": str(alert.alert_id),
                            "short": True
                        },
                        {
                            "title": "Created At",
                            "value": alert.created_at.strftime("%Y-%m-%d %H:%M:%S UTC"),
                            "short": True
                        }
                    ],
                    "footer": "Agent Orchestration Platform",
                    "ts": int(alert.created_at.timestamp())
                }
            ]
        }

        # Add metadata fields if present
        if alert.metadata:
            for key, value in list(alert.metadata.items())[:5]:  # Limit to 5 fields
                payload["attachments"][0]["fields"].append({
                    "title": key.replace("_", " ").title(),
                    "value": str(value),
                    "short": True
                })

        async with httpx.AsyncClient() as client:
            response = await client.post(
                webhook_url,
                json=payload,
                timeout=10.0
            )
            response.raise_for_status()
            logger.info(f"Sent Slack notification for alert {alert.alert_id}")

    except ImportError:
        logger.error("httpx not installed. Install with: pip install httpx")
    except Exception as e:
        logger.error(f"Failed to send Slack notification for alert {alert.alert_id}: {e}")


async def email_notification_handler(alert: Alert) -> None:
    """
    Email notification handler using SMTP.

    Requires these environment variables:
    - SMTP_HOST: SMTP server hostname
    - SMTP_PORT: SMTP server port (default: 587)
    - SMTP_USERNAME: SMTP username
    - SMTP_PASSWORD: SMTP password
    - ALERT_EMAIL_FROM: Sender email address
    - ALERT_EMAIL_TO: Recipient email address(es), comma-separated

    Args:
        alert: Alert to handle
    """
    smtp_host = os.environ.get("SMTP_HOST")
    smtp_port = int(os.environ.get("SMTP_PORT", "587"))
    smtp_username = os.environ.get("SMTP_USERNAME")
    smtp_password = os.environ.get("SMTP_PASSWORD")
    email_from = os.environ.get("ALERT_EMAIL_FROM")
    email_to = os.environ.get("ALERT_EMAIL_TO")

    if not all([smtp_host, smtp_username, smtp_password, email_from, email_to]):
        logger.warning("Email configuration incomplete, skipping email notification")
        print(f"📧 Would send email notification for alert: {alert.alert_id}")
        return

    try:
        # Build email
        msg = MIMEMultipart("alternative")
        msg["Subject"] = f"[{alert.severity.value.upper()}] Alert: {alert.alert_type}"
        msg["From"] = email_from
        msg["To"] = email_to

        # Plain text version
        text_content = f"""
Alert Notification
==================

Type: {alert.alert_type}
Severity: {alert.severity.value.upper()}
Message: {alert.message}
State: {alert.state.value}
Alert ID: {alert.alert_id}
Created: {alert.created_at.strftime("%Y-%m-%d %H:%M:%S UTC")}

"""
        if alert.metadata:
            text_content += "Metadata:\n"
            for key, value in alert.metadata.items():
                text_content += f"  {key}: {value}\n"

        text_content += """
---
Agent Orchestration Platform
"""

        # HTML version
        severity_colors = {
            AlertSeverity.INFO: "#36a64f",
            AlertSeverity.WARNING: "#ffcc00",
            AlertSeverity.CRITICAL: "#ff0000",
        }
        color = severity_colors.get(alert.severity, "#808080")

        html_content = f"""
<!DOCTYPE html>
<html>
<head>
    <style>
        body {{ font-family: Arial, sans-serif; margin: 20px; }}
        .alert-box {{ border-left: 4px solid {color}; padding: 15px; background: #f9f9f9; }}
        .severity {{ color: {color}; font-weight: bold; }}
        .metadata {{ margin-top: 15px; }}
        .metadata dt {{ font-weight: bold; }}
        .footer {{ margin-top: 20px; color: #666; font-size: 12px; }}
    </style>
</head>
<body>
    <h2>🚨 Alert Notification</h2>
    <div class="alert-box">
        <h3>{alert.alert_type}</h3>
        <p><strong>Severity:</strong> <span class="severity">{alert.severity.value.upper()}</span></p>
        <p><strong>Message:</strong> {alert.message}</p>
        <p><strong>State:</strong> {alert.state.value}</p>
        <p><strong>Alert ID:</strong> {alert.alert_id}</p>
        <p><strong>Created:</strong> {alert.created_at.strftime("%Y-%m-%d %H:%M:%S UTC")}</p>
"""
        if alert.metadata:
            html_content += """
        <div class="metadata">
            <h4>Additional Details:</h4>
            <dl>
"""
            for key, value in alert.metadata.items():
                html_content += f"                <dt>{key}</dt><dd>{value}</dd>\n"
            html_content += """
            </dl>
        </div>
"""
        html_content += """
    </div>
    <div class="footer">
        <p>Agent Orchestration Platform</p>
    </div>
</body>
</html>
"""

        msg.attach(MIMEText(text_content, "plain"))
        msg.attach(MIMEText(html_content, "html"))

        # Send email in thread pool to avoid blocking
        def send_email():
            with smtplib.SMTP(smtp_host, smtp_port) as server:
                server.starttls()
                server.login(smtp_username, smtp_password)
                server.send_message(msg)

        # Run in executor to avoid blocking
        loop = asyncio.get_event_loop()
        await loop.run_in_executor(None, send_email)

        logger.info(f"Sent email notification for alert {alert.alert_id} to {email_to}")

    except Exception as e:
        logger.error(f"Failed to send email notification for alert {alert.alert_id}: {e}")
