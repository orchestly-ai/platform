"""
Workflow Execution Engine

Executes visual workflows built with the DAG builder.
Supports parallel execution, conditional routing, error handling, and cost tracking.
"""

import logging
import asyncio
import copy
import sys
from typing import Optional, Dict, Any, List, Set
from datetime import datetime, timedelta
from uuid import UUID, uuid4
from enum import Enum
import json
from dataclasses import is_dataclass, asdict

# REMOVED: Recursion limit increase - should not be needed with JSON firewall fix
# sys.setrecursionlimit(5000)

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_, update

from backend.shared.workflow_models import (
    WorkflowModel, WorkflowExecutionModel, WorkflowTemplateModel,
    Workflow, WorkflowExecution, WorkflowNode, WorkflowEdge,
    NodeType, ExecutionStatus, WorkflowStatus
)
from backend.shared.cost_service import get_cost_service
from backend.shared.cost_models import CostEvent, CostCategory
from backend.shared.audit_logger import get_audit_logger
from backend.shared.audit_models import AuditEvent, AuditEventType
from backend.shared.integration_executor import IntegrationExecutor
from backend.shared.integration_models import IntegrationInstallationModel, IntegrationModel
from backend.shared.ab_testing_middleware import ABTestingMiddleware, ABOverride

logger = logging.getLogger(__name__)


def strict_json_serialize(obj: Any, depth: int = 0, max_depth: int = 50, _seen: Optional[set] = None) -> Any:
    """
    Ruthless JSON serializer with circular reference detection.
    This is the "JSON Firewall" approach from Gemini + ChatGPT combined.

    If it hits a circular reference, unknown type, or max depth, converts to string immediately.
    This breaks circular references by severing object graph links.
    """
    if _seen is None:
        _seen = set()

    if depth > max_depth:
        return "[Max Depth Exceeded]"

    # Handle None and basic JSON-safe types (these are immutable primitives, no cycles possible)
    if obj is None or isinstance(obj, (str, int, float, bool)):
        return obj

    # Handle datetime and UUID (immutable, no cycles)
    if isinstance(obj, (datetime, UUID)):
        return str(obj)

    # Handle Enum types - extract the value
    if isinstance(obj, Enum):
        return obj.value

    # Handle dataclasses
    if is_dataclass(obj) and not isinstance(obj, type):
        try:
            return strict_json_serialize(asdict(obj), depth + 1, max_depth, _seen)
        except (TypeError, RecursionError):
            return f"<{type(obj).__name__}: dataclass>"

    # Check for circular reference BEFORE recursing
    obj_id = id(obj)
    if obj_id in _seen:
        return f"[Circular Reference: {type(obj).__name__}]"

    # Add to seen set
    _seen.add(obj_id)

    # Handle Lists and Tuples
    if isinstance(obj, (list, tuple)):
        return [strict_json_serialize(item, depth + 1, max_depth, _seen) for item in obj]

    # Handle Dicts
    if isinstance(obj, dict):
        return {
            str(k): strict_json_serialize(v, depth + 1, max_depth, _seen)
            for k, v in obj.items()
        }

    # Handle Pydantic models (v1/v2 compatibility)
    if hasattr(obj, 'model_dump'):
        return strict_json_serialize(obj.model_dump(), depth + 1, max_depth, _seen)
    if hasattr(obj, 'dict'):
        return strict_json_serialize(obj.dict(), depth + 1, max_depth, _seen)

    # Handle sets - convert to list
    if isinstance(obj, (set, frozenset)):
        return [strict_json_serialize(item, depth + 1, max_depth, _seen) for item in obj]

    # Handle bytes - encode as string
    if isinstance(obj, bytes):
        try:
            return obj.decode('utf-8')
        except UnicodeDecodeError:
            return f"<bytes: {len(obj)} bytes>"

    # FALLBACK: Force string representation for complex objects
    # This breaks the cycle by severing the object graph link
    # Handles: Tasks, Agents, ORM models, coroutines, etc.
    try:
        # Try to get a clean string representation
        obj_str = str(obj)
        if len(obj_str) > 200:
            obj_str = obj_str[:200] + "..."
        return f"<{type(obj).__name__}: {obj_str}>"
    except (RecursionError, Exception):
        return f"<{type(obj).__name__}: Unprintable>"


class WorkflowExecutionEngine:
    """
    Workflow execution engine.

    Executes DAG-based workflows with:
    - Topological sorting for dependency resolution
    - Parallel execution of independent nodes
    - Conditional routing (if/switch nodes)
    - Error handling and retry logic
    - Cost tracking per node
    - Real-time status updates
    - Detailed step-by-step execution tracking
    """

    def __init__(self):
        self._executing: Dict[UUID, bool] = {}  # Track running executions
        self.execution_steps: List[Dict[str, Any]] = []  # Collect execution steps for Time-Travel Debugger

    async def execute_workflow(
        self,
        workflow_id: UUID,
        input_data: Dict[str, Any],
        triggered_by: str,
        db: AsyncSession,
        retry_execution: Optional[WorkflowExecution] = None,
    ) -> WorkflowExecution:
        """
        Execute a workflow.

        Args:
            workflow_id: ID of the workflow to execute
            input_data: Input data for the workflow
            triggered_by: User/system that triggered the execution
            db: Database session
            retry_execution: Optional existing execution to retry (preserves retry_count)

        Returns the execution instance with results.
        """
        # Load workflow
        workflow = await self._load_workflow(workflow_id, db)
        if not workflow:
            raise ValueError(f"Workflow not found: {workflow_id}")

        # Allow DRAFT workflows to execute for testing purposes
        # Only block ARCHIVED workflows
        if workflow.status == WorkflowStatus.ARCHIVED:
            raise ValueError(f"Cannot execute archived workflow")

        # Reuse existing execution for retry, or create new one
        if retry_execution:
            execution = retry_execution
            execution.status = ExecutionStatus.PENDING
            execution.started_at = None
            execution.completed_at = None
            execution.error_message = None
            execution.error_node_id = None
            logger.info(f"Retrying execution {execution.execution_id}, attempt {execution.retry_count}")
        else:
            # Create new execution record
            execution = WorkflowExecution(
                execution_id=uuid4(),
                workflow_id=workflow_id,
                workflow_version=workflow.version,
                organization_id=workflow.organization_id,
                status=ExecutionStatus.PENDING,
                triggered_by=triggered_by,
            trigger_source="manual",
            input_data=input_data,
            node_states={}
        )

        execution_model = WorkflowExecutionModel(
            execution_id=execution.execution_id,
            workflow_id=workflow_id,
            workflow_version=workflow.version,
            organization_id=workflow.organization_id,
            status=ExecutionStatus.PENDING.value,
            triggered_by=triggered_by,
            trigger_source="manual",
            input_data=input_data,
            node_states={}
        )
        db.add(execution_model)
        await db.commit()

        # Mark as executing
        self._executing[execution.execution_id] = True

        # Reset execution steps for this workflow run
        self.execution_steps = []

        try:
            # Start execution (in memory - no DB update until end)
            execution.status = ExecutionStatus.RUNNING
            execution.started_at = datetime.utcnow()

            # Execute nodes
            result = await self._execute_nodes(workflow, execution, db)

            # Complete execution
            execution.status = ExecutionStatus.COMPLETED
            execution.completed_at = datetime.utcnow()
            execution.duration_seconds = (
                execution.completed_at - execution.started_at
            ).total_seconds()

            # CRITICAL: Serialize the entire result dict to prevent circular references
            # Even though individual node outputs are serialized, the dict structure
            # can still contain cross-references that cause SQLAlchemy recursion
            execution.output_data = strict_json_serialize(result)

            # Save final execution state to DB
            await self._update_execution_final(execution, db)
            await self._update_workflow_analytics(workflow_id, execution, db)

            return execution

        except Exception as e:
            # Handle failure
            execution.status = ExecutionStatus.FAILED
            execution.completed_at = datetime.utcnow()
            if execution.started_at:
                execution.duration_seconds = (
                    execution.completed_at - execution.started_at
                ).total_seconds()
            execution.error_message = str(e)

            # Save error state to DB
            try:
                await self._update_execution_final(execution, db)
            except Exception as save_err:
                logger.error(f"Failed to save error state: {save_err}")

            # Retry logic - reuse same execution to preserve retry_count
            if workflow.retry_on_failure and execution.retry_count < workflow.max_retries:
                execution.retry_count += 1
                logger.info(
                    f"Retrying workflow execution {execution.execution_id}, "
                    f"attempt {execution.retry_count}/{workflow.max_retries}"
                )

                # Persist retry count before retrying
                try:
                    await self._update_execution_retry_count(execution, db)
                except Exception as update_err:
                    logger.error(f"Failed to persist retry count: {update_err}")

                # Retry with same execution (preserves retry_count)
                return await self.execute_workflow(
                    workflow_id,
                    input_data,
                    triggered_by,
                    db,
                    retry_execution=execution
                )

            raise

        finally:
            self._executing.pop(execution.execution_id, None)

    async def execute_workflow_with_existing(
        self,
        workflow: Workflow,
        execution_id: UUID,
        input_data: Dict[str, Any],
        triggered_by: str,
        db: AsyncSession
    ) -> WorkflowExecution:
        """
        Execute a workflow using an existing execution record and pre-loaded workflow.

        This method is called by the API endpoint which already has:
        1. Created an execution record in the database
        2. Loaded and converted the workflow to domain objects

        Args:
            workflow: Pre-loaded Workflow domain object
            execution_id: ID of existing execution record to update
            input_data: Input data for the workflow
            triggered_by: User/system that triggered the execution
            db: Database session

        Returns the execution instance with results.
        """
        # Create execution object matching the existing DB record
        execution = WorkflowExecution(
            execution_id=execution_id,
            workflow_id=workflow.workflow_id,
            workflow_version=workflow.version,
            organization_id=workflow.organization_id,
            status=ExecutionStatus.PENDING,
            triggered_by=triggered_by,
            trigger_source="manual",
            input_data=input_data,
            node_states={}
        )

        # Mark as executing
        self._executing[execution.execution_id] = True

        # Reset execution steps for this workflow run
        self.execution_steps = []

        try:
            # Start execution
            execution.status = ExecutionStatus.RUNNING
            execution.started_at = datetime.utcnow()

            # Execute nodes
            result = await self._execute_nodes(workflow, execution, db)

            # Complete execution
            execution.status = ExecutionStatus.COMPLETED
            execution.completed_at = datetime.utcnow()
            execution.duration_seconds = (
                execution.completed_at - execution.started_at
            ).total_seconds()

            # CRITICAL: Serialize the entire result dict to prevent circular references
            execution.output_data = strict_json_serialize(result)

            # Save final execution state to DB (updates existing record)
            await self._update_execution_final(execution, db)
            await self._update_workflow_analytics(workflow.workflow_id, execution, db)

            return execution

        except Exception as e:
            # Handle failure
            execution.status = ExecutionStatus.FAILED
            execution.completed_at = datetime.utcnow()
            if execution.started_at:
                execution.duration_seconds = (
                    execution.completed_at - execution.started_at
                ).total_seconds()
            execution.error_message = str(e)

            # Save error state to DB
            try:
                await self._update_execution_final(execution, db)
            except Exception as save_err:
                logger.error(f"Failed to save error state: {save_err}")

            # Retry logic
            if workflow.retry_on_failure and execution.retry_count < workflow.max_retries:
                execution.retry_count += 1
                logger.info(
                    f"Retrying workflow execution {execution.execution_id}, "
                    f"attempt {execution.retry_count}/{workflow.max_retries}"
                )

                # Persist retry count before retrying
                try:
                    await self._update_execution_retry_count(execution, db)
                except Exception as update_err:
                    logger.error(f"Failed to persist retry count: {update_err}")

                # Retry with same execution (preserves retry_count)
                return await self.execute_workflow_with_existing(
                    workflow,
                    execution_id,
                    input_data,
                    triggered_by,
                    db
                )

            raise

        finally:
            self._executing.pop(execution.execution_id, None)

    async def _execute_nodes(
        self,
        workflow: Workflow,
        execution: WorkflowExecution,
        db: AsyncSession
    ) -> Dict[str, Any]:
        """
        Execute workflow nodes in topological order.

        Supports parallel execution of independent nodes.
        """
        # Build dependency graph
        dependencies = self._build_dependency_graph(workflow.nodes, workflow.edges)

        # Find execution order (topological sort)
        execution_order = self._topological_sort(workflow.nodes, dependencies)

        # Execute nodes
        node_outputs: Dict[str, Any] = {}
        # Serialize the initial input data to prevent circular references
        node_outputs["input"] = strict_json_serialize(execution.input_data)

        for node_id in execution_order:
            node = next(n for n in workflow.nodes if n.id == node_id)

            # Check if execution was cancelled
            if not self._executing.get(execution.execution_id):
                raise RuntimeError("Execution cancelled")

            # Collect ALL previous node outputs so any node can reference {{any_node.field}}
            # This is critical for variable substitution to work correctly
            # Example: discord node referencing {{trigger-xxx.title}} or {{worker-xxx.text}}
            node_inputs = {}
            for prev_node_id, prev_output in node_outputs.items():
                # Include all previous outputs (already serialized to JSON primitives)
                node_inputs[prev_node_id] = prev_output

            # ALWAYS include the workflow's input data so nodes can access {{input.field}}
            # This may already be in node_outputs but ensure it's always available
            if "input" not in node_inputs:
                node_inputs["input"] = node_outputs.get("input", {})

            # Execute node
            try:
                node_start = datetime.utcnow()

                output = await self._execute_node(
                    node,
                    node_inputs,
                    workflow,
                    execution,
                    db
                )

                node_duration = (datetime.utcnow() - node_start).total_seconds()

                # CRITICAL: Serialize output immediately after node execution
                serialized_output = strict_json_serialize(output)
                node_outputs[node_id] = serialized_output
                logger.info(f"DEBUG: Stored output for node '{node_id}': keys={list(serialized_output.keys()) if isinstance(serialized_output, dict) else type(serialized_output)}")

                # Update node state with actual output data for frontend display
                # Include key fields that the Executions and Debugger pages need
                node_state = {
                    "status": "completed",
                    "output": serialized_output,  # Full serialized output
                    "duration": node_duration,
                    "completed_at": datetime.utcnow().isoformat()
                }

                # Extract LLM-specific metadata if available
                if isinstance(serialized_output, dict):
                    if "model" in serialized_output:
                        node_state["model"] = serialized_output.get("model")
                    if "tokens" in serialized_output:
                        node_state["tokens"] = serialized_output.get("tokens")
                    if "cost" in serialized_output:
                        node_state["cost"] = serialized_output.get("cost")
                    if "text" in serialized_output:
                        node_state["text"] = serialized_output.get("text")

                execution.node_states[node_id] = node_state

                # Skip intermediate DB update - will save at end
                # await self._update_execution_status(execution, db)

            except Exception as e:
                # Node execution failed
                execution.node_states[node_id] = {
                    "status": "failed",
                    "error": str(e),
                    "completed_at": datetime.utcnow().isoformat()
                }
                execution.error_node_id = node_id
                # Skip intermediate DB update - will save at end
                # await self._update_execution_status(execution, db)
                raise

        # Return final output (from last node or specified output node)
        return node_outputs

    async def _execute_node(
        self,
        node: WorkflowNode,
        inputs: Dict[str, Any],
        workflow: Workflow,
        execution: WorkflowExecution,
        db: AsyncSession
    ) -> Any:
        """Execute a single node and track detailed execution step"""
        logger.info(f"Executing node {node.id} (type: {node.type.value})")

        # Record step start time
        step_start_time = datetime.utcnow()
        step_id = len(self.execution_steps) + 1

        # Update node state to running (in memory only)
        execution.node_states[node.id] = {
            "status": "running",
            "started_at": step_start_time.isoformat()
        }
        # Skip intermediate DB update - will save at end
        # await self._update_execution_status(execution, db)

        # Initialize step data
        step_data = {
            "id": step_id,
            "name": node.label or node.id,
            "timestamp": step_start_time.isoformat(),
            "status": "running",
            "state": {
                "input": str(inputs)[:500] if inputs else None  # Truncate for storage
            }
        }

        try:
            # Execute based on node type
            logger.info(f"DEBUG: Executing node '{node.id}' with type '{node.type}' (value: {node.type.value if hasattr(node.type, 'value') else node.type})")
            if node.type == NodeType.AGENT_LLM or node.type == NodeType.LLM or node.type == NodeType.WORKER or node.type == NodeType.AI:
                output = await self._execute_llm_node(node, inputs, workflow, execution, db)
            elif node.type == NodeType.DATA_TRANSFORM:
                output = await self._execute_transform_node(node, inputs)
            elif node.type == NodeType.CONTROL_IF or node.type == NodeType.CONDITION:
                output = await self._execute_if_node(node, inputs)
            elif node.type == NodeType.INTEGRATION_HTTP or node.type == NodeType.HTTP:
                output = await self._execute_http_node(node, inputs)
            elif node.type == NodeType.LLM_OPENAI:
                output = await self._execute_openai_node(node, inputs, workflow, execution, db)
            elif node.type == NodeType.LLM_ANTHROPIC:
                output = await self._execute_anthropic_node(node, inputs, workflow, execution, db)
            elif node.type == NodeType.DATA_INPUT or node.type == NodeType.INPUT or node.type == NodeType.TRIGGER:
                # Pass through input data
                output = inputs.get("input", {})
            elif node.type == NodeType.DATA_OUTPUT or node.type == NodeType.OUTPUT:
                # CRITICAL FIX: Return a simple status dict, NOT the inputs reference
                output = {
                    "status": "output_complete",
                    "node_id": node.id,
                    "input_count": len(inputs)
                }
            elif node.type == NodeType.DATA_MERGE:
                # Merge node - combine all inputs into a single dict
                merged = {}
                for key, value in inputs.items():
                    if isinstance(value, dict):
                        merged.update(copy.deepcopy(value))
                output = merged
            elif node.type == NodeType.LLM_DEEPSEEK:
                output = await self._execute_deepseek_node(node, inputs, workflow, execution, db)
            elif node.type == NodeType.LLM_GOOGLE:
                output = await self._execute_google_node(node, inputs, workflow, execution, db)
            elif node.type == NodeType.DATA_SPLIT:
                # Split node - return a copy of inputs
                output = copy.deepcopy(inputs)
            elif node.type == NodeType.CONTROL_SWITCH:
                # Switch node - conditional routing
                output = await self._execute_switch_node(node, inputs)
            elif node.type == NodeType.CONTROL_LOOP:
                # Loop node - iterative execution
                output = await self._execute_loop_node(node, inputs)
            elif node.type == NodeType.CONTROL_PARALLEL:
                # Parallel node - concurrent execution
                output = await self._execute_parallel_node(node, inputs)
            elif node.type == NodeType.CONTROL_WAIT:
                # Wait node - delay execution
                output = await self._execute_wait_node(node, inputs)
            elif node.type == NodeType.AGENT_FUNCTION:
                # Function calling node
                output = await self._execute_function_node(node, inputs)
            elif node.type == NodeType.AGENT_TOOL or node.type == NodeType.TOOL:
                # Tool execution node
                output = await self._execute_tool_node(node, inputs)
            elif node.type == NodeType.INTEGRATION or node.type == NodeType.INTEGRATION_WEBHOOK or node.type == NodeType.WEBHOOK:
                # Integration nodes - execute real integrations (Discord, Gmail, Slack, etc.)
                output = await self._execute_integration_node(node, inputs, workflow, db)
            elif node.type == NodeType.SUPERVISOR:
                # Supervisor node - treat as special LLM node
                output = await self._execute_llm_node(node, inputs, workflow, execution, db)
            elif node.type == NodeType.HITL:
                # Human-in-the-loop approval node
                output = await self._execute_hitl_node(node, inputs, workflow, execution, db)
            elif node.type == NodeType.END:
                # End node - simple passthrough
                output = {"status": "workflow_completed", "node_id": node.id}
            else:
                raise ValueError(f"Unsupported node type: {node.type}")

            # Calculate duration
            step_end_time = datetime.utcnow()
            duration_seconds = (step_end_time - step_start_time).total_seconds()

            # Update step data with successful completion
            step_data["status"] = "completed"
            step_data["duration"] = f"{duration_seconds:.2f}s" if duration_seconds >= 1 else f"{int(duration_seconds * 1000)}ms"

            # Extract metadata from output if available (LLM nodes return detailed info)
            if isinstance(output, dict):
                if "model" in output:
                    step_data["state"]["model"] = output.get("model")
                if "tokens" in output:
                    tokens = output.get("tokens", {})
                    step_data["state"]["tokens"] = tokens.get("total", 0)
                if "cost" in output:
                    step_data["state"]["cost"] = output.get("cost")
                if "text" in output:
                    step_data["state"]["output"] = str(output.get("text"))[:500]  # Truncate
                else:
                    step_data["state"]["output"] = str(output)[:500]  # Truncate
            else:
                step_data["state"]["output"] = str(output)[:500]  # Truncate

            # Add completed step to execution steps list
            self.execution_steps.append(step_data)

            return output

        except Exception as e:
            # Calculate duration even on failure
            step_end_time = datetime.utcnow()
            duration_seconds = (step_end_time - step_start_time).total_seconds()

            # Update step data with failure
            step_data["status"] = "failed"
            step_data["duration"] = f"{duration_seconds:.2f}s" if duration_seconds >= 1 else f"{int(duration_seconds * 1000)}ms"
            step_data["state"]["error"] = str(e)[:500]  # Truncate error message

            # Add failed step to execution steps list
            self.execution_steps.append(step_data)

            # Re-raise the exception to maintain existing error handling
            raise

    def _get_llm_provider_for_model(self, model: str) -> str:
        """Determine LLM provider based on model name."""
        # Handle None or empty model - default to OpenAI
        if not model:
            return "openai"

        model_lower = model.lower()

        if "gpt" in model_lower or model_lower.startswith("o1"):
            return "openai"
        elif "claude" in model_lower:
            return "anthropic"
        elif "gemini" in model_lower:
            return "google-ai"
        elif "deepseek" in model_lower:
            return "deepseek"
        elif "llama" in model_lower or "mixtral" in model_lower or "gemma" in model_lower:
            return "groq"
        else:
            # Default to OpenAI for unknown models
            return "openai"

    async def _execute_llm_node(
        self,
        node: WorkflowNode,
        inputs: Dict[str, Any],
        workflow: Workflow,
        execution: WorkflowExecution,
        db: AsyncSession
    ) -> Dict[str, Any]:
        """Execute LLM agent node using configured LLM integrations."""
        import time

        # Get configuration
        config = node.data
        prompt = config.get("prompt", "")
        # Handle model being None explicitly (not just missing)
        model = config.get("model") or config.get("llmModel") or "gpt-4"
        temperature = config.get("temperature", 0.7)
        max_tokens = config.get("max_tokens", 1000)

        # Format prompt with inputs (template interpolation)
        formatted_prompt = self._interpolate_template(prompt, inputs)

        logger.info(f"LLM node: model={model}, prompt_length={len(formatted_prompt)}")

        # A/B TESTING: Check for running experiments before LLM execution
        ab_override: Optional[ABOverride] = None
        start_time = time.time()
        try:
            # Build node_data dict for A/B middleware (mimics workflow_executor format)
            node_data = {
                "data": {
                    "type": node.type.value if hasattr(node.type, 'value') else str(node.type),
                    "label": node.label or node.id,
                    "prompt": formatted_prompt,
                    "config": config,
                }
            }

            ab_override = await ABTestingMiddleware.check_and_assign(
                db=db,
                node_data=node_data,
                workflow_id=str(workflow.workflow_id),
                user_id=execution.triggered_by or "system",
                node_id=node.id,
            )

            if ab_override:
                logger.info(
                    f"[A/B Testing] Experiment matched! variant='{ab_override.variant_name}', "
                    f"model_override={ab_override.model_name}"
                )
                # Apply model override if specified
                if ab_override.model_name:
                    # Parse "provider/model" format
                    if "/" in ab_override.model_name:
                        _, model = ab_override.model_name.split("/", 1)
                    else:
                        model = ab_override.model_name
                    logger.info(f"[A/B Testing] Overriding model to: {model}")

                # Apply prompt override if specified
                if ab_override.prompt_template:
                    formatted_prompt = self._interpolate_template(ab_override.prompt_template, inputs)
                    logger.info(f"[A/B Testing] Overriding prompt (length: {len(formatted_prompt)})")
        except Exception as e:
            logger.warning(f"[A/B Testing] check_and_assign failed (non-fatal): {e}")

        # Determine which LLM provider to use
        provider_slug = self._get_llm_provider_for_model(model)
        logger.info(f"Using LLM provider: {provider_slug}")

        # Try to find an active installation for this provider
        try:
            # First, try to find org-specific installation
            installation = None

            if workflow.organization_id:
                query = select(IntegrationInstallationModel).join(
                    IntegrationModel,
                    IntegrationInstallationModel.integration_id == IntegrationModel.integration_id
                ).where(
                    and_(
                        IntegrationModel.slug == provider_slug,
                        IntegrationInstallationModel.status == "active",
                        IntegrationInstallationModel.organization_id == workflow.organization_id
                    )
                )
                result = await db.execute(query)
                installation = result.scalar_one_or_none()
                logger.info(f"Org-specific {provider_slug} installation: {installation.installation_id if installation else 'not found'}")

            # Fallback: find any active installation for this provider
            if not installation:
                query = select(IntegrationInstallationModel).join(
                    IntegrationModel,
                    IntegrationInstallationModel.integration_id == IntegrationModel.integration_id
                ).where(
                    and_(
                        IntegrationModel.slug == provider_slug,
                        IntegrationInstallationModel.status == "active"
                    )
                )
                result = await db.execute(query)
                installation = result.scalar_one_or_none()
                logger.info(f"Fallback {provider_slug} installation: {installation.installation_id if installation else 'not found'}")

            if installation:
                # Execute via IntegrationExecutor with real LLM
                executor = IntegrationExecutor(db)
                exec_result = await executor.execute(
                    installation_id=installation.installation_id,
                    action_name="chat_completion",
                    parameters={
                        "prompt": formatted_prompt,
                        "model": model,
                        "temperature": temperature,
                        "max_tokens": max_tokens
                    }
                )

                if exec_result.success:
                    response = {
                        "text": exec_result.data.get("text", ""),
                        "model": exec_result.data.get("model", model),
                        "tokens": exec_result.data.get("tokens", {"input": 0, "output": 0, "total": 0}),
                        "provider": provider_slug
                    }

                    # Track cost
                    cost = self._calculate_llm_cost(model, response["tokens"])
                    response["cost"] = cost

                    await self._track_node_cost(
                        workflow.organization_id,
                        workflow.workflow_id,
                        node.id,
                        cost,
                        response["tokens"],
                        model,
                        db
                    )

                    # A/B TESTING: Record successful completion
                    if ab_override:
                        try:
                            latency_ms = (time.time() - start_time) * 1000
                            await ABTestingMiddleware.record_result(
                                db=db,
                                override=ab_override,
                                success=True,
                                latency_ms=latency_ms,
                                cost=cost,
                            )
                            logger.info(f"[A/B Testing] Recorded success: latency={latency_ms:.0f}ms, cost=${cost:.4f}")
                            # Include A/B testing metadata in response for frontend feedback
                            response["ab_testing"] = {
                                "assignment_id": ab_override.assignment_id,
                                "experiment_id": ab_override.experiment_id,
                                "variant_name": ab_override.variant_name,
                            }
                        except Exception as ab_err:
                            logger.warning(f"[A/B Testing] record_result failed (non-fatal): {ab_err}")

                    return response
                else:
                    logger.error(f"LLM execution failed: {exec_result.error_message}")
                    # A/B TESTING: Record failure
                    if ab_override:
                        try:
                            latency_ms = (time.time() - start_time) * 1000
                            await ABTestingMiddleware.record_result(
                                db=db,
                                override=ab_override,
                                success=False,
                                latency_ms=latency_ms,
                                error_message=exec_result.error_message,
                            )
                            logger.info(f"[A/B Testing] Recorded failure: {exec_result.error_message}")
                        except Exception as ab_err:
                            logger.warning(f"[A/B Testing] record_result failed (non-fatal): {ab_err}")
                    # Fall through to simulated response

        except Exception as e:
            logger.warning(f"Failed to execute LLM via integration: {e}")
            # A/B TESTING: Record failure on exception
            if ab_override:
                try:
                    latency_ms = (time.time() - start_time) * 1000
                    await ABTestingMiddleware.record_result(
                        db=db,
                        override=ab_override,
                        success=False,
                        latency_ms=latency_ms,
                        error_message=str(e),
                    )
                    logger.info(f"[A/B Testing] Recorded exception: {e}")
                except Exception as ab_err:
                    logger.warning(f"[A/B Testing] record_result failed (non-fatal): {ab_err}")
            # Fall through to simulated response

        # Fallback: Simulated response if no integration configured
        logger.info(f"No {provider_slug} integration configured, using simulated response")
        response = {
            "text": f"[Simulated - configure {provider_slug} integration for real LLM] Response for: {formatted_prompt[:100]}...",
            "model": model,
            "tokens": {
                "input": len(formatted_prompt.split()),
                "output": 50,
                "total": len(formatted_prompt.split()) + 50
            },
            "simulated": True
        }

        # Track cost
        cost = self._calculate_llm_cost(model, response["tokens"])
        response["cost"] = cost

        await self._track_node_cost(
            workflow.organization_id,
            workflow.workflow_id,
            node.id,
            cost,
            response["tokens"],
            model,
            db
        )

        # A/B TESTING: Record simulated response (still counts as success for metrics)
        if ab_override:
            try:
                latency_ms = (time.time() - start_time) * 1000
                await ABTestingMiddleware.record_result(
                    db=db,
                    override=ab_override,
                    success=True,
                    latency_ms=latency_ms,
                    cost=cost,
                )
                logger.info(f"[A/B Testing] Recorded simulated success: latency={latency_ms:.0f}ms, cost=${cost:.4f}")
                # Include A/B testing metadata in response for frontend feedback
                response["ab_testing"] = {
                    "assignment_id": ab_override.assignment_id,
                    "experiment_id": ab_override.experiment_id,
                    "variant_name": ab_override.variant_name,
                }
            except Exception as ab_err:
                logger.warning(f"[A/B Testing] record_result failed (non-fatal): {ab_err}")

        return response

    async def _execute_transform_node(
        self,
        node: WorkflowNode,
        inputs: Dict[str, Any]
    ) -> Any:
        """Execute data transformation node"""
        config = node.data
        code = config.get("code", "")

        # Execute transformation code
        # In production, use safe execution environment (sandbox)
        logger.info(f"Transform node: code_length={len(code)}")

        # Simulated transformation
        result = {
            "transformed": True,
            "inputs": inputs,
            "code_length": len(code)
        }

        return result

    async def _execute_if_node(
        self,
        node: WorkflowNode,
        inputs: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Execute conditional if/else node"""
        config = node.data
        condition = config.get("condition", "")

        # Evaluate condition
        # In production, use safe expression evaluator
        logger.info(f"If node: condition={condition}")

        # Simulated condition evaluation
        result = True  # Placeholder

        return {
            "condition_met": result,
            "branch": "true" if result else "false"
        }

    async def _execute_http_node(
        self,
        node: WorkflowNode,
        inputs: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Execute HTTP request node"""
        config = node.data
        url = config.get("url", "")
        method = config.get("method", "GET")

        logger.info(f"HTTP node: {method} {url}")

        # Simulated HTTP call
        result = {
            "status": 200,
            "body": {"simulated": True},
            "headers": {}
        }

        return result

    async def _execute_integration_node(
        self,
        node: WorkflowNode,
        inputs: Dict[str, Any],
        workflow: Workflow,
        db: AsyncSession
    ) -> Dict[str, Any]:
        """
        Execute integration node (Discord, Gmail, Slack, GitHub, etc.)

        This method:
        1. Extracts integration config from node data
        2. Finds the user's installation for this integration type
        3. Executes the action via IntegrationExecutor
        4. Returns the result
        """
        # Get integration configuration from node
        config = node.data
        integration_config = config.get("integrationConfig", {})
        integration_type = integration_config.get("integrationType", "custom")
        action_name = integration_config.get("action", "")
        parameters = integration_config.get("parameters", {})

        # Interpolate template variables in parameters using upstream node outputs
        # This allows: {"content": "Ticket #{{trigger.ticket_id}} - {{classify.priority}}"}
        logger.info(f"DEBUG: inputs keys = {list(inputs.keys())}")
        logger.info(f"DEBUG: inputs['input'] = {inputs.get('input', 'NOT FOUND')}")
        # Log all worker/llm node outputs for debugging variable substitution
        for key in inputs.keys():
            if 'worker' in key.lower() or 'llm' in key.lower():
                logger.info(f"DEBUG: inputs['{key}'] = {inputs.get(key, 'NOT FOUND')}")
        interpolated_params = self._interpolate_parameters(parameters, inputs)

        logger.info(f"Executing integration: {integration_type}.{action_name}")
        logger.info(f"  Original params: {parameters}")
        logger.info(f"  Interpolated params: {interpolated_params}")

        if not action_name:
            return {
                "success": False,
                "error": "No action specified for integration node",
                "integration": integration_type
            }

        try:
            # Find the installation for this integration type
            # Join with integrations table to lookup by slug (e.g., 'discord', 'gmail')
            # since integration_id is a UUID, not a string slug
            query = select(IntegrationInstallationModel).join(
                IntegrationModel,
                IntegrationInstallationModel.integration_id == IntegrationModel.integration_id
            ).where(
                and_(
                    IntegrationModel.slug == integration_type,  # Match by slug (e.g., 'discord')
                    IntegrationInstallationModel.status == "active"
                )
            )

            # If we have org context, filter by it
            if workflow.organization_id:
                query = query.where(
                    IntegrationInstallationModel.organization_id == workflow.organization_id
                )

            result = await db.execute(query)
            installation = result.scalar_one_or_none()

            if not installation:
                logger.warning(f"No active installation found for integration: {integration_type}")
                return {
                    "success": False,
                    "error": f"Integration '{integration_type}' is not installed or configured. Please go to Integrations page and set it up.",
                    "integration": integration_type,
                    "action": action_name
                }

            # Execute via IntegrationExecutor with interpolated parameters
            executor = IntegrationExecutor(db)
            exec_result = await executor.execute(
                installation_id=installation.installation_id,
                action_name=action_name,
                parameters=interpolated_params
            )

            if exec_result.success:
                logger.info(f"Integration {integration_type}.{action_name} executed successfully")
                return {
                    "success": True,
                    "integration": integration_type,
                    "action": action_name,
                    "data": exec_result.data,
                    "duration_ms": exec_result.duration_ms
                }
            else:
                logger.error(f"Integration {integration_type}.{action_name} failed: {exec_result.error_message}")
                return {
                    "success": False,
                    "error": exec_result.error_message,
                    "error_code": exec_result.error_code,
                    "integration": integration_type,
                    "action": action_name
                }

        except Exception as e:
            logger.exception(f"Error executing integration {integration_type}.{action_name}: {e}")
            return {
                "success": False,
                "error": str(e),
                "integration": integration_type,
                "action": action_name
            }

    async def _execute_openai_node(
        self,
        node: WorkflowNode,
        inputs: Dict[str, Any],
        workflow: Workflow,
        execution: WorkflowExecution,
        db: AsyncSession
    ) -> Dict[str, Any]:
        """Execute OpenAI API call"""
        config = node.data
        model = config.get("model", "gpt-4")
        prompt = self._format_prompt(config.get("prompt", ""), inputs)

        # Simulated OpenAI call
        response = {
            "text": f"OpenAI response (model={model})",
            "model": model,
            "tokens": {"input": 100, "output": 50, "total": 150}
        }

        # Track cost
        cost = self._calculate_llm_cost(model, response["tokens"])
        response["cost"] = cost  # Add cost to response for step tracking

        await self._track_node_cost(
            workflow.organization_id,
            workflow.workflow_id,
            node.id,
            cost,
            response["tokens"],
            model,
            db
        )

        return response

    async def _execute_anthropic_node(
        self,
        node: WorkflowNode,
        inputs: Dict[str, Any],
        workflow: Workflow,
        execution: WorkflowExecution,
        db: AsyncSession
    ) -> Dict[str, Any]:
        """Execute Anthropic API call"""
        config = node.data
        model = config.get("model", "claude-3-sonnet")
        prompt = self._format_prompt(config.get("prompt", ""), inputs)

        # Simulated Anthropic call
        response = {
            "text": f"Anthropic response (model={model})",
            "model": model,
            "tokens": {"input": 100, "output": 50, "total": 150}
        }

        # Track cost
        cost = self._calculate_llm_cost(model, response["tokens"])
        response["cost"] = cost  # Add cost to response for step tracking

        await self._track_node_cost(
            workflow.organization_id,
            workflow.workflow_id,
            node.id,
            cost,
            response["tokens"],
            model,
            db
        )

        return response

    async def _execute_deepseek_node(
        self,
        node: WorkflowNode,
        inputs: Dict[str, Any],
        workflow: Workflow,
        execution: WorkflowExecution,
        db: AsyncSession
    ) -> Dict[str, Any]:
        """Execute a DeepSeek LLM node"""
        config = node.data
        model = config.get("model", "deepseek-chat")
        prompt = self._format_prompt(config.get("prompt", ""), inputs)

        # Simulated DeepSeek call
        response = {
            "text": f"DeepSeek response (model={model})",
            "model": model,
            "tokens": {"input": 100, "output": 50, "total": 150}
        }

        # Track cost
        cost = self._calculate_llm_cost(model, response["tokens"])
        response["cost"] = cost  # Add cost to response for step tracking

        await self._track_node_cost(
            workflow.organization_id,
            workflow.workflow_id,
            node.id,
            cost,
            response["tokens"],
            model,
            db
        )

        return response

    async def _execute_google_node(
        self,
        node: WorkflowNode,
        inputs: Dict[str, Any],
        workflow: Workflow,
        execution: WorkflowExecution,
        db: AsyncSession
    ) -> Dict[str, Any]:
        """Execute a Google LLM node (Gemini)"""
        config = node.data
        model = config.get("model", "gemini-pro")
        prompt = self._format_prompt(config.get("prompt", ""), inputs)

        # Simulated Google call
        response = {
            "text": f"Gemini response (model={model})",
            "model": model,
            "tokens": {"input": 100, "output": 50, "total": 150}
        }

        # Track cost
        cost = self._calculate_llm_cost(model, response["tokens"])
        response["cost"] = cost  # Add cost to response for step tracking

        await self._track_node_cost(
            workflow.organization_id,
            workflow.workflow_id,
            node.id,
            cost,
            response["tokens"],
            model,
            db
        )

        return response

    async def _execute_switch_node(
        self,
        node: WorkflowNode,
        inputs: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Execute switch/case conditional node"""
        config = node.data
        switch_key = config.get("switch_key", "value")

        # Get the value to switch on
        switch_value = inputs.get(switch_key, "default")

        logger.info(f"Switch node: key={switch_key}, value={switch_value}")

        return {
            "switch_value": switch_value,
            "branch_taken": str(switch_value)
        }

    async def _execute_loop_node(
        self,
        node: WorkflowNode,
        inputs: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Execute loop/iteration node"""
        config = node.data
        max_iterations = config.get("max_iterations", 10)

        logger.info(f"Loop node: max_iterations={max_iterations}")

        # Simulated loop execution
        return {
            "iterations_completed": max_iterations,
            "results": [{"iteration": i, "status": "completed"} for i in range(max_iterations)]
        }

    async def _execute_parallel_node(
        self,
        node: WorkflowNode,
        inputs: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Execute parallel execution node"""
        logger.info(f"Parallel node: processing {len(inputs)} parallel branches")

        # Simulated parallel execution - in production, use asyncio.gather
        return {
            "parallel_results": list(inputs.values()),
            "branches_completed": len(inputs)
        }

    async def _execute_wait_node(
        self,
        node: WorkflowNode,
        inputs: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Execute wait/delay node"""
        config = node.data
        wait_seconds = config.get("wait_seconds", 1)

        logger.info(f"Wait node: waiting {wait_seconds} seconds")

        # In production, actually wait: await asyncio.sleep(wait_seconds)
        # For now, just simulate
        return {
            "waited_seconds": wait_seconds,
            "completed": True
        }

    async def _execute_function_node(
        self,
        node: WorkflowNode,
        inputs: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Execute function calling node"""
        config = node.data
        function_name = config.get("function_name", "unknown")

        logger.info(f"Function node: calling {function_name}")

        # Simulated function call
        return {
            "function": function_name,
            "result": f"Simulated result from {function_name}",
            "success": True
        }

    async def _execute_tool_node(
        self,
        node: WorkflowNode,
        inputs: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Execute tool execution node"""
        config = node.data
        tool_name = config.get("tool_name", "unknown")

        logger.info(f"Tool node: executing {tool_name}")

        # Simulated tool execution
        return {
            "tool": tool_name,
            "output": f"Simulated output from {tool_name}",
            "success": True
        }

    async def _execute_hitl_node(
        self,
        node: WorkflowNode,
        inputs: Dict[str, Any],
        workflow: Workflow,
        execution: WorkflowExecution,
        db: AsyncSession
    ) -> Dict[str, Any]:
        """
        Execute Human-in-the-Loop (HITL) approval node.

        Creates an approval request and waits for human decision.
        The workflow pauses until approved/rejected or timeout.
        """
        from backend.shared.hitl_models import (
            ApprovalRequestCreate,
            ApprovalPriority,
            NotificationChannel,
            ApprovalStatus,
            ApprovalRequest,
        )
        from backend.shared.hitl_service import HITLService

        config = node.data
        hitl_config = config.get("hitlConfig", {})

        # Extract configuration
        title = hitl_config.get("title", f"Approval required: {node.label or node.id}")
        description = hitl_config.get("description", "Workflow execution paused for human approval.")
        approvers = hitl_config.get("approvers", [])
        approval_type = hitl_config.get("approvalType", "any")
        priority_str = hitl_config.get("priority", "medium")
        timeout_minutes = hitl_config.get("timeout", 60)
        timeout_action = hitl_config.get("timeoutAction", "reject")
        context = hitl_config.get("context", {})

        if not approvers:
            raise ValueError(f"HITL node {node.id} has no approvers configured")

        # Map priority string to enum
        priority_map = {
            'low': ApprovalPriority.LOW,
            'medium': ApprovalPriority.MEDIUM,
            'high': ApprovalPriority.HIGH,
            'critical': ApprovalPriority.CRITICAL,
        }
        priority = priority_map.get(priority_str.lower(), ApprovalPriority.MEDIUM)

        logger.info(f"HITL node {node.id}: creating approval request")
        logger.info(f"  Title: {title}")
        logger.info(f"  Approvers: {approvers}")
        logger.info(f"  Priority: {priority_str}")

        # Create approval request
        approval_data = ApprovalRequestCreate(
            workflow_execution_id=0,  # Will be updated with real execution ID
            node_id=node.id,
            title=title,
            description=description,
            context=context,
            required_approvers=approvers,
            approval_type=approval_type,
            priority=priority,
            timeout_minutes=timeout_minutes,
            notification_channels=[NotificationChannel.EMAIL],
        )

        approval = await HITLService.create_approval_request(
            db, approval_data, user_id='workflow_executor', organization_id=workflow.organization_id
        )
        approval_id = approval.id

        logger.info(f"HITL approval request created: ID {approval_id}")

        # Poll for approval decision (with timeout)
        import time
        start_time = time.time()
        max_wait = timeout_minutes * 60
        poll_interval = 5  # seconds
        waited = 0
        approval_decision = 'pending'
        approved = False

        while waited < max_wait:
            await asyncio.sleep(poll_interval)
            waited += poll_interval

            # Check approval status
            stmt = select(ApprovalRequest).where(ApprovalRequest.id == approval_id)
            result = await db.execute(stmt)
            current_approval = result.scalar_one_or_none()

            if current_approval and current_approval.status != ApprovalStatus.PENDING:
                approval_decision = current_approval.status.value
                approved = (current_approval.status == ApprovalStatus.APPROVED)
                break

            # Log waiting status periodically
            if waited % 30 == 0:
                logger.info(f"HITL node {node.id} waiting for approval... ({waited}s elapsed)")

        # Handle timeout
        if approval_decision == 'pending':
            logger.warning(f"HITL node {node.id} timed out after {timeout_minutes} minutes")
            approval_decision = f'timeout_{timeout_action}'
            approved = (timeout_action == 'approve')

        latency_ms = (time.time() - start_time) * 1000

        logger.info(f"HITL node {node.id} {approval_decision} ({latency_ms:.0f}ms)")

        if not approved:
            raise RuntimeError(f"HITL approval rejected for node {node.id}")

        return {
            "approval_id": approval_id,
            "decision": approval_decision,
            "approved": approved,
            "latency_ms": latency_ms,
            "inputs": inputs
        }

    def _format_prompt(self, template: str, inputs: Dict[str, Any]) -> str:
        """Format prompt template with input values"""
        return self._interpolate_template(template, inputs)

    def _interpolate_template(self, template: str, inputs: Dict[str, Any]) -> str:
        """
        Interpolate template variables in a string.

        Supports:
        - Simple: {{node_id}} -> value from inputs["node_id"]
        - Nested: {{node_id.field}} -> inputs["node_id"]["field"]
        - Deep: {{node_id.data.ticket.id}} -> inputs["node_id"]["data"]["ticket"]["id"]

        Example:
            template = "Ticket #{{trigger.ticket_id}} - Priority: {{classify.priority}}"
            inputs = {
                "trigger": {"ticket_id": "123", "title": "Bug"},
                "classify": {"priority": "high"}
            }
            result = "Ticket #123 - Priority: high"
        """
        import re

        def get_nested_value(data: Dict[str, Any], path: str) -> Any:
            """Get value from nested dict using dot notation."""
            keys = path.split('.')
            value = data
            for key in keys:
                if isinstance(value, dict) and key in value:
                    value = value[key]
                else:
                    return None  # Path not found
            return value

        # Find all {{variable.path}} patterns
        pattern = r'\{\{([^}]+)\}\}'

        def replace_match(match):
            path = match.group(1).strip()
            value = get_nested_value(inputs, path)
            if value is not None:
                return str(value)
            # Keep original if not found (helps debugging)
            return match.group(0)

        return re.sub(pattern, replace_match, template)

    def _interpolate_parameters(self, parameters: Dict[str, Any], inputs: Dict[str, Any]) -> Dict[str, Any]:
        """
        Recursively interpolate template variables in parameters dict.

        Handles nested dicts and lists.
        """
        result = {}
        for key, value in parameters.items():
            if isinstance(value, str):
                result[key] = self._interpolate_template(value, inputs)
            elif isinstance(value, dict):
                result[key] = self._interpolate_parameters(value, inputs)
            elif isinstance(value, list):
                result[key] = [
                    self._interpolate_template(item, inputs) if isinstance(item, str)
                    else self._interpolate_parameters(item, inputs) if isinstance(item, dict)
                    else item
                    for item in value
                ]
            else:
                result[key] = value
        return result

    def _calculate_llm_cost(self, model: str, tokens: Dict[str, int]) -> float:
        """Calculate LLM API cost"""
        # Simplified cost calculation
        # In production, use actual pricing
        costs_per_1k_tokens = {
            "gpt-4": 0.03,
            "gpt-3.5-turbo": 0.002,
            "claude-3-sonnet": 0.015,
            "claude-3-haiku": 0.0025
        }

        rate = costs_per_1k_tokens.get(model, 0.01)
        total_tokens = tokens.get("total", 0)
        return (total_tokens / 1000) * rate

    async def _track_node_cost(
        self,
        organization_id: str,
        workflow_id: UUID,
        node_id: str,
        cost: float,
        tokens: Dict[str, int],
        model: str,
        db: AsyncSession
    ):
        """Track cost for a node execution"""
        # Skip cost tracking if no organization_id (e.g., test workflows)
        if not organization_id:
            logger.debug(f"Skipping cost tracking for node {node_id} - no organization_id")
            return

        cost_service = get_cost_service()

        event = CostEvent(
            timestamp=datetime.utcnow(),
            organization_id=organization_id,
            category=CostCategory.LLM_INFERENCE,
            amount=cost,
            currency="USD",
            workflow_id=workflow_id,
            provider="openai" if "gpt" in model else "anthropic",
            model=model,
            input_tokens=tokens.get("input"),
            output_tokens=tokens.get("output"),
            metadata={"node_id": node_id}
        )

        try:
            await cost_service.track_cost(event, db)
        except Exception as cost_err:
            # Don't fail workflow execution if cost tracking fails
            # Rollback the failed transaction to prevent session corruption
            logger.warning(f"Cost tracking failed: {cost_err}")
            await db.rollback()

    def _build_dependency_graph(
        self,
        nodes: List[WorkflowNode],
        edges: List[WorkflowEdge]
    ) -> Dict[str, List[str]]:
        """Build node dependency graph from edges"""
        dependencies: Dict[str, List[str]] = {node.id: [] for node in nodes}

        for edge in edges:
            # edge.target depends on edge.source
            if edge.target in dependencies:
                dependencies[edge.target].append(edge.source)

        return dependencies

    def _topological_sort(
        self,
        nodes: List[WorkflowNode],
        dependencies: Dict[str, List[str]]
    ) -> List[str]:
        """
        Topological sort of nodes based on dependencies.

        Returns execution order.
        """
        # Kahn's algorithm
        in_degree = {node.id: len(dependencies.get(node.id, [])) for node in nodes}
        queue = [node.id for node in nodes if in_degree[node.id] == 0]
        result = []

        while queue:
            node_id = queue.pop(0)
            result.append(node_id)

            # Reduce in-degree for dependent nodes
            for other_id, deps in dependencies.items():
                if node_id in deps:
                    in_degree[other_id] -= 1
                    if in_degree[other_id] == 0:
                        queue.append(other_id)

        if len(result) != len(nodes):
            raise ValueError("Workflow has circular dependencies")

        return result

    async def _load_workflow(
        self,
        workflow_id: UUID,
        db: AsyncSession
    ) -> Optional[Workflow]:
        """Load workflow from database"""
        stmt = select(WorkflowModel).where(WorkflowModel.workflow_id == workflow_id)
        result = await db.execute(stmt)
        model = result.scalar_one_or_none()

        if not model:
            return None

        # Convert to Workflow dataclass
        nodes = [
            WorkflowNode(
                id=n["id"],
                type=NodeType(n["type"]),
                position=n["position"],
                data=n.get("data", {}),
                label=n.get("label")
            )
            for n in model.nodes
        ]

        edges = [
            WorkflowEdge(
                id=e["id"],
                source=e["source"],
                target=e["target"],
                source_handle=e.get("sourceHandle"),
                target_handle=e.get("targetHandle")
            )
            for e in model.edges
        ]

        return Workflow(
            workflow_id=model.workflow_id,
            organization_id=model.organization_id,
            name=model.name,
            description=model.description,
            status=WorkflowStatus(model.status),
            version=model.version,
            nodes=nodes,
            edges=edges,
            max_execution_time_seconds=model.max_execution_time_seconds,
            retry_on_failure=model.retry_on_failure,
            max_retries=model.max_retries,
            variables=model.variables,
            environment=model.environment
        )

    async def _update_execution_retry_count(
        self,
        execution: WorkflowExecution,
        db: AsyncSession
    ):
        """
        Update only the retry count in database.

        Called before retrying to persist the incremented retry_count,
        ensuring the count survives even if the retry also fails.
        """
        try:
            stmt = (
                update(WorkflowExecutionModel)
                .where(WorkflowExecutionModel.execution_id == execution.execution_id)
                .values(retry_count=execution.retry_count)
            )
            await db.execute(stmt)
            await db.commit()
            logger.debug(f"Persisted retry_count={execution.retry_count} for {execution.execution_id}")
        except Exception as e:
            logger.error(f"Failed to update retry count: {e}")
            await db.rollback()
            raise

    async def _update_execution_status(
        self,
        execution: WorkflowExecution,
        db: AsyncSession
    ):
        """
        Update execution status in database using raw SQL UPDATE.

        CRITICAL FIX: Only update essential fields to avoid JSON serialization issues.
        JSON fields (output_data, node_states) are only updated at workflow completion.
        """
        try:
            # Minimal update - just status and timing
            # Skip JSON fields during intermediate updates to avoid recursion
            stmt = (
                update(WorkflowExecutionModel)
                .where(WorkflowExecutionModel.execution_id == execution.execution_id)
                .values(
                    status=execution.status.value,
                    started_at=execution.started_at,
                    completed_at=execution.completed_at,
                    duration_seconds=execution.duration_seconds,
                    error_message=execution.error_message,
                    error_node_id=execution.error_node_id,
                    retry_count=execution.retry_count,
                    total_cost=execution.total_cost
                )
            )

            await db.execute(stmt)
            await db.commit()
        except RecursionError as re:
            logger.error(f"Recursion error in _update_execution_status: {re}")
            await db.rollback()
            raise
        except Exception as e:
            logger.error(f"Failed to update execution status: {e}")
            await db.rollback()
            raise

    async def _update_execution_final(
        self,
        execution: WorkflowExecution,
        db: AsyncSession
    ):
        """
        Final update with JSON data - only called once at workflow completion.
        Includes execution steps for Time-Travel Debugger.
        """
        try:
            # Serialize JSON data safely
            safe_output = execution.output_data if execution.output_data else {}
            safe_states = execution.node_states if execution.node_states else {}

            stmt = (
                update(WorkflowExecutionModel)
                .where(WorkflowExecutionModel.execution_id == execution.execution_id)
                .values(
                    status=execution.status.value,
                    started_at=execution.started_at,
                    completed_at=execution.completed_at,
                    duration_seconds=execution.duration_seconds,
                    output_data=safe_output,
                    node_states=safe_states,
                    node_executions=self.execution_steps,  # NEW: Save execution steps
                    error_message=execution.error_message,
                    error_node_id=execution.error_node_id,
                    retry_count=execution.retry_count,
                    total_cost=execution.total_cost
                )
            )

            await db.execute(stmt)
            await db.commit()
        except Exception as e:
            logger.error(f"Failed to update execution final: {e}")
            # Fall back to status-only update
            await self._update_execution_status(execution, db)

    async def _update_workflow_analytics(
        self,
        workflow_id: UUID,
        execution: WorkflowExecution,
        db: AsyncSession
    ):
        """Update workflow analytics after execution"""
        stmt = select(WorkflowModel).where(WorkflowModel.workflow_id == workflow_id)
        result = await db.execute(stmt)
        model = result.scalar_one_or_none()

        if model:
            model.total_executions += 1

            if execution.status == ExecutionStatus.COMPLETED:
                model.successful_executions += 1
            elif execution.status == ExecutionStatus.FAILED:
                model.failed_executions += 1

            # Update average execution time
            if execution.duration_seconds:
                if model.avg_execution_time_seconds:
                    model.avg_execution_time_seconds = (
                        model.avg_execution_time_seconds * (model.total_executions - 1) +
                        execution.duration_seconds
                    ) / model.total_executions
                else:
                    model.avg_execution_time_seconds = execution.duration_seconds

            # Update total cost
            model.total_cost += execution.total_cost

            await db.commit()


# Global workflow service instance
_workflow_service: Optional[WorkflowExecutionEngine] = None


def get_workflow_service() -> WorkflowExecutionEngine:
    """Get the global workflow service instance"""
    global _workflow_service
    if _workflow_service is None:
        _workflow_service = WorkflowExecutionEngine()
    return _workflow_service
