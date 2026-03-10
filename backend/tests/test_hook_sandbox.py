"""
Unit Tests for Hook Execution Sandbox

Tests sandboxed hook execution including:
- Timeout enforcement
- Memory limits (soft limits)
- Fail-open/fail-fast behavior
- Sandbox configuration
- Resource usage tracking
"""

import pytest
import asyncio
import time
from backend.shared.hook_sandbox import (
    SandboxedHookExecutor,
    SandboxConfig,
    SandboxResult,
    SandboxMode,
    STRICT_SANDBOX,
    PERMISSIVE_SANDBOX,
    PRODUCTION_SANDBOX
)
from backend.shared.hook_manager import HookContext


class TestSandboxConfig:
    """Test sandbox configuration."""

    def test_default_config(self):
        """Test default sandbox configuration."""
        config = SandboxConfig()
        assert config.timeout_seconds == 5.0
        assert config.max_memory_mb == 128
        assert config.fail_open is True
        assert config.mode == SandboxMode.IN_PROCESS

    def test_strict_config(self):
        """Test strict sandbox profile."""
        assert STRICT_SANDBOX.timeout_seconds == 2.0
        assert STRICT_SANDBOX.max_memory_mb == 64
        assert STRICT_SANDBOX.fail_open is False

    def test_permissive_config(self):
        """Test permissive sandbox profile."""
        assert PERMISSIVE_SANDBOX.timeout_seconds == 10.0
        assert PERMISSIVE_SANDBOX.max_memory_mb == 256
        assert PERMISSIVE_SANDBOX.fail_open is True

    def test_production_config(self):
        """Test production sandbox profile."""
        assert PRODUCTION_SANDBOX.timeout_seconds == 5.0
        assert PRODUCTION_SANDBOX.max_memory_mb == 128
        assert PRODUCTION_SANDBOX.fail_open is True


class TestSandboxExecution:
    """Test sandboxed hook execution."""

    @pytest.mark.asyncio
    async def test_successful_execution(self):
        """Test successful hook execution in sandbox."""
        executor = SandboxedHookExecutor()

        async def simple_hook(data, context):
            from backend.shared.hook_manager import HookExecutionResult, HookType, HookResult
            return HookExecutionResult(
                hook_name="test",
                hook_type=HookType.PRE_LLM_CALL,
                result=HookResult.CONTINUE
            )

        result = await executor.execute(
            simple_hook,
            {},
            HookContext(),
            "simple_hook"
        )

        assert result.success is True
        assert result.error is None
        assert result.execution_time_ms > 0
        assert result.timeout_exceeded is False

    @pytest.mark.asyncio
    async def test_timeout_enforcement(self):
        """Test timeout enforcement in sandbox."""
        config = SandboxConfig(timeout_seconds=0.5, fail_open=True)
        executor = SandboxedHookExecutor(config)

        async def slow_hook(data, context):
            await asyncio.sleep(2.0)  # Exceeds 0.5s timeout
            from backend.shared.hook_manager import HookExecutionResult, HookType, HookResult
            return HookExecutionResult(
                hook_name="test",
                hook_type=HookType.PRE_LLM_CALL,
                result=HookResult.CONTINUE
            )

        result = await executor.execute(
            slow_hook,
            {},
            HookContext(),
            "slow_hook"
        )

        # With fail_open=True, should fail but not raise exception
        assert result.success is False
        assert result.timeout_exceeded is True
        assert "timeout" in result.error.lower()

    @pytest.mark.asyncio
    async def test_fail_open_on_timeout(self):
        """Test fail-open behavior on timeout."""
        config = SandboxConfig(timeout_seconds=0.1, fail_open=True)
        executor = SandboxedHookExecutor(config)

        async def timeout_hook(data, context):
            await asyncio.sleep(1.0)

        result = await executor.execute(
            timeout_hook,
            {},
            HookContext(),
            "timeout_hook"
        )

        # Fail-open: execution fails but doesn't raise exception
        assert result.success is False
        assert result.timeout_exceeded is True

    @pytest.mark.asyncio
    async def test_fail_fast_on_error(self):
        """Test fail-fast behavior on error."""
        config = SandboxConfig(fail_open=False)
        executor = SandboxedHookExecutor(config)

        async def failing_hook(data, context):
            raise ValueError("Test error")

        result = await executor.execute(
            failing_hook,
            {},
            HookContext(),
            "failing_hook"
        )

        # Fail-fast: execution should fail
        assert result.success is False
        assert "Test error" in result.error

    @pytest.mark.asyncio
    async def test_execution_time_tracking(self):
        """Test execution time is tracked."""
        executor = SandboxedHookExecutor()

        async def timed_hook(data, context):
            await asyncio.sleep(0.1)
            from backend.shared.hook_manager import HookExecutionResult, HookType, HookResult
            return HookExecutionResult(
                hook_name="test",
                hook_type=HookType.PRE_LLM_CALL,
                result=HookResult.CONTINUE
            )

        result = await executor.execute(
            timed_hook,
            {},
            HookContext(),
            "timed_hook"
        )

        assert result.success is True
        # Should take at least 100ms
        assert result.execution_time_ms >= 100

    @pytest.mark.asyncio
    async def test_data_passing(self):
        """Test data is passed correctly to hook."""
        executor = SandboxedHookExecutor()
        test_data = {"key": "value"}

        async def data_hook(data, context):
            from backend.shared.hook_manager import HookExecutionResult, HookType, HookResult
            # Verify data was passed
            assert data["key"] == "value"
            # Modify data
            data["modified"] = True
            return HookExecutionResult(
                hook_name="test",
                hook_type=HookType.PRE_LLM_CALL,
                result=HookResult.MODIFY,
                modified_data=data
            )

        result = await executor.execute(
            data_hook,
            test_data,
            HookContext(),
            "data_hook"
        )

        assert result.success is True
        assert result.result.modified_data["modified"] is True

    @pytest.mark.asyncio
    async def test_context_passing(self):
        """Test context is passed correctly to hook."""
        executor = SandboxedHookExecutor()
        test_context = HookContext(
            workflow_id="wf_123",
            model="gpt-4"
        )

        async def context_hook(data, context):
            from backend.shared.hook_manager import HookExecutionResult, HookType, HookResult
            # Verify context was passed
            assert context.workflow_id == "wf_123"
            assert context.model == "gpt-4"
            return HookExecutionResult(
                hook_name="test",
                hook_type=HookType.PRE_LLM_CALL,
                result=HookResult.CONTINUE
            )

        result = await executor.execute(
            context_hook,
            {},
            test_context,
            "context_hook"
        )

        assert result.success is True


class TestMemoryLimits:
    """Test memory limit enforcement."""

    @pytest.mark.asyncio
    async def test_memory_limit_configuration(self):
        """Test memory limit can be configured."""
        config = SandboxConfig(max_memory_mb=64)
        executor = SandboxedHookExecutor(config)

        # Just verify executor was created with config
        assert executor.config.max_memory_mb == 64

    @pytest.mark.asyncio
    async def test_memory_usage_tracking(self):
        """Test memory usage is tracked (if psutil available)."""
        executor = SandboxedHookExecutor()

        async def simple_hook(data, context):
            from backend.shared.hook_manager import HookExecutionResult, HookType, HookResult
            return HookExecutionResult(
                hook_name="test",
                hook_type=HookType.PRE_LLM_CALL,
                result=HookResult.CONTINUE
            )

        result = await executor.execute(
            simple_hook,
            {},
            HookContext(),
            "simple_hook"
        )

        # Memory tracking may not work without psutil
        # Just verify field exists
        assert hasattr(result, 'memory_used_mb')
        assert result.memory_used_mb >= 0


class TestErrorHandling:
    """Test error handling in sandbox."""

    @pytest.mark.asyncio
    async def test_exception_handling(self):
        """Test exceptions are caught and reported."""
        executor = SandboxedHookExecutor()

        async def error_hook(data, context):
            raise RuntimeError("Intentional error")

        result = await executor.execute(
            error_hook,
            {},
            HookContext(),
            "error_hook"
        )

        assert result.success is False
        assert "Intentional error" in result.error

    @pytest.mark.asyncio
    async def test_multiple_error_types(self):
        """Test different error types are handled."""
        executor = SandboxedHookExecutor()

        errors = [
            ValueError("Value error"),
            TypeError("Type error"),
            KeyError("Key error"),
            RuntimeError("Runtime error")
        ]

        for error in errors:
            async def error_hook(data, context):
                raise error

            result = await executor.execute(
                error_hook,
                {},
                HookContext(),
                "error_hook"
            )

            assert result.success is False
            assert str(error) in result.error


class TestSandboxIntegration:
    """Test sandbox integration with HookManager."""

    @pytest.mark.asyncio
    async def test_hookmanager_uses_sandbox(self):
        """Test HookManager uses sandbox by default."""
        from backend.shared.hook_manager import HookManager, HookType, HookResult, HookExecutionResult

        manager = HookManager(enable_sandbox=True)

        @manager.register_hook(HookType.PRE_LLM_CALL, "test_hook")
        async def test_hook(data, context):
            return HookExecutionResult(
                hook_name="test_hook",
                hook_type=HookType.PRE_LLM_CALL,
                result=HookResult.CONTINUE
            )

        # Execute hook (should use sandbox)
        results, _ = await manager.execute_hooks(
            HookType.PRE_LLM_CALL,
            {},
            HookContext()
        )

        assert len(results) == 1
        assert results[0].hook_name == "test_hook"
        assert results[0].result == HookResult.CONTINUE

    @pytest.mark.asyncio
    async def test_hookmanager_without_sandbox(self):
        """Test HookManager can disable sandbox."""
        from backend.shared.hook_manager import HookManager, HookType, HookResult, HookExecutionResult

        manager = HookManager(enable_sandbox=False)

        @manager.register_hook(HookType.PRE_LLM_CALL, "test_hook")
        async def test_hook(data, context):
            return HookExecutionResult(
                hook_name="test_hook",
                hook_type=HookType.PRE_LLM_CALL,
                result=HookResult.CONTINUE
            )

        # Execute hook (should not use sandbox)
        results, _ = await manager.execute_hooks(
            HookType.PRE_LLM_CALL,
            {},
            HookContext()
        )

        assert len(results) == 1


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
