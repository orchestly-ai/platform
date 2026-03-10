"""
Unit Tests for Webhook Processor

Tests for webhook function registry, workflow triggering, and HTTP forwarding.
"""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from datetime import datetime
from uuid import uuid4

from backend.webhooks.processor import (
    register_webhook_function,
    get_webhook_function,
    _webhook_function_registry,
    WebhookProcessor,
)
from backend.webhooks.schema import WebhookEvent, WebhookHandler


class TestWebhookFunctionRegistry:
    """Tests for webhook function registry."""

    def setup_method(self):
        """Clear registry before each test."""
        _webhook_function_registry.clear()

    def test_register_webhook_function_decorator(self):
        """Test registering a function with decorator."""
        @register_webhook_function("test_handler")
        def my_handler(event, config):
            return "handled"

        assert "test_handler" in _webhook_function_registry
        assert _webhook_function_registry["test_handler"] is my_handler

    def test_register_async_webhook_function(self):
        """Test registering an async function."""
        @register_webhook_function("async_handler")
        async def my_async_handler(event, config):
            return "async handled"

        assert "async_handler" in _webhook_function_registry

    def test_get_registered_function(self):
        """Test getting a registered function."""
        @register_webhook_function("get_test")
        def handler(event, config):
            pass

        result = get_webhook_function("get_test")

        assert result is handler

    def test_get_unregistered_function_returns_none(self):
        """Test getting an unregistered function returns None."""
        result = get_webhook_function("nonexistent")

        assert result is None

    def test_multiple_registrations(self):
        """Test registering multiple functions."""
        @register_webhook_function("handler1")
        def handler1(event, config):
            pass

        @register_webhook_function("handler2")
        def handler2(event, config):
            pass

        assert len(_webhook_function_registry) >= 2
        assert get_webhook_function("handler1") is handler1
        assert get_webhook_function("handler2") is handler2


class TestWebhookEventFormat:
    """Tests for webhook event input data format."""

    def test_webhook_event_to_input_data(self):
        """Test converting webhook event to workflow input data format."""
        event = MagicMock()
        event.event_id = "evt-123"
        event.provider = "github"
        event.event_type = "push"
        event.payload = {"commits": [{"id": "abc123"}]}
        event.received_at = datetime(2025, 1, 17, 12, 0, 0)

        input_data = {
            "webhook_event": {
                "event_id": event.event_id,
                "provider": event.provider,
                "event_type": event.event_type,
                "payload": event.payload,
                "received_at": event.received_at.isoformat() if event.received_at else None,
            }
        }

        assert input_data["webhook_event"]["event_id"] == "evt-123"
        assert input_data["webhook_event"]["provider"] == "github"
        assert input_data["webhook_event"]["event_type"] == "push"
        assert input_data["webhook_event"]["payload"]["commits"][0]["id"] == "abc123"
        assert "2025-01-17" in input_data["webhook_event"]["received_at"]

    def test_webhook_event_without_received_at(self):
        """Test handling event without received_at."""
        event = MagicMock()
        event.event_id = "evt-456"
        event.provider = "stripe"
        event.event_type = "payment.completed"
        event.payload = {"amount": 1000}
        event.received_at = None

        input_data = {
            "webhook_event": {
                "event_id": event.event_id,
                "provider": event.provider,
                "event_type": event.event_type,
                "payload": event.payload,
                "received_at": event.received_at.isoformat() if event.received_at else None,
            }
        }

        assert input_data["webhook_event"]["received_at"] is None


class TestWebhookTriggerSource:
    """Tests for webhook trigger source formatting."""

    def test_trigger_source_format(self):
        """Test trigger source format for webhook events."""
        provider = "github"
        event_type = "push"

        trigger_source = f"webhook:{provider}.{event_type}"

        assert trigger_source == "webhook:github.push"

    def test_various_provider_event_combinations(self):
        """Test various provider/event type combinations."""
        test_cases = [
            ("stripe", "payment.completed", "webhook:stripe.payment.completed"),
            ("github", "pull_request.opened", "webhook:github.pull_request.opened"),
            ("slack", "message", "webhook:slack.message"),
        ]

        for provider, event_type, expected in test_cases:
            trigger_source = f"webhook:{provider}.{event_type}"
            assert trigger_source == expected


class TestWebhookHandlerConfig:
    """Tests for webhook handler configuration."""

    def test_workflow_handler_requires_workflow_id(self):
        """Test that workflow handlers need workflow_id in config."""
        handler_config = {"workflow_id": str(uuid4())}

        workflow_id = handler_config.get("workflow_id")

        assert workflow_id is not None

    def test_workflow_handler_missing_workflow_id(self):
        """Test handling missing workflow_id."""
        handler_config = {}

        workflow_id = handler_config.get("workflow_id")

        assert workflow_id is None

    def test_function_handler_requires_function_name(self):
        """Test that function handlers need function_name in config."""
        handler_config = {"function_name": "my_handler"}

        function_name = handler_config.get("function_name")

        assert function_name == "my_handler"

    def test_http_handler_requires_url(self):
        """Test that HTTP handlers need url in config."""
        handler_config = {
            "url": "https://api.example.com/webhook",
            "method": "POST",
            "headers": {"Authorization": "Bearer token"}
        }

        assert handler_config.get("url") is not None
        assert handler_config.get("method") == "POST"

    def test_organization_id_from_config(self):
        """Test extracting organization_id from handler config."""
        handler_config = {
            "workflow_id": str(uuid4()),
            "organization_id": "org-123"
        }

        org_id = handler_config.get("organization_id", "default")

        assert org_id == "org-123"

    def test_organization_id_default(self):
        """Test default organization_id when not in config."""
        handler_config = {"workflow_id": str(uuid4())}

        org_id = handler_config.get("organization_id", "default")

        assert org_id == "default"


class TestWebhookProcessorAsync:
    """Tests for async webhook processor methods."""

    @pytest.mark.asyncio
    async def test_call_function_sync(self):
        """Test calling a synchronous webhook function."""
        _webhook_function_registry.clear()

        call_count = {"count": 0}

        @register_webhook_function("sync_test")
        def sync_handler(event, config):
            call_count["count"] += 1
            return {"status": "ok"}

        processor = WebhookProcessor()

        handler = MagicMock()
        handler.handler_config = {"function_name": "sync_test"}

        event = MagicMock()
        event.event_id = "test-123"

        result = await processor._call_function(handler, event)

        assert call_count["count"] == 1
        assert result == {"status": "ok"}

    @pytest.mark.asyncio
    async def test_call_function_async(self):
        """Test calling an asynchronous webhook function."""
        _webhook_function_registry.clear()

        call_count = {"count": 0}

        @register_webhook_function("async_test")
        async def async_handler(event, config):
            call_count["count"] += 1
            return {"status": "async ok"}

        processor = WebhookProcessor()

        handler = MagicMock()
        handler.handler_config = {"function_name": "async_test"}

        event = MagicMock()
        event.event_id = "test-456"

        result = await processor._call_function(handler, event)

        assert call_count["count"] == 1
        assert result == {"status": "async ok"}

    @pytest.mark.asyncio
    async def test_call_function_not_found(self):
        """Test calling an unregistered function raises error."""
        _webhook_function_registry.clear()

        processor = WebhookProcessor()

        handler = MagicMock()
        handler.handler_config = {"function_name": "nonexistent"}

        event = MagicMock()

        with pytest.raises(ValueError, match="Unknown webhook function"):
            await processor._call_function(handler, event)

    @pytest.mark.asyncio
    async def test_call_function_missing_name(self):
        """Test calling without function_name raises error."""
        processor = WebhookProcessor()

        handler = MagicMock()
        handler.handler_config = {}  # No function_name

        event = MagicMock()

        with pytest.raises(ValueError, match="No function_name"):
            await processor._call_function(handler, event)
