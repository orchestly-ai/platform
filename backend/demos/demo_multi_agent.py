#!/usr/bin/env python3
"""
Demo: Multi-Agent Orchestration

Demonstrates coordination between multiple specialized AI agents.

Features demonstrated:
1. Agent registration with capabilities
2. Task decomposition and routing
3. Parallel agent execution
4. Agent communication
5. Result aggregation

Usage:
    python demo_multi_agent.py
"""

import sys
from pathlib import Path

# Add parent directory to path so backend.* imports work
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

import asyncio
import random
from datetime import datetime
from dataclasses import dataclass, field
from typing import Optional, List, Dict, Any, Callable
from enum import Enum
import json


class AgentStatus(Enum):
    """Agent status"""
    IDLE = "idle"
    BUSY = "busy"
    OFFLINE = "offline"


@dataclass
class Agent:
    """An AI agent with specific capabilities"""
    id: str
    name: str
    capabilities: List[str]
    status: AgentStatus = AgentStatus.IDLE
    current_task: Optional[str] = None
    tasks_completed: int = 0
    avg_execution_time_ms: float = 0.0
    cost_per_task: float = 0.01

    def can_handle(self, required_capabilities: List[str]) -> bool:
        """Check if agent can handle task"""
        return all(cap in self.capabilities for cap in required_capabilities)


@dataclass
class Task:
    """A task to be executed by agents"""
    id: str
    description: str
    required_capabilities: List[str]
    input_data: Dict[str, Any]
    priority: int = 1
    status: str = "pending"
    assigned_agent: Optional[str] = None
    result: Optional[Dict[str, Any]] = None
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None


@dataclass
class AgentMessage:
    """Message between agents"""
    from_agent: str
    to_agent: str
    message_type: str
    content: Dict[str, Any]
    timestamp: datetime = field(default_factory=datetime.utcnow)


class AgentRegistry:
    """Registry of available agents"""

    def __init__(self):
        self.agents: Dict[str, Agent] = {}

    def register(self, agent: Agent):
        """Register an agent"""
        self.agents[agent.id] = agent
        print(f"  📋 Registered: {agent.name}")
        print(f"     Capabilities: {', '.join(agent.capabilities)}")

    def find_capable_agents(self, capabilities: List[str]) -> List[Agent]:
        """Find agents that can handle required capabilities"""
        return [
            agent for agent in self.agents.values()
            if agent.can_handle(capabilities) and agent.status != AgentStatus.OFFLINE
        ]

    def get_best_agent(self, capabilities: List[str]) -> Optional[Agent]:
        """Get the best available agent for capabilities"""
        capable = self.find_capable_agents(capabilities)

        # Prefer idle agents, then by execution time
        idle_agents = [a for a in capable if a.status == AgentStatus.IDLE]
        if idle_agents:
            return min(idle_agents, key=lambda a: a.avg_execution_time_ms)

        return None


class TaskDecomposer:
    """Decomposes complex tasks into subtasks"""

    def decompose(self, complex_task: str) -> List[Task]:
        """Decompose a complex task into subtasks"""
        # Simulate task decomposition based on keywords
        subtasks = []
        task_id = 1

        if "code" in complex_task.lower() or "implement" in complex_task.lower():
            subtasks.append(Task(
                id=f"subtask_{task_id}",
                description="Analyze requirements and design solution",
                required_capabilities=["analysis", "design"],
                input_data={"original_task": complex_task}
            ))
            task_id += 1

            subtasks.append(Task(
                id=f"subtask_{task_id}",
                description="Write implementation code",
                required_capabilities=["code_generation"],
                input_data={"original_task": complex_task}
            ))
            task_id += 1

            subtasks.append(Task(
                id=f"subtask_{task_id}",
                description="Review code for quality and security",
                required_capabilities=["code_review", "security"],
                input_data={"original_task": complex_task}
            ))
            task_id += 1

            subtasks.append(Task(
                id=f"subtask_{task_id}",
                description="Write tests for the implementation",
                required_capabilities=["testing"],
                input_data={"original_task": complex_task}
            ))

        elif "research" in complex_task.lower():
            subtasks.append(Task(
                id=f"subtask_{task_id}",
                description="Gather information from sources",
                required_capabilities=["research", "web_search"],
                input_data={"original_task": complex_task}
            ))
            task_id += 1

            subtasks.append(Task(
                id=f"subtask_{task_id}",
                description="Analyze and synthesize findings",
                required_capabilities=["analysis"],
                input_data={"original_task": complex_task}
            ))
            task_id += 1

            subtasks.append(Task(
                id=f"subtask_{task_id}",
                description="Generate report with conclusions",
                required_capabilities=["writing"],
                input_data={"original_task": complex_task}
            ))

        else:
            # Default: single task
            subtasks.append(Task(
                id=f"subtask_{task_id}",
                description=complex_task,
                required_capabilities=["general"],
                input_data={"original_task": complex_task}
            ))

        return subtasks


class Orchestrator:
    """Orchestrates multi-agent task execution"""

    def __init__(self, registry: AgentRegistry):
        self.registry = registry
        self.decomposer = TaskDecomposer()
        self.message_queue: List[AgentMessage] = []
        self.completed_tasks: List[Task] = []
        self.total_cost = 0.0

    async def execute_task(self, agent: Agent, task: Task) -> Dict[str, Any]:
        """Simulate task execution by agent"""
        agent.status = AgentStatus.BUSY
        agent.current_task = task.id
        task.assigned_agent = agent.id
        task.started_at = datetime.utcnow()
        task.status = "running"

        # Simulate execution time
        exec_time = random.uniform(0.2, 0.8)
        await asyncio.sleep(exec_time)

        # Generate result
        result = {
            "agent": agent.name,
            "task": task.description[:50],
            "output": f"Completed: {task.description[:30]}...",
            "execution_time_ms": exec_time * 1000
        }

        task.result = result
        task.completed_at = datetime.utcnow()
        task.status = "completed"

        # Update agent stats
        agent.status = AgentStatus.IDLE
        agent.current_task = None
        agent.tasks_completed += 1
        agent.avg_execution_time_ms = (
            (agent.avg_execution_time_ms * (agent.tasks_completed - 1) + exec_time * 1000)
            / agent.tasks_completed
        )

        self.total_cost += agent.cost_per_task

        return result

    async def orchestrate(self, complex_task: str) -> Dict[str, Any]:
        """Orchestrate multi-agent execution of complex task"""
        print(f"\n🎯 Task: {complex_task}")

        # Decompose task
        subtasks = self.decomposer.decompose(complex_task)
        print(f"📋 Decomposed into {len(subtasks)} subtasks")

        results = []

        for task in subtasks:
            print(f"\n  📌 Subtask: {task.description[:50]}...")
            print(f"     Needs: {', '.join(task.required_capabilities)}")

            # Find capable agent
            agent = self.registry.get_best_agent(task.required_capabilities)

            if agent:
                print(f"     Assigned to: {agent.name}")
                result = await self.execute_task(agent, task)
                results.append(result)
                self.completed_tasks.append(task)
                print(f"     ✅ Completed in {result['execution_time_ms']:.0f}ms")
            else:
                print(f"     ❌ No capable agent available")
                task.status = "failed"

        return {
            "original_task": complex_task,
            "subtasks_total": len(subtasks),
            "subtasks_completed": len([t for t in subtasks if t.status == "completed"]),
            "total_cost": round(self.total_cost, 4),
            "results": results
        }

    async def orchestrate_parallel(self, complex_task: str) -> Dict[str, Any]:
        """Execute subtasks in parallel where possible"""
        print(f"\n🎯 Task (Parallel): {complex_task}")

        subtasks = self.decomposer.decompose(complex_task)
        print(f"📋 Decomposed into {len(subtasks)} subtasks")

        # Group tasks by capability for parallel execution
        async_tasks = []

        for task in subtasks:
            agent = self.registry.get_best_agent(task.required_capabilities)
            if agent:
                print(f"  📌 {task.description[:40]}... → {agent.name}")
                async_tasks.append(self.execute_task(agent, task))

        # Execute in parallel
        print(f"\n⚡ Executing {len(async_tasks)} tasks in parallel...")
        start_time = datetime.utcnow()
        results = await asyncio.gather(*async_tasks)
        elapsed = (datetime.utcnow() - start_time).total_seconds()

        print(f"✅ All tasks completed in {elapsed:.2f}s")

        return {
            "original_task": complex_task,
            "parallel_execution": True,
            "total_time_seconds": elapsed,
            "results": results
        }


async def demo_basic_orchestration():
    """Demo: Basic multi-agent orchestration"""
    print("\n" + "="*60)
    print("Demo 1: Basic Multi-Agent Orchestration")
    print("="*60)

    # Create registry and register agents
    registry = AgentRegistry()
    print("\n📋 Registering agents...")

    registry.register(Agent(
        id="agent_analyst",
        name="Analyst Agent",
        capabilities=["analysis", "design", "research"]
    ))

    registry.register(Agent(
        id="agent_coder",
        name="Coder Agent",
        capabilities=["code_generation", "testing"]
    ))

    registry.register(Agent(
        id="agent_reviewer",
        name="Reviewer Agent",
        capabilities=["code_review", "security", "testing"]
    ))

    # Create orchestrator
    orchestrator = Orchestrator(registry)

    # Execute complex task
    result = await orchestrator.orchestrate(
        "Implement a user authentication system with password hashing"
    )

    print(f"\n📊 Summary:")
    print(f"  Subtasks completed: {result['subtasks_completed']}/{result['subtasks_total']}")
    print(f"  Total cost: ${result['total_cost']}")


async def demo_parallel_execution():
    """Demo: Parallel agent execution"""
    print("\n" + "="*60)
    print("Demo 2: Parallel Agent Execution")
    print("="*60)

    registry = AgentRegistry()
    print("\n📋 Registering multiple agents per capability...")

    # Register multiple agents per capability
    for i in range(3):
        registry.register(Agent(
            id=f"researcher_{i}",
            name=f"Researcher {i+1}",
            capabilities=["research", "web_search", "analysis"]
        ))

    for i in range(2):
        registry.register(Agent(
            id=f"writer_{i}",
            name=f"Writer {i+1}",
            capabilities=["writing", "analysis"]
        ))

    orchestrator = Orchestrator(registry)

    result = await orchestrator.orchestrate_parallel(
        "Research the latest AI trends and write a comprehensive report"
    )

    print(f"\n📊 Parallel Execution Results:")
    print(f"  Total time: {result['total_time_seconds']:.2f}s")
    print(f"  Tasks executed: {len(result['results'])}")


async def demo_agent_communication():
    """Demo: Agent-to-agent communication"""
    print("\n" + "="*60)
    print("Demo 3: Agent Communication")
    print("="*60)

    registry = AgentRegistry()

    # Register specialized agents
    registry.register(Agent(
        id="planner",
        name="Planner Agent",
        capabilities=["planning", "decomposition"]
    ))

    registry.register(Agent(
        id="executor",
        name="Executor Agent",
        capabilities=["execution", "code_generation"]
    ))

    registry.register(Agent(
        id="validator",
        name="Validator Agent",
        capabilities=["validation", "testing"]
    ))

    # Simulate agent communication
    messages = [
        AgentMessage(
            from_agent="planner",
            to_agent="executor",
            message_type="task_assignment",
            content={"task": "Implement login endpoint", "priority": 1}
        ),
        AgentMessage(
            from_agent="executor",
            to_agent="planner",
            message_type="status_update",
            content={"task": "login endpoint", "status": "completed"}
        ),
        AgentMessage(
            from_agent="planner",
            to_agent="validator",
            message_type="validation_request",
            content={"artifact": "login_endpoint.py", "tests_required": True}
        ),
        AgentMessage(
            from_agent="validator",
            to_agent="planner",
            message_type="validation_result",
            content={"passed": True, "coverage": 95}
        )
    ]

    print("\n📬 Agent Communication Flow:")
    for msg in messages:
        print(f"\n  [{msg.message_type}]")
        print(f"  From: {msg.from_agent} → To: {msg.to_agent}")
        print(f"  Content: {json.dumps(msg.content)}")
        await asyncio.sleep(0.3)


async def demo_capability_routing():
    """Demo: Capability-based routing"""
    print("\n" + "="*60)
    print("Demo 4: Capability-Based Routing")
    print("="*60)

    registry = AgentRegistry()

    # Register specialized agents
    agents = [
        Agent("nlp_agent", "NLP Specialist", ["text_analysis", "sentiment", "summarization"]),
        Agent("vision_agent", "Vision Specialist", ["image_analysis", "ocr", "object_detection"]),
        Agent("data_agent", "Data Specialist", ["data_analysis", "sql", "visualization"]),
        Agent("general_agent", "General Assistant", ["general", "writing", "research"]),
    ]

    print("\n📋 Registering specialized agents...")
    for agent in agents:
        registry.register(agent)

    # Test different task types
    test_tasks = [
        (["text_analysis", "sentiment"], "Analyze customer feedback sentiment"),
        (["image_analysis"], "Extract text from scanned document"),
        (["data_analysis", "visualization"], "Create sales dashboard"),
        (["general"], "Write a blog post about AI"),
        (["quantum_computing"], "Simulate quantum algorithm")  # No agent can handle
    ]

    print("\n🔍 Testing capability routing...")
    for capabilities, description in test_tasks:
        print(f"\n  Task: {description}")
        print(f"  Requires: {capabilities}")

        agent = registry.get_best_agent(capabilities)
        if agent:
            print(f"  ✅ Routed to: {agent.name}")
        else:
            print(f"  ❌ No capable agent found")


async def demo_supervisor_pattern():
    """Demo: Supervisor agent pattern"""
    print("\n" + "="*60)
    print("Demo 5: Supervisor Agent Pattern")
    print("="*60)

    registry = AgentRegistry()

    # Register supervisor and workers
    supervisor = Agent(
        id="supervisor",
        name="Supervisor Agent",
        capabilities=["planning", "coordination", "decision_making"]
    )
    registry.register(supervisor)

    workers = [
        Agent("worker_1", "Worker 1", ["code_generation", "general"]),
        Agent("worker_2", "Worker 2", ["testing", "general"]),
        Agent("worker_3", "Worker 3", ["documentation", "general"]),
    ]
    for w in workers:
        registry.register(w)

    print("\n🎯 Supervisor coordinating task: 'Build a REST API endpoint'")

    # Supervisor assigns subtasks
    assignments = [
        ("worker_1", "Implement the endpoint handler"),
        ("worker_2", "Write unit and integration tests"),
        ("worker_3", "Document the API endpoint"),
    ]

    print("\n📋 Supervisor distributing work:")
    for worker_id, task in assignments:
        worker = registry.agents.get(worker_id)
        print(f"  → {worker.name}: {task}")

    # Simulate parallel execution
    print("\n⚡ Workers executing in parallel...")
    await asyncio.sleep(0.5)

    print("\n📊 Supervisor collecting results:")
    for worker_id, task in assignments:
        worker = registry.agents.get(worker_id)
        print(f"  ✅ {worker.name}: Completed")

    print("\n🎯 Supervisor: All subtasks completed, aggregating results...")
    await asyncio.sleep(0.2)
    print("✅ Final result: REST API endpoint implementation complete")


async def main():
    """Run all demos"""
    print("="*60)
    print("🤖 Multi-Agent Orchestration Demo")
    print("="*60)
    print("\nThis demo shows coordination between multiple AI agents.")

    await demo_basic_orchestration()
    await demo_parallel_execution()
    await demo_agent_communication()
    await demo_capability_routing()
    await demo_supervisor_pattern()

    print("\n" + "="*60)
    print("✅ All demos completed!")
    print("="*60)


if __name__ == "__main__":
    asyncio.run(main())
