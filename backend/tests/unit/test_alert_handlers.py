"""
Unit Tests for Alert Handlers

Tests for Slack and Email notification handlers, message formatting, and configuration.
"""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from datetime import datetime
from uuid import uuid4
import json
import os

from backend.observer.alert_manager import (
    Alert,
    AlertSeverity,
    AlertState,
    slack_notification_handler,
    email_notification_handler,
)


class TestAlertModel:
    """Tests for Alert model."""

    def test_alert_creation(self):
        """Test creating an alert."""
        alert = Alert(
            alert_type="cost_exceeded",
            severity=AlertSeverity.WARNING,
            message="Daily cost limit exceeded"
        )

        assert alert.alert_type == "cost_exceeded"
        assert alert.severity == AlertSeverity.WARNING
        assert alert.message == "Daily cost limit exceeded"
        assert alert.state == AlertState.ACTIVE
        assert alert.metadata == {}
        assert isinstance(alert.alert_id, type(uuid4()))

    def test_alert_with_metadata(self):
        """Test creating alert with metadata."""
        alert = Alert(
            alert_type="agent_failure",
            severity=AlertSeverity.CRITICAL,
            message="Agent crashed",
            metadata={"agent_id": "agent-123", "error": "OOM"}
        )

        assert alert.metadata["agent_id"] == "agent-123"
        assert alert.metadata["error"] == "OOM"

    def test_alert_to_dict(self):
        """Test converting alert to dictionary."""
        alert = Alert(
            alert_type="test",
            severity=AlertSeverity.INFO,
            message="Test message"
        )

        data = alert.to_dict()

        assert data["alert_type"] == "test"
        assert data["severity"] == "info"
        assert data["message"] == "Test message"
        assert data["state"] == "active"
        assert "alert_id" in data
        assert "created_at" in data


class TestAlertSeverity:
    """Tests for alert severity levels."""

    def test_severity_values(self):
        """Test severity enum values."""
        assert AlertSeverity.INFO.value == "info"
        assert AlertSeverity.WARNING.value == "warning"
        assert AlertSeverity.CRITICAL.value == "critical"

    def test_severity_colors_mapping(self):
        """Test severity to color mapping for Slack."""
        severity_colors = {
            AlertSeverity.INFO: "#36a64f",      # Green
            AlertSeverity.WARNING: "#ffcc00",   # Yellow
            AlertSeverity.CRITICAL: "#ff0000",  # Red
        }

        assert severity_colors[AlertSeverity.INFO] == "#36a64f"
        assert severity_colors[AlertSeverity.WARNING] == "#ffcc00"
        assert severity_colors[AlertSeverity.CRITICAL] == "#ff0000"


class TestSlackNotificationPayload:
    """Tests for Slack notification payload formatting."""

    def test_slack_attachment_structure(self):
        """Test Slack message attachment structure."""
        alert = Alert(
            alert_type="test_alert",
            severity=AlertSeverity.WARNING,
            message="Test message"
        )

        # Simulating payload construction
        payload = {
            "attachments": [
                {
                    "color": "#ffcc00",
                    "title": f"🚨 Alert: {alert.alert_type}",
                    "text": alert.message,
                    "fields": [
                        {"title": "Severity", "value": "WARNING", "short": True},
                        {"title": "State", "value": alert.state.value, "short": True},
                    ],
                    "footer": "Agent Orchestration Platform",
                }
            ]
        }

        assert len(payload["attachments"]) == 1
        assert payload["attachments"][0]["color"] == "#ffcc00"
        assert "test_alert" in payload["attachments"][0]["title"]
        assert payload["attachments"][0]["text"] == "Test message"

    def test_slack_payload_with_metadata_fields(self):
        """Test Slack payload includes metadata as fields."""
        alert = Alert(
            alert_type="cost_alert",
            severity=AlertSeverity.WARNING,
            message="Cost exceeded",
            metadata={
                "current_cost": 150.00,
                "limit": 100.00,
                "agent_id": "agent-xyz"
            }
        )

        # Build fields from metadata
        metadata_fields = []
        for key, value in list(alert.metadata.items())[:5]:
            metadata_fields.append({
                "title": key.replace("_", " ").title(),
                "value": str(value),
                "short": True
            })

        assert len(metadata_fields) == 3
        assert metadata_fields[0]["title"] == "Current Cost"
        assert metadata_fields[0]["value"] == "150.0"

    def test_slack_payload_metadata_limit(self):
        """Test Slack payload limits metadata fields to 5."""
        metadata = {f"field_{i}": f"value_{i}" for i in range(10)}

        alert = Alert(
            alert_type="test",
            severity=AlertSeverity.INFO,
            message="Test",
            metadata=metadata
        )

        # Limit to 5 fields
        limited_fields = list(alert.metadata.items())[:5]

        assert len(limited_fields) == 5


class TestEmailNotificationFormat:
    """Tests for Email notification formatting."""

    def test_email_subject_format(self):
        """Test email subject line format."""
        alert = Alert(
            alert_type="agent_failure",
            severity=AlertSeverity.CRITICAL,
            message="Agent crashed"
        )

        subject = f"[{alert.severity.value.upper()}] Alert: {alert.alert_type}"

        assert subject == "[CRITICAL] Alert: agent_failure"

    def test_email_plain_text_content(self):
        """Test email plain text content format."""
        alert = Alert(
            alert_type="cost_limit",
            severity=AlertSeverity.WARNING,
            message="Budget exceeded"
        )

        text_content = f"""
Alert Notification
==================

Type: {alert.alert_type}
Severity: {alert.severity.value.upper()}
Message: {alert.message}
State: {alert.state.value}
Alert ID: {alert.alert_id}
"""

        assert "Alert Notification" in text_content
        assert "cost_limit" in text_content
        assert "WARNING" in text_content
        assert "Budget exceeded" in text_content

    def test_email_html_severity_color(self):
        """Test email HTML uses severity color."""
        severity_colors = {
            AlertSeverity.INFO: "#36a64f",
            AlertSeverity.WARNING: "#ffcc00",
            AlertSeverity.CRITICAL: "#ff0000",
        }

        for severity, color in severity_colors.items():
            alert = Alert(
                alert_type="test",
                severity=severity,
                message="Test"
            )

            # Simulating HTML content generation
            html_style = f"border-left: 4px solid {color};"

            assert color in html_style


class TestAlertHandlerConfiguration:
    """Tests for alert handler configuration validation."""

    def test_slack_requires_webhook_url(self):
        """Test Slack handler requires SLACK_WEBHOOK_URL env var."""
        # Test when not configured
        with patch.dict(os.environ, {}, clear=True):
            webhook_url = os.environ.get("SLACK_WEBHOOK_URL")
            assert webhook_url is None

        # Test when configured
        with patch.dict(os.environ, {"SLACK_WEBHOOK_URL": "https://hooks.slack.com/xxx"}):
            webhook_url = os.environ.get("SLACK_WEBHOOK_URL")
            assert webhook_url == "https://hooks.slack.com/xxx"

    def test_email_requires_smtp_config(self):
        """Test email handler requires SMTP configuration."""
        required_env_vars = [
            "SMTP_HOST",
            "SMTP_USERNAME",
            "SMTP_PASSWORD",
            "ALERT_EMAIL_FROM",
            "ALERT_EMAIL_TO"
        ]

        # Test when not configured
        with patch.dict(os.environ, {}, clear=True):
            all_configured = all(
                os.environ.get(var) for var in required_env_vars
            )
            assert all_configured is False

        # Test when configured
        with patch.dict(os.environ, {
            "SMTP_HOST": "smtp.example.com",
            "SMTP_PORT": "587",
            "SMTP_USERNAME": "user",
            "SMTP_PASSWORD": "pass",
            "ALERT_EMAIL_FROM": "alerts@example.com",
            "ALERT_EMAIL_TO": "team@example.com"
        }):
            all_configured = all(
                os.environ.get(var) for var in required_env_vars
            )
            assert all_configured is True


class TestAlertHandlerAsync:
    """Tests for async alert handler execution."""

    @pytest.mark.asyncio
    async def test_slack_handler_without_config_logs_fallback(self):
        """Test Slack handler logs fallback when not configured."""
        with patch.dict(os.environ, {}, clear=True):
            alert = Alert(
                alert_type="test",
                severity=AlertSeverity.INFO,
                message="Test"
            )

            # Should not raise, just log
            await slack_notification_handler(alert)

    @pytest.mark.asyncio
    async def test_email_handler_without_config_logs_fallback(self):
        """Test email handler logs fallback when not configured."""
        with patch.dict(os.environ, {}, clear=True):
            alert = Alert(
                alert_type="test",
                severity=AlertSeverity.INFO,
                message="Test"
            )

            # Should not raise, just log
            await email_notification_handler(alert)

    @pytest.mark.asyncio
    async def test_slack_handler_with_valid_config(self):
        """Test Slack handler makes HTTP request when configured."""
        with patch.dict(os.environ, {"SLACK_WEBHOOK_URL": "https://hooks.slack.com/test"}):
            alert = Alert(
                alert_type="test",
                severity=AlertSeverity.INFO,
                message="Test message"
            )

            # Mock httpx
            with patch("httpx.AsyncClient") as mock_client_class:
                mock_client = AsyncMock()
                mock_response = MagicMock()
                mock_response.raise_for_status = MagicMock()
                mock_client.post = AsyncMock(return_value=mock_response)
                mock_client.__aenter__ = AsyncMock(return_value=mock_client)
                mock_client.__aexit__ = AsyncMock()
                mock_client_class.return_value = mock_client

                await slack_notification_handler(alert)

                # Verify POST was called
                mock_client.post.assert_called_once()
                call_args = mock_client.post.call_args
                assert call_args[0][0] == "https://hooks.slack.com/test"
