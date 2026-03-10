#!/usr/bin/env python
"""
Demo Script: AgentOrch Sandbox Workflows

This script demonstrates the 5 pre-built demo workflows without needing
the API server running. It shows how the mock LLM and integrations work.

Usage:
    python demo_sandbox_workflows.py

Each workflow runs through its steps, showing:
- Mock LLM responses
- Mock integration calls
- Cost tracking
- Execution traces
"""

import asyncio
import sys
from datetime import datetime

# Add parent to path for imports
sys.path.insert(0, ".")

from sandbox.mock.llm_mock import get_mock_provider
from sandbox.mock.integration_mock import get_mock_integration_provider
from sandbox.workflows import get_demo_workflows


def print_header(text: str):
    """Print a styled header."""
    print("\n" + "=" * 70)
    print(f"  {text}")
    print("=" * 70)


def print_step(step_num: int, name: str, step_type: str):
    """Print a step indicator."""
    icons = {
        "llm": "🤖",
        "integration": "🔌",
        "conditional": "🔀",
    }
    icon = icons.get(step_type, "📋")
    print(f"\n  [{step_num}] {icon} {name} ({step_type})")
    print("  " + "-" * 50)


async def run_workflow(workflow):
    """Execute a demo workflow and show the results."""
    llm_provider = get_mock_provider()
    integration_provider = get_mock_integration_provider()

    print_header(f"WORKFLOW: {workflow.name}")
    print(f"  📝 {workflow.description}")
    print(f"  📁 Category: {workflow.category}")
    print(f"  💰 Estimated Cost: ${workflow.estimated_cost:.4f}")
    print(f"  ⏱️  Estimated Duration: {workflow.estimated_duration_ms}ms")
    print(f"\n  🎯 Showcase Features: {', '.join(workflow.showcase_features)}")

    print("\n  📥 Sample Inputs:")
    for key, value in workflow.sample_inputs.items():
        value_str = str(value)[:60] + "..." if len(str(value)) > 60 else str(value)
        print(f"     • {key}: {value_str}")

    # Execute steps
    print("\n" + "─" * 70)
    print("  EXECUTION TRACE")
    print("─" * 70)

    total_cost = 0.0
    current_state = dict(workflow.sample_inputs)
    start_time = datetime.now()

    for i, step in enumerate(workflow.steps, 1):
        step_name = step.get("name", f"step_{i}")
        step_type = step.get("type", "unknown")

        print_step(i, step_name, step_type)

        if step_type == "llm":
            # Show LLM call
            model = step.get("model", "gpt-4")
            provider = step.get("provider", "openai")
            print(f"     Model: {provider}/{model}")

            # Execute mock LLM
            messages = [
                {"role": "system", "content": step.get("system_prompt", "You are helpful.")},
                {"role": "user", "content": step.get("prompt", "Hello")[:100] + "..."},
            ]

            response = await llm_provider.complete(
                messages=messages,
                model=model,
                provider=provider,
                scenario=step.get("scenario"),
                variant=step.get("variant"),
            )

            # Show response preview
            content_preview = response.content[:200].replace("\n", " ") + "..."
            print(f"     Response: {content_preview}")
            print(f"     Tokens: {response.total_tokens} | Cost: ${response.cost:.4f} | Latency: {response.latency_ms}ms")

            total_cost += response.cost
            current_state[step_name] = response.content

        elif step_type == "integration":
            # Show integration call
            connector = step.get("connector", step.get("integration", "unknown"))
            action = step.get("action", "execute")
            print(f"     Integration: {connector}")
            print(f"     Action: {action}")

            # Execute mock integration
            result = await integration_provider.execute(
                integration=connector,
                action=action,
                params=step.get("params", {}),
            )

            print(f"     Success: {result.success}")
            print(f"     Latency: {result.latency_ms}ms")

            current_state[step_name] = result.data

        elif step_type == "conditional":
            # Show conditional
            condition = step.get("condition", "true")
            print(f"     Condition: {condition}")
            print(f"     Result: True (simulated)")

        else:
            print(f"     (Generic step)")

    # Summary
    end_time = datetime.now()
    duration_ms = int((end_time - start_time).total_seconds() * 1000)

    print("\n" + "─" * 70)
    print("  EXECUTION SUMMARY")
    print("─" * 70)
    print(f"     Status: ✅ Completed")
    print(f"     Steps: {len(workflow.steps)}")
    print(f"     Duration: {duration_ms}ms")
    print(f"     Total Cost: ${total_cost:.4f}")


async def main():
    """Run all demo workflows."""
    print("\n" + "█" * 70)
    print("█" + " " * 68 + "█")
    print("█" + "    AgentOrch Sandbox - Demo Workflows".center(68) + "█")
    print("█" + " " * 68 + "█")
    print("█" * 70)

    workflows = get_demo_workflows()

    print(f"\n  📋 {len(workflows)} Demo Workflows Available:")
    for i, w in enumerate(workflows, 1):
        print(f"     {i}. {w.name} ({w.category})")

    print("\n  Running all workflows...\n")

    for workflow in workflows:
        await run_workflow(workflow)
        print("\n")

    # Final stats
    llm_provider = get_mock_provider()
    integration_provider = get_mock_integration_provider()

    print("═" * 70)
    print("  FINAL STATISTICS")
    print("═" * 70)

    llm_stats = llm_provider.get_usage_stats()
    int_stats = integration_provider.get_usage_stats()

    print(f"\n  🤖 LLM Calls: {llm_stats['total_calls']}")
    print(f"     Total Tokens: {llm_stats['total_tokens']}")
    print(f"     Total Cost: ${llm_stats['total_cost']:.4f}")

    if llm_stats.get("by_provider"):
        print("\n     By Provider:")
        for provider, stats in llm_stats["by_provider"].items():
            print(f"       • {provider}: {stats['calls']} calls, ${stats['cost']:.4f}")

    print(f"\n  🔌 Integration Calls: {int_stats['total_calls']}")
    print(f"     Successful: {int_stats['successful']}")
    print(f"     Failed: {int_stats['failed']}")

    if int_stats.get("by_integration"):
        print("\n     By Integration:")
        for integration, stats in int_stats["by_integration"].items():
            print(f"       • {integration}: {stats['calls']} calls")

    print("\n" + "═" * 70)
    print("  ✅ All demos completed successfully!")
    print("  💡 These are mock responses - no actual API calls were made.")
    print("═" * 70 + "\n")


if __name__ == "__main__":
    asyncio.run(main())
