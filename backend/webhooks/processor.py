"""
Webhook Processor

Processes incoming webhook events and routes them to handlers.
"""

import json
import logging
from datetime import datetime
from typing import Any, Callable, Dict, List, Optional
from uuid import UUID, uuid4

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from .schema import (
    WebhookConfig,
    WebhookEvent,
    WebhookHandler,
    WebhookStatus,
    WebhookSignatureVerifier,
)
from .registry import (
    WebhookRegistry,
    WebhookEventStore,
    get_webhook_registry,
    get_event_store,
)

logger = logging.getLogger(__name__)


# Function registry for webhook handlers
_webhook_function_registry: Dict[str, Callable] = {}


def register_webhook_function(name: str):
    """Decorator to register a function as a webhook handler."""
    def decorator(func: Callable):
        _webhook_function_registry[name] = func
        logger.info(f"Registered webhook function: {name}")
        return func
    return decorator


def get_webhook_function(name: str) -> Optional[Callable]:
    """Get a registered webhook function by name."""
    return _webhook_function_registry.get(name)


class WebhookProcessor:
    """
    Processes incoming webhook events.

    Responsibilities:
    - Verify webhook signatures
    - Parse event payloads
    - Route events to handlers
    - Track event status
    """

    def __init__(
        self,
        registry: Optional[WebhookRegistry] = None,
        event_store: Optional[WebhookEventStore] = None,
    ):
        self._registry = registry or get_webhook_registry()
        self._event_store = event_store or get_event_store()
        self._verifier = WebhookSignatureVerifier()

    def _get_nested_value(self, data: Dict, path: str) -> Any:
        """Get a value from nested dict using dot notation."""
        keys = path.split(".")
        value = data
        for key in keys:
            if isinstance(value, dict):
                value = value.get(key)
            else:
                return None
        return value

    def _extract_event_type(
        self,
        config: WebhookConfig,
        payload: Dict[str, Any],
        headers: Dict[str, str]
    ) -> str:
        """Extract event type from payload or headers."""
        path = config.event_type_path

        # Special handling for header-based event types
        if path.startswith("__header__"):
            header_name = path.replace("__header__", "")
            return headers.get(header_name, "unknown")

        # Get from payload
        event_type = self._get_nested_value(payload, path)
        return str(event_type) if event_type else "unknown"

    async def receive_webhook(
        self,
        provider: str,
        raw_body: bytes,
        headers: Dict[str, str],
        organization_id: Optional[str] = None,
    ) -> WebhookEvent:
        """
        Receive and process an incoming webhook.

        Args:
            provider: Provider name (stripe, github, etc.)
            raw_body: Raw request body
            headers: Request headers
            organization_id: Optional org ID for multi-tenant

        Returns:
            WebhookEvent with processing status
        """
        # Get provider config
        config = self._registry.get_config(provider)
        if not config:
            logger.warning(f"No webhook config for provider: {provider}")
            # Create default config
            config = WebhookConfig(provider=provider)

        # Verify signature
        if not self._verifier.verify(config, raw_body, headers):
            logger.warning(f"Webhook signature verification failed for {provider}")
            event = WebhookEvent(
                provider=provider,
                event_type="verification_failed",
                payload={},
                headers=headers,
                raw_body=raw_body,
                status=WebhookStatus.FAILED,
                organization_id=organization_id,
                error_message="Signature verification failed",
            )
            await self._event_store.store(event)
            return event

        # Parse payload
        try:
            payload = json.loads(raw_body.decode('utf-8'))
        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse webhook payload: {e}")
            event = WebhookEvent(
                provider=provider,
                event_type="parse_error",
                payload={},
                headers=headers,
                raw_body=raw_body,
                status=WebhookStatus.FAILED,
                organization_id=organization_id,
                error_message=f"Failed to parse JSON: {str(e)}",
            )
            await self._event_store.store(event)
            return event

        # Extract event type
        raw_event_type = self._extract_event_type(config, payload, headers)
        internal_event_type = config.get_internal_event_type(raw_event_type)

        # Create event
        event = WebhookEvent(
            provider=provider,
            event_type=internal_event_type,
            payload=payload,
            headers=dict(headers),
            raw_body=raw_body,
            organization_id=organization_id,
        )

        # Store event
        await self._event_store.store(event)

        # Process event
        await self.process_event(event)

        return event

    async def process_event(self, event: WebhookEvent) -> bool:
        """
        Process a webhook event through registered handlers.

        Returns True if all handlers succeeded.
        """
        # Get handlers for this event type
        full_event_type = f"{event.provider}.{event.event_type}"
        handlers = self._registry.get_handlers(full_event_type)

        # Also check for provider-wide handlers
        handlers.extend(self._registry.get_handlers(f"{event.provider}.*"))

        if not handlers:
            logger.info(f"No handlers for event: {full_event_type}")
            await self._event_store.update_status(
                event.event_id,
                WebhookStatus.COMPLETED
            )
            return True

        # Update status to processing
        await self._event_store.update_status(
            event.event_id,
            WebhookStatus.PROCESSING
        )

        all_succeeded = True
        errors = []

        for handler in handlers:
            try:
                await self._execute_handler(handler, event)
            except Exception as e:
                logger.error(f"Handler failed for {full_event_type}: {e}")
                all_succeeded = False
                errors.append(str(e))

        # Update final status
        if all_succeeded:
            await self._event_store.update_status(
                event.event_id,
                WebhookStatus.COMPLETED
            )
        else:
            await self._event_store.update_status(
                event.event_id,
                WebhookStatus.FAILED,
                error_message="; ".join(errors)
            )

        return all_succeeded

    async def _execute_handler(
        self,
        handler: WebhookHandler,
        event: WebhookEvent
    ):
        """Execute a single handler for an event."""
        logger.info(f"Executing handler {handler.handler_type} for {event.event_type}")

        if handler.handler_type == "workflow":
            await self._trigger_workflow(handler, event)
        elif handler.handler_type == "function":
            await self._call_function(handler, event)
        elif handler.handler_type == "http":
            await self._send_http(handler, event)
        elif handler.handler_type == "log":
            logger.info(f"Webhook event: {event.provider}.{event.event_type}: {event.payload}")
        else:
            logger.warning(f"Unknown handler type: {handler.handler_type}")

    async def _trigger_workflow(
        self,
        handler: WebhookHandler,
        event: WebhookEvent
    ):
        """Trigger a workflow from webhook event."""
        workflow_id = handler.handler_config.get("workflow_id")
        if not workflow_id:
            raise ValueError("No workflow_id in handler config")

        organization_id = handler.handler_config.get("organization_id", "default")

        # Import here to avoid circular imports
        from backend.database.session import get_async_session
        from backend.database.models import WorkflowModel, WorkflowExecutionModel
        from backend.shared.workflow_models import (
            Workflow, WorkflowNode, WorkflowEdge, WorkflowExecution,
            WorkflowStatus, ExecutionStatus, NodeType
        )
        from backend.services.workflow_executor import WorkflowExecutionEngine

        async with get_async_session() as db:
            # Get the workflow
            query = select(WorkflowModel).where(WorkflowModel.workflow_id == UUID(workflow_id))
            result = await db.execute(query)
            workflow = result.scalar_one_or_none()

            if not workflow:
                logger.error(f"Webhook trigger failed: Workflow {workflow_id} not found")
                return

            if workflow.status == WorkflowStatus.ARCHIVED.value:
                logger.error(f"Webhook trigger failed: Workflow {workflow_id} is archived")
                return

            # Create input data from webhook event
            input_data = {
                "webhook_event": {
                    "event_id": event.event_id,
                    "provider": event.provider,
                    "event_type": event.event_type,
                    "payload": event.payload,
                    "received_at": event.received_at.isoformat() if event.received_at else None,
                }
            }

            # Create execution record
            execution = WorkflowExecutionModel(
                execution_id=uuid4(),
                workflow_id=UUID(workflow_id),
                workflow_version=workflow.version,
                organization_id=organization_id,
                triggered_by="webhook",
                trigger_source=f"webhook:{event.provider}.{event.event_type}",
                status=ExecutionStatus.PENDING.value,
                input_data=input_data,
                node_states={}
            )

            db.add(execution)
            await db.commit()
            await db.refresh(execution)

            # Convert workflow to domain model
            workflow_nodes = [
                WorkflowNode(
                    id=n["id"],
                    type=NodeType(n["type"]),
                    position=n["position"],
                    data=n["data"],
                    label=n.get("label")
                )
                for n in workflow.nodes
            ]

            workflow_edges = [
                WorkflowEdge(
                    id=e["id"],
                    source=e["source"],
                    target=e["target"],
                    source_handle=e.get("sourceHandle", "out"),
                    target_handle=e.get("targetHandle", "in"),
                    label=e.get("label"),
                    animated=e.get("animated", False)
                )
                for e in workflow.edges
            ]

            workflow_obj = Workflow(
                workflow_id=workflow.workflow_id,
                organization_id=workflow.organization_id,
                name=workflow.name,
                description=workflow.description,
                status=WorkflowStatus(workflow.status),
                version=workflow.version,
                nodes=workflow_nodes,
                edges=workflow_edges,
                variables=workflow.variables,
                environment=workflow.environment,
                max_execution_time_seconds=workflow.max_execution_time_seconds,
                retry_on_failure=workflow.retry_on_failure,
                max_retries=workflow.max_retries
            )

            # Execute the workflow
            engine = WorkflowExecutionEngine()
            try:
                await engine.execute_workflow(
                    workflow=workflow_obj,
                    execution=WorkflowExecution(
                        execution_id=execution.execution_id,
                        workflow_id=UUID(workflow_id),
                        workflow_version=workflow.version,
                        organization_id=organization_id,
                        status=ExecutionStatus.PENDING,
                        triggered_by="webhook",
                        trigger_source=f"webhook:{event.provider}.{event.event_type}",
                        input_data=input_data
                    ),
                    db=db
                )
                logger.info(f"Triggered workflow {workflow_id} from webhook event {event.event_id}")
            except Exception as e:
                logger.error(f"Workflow execution failed for webhook event {event.event_id}: {e}")

    async def _call_function(
        self,
        handler: WebhookHandler,
        event: WebhookEvent
    ):
        """Call a registered function handler."""
        function_name = handler.handler_config.get("function_name")
        if not function_name:
            raise ValueError("No function_name in handler config")

        # Get function from registry
        func = get_webhook_function(function_name)
        if not func:
            logger.warning(f"Webhook function not found: {function_name}")
            raise ValueError(f"Unknown webhook function: {function_name}")

        # Call the function with event data
        try:
            import asyncio
            if asyncio.iscoroutinefunction(func):
                result = await func(event, handler.handler_config)
            else:
                result = func(event, handler.handler_config)
            logger.info(f"Called webhook function {function_name} for event {event.event_id}")
            return result
        except Exception as e:
            logger.error(f"Webhook function {function_name} failed: {e}")
            raise

    async def _send_http(
        self,
        handler: WebhookHandler,
        event: WebhookEvent
    ):
        """Forward webhook to an HTTP endpoint."""
        import aiohttp
        from backend.shared.url_validator import validate_url

        url = handler.handler_config.get("url")
        method = handler.handler_config.get("method", "POST")
        headers = handler.handler_config.get("headers", {})

        if not url:
            raise ValueError("No url in handler config")

        # SSRF protection: validate URL before making request
        validate_url(url)

        async with aiohttp.ClientSession() as session:
            async with session.request(
                method,
                url,
                json=event.to_dict(),
                headers=headers
            ) as response:
                if response.status >= 400:
                    text = await response.text()
                    raise RuntimeError(f"HTTP handler failed: {response.status} {text}")


# Singleton instance
_processor: Optional[WebhookProcessor] = None


def get_webhook_processor() -> WebhookProcessor:
    """Get singleton webhook processor."""
    global _processor
    if _processor is None:
        _processor = WebhookProcessor()
    return _processor
