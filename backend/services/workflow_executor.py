"""
Workflow Executor Service

Executes workflows and streams real-time status updates via WebSocket.

Integrated with Circuit Breaker for runaway agent protection.
"""

import asyncio
import json
import logging
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Any, Callable
from uuid import UUID
from datetime import datetime
from enum import Enum

from backend.database.repositories import WorkflowRepository
from backend.database.session import AsyncSessionLocal
from backend.shared.integration_models import IntegrationModel, IntegrationInstallationModel
from backend.orchestrator import get_queue, get_registry
from backend.shared.models import Task, TaskInput, TaskPriority
from backend.shared.circuit_breaker_service import (
    CircuitBreaker,
    CircuitBreakerConfig,
    CircuitBreakerAction,
    BatchOperationConfig,
)
from backend.services.routing_integration import RoutingResolver, FailoverExecutor, ProviderError
from backend.shared.llm_clients import call_llm, LLMResponse
from backend.shared.shared_state_manager import (
    SharedStateManager,
    StateScope,
    get_shared_state_manager
)
from backend.shared.hook_manager import (
    get_hook_manager,
    HookType,
    HookContext,
    HookResult
)
from backend.integrations import get_integration_registry, get_action_executor
from backend.integrations.schema import IntegrationCredentials
from backend.shared.credential_manager import decrypt_credentials
from backend.shared.hitl_models import (
    ApprovalRequestCreate,
    ApprovalPriority,
    NotificationChannel,
    ApprovalStatus,
)
from backend.shared.hitl_service import HITLService
from backend.shared.timetravel_service import SnapshotCaptureService
from backend.shared.ab_testing_middleware import ABTestingMiddleware, ABOverride

logger = logging.getLogger(__name__)


@dataclass
class WorkflowContext:
    """
    Context that carries organization, user, and configuration through workflow execution.

    This context is propagated to all node executions and service calls,
    replacing hardcoded default values with actual runtime context.
    """
    organization_id: str = "default-org"
    user_id: str = "system"
    embedding_api_key: Optional[str] = None
    llm_api_keys: Dict[str, str] = field(default_factory=dict)  # provider -> api_key
    variables: Dict[str, Any] = field(default_factory=dict)

    @classmethod
    def from_execution(cls, execution: Any) -> "WorkflowContext":
        """Create context from workflow execution object."""
        return cls(
            organization_id=getattr(execution, 'organization_id', 'default-org'),
            user_id=getattr(execution, 'triggered_by', 'system'),
            variables=getattr(execution, 'input_data', {}) or {},
        )

    @classmethod
    def from_request(
        cls,
        organization_id: str,
        user_id: str,
        embedding_api_key: Optional[str] = None,
        llm_api_keys: Optional[Dict[str, str]] = None,
    ) -> "WorkflowContext":
        """Create context from API request parameters."""
        return cls(
            organization_id=organization_id,
            user_id=user_id,
            embedding_api_key=embedding_api_key,
            llm_api_keys=llm_api_keys or {},
        )


class _SnapshotNodeStub:
    """Lightweight stub matching the WorkflowNode interface for SnapshotCaptureService."""
    def __init__(self, node_id: str, node_type: str):
        self.id = node_id
        self.type = type('_NodeType', (), {'value': node_type})()


class NodeStatus(str, Enum):
    """Node execution status."""
    IDLE = "idle"
    PENDING = "pending"
    RUNNING = "running"
    SUCCESS = "success"
    ERROR = "error"


class ExecutionEvent:
    """Workflow execution event."""
    def __init__(
        self,
        event_type: str,
        node_id: Optional[str] = None,
        status: Optional[NodeStatus] = None,
        message: Optional[str] = None,
        data: Optional[Dict[str, Any]] = None,
        cost: Optional[float] = None,
        execution_time: Optional[float] = None,
        error: Optional[str] = None,
        actual_model: Optional[str] = None,
        actual_provider: Optional[str] = None,
        routing_reason: Optional[str] = None,
    ):
        self.event_type = event_type
        self.node_id = node_id
        self.status = status
        self.message = message
        self.data = data
        self.cost = cost
        self.execution_time = execution_time
        self.error = error
        self.actual_model = actual_model
        self.actual_provider = actual_provider
        self.routing_reason = routing_reason
        self.timestamp = datetime.utcnow().isoformat()

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return {
            "event_type": self.event_type,
            "node_id": self.node_id,
            "status": self.status.value if self.status else None,
            "message": self.message,
            "data": self.data,
            "cost": self.cost,
            "execution_time": self.execution_time,
            "error": self.error,
            "actual_model": self.actual_model,
            "actual_provider": self.actual_provider,
            "routing_reason": self.routing_reason,
            "timestamp": self.timestamp,
        }


class WorkflowExecutor:
    """Executes workflows and provides real-time status updates."""

    def __init__(
        self,
        db=None,
        circuit_breaker_config: Optional[CircuitBreakerConfig] = None,
        redis_client=None
    ):
        logger.info("Initializing WorkflowExecutor")
        self.active_executions: Dict[UUID, bool] = {}
        self.db = db
        self.redis = redis_client

        # Initialize circuit breaker with default or custom config
        try:
            logger.debug("Creating CircuitBreaker")
            self.circuit_breaker = CircuitBreaker(
                db=db,
                config=circuit_breaker_config or CircuitBreakerConfig()
            )
            logger.debug("CircuitBreaker created")
        except Exception as e:
            logger.error(f"Error creating CircuitBreaker: {e}", exc_info=True)
            raise

        # Initialize routing resolver for SmartRouter integration
        try:
            logger.debug("Creating RoutingResolver")
            self.routing_resolver = RoutingResolver(db=db) if db else None
            logger.debug(f"RoutingResolver initialized: {self.routing_resolver is not None}")
        except Exception as e:
            logger.error(f"Error creating RoutingResolver: {e}", exc_info=True)
            self.routing_resolver = None  # Continue without routing resolver

        # Initialize shared state manager for cross-node context passing
        try:
            logger.debug("Creating SharedStateManager")
            self.state_manager = get_shared_state_manager(
                redis_client=redis_client,
                db=db
            )
            logger.debug("SharedStateManager created")
        except Exception as e:
            logger.error(f"Error creating SharedStateManager: {e}", exc_info=True)
            raise

        # Initialize hook manager for extensibility
        try:
            logger.debug("Creating HookManager")
            self.hook_manager = get_hook_manager()
            logger.debug("HookManager created")
        except Exception as e:
            logger.error(f"Error creating HookManager: {e}", exc_info=True)
            # Continue without hook manager - hooks are optional
            self.hook_manager = None

        # Initialize time-travel snapshot capture (optional, requires DB)
        self.snapshot_service: Optional[SnapshotCaptureService] = None
        if db:
            try:
                logger.debug("Creating SnapshotCaptureService for time-travel debugging")
                self.snapshot_service = SnapshotCaptureService(db=db)
                logger.debug("SnapshotCaptureService created")
            except Exception as e:
                logger.warning(f"SnapshotCaptureService unavailable: {e}. Time-travel disabled.")
                self.snapshot_service = None

        logger.info("WorkflowExecutor initialization complete")

    async def execute_workflow(
        self,
        workflow_id: UUID,
        workflow_data: Dict[str, Any],
        send_update: callable,
        batch_config: Optional[BatchOperationConfig] = None,
        context: Optional[WorkflowContext] = None,
        input_data: Optional[Dict[str, Any]] = None,
    ) -> None:
        """
        Execute a workflow and send real-time status updates.

        Args:
            workflow_id: Workflow ID
            workflow_data: Workflow definition (nodes, edges)
            send_update: Async callback to send updates (WebSocket)
            batch_config: Optional batch operation config for elevated limits
            context: Workflow execution context with org_id, user_id, and API keys
            input_data: Input data for the workflow (from trigger node)
        """
        execution_id = workflow_id
        self.active_executions[execution_id] = True
        self._batch_config = batch_config
        # Use provided context or create default
        self._context = context or WorkflowContext()
        self._input_data = input_data or {}

        # Track total execution time for time-travel
        execution_start_time = datetime.utcnow()

        try:
            # Send start event
            await send_update(ExecutionEvent(
                event_type="execution_started",
                message=f"Starting workflow execution"
            ))

            # Capture time-travel snapshot: execution start
            if self.snapshot_service:
                try:
                    await self.snapshot_service.capture_execution_start(
                        execution_id=execution_id,
                        workflow_id=workflow_id,
                        organization_id=self._context.organization_id,
                        input_data=self._input_data,
                    )
                except Exception as e:
                    logger.warning(f"Time-travel snapshot (execution_start) failed: {e}")

            # Store input data in state so downstream nodes can reference it via {{input.field}}
            if self._input_data:
                try:
                    await self.state_manager.set(
                        key="node_output:input",
                        value=self._input_data,
                        scope=StateScope.WORKFLOW,
                        scope_id=str(workflow_id),
                        metadata={"node_type": "trigger", "node_label": "Input Data"}
                    )
                    logger.info(f"Stored input data in workflow state: {self._input_data}")
                except Exception as e:
                    logger.warning(f"Failed to store input data in state: {e}")

            nodes = workflow_data.get("nodes", [])
            edges = workflow_data.get("edges", [])
            self._current_edges = edges  # Store for upstream context lookup

            # Validate and normalize nodes - ensure all nodes have valid data
            for node in nodes:
                if node.get('data') is None:
                    node['data'] = {}
                if not isinstance(node['data'], dict):
                    node['data'] = {}
                # Ensure essential fields exist
                if 'type' not in node['data']:
                    node['data']['type'] = node.get('type', 'unknown')
                if 'label' not in node['data']:
                    node['data']['label'] = node.get('id', 'Unknown Node')

            # Build execution graph
            node_map = {node["id"]: node for node in nodes}
            adjacency = self._build_adjacency_list(edges)
            in_degree = self._calculate_in_degree(nodes, edges)

            # Execute nodes in topological order
            await self._execute_topological(
                node_map,
                adjacency,
                in_degree,
                send_update,
                execution_id,
                str(workflow_id)  # Pass workflow_id for routing
            )

            # Capture time-travel snapshot: execution complete
            if self.snapshot_service:
                try:
                    total_duration_ms = (datetime.utcnow() - execution_start_time).total_seconds() * 1000
                    await self.snapshot_service.capture_execution_complete(
                        execution_id=execution_id,
                        workflow_id=workflow_id,
                        organization_id=self._context.organization_id,
                        output_data={"status": "completed"},
                        total_duration_ms=total_duration_ms,
                        total_cost=0.0,  # Aggregated cost tracked by circuit breaker
                    )
                except Exception as e:
                    logger.warning(f"Time-travel snapshot (execution_complete) failed: {e}")

            # Send completion event
            await send_update(ExecutionEvent(
                event_type="execution_completed",
                message="Workflow execution completed successfully"
            ))

            # Clean up workflow state (TTL will handle auto-cleanup, but explicit is better)
            try:
                cleared_count = await self.state_manager.clear(
                    scope=StateScope.WORKFLOW,
                    scope_id=str(workflow_id)
                )
                logger.info(f"Cleared {cleared_count} workflow state entries for {workflow_id}")
            except Exception as e:
                logger.warning(f"Failed to clear workflow state: {e}")

        except Exception as e:
            # Send error event
            await send_update(ExecutionEvent(
                event_type="execution_failed",
                message=f"Workflow execution failed: {str(e)}",
                error=str(e)
            ))

            # Clean up workflow state even on failure
            try:
                await self.state_manager.clear(
                    scope=StateScope.WORKFLOW,
                    scope_id=str(workflow_id)
                )
            except Exception as e:
                logger.warning(f"Failed to clear workflow state on error: {e}")

        finally:
            self.active_executions.pop(execution_id, None)

    def _build_adjacency_list(self, edges: List[Dict]) -> Dict[str, List[str]]:
        """Build adjacency list from edges."""
        adjacency = {}
        for edge in edges:
            source = edge["source"]
            target = edge["target"]
            if source not in adjacency:
                adjacency[source] = []
            adjacency[source].append(target)
        return adjacency

    def _calculate_in_degree(
        self,
        nodes: List[Dict],
        edges: List[Dict]
    ) -> Dict[str, int]:
        """Calculate in-degree for each node."""
        in_degree = {node["id"]: 0 for node in nodes}
        for edge in edges:
            in_degree[edge["target"]] += 1
        return in_degree

    async def _gather_upstream_context(
        self,
        node_id: str,
        workflow_id: str
    ) -> str:
        """
        Gather output from upstream nodes to use as LLM input context.

        When a worker/supervisor node has no explicit prompt, this method
        collects outputs from predecessor nodes and the workflow input data,
        formatting them as the user message for the LLM.
        """
        import json as _json
        parts = []

        # 1. Check for workflow input data (from trigger)
        try:
            input_state = await self.state_manager.get(
                key="node_output:input",
                scope=StateScope.WORKFLOW,
                scope_id=str(workflow_id),
            )
            if input_state:
                val = input_state.value if hasattr(input_state, 'value') else input_state
                if isinstance(val, dict):
                    # Format as human-readable key-value pairs for the LLM
                    lines = []
                    for k, v in val.items():
                        if k == 'output':
                            continue  # Skip the redundant serialized 'output' field
                        lines.append(f"{k}: {v}")
                    if lines:
                        parts.append("\n".join(lines))
                    else:
                        parts.append(_json.dumps(val, indent=2))
                elif val:
                    parts.append(str(val))
        except Exception as e:
            logger.debug(f"No input data in state: {e}")

        # 2. Check for predecessor node outputs (look up edges to find parents)
        try:
            edges = getattr(self, '_current_edges', [])
            parent_ids = [e['source'] for e in edges if e['target'] == node_id]
            for pid in parent_ids:
                parent_state = await self.state_manager.get(
                    key=f"node_output:{pid}",
                    scope=StateScope.WORKFLOW,
                    scope_id=str(workflow_id),
                )
                if parent_state:
                    val = parent_state.value if hasattr(parent_state, 'value') else parent_state
                    if isinstance(val, dict):
                        # Extract content field if it's an LLM response
                        if 'content' in val:
                            parts.append(str(val['content']))
                        elif 'output' in val:
                            parts.append(str(val['output']))
                        else:
                            parts.append(_json.dumps(val, indent=2))
                    elif val:
                        parts.append(str(val))
        except Exception as e:
            logger.debug(f"Error gathering upstream outputs: {e}")

        return "\n\n".join(parts) if parts else ""

    async def _substitute_variables(
        self,
        text: str,
        workflow_id: str
    ) -> str:
        """
        Replace {{node_id.field}} with values from workflow state.

        Example:
            Input: "Process {{user_input.message}}"
            Output: "Process Hello World" (if user_input node stored message="Hello World")

        Args:
            text: Text with variable placeholders
            workflow_id: Workflow ID for state scope

        Returns:
            Text with variables substituted
        """
        if not text or "{{" not in text:
            return text

        import re

        logger.debug(f"Variable substitution for workflow {workflow_id}: {text[:200]}...")

        # Find all {{node_id.field}} or {{node label.field}} patterns
        # Supports: node_id, node-id, "Node Label", Node Label (with spaces)
        pattern = r'\{\{([a-zA-Z0-9_\- ]+)\.([a-zA-Z0-9_.-]+)\}\}'

        async def replace_variable(match):
            node_id = match.group(1)
            field_path = match.group(2)

            logger.debug(f"Looking up variable: node_id='{node_id}', field='{field_path}'")

            # Get node output from state
            node_output = await self.state_manager.get(
                key=f"node_output:{node_id}",
                scope=StateScope.WORKFLOW,
                scope_id=workflow_id
            )

            logger.debug(f"State lookup result for '{node_id}': {node_output}")

            if node_output is None:
                # Try listing all keys in the state to debug
                try:
                    all_keys = await self.state_manager.keys(
                        scope=StateScope.WORKFLOW,
                        scope_id=workflow_id
                    )
                    logger.debug(f"All keys in workflow state: {all_keys}")
                except Exception as e:
                    logger.debug(f"Failed to list keys: {e}")
                logger.warning(f"Variable {{{{ {node_id}.{field_path} }}}} not found in state")
                return match.group(0)  # Return original if not found

            # Navigate nested fields (e.g., user.name.first)
            value = node_output
            for field in field_path.split("."):
                if isinstance(value, dict):
                    value = value.get(field)
                elif isinstance(value, list) and field.isdigit():
                    idx = int(field)
                    value = value[idx] if idx < len(value) else None
                else:
                    value = None
                    break

            if value is None:
                logger.warning(f"Field {field_path} not found in node {node_id} output")
                return match.group(0)

            return str(value)

        # Replace all variables
        result = text
        for match in re.finditer(pattern, text):
            replacement = await replace_variable(match)
            result = result.replace(match.group(0), replacement)

        return result

    async def _execute_topological(
        self,
        node_map: Dict[str, Dict],
        adjacency: Dict[str, List[str]],
        in_degree: Dict[str, int],
        send_update: callable,
        execution_id: UUID,
        workflow_id: Optional[str] = None,
    ) -> None:
        """Execute nodes in topological order using Kahn's algorithm."""
        # Find all nodes with in-degree 0 (start nodes)
        queue = [node_id for node_id, degree in in_degree.items() if degree == 0]
        completed_nodes = set()

        # Mark all nodes as pending initially
        for node_id in node_map.keys():
            await send_update(ExecutionEvent(
                event_type="node_status_changed",
                node_id=node_id,
                status=NodeStatus.PENDING,
                message="Waiting to execute"
            ))

        while queue and self.active_executions.get(execution_id, False):
            # Process all nodes at current level in parallel
            current_level = queue[:]
            queue = []

            # Execute nodes in parallel with circuit breaker protection
            tasks = [
                self._execute_node(node_id, node_map[node_id], send_update, execution_id, workflow_id)
                for node_id in current_level
            ]
            results = await asyncio.gather(*tasks, return_exceptions=True)

            # Process results
            for node_id, result in zip(current_level, results):
                if isinstance(result, Exception):
                    # Capture time-travel snapshot: node error
                    if self.snapshot_service and execution_id:
                        try:
                            node_data = node_map.get(node_id, {})
                            node_type_val = (node_data.get('data') or {}).get('type', 'unknown')
                            snap_node = _SnapshotNodeStub(node_id, node_type_val)
                            await self.snapshot_service.capture_node_error(
                                execution_id=execution_id,
                                workflow_id=UUID(workflow_id) if workflow_id else execution_id,
                                organization_id=self._context.organization_id,
                                node=snap_node,
                                input_state=(node_data.get('data') or {}),
                                error_message=str(result),
                                error_type=type(result).__name__,
                            )
                        except Exception as e:
                            logger.debug(f"Time-travel snapshot (node_error) failed: {e}")

                    # Node failed
                    await send_update(ExecutionEvent(
                        event_type="node_status_changed",
                        node_id=node_id,
                        status=NodeStatus.ERROR,
                        error=str(result),
                        message=f"Node execution failed: {str(result)}"
                    ))
                    # Stop execution on error
                    raise result
                else:
                    completed_nodes.add(node_id)

                    # Add downstream nodes to queue if all dependencies met
                    for neighbor in adjacency.get(node_id, []):
                        in_degree[neighbor] -= 1
                        if in_degree[neighbor] == 0:
                            queue.append(neighbor)

    async def _execute_node(
        self,
        node_id: str,
        node_data: Dict,
        send_update: callable,
        execution_id: Optional[UUID] = None,
        workflow_id: Optional[str] = None,
    ) -> None:
        """Execute a single node with circuit breaker protection."""
        start_time = datetime.utcnow()

        # Ensure node_data['data'] is always a dict, never None
        if node_data.get('data') is None:
            node_data['data'] = {}

        node_type = node_data['data'].get('type', 'unknown')
        node_label = node_data['data'].get('label', node_id)

        logger.debug(f"Executing node: id={node_id}, label={node_label}, type={node_type}, workflow={workflow_id}")
        logger.debug(f"Has routing_resolver: {self.routing_resolver is not None}")

        # Resolve model selection using SmartRouter for LLM nodes
        routing_decision = None
        if node_type in ["supervisor", "worker"] and self.routing_resolver:
            logger.debug(f"Resolving model selection for worker/supervisor node")
            try:
                model_config = await self.routing_resolver.resolve_model_selection(
                    node_data=node_data['data'],
                    workflow_id=workflow_id or str(execution_id),
                    agent_id=node_id,
                    org_id=self._context.organization_id
                )
                routing_decision = model_config.routing_decision
                logger.info(
                    f"Routing decision for node {node_id}: "
                    f"{routing_decision.provider}/{routing_decision.model} "
                    f"(source: {model_config.config_source}, reason: {routing_decision.reason})"
                )
            except Exception as e:
                logger.warning(f"Failed to resolve routing for node {node_id}: {e}. Using default.", exc_info=True)
                routing_decision = None
        else:
            logger.debug(f"Skipping routing (type={node_type}, has_resolver={self.routing_resolver is not None})")

        # CIRCUIT BREAKER CHECK: Before LLM call
        if node_type in ["supervisor", "worker"] and execution_id:
            cb_result = await self.circuit_breaker.check_before_llm_call(
                execution_id,
                estimated_tokens=1000,  # Estimate, adjust based on prompt
                batch_config=getattr(self, '_batch_config', None)
            )
            if not cb_result.proceed:
                logger.warning(
                    f"Circuit breaker blocked node {node_id}: "
                    f"{cb_result.action.value} - {cb_result.reason}"
                )
                if cb_result.action == CircuitBreakerAction.KILL:
                    raise RuntimeError(
                        f"Circuit breaker KILLED execution: {cb_result.reason}"
                    )
                elif cb_result.action == CircuitBreakerAction.SUSPEND_FOR_APPROVAL:
                    await send_update(ExecutionEvent(
                        event_type="node_status_changed",
                        node_id=node_id,
                        status=NodeStatus.PENDING,
                        message=f"Suspended for approval: {cb_result.reason}",
                        data={"circuit_breaker": cb_result.to_dict()}
                    ))
                    # In production, this would pause and wait for HITL approval
                    raise RuntimeError(
                        f"Circuit breaker suspended: {cb_result.reason}"
                    )

        # CIRCUIT BREAKER CHECK: Before tool call
        if node_type == "tool" and execution_id:
            tool_name = node_data['data'].get('label', 'unknown_tool')
            tool_params = node_data['data'].get('config') or {}
            cb_result = await self.circuit_breaker.check_before_tool_call(
                execution_id,
                tool_name,
                tool_params,
                batch_config=getattr(self, '_batch_config', None)
            )
            if not cb_result.proceed:
                logger.warning(
                    f"Circuit breaker blocked tool {tool_name}: "
                    f"{cb_result.action.value} - {cb_result.reason}"
                )
                if cb_result.action == CircuitBreakerAction.KILL:
                    raise RuntimeError(
                        f"Circuit breaker KILLED: Tool loop detected - {cb_result.reason}"
                    )
                elif cb_result.action == CircuitBreakerAction.SUSPEND_FOR_APPROVAL:
                    await send_update(ExecutionEvent(
                        event_type="node_status_changed",
                        node_id=node_id,
                        status=NodeStatus.PENDING,
                        message=f"Tool suspended: {cb_result.reason}",
                        data={"circuit_breaker": cb_result.to_dict()}
                    ))
                    raise RuntimeError(
                        f"Circuit breaker suspended tool: {cb_result.reason}"
                    )

        # Send running status
        node_label = node_data['data'].get('label', node_id)
        await send_update(ExecutionEvent(
            event_type="node_status_changed",
            node_id=node_id,
            status=NodeStatus.RUNNING,
            message=f"Executing {node_label}"
        ))

        # Capture time-travel snapshot: node start
        if self.snapshot_service and execution_id:
            try:
                snap_node = _SnapshotNodeStub(node_id, node_type)
                await self.snapshot_service.capture_node_start(
                    execution_id=execution_id,
                    workflow_id=UUID(workflow_id) if workflow_id else execution_id,
                    organization_id=self._context.organization_id,
                    node=snap_node,
                    input_state=node_data.get('data', {}),
                    variables=self._context.variables,
                )
            except Exception as e:
                logger.debug(f"Time-travel snapshot (node_start) failed: {e}")

        # A/B TESTING: Check for running experiments before LLM execution
        # Note: We always try A/B testing for LLM nodes - the middleware creates its own db session
        ab_override: Optional[ABOverride] = None
        if node_type in ["supervisor", "worker"]:
            try:
                from backend.database.session import AsyncSessionLocal
                async with AsyncSessionLocal() as ab_db:
                    ab_override = await ABTestingMiddleware.check_and_assign(
                        db=ab_db,
                        node_data=node_data,
                        workflow_id=workflow_id,
                        user_id=self._context.user_id if self._context else "system",
                        node_id=node_id,
                    )
                    if ab_override and routing_decision:
                        routing_decision, node_data = ABTestingMiddleware.apply_override(
                            ab_override, routing_decision, node_data
                        )
            except Exception as e:
                logger.warning(f"A/B testing pre-check failed (non-fatal): {e}")
                ab_override = None

        # Execute node based on type
        if node_type in ["supervisor", "worker"] and routing_decision:
            # Real LLM execution
            logger.debug(f"Executing LLM node with routing decision")
            try:
                llm_result = await self._execute_llm_node(
                    node_data=node_data,
                    routing_decision=routing_decision,
                    workflow_id=workflow_id,
                    node_id=node_id
                )
                logger.debug(
                    f"LLM execution completed: model={llm_result.model}, "
                    f"provider={llm_result.provider}, latency={llm_result.latency_ms}ms"
                )
            except Exception as e:
                logger.error(f"LLM execution failed: {e}", exc_info=True)
                # A/B TESTING: Record failure (middleware creates its own db session)
                if ab_override:
                    try:
                        from backend.database.session import AsyncSessionLocal
                        async with AsyncSessionLocal() as ab_db:
                            await ABTestingMiddleware.record_result(
                                db=ab_db,
                                override=ab_override,
                                success=False,
                                error_message=str(e),
                            )
                    except Exception as ab_err:
                        logger.warning(f"A/B record failure error: {ab_err}")
                raise
            execution_time = llm_result.latency_ms
            cost = llm_result.cost
            tokens_used = llm_result.tokens_used

            # A/B TESTING: Record successful completion (middleware creates its own db session)
            if ab_override:
                try:
                    from backend.database.session import AsyncSessionLocal
                    async with AsyncSessionLocal() as ab_db:
                        await ABTestingMiddleware.record_result(
                            db=ab_db,
                            override=ab_override,
                            success=True,
                            latency_ms=llm_result.latency_ms,
                            cost=llm_result.cost,
                        )
                except Exception as ab_err:
                    logger.warning(f"A/B record success error: {ab_err}")
        elif node_type == "tool":
            # Real HTTP API execution
            tool_result = await self._execute_tool_node(
                node_data=node_data,
                node_id=node_id,
                workflow_id=workflow_id
            )
            execution_time = tool_result.get('latency_ms', 0)
            cost = tool_result.get('cost', 0.0001)  # Minimal cost for API calls
            tokens_used = 0  # Tools don't use LLM tokens
        elif node_type == "memory":
            # Real memory operation (store/query/delete)
            memory_result = await self._execute_memory_node(
                node_data=node_data,
                node_id=node_id,
                workflow_id=workflow_id
            )
            execution_time = memory_result.get('latency_ms', 0)
            cost = memory_result.get('cost', 0.0001)  # Minimal cost for memory ops
            tokens_used = memory_result.get('tokens_used', 0)  # Embedding tokens
        elif node_type == "knowledge":
            # Real knowledge base query (RAG)
            knowledge_result = await self._execute_knowledge_node(
                node_data=node_data,
                node_id=node_id,
                workflow_id=workflow_id
            )
            execution_time = knowledge_result.get('latency_ms', 0)
            cost = knowledge_result.get('cost', 0.0001)  # Minimal cost for RAG queries
            tokens_used = knowledge_result.get('tokens_used', 0)  # Embedding tokens
        elif node_type == "webhook":
            # Webhook listener execution
            webhook_result = await self._execute_webhook_node(
                node_data=node_data,
                node_id=node_id
            )
            execution_time = webhook_result.get('latency_ms', 0)
            cost = 0.0  # No cost for webhook listeners
            tokens_used = 0
        elif node_type == "hitl":
            # Human-in-the-loop approval
            hitl_result = await self._execute_hitl_node(
                node_data=node_data,
                node_id=node_id,
                send_update=send_update
            )
            execution_time = hitl_result.get('latency_ms', 0)
            cost = 0.0  # No cost for HITL approvals
            tokens_used = 0
        elif node_type == "integration":
            # Real integration execution (Discord, Slack, Groq, etc.)
            integration_result = await self._execute_integration_node(
                node_data=node_data,
                node_id=node_id,
                workflow_id=workflow_id
            )
            execution_time = integration_result.get('latency_ms', 0)
            cost = integration_result.get('cost', 0.0001)
            tokens_used = 0
        elif node_type == "print":
            # Print node - outputs message to Execution Log
            print_result = await self._execute_print_node(
                node_data=node_data,
                node_id=node_id,
                workflow_id=workflow_id,
                send_update=send_update
            )
            execution_time = print_result.get('latency_ms', 0)
            cost = 0.0  # No cost for print nodes
            tokens_used = 0
        else:
            # Simulate node execution for non-LLM nodes or when routing unavailable
            execution_time = await self._simulate_node_execution(node_type, node_data)
            cost = self._calculate_node_cost(node_data)
            tokens_used = self._estimate_tokens_used(node_data)

        # CIRCUIT BREAKER: Record metrics after execution
        if node_type in ["supervisor", "worker"] and execution_id:
            await self.circuit_breaker.record_llm_call(
                execution_id,
                tokens_used=tokens_used,
                cost=cost
            )

        # Prepare node output data
        # For trigger nodes, pass through the workflow input data
        if node_type == "trigger" and self._input_data:
            node_output = {**self._input_data, "output": json.dumps(self._input_data)}
        else:
            node_output = {"output": f"Result from {node_label}"}

        # Store specific outputs based on node type
        if node_type in ["supervisor", "worker"] and 'llm_result' in locals():
            node_output = {
                "content": llm_result.content,
                "text": llm_result.content,  # Alias so {{node.text}} works
                "model": llm_result.model,
                "provider": llm_result.provider,
                "tokens": llm_result.tokens_used,
                "cost": llm_result.cost
            }
            # Attach A/B test metadata if variant was used
            if ab_override:
                node_output["ab_test"] = {
                    "experiment_id": ab_override.experiment_id,
                    "variant_name": ab_override.variant_name,
                    "variant_key": ab_override.variant_key,
                    "assignment_id": ab_override.assignment_id,
                }
        elif node_type in ["supervisor", "worker"]:
            # Fallback for worker nodes when LLM call was skipped (routing unavailable)
            # Include "content" field for variable substitution compatibility
            node_output = {
                "content": f"Simulated response from {node_label}",
                "output": f"Result from {node_label}",
                "model": "simulated",
                "provider": "simulated",
                "tokens": 0,
                "cost": 0
            }
            logger.warning(f"Node {node_label} used simulated output - routing_resolver may be unavailable")
        elif node_type == "tool" and 'tool_result' in locals():
            node_output = tool_result.get('response_data', {})
        elif node_type == "memory" and 'memory_result' in locals():
            node_output = memory_result.get('response_data', {})
        elif node_type == "knowledge" and 'knowledge_result' in locals():
            node_output = knowledge_result.get('response_data', {})
        elif node_type == "webhook" and 'webhook_result' in locals():
            node_output = webhook_result.get('response_data', {})
        elif node_type == "hitl" and 'hitl_result' in locals():
            node_output = hitl_result.get('response_data', {})
        elif node_type == "integration" and 'integration_result' in locals():
            node_output = integration_result.get('response_data', {})
        elif node_type == "print" and 'print_result' in locals():
            node_output = print_result.get('response_data', {})

        # Store node output in workflow state for cross-node access
        # Store by both node_id and node_label so users can reference either
        logger.debug(f"Storing node output in state for workflow {workflow_id}")
        if workflow_id:
            try:
                # Store by node ID
                await self.state_manager.set(
                    key=f"node_output:{node_id}",
                    value=node_output,
                    scope=StateScope.WORKFLOW,
                    scope_id=str(workflow_id),
                    metadata={
                        "node_type": node_type,
                        "node_label": node_label,
                        "execution_time": execution_time,
                        "cost": cost
                    }
                )
                # Also store by node label (for user-friendly variable references)
                await self.state_manager.set(
                    key=f"node_output:{node_label}",
                    value=node_output,
                    scope=StateScope.WORKFLOW,
                    scope_id=str(workflow_id),
                    metadata={
                        "node_type": node_type,
                        "node_id": node_id,
                        "execution_time": execution_time,
                        "cost": cost
                    }
                )
                logger.debug(f"Stored output for node {node_id} ({node_label}) in workflow state")
            except Exception as e:
                logger.warning(f"Failed to store node output in state: {e}", exc_info=True)
        else:
            logger.debug(f"Not storing node output - no workflow_id provided")

        # Capture time-travel snapshot: node complete
        if self.snapshot_service and execution_id:
            try:
                snap_node = _SnapshotNodeStub(node_id, node_type)
                duration_ms = (datetime.utcnow() - start_time).total_seconds() * 1000
                await self.snapshot_service.capture_node_complete(
                    execution_id=execution_id,
                    workflow_id=UUID(workflow_id) if workflow_id else execution_id,
                    organization_id=self._context.organization_id,
                    node=snap_node,
                    input_state=node_data.get('data', {}),
                    output_state=node_output,
                    variables=self._context.variables,
                    duration_ms=duration_ms,
                    cost=cost,
                    tokens_used=tokens_used,
                )
            except Exception as e:
                logger.debug(f"Time-travel snapshot (node_complete) failed: {e}")

        # Send success status with routing information
        await send_update(ExecutionEvent(
            event_type="node_status_changed",
            node_id=node_id,
            status=NodeStatus.SUCCESS,
            message=f"Completed {node_label}",
            cost=cost,
            execution_time=execution_time,
            data=node_output,
            actual_model=routing_decision.model if routing_decision else None,
            actual_provider=routing_decision.provider if routing_decision else None,
            routing_reason=routing_decision.reason if routing_decision else None,
        ))

    async def _execute_llm_node(
        self,
        node_data: Dict,
        routing_decision,
        workflow_id: Optional[str] = None,
        node_id: Optional[str] = None
    ) -> LLMResponse:
        """
        Execute LLM node with automatic failover via SmartRouter.

        Uses the FailoverExecutor to handle provider failures and automatic
        failover to backup providers.

        Args:
            node_data: Node configuration
            routing_decision: Routing decision with provider, model, and fallback
            workflow_id: Workflow ID for hook context
            node_id: Node ID for hook context

        Returns:
            LLMResponse with actual metrics

        Raises:
            ProviderError: If all providers fail (no simulated fallback)
        """
        # Build prompt from node configuration
        data = node_data.get('data') or {}
        agent_label = data.get('label', 'Agent')
        agent_config = data.get('config') or {}  # Use 'or {}' to handle None values
        capabilities = data.get('capabilities') or []  # Use 'or []' to handle None values

        # Construct system message based on agent type
        # Use systemPrompt if provided (from workflow builder), otherwise build from label
        system_message = data.get('systemPrompt') or f"You are {agent_label}."
        if not data.get('systemPrompt') and capabilities:
            system_message += f" You have the following capabilities: {', '.join(capabilities)}."

        # Get user input (prompt) - check multiple locations where it might be stored:
        # 1. data.prompt (frontend stores it here)
        # 2. data.config.prompt (API/programmatic might store it here)
        # 3. Default fallback
        explicit_prompt = data.get('prompt') or agent_config.get('prompt') or ''

        # Always gather upstream context (previous node outputs / workflow input)
        # so the LLM has the actual data to work with
        upstream_data = ''
        if workflow_id:
            upstream_data = await self._gather_upstream_context(node_id, workflow_id)

        # Combine: if there's both a prompt and upstream data, include both
        if explicit_prompt and upstream_data:
            user_input = f"{explicit_prompt}\n\n{upstream_data}"
        elif upstream_data:
            user_input = upstream_data
        elif explicit_prompt:
            user_input = explicit_prompt
        else:
            user_input = 'Execute your task.'

        logger.debug(f"Prompt sources: data.prompt={data.get('prompt') is not None}, config.prompt={agent_config.get('prompt') is not None}, systemPrompt={data.get('systemPrompt') is not None}")

        # CRITICAL: Substitute variables in the prompt (e.g., {{input.title}})
        if workflow_id:
            logger.debug(f"Substituting variables in prompt")
            user_input = await self._substitute_variables(user_input, workflow_id)
            system_message = await self._substitute_variables(system_message, workflow_id)

        messages = [
            {"role": "system", "content": system_message},
            {"role": "user", "content": user_input}
        ]

        # Estimate tokens for hooks
        estimated_tokens = sum(len(m["content"].split()) * 1.3 for m in messages)
        estimated_cost = estimated_tokens * 0.00001  # Rough estimate

        # PRE-LLM HOOKS: Input validation, enrichment, cost guardrails
        hook_context = HookContext(
            workflow_id=workflow_id,
            node_id=node_id,
            model=routing_decision.model,
            provider=routing_decision.provider,
            estimated_cost=estimated_cost,
            estimated_tokens=int(estimated_tokens)
        )

        if self.hook_manager:
            try:
                pre_hook_results, messages = await self.hook_manager.execute_hooks(
                    HookType.PRE_LLM_CALL,
                    messages,
                    hook_context
                )
                logger.debug(f"Pre-LLM hooks executed: {len(pre_hook_results)} hooks")
            except RuntimeError as e:
                # Hook blocked execution
                logger.warning(f"Pre-LLM hook blocked execution: {e}")
                raise

        # Get API keys from context or stored credentials
        api_key = None
        fallback_api_key = None
        if self._context and self._context.llm_api_keys:
            api_key = self._context.llm_api_keys.get(routing_decision.provider)
            if routing_decision.fallback_provider:
                fallback_api_key = self._context.llm_api_keys.get(routing_decision.fallback_provider)

        # If no API key in context, try to load from stored integration credentials
        if not api_key:
            api_key = await self._get_llm_api_key(routing_decision.provider)
        if not fallback_api_key and routing_decision.fallback_provider:
            fallback_api_key = await self._get_llm_api_key(routing_decision.fallback_provider)

        # Use FailoverExecutor for automatic failover handling
        if self.routing_resolver:
            failover_executor = self.routing_resolver.get_failover_executor()
            try:
                failover_result = await failover_executor.execute(
                    messages=messages,
                    routing_decision=routing_decision,
                    max_tokens=agent_config.get('max_tokens', 1000),
                    temperature=agent_config.get('temperature', 0.7),
                    api_key=api_key,
                    fallback_api_key=fallback_api_key,
                )

                # Log failover if it occurred
                if failover_result.failover_used:
                    logger.warning(
                        f"LLM failover occurred: {failover_result.original_provider} -> "
                        f"{failover_result.provider} (reason: {failover_result.failover_reason})"
                    )

                # Convert to LLMResponse for backward compatibility
                llm_response = failover_result.to_llm_response()

                logger.info(
                    f"LLM call completed: {llm_response.provider}/{llm_response.model} "
                    f"({llm_response.latency_ms:.0f}ms, ${llm_response.cost:.4f})"
                    f"{' [FAILOVER]' if failover_result.failover_used else ''}"
                )

                # POST-LLM HOOKS: Output validation, PII redaction, content filtering
                if self.hook_manager:
                    try:
                        post_hook_results, llm_response = await self.hook_manager.execute_hooks(
                            HookType.POST_LLM_CALL,
                            llm_response,
                            hook_context
                        )
                        logger.debug(f"Post-LLM hooks executed: {len(post_hook_results)} hooks")
                    except RuntimeError as e:
                        # Hook blocked output
                        logger.warning(f"Post-LLM hook blocked output: {e}")
                        raise

                return llm_response

            except ProviderError as e:
                # All providers failed - no fallback to simulation
                logger.error(
                    f"All LLM providers failed for node {node_id}: {e}"
                )
                raise RuntimeError(
                    f"LLM execution failed - all providers unavailable: {e}"
                )

        else:
            # Fallback to direct call_llm if routing_resolver not available
            # This maintains backward compatibility
            logger.warning("No routing_resolver available - using direct LLM call without failover")
            try:
                llm_response = await call_llm(
                    provider=routing_decision.provider,
                    model=routing_decision.model,
                    messages=messages,
                    max_tokens=agent_config.get('max_tokens', 1000),
                    temperature=agent_config.get('temperature', 0.7),
                    api_key=api_key
                )
                logger.info(
                    f"LLM call completed: {llm_response.provider}/{llm_response.model} "
                    f"({llm_response.latency_ms:.0f}ms, ${llm_response.cost:.4f})"
                )

                # POST-LLM HOOKS
                if self.hook_manager:
                    try:
                        post_hook_results, llm_response = await self.hook_manager.execute_hooks(
                            HookType.POST_LLM_CALL,
                            llm_response,
                            hook_context
                        )
                        logger.debug(f"Post-LLM hooks executed: {len(post_hook_results)} hooks")
                    except RuntimeError as e:
                        logger.warning(f"Post-LLM hook blocked output: {e}")
                        raise

                return llm_response

            except Exception as e:
                logger.error(f"LLM execution failed (no failover): {e}")
                raise RuntimeError(f"LLM execution failed: {e}")

    async def _execute_tool_node(
        self,
        node_data: Dict,
        node_id: str,
        workflow_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Execute Tool/API node with real HTTP request and hook integration.

        Args:
            node_data: Node configuration
            node_id: Node ID for error reporting
            workflow_id: Workflow ID for state context

        Returns:
            Dict with latency_ms, cost, status_code, response_data
        """
        import httpx
        import time
        import json
        import re

        tool_config = node_data['data'].get('toolConfig', {})
        url = tool_config.get('url')
        method = tool_config.get('method', 'GET').upper()
        timeout_ms = tool_config.get('timeout', 30000)
        auth_config = tool_config.get('auth', {})
        body = tool_config.get('body')
        headers = tool_config.get('headers', {}).copy()

        if not url:
            raise ValueError(f"Tool node {node_id} has no URL configured")

        # Substitute variables from workflow state ({{node_id.field}})
        if workflow_id:
            url = await self._substitute_variables(url, workflow_id)
            if body:
                body = await self._substitute_variables(body, workflow_id)

        # PRE-TOOL HOOKS: Parameter validation, auth injection, URL whitelist
        tool_params = {
            'url': url,
            'method': method,
            'headers': headers,
            'body': body,
            'auth': auth_config
        }

        hook_context = HookContext(
            workflow_id=workflow_id,
            node_id=node_id,
            tool_name=node_data['data'].get('label', 'unknown'),
            url=url
        )

        if self.hook_manager:
            try:
                pre_hook_results, tool_params = await self.hook_manager.execute_hooks(
                    HookType.PRE_TOOL_CALL,
                    tool_params,
                    hook_context
                )
                logger.debug(f"Pre-Tool hooks executed: {len(pre_hook_results)} hooks")

                # Extract potentially modified values
                url = tool_params.get('url', url)
                method = tool_params.get('method', method)
                headers = tool_params.get('headers', headers)
                body = tool_params.get('body', body)
                auth_config = tool_params.get('auth', auth_config)
            except RuntimeError as e:
                # Hook blocked execution
                logger.warning(f"Pre-Tool hook blocked execution: {e}")
                raise

        # Build auth headers
        auth_type = auth_config.get('type', 'none')
        if auth_type == 'api_key':
            header_name = auth_config.get('headerName', 'X-API-Key')
            api_key = auth_config.get('apiKey', '')
            if api_key:
                headers[header_name] = api_key
        elif auth_type == 'bearer':
            bearer_token = auth_config.get('bearerToken', '')
            if bearer_token:
                headers['Authorization'] = f'Bearer {bearer_token}'
        elif auth_type == 'basic':
            import base64
            username = auth_config.get('username', '')
            password = auth_config.get('password', '')
            if username:
                credentials = base64.b64encode(f'{username}:{password}'.encode()).decode()
                headers['Authorization'] = f'Basic {credentials}'

        # Add Content-Type for POST/PUT/PATCH
        if method in ['POST', 'PUT', 'PATCH'] and body and 'Content-Type' not in headers:
            headers['Content-Type'] = 'application/json'

        # Make HTTP request
        start_time = time.time()
        try:
            async with httpx.AsyncClient(timeout=timeout_ms / 1000) as client:
                # Parse body if it's a string
                request_body = None
                if body:
                    try:
                        request_body = json.loads(body)
                    except json.JSONDecodeError:
                        request_body = body  # Send as raw string

                response = await client.request(
                    method=method,
                    url=url,
                    headers=headers,
                    json=request_body if isinstance(request_body, dict) else None,
                    content=request_body if isinstance(request_body, str) else None,
                )

                latency_ms = (time.time() - start_time) * 1000

                # Parse response
                try:
                    response_data = response.json()
                except:
                    response_data = {"text": response.text}

                logger.info(
                    f"HTTP {method} {url} completed: "
                    f"{response.status_code} ({latency_ms:.0f}ms)"
                )

                tool_result = {
                    'latency_ms': latency_ms,
                    'cost': 0.0001,  # Minimal cost for HTTP calls
                    'status_code': response.status_code,
                    'response_data': response_data,
                    'success': 200 <= response.status_code < 300,
                }

                # POST-TOOL HOOKS: Response transformation, error handling
                if self.hook_manager:
                    try:
                        post_hook_results, tool_result = await self.hook_manager.execute_hooks(
                            HookType.POST_TOOL_CALL,
                            tool_result,
                            hook_context
                        )
                        logger.debug(f"Post-Tool hooks executed: {len(post_hook_results)} hooks")
                    except RuntimeError as e:
                        # Hook blocked result
                        logger.warning(f"Post-Tool hook blocked result: {e}")
                        raise

                return tool_result

        except httpx.TimeoutException:
            latency_ms = (time.time() - start_time) * 1000
            logger.error(f"HTTP {method} {url} timed out after {timeout_ms}ms")
            raise RuntimeError(f"HTTP request timed out after {timeout_ms}ms")

        except Exception as e:
            latency_ms = (time.time() - start_time) * 1000
            logger.error(f"HTTP {method} {url} failed: {e}")
            raise RuntimeError(f"HTTP request failed: {str(e)}")

    async def _get_llm_api_key(self, provider: str) -> Optional[str]:
        """
        Get LLM API key from stored integration credentials.

        Looks up the integration installation for the provider and extracts
        the API key from the encrypted credentials.

        Args:
            provider: LLM provider name (groq, openai, anthropic, etc.)

        Returns:
            API key string if found, None otherwise
        """
        from sqlalchemy import select

        try:
            async with AsyncSessionLocal() as session:
                query = select(IntegrationInstallationModel).join(
                    IntegrationModel,
                    IntegrationInstallationModel.integration_id == IntegrationModel.integration_id
                ).where(
                    IntegrationModel.slug == provider
                )
                result = await session.execute(query)
                installation = result.scalar_one_or_none()

                if installation and installation.auth_credentials:
                    credentials = decrypt_credentials(installation.auth_credentials)
                    # Ensure credentials is a dict before calling .get()
                    if credentials and isinstance(credentials, dict):
                        # API key might be stored as 'api_key' or 'apiKey'
                        api_key = credentials.get('api_key') or credentials.get('apiKey')
                        if api_key:
                            logger.info(f"Loaded API key for {provider} from stored credentials")
                            return api_key

            logger.debug(f"No stored API key found for {provider}")
            return None

        except Exception as e:
            logger.warning(f"Failed to load API key for {provider}: {e}")
            return None

    async def _execute_integration_node(
        self,
        node_data: Dict,
        node_id: str,
        workflow_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Execute Integration node (Discord, Slack, Groq, etc.) with real API calls.

        Uses the declarative integration system to:
        1. Look up integration config from registry
        2. Get stored credentials for the organization
        3. Execute the action via HTTP executor

        Args:
            node_data: Node configuration with integrationConfig
            node_id: Node ID for error reporting
            workflow_id: Workflow ID for state context

        Returns:
            Dict with latency_ms, cost, status_code, response_data
        """
        import time
        from sqlalchemy import select
        from backend.shared.integration_models import (
            IntegrationModel,
            IntegrationInstallationModel
        )
        from backend.shared.credential_manager import decrypt_credentials
        from backend.database.session import AsyncSessionLocal

        start_time = time.time()

        # Get integration config from node
        integration_config = node_data['data'].get('integrationConfig') or {}
        integration_type = integration_config.get('integrationType')
        action_name = integration_config.get('action', 'send_message')
        parameters = integration_config.get('parameters') or {}

        if not integration_type:
            raise ValueError(f"Integration node {node_id} has no integrationType configured")

        logger.info(f"Executing integration: {integration_type}.{action_name}")

        # Substitute variables from workflow state in parameters
        if workflow_id and parameters:
            for key, value in parameters.items():
                if isinstance(value, str):
                    parameters[key] = await self._substitute_variables(value, workflow_id)

        # Get integration from registry
        registry = get_integration_registry()
        integration = registry.get(integration_type)

        if not integration:
            raise ValueError(f"Integration '{integration_type}' not found in registry")

        # Get the action config
        action = integration.get_action(action_name)
        if not action:
            available = list(integration.actions.keys())
            raise ValueError(
                f"Action '{action_name}' not found for integration '{integration_type}'. "
                f"Available: {available}"
            )

        # Get stored credentials from database
        org_id = self._context.organization_id if self._context else "default-org"

        # Fetch credentials - ALWAYS use a fresh session to avoid transaction state issues
        # If a previous operation (like LLM call) failed, the shared session may have
        # an aborted transaction that would block all subsequent queries
        credentials_data = {}
        try:
            async def fetch_credentials(db_session):
                # First, check if the integration record exists
                int_query = select(IntegrationModel).where(IntegrationModel.slug == integration_type)
                int_result = await db_session.execute(int_query)
                integration_record = int_result.scalar_one_or_none()
                logger.info(f"[CRED-DEBUG] IntegrationModel for {integration_type}: {integration_record}")
                if integration_record:
                    logger.info(f"[CRED-DEBUG]   integration_id: {integration_record.integration_id}")

                # Check all installations for this integration
                if integration_record:
                    all_inst_query = select(IntegrationInstallationModel).where(
                        IntegrationInstallationModel.integration_id == integration_record.integration_id
                    )
                    all_inst_result = await db_session.execute(all_inst_query)
                    all_installations = all_inst_result.scalars().all()
                    logger.info(f"[CRED-DEBUG] All installations for {integration_type}: {len(all_installations)}")
                    for inst in all_installations:
                        logger.info(f"[CRED-DEBUG]   org_id={inst.organization_id}, status={inst.status}, has_creds={inst.auth_credentials is not None}")

                query = select(IntegrationInstallationModel).join(
                    IntegrationModel,
                    IntegrationInstallationModel.integration_id == IntegrationModel.integration_id
                ).where(
                    IntegrationModel.slug == integration_type,
                    IntegrationInstallationModel.organization_id == org_id
                )
                result = await db_session.execute(query)
                installation = result.scalar_one_or_none()

                # Fallback: if no installation found for this org_id, try to find ANY installation
                # This handles cases where credentials were stored with a different org_id
                if not installation:
                    logger.warning(f"No installation found for org_id={org_id}, trying fallback query")
                    fallback_query = select(IntegrationInstallationModel).join(
                        IntegrationModel,
                        IntegrationInstallationModel.integration_id == IntegrationModel.integration_id
                    ).where(
                        IntegrationModel.slug == integration_type
                    )
                    fallback_result = await db_session.execute(fallback_query)
                    installation = fallback_result.scalar_one_or_none()
                    if installation:
                        logger.warning(f"Found {integration_type} installation with org_id={installation.organization_id} (expected {org_id})")

                return installation

            # Always create a new session for credential fetching
            async with AsyncSessionLocal() as session:
                installation = await fetch_credentials(session)

            if installation and installation.auth_credentials:
                decrypted = decrypt_credentials(installation.auth_credentials)
                # Ensure decrypted credentials is a dict
                if decrypted and isinstance(decrypted, dict):
                    credentials_data = decrypted
                    logger.info(f"Found stored credentials for {integration_type}")
                else:
                    logger.warning(f"Invalid credentials format for {integration_type}")
            else:
                logger.warning(f"No stored credentials found for {integration_type} (org_id={org_id})")
        except Exception as e:
            logger.warning(f"Could not fetch credentials from DB: {e}")

        # Create credentials object
        credentials = IntegrationCredentials(
            integration_id=integration_type,
            auth_type=integration.auth.type,
            data=credentials_data
        )

        # Execute the action using IntegrationActionExecutor
        # It takes integration_id and action_name, not the config objects
        executor = get_action_executor()
        result = await executor.execute(
            integration_id=integration_type,
            action_name=action_name,
            credentials=credentials,
            parameters=parameters
        )

        latency_ms = (time.time() - start_time) * 1000

        if result.success:
            logger.info(f"Integration {integration_type}.{action_name} succeeded in {latency_ms:.0f}ms")
            return {
                'latency_ms': latency_ms,
                'cost': 0.0001,  # Minimal cost for API calls
                'status_code': 200,
                'response_data': result.data or {},
                'success': True
            }
        else:
            logger.error(f"Integration {integration_type}.{action_name} failed: {result.error}")
            raise RuntimeError(f"Integration action failed: {result.error}")

    async def _execute_memory_node(
        self,
        node_data: Dict,
        node_id: str
    ) -> Dict[str, Any]:
        """
        Execute Memory node with real vector database operation.

        Args:
            node_data: Node configuration
            node_id: Node ID for error reporting

        Returns:
            Dict with latency_ms, cost, tokens_used, response_data
        """
        import time
        from backend.shared.memory_service import MemoryService
        from backend.database.session import AsyncSessionLocal

        memory_config = node_data['data'].get('memoryConfig', {})
        operation = memory_config.get('operation', 'query')
        provider_id = memory_config.get('providerId')
        namespace = memory_config.get('namespace', 'default')

        if not provider_id:
            raise ValueError(f"Memory node {node_id} has no provider ID configured")

        # Template variable substitution (simple version)
        def substitute_variables(text: str) -> str:
            """Replace {{node_id.field}} with actual values from workflow context"""
            # For now, just return as-is. In production, this would look up values from previous nodes
            return text if text else ''

        start_time = time.time()

        try:
            async with AsyncSessionLocal() as db:
                service = MemoryService(db)

                if operation == 'store':
                    # Store memory
                    content = substitute_variables(memory_config.get('content', ''))
                    if not content:
                        raise ValueError(f"Memory node {node_id} has no content to store")

                    metadata = memory_config.get('metadata', {})

                    memory_id = await service.store_memory(
                        organization_id=self._context.organization_id,
                        content=content,
                        namespace=namespace,
                        memory_type=memory_config.get('memoryType', 'long_term'),
                        metadata=metadata,
                        provider_config_id=provider_id,
                        embedding_api_key=self._context.embedding_api_key
                    )

                    latency_ms = (time.time() - start_time) * 1000
                    logger.info(
                        f"Memory STORE to {provider_id}/{namespace} completed: "
                        f"{memory_id} ({latency_ms:.0f}ms)"
                    )

                    return {
                        'latency_ms': latency_ms,
                        'cost': 0.0001,  # Minimal cost for embedding
                        'tokens_used': len(content.split()) * 2,  # Rough estimate
                        'response_data': {'memory_id': memory_id, 'status': 'stored'},
                        'success': True,
                    }

                elif operation == 'query':
                    # Query memories
                    query = substitute_variables(memory_config.get('query', ''))
                    if not query:
                        raise ValueError(f"Memory node {node_id} has no query configured")

                    limit = memory_config.get('limit', 5)
                    filters = memory_config.get('filters', {})

                    memories = await service.retrieve_memories(
                        organization_id=self._context.organization_id,
                        query=query,
                        namespace=namespace,
                        memory_types=None,
                        filters=filters,
                        top_k=limit,
                        min_score=0.0,
                        provider_config_id=provider_id,
                        embedding_api_key=self._context.embedding_api_key
                    )

                    latency_ms = (time.time() - start_time) * 1000
                    logger.info(
                        f"Memory QUERY to {provider_id}/{namespace} completed: "
                        f"{len(memories)} results ({latency_ms:.0f}ms)"
                    )

                    return {
                        'latency_ms': latency_ms,
                        'cost': 0.0001,  # Minimal cost for embedding
                        'tokens_used': len(query.split()) * 2,  # Rough estimate
                        'response_data': {
                            'memories': [
                                {
                                    'id': m.id,
                                    'content': m.content,
                                    'score': m.score,
                                    'metadata': m.metadata
                                }
                                for m in memories
                            ],
                            'count': len(memories)
                        },
                        'success': True,
                    }

                elif operation == 'delete':
                    # Delete memory
                    memory_id = memory_config.get('memoryId')
                    if not memory_id:
                        raise ValueError(f"Memory node {node_id} has no memory ID to delete")

                    deleted = await service.delete_memory(
                        organization_id=self._context.organization_id,
                        memory_id=memory_id,
                        namespace=namespace,
                        provider_config_id=provider_id
                    )

                    latency_ms = (time.time() - start_time) * 1000
                    logger.info(
                        f"Memory DELETE from {provider_id}/{namespace} completed: "
                        f"{memory_id} ({latency_ms:.0f}ms)"
                    )

                    return {
                        'latency_ms': latency_ms,
                        'cost': 0.0,  # No cost for delete
                        'tokens_used': 0,
                        'response_data': {'status': 'deleted' if deleted else 'not_found'},
                        'success': deleted,
                    }

                else:
                    raise ValueError(f"Unknown memory operation: {operation}")

        except Exception as e:
            latency_ms = (time.time() - start_time) * 1000
            logger.error(f"Memory {operation} to {provider_id}/{namespace} failed: {e}")
            raise RuntimeError(f"Memory operation failed: {str(e)}")

    async def _execute_knowledge_node(
        self,
        node_data: Dict,
        node_id: str
    ) -> Dict[str, Any]:
        """
        Execute Knowledge node with real RAG query.

        Args:
            node_data: Node configuration
            node_id: Node ID for error reporting

        Returns:
            Dict with latency_ms, cost, tokens_used, response_data
        """
        import time
        from backend.shared.rag_service import RAGService
        from backend.database.session import AsyncSessionLocal

        knowledge_config = node_data['data'].get('knowledgeConfig', {})
        connector_id = knowledge_config.get('connectorId')
        query = knowledge_config.get('query')

        if not connector_id:
            raise ValueError(f"Knowledge node {node_id} has no connector ID configured")

        if not query:
            raise ValueError(f"Knowledge node {node_id} has no query configured")

        # Template variable substitution
        def substitute_variables(text: str) -> str:
            """Replace {{node_id.field}} with actual values from workflow context"""
            # For now, just return as-is. In production, this would look up values from previous nodes
            return text if text else ''

        query = substitute_variables(query)
        limit = knowledge_config.get('limit', 5)
        min_score = knowledge_config.get('minScore', 0.7)
        filters = knowledge_config.get('filters', {})
        rerank = knowledge_config.get('rerank', False)

        start_time = time.time()

        try:
            async with AsyncSessionLocal() as db:
                service = RAGService(db)

                # Query knowledge base
                results = await service.query_documents(
                    organization_id=self._context.organization_id,
                    connector_id=connector_id,
                    query=query,
                    top_k=limit,
                    min_score=min_score,
                    filters=filters,
                    rerank=rerank,
                    embedding_api_key=self._context.embedding_api_key
                )

                latency_ms = (time.time() - start_time) * 1000
                logger.info(
                    f"Knowledge query to {connector_id} completed: "
                    f"{len(results)} results ({latency_ms:.0f}ms)"
                )

                return {
                    'latency_ms': latency_ms,
                    'cost': 0.0001 + (0.0001 if rerank else 0),  # Small cost for embeddings + optional rerank
                    'tokens_used': len(query.split()) * 2,  # Rough estimate
                    'response_data': {
                        'results': [
                            {
                                'chunk_id': r.chunk_id,
                                'document_id': r.document_id,
                                'content': r.content,
                                'score': r.score,
                                'document_title': r.document_title,
                                'source_path': r.source_path,
                                'metadata': r.metadata
                            }
                            for r in results
                        ],
                        'count': len(results)
                    },
                    'success': True,
                }

        except Exception as e:
            latency_ms = (time.time() - start_time) * 1000
            logger.error(f"Knowledge query to {connector_id} failed: {e}")
            raise RuntimeError(f"Knowledge query failed: {str(e)}")

    async def _execute_webhook_node(
        self,
        node_data: Dict,
        node_id: str
    ) -> Dict[str, Any]:
        """
        Execute Webhook node - sets up webhook listener configuration.

        In production, this would:
        1. Register the webhook endpoint with the configured authentication
        2. Wait for incoming HTTP requests
        3. Validate authentication
        4. Return configured response status

        For now, this simulates webhook readiness.

        Args:
            node_data: Node configuration
            node_id: Node ID for logging

        Returns:
            Dict with latency_ms, response_data
        """
        import time

        webhook_config = node_data['data'].get('webhookConfig', {})
        method = webhook_config.get('method', 'POST')
        auth_type = webhook_config.get('authentication', {}).get('type', 'none')
        response_status = webhook_config.get('responseStatus', 200)

        start_time = time.time()

        # In production, this would:
        # 1. Generate webhook URL: /api/webhooks/{workflow_id}/{node_id}
        # 2. Store webhook config in database
        # 3. Wait for incoming request (would be handled by separate webhook handler)
        # 4. Validate auth based on auth_type
        # 5. Return configured response_status

        # For now, simulate webhook being triggered
        await asyncio.sleep(0.1)  # Simulate minimal processing

        latency_ms = (time.time() - start_time) * 1000

        webhook_url = f"/api/webhooks/{node_id}"
        logger.info(
            f"Webhook node {node_id} ready: "
            f"{method} {webhook_url} (auth: {auth_type}, status: {response_status})"
        )

        return {
            'latency_ms': latency_ms,
            'response_data': {
                'webhook_url': webhook_url,
                'method': method,
                'authentication': auth_type,
                'response_status': response_status,
                'status': 'ready'
            },
            'success': True,
        }

    async def _execute_hitl_node(
        self,
        node_data: Dict,
        node_id: str,
        send_update: callable
    ) -> Dict[str, Any]:
        """
        Execute HITL (Human-in-the-Loop) node - requires manual approval.

        In production, this would:
        1. Send notifications via configured channels (email, Slack, Teams)
        2. Create approval request in database
        3. Wait for approver response or timeout
        4. Take timeout action if no response

        For now, this simulates the approval process.

        Args:
            node_data: Node configuration
            node_id: Node ID for logging
            send_update: Callback to send status updates

        Returns:
            Dict with latency_ms, response_data
        """
        import time

        hitl_config = node_data['data'].get('hitlConfig', {})
        approval_type = hitl_config.get('approvalType', 'any')
        timeout_minutes = hitl_config.get('timeout', 60)
        timeout_action = hitl_config.get('timeoutAction', 'reject')
        notify_via = hitl_config.get('notifyVia', ['email'])
        approvers = hitl_config.get('approvers', [])

        if not approvers:
            raise ValueError(f"HITL node {node_id} has no approvers configured")

        start_time = time.time()

        # Send notification about pending approval
        await send_update(ExecutionEvent(
            event_type="hitl_approval_requested",
            node_id=node_id,
            message=f"Approval requested from {len(approvers)} approver(s)",
            data={
                'approval_type': approval_type,
                'approvers': approvers,
                'notify_via': notify_via,
                'timeout_minutes': timeout_minutes,
            }
        ))

        logger.info(
            f"HITL node {node_id} requesting approval: "
            f"type={approval_type}, approvers={len(approvers)}, "
            f"timeout={timeout_minutes}min, action={timeout_action}"
        )

        # Create actual HITL approval request in database
        title = hitl_config.get('title', f'Approval required for node {node_id}')
        description = hitl_config.get('description', 'Workflow execution paused for human approval.')
        context = hitl_config.get('context', {})

        # Map priority string to enum
        priority_map = {
            'low': ApprovalPriority.LOW,
            'medium': ApprovalPriority.MEDIUM,
            'high': ApprovalPriority.HIGH,
            'critical': ApprovalPriority.CRITICAL,
        }
        priority = priority_map.get(hitl_config.get('priority', 'medium'), ApprovalPriority.MEDIUM)

        # Map notification channels
        channel_map = {
            'email': NotificationChannel.EMAIL,
            'slack': NotificationChannel.SLACK,
            'sms': NotificationChannel.SMS,
            'webhook': NotificationChannel.WEBHOOK,
            'in_app': NotificationChannel.IN_APP,
        }
        notification_channels = [
            channel_map.get(c, NotificationChannel.EMAIL)
            for c in notify_via if c in channel_map
        ]

        # Create approval request using HITL service
        async with AsyncSessionLocal() as db:
            approval_data = ApprovalRequestCreate(
                workflow_execution_id=self.execution_id if hasattr(self, 'execution_id') else 0,
                node_id=node_id,
                title=title,
                description=description,
                context=context,
                required_approvers=approvers,
                required_approval_count=len(approvers) if approval_type == 'all' else 1,
                priority=priority,
                timeout_seconds=timeout_minutes * 60,
                timeout_action=timeout_action,
                notification_channels=notification_channels,
            )

            approval = await HITLService.create_approval_request(
                db, approval_data, user_id='workflow_executor', organization_id=1  # Default org for now
            )
            approval_id = approval.id

            logger.info(f"HITL approval request created: ID {approval_id}")

            await send_update(ExecutionEvent(
                event_type="hitl_approval_created",
                node_id=node_id,
                message=f"Approval request #{approval_id} created, waiting for decision",
                data={
                    'approval_id': approval_id,
                    'title': title,
                    'approvers': approvers,
                    'timeout_minutes': timeout_minutes,
                }
            ))

            # Poll for approval decision with timeout
            poll_interval = 5  # seconds
            max_wait = timeout_minutes * 60
            waited = 0
            approved = False
            approval_decision = 'pending'

            from sqlalchemy import select
            from backend.shared.hitl_models import ApprovalRequest

            while waited < max_wait:
                # CRITICAL: Use a fresh session for each poll to see updates from other sessions
                # The original session caches query results and won't see UI approval updates
                async with AsyncSessionLocal() as poll_db:
                    stmt = select(ApprovalRequest).where(ApprovalRequest.id == approval_id)
                    result = await poll_db.execute(stmt)
                    current_approval = result.scalar_one_or_none()

                    if current_approval:
                        logger.debug(f"HITL poll: approval {approval_id} status = {current_approval.status}")
                        if current_approval.status in [ApprovalStatus.APPROVED, ApprovalStatus.TIMEOUT_APPROVED]:
                            approved = True
                            approval_decision = 'approved'
                            break
                        elif current_approval.status in [ApprovalStatus.REJECTED, ApprovalStatus.TIMEOUT_REJECTED, ApprovalStatus.CANCELLED]:
                            approved = False
                            approval_decision = current_approval.status.value
                            break

                # Wait before polling again
                await asyncio.sleep(poll_interval)
                waited += poll_interval

                # Log waiting status periodically
                if waited % 30 == 0:
                    logger.info(f"HITL node {node_id} waiting for approval... ({waited}s elapsed)")

            # Handle timeout
            if approval_decision == 'pending':
                logger.warning(f"HITL node {node_id} timed out after {timeout_minutes} minutes")
                approval_decision = f'timeout_{timeout_action}'
                approved = (timeout_action == 'approve')

        latency_ms = (time.time() - start_time) * 1000

        await send_update(ExecutionEvent(
            event_type="hitl_approval_completed",
            node_id=node_id,
            message=f"Approval {approval_decision}",
            data={
                'decision': approval_decision,
                'approved_by': approvers[0] if approved else None,
            }
        ))

        logger.info(
            f"HITL node {node_id} {approval_decision} ({latency_ms:.0f}ms)"
        )

        if not approved:
            raise RuntimeError(f"HITL approval rejected for node {node_id}")

        return {
            'latency_ms': latency_ms,
            'response_data': {
                'decision': approval_decision,
                'approved_by': approvers[0] if approved else None,
                'approval_type': approval_type,
                'timestamp': datetime.utcnow().isoformat(),
            },
            'success': approved,
        }

    async def _execute_print_node(
        self,
        node_data: Dict,
        node_id: str,
        workflow_id: Optional[str] = None,
        send_update: Optional[Callable] = None
    ) -> Dict[str, Any]:
        """
        Execute Print node - outputs message to Execution Log.

        This node allows non-technical users to print output at any point
        in the workflow for debugging and visibility purposes.

        Args:
            node_data: Node configuration with printConfig
            node_id: Node ID for logging
            workflow_id: Workflow ID for variable substitution
            send_update: Callback to send execution events

        Returns:
            Dict with latency_ms, response_data
        """
        import time

        print_config = node_data['data'].get('printConfig', {})
        label = print_config.get('label', 'Output')
        message = print_config.get('message', '')
        log_level = print_config.get('logLevel', 'info')
        include_timestamp = print_config.get('includeTimestamp', True)

        start_time = time.time()

        # Substitute variables from workflow state ({{node_id.field}})
        if workflow_id and message:
            message = await self._substitute_variables(message, workflow_id)

        # Build the print output
        timestamp = datetime.utcnow().isoformat() if include_timestamp else None
        print_output = {
            'label': label,
            'message': message,
            'logLevel': log_level,
            'timestamp': timestamp,
        }

        # Log to server console
        log_prefix = f"[PRINT:{label}]"
        if log_level == 'error':
            logger.error(f"{log_prefix} {message}")
        elif log_level == 'warning':
            logger.warning(f"{log_prefix} {message}")
        elif log_level == 'debug':
            logger.debug(f"{log_prefix} {message}")
        else:
            logger.info(f"{log_prefix} {message}")

        # Log to stdout for visibility during development (only in DEBUG mode)
        if logger.isEnabledFor(logging.DEBUG):
            logger.debug(f"PRINT OUTPUT [{label}]: {message} (level={log_level})")

        # Send a special print_output event to the frontend
        # This will be displayed in the Execution Log panel
        if send_update:
            await send_update(ExecutionEvent(
                event_type="print_output",
                node_id=node_id,
                message=message,
                data={
                    'label': label,
                    'message': message,
                    'logLevel': log_level,
                    'timestamp': timestamp,
                }
            ))

        latency_ms = (time.time() - start_time) * 1000

        return {
            'latency_ms': latency_ms,
            'response_data': print_output,
            'success': True,
        }

    async def _simulate_node_execution(
        self,
        node_type: str,
        node_data: Dict
    ) -> float:
        """
        Simulate node execution (replace with actual execution).

        In production, this would:
        1. Create a task for the agent
        2. Submit to queue
        3. Wait for agent to complete
        4. Return actual execution time
        """
        # Simulate different execution times based on node type
        execution_times = {
            "supervisor": 2.0,  # 2 seconds
            "worker": 1.5,      # 1.5 seconds
            "tool": 0.5,        # 0.5 seconds
        }

        wait_time = execution_times.get(node_type, 1.0)
        await asyncio.sleep(wait_time)

        return wait_time

    def _calculate_node_cost(self, node_data: Dict) -> float:
        """Calculate node execution cost (simulated)."""
        # In production, get from actual LLM usage
        data = node_data.get('data') or {}
        node_type = data.get('type', 'unknown')
        llm_model = data.get('llmModel', 'gpt-3.5-turbo')

        # Simulated costs
        costs = {
            "supervisor": {
                "gpt-4": 0.05,
                "gpt-3.5-turbo": 0.002,
                "claude-2": 0.03,
            },
            "worker": {
                "gpt-4": 0.03,
                "gpt-3.5-turbo": 0.001,
                "claude-2": 0.02,
            },
            "tool": 0.0001,  # API calls are cheap
        }

        if node_type in ["supervisor", "worker"]:
            return costs[node_type].get(llm_model, 0.001)
        else:
            return costs["tool"]

    def _estimate_tokens_used(self, node_data: Dict) -> int:
        """Estimate tokens used for a node (simulated).

        In production, this would come from actual LLM response metadata.
        """
        data = node_data.get('data') or {}
        node_type = data.get('type', 'unknown')
        llm_model = data.get('llmModel', 'gpt-3.5-turbo')

        # Simulated token usage based on node type and model
        token_estimates = {
            "supervisor": {
                "gpt-4": 2000,
                "gpt-3.5-turbo": 1500,
                "claude-2": 1800,
            },
            "worker": {
                "gpt-4": 1000,
                "gpt-3.5-turbo": 800,
                "claude-2": 900,
            },
            "tool": 0,  # Tools don't use LLM tokens directly
        }

        if node_type in ["supervisor", "worker"]:
            return token_estimates[node_type].get(llm_model, 1000)
        else:
            return 0

    async def stop_execution(self, execution_id: UUID) -> bool:
        """Stop a running workflow execution."""
        if execution_id in self.active_executions:
            self.active_executions[execution_id] = False
            return True
        return False


# Global executor instance
_executor: Optional[WorkflowExecutor] = None


def get_executor(
    db=None,
    circuit_breaker_config: Optional[CircuitBreakerConfig] = None
) -> WorkflowExecutor:
    """Get global workflow executor instance.

    Args:
        db: Database session for circuit breaker persistence and routing resolver
        circuit_breaker_config: Custom circuit breaker configuration

    Returns:
        WorkflowExecutor instance with circuit breaker protection
    """
    global _executor
    # Create new executor if none exists
    if _executor is None:
        _executor = WorkflowExecutor(
            db=db,
            circuit_breaker_config=circuit_breaker_config
        )
    # CRITICAL FIX: Reinitialize if db provided but routing_resolver is None
    # This handles the case where executor was first created without db
    elif db is not None and _executor.routing_resolver is None:
        logger.info("Reinitializing executor with db for routing resolver")
        _executor = WorkflowExecutor(
            db=db,
            circuit_breaker_config=circuit_breaker_config
        )
    return _executor


def reset_executor() -> None:
    """Reset the global executor (useful for testing)."""
    global _executor
    _executor = None
