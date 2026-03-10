"""
Hook Execution Sandbox

Provides isolated execution environment for customer-defined hooks to prevent:
- Resource exhaustion (memory, CPU)
- Infinite loops (timeout)
- Blocking critical paths (fail-open)
- Security vulnerabilities (subprocess isolation)

Design Principles (from ROADMAP.md):
1. Fail-open: Hook failures don't block workflows
2. Resource limits: 128MB memory, 0.5 CPU cores, 5s timeout
3. Isolation: Subprocess execution with restricted permissions
4. Observable: All failures logged with context

Phase 1: In-process with resource limits
Phase 2: Subprocess isolation (future)
Phase 3: WASM sandbox (future)
"""

import asyncio
import logging
import time
import traceback
from dataclasses import dataclass
from enum import Enum
from typing import Any, Callable, Dict, Optional
import resource
import signal

logger = logging.getLogger(__name__)


class SandboxMode(str, Enum):
    """Sandbox execution mode."""
    IN_PROCESS = "in_process"          # Same process, resource limits only
    SUBPROCESS = "subprocess"          # Isolated subprocess (future)
    WEBHOOK = "webhook"                # External webhook call (future)
    WASM = "wasm"                      # WebAssembly sandbox (future)


@dataclass
class SandboxConfig:
    """Sandbox resource limits and configuration."""

    # Timeout limits
    timeout_seconds: float = 5.0          # Max execution time

    # Memory limits (bytes)
    max_memory_mb: int = 128              # Max memory usage

    # CPU limits
    max_cpu_percent: float = 50.0         # Max CPU usage (not enforced in Phase 1)

    # Network limits
    allow_network: bool = False           # Allow network access (not enforced in Phase 1)
    allowed_domains: list = None          # Whitelist of allowed domains

    # Filesystem limits
    allow_filesystem: bool = False        # Allow file I/O (not enforced in Phase 1)

    # Failure behavior
    fail_open: bool = True                # Don't block on hook failure

    # Execution mode
    mode: SandboxMode = SandboxMode.IN_PROCESS


@dataclass
class SandboxResult:
    """Result of sandboxed execution."""

    success: bool                         # Execution succeeded
    result: Any = None                    # Execution result (if success)
    error: Optional[str] = None           # Error message (if failed)
    execution_time_ms: float = 0.0        # Actual execution time
    memory_used_mb: float = 0.0           # Peak memory usage
    timeout_exceeded: bool = False        # Whether timeout was exceeded
    resource_limit_exceeded: bool = False # Whether resource limit was hit


class SandboxedHookExecutor:
    """
    Executes hooks in isolated sandbox with resource limits.

    Phase 1: In-process execution with timeout and memory limits
    Phase 2: Subprocess isolation with network/filesystem restrictions
    Phase 3: WASM-based sandbox for maximum security
    """

    def __init__(self, config: Optional[SandboxConfig] = None):
        """
        Initialize sandbox executor.

        Args:
            config: Sandbox configuration (uses defaults if not provided)
        """
        self.config = config or SandboxConfig()

    async def execute(
        self,
        hook_function: Callable,
        data: Any,
        context: Any,
        hook_name: str = "unknown"
    ) -> SandboxResult:
        """
        Execute hook function in sandboxed environment.

        Args:
            hook_function: Hook function to execute
            data: Data passed to hook
            context: Context passed to hook
            hook_name: Name of hook (for logging)

        Returns:
            SandboxResult with execution outcome
        """
        if self.config.mode == SandboxMode.IN_PROCESS:
            return await self._execute_in_process(
                hook_function,
                data,
                context,
                hook_name
            )
        elif self.config.mode == SandboxMode.SUBPROCESS:
            # Future: subprocess isolation
            logger.warning(
                f"Subprocess mode not yet implemented for {hook_name}, "
                f"falling back to in-process"
            )
            return await self._execute_in_process(
                hook_function,
                data,
                context,
                hook_name
            )
        else:
            return SandboxResult(
                success=False,
                error=f"Unsupported sandbox mode: {self.config.mode}"
            )

    async def _execute_in_process(
        self,
        hook_function: Callable,
        data: Any,
        context: Any,
        hook_name: str
    ) -> SandboxResult:
        """
        Execute hook in current process with resource limits.

        Resource limits enforced:
        1. Timeout: asyncio.wait_for
        2. Memory: resource.setrlimit (soft limit) - Unix only
        3. CPU: Not enforced in Phase 1 (requires cgroups)

        Args:
            hook_function: Hook to execute (sync or async)
            data: Data for hook
            context: Context for hook
            hook_name: Hook name for logging

        Returns:
            SandboxResult with outcome
        """
        start_time = time.time()
        timeout_exceeded = False
        resource_limit_exceeded = False
        result = None
        error = None
        original_limit = None

        # Set memory limit (soft limit only to allow graceful handling)
        # Note: RLIMIT_AS may not work properly on macOS
        if self.config.max_memory_mb > 0:
            try:
                # Check if RLIMIT_AS is available (Unix-specific)
                if hasattr(resource, 'RLIMIT_AS'):
                    memory_limit_bytes = self.config.max_memory_mb * 1024 * 1024
                    # Get current limits
                    soft, hard = resource.getrlimit(resource.RLIMIT_AS)
                    original_limit = (soft, hard)

                    # Set new soft limit (don't exceed hard limit)
                    new_soft = min(memory_limit_bytes, hard) if hard > 0 else memory_limit_bytes
                    resource.setrlimit(resource.RLIMIT_AS, (new_soft, hard))

                    logger.debug(
                        f"Set memory limit for {hook_name}: {self.config.max_memory_mb}MB "
                        f"(soft={new_soft}, hard={hard})"
                    )
            except (OSError, ValueError) as e:
                # On macOS, setting RLIMIT_AS may fail - this is expected
                logger.debug(f"Memory limit not supported on this platform for {hook_name}: {e}")
                original_limit = None
            except Exception as e:
                logger.warning(f"Failed to set memory limit for {hook_name}: {e}")
                original_limit = None

        try:
            # Check if hook_function is async or sync
            if asyncio.iscoroutinefunction(hook_function):
                # Async function - wrap in wait_for for timeout
                result = await asyncio.wait_for(
                    hook_function(data, context),
                    timeout=self.config.timeout_seconds
                )
            else:
                # Sync function - run in thread executor with timeout
                loop = asyncio.get_event_loop()
                result = await asyncio.wait_for(
                    loop.run_in_executor(None, hook_function, data, context),
                    timeout=self.config.timeout_seconds
                )
            success = True

        except asyncio.TimeoutError:
            success = False
            timeout_exceeded = True
            error = f"Hook {hook_name} exceeded timeout of {self.config.timeout_seconds}s"
            logger.warning(error)

            if self.config.fail_open:
                logger.info(f"Fail-open enabled: continuing despite timeout in {hook_name}")

        except MemoryError as e:
            success = False
            resource_limit_exceeded = True
            error = f"Hook {hook_name} exceeded memory limit: {e}"
            logger.error(error)

            if self.config.fail_open:
                logger.info(f"Fail-open enabled: continuing despite memory error in {hook_name}")

        except Exception as e:
            success = False
            error = f"Hook {hook_name} failed: {str(e)}"
            logger.error(f"{error}\n{traceback.format_exc()}")

            if self.config.fail_open:
                logger.info(f"Fail-open enabled: continuing despite error in {hook_name}")

        finally:
            # Restore original memory limit
            if original_limit is not None:
                try:
                    resource.setrlimit(resource.RLIMIT_AS, original_limit)
                except Exception as e:
                    logger.debug(f"Failed to restore memory limit: {e}")

        execution_time_ms = (time.time() - start_time) * 1000

        # Estimate memory usage (rough approximation)
        try:
            import psutil
            process = psutil.Process()
            memory_used_mb = process.memory_info().rss / 1024 / 1024
        except:
            memory_used_mb = 0.0

        return SandboxResult(
            success=success,
            result=result,
            error=error,
            execution_time_ms=execution_time_ms,
            memory_used_mb=memory_used_mb,
            timeout_exceeded=timeout_exceeded,
            resource_limit_exceeded=resource_limit_exceeded
        )


# Global sandbox executor instance
_sandbox_executor: Optional[SandboxedHookExecutor] = None


def get_sandbox_executor(
    config: Optional[SandboxConfig] = None
) -> SandboxedHookExecutor:
    """
    Get global sandboxed hook executor.

    Args:
        config: Optional sandbox configuration

    Returns:
        SandboxedHookExecutor instance
    """
    global _sandbox_executor
    if _sandbox_executor is None:
        _sandbox_executor = SandboxedHookExecutor(config)
    return _sandbox_executor


def reset_sandbox_executor():
    """Reset global sandbox executor (for testing)."""
    global _sandbox_executor
    _sandbox_executor = None


# Example usage and built-in sandbox configurations

# Strict sandbox: Low limits, fail-fast
STRICT_SANDBOX = SandboxConfig(
    timeout_seconds=2.0,
    max_memory_mb=64,
    fail_open=False  # Fail-fast on errors
)

# Permissive sandbox: Higher limits, fail-open
PERMISSIVE_SANDBOX = SandboxConfig(
    timeout_seconds=10.0,
    max_memory_mb=256,
    fail_open=True  # Continue on errors
)

# Production sandbox: Balanced settings
PRODUCTION_SANDBOX = SandboxConfig(
    timeout_seconds=5.0,
    max_memory_mb=128,
    fail_open=True,  # Don't block workflows
    allow_network=False,
    allow_filesystem=False
)
