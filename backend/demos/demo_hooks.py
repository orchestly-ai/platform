"""
Demo: Hook System for LLM and Workflow Extensibility

This demo showcases:
1. Pre-LLM hooks (cost guardrails, input validation, prompt enrichment)
2. Post-LLM hooks (PII redaction, output validation, content filtering)
3. Pre-Tool hooks (URL whitelist, auth injection)
4. Post-Tool hooks (response transformation, error handling)
5. Custom hook creation
6. Hook chaining and priority
7. Error handling modes

Run with: python backend/demos/demo_hooks.py
"""

import asyncio
import sys
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

from backend.shared.hook_manager import (
    HookManager,
    HookType,
    HookContext,
    HookResult,
    HookExecutionResult,
    ErrorMode,
    reset_hook_manager
)
from backend.shared.builtin_hooks import register_builtin_hooks


async def demo_basic_hooks():
    """Demo 1: Basic hook registration and execution."""
    print("\n" + "="*80)
    print("DEMO 1: Basic Hook Registration and Execution")
    print("="*80)

    manager = HookManager()

    # Register a simple pre-LLM hook
    @manager.register_hook(HookType.PRE_LLM_CALL, "simple_logger")
    async def log_llm_call(data, context):
        print(f"\n📝 Pre-LLM Hook: Logging call to {context.model}")
        print(f"   Messages: {len(data)} messages")
        return HookExecutionResult(
            hook_name="simple_logger",
            hook_type=HookType.PRE_LLM_CALL,
            result=HookResult.CONTINUE
        )

    # Test execution
    print("\n1. Executing pre-LLM hooks...")
    messages = [
        {"role": "system", "content": "You are a helpful assistant"},
        {"role": "user", "content": "Hello!"}
    ]
    context = HookContext(
        model="gpt-4o-mini",
        provider="openai",
        estimated_cost=0.001
    )

    results, modified_data = await manager.execute_hooks(
        HookType.PRE_LLM_CALL,
        messages,
        context
    )

    print(f"\n✓ Executed {len(results)} hooks")
    for result in results:
        print(f"  - {result.hook_name}: {result.result.value} ({result.execution_time_ms:.2f}ms)")


async def demo_cost_guardrail():
    """Demo 2: Cost guardrail hook blocking expensive calls."""
    print("\n" + "="*80)
    print("DEMO 2: Cost Guardrail - Blocking Expensive Calls")
    print("="*80)

    manager = HookManager()

    # Register cost guardrail
    @manager.register_hook(HookType.PRE_LLM_CALL, "cost_guard", priority=10)
    async def cost_guardrail(data, context):
        max_cost = 0.05
        if context.estimated_cost > max_cost:
            print(f"\n🚫 BLOCKED: Cost ${context.estimated_cost:.4f} exceeds limit ${max_cost:.4f}")
            return HookExecutionResult(
                hook_name="cost_guard",
                hook_type=HookType.PRE_LLM_CALL,
                result=HookResult.BLOCK,
                blocked_reason=f"Estimated cost ${context.estimated_cost:.4f} exceeds budget ${max_cost:.4f}"
            )
        else:
            print(f"\n✓ ALLOWED: Cost ${context.estimated_cost:.4f} within limit")
            return HookExecutionResult(
                hook_name="cost_guard",
                hook_type=HookType.PRE_LLM_CALL,
                result=HookResult.CONTINUE
            )

    # Test 1: Cheap call (should pass)
    print("\n1. Testing cheap LLM call (should pass)...")
    context_cheap = HookContext(model="gpt-4o-mini", estimated_cost=0.01)
    try:
        results, _ = await manager.execute_hooks(
            HookType.PRE_LLM_CALL,
            {"messages": []},
            context_cheap
        )
        print("✓ Call allowed")
    except RuntimeError as e:
        print(f"✗ Call blocked: {e}")

    # Test 2: Expensive call (should block)
    print("\n2. Testing expensive LLM call (should block)...")
    context_expensive = HookContext(model="gpt-4", estimated_cost=0.10)
    try:
        results, _ = await manager.execute_hooks(
            HookType.PRE_LLM_CALL,
            {"messages": []},
            context_expensive
        )
        print("✓ Call allowed")
    except RuntimeError as e:
        print(f"✗ Call blocked: {e}")


async def demo_pii_redaction():
    """Demo 3: PII redaction in LLM outputs."""
    print("\n" + "="*80)
    print("DEMO 3: PII Redaction - Removing Sensitive Data")
    print("="*80)

    manager = HookManager()

    # Register PII redaction hook
    @manager.register_hook(HookType.POST_LLM_CALL, "pii_redactor")
    async def redact_pii(data, context):
        import re

        # Simulate LLMResponse object
        content = data.get('content', '')
        original = content

        # Redact SSNs
        content = re.sub(r'\b\d{3}-\d{2}-\d{4}\b', '[SSN-REDACTED]', content)

        # Redact credit cards
        content = re.sub(r'\b\d{4}[- ]?\d{4}[- ]?\d{4}[- ]?\d{4}\b', '[CC-REDACTED]', content)

        # Redact emails
        content = re.sub(r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b', '[EMAIL-REDACTED]', content)

        if content != original:
            print(f"\n🔒 PII REDACTED:")
            print(f"   Before: {original[:80]}...")
            print(f"   After:  {content[:80]}...")

            data['content'] = content
            return HookExecutionResult(
                hook_name="pii_redactor",
                hook_type=HookType.POST_LLM_CALL,
                result=HookResult.MODIFY,
                modified_data=data
            )
        else:
            print("\n✓ No PII detected")
            return HookExecutionResult(
                hook_name="pii_redactor",
                hook_type=HookType.POST_LLM_CALL,
                result=HookResult.CONTINUE
            )

    # Test with PII data
    print("\n1. Testing LLM output with PII...")
    llm_output = {
        'content': 'The customer SSN is 123-45-6789 and credit card is 4532-1111-2222-3333. Contact: user@example.com',
        'model': 'gpt-4o-mini',
        'provider': 'openai'
    }

    results, modified_output = await manager.execute_hooks(
        HookType.POST_LLM_CALL,
        llm_output,
        HookContext()
    )

    print(f"\n✓ Final output: {modified_output['content']}")


async def demo_prompt_enrichment():
    """Demo 4: Prompt enrichment with context."""
    print("\n" + "="*80)
    print("DEMO 4: Prompt Enrichment - Adding Context")
    print("="*80)

    manager = HookManager()

    # Register prompt enrichment hook
    @manager.register_hook(HookType.PRE_LLM_CALL, "prompt_enricher", priority=50)
    async def enrich_prompt(data, context):
        # Add system context
        if isinstance(data, list) and len(data) > 0:
            original_content = data[0].get('content', '')
            enriched_content = (
                f"{original_content}\n\n"
                f"[Context: Model={context.model}, Provider={context.provider}]\n"
                f"[Workflow ID: {context.workflow_id or 'N/A'}]"
            )

            print(f"\n✨ ENRICHING PROMPT:")
            print(f"   Original: {original_content[:60]}...")
            print(f"   Enriched: {enriched_content[:80]}...")

            data[0]['content'] = enriched_content

            return HookExecutionResult(
                hook_name="prompt_enricher",
                hook_type=HookType.PRE_LLM_CALL,
                result=HookResult.MODIFY,
                modified_data=data
            )

        return HookExecutionResult(
            hook_name="prompt_enricher",
            hook_type=HookType.PRE_LLM_CALL,
            result=HookResult.CONTINUE
        )

    # Test
    print("\n1. Testing prompt enrichment...")
    messages = [
        {"role": "system", "content": "You are a helpful assistant."},
        {"role": "user", "content": "What is AI?"}
    ]
    context = HookContext(
        model="gpt-4o-mini",
        provider="openai",
        workflow_id="wf_12345"
    )

    results, modified_messages = await manager.execute_hooks(
        HookType.PRE_LLM_CALL,
        messages,
        context
    )

    print(f"\n✓ Final system message:\n{modified_messages[0]['content']}")


async def demo_hook_priority():
    """Demo 5: Hook priority and chaining."""
    print("\n" + "="*80)
    print("DEMO 5: Hook Priority and Chaining")
    print("="*80)

    manager = HookManager()

    # Register hooks with different priorities
    @manager.register_hook(HookType.PRE_LLM_CALL, "hook_1", priority=100)
    async def hook_1(data, context):
        print("   [3] Hook 1 executed (priority=100)")
        return HookExecutionResult(
            hook_name="hook_1",
            hook_type=HookType.PRE_LLM_CALL,
            result=HookResult.CONTINUE
        )

    @manager.register_hook(HookType.PRE_LLM_CALL, "hook_2", priority=10)
    async def hook_2(data, context):
        print("   [1] Hook 2 executed (priority=10) <- Runs FIRST")
        return HookExecutionResult(
            hook_name="hook_2",
            hook_type=HookType.PRE_LLM_CALL,
            result=HookResult.CONTINUE
        )

    @manager.register_hook(HookType.PRE_LLM_CALL, "hook_3", priority=50)
    async def hook_3(data, context):
        print("   [2] Hook 3 executed (priority=50)")
        return HookExecutionResult(
            hook_name="hook_3",
            hook_type=HookType.PRE_LLM_CALL,
            result=HookResult.CONTINUE
        )

    # Test
    print("\n1. Executing hooks in priority order (lower priority number = runs first)...")
    results, _ = await manager.execute_hooks(
        HookType.PRE_LLM_CALL,
        [],
        HookContext()
    )

    print(f"\n✓ Execution order confirmed: {[r.hook_name for r in results]}")


async def demo_error_handling():
    """Demo 6: Error handling modes."""
    print("\n" + "="*80)
    print("DEMO 6: Error Handling Modes")
    print("="*80)

    # Test CONTINUE mode (default)
    print("\n1. Testing ErrorMode.CONTINUE (log and continue)...")
    manager1 = HookManager()

    @manager1.register_hook(HookType.PRE_LLM_CALL, "failing_hook", error_mode=ErrorMode.CONTINUE)
    async def failing_hook(data, context):
        raise ValueError("Intentional error for testing")

    try:
        results, _ = await manager1.execute_hooks(HookType.PRE_LLM_CALL, [], HookContext())
        print(f"✓ Execution continued despite error. Results: {len(results)} hooks")
        print(f"  Error: {results[0].error}")
    except Exception as e:
        print(f"✗ Execution failed: {e}")

    # Test FAIL_FAST mode
    print("\n2. Testing ErrorMode.FAIL_FAST (stop on error)...")
    manager2 = HookManager()

    @manager2.register_hook(HookType.PRE_LLM_CALL, "strict_hook", error_mode=ErrorMode.FAIL_FAST)
    async def strict_hook(data, context):
        raise ValueError("Critical error - must stop")

    try:
        results, _ = await manager2.execute_hooks(HookType.PRE_LLM_CALL, [], HookContext())
        print("✓ Execution completed")
    except RuntimeError as e:
        print(f"✓ Execution stopped as expected: {e}")


async def demo_url_whitelist():
    """Demo 7: URL whitelist for tool calls."""
    print("\n" + "="*80)
    print("DEMO 7: URL Whitelist - Tool Security")
    print("="*80)

    manager = HookManager()

    # Register URL whitelist hook
    @manager.register_hook(HookType.PRE_TOOL_CALL, "url_whitelist", priority=10)
    async def check_url(data, context):
        allowed_domains = [
            'api.example.com',
            'jsonplaceholder.typicode.com',
            'httpbin.org'
        ]

        url = data.get('url', '')
        from urllib.parse import urlparse
        domain = urlparse(url).netloc

        if domain not in allowed_domains:
            print(f"\n🚫 BLOCKED: URL domain '{domain}' not in whitelist")
            return HookExecutionResult(
                hook_name="url_whitelist",
                hook_type=HookType.PRE_TOOL_CALL,
                result=HookResult.BLOCK,
                blocked_reason=f"Domain {domain} not whitelisted"
            )
        else:
            print(f"\n✓ ALLOWED: URL domain '{domain}' is whitelisted")
            return HookExecutionResult(
                hook_name="url_whitelist",
                hook_type=HookType.PRE_TOOL_CALL,
                result=HookResult.CONTINUE
            )

    # Test allowed URL
    print("\n1. Testing allowed URL...")
    try:
        results, _ = await manager.execute_hooks(
            HookType.PRE_TOOL_CALL,
            {'url': 'https://api.example.com/users'},
            HookContext(tool_name='fetch_users')
        )
        print("✓ Call allowed")
    except RuntimeError as e:
        print(f"✗ Call blocked: {e}")

    # Test blocked URL
    print("\n2. Testing blocked URL...")
    try:
        results, _ = await manager.execute_hooks(
            HookType.PRE_TOOL_CALL,
            {'url': 'https://malicious-site.com/hack'},
            HookContext(tool_name='dangerous_call')
        )
        print("✓ Call allowed")
    except RuntimeError as e:
        print(f"✗ Call blocked: {e}")


async def demo_builtin_hooks():
    """Demo 8: Using built-in hooks."""
    print("\n" + "="*80)
    print("DEMO 8: Built-in Hooks")
    print("="*80)

    # Reset and register built-in hooks
    reset_hook_manager()
    from backend.shared.hook_manager import get_hook_manager
    manager = get_hook_manager()

    # Register all built-in hooks
    register_builtin_hooks(manager)

    print("\n1. Registered built-in hooks:")
    for hook_type in HookType:
        hooks = manager.get_hooks(hook_type)
        if hooks:
            print(f"\n   {hook_type.value}:")
            for hook in hooks:
                print(f"     - {hook.name} (priority={hook.priority})")

    # Test cost guardrail
    print("\n2. Testing built-in cost_guardrail...")
    context = HookContext(
        estimated_cost=0.001,
        metadata={'max_cost': 0.10}
    )
    try:
        results, _ = await manager.execute_hooks(
            HookType.PRE_LLM_CALL,
            [],
            context
        )
        print(f"✓ {len(results)} hooks executed successfully")
    except Exception as e:
        print(f"✗ Error: {e}")


async def main():
    """Run all demos."""
    print("\n")
    print("╔" + "="*78 + "╗")
    print("║" + " " * 25 + "HOOK SYSTEM DEMO" + " " * 37 + "║")
    print("╚" + "="*78 + "╝")

    try:
        await demo_basic_hooks()
        await demo_cost_guardrail()
        await demo_pii_redaction()
        await demo_prompt_enrichment()
        await demo_hook_priority()
        await demo_error_handling()
        await demo_url_whitelist()
        await demo_builtin_hooks()

        print("\n" + "="*80)
        print("✓ All hook demos completed successfully!")
        print("="*80)
        print("\nKey Takeaways:")
        print("  • Hooks enable extensibility without modifying core code")
        print("  • Pre-LLM hooks: cost control, input validation, prompt enrichment")
        print("  • Post-LLM hooks: PII redaction, output validation, content filtering")
        print("  • Pre-Tool hooks: URL whitelisting, auth injection, parameter validation")
        print("  • Post-Tool hooks: response transformation, error handling")
        print("  • Priority system: lower number = runs first")
        print("  • Error modes: CONTINUE (log), FAIL_FAST (stop), FALLBACK (revert)")
        print("="*80)

    except Exception as e:
        print(f"\n❌ Demo failed: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    asyncio.run(main())
