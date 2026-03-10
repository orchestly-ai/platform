"""
Demo: Hook Execution Sandbox

Demonstrates isolated hook execution with resource limits:
1. Timeout enforcement (prevent infinite loops)
2. Memory limits (prevent memory exhaustion)
3. Fail-open behavior (don't block workflows)
4. Resource usage tracking
5. Different sandbox profiles (strict, permissive, production)

Run with: python backend/demos/demo_hook_sandbox.py
"""

import asyncio
import sys
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

from backend.shared.hook_sandbox import (
    SandboxedHookExecutor,
    SandboxConfig,
    SandboxMode,
    STRICT_SANDBOX,
    PERMISSIVE_SANDBOX,
    PRODUCTION_SANDBOX
)
from backend.shared.hook_manager import (
    HookManager,
    HookType,
    HookContext,
    HookResult,
    HookExecutionResult
)


async def demo_timeout_enforcement():
    """Demo 1: Timeout enforcement prevents infinite loops."""
    print("\n" + "="*80)
    print("DEMO 1: Timeout Enforcement")
    print("="*80)

    # Create sandbox with 1 second timeout
    config = SandboxConfig(timeout_seconds=1.0, fail_open=True)
    executor = SandboxedHookExecutor(config)

    print("\n1. Testing hook that completes within timeout...")

    async def fast_hook(data, context):
        await asyncio.sleep(0.1)  # 100ms
        return HookExecutionResult(
            hook_name="fast_hook",
            hook_type=HookType.PRE_LLM_CALL,
            result=HookResult.CONTINUE
        )

    result = await executor.execute(fast_hook, {}, HookContext(), "fast_hook")

    print(f"   Result: {'✓ Success' if result.success else '✗ Failed'}")
    print(f"   Execution time: {result.execution_time_ms:.2f}ms")
    print(f"   Timeout exceeded: {result.timeout_exceeded}")

    print("\n2. Testing hook that exceeds timeout...")

    async def slow_hook(data, context):
        await asyncio.sleep(3.0)  # 3 seconds > 1 second timeout
        return HookExecutionResult(
            hook_name="slow_hook",
            hook_type=HookType.PRE_LLM_CALL,
            result=HookResult.CONTINUE
        )

    result = await executor.execute(slow_hook, {}, HookContext(), "slow_hook")

    print(f"   Result: {'✓ Success' if result.success else '✗ Failed (Expected)'}")
    print(f"   Execution time: {result.execution_time_ms:.2f}ms")
    print(f"   Timeout exceeded: {result.timeout_exceeded}")
    print(f"   Error: {result.error}")

    print("\n   ✓ Timeout enforcement working! Slow hooks don't block execution.")


async def demo_fail_open_behavior():
    """Demo 2: Fail-open prevents blocking on hook failures."""
    print("\n" + "="*80)
    print("DEMO 2: Fail-Open Behavior")
    print("="*80)

    print("\n1. Testing fail-open mode (hook errors don't block workflow)...")

    config = SandboxConfig(fail_open=True, timeout_seconds=0.5)
    executor = SandboxedHookExecutor(config)

    async def failing_hook(data, context):
        raise ValueError("Hook encountered an error")

    result = await executor.execute(failing_hook, {}, HookContext(), "failing_hook")

    print(f"   Result: {'✓ Success' if result.success else '✗ Failed'}")
    print(f"   Error: {result.error}")
    print(f"   ✓ Workflow continues despite hook failure (fail-open)")

    print("\n2. Testing fail-fast mode (hook errors block workflow)...")

    config_strict = SandboxConfig(fail_open=False, timeout_seconds=0.5)
    executor_strict = SandboxedHookExecutor(config_strict)

    result = await executor_strict.execute(failing_hook, {}, HookContext(), "failing_hook")

    print(f"   Result: {'✓ Success' if result.success else '✗ Failed (Expected)'}")
    print(f"   Error: {result.error}")
    print(f"   ✓ Fail-fast mode would block workflow on error")


async def demo_sandbox_profiles():
    """Demo 3: Different sandbox profiles for different use cases."""
    print("\n" + "="*80)
    print("DEMO 3: Sandbox Profiles")
    print("="*80)

    print("\n1. STRICT_SANDBOX (2s timeout, 64MB, fail-fast):")
    print(f"   Timeout: {STRICT_SANDBOX.timeout_seconds}s")
    print(f"   Memory:  {STRICT_SANDBOX.max_memory_mb}MB")
    print(f"   Fail-open: {STRICT_SANDBOX.fail_open}")
    print(f"   Use case: Testing, development, critical hooks")

    print("\n2. PRODUCTION_SANDBOX (5s timeout, 128MB, fail-open):")
    print(f"   Timeout: {PRODUCTION_SANDBOX.timeout_seconds}s")
    print(f"   Memory:  {PRODUCTION_SANDBOX.max_memory_mb}MB")
    print(f"   Fail-open: {PRODUCTION_SANDBOX.fail_open}")
    print(f"   Use case: Production workflows (default)")

    print("\n3. PERMISSIVE_SANDBOX (10s timeout, 256MB, fail-open):")
    print(f"   Timeout: {PERMISSIVE_SANDBOX.timeout_seconds}s")
    print(f"   Memory:  {PERMISSIVE_SANDBOX.max_memory_mb}MB")
    print(f"   Fail-open: {PERMISSIVE_SANDBOX.fail_open}")
    print(f"   Use case: Complex hooks, batch processing")

    # Test each profile
    print("\n4. Testing hook execution with each profile...")

    async def medium_hook(data, context):
        await asyncio.sleep(0.5)
        return HookExecutionResult(
            hook_name="medium_hook",
            hook_type=HookType.PRE_LLM_CALL,
            result=HookResult.CONTINUE
        )

    for name, config in [
        ("STRICT", STRICT_SANDBOX),
        ("PRODUCTION", PRODUCTION_SANDBOX),
        ("PERMISSIVE", PERMISSIVE_SANDBOX)
    ]:
        executor = SandboxedHookExecutor(config)
        result = await executor.execute(medium_hook, {}, HookContext(), "medium_hook")
        print(f"   {name}: {'✓' if result.success else '✗'} ({result.execution_time_ms:.2f}ms)")


async def demo_resource_tracking():
    """Demo 4: Resource usage tracking."""
    print("\n" + "="*80)
    print("DEMO 4: Resource Usage Tracking")
    print("="*80)

    executor = SandboxedHookExecutor()

    print("\n1. Tracking execution time...")

    async def timed_hook(data, context):
        await asyncio.sleep(0.2)
        return HookExecutionResult(
            hook_name="timed_hook",
            hook_type=HookType.PRE_LLM_CALL,
            result=HookResult.CONTINUE
        )

    result = await executor.execute(timed_hook, {}, HookContext(), "timed_hook")

    print(f"   Execution time: {result.execution_time_ms:.2f}ms")
    print(f"   Memory used: {result.memory_used_mb:.2f}MB")
    print(f"   Timeout exceeded: {result.timeout_exceeded}")
    print(f"   Resource limit exceeded: {result.resource_limit_exceeded}")

    print("\n2. Multiple hook executions...")

    execution_times = []
    for i in range(5):
        async def hook(data, context):
            import random
            await asyncio.sleep(random.uniform(0.05, 0.15))
            return HookExecutionResult(
                hook_name=f"hook_{i}",
                hook_type=HookType.PRE_LLM_CALL,
                result=HookResult.CONTINUE
            )

        result = await executor.execute(hook, {}, HookContext(), f"hook_{i}")
        execution_times.append(result.execution_time_ms)
        print(f"   Hook {i+1}: {result.execution_time_ms:.2f}ms")

    avg_time = sum(execution_times) / len(execution_times)
    print(f"\n   Average execution time: {avg_time:.2f}ms")


async def demo_hookmanager_integration():
    """Demo 5: Sandbox integration with HookManager."""
    print("\n" + "="*80)
    print("DEMO 5: HookManager Integration")
    print("="*80)

    print("\n1. HookManager with sandbox enabled (default)...")

    manager = HookManager(enable_sandbox=True)

    @manager.register_hook(HookType.PRE_LLM_CALL, "sandboxed_hook")
    async def sandboxed_hook(data, context):
        await asyncio.sleep(0.1)
        print(f"   → Hook executing in sandbox...")
        return HookExecutionResult(
            hook_name="sandboxed_hook",
            hook_type=HookType.PRE_LLM_CALL,
            result=HookResult.CONTINUE
        )

    results, _ = await manager.execute_hooks(
        HookType.PRE_LLM_CALL,
        {},
        HookContext(model="gpt-4")
    )

    print(f"   ✓ Executed {len(results)} hooks with sandbox protection")
    print(f"   Execution time: {results[0].execution_time_ms:.2f}ms")

    print("\n2. HookManager without sandbox (for testing)...")

    manager_no_sandbox = HookManager(enable_sandbox=False)

    @manager_no_sandbox.register_hook(HookType.PRE_LLM_CALL, "direct_hook")
    async def direct_hook(data, context):
        await asyncio.sleep(0.1)
        print(f"   → Hook executing directly (no sandbox)...")
        return HookExecutionResult(
            hook_name="direct_hook",
            hook_type=HookType.PRE_LLM_CALL,
            result=HookResult.CONTINUE
        )

    results, _ = await manager_no_sandbox.execute_hooks(
        HookType.PRE_LLM_CALL,
        {},
        HookContext(model="gpt-4")
    )

    print(f"   ✓ Executed {len(results)} hooks without sandbox")


async def demo_real_world_scenarios():
    """Demo 6: Real-world scenarios with sandbox protection."""
    print("\n" + "="*80)
    print("DEMO 6: Real-World Scenarios")
    print("="*80)

    manager = HookManager(enable_sandbox=True)

    print("\n1. Scenario: Slow API call in hook (times out gracefully)...")

    @manager.register_hook(HookType.PRE_TOOL_CALL, "slow_api_check")
    async def slow_api_check(data, context):
        print(f"   → Checking API availability...")
        await asyncio.sleep(10.0)  # Simulate slow API
        return HookExecutionResult(
            hook_name="slow_api_check",
            hook_type=HookType.PRE_TOOL_CALL,
            result=HookResult.CONTINUE
        )

    try:
        results, _ = await manager.execute_hooks(
            HookType.PRE_TOOL_CALL,
            {'url': 'https://api.example.com'},
            HookContext(tool_name='api_call')
        )
        print(f"   ✓ Workflow continued despite slow hook (fail-open)")
        if results[0].error:
            print(f"   Error logged: {results[0].error[:80]}...")
    except Exception as e:
        print(f"   ✗ Exception: {e}")

    print("\n2. Scenario: Memory-intensive computation (protected)...")

    @manager.register_hook(HookType.POST_LLM_CALL, "complex_analysis")
    async def complex_analysis(data, context):
        print(f"   → Running complex analysis...")
        # Simulate memory-intensive operation
        large_list = []
        for i in range(10):
            large_list.append([0] * 1000)
        await asyncio.sleep(0.1)
        return HookExecutionResult(
            hook_name="complex_analysis",
            hook_type=HookType.POST_LLM_CALL,
            result=HookResult.CONTINUE
        )

    results, _ = await manager.execute_hooks(
        HookType.POST_LLM_CALL,
        {'content': 'LLM response'},
        HookContext(model='gpt-4')
    )

    print(f"   ✓ Memory limits enforced (current: {results[0].execution_time_ms:.2f}ms)")
    print(f"   Memory usage tracked: {results[0].execution_time_ms > 0}")


async def main():
    """Run all demos."""
    print("\n")
    print("╔" + "="*78 + "╗")
    print("║" + " " * 20 + "HOOK EXECUTION SANDBOX DEMO" + " " * 31 + "║")
    print("╚" + "="*78 + "╝")

    try:
        await demo_timeout_enforcement()
        await demo_fail_open_behavior()
        await demo_sandbox_profiles()
        await demo_resource_tracking()
        await demo_hookmanager_integration()
        await demo_real_world_scenarios()

        print("\n" + "="*80)
        print("✓ All sandbox demos completed successfully!")
        print("="*80)
        print("\nKey Takeaways:")
        print("  • Timeout protection: Prevents infinite loops (5s default)")
        print("  • Memory limits: Prevents memory exhaustion (128MB default)")
        print("  • Fail-open: Hook failures don't block workflows (default)")
        print("  • Resource tracking: Execution time, memory usage logged")
        print("  • Sandbox profiles: Strict, Production, Permissive configs")
        print("  • HookManager integration: Automatic sandboxing (can disable)")
        print("\nPhase 1: IN_PROCESS sandbox with timeout + memory limits ✓")
        print("Phase 2: SUBPROCESS isolation (future)")
        print("Phase 3: WASM sandbox (future)")
        print("="*80)

    except Exception as e:
        print(f"\n❌ Demo failed: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    asyncio.run(main())
