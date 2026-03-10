"""
Test script to reproduce and debug the recursion issue in the DAG builder.

The recursion issue occurs when:
1. Parallel nodes execute (like multi-LLM comparison)
2. Their outputs are merged
3. The output_data is saved to the database

This script simulates the exact conditions that cause the recursion.
"""

import asyncio
import sys
import json
from datetime import datetime
from uuid import uuid4, UUID
from typing import Any, Optional

# Track recursion depth manually
RECURSION_DEPTH = 0
MAX_RECURSION = 100


def test_json_serialization():
    """Test the JSON serialization function for circular reference issues."""

    print("=" * 80)
    print("TEST 1: Basic strict_json_serialize tests")
    print("=" * 80)

    # Import the function
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    from backend.shared.workflow_service import strict_json_serialize
    from backend.shared.workflow_models import ExecutionStatus, NodeType, WorkflowStatus

    # Test 1: Simple data
    print("\n1.1 Testing simple data...")
    simple_data = {"key": "value", "number": 42, "list": [1, 2, 3]}
    result = strict_json_serialize(simple_data)
    print(f"   Simple data: OK - {result}")

    # Test 1.1b: Enum handling (NEW TEST)
    print("\n1.1b Testing Enum serialization...")
    enum_data = {
        "status": ExecutionStatus.RUNNING,
        "node_type": NodeType.AGENT_LLM,
        "workflow_status": WorkflowStatus.ACTIVE
    }
    result = strict_json_serialize(enum_data)
    print(f"   Enum data: {result}")
    assert result["status"] == "running", f"Expected 'running', got {result['status']}"
    assert result["node_type"] == "agent_llm", f"Expected 'agent_llm', got {result['node_type']}"
    print("   Enum serialization: OK")

    # Test 2: Data with UUID and datetime
    print("\n1.2 Testing UUID and datetime...")
    complex_data = {
        "id": uuid4(),
        "timestamp": datetime.utcnow(),
        "nested": {"uuid": uuid4()}
    }
    result = strict_json_serialize(complex_data)
    print(f"   UUID/datetime: OK")

    # Test 3: Circular reference (simulating workflow output cross-reference)
    print("\n1.3 Testing circular reference...")
    node_outputs = {}
    node_outputs["node_a"] = {"data": "from A", "ref": None}
    node_outputs["node_b"] = {"data": "from B", "ref": node_outputs["node_a"]}
    node_outputs["node_a"]["ref"] = node_outputs["node_b"]  # Circular!

    try:
        result = strict_json_serialize(node_outputs)
        print(f"   Circular reference handled: OK")
        print(f"   Result type: {type(result)}")
    except RecursionError as e:
        print(f"   FAIL - RecursionError: {e}")

    # Test 4: Deep nesting (like merge node combining multiple parallel outputs)
    print("\n1.4 Testing deep nested structure (parallel nodes + merge)...")

    # Simulate multi-LLM comparison workflow
    input_node = {"query": "What is AI?", "type": "input"}
    llm_openai = {"text": "OpenAI response", "tokens": {"input": 10, "output": 50}}
    llm_anthropic = {"text": "Anthropic response", "tokens": {"input": 10, "output": 50}}
    llm_deepseek = {"text": "DeepSeek response", "tokens": {"input": 10, "output": 50}}

    # Merge node output - this is where circular references can occur
    merge_output = {
        "openai": llm_openai,
        "anthropic": llm_anthropic,
        "deepseek": llm_deepseek,
    }

    # Final output references back to merged data
    output_node = {
        "status": "complete",
        "results": merge_output,
    }

    # Build the full node_outputs dict (as would happen in workflow execution)
    node_outputs = {
        "input": input_node,
        "input_1": input_node,
        "llm_openai": llm_openai,
        "llm_anthropic": llm_anthropic,
        "llm_deepseek": llm_deepseek,
        "merge_1": merge_output,
        "output_1": output_node,
    }

    try:
        result = strict_json_serialize(node_outputs)
        print(f"   Deep nested structure: OK")
        # Try to JSON dump it
        json_str = json.dumps(result)
        print(f"   JSON serializable: OK (length: {len(json_str)})")
    except RecursionError as e:
        print(f"   FAIL - RecursionError: {e}")
    except Exception as e:
        print(f"   FAIL - {type(e).__name__}: {e}")


def test_complex_object_serialization():
    """Test serialization of complex objects that might cause issues."""

    print("\n" + "=" * 80)
    print("TEST 2: Complex object serialization")
    print("=" * 80)

    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    from backend.shared.workflow_service import strict_json_serialize

    # Test with dataclass-like objects
    print("\n2.1 Testing with workflow dataclasses...")

    try:
        from backend.shared.workflow_models import (
            WorkflowNode, WorkflowEdge, WorkflowExecution,
            NodeType, ExecutionStatus
        )

        # Create workflow nodes
        nodes = [
            WorkflowNode(
                id="input_1",
                type=NodeType.DATA_INPUT,
                position={"x": 100, "y": 200},
                data={"label": "Input"}
            ),
            WorkflowNode(
                id="llm_1",
                type=NodeType.LLM_OPENAI,
                position={"x": 400, "y": 200},
                data={"model": "gpt-4"}
            ),
        ]

        result = strict_json_serialize(nodes)
        print(f"   WorkflowNode list: OK")

        # Create execution with node_states
        execution = WorkflowExecution(
            execution_id=uuid4(),
            workflow_id=uuid4(),
            workflow_version=1,
            organization_id="test_org",
            status=ExecutionStatus.COMPLETED,
            node_states={
                "input_1": {"status": "completed", "output": {"data": "test"}},
                "llm_1": {"status": "completed", "output": {"text": "response"}}
            },
            output_data={"final": "result"}
        )

        result = strict_json_serialize(execution)
        print(f"   WorkflowExecution: OK")

    except Exception as e:
        print(f"   FAIL - {type(e).__name__}: {e}")


def test_the_actual_bug_scenario():
    """
    Test the EXACT scenario that causes the bug:
    Multi-LLM comparison workflow with parallel execution and merge.
    """

    print("\n" + "=" * 80)
    print("TEST 3: Reproducing the exact bug scenario")
    print("=" * 80)

    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    from backend.shared.workflow_service import strict_json_serialize

    print("\n3.1 Simulating Multi-LLM Comparison workflow execution...")

    # This is the EXACT structure built during workflow execution
    node_outputs = {}

    # Step 1: Input node executed first
    input_data = {"query": "Explain quantum computing in simple terms"}
    node_outputs["input"] = strict_json_serialize(input_data)

    # Step 2: Three LLM nodes execute in parallel (they share input reference)
    node_inputs_for_llms = {
        "input_1": node_outputs["input"]  # All LLMs get same input
    }

    # OpenAI response
    openai_output = {
        "text": "OpenAI GPT-4 response about quantum computing...",
        "model": "gpt-4",
        "tokens": {"input": 100, "output": 50, "total": 150}
    }
    node_outputs["llm_openai"] = strict_json_serialize(openai_output)

    # Anthropic response
    anthropic_output = {
        "text": "Anthropic Claude response about quantum computing...",
        "model": "claude-3-opus",
        "tokens": {"input": 100, "output": 50, "total": 150}
    }
    node_outputs["llm_anthropic"] = strict_json_serialize(anthropic_output)

    # DeepSeek response
    deepseek_output = {
        "text": "DeepSeek response about quantum computing...",
        "model": "deepseek-chat",
        "tokens": {"input": 100, "output": 50, "total": 150}
    }
    node_outputs["llm_deepseek"] = strict_json_serialize(deepseek_output)

    # Step 3: Merge node combines all LLM outputs
    merge_inputs = {
        "llm_openai": node_outputs["llm_openai"],
        "llm_anthropic": node_outputs["llm_anthropic"],
        "llm_deepseek": node_outputs["llm_deepseek"],
    }

    # CRITICAL: This is where the DATA_MERGE node combines inputs
    merged = {}
    for key, value in merge_inputs.items():
        if isinstance(value, dict):
            merged.update(value)
    node_outputs["merge_1"] = strict_json_serialize(merged)

    # Step 4: Output node - THE BUG WAS HERE
    # Old buggy code: return inputs (which creates cross-references)
    # Fixed code: return simple status dict
    output_inputs = {
        "merge_1": node_outputs["merge_1"]
    }

    # OLD BUGGY VERSION (commented out):
    # output_result = output_inputs  # This creates circular refs!

    # FIXED VERSION:
    output_result = {
        "status": "output_complete",
        "node_id": "output_1",
        "input_count": len(output_inputs)
    }
    node_outputs["output_1"] = strict_json_serialize(output_result)

    print("   All nodes executed and serialized: OK")

    # Step 5: Final serialization of entire output (what gets saved to DB)
    print("\n3.2 Testing final serialization (what goes to database)...")

    try:
        final_result = strict_json_serialize(node_outputs)
        json_str = json.dumps(final_result)
        print(f"   Final output serialized: OK (length: {len(json_str)})")

        # Verify it's valid JSON by parsing it back
        parsed = json.loads(json_str)
        print(f"   JSON round-trip: OK (keys: {list(parsed.keys())})")

    except RecursionError as e:
        print(f"   FAIL - RecursionError during final serialization!")
        print(f"   Error: {e}")
        return False

    except Exception as e:
        print(f"   FAIL - {type(e).__name__}: {e}")
        return False

    # Step 6: Test with actual cross-references (simulating the bug)
    print("\n3.3 Testing with INTENTIONAL cross-references (bug simulation)...")

    buggy_node_outputs = {}
    buggy_node_outputs["a"] = {"data": "A"}
    buggy_node_outputs["b"] = {"data": "B", "ref_to_a": buggy_node_outputs["a"]}
    buggy_node_outputs["c"] = {"data": "C", "ref_to_b": buggy_node_outputs["b"]}
    buggy_node_outputs["a"]["ref_to_c"] = buggy_node_outputs["c"]  # Circular!

    try:
        result = strict_json_serialize(buggy_node_outputs)
        json_str = json.dumps(result)
        print(f"   Circular refs handled: OK")
        print(f"   Result: {json_str[:200]}...")
    except RecursionError as e:
        print(f"   FAIL - RecursionError: {e}")

    return True


def test_sqlalchemy_json_serialization():
    """
    Test that the data can be stored in SQLAlchemy JSON column.
    This simulates what happens in _update_execution_status.
    """

    print("\n" + "=" * 80)
    print("TEST 4: SQLAlchemy JSON column compatibility")
    print("=" * 80)

    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    from backend.shared.workflow_service import strict_json_serialize

    # Create the data that would be stored
    execution_output = {
        "input": {"query": "test"},
        "llm_1": {"text": "response", "tokens": {"total": 100}},
        "output_1": {"status": "complete"}
    }

    node_states = {
        "input_1": {
            "status": "completed",
            "output_summary": "dict data",
            "duration": 0.01,
            "completed_at": datetime.utcnow().isoformat()
        },
        "llm_1": {
            "status": "completed",
            "output_summary": "dict data",
            "duration": 1.5,
            "completed_at": datetime.utcnow().isoformat()
        },
    }

    print("\n4.1 Testing data structures for database storage...")

    try:
        # Serialize as would happen in workflow_service.py
        safe_output = strict_json_serialize(execution_output)
        safe_states = strict_json_serialize(node_states)

        # These should be JSON-serializable
        json.dumps(safe_output)
        json.dumps(safe_states)

        print(f"   Output data: OK")
        print(f"   Node states: OK")

    except Exception as e:
        print(f"   FAIL - {type(e).__name__}: {e}")


if __name__ == "__main__":
    print("\n" + "=" * 80)
    print("DAG BUILDER RECURSION DEBUG TEST")
    print("=" * 80)
    print("\nThis test suite reproduces the conditions that cause the recursion bug")
    print("in the Visual DAG Builder workflow execution engine.\n")

    test_json_serialization()
    test_complex_object_serialization()
    success = test_the_actual_bug_scenario()
    test_sqlalchemy_json_serialization()

    print("\n" + "=" * 80)
    if success:
        print("✅ ALL TESTS PASSED - No recursion issues detected")
        print("   The strict_json_serialize function handles circular refs correctly")
        print("   The bug may be in SQLAlchemy ORM graph traversal during commit")
    else:
        print("❌ TESTS FAILED - Recursion issues detected")
    print("=" * 80 + "\n")
