"""
Unit Tests for Hook Manager

Tests all hook functionality including:
- Hook registration and execution
- Priority ordering
- Error handling modes
- Pre/Post LLM hooks
- Pre/Post Tool hooks
- Built-in hooks
"""

import pytest
import asyncio
from backend.shared.hook_manager import (
    HookManager,
    HookType,
    HookContext,
    HookResult,
    HookExecutionResult,
    ErrorMode,
    reset_hook_manager,
    get_hook_manager
)
from backend.shared.builtin_hooks import register_builtin_hooks


class TestHookRegistration:
    """Test hook registration functionality."""

    @pytest.mark.asyncio
    async def test_register_hook_decorator(self):
        """Test registering hook using decorator pattern."""
        manager = HookManager()

        @manager.register_hook(HookType.PRE_LLM_CALL, "test_hook")
        async def my_hook(data, context):
            return HookExecutionResult(
                hook_name="test_hook",
                hook_type=HookType.PRE_LLM_CALL,
                result=HookResult.CONTINUE
            )

        hooks = manager.get_hooks(HookType.PRE_LLM_CALL)
        assert len(hooks) == 1
        assert hooks[0].name == "test_hook"

    @pytest.mark.asyncio
    async def test_register_hook_direct(self):
        """Test registering hook using direct call."""
        manager = HookManager()

        async def my_hook(data, context):
            return HookExecutionResult(
                hook_name="test_hook",
                hook_type=HookType.PRE_LLM_CALL,
                result=HookResult.CONTINUE
            )

        manager.register_hook(
            HookType.PRE_LLM_CALL,
            "test_hook",
            function=my_hook
        )

        hooks = manager.get_hooks(HookType.PRE_LLM_CALL)
        assert len(hooks) == 1
        assert hooks[0].name == "test_hook"

    @pytest.mark.asyncio
    async def test_unregister_hook(self):
        """Test unregistering a hook."""
        manager = HookManager()

        @manager.register_hook(HookType.PRE_LLM_CALL, "test_hook")
        async def my_hook(data, context):
            return HookExecutionResult(
                hook_name="test_hook",
                hook_type=HookType.PRE_LLM_CALL,
                result=HookResult.CONTINUE
            )

        assert len(manager.get_hooks(HookType.PRE_LLM_CALL)) == 1

        removed = manager.unregister_hook(HookType.PRE_LLM_CALL, "test_hook")
        assert removed is True
        assert len(manager.get_hooks(HookType.PRE_LLM_CALL)) == 0

    @pytest.mark.asyncio
    async def test_enable_disable_hook(self):
        """Test enabling and disabling hooks."""
        manager = HookManager()

        @manager.register_hook(HookType.PRE_LLM_CALL, "test_hook")
        async def my_hook(data, context):
            return HookExecutionResult(
                hook_name="test_hook",
                hook_type=HookType.PRE_LLM_CALL,
                result=HookResult.CONTINUE
            )

        # Initially enabled
        assert len(manager.get_hooks(HookType.PRE_LLM_CALL, enabled_only=True)) == 1

        # Disable
        manager.disable_hook(HookType.PRE_LLM_CALL, "test_hook")
        assert len(manager.get_hooks(HookType.PRE_LLM_CALL, enabled_only=True)) == 0
        assert len(manager.get_hooks(HookType.PRE_LLM_CALL, enabled_only=False)) == 1

        # Enable
        manager.enable_hook(HookType.PRE_LLM_CALL, "test_hook")
        assert len(manager.get_hooks(HookType.PRE_LLM_CALL, enabled_only=True)) == 1


class TestHookExecution:
    """Test hook execution functionality."""

    @pytest.mark.asyncio
    async def test_execute_simple_hook(self):
        """Test executing a simple hook."""
        manager = HookManager()

        @manager.register_hook(HookType.PRE_LLM_CALL, "test_hook")
        async def my_hook(data, context):
            return HookExecutionResult(
                hook_name="test_hook",
                hook_type=HookType.PRE_LLM_CALL,
                result=HookResult.CONTINUE
            )

        results, modified_data = await manager.execute_hooks(
            HookType.PRE_LLM_CALL,
            {"test": "data"},
            HookContext()
        )

        assert len(results) == 1
        assert results[0].hook_name == "test_hook"
        assert results[0].result == HookResult.CONTINUE
        assert results[0].execution_time_ms > 0

    @pytest.mark.asyncio
    async def test_hook_modify_data(self):
        """Test hook modifying data."""
        manager = HookManager()

        @manager.register_hook(HookType.PRE_LLM_CALL, "modifier")
        async def modifier_hook(data, context):
            data['modified'] = True
            return HookExecutionResult(
                hook_name="modifier",
                hook_type=HookType.PRE_LLM_CALL,
                result=HookResult.MODIFY,
                modified_data=data
            )

        input_data = {"original": "value"}
        results, modified_data = await manager.execute_hooks(
            HookType.PRE_LLM_CALL,
            input_data,
            HookContext()
        )

        assert modified_data['modified'] is True
        assert modified_data['original'] == "value"

    @pytest.mark.asyncio
    async def test_hook_block_execution(self):
        """Test hook blocking execution."""
        manager = HookManager()

        @manager.register_hook(HookType.PRE_LLM_CALL, "blocker")
        async def blocker_hook(data, context):
            return HookExecutionResult(
                hook_name="blocker",
                hook_type=HookType.PRE_LLM_CALL,
                result=HookResult.BLOCK,
                blocked_reason="Test block"
            )

        with pytest.raises(RuntimeError, match="Test block"):
            await manager.execute_hooks(
                HookType.PRE_LLM_CALL,
                {},
                HookContext()
            )

    @pytest.mark.asyncio
    async def test_hook_priority_ordering(self):
        """Test hooks execute in priority order."""
        manager = HookManager()
        execution_order = []

        @manager.register_hook(HookType.PRE_LLM_CALL, "hook_1", priority=100)
        async def hook_1(data, context):
            execution_order.append("hook_1")
            return HookExecutionResult(
                hook_name="hook_1",
                hook_type=HookType.PRE_LLM_CALL,
                result=HookResult.CONTINUE
            )

        @manager.register_hook(HookType.PRE_LLM_CALL, "hook_2", priority=10)
        async def hook_2(data, context):
            execution_order.append("hook_2")
            return HookExecutionResult(
                hook_name="hook_2",
                hook_type=HookType.PRE_LLM_CALL,
                result=HookResult.CONTINUE
            )

        @manager.register_hook(HookType.PRE_LLM_CALL, "hook_3", priority=50)
        async def hook_3(data, context):
            execution_order.append("hook_3")
            return HookExecutionResult(
                hook_name="hook_3",
                hook_type=HookType.PRE_LLM_CALL,
                result=HookResult.CONTINUE
            )

        await manager.execute_hooks(HookType.PRE_LLM_CALL, {}, HookContext())

        # Lower priority number = runs first
        assert execution_order == ["hook_2", "hook_3", "hook_1"]


class TestErrorHandling:
    """Test error handling modes."""

    @pytest.mark.asyncio
    async def test_error_mode_continue(self):
        """Test CONTINUE error mode (log and continue)."""
        manager = HookManager()

        @manager.register_hook(
            HookType.PRE_LLM_CALL,
            "failing_hook",
            error_mode=ErrorMode.CONTINUE
        )
        async def failing_hook(data, context):
            raise ValueError("Test error")

        # Should not raise exception
        results, _ = await manager.execute_hooks(
            HookType.PRE_LLM_CALL,
            {},
            HookContext()
        )

        assert len(results) == 1
        assert results[0].error is not None
        assert "Test error" in results[0].error

    @pytest.mark.asyncio
    async def test_error_mode_fail_fast(self):
        """Test FAIL_FAST error mode (stop execution)."""
        manager = HookManager()

        @manager.register_hook(
            HookType.PRE_LLM_CALL,
            "failing_hook",
            error_mode=ErrorMode.FAIL_FAST
        )
        async def failing_hook(data, context):
            raise ValueError("Critical error")

        with pytest.raises(RuntimeError, match="Critical error"):
            await manager.execute_hooks(
                HookType.PRE_LLM_CALL,
                {},
                HookContext()
            )

    @pytest.mark.asyncio
    async def test_error_mode_fallback(self):
        """Test FALLBACK error mode (use original data)."""
        manager = HookManager()

        @manager.register_hook(
            HookType.PRE_LLM_CALL,
            "failing_hook",
            error_mode=ErrorMode.FALLBACK
        )
        async def failing_hook(data, context):
            raise ValueError("Error")

        original_data = {"original": True}
        results, modified_data = await manager.execute_hooks(
            HookType.PRE_LLM_CALL,
            original_data,
            HookContext()
        )

        # Should return original data on error
        assert modified_data == original_data


class TestHookContext:
    """Test HookContext functionality."""

    @pytest.mark.asyncio
    async def test_hook_context_llm(self):
        """Test HookContext with LLM-specific fields."""
        context = HookContext(
            workflow_id="wf_123",
            node_id="node_456",
            model="gpt-4",
            provider="openai",
            estimated_cost=0.05,
            estimated_tokens=1000
        )

        assert context.workflow_id == "wf_123"
        assert context.node_id == "node_456"
        assert context.model == "gpt-4"
        assert context.provider == "openai"
        assert context.estimated_cost == 0.05
        assert context.estimated_tokens == 1000

    @pytest.mark.asyncio
    async def test_hook_context_tool(self):
        """Test HookContext with Tool-specific fields."""
        context = HookContext(
            workflow_id="wf_123",
            node_id="node_456",
            tool_name="api_call",
            url="https://api.example.com"
        )

        assert context.tool_name == "api_call"
        assert context.url == "https://api.example.com"

    @pytest.mark.asyncio
    async def test_hook_context_to_dict(self):
        """Test converting HookContext to dictionary."""
        context = HookContext(
            workflow_id="wf_123",
            model="gpt-4",
            metadata={"key": "value"}
        )

        context_dict = context.to_dict()
        assert context_dict["workflow_id"] == "wf_123"
        assert context_dict["model"] == "gpt-4"
        assert context_dict["metadata"]["key"] == "value"


class TestBuiltinHooks:
    """Test built-in hooks."""

    @pytest.mark.asyncio
    async def test_register_builtin_hooks(self):
        """Test registering all built-in hooks."""
        reset_hook_manager()
        manager = get_hook_manager()

        # Pass config to enable built-in hooks
        config = {
            "cost_guardrail": {"enabled": True},
            "token_limit": {"enabled": True},
            "pii_redaction": {"enabled": True},
            "url_whitelist": {"enabled": True}
        }
        register_builtin_hooks(manager, config)

        # Check that hooks were registered
        pre_llm_hooks = manager.get_hooks(HookType.PRE_LLM_CALL)
        post_llm_hooks = manager.get_hooks(HookType.POST_LLM_CALL)
        pre_tool_hooks = manager.get_hooks(HookType.PRE_TOOL_CALL)

        assert len(pre_llm_hooks) > 0
        assert len(post_llm_hooks) > 0
        assert len(pre_tool_hooks) > 0

    @pytest.mark.asyncio
    async def test_cost_guardrail_hook(self):
        """Test cost guardrail hook."""
        reset_hook_manager()
        manager = get_hook_manager()

        # Enable cost guardrail hook
        config = {"cost_guardrail": {"enabled": True}}
        register_builtin_hooks(manager, config)

        # Test within budget
        context_cheap = HookContext(
            estimated_cost=0.01,
            metadata={'max_cost': 0.10}
        )
        results, _ = await manager.execute_hooks(
            HookType.PRE_LLM_CALL,
            [],
            context_cheap
        )
        # Should not block
        assert all(r.result != HookResult.BLOCK for r in results)

        # Test over budget
        context_expensive = HookContext(
            estimated_cost=0.20,
            metadata={'max_cost': 0.10}
        )
        with pytest.raises(RuntimeError, match="cost"):
            await manager.execute_hooks(
                HookType.PRE_LLM_CALL,
                [],
                context_expensive
            )

    @pytest.mark.asyncio
    async def test_pii_redaction_hook(self):
        """Test PII redaction hook."""
        reset_hook_manager()
        manager = get_hook_manager()

        # Enable pii_redaction hook
        config = {"pii_redaction": {"enabled": True}}
        register_builtin_hooks(manager, config)

        # Create mock LLM response with PII - pii_redaction_hook expects a string
        llm_response = 'SSN: 123-45-6789, CC: 4532-1111-2222-3333, Email: user@example.com'

        results, modified = await manager.execute_hooks(
            HookType.POST_LLM_CALL,
            llm_response,
            HookContext()
        )

        # PII should be redacted
        content = modified if isinstance(modified, str) else modified.get('content', '')
        assert '123-45-6789' not in content
        assert '4532-1111-2222-3333' not in content
        assert 'user@example.com' not in content
        assert '[REDACTED]_SSN' in content or '[REDACTED]_CC' in content or '[REDACTED]_EMAIL' in content


class TestHookStats:
    """Test hook statistics tracking."""

    @pytest.mark.asyncio
    async def test_execution_stats(self):
        """Test tracking hook execution statistics."""
        manager = HookManager()

        @manager.register_hook(HookType.PRE_LLM_CALL, "test_hook")
        async def my_hook(data, context):
            return HookExecutionResult(
                hook_name="test_hook",
                hook_type=HookType.PRE_LLM_CALL,
                result=HookResult.CONTINUE
            )

        # Execute hook 3 times
        for _ in range(3):
            await manager.execute_hooks(HookType.PRE_LLM_CALL, {}, HookContext())

        stats = manager.get_stats()
        assert stats["test_hook"] == 3

    @pytest.mark.asyncio
    async def test_reset_stats(self):
        """Test resetting execution statistics."""
        manager = HookManager()

        @manager.register_hook(HookType.PRE_LLM_CALL, "test_hook")
        async def my_hook(data, context):
            return HookExecutionResult(
                hook_name="test_hook",
                hook_type=HookType.PRE_LLM_CALL,
                result=HookResult.CONTINUE
            )

        await manager.execute_hooks(HookType.PRE_LLM_CALL, {}, HookContext())
        assert manager.get_stats()["test_hook"] == 1

        manager.reset_stats()
        assert len(manager.get_stats()) == 0


class TestHookChaining:
    """Test hook chaining and data flow."""

    @pytest.mark.asyncio
    async def test_multiple_hooks_modify_data(self):
        """Test multiple hooks modifying data in sequence."""
        manager = HookManager()

        @manager.register_hook(HookType.PRE_LLM_CALL, "hook_1", priority=10)
        async def hook_1(data, context):
            data['step1'] = 'done'
            return HookExecutionResult(
                hook_name="hook_1",
                hook_type=HookType.PRE_LLM_CALL,
                result=HookResult.MODIFY,
                modified_data=data
            )

        @manager.register_hook(HookType.PRE_LLM_CALL, "hook_2", priority=20)
        async def hook_2(data, context):
            data['step2'] = 'done'
            return HookExecutionResult(
                hook_name="hook_2",
                hook_type=HookType.PRE_LLM_CALL,
                result=HookResult.MODIFY,
                modified_data=data
            )

        results, modified_data = await manager.execute_hooks(
            HookType.PRE_LLM_CALL,
            {},
            HookContext()
        )

        # Both hooks should have modified the data
        assert modified_data['step1'] == 'done'
        assert modified_data['step2'] == 'done'

    @pytest.mark.asyncio
    async def test_hook_chain_stops_on_block(self):
        """Test hook chain stops when one hook blocks."""
        manager = HookManager()
        executed = []

        @manager.register_hook(HookType.PRE_LLM_CALL, "hook_1", priority=10)
        async def hook_1(data, context):
            executed.append("hook_1")
            return HookExecutionResult(
                hook_name="hook_1",
                hook_type=HookType.PRE_LLM_CALL,
                result=HookResult.CONTINUE
            )

        @manager.register_hook(HookType.PRE_LLM_CALL, "hook_2", priority=20)
        async def hook_2(data, context):
            executed.append("hook_2")
            return HookExecutionResult(
                hook_name="hook_2",
                hook_type=HookType.PRE_LLM_CALL,
                result=HookResult.BLOCK,
                blocked_reason="Testing block"
            )

        @manager.register_hook(HookType.PRE_LLM_CALL, "hook_3", priority=30)
        async def hook_3(data, context):
            executed.append("hook_3")
            return HookExecutionResult(
                hook_name="hook_3",
                hook_type=HookType.PRE_LLM_CALL,
                result=HookResult.CONTINUE
            )

        with pytest.raises(RuntimeError):
            await manager.execute_hooks(HookType.PRE_LLM_CALL, {}, HookContext())

        # Only hooks before the blocker should execute
        assert "hook_1" in executed
        assert "hook_2" in executed
        assert "hook_3" not in executed


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
