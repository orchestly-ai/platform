"""
Hook Manager - Extensibility System for LLM and Workflow Steps

Implements ROADMAP.md Phase 2: Extensibility & Hooks (P0)

Features:
- Pre-LLM Call Hooks: Input validation, enrichment, cost guardrails
- Post-LLM Call Hooks: Output validation, PII redaction, content filtering
- Pre-Tool Call Hooks: Parameter validation, auth injection
- Post-Tool Call Hooks: Response transformation, error handling
- Workflow Step Hooks: Data transformation between nodes
- Hook chaining: Multiple hooks executed in sequence
- Error handling: Continue on error vs fail-fast modes

Architecture:
- Hooks are Python functions with standard signature
- Hooks can modify input/output or block execution
- Hooks run in isolated context (sandboxed)
- Hooks can be configured via YAML/JSON

Design Principles (from ROADMAP.md):
- "Provide hooks, not logic" - We give extension points, customers provide implementation
- "Not in the critical path" - Hook failures should not block execution (configurable)
- "Observable by default" - All hook executions are logged

Example Use Cases:
1. Cost Guardrail: Block LLM call if estimated cost > budget
2. PII Redaction: Remove SSN/credit cards from outputs
3. Input Validation: Ensure prompt meets length/format requirements
4. Output Enrichment: Add metadata or format response
5. Custom Authentication: Inject dynamic auth tokens
"""

import asyncio
import logging
import time
import traceback
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Callable, Dict, List, Optional, Union
from enum import Enum

logger = logging.getLogger(__name__)

# Import sandbox executor (lazy import to avoid circular dependencies)
_SandboxedHookExecutor = None
_SandboxConfig = None


def _get_sandbox_executor():
    """Lazy import and get sandbox executor."""
    global _SandboxedHookExecutor, _SandboxConfig
    if _SandboxedHookExecutor is None:
        from backend.shared.hook_sandbox import (
            get_sandbox_executor,
            SandboxConfig
        )
        _SandboxedHookExecutor = get_sandbox_executor
        _SandboxConfig = SandboxConfig
    return _SandboxedHookExecutor()


class HookType(Enum):
    """Types of hooks that can be registered."""
    PRE_LLM_CALL = "pre_llm_call"           # Before LLM API call
    POST_LLM_CALL = "post_llm_call"         # After LLM API call
    PRE_TOOL_CALL = "pre_tool_call"         # Before tool/API call
    POST_TOOL_CALL = "post_tool_call"       # After tool/API call
    WORKFLOW_STEP = "workflow_step"         # Between workflow nodes


class HookResult(Enum):
    """Result of hook execution."""
    CONTINUE = "continue"      # Continue execution
    BLOCK = "block"           # Block execution
    MODIFY = "modify"         # Modified input/output


class ErrorMode(Enum):
    """Error handling mode for hooks."""
    FAIL_FAST = "fail_fast"       # Stop execution on error
    CONTINUE = "continue"          # Log error and continue
    FALLBACK = "fallback"         # Use fallback value on error


@dataclass
class HookContext:
    """Context passed to hooks."""
    # Execution context
    workflow_id: Optional[str] = None
    node_id: Optional[str] = None
    agent_id: Optional[str] = None
    user_id: Optional[str] = None

    # For LLM hooks
    model: Optional[str] = None
    provider: Optional[str] = None
    estimated_cost: Optional[float] = None
    estimated_tokens: Optional[int] = None

    # For tool hooks
    tool_name: Optional[str] = None
    url: Optional[str] = None

    # Metadata
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "workflow_id": self.workflow_id,
            "node_id": self.node_id,
            "agent_id": self.agent_id,
            "user_id": self.user_id,
            "model": self.model,
            "provider": self.provider,
            "estimated_cost": self.estimated_cost,
            "estimated_tokens": self.estimated_tokens,
            "tool_name": self.tool_name,
            "url": self.url,
            "metadata": self.metadata
        }


@dataclass
class HookExecutionResult:
    """Result of hook execution."""
    hook_name: str
    hook_type: HookType
    result: HookResult
    modified_data: Optional[Any] = None
    error: Optional[str] = None
    execution_time_ms: float = 0
    blocked_reason: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "hook_name": self.hook_name,
            "hook_type": self.hook_type.value,
            "result": self.result.value,
            "modified_data": self.modified_data,
            "error": self.error,
            "execution_time_ms": self.execution_time_ms,
            "blocked_reason": self.blocked_reason,
            "metadata": self.metadata
        }


@dataclass
class Hook:
    """Hook configuration."""
    name: str
    hook_type: HookType
    function: Callable
    enabled: bool = True
    error_mode: ErrorMode = ErrorMode.CONTINUE
    priority: int = 100  # Lower number = higher priority
    description: Optional[str] = None

    def __lt__(self, other):
        """Sort by priority."""
        return self.priority < other.priority


class HookManager:
    """
    Manages hook registration and execution.

    Usage:
        manager = HookManager()

        # Register a pre-LLM hook
        @manager.register_hook(HookType.PRE_LLM_CALL, "cost_guard")
        async def check_cost(data, context):
            if context.estimated_cost > 0.10:
                return HookExecutionResult(
                    hook_name="cost_guard",
                    hook_type=HookType.PRE_LLM_CALL,
                    result=HookResult.BLOCK,
                    blocked_reason="Estimated cost exceeds budget"
                )
            return HookExecutionResult(
                hook_name="cost_guard",
                hook_type=HookType.PRE_LLM_CALL,
                result=HookResult.CONTINUE
            )

        # Execute hooks
        data = {"messages": [{"role": "user", "content": "Hello"}]}
        context = HookContext(model="gpt-4", estimated_cost=0.05)
        result, modified_data = await manager.execute_hooks(
            HookType.PRE_LLM_CALL,
            data,
            context
        )
    """

    def __init__(self, enable_sandbox: bool = True):
        """
        Initialize hook manager.

        Args:
            enable_sandbox: Enable sandboxed execution for hooks (default: True)
        """
        self._hooks: Dict[HookType, List[Hook]] = {
            hook_type: [] for hook_type in HookType
        }
        self._execution_stats: Dict[str, int] = {}
        self._enable_sandbox = enable_sandbox
        self._sandbox_executor = _get_sandbox_executor() if enable_sandbox else None

    def register_hook(
        self,
        hook_type: HookType,
        name: str,
        function: Optional[Callable] = None,
        enabled: bool = True,
        error_mode: ErrorMode = ErrorMode.CONTINUE,
        priority: int = 100,
        description: Optional[str] = None
    ) -> Callable:
        """
        Register a hook.

        Can be used as decorator or direct call:

        # As decorator
        @manager.register_hook(HookType.PRE_LLM_CALL, "my_hook")
        async def my_hook(data, context):
            ...

        # Direct call
        manager.register_hook(
            HookType.PRE_LLM_CALL,
            "my_hook",
            function=my_hook_function
        )

        Args:
            hook_type: Type of hook
            name: Hook name (unique per type)
            function: Hook function (if not using as decorator)
            enabled: Whether hook is enabled
            error_mode: Error handling mode
            priority: Execution priority (lower = earlier)
            description: Hook description

        Returns:
            Decorator function or registered function
        """
        def decorator(func: Callable) -> Callable:
            hook = Hook(
                name=name,
                hook_type=hook_type,
                function=func,
                enabled=enabled,
                error_mode=error_mode,
                priority=priority,
                description=description
            )

            # Remove existing hook with same name
            self._hooks[hook_type] = [
                h for h in self._hooks[hook_type] if h.name != name
            ]

            # Add new hook and sort by priority
            self._hooks[hook_type].append(hook)
            self._hooks[hook_type].sort()

            logger.info(
                f"Registered {hook_type.value} hook: {name} "
                f"(priority={priority}, error_mode={error_mode.value})"
            )

            return func

        if function is not None:
            return decorator(function)
        return decorator

    def unregister_hook(self, hook_type: HookType, name: str) -> bool:
        """
        Unregister a hook.

        Args:
            hook_type: Type of hook
            name: Hook name

        Returns:
            True if hook was found and removed
        """
        initial_count = len(self._hooks[hook_type])
        self._hooks[hook_type] = [
            h for h in self._hooks[hook_type] if h.name != name
        ]
        removed = len(self._hooks[hook_type]) < initial_count

        if removed:
            logger.info(f"Unregistered {hook_type.value} hook: {name}")

        return removed

    def enable_hook(self, hook_type: HookType, name: str) -> bool:
        """Enable a hook."""
        for hook in self._hooks[hook_type]:
            if hook.name == name:
                hook.enabled = True
                logger.info(f"Enabled {hook_type.value} hook: {name}")
                return True
        return False

    def disable_hook(self, hook_type: HookType, name: str) -> bool:
        """Disable a hook."""
        for hook in self._hooks[hook_type]:
            if hook.name == name:
                hook.enabled = False
                logger.info(f"Disabled {hook_type.value} hook: {name}")
                return True
        return False

    def get_hooks(self, hook_type: HookType, enabled_only: bool = True) -> List[Hook]:
        """
        Get registered hooks for a type.

        Args:
            hook_type: Type of hooks to retrieve
            enabled_only: Only return enabled hooks

        Returns:
            List of hooks sorted by priority
        """
        hooks = self._hooks[hook_type]
        if enabled_only:
            hooks = [h for h in hooks if h.enabled]
        return hooks

    async def execute_hooks(
        self,
        hook_type: HookType,
        data: Any,
        context: Optional[HookContext] = None
    ) -> tuple[List[HookExecutionResult], Any]:
        """
        Execute all hooks for a given type.

        Args:
            hook_type: Type of hooks to execute
            data: Data to pass to hooks (will be modified)
            context: Execution context

        Returns:
            Tuple of (results, modified_data)
            - results: List of hook execution results
            - modified_data: Data after all modifications

        Raises:
            RuntimeError: If hook blocks execution or fails in FAIL_FAST mode
        """
        context = context or HookContext()
        hooks = self.get_hooks(hook_type, enabled_only=True)
        results: List[HookExecutionResult] = []
        current_data = data

        logger.debug(f"Executing {len(hooks)} {hook_type.value} hooks")

        for hook in hooks:
            start_time = time.time()

            try:
                # Execute hook (sandboxed if enabled)
                if self._enable_sandbox and self._sandbox_executor:
                    # Sandboxed execution with resource limits
                    sandbox_result = await self._sandbox_executor.execute(
                        hook.function,
                        current_data,
                        context,
                        hook_name=hook.name
                    )

                    if sandbox_result.success:
                        result = sandbox_result.result
                    else:
                        # Sandbox execution failed
                        raise RuntimeError(sandbox_result.error or "Sandbox execution failed")

                    execution_time_ms = sandbox_result.execution_time_ms

                else:
                    # Direct execution without sandbox
                    if asyncio.iscoroutinefunction(hook.function):
                        result = await hook.function(current_data, context)
                    else:
                        result = hook.function(current_data, context)

                    execution_time_ms = (time.time() - start_time) * 1000

                # Ensure result is HookExecutionResult
                if not isinstance(result, HookExecutionResult):
                    result = HookExecutionResult(
                        hook_name=hook.name,
                        hook_type=hook_type,
                        result=HookResult.CONTINUE,
                        modified_data=result
                    )

                result.execution_time_ms = execution_time_ms
                results.append(result)

                # Track execution
                self._execution_stats[hook.name] = self._execution_stats.get(hook.name, 0) + 1

                logger.debug(
                    f"Hook {hook.name} executed: {result.result.value} "
                    f"({execution_time_ms:.2f}ms)"
                )

                # Handle result
                if result.result == HookResult.BLOCK:
                    logger.warning(
                        f"Hook {hook.name} blocked execution: {result.blocked_reason}"
                    )
                    # Raise outside try block to prevent catching
                    block_error = RuntimeError(
                        f"Execution blocked by hook '{hook.name}': {result.blocked_reason}"
                    )
                    raise block_error

                elif result.result == HookResult.MODIFY:
                    if result.modified_data is not None:
                        current_data = result.modified_data
                        logger.debug(f"Hook {hook.name} modified data")

            except RuntimeError as e:
                # Re-raise BLOCK errors immediately (they contain "Execution blocked by hook")
                if "Execution blocked by hook" in str(e):
                    raise
                # For other RuntimeErrors (like sandbox failures), handle based on error_mode
                error_msg = str(e)
                execution_time_ms = (time.time() - start_time) * 1000

                error_result = HookExecutionResult(
                    hook_name=hook.name,
                    hook_type=hook_type,
                    result=HookResult.CONTINUE,
                    error=error_msg,
                    execution_time_ms=execution_time_ms
                )
                results.append(error_result)

                logger.error(f"{error_msg}\n{traceback.format_exc()}")

                # Handle error based on mode
                if hook.error_mode == ErrorMode.FAIL_FAST:
                    raise RuntimeError(error_msg) from e
                elif hook.error_mode == ErrorMode.CONTINUE:
                    continue  # Just log and continue
                elif hook.error_mode == ErrorMode.FALLBACK:
                    # Use original data as fallback
                    current_data = data
                    continue

            except Exception as e:
                error_msg = f"Hook {hook.name} failed: {str(e)}"
                execution_time_ms = (time.time() - start_time) * 1000

                error_result = HookExecutionResult(
                    hook_name=hook.name,
                    hook_type=hook_type,
                    result=HookResult.CONTINUE,
                    error=error_msg,
                    execution_time_ms=execution_time_ms
                )
                results.append(error_result)

                logger.error(f"{error_msg}\n{traceback.format_exc()}")

                # Handle error based on mode
                if hook.error_mode == ErrorMode.FAIL_FAST:
                    raise RuntimeError(error_msg) from e
                elif hook.error_mode == ErrorMode.CONTINUE:
                    continue  # Just log and continue
                elif hook.error_mode == ErrorMode.FALLBACK:
                    # Use original data as fallback
                    current_data = data
                    continue

        return results, current_data

    def get_stats(self) -> Dict[str, int]:
        """Get hook execution statistics."""
        return self._execution_stats.copy()

    def reset_stats(self) -> None:
        """Reset execution statistics."""
        self._execution_stats.clear()

    def clear_hooks(self, hook_type: Optional[HookType] = None) -> None:
        """
        Clear hooks.

        Args:
            hook_type: Type to clear, or None to clear all
        """
        if hook_type:
            self._hooks[hook_type].clear()
            logger.info(f"Cleared all {hook_type.value} hooks")
        else:
            for ht in HookType:
                self._hooks[ht].clear()
            logger.info("Cleared all hooks")


# Singleton instance
_hook_manager: Optional[HookManager] = None


def get_hook_manager() -> HookManager:
    """Get or create the HookManager singleton."""
    global _hook_manager
    if _hook_manager is None:
        _hook_manager = HookManager()
    return _hook_manager


def reset_hook_manager() -> None:
    """Reset the singleton (for testing)."""
    global _hook_manager
    _hook_manager = None
