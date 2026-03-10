#!/usr/bin/env python3
"""
Demo: Time Travel Debugging

Demonstrates workflow execution history and state replay.

Features demonstrated:
1. Execution state snapshots
2. Step-by-step replay
3. State inspection at any point
4. Branching from historical states
5. Comparison between executions

Usage:
    python demo_time_travel.py
"""

import sys
from pathlib import Path

# Add parent directory to path so backend.* imports work
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

import asyncio
import json
from datetime import datetime, timedelta
from dataclasses import dataclass, field
from typing import Optional, List, Dict, Any
from enum import Enum
import copy


class StepStatus(Enum):
    """Execution step status"""
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    SKIPPED = "skipped"


@dataclass
class StateSnapshot:
    """Snapshot of execution state at a point in time"""
    snapshot_id: str
    execution_id: str
    step_index: int
    step_name: str
    timestamp: datetime
    status: StepStatus
    input_state: Dict[str, Any]
    output_state: Dict[str, Any]
    variables: Dict[str, Any]
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "snapshot_id": self.snapshot_id,
            "step_index": self.step_index,
            "step_name": self.step_name,
            "timestamp": self.timestamp.isoformat(),
            "status": self.status.value,
            "variables": self.variables
        }


@dataclass
class ExecutionHistory:
    """Complete history of an execution"""
    execution_id: str
    workflow_id: str
    started_at: datetime
    completed_at: Optional[datetime] = None
    snapshots: List[StateSnapshot] = field(default_factory=list)
    final_status: str = "running"

    def add_snapshot(self, snapshot: StateSnapshot):
        """Add a snapshot to history"""
        self.snapshots.append(snapshot)

    def get_snapshot_at(self, step_index: int) -> Optional[StateSnapshot]:
        """Get snapshot at specific step"""
        for snapshot in self.snapshots:
            if snapshot.step_index == step_index:
                return snapshot
        return None

    def get_snapshots_in_range(self, start: int, end: int) -> List[StateSnapshot]:
        """Get snapshots in step range"""
        return [s for s in self.snapshots if start <= s.step_index <= end]


class TimeTravelDebugger:
    """Time travel debugging for workflow executions"""

    def __init__(self):
        self.histories: Dict[str, ExecutionHistory] = {}
        self.snapshot_counter = 0

    def create_history(self, execution_id: str, workflow_id: str) -> ExecutionHistory:
        """Create new execution history"""
        history = ExecutionHistory(
            execution_id=execution_id,
            workflow_id=workflow_id,
            started_at=datetime.utcnow()
        )
        self.histories[execution_id] = history
        return history

    def capture_snapshot(
        self,
        execution_id: str,
        step_index: int,
        step_name: str,
        status: StepStatus,
        input_state: Dict[str, Any],
        output_state: Dict[str, Any],
        variables: Dict[str, Any]
    ) -> StateSnapshot:
        """Capture state snapshot"""
        self.snapshot_counter += 1
        snapshot = StateSnapshot(
            snapshot_id=f"snap_{self.snapshot_counter:04d}",
            execution_id=execution_id,
            step_index=step_index,
            step_name=step_name,
            timestamp=datetime.utcnow(),
            status=status,
            input_state=copy.deepcopy(input_state),
            output_state=copy.deepcopy(output_state),
            variables=copy.deepcopy(variables)
        )

        history = self.histories.get(execution_id)
        if history:
            history.add_snapshot(snapshot)

        return snapshot

    def replay_to_step(self, execution_id: str, target_step: int) -> Dict[str, Any]:
        """Replay execution to specific step"""
        history = self.histories.get(execution_id)
        if not history:
            raise ValueError(f"Execution not found: {execution_id}")

        snapshots = history.get_snapshots_in_range(0, target_step)
        if not snapshots:
            return {"error": "No snapshots found for range"}

        final_snapshot = snapshots[-1]

        return {
            "execution_id": execution_id,
            "replayed_to_step": target_step,
            "step_name": final_snapshot.step_name,
            "status": final_snapshot.status.value,
            "variables": final_snapshot.variables,
            "timestamp": final_snapshot.timestamp.isoformat()
        }

    def compare_executions(
        self,
        execution_id_1: str,
        execution_id_2: str
    ) -> Dict[str, Any]:
        """Compare two execution histories"""
        history1 = self.histories.get(execution_id_1)
        history2 = self.histories.get(execution_id_2)

        if not history1 or not history2:
            raise ValueError("One or both executions not found")

        differences = []

        # Compare snapshots at each step
        max_steps = max(len(history1.snapshots), len(history2.snapshots))

        for i in range(max_steps):
            snap1 = history1.get_snapshot_at(i)
            snap2 = history2.get_snapshot_at(i)

            if snap1 and snap2:
                if snap1.status != snap2.status:
                    differences.append({
                        "step": i,
                        "type": "status_diff",
                        "exec1": snap1.status.value,
                        "exec2": snap2.status.value
                    })

                if snap1.variables != snap2.variables:
                    differences.append({
                        "step": i,
                        "type": "variable_diff",
                        "exec1_vars": list(snap1.variables.keys()),
                        "exec2_vars": list(snap2.variables.keys())
                    })

            elif snap1 and not snap2:
                differences.append({
                    "step": i,
                    "type": "missing_in_exec2",
                    "step_name": snap1.step_name
                })

            elif snap2 and not snap1:
                differences.append({
                    "step": i,
                    "type": "missing_in_exec1",
                    "step_name": snap2.step_name
                })

        return {
            "execution_1": execution_id_1,
            "execution_2": execution_id_2,
            "total_steps_1": len(history1.snapshots),
            "total_steps_2": len(history2.snapshots),
            "differences": differences
        }

    def branch_from_snapshot(
        self,
        snapshot_id: str,
        new_execution_id: str
    ) -> ExecutionHistory:
        """Create new execution branch from snapshot"""
        # Find the snapshot
        source_snapshot = None
        source_history = None

        for history in self.histories.values():
            for snapshot in history.snapshots:
                if snapshot.snapshot_id == snapshot_id:
                    source_snapshot = snapshot
                    source_history = history
                    break

        if not source_snapshot:
            raise ValueError(f"Snapshot not found: {snapshot_id}")

        # Create new history branching from snapshot
        new_history = ExecutionHistory(
            execution_id=new_execution_id,
            workflow_id=source_history.workflow_id,
            started_at=datetime.utcnow()
        )

        # Copy snapshots up to branch point
        for snapshot in source_history.snapshots:
            if snapshot.step_index <= source_snapshot.step_index:
                new_snapshot = StateSnapshot(
                    snapshot_id=f"snap_{self.snapshot_counter:04d}",
                    execution_id=new_execution_id,
                    step_index=snapshot.step_index,
                    step_name=snapshot.step_name,
                    timestamp=datetime.utcnow(),
                    status=snapshot.status,
                    input_state=copy.deepcopy(snapshot.input_state),
                    output_state=copy.deepcopy(snapshot.output_state),
                    variables=copy.deepcopy(snapshot.variables),
                    metadata={"branched_from": snapshot_id}
                )
                self.snapshot_counter += 1
                new_history.add_snapshot(new_snapshot)

        self.histories[new_execution_id] = new_history
        return new_history


class WorkflowSimulator:
    """Simulates workflow execution with time travel support"""

    def __init__(self, debugger: TimeTravelDebugger):
        self.debugger = debugger

    async def execute_workflow(
        self,
        workflow_id: str,
        steps: List[Dict[str, Any]],
        initial_variables: Dict[str, Any] = None,
        fail_at_step: int = -1
    ) -> str:
        """Execute workflow with state capture"""
        execution_id = f"exec_{datetime.utcnow().strftime('%H%M%S')}"
        history = self.debugger.create_history(execution_id, workflow_id)

        variables = initial_variables or {}
        print(f"\n🚀 Starting execution: {execution_id}")

        for i, step in enumerate(steps):
            step_name = step.get("name", f"Step {i}")
            print(f"\n  Step {i}: {step_name}")

            # Capture input state
            input_state = {"step_input": step.get("input", {})}

            # Check for simulated failure
            if i == fail_at_step:
                self.debugger.capture_snapshot(
                    execution_id, i, step_name,
                    StepStatus.FAILED, input_state, {},
                    variables
                )
                print(f"    ❌ Failed!")
                history.final_status = "failed"
                history.completed_at = datetime.utcnow()
                return execution_id

            # Simulate execution
            await asyncio.sleep(0.1)

            # Update variables based on step
            if step.get("type") == "set_variable":
                variables[step["var_name"]] = step["var_value"]
            elif step.get("type") == "llm_call":
                variables["last_llm_output"] = f"Response for {step_name}"
            elif step.get("type") == "compute":
                if "counter" in variables:
                    variables["counter"] += 1
                else:
                    variables["counter"] = 1

            # Capture output state
            output_state = {"step_output": f"Output from {step_name}"}

            self.debugger.capture_snapshot(
                execution_id, i, step_name,
                StepStatus.COMPLETED, input_state, output_state,
                variables
            )

            print(f"    ✅ Completed (variables: {list(variables.keys())})")

        history.final_status = "completed"
        history.completed_at = datetime.utcnow()
        print(f"\n✅ Execution {execution_id} completed!")

        return execution_id


async def demo_basic_time_travel():
    """Demo: Basic time travel debugging"""
    print("\n" + "="*60)
    print("Demo 1: Basic Time Travel Debugging")
    print("="*60)

    debugger = TimeTravelDebugger()
    simulator = WorkflowSimulator(debugger)

    # Execute workflow
    workflow_steps = [
        {"name": "Initialize", "type": "set_variable", "var_name": "status", "var_value": "started"},
        {"name": "Fetch Data", "type": "llm_call"},
        {"name": "Process Data", "type": "compute"},
        {"name": "Validate", "type": "compute"},
        {"name": "Finalize", "type": "set_variable", "var_name": "status", "var_value": "complete"}
    ]

    exec_id = await simulator.execute_workflow("workflow_1", workflow_steps)

    # Time travel to different points
    print("\n⏪ Time Travel: Replaying execution...")

    for step in range(len(workflow_steps)):
        result = debugger.replay_to_step(exec_id, step)
        print(f"\n  → Step {step}: {result['step_name']}")
        print(f"    Status: {result['status']}")
        print(f"    Variables: {result['variables']}")


async def demo_failure_analysis():
    """Demo: Analyzing failed executions"""
    print("\n" + "="*60)
    print("Demo 2: Failure Analysis")
    print("="*60)

    debugger = TimeTravelDebugger()
    simulator = WorkflowSimulator(debugger)

    workflow_steps = [
        {"name": "Initialize", "type": "set_variable", "var_name": "attempts", "var_value": 0},
        {"name": "Connect to API", "type": "llm_call"},
        {"name": "Fetch Records", "type": "llm_call"},
        {"name": "Transform Data", "type": "compute"},
        {"name": "Save Results", "type": "compute"}
    ]

    # Execute with failure at step 3
    exec_id = await simulator.execute_workflow(
        "workflow_failure_test",
        workflow_steps,
        fail_at_step=3
    )

    # Analyze failure
    print("\n🔍 Analyzing failure...")

    history = debugger.histories[exec_id]
    print(f"\n  Execution: {exec_id}")
    print(f"  Final Status: {history.final_status}")
    print(f"  Steps Completed: {len(history.snapshots)}")

    # Show state at failure
    failure_step = history.snapshots[-1]
    print(f"\n  Failure at step {failure_step.step_index}: {failure_step.step_name}")
    print(f"  Variables at failure: {failure_step.variables}")

    # Show previous successful step
    if len(history.snapshots) > 1:
        prev_step = history.snapshots[-2]
        print(f"\n  Last successful step: {prev_step.step_name}")
        print(f"  Variables: {prev_step.variables}")


async def demo_execution_comparison():
    """Demo: Comparing two executions"""
    print("\n" + "="*60)
    print("Demo 3: Execution Comparison")
    print("="*60)

    debugger = TimeTravelDebugger()
    simulator = WorkflowSimulator(debugger)

    workflow_steps = [
        {"name": "Start", "type": "set_variable", "var_name": "version", "var_value": "v1"},
        {"name": "Process", "type": "compute"},
        {"name": "Validate", "type": "compute"},
        {"name": "Complete", "type": "set_variable", "var_name": "status", "var_value": "done"}
    ]

    # Execute twice with different initial states
    print("\n📌 Running Execution 1 (v1)...")
    exec_id_1 = await simulator.execute_workflow(
        "compare_workflow",
        workflow_steps,
        initial_variables={"env": "dev"}
    )

    # Modify workflow slightly for second run
    workflow_steps_v2 = [
        {"name": "Start", "type": "set_variable", "var_name": "version", "var_value": "v2"},
        {"name": "Process", "type": "compute"},
        {"name": "Extra Step", "type": "compute"},  # Extra step
        {"name": "Validate", "type": "compute"},
        {"name": "Complete", "type": "set_variable", "var_name": "status", "var_value": "done"}
    ]

    print("\n📌 Running Execution 2 (v2 with extra step)...")
    exec_id_2 = await simulator.execute_workflow(
        "compare_workflow",
        workflow_steps_v2,
        initial_variables={"env": "prod"}
    )

    # Compare executions
    comparison = debugger.compare_executions(exec_id_1, exec_id_2)

    print("\n📊 Comparison Results:")
    print(f"  Execution 1: {comparison['total_steps_1']} steps")
    print(f"  Execution 2: {comparison['total_steps_2']} steps")
    print(f"\n  Differences found: {len(comparison['differences'])}")

    for diff in comparison['differences']:
        print(f"\n    Step {diff['step']}: {diff['type']}")
        if diff['type'] == 'variable_diff':
            print(f"      Exec1 vars: {diff['exec1_vars']}")
            print(f"      Exec2 vars: {diff['exec2_vars']}")


async def demo_branching():
    """Demo: Branching from historical state"""
    print("\n" + "="*60)
    print("Demo 4: Branching from Historical State")
    print("="*60)

    debugger = TimeTravelDebugger()
    simulator = WorkflowSimulator(debugger)

    workflow_steps = [
        {"name": "Initialize", "type": "set_variable", "var_name": "path", "var_value": "original"},
        {"name": "Decision Point", "type": "compute"},
        {"name": "Path A", "type": "compute"},
        {"name": "Complete A", "type": "set_variable", "var_name": "result", "var_value": "path_a_done"}
    ]

    # Execute original workflow
    print("\n📌 Running original execution...")
    exec_id = await simulator.execute_workflow("branch_workflow", workflow_steps)

    # Find decision point snapshot
    history = debugger.histories[exec_id]
    decision_snapshot = history.get_snapshot_at(1)

    print(f"\n🌿 Creating branch from step 1 (Decision Point)...")
    print(f"  Source snapshot: {decision_snapshot.snapshot_id}")

    # Branch from decision point
    new_exec_id = f"branch_{datetime.utcnow().strftime('%H%M%S')}"
    new_history = debugger.branch_from_snapshot(
        decision_snapshot.snapshot_id,
        new_exec_id
    )

    print(f"  New execution: {new_exec_id}")
    print(f"  Inherited {len(new_history.snapshots)} snapshots")

    # Continue with different path
    print("\n  Continuing with alternative path...")
    alt_steps = [
        {"name": "Path B", "type": "set_variable", "var_name": "path", "var_value": "alternative"},
        {"name": "Complete B", "type": "set_variable", "var_name": "result", "var_value": "path_b_done"}
    ]

    # Add more snapshots to the branch
    variables = new_history.snapshots[-1].variables.copy()
    for i, step in enumerate(alt_steps):
        step_idx = len(new_history.snapshots)
        variables["path"] = "alternative"
        debugger.capture_snapshot(
            new_exec_id, step_idx, step["name"],
            StepStatus.COMPLETED, {}, {},
            variables
        )
        print(f"    ✅ {step['name']}")

    # Compare branches
    print("\n📊 Branch Comparison:")
    print(f"  Original: {len(history.snapshots)} steps")
    print(f"  Branch: {len(new_history.snapshots)} steps")


async def demo_state_inspection():
    """Demo: Detailed state inspection"""
    print("\n" + "="*60)
    print("Demo 5: Detailed State Inspection")
    print("="*60)

    debugger = TimeTravelDebugger()
    simulator = WorkflowSimulator(debugger)

    workflow_steps = [
        {"name": "Load Config", "type": "set_variable", "var_name": "config", "var_value": {"api_url": "https://api.example.com", "timeout": 30}},
        {"name": "Authenticate", "type": "set_variable", "var_name": "token", "var_value": "jwt_xxx"},
        {"name": "Fetch Users", "type": "set_variable", "var_name": "users", "var_value": ["user1", "user2", "user3"]},
        {"name": "Process Users", "type": "compute"},
        {"name": "Generate Report", "type": "set_variable", "var_name": "report", "var_value": {"total": 3, "processed": 3}}
    ]

    exec_id = await simulator.execute_workflow("inspect_workflow", workflow_steps)

    print("\n🔍 State Inspection at each step:")

    history = debugger.histories[exec_id]
    for snapshot in history.snapshots:
        print(f"\n  Step {snapshot.step_index}: {snapshot.step_name}")
        print(f"    Timestamp: {snapshot.timestamp.strftime('%H:%M:%S.%f')[:-3]}")
        print(f"    Status: {snapshot.status.value}")
        print(f"    Variables ({len(snapshot.variables)}):")
        for key, value in snapshot.variables.items():
            value_str = json.dumps(value) if isinstance(value, (dict, list)) else str(value)
            if len(value_str) > 50:
                value_str = value_str[:50] + "..."
            print(f"      {key}: {value_str}")


async def main():
    """Run all demos"""
    print("="*60)
    print("⏰ Time Travel Debugging Demo")
    print("="*60)
    print("\nThis demo shows execution history and state replay capabilities.")

    await demo_basic_time_travel()
    await demo_failure_analysis()
    await demo_execution_comparison()
    await demo_branching()
    await demo_state_inspection()

    print("\n" + "="*60)
    print("✅ All demos completed!")
    print("="*60)


if __name__ == "__main__":
    asyncio.run(main())
