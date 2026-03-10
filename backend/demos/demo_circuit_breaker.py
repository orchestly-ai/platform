#!/usr/bin/env python3
"""
Circuit Breaker Demo

Demonstrates the circuit breaker protection for runaway agents.

Scenarios:
1. Normal operation - within limits
2. Token velocity breach - suspension triggered
3. Cost runaway - kill triggered
4. Tool loop detection - infinite loop caught
5. Batch operation bypass - elevated limits

Run with: ./run_demo.sh backend/demos/demo_circuit_breaker.py
"""

import asyncio
import sys
from pathlib import Path
from uuid import uuid4
from datetime import datetime

# Add backend to path
backend_dir = Path(__file__).parent.parent
sys.path.insert(0, str(backend_dir))
parent_dir = backend_dir.parent
sys.path.insert(0, str(parent_dir))

from backend.shared.circuit_breaker_service import (
    CircuitBreaker,
    CircuitBreakerConfig,
    CircuitBreakerAction,
    BatchOperationConfig,
    validate_batch_config
)


class MockDB:
    """Mock database for demo."""
    async def execute(self, query):
        class Result:
            def scalar_one_or_none(self):
                return None
        return Result()

    async def flush(self):
        pass


def print_header(title: str):
    """Print a section header."""
    print("\n" + "=" * 60)
    print(f"  {title}")
    print("=" * 60)


def print_result(result, context: str = ""):
    """Print a circuit breaker result."""
    status = "PROCEED" if result.proceed else "BLOCKED"
    action = result.action.value.upper()
    color = "\033[92m" if result.proceed else "\033[91m"  # Green or Red
    reset = "\033[0m"

    print(f"\n{color}[{status}]{reset} Action: {action}")
    if context:
        print(f"  Context: {context}")
    if result.reason:
        print(f"  Reason: {result.reason}")
    if result.metrics:
        print(f"  Metrics: {result.metrics}")


async def demo_normal_operation():
    """Scenario 1: Normal operation within limits."""
    print_header("Scenario 1: Normal Operation (Within Limits)")
    print("\nSimulating normal agent behavior with reasonable token/cost usage...")

    db = MockDB()
    config = CircuitBreakerConfig(
        token_velocity_per_minute=50_000,
        cost_velocity_per_minute=5.0,
        same_tool_consecutive_limit=5,
        total_tool_calls_per_execution=100
    )
    cb = CircuitBreaker(db, config)
    execution_id = uuid4()

    # Simulate 3 normal LLM calls
    print("\n--- Making 3 normal LLM calls ---")
    for i in range(3):
        result = await cb.check_before_llm_call(execution_id)
        print_result(result, f"Pre-check for LLM call #{i+1}")

        await cb.record_llm_call(execution_id, tokens_used=1000, cost=0.01)
        print(f"  Recorded: 1,000 tokens, $0.01")

    # Simulate tool calls
    print("\n--- Making 2 different tool calls ---")
    tools = [
        ("search_database", {"query": "SELECT * FROM users"}),
        ("send_email", {"to": "user@example.com", "subject": "Hello"})
    ]

    for tool_name, params in tools:
        result = await cb.check_before_tool_call(execution_id, tool_name, params)
        print_result(result, f"Tool: {tool_name}")

    print("\n Result: All operations completed within limits.")


async def demo_token_velocity_breach():
    """Scenario 2: Token velocity breach triggers suspension."""
    print_header("Scenario 2: Token Velocity Breach")
    print("\nSimulating rapid token consumption that exceeds limits...")

    db = MockDB()
    config = CircuitBreakerConfig(
        token_velocity_per_minute=5_000,  # Low limit for demo
        cost_velocity_per_minute=5.0
    )
    cb = CircuitBreaker(db, config)
    execution_id = uuid4()

    print(f"\nLimit: 5,000 tokens/minute")
    print("Simulating rapid consumption of 10,000 tokens...")

    # Rapidly consume tokens
    for i in range(10):
        await cb.record_llm_call(execution_id, tokens_used=1000, cost=0.01)

    # Check if we can proceed
    result = await cb.check_before_llm_call(execution_id)
    print_result(result, "After consuming 10,000 tokens")

    print("\n Result: Circuit breaker suspended execution for human approval.")
    print("         This prevents runaway token consumption.")


async def demo_cost_runaway():
    """Scenario 3: Cost runaway triggers kill."""
    print_header("Scenario 3: Cost Runaway Detection")
    print("\nSimulating runaway cost that triggers immediate termination...")

    db = MockDB()
    config = CircuitBreakerConfig(
        token_velocity_per_minute=100_000,
        cost_velocity_per_minute=0.50  # $0.50/min limit for demo
    )
    cb = CircuitBreaker(db, config)
    execution_id = uuid4()

    print(f"\nLimit: $0.50/minute")
    print("Simulating $5.00 in costs (10x the limit)...")

    # Simulate expensive operations
    for i in range(10):
        await cb.record_llm_call(execution_id, tokens_used=5000, cost=0.50)

    result = await cb.check_before_llm_call(execution_id)
    print_result(result, "After $5.00 in costs")

    print("\n Result: Circuit breaker KILLED execution immediately.")
    print("         KILL is the most severe action, used for cost runaways.")
    print("         This prevents $100+ surprises in 5 minutes.")


async def demo_tool_loop_detection():
    """Scenario 4: Tool loop detection catches infinite loops."""
    print_header("Scenario 4: Tool Loop Detection (Infinite Loop Prevention)")
    print("\nSimulating an agent stuck in an infinite loop...")

    db = MockDB()
    config = CircuitBreakerConfig(
        same_tool_consecutive_limit=5
    )
    cb = CircuitBreaker(db, config)
    execution_id = uuid4()

    print("\n--- Identical Tool Calls (Same Params) ---")
    print("Calling 'fetch_data' with same params repeatedly...")

    for i in range(4):
        result = await cb.check_before_tool_call(
            execution_id,
            "fetch_data",
            {"url": "https://api.example.com/data", "limit": 100}  # Same params
        )
        print_result(result, f"Identical call #{i+1}")

        if not result.proceed:
            break

    print("\n Result: Infinite loop detected after 3 identical calls.")
    print("         Agent was likely stuck retrying the same failed operation.")

    # Reset for consecutive demo
    cb2 = CircuitBreaker(MockDB(), CircuitBreakerConfig(same_tool_consecutive_limit=3))
    execution_id2 = uuid4()

    print("\n--- Consecutive Same Tool (Different Params) ---")
    print("Calling 'send_email' repeatedly with different recipients...")

    for i in range(4):
        result = await cb2.check_before_tool_call(
            execution_id2,
            "send_email",
            {"recipient": f"user{i}@example.com", "subject": f"Message {i}"}
        )
        print_result(result, f"Email to user{i}@example.com")

        if not result.proceed:
            break

    print("\n Result: Consecutive tool calls triggered suspension.")
    print("         Agent might be in a loop even with varying params.")


async def demo_batch_bypass():
    """Scenario 5: Batch operation bypass with elevated limits."""
    print_header("Scenario 5: Batch Operation Bypass")
    print("\nDemonstrating legitimate high-volume batch processing...")

    db = MockDB()
    config = CircuitBreakerConfig(
        token_velocity_per_minute=5_000,  # Normal limit
        cost_velocity_per_minute=0.50
    )
    cb = CircuitBreaker(db, config)
    execution_id = uuid4()

    print("\nNormal limits: 5,000 tokens/min, $0.50/min")

    # First, show it would normally block
    print("\n--- Without Batch Bypass ---")
    for i in range(10):
        await cb.record_llm_call(execution_id, tokens_used=1000, cost=0.10)

    result = await cb.check_before_llm_call(execution_id)
    print_result(result, "High volume without bypass")

    # Now with batch bypass
    print("\n--- With Batch Bypass (Admin Approved) ---")

    batch_config = BatchOperationConfig(
        bypass_circuit_breaker=True,
        elevated_token_limit=500_000,
        elevated_cost_limit=50.0,
        audit_reason="Quarterly financial report generation - 500 documents"
    )

    # Validate permissions (simulating admin)
    try:
        validate_batch_config(batch_config, {"ADMIN"})
        print("  Permission check: PASSED (ADMIN)")
    except PermissionError as e:
        print(f"  Permission check: FAILED ({e})")
        return

    # Now check with bypass
    result = await cb.check_before_llm_call(execution_id, batch_config=batch_config)
    print_result(result, "Same volume WITH batch bypass")

    print("\n Batch config:")
    print(f"    Elevated token limit: 500,000/min (10x)")
    print(f"    Elevated cost limit: $50/min (10x)")
    print(f"    Audit reason: '{batch_config.audit_reason}'")

    print("\n Result: Batch bypass allowed high-volume processing.")
    print("         Requires ADMIN permission and audit reason.")
    print("         All bypass usage is logged for audit trail.")

    # Show what happens without permission
    print("\n--- Batch Bypass Without Permission ---")
    try:
        validate_batch_config(batch_config, {"USER", "EDITOR"})
    except PermissionError as e:
        print(f"  PermissionError: {e}")


async def demo_summary():
    """Print summary of circuit breaker actions."""
    print_header("Circuit Breaker Action Summary")

    print("""
    ACTION              SEVERITY    WHEN TRIGGERED
    ──────────────────────────────────────────────────────────────
    PROCEED             None        Normal operation, all checks pass

    ALERT               Low         Warning logged, execution continues
                                    (For metrics approaching limits)

    SUSPEND_FOR_APPROVAL Medium     Execution paused, human review needed
                                    - Token velocity exceeded
                                    - Tool called too many times
                                    - Recursion depth exceeded
                                    - LLM call limit reached

    KILL                High        Execution terminated immediately
                                    - Cost runaway detected ($$/min)
                                    - Infinite loop (identical params 3x)

    ──────────────────────────────────────────────────────────────

    DEFAULT LIMITS:
    - Token velocity:     50,000 tokens/minute
    - Cost velocity:      $5.00/minute
    - Same tool limit:    5 consecutive calls
    - Total tool calls:   100 per execution
    - Total LLM calls:    50 per execution
    - Recursion depth:    10 levels

    BATCH OPERATION BYPASS (requires ADMIN):
    - Token velocity:     500,000 tokens/minute (10x)
    - Cost velocity:      $50.00/minute (10x)
    - Total tool calls:   1,000 per execution (10x)
    - Requires audit reason for compliance
    """)


async def main():
    """Run all demo scenarios."""
    print("\n" + "=" * 60)
    print("  CIRCUIT BREAKER DEMO")
    print("  Runaway Agent Protection")
    print("=" * 60)
    print("\nThis demo shows how the circuit breaker protects against:")
    print("  1. Token velocity overruns")
    print("  2. Cost runaways (prevents $100+ surprises)")
    print("  3. Infinite loops in tool calls")
    print("  4. Excessive LLM calls")
    print("  5. Deep recursion")

    await demo_normal_operation()
    await demo_token_velocity_breach()
    await demo_cost_runaway()
    await demo_tool_loop_detection()
    await demo_batch_bypass()
    await demo_summary()

    print("\n" + "=" * 60)
    print("  DEMO COMPLETE")
    print("=" * 60)
    print("\nThe circuit breaker catches problems BEFORE the 30-second")
    print("heartbeat would detect them, preventing expensive runaways.")
    print("\nSee ROADMAP.md Section: 'Recursive Loop & Cost Runaway Circuit Breaker'")


if __name__ == "__main__":
    asyncio.run(main())
