"""
Supervisor Orchestration Service

Implements multi-agent coordination patterns:
- Supervisor routing (intelligent task assignment)
- Task decomposition (break complex tasks into subtasks)
- Group chat mode (AutoGen-style multi-agent conversations)
- Sequential/concurrent execution
- Dynamic handoffs

Competitive advantage: Matches AWS Agent Squad + Microsoft AutoGen.
This solves complex multi-agent orchestration at scale.
"""

from typing import Optional, Dict, Any, List, Tuple
from uuid import UUID, uuid4
from datetime import datetime
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_, update
import asyncio
import json

from backend.shared.supervisor_models import (
    SupervisorConfigModel, SupervisorExecutionModel,
    AgentRegistryModel, TaskAssignmentModel,
    SupervisorMode, RoutingStrategy, AgentRole, TaskStatus,
    SupervisorConfig, SupervisorExecution, Agent, TaskAssignment
)


# ============================================================================
# Task Decomposition Service
# ============================================================================

class TaskDecompositionService:
    """
    Breaks down complex tasks into subtasks.

    Uses LLM to intelligently decompose tasks based on:
    - Task complexity
    - Available agents
    - Dependencies
    """

    def __init__(self, db: AsyncSession):
        self.db = db

    async def decompose_task(
        self,
        task: str,
        config: SupervisorConfig,
        agent_pool: List[Agent]
    ) -> List[Dict[str, Any]]:
        """
        Decompose complex task into subtasks.

        Returns list of subtasks with:
        - Task ID
        - Description
        - Type/category
        - Suggested agent (based on capabilities)
        - Dependencies
        - Priority
        """

        # Build agent capabilities summary for LLM
        agent_summary = self._build_agent_summary(agent_pool)

        # Generate decomposition prompt
        decomposition_prompt = config.decomposition_prompt or self._default_decomposition_prompt()

        # In production, this would call LLM API
        # For now, simulate intelligent decomposition
        subtasks = await self._simulate_task_decomposition(
            task=task,
            agent_summary=agent_summary,
            decomposition_prompt=decomposition_prompt
        )

        return subtasks

    def _build_agent_summary(self, agent_pool: List[Agent]) -> str:
        """Build human-readable summary of available agents."""
        summary_lines = []
        for agent in agent_pool:
            capabilities_str = ", ".join(agent.capabilities) if agent.capabilities else "general"
            summary_lines.append(
                f"- {agent.name} ({agent.role.value}): {capabilities_str}"
            )
        return "\n".join(summary_lines)

    def _default_decomposition_prompt(self) -> str:
        """Default prompt for task decomposition."""
        return """
You are a task decomposition expert. Break down the given task into smaller, manageable subtasks.

For each subtask, specify:
1. Task ID (short identifier)
2. Description (clear, actionable description)
3. Type (research, analysis, writing, coding, etc.)
4. Dependencies (which other subtasks must complete first)
5. Priority (1-10, higher is more important)

Available agents:
{agent_summary}

Task to decompose:
{task}

Provide subtasks in JSON format.
"""

    async def _simulate_task_decomposition(
        self,
        task: str,
        agent_summary: str,
        decomposition_prompt: str
    ) -> List[Dict[str, Any]]:
        """
        Simulate LLM-based task decomposition.

        In production, this would call GPT-4/Claude to decompose the task.
        For demo purposes, we do intelligent rule-based decomposition.
        """

        # Simple rule-based decomposition for demo
        task_lower = task.lower()

        subtasks = []

        # Research task pattern
        if "research" in task_lower or "analyze" in task_lower:
            subtasks = [
                {
                    "id": "research_1",
                    "description": f"Gather information about: {task}",
                    "type": "research",
                    "dependencies": [],
                    "priority": 8,
                    "suggested_agent_role": "specialist"
                },
                {
                    "id": "analysis_1",
                    "description": "Analyze gathered information and identify key insights",
                    "type": "analysis",
                    "dependencies": ["research_1"],
                    "priority": 7,
                    "suggested_agent_role": "specialist"
                },
                {
                    "id": "summary_1",
                    "description": "Summarize findings and create report",
                    "type": "writing",
                    "dependencies": ["analysis_1"],
                    "priority": 6,
                    "suggested_agent_role": "worker"
                }
            ]

        # Writing task pattern
        elif "write" in task_lower or "create content" in task_lower:
            subtasks = [
                {
                    "id": "outline_1",
                    "description": "Create outline for content",
                    "type": "planning",
                    "dependencies": [],
                    "priority": 8,
                    "suggested_agent_role": "worker"
                },
                {
                    "id": "draft_1",
                    "description": "Write first draft",
                    "type": "writing",
                    "dependencies": ["outline_1"],
                    "priority": 7,
                    "suggested_agent_role": "worker"
                },
                {
                    "id": "review_1",
                    "description": "Review and edit content",
                    "type": "review",
                    "dependencies": ["draft_1"],
                    "priority": 6,
                    "suggested_agent_role": "reviewer"
                }
            ]

        # Coding task pattern
        elif "code" in task_lower or "implement" in task_lower or "develop" in task_lower:
            subtasks = [
                {
                    "id": "design_1",
                    "description": "Design solution architecture",
                    "type": "design",
                    "dependencies": [],
                    "priority": 9,
                    "suggested_agent_role": "specialist"
                },
                {
                    "id": "implement_1",
                    "description": "Implement core functionality",
                    "type": "coding",
                    "dependencies": ["design_1"],
                    "priority": 8,
                    "suggested_agent_role": "worker"
                },
                {
                    "id": "test_1",
                    "description": "Write and run tests",
                    "type": "testing",
                    "dependencies": ["implement_1"],
                    "priority": 7,
                    "suggested_agent_role": "worker"
                },
                {
                    "id": "review_code_1",
                    "description": "Code review and quality check",
                    "type": "review",
                    "dependencies": ["test_1"],
                    "priority": 6,
                    "suggested_agent_role": "reviewer"
                }
            ]

        # Default: simple 3-step decomposition
        else:
            subtasks = [
                {
                    "id": "step_1",
                    "description": f"Execute first step: {task[:50]}...",
                    "type": "general",
                    "dependencies": [],
                    "priority": 8,
                    "suggested_agent_role": "worker"
                },
                {
                    "id": "step_2",
                    "description": "Execute second step based on step 1 results",
                    "type": "general",
                    "dependencies": ["step_1"],
                    "priority": 7,
                    "suggested_agent_role": "worker"
                },
                {
                    "id": "step_3",
                    "description": "Finalize and compile results",
                    "type": "general",
                    "dependencies": ["step_2"],
                    "priority": 6,
                    "suggested_agent_role": "worker"
                }
            ]

        return subtasks


# ============================================================================
# Routing Service
# ============================================================================

class RoutingService:
    """
    Routes tasks to best-fit agents based on strategy.

    Implements multiple routing strategies:
    - Round robin
    - Capability matching
    - Load balancing
    - Priority-based
    - LLM decision
    - Custom rules
    """

    def __init__(self, db: AsyncSession):
        self.db = db
        self._round_robin_index = 0

    async def route_task(
        self,
        task: Dict[str, Any],
        agent_pool: List[Agent],
        strategy: RoutingStrategy,
        routing_rules: Optional[List[Dict[str, Any]]] = None
    ) -> Tuple[Agent, str, float]:
        """
        Route task to best agent.

        Returns: (selected_agent, reason, confidence_score)
        """

        if strategy == RoutingStrategy.ROUND_ROBIN:
            return await self._route_round_robin(task, agent_pool)

        elif strategy == RoutingStrategy.CAPABILITY_MATCH:
            return await self._route_capability_match(task, agent_pool)

        elif strategy == RoutingStrategy.LOAD_BALANCED:
            return await self._route_load_balanced(task, agent_pool)

        elif strategy == RoutingStrategy.PRIORITY_BASED:
            return await self._route_priority_based(task, agent_pool)

        elif strategy == RoutingStrategy.LLM_DECISION:
            return await self._route_llm_decision(task, agent_pool)

        elif strategy == RoutingStrategy.CUSTOM_RULES:
            return await self._route_custom_rules(task, agent_pool, routing_rules)

        else:
            # Default to capability match
            return await self._route_capability_match(task, agent_pool)

    async def _route_round_robin(
        self,
        task: Dict[str, Any],
        agent_pool: List[Agent]
    ) -> Tuple[Agent, str, float]:
        """Round robin routing - distribute evenly."""
        if not agent_pool:
            raise ValueError("No agents available")

        active_agents = [a for a in agent_pool if a.is_active]
        if not active_agents:
            raise ValueError("No active agents available")

        agent = active_agents[self._round_robin_index % len(active_agents)]
        self._round_robin_index += 1

        return agent, "Round robin distribution", 1.0

    async def _route_capability_match(
        self,
        task: Dict[str, Any],
        agent_pool: List[Agent]
    ) -> Tuple[Agent, str, float]:
        """Match task to agent capabilities."""
        if not agent_pool:
            raise ValueError("No agents available")

        active_agents = [a for a in agent_pool if a.is_active]
        if not active_agents:
            raise ValueError("No active agents available")

        task_type = task.get("type", "general")
        suggested_role = task.get("suggested_agent_role")

        # Score each agent based on capability match
        scores = []
        for agent in active_agents:
            score = 0.0

            # Role match
            if suggested_role and agent.role.value == suggested_role:
                score += 0.5

            # Capability match
            if agent.capabilities:
                for capability in agent.capabilities:
                    if capability.lower() in task_type.lower():
                        score += 0.3
                    if "description" in task and capability.lower() in task["description"].lower():
                        score += 0.2

            # Specialization match
            if agent.specialization:
                if task_type.lower() in agent.specialization.lower():
                    score += 0.4

            # Performance bonus
            if agent.success_rate and agent.success_rate > 0.8:
                score += 0.1

            # Load penalty
            if agent.current_load > agent.max_concurrent_tasks * 0.5:
                score -= 0.2

            scores.append((agent, score))

        # Select highest scoring agent
        scores.sort(key=lambda x: x[1], reverse=True)
        best_agent, best_score = scores[0]

        confidence = min(best_score, 1.0)
        reason = f"Best capability match (score: {best_score:.2f})"

        return best_agent, reason, confidence

    async def _route_load_balanced(
        self,
        task: Dict[str, Any],
        agent_pool: List[Agent]
    ) -> Tuple[Agent, str, float]:
        """Route to least busy agent."""
        if not agent_pool:
            raise ValueError("No agents available")

        active_agents = [a for a in agent_pool if a.is_active]
        if not active_agents:
            raise ValueError("No active agents available")

        # Sort by current load (ascending)
        active_agents.sort(key=lambda a: a.current_load)
        least_busy = active_agents[0]

        utilization = (least_busy.current_load / least_busy.max_concurrent_tasks) if least_busy.max_concurrent_tasks > 0 else 0
        reason = f"Least busy agent (utilization: {utilization:.1%})"

        return least_busy, reason, 0.9

    async def _route_priority_based(
        self,
        task: Dict[str, Any],
        agent_pool: List[Agent]
    ) -> Tuple[Agent, str, float]:
        """Route based on task priority."""
        task_priority = task.get("priority", 5)

        # High priority tasks get specialized agents
        if task_priority >= 8:
            specialists = [a for a in agent_pool if a.role == AgentRole.SPECIALIST and a.is_active]
            if specialists:
                # Get least busy specialist
                specialists.sort(key=lambda a: a.current_load)
                return specialists[0], f"High priority ({task_priority}) → specialist", 0.95

        # Medium priority get workers
        workers = [a for a in agent_pool if a.role == AgentRole.WORKER and a.is_active]
        if workers:
            workers.sort(key=lambda a: a.current_load)
            return workers[0], f"Medium priority ({task_priority}) → worker", 0.85

        # Fallback to any active agent
        active = [a for a in agent_pool if a.is_active]
        if active:
            return active[0], f"Priority {task_priority} → first available", 0.7

        raise ValueError("No active agents available")

    async def _route_llm_decision(
        self,
        task: Dict[str, Any],
        agent_pool: List[Agent]
    ) -> Tuple[Agent, str, float]:
        """Use LLM to decide routing (simulated for now)."""
        # In production, this would call GPT-4/Claude to make routing decision
        # For demo, use capability matching as proxy
        return await self._route_capability_match(task, agent_pool)

    async def _route_custom_rules(
        self,
        task: Dict[str, Any],
        agent_pool: List[Agent],
        routing_rules: Optional[List[Dict[str, Any]]] = None
    ) -> Tuple[Agent, str, float]:
        """Apply custom routing rules."""
        if not routing_rules:
            return await self._route_capability_match(task, agent_pool)

        task_desc = task.get("description", "").lower()
        task_type = task.get("type", "").lower()

        # Check each rule
        for rule in routing_rules:
            condition = rule.get("if", "").lower()
            target_agent_id = rule.get("route_to")

            # Simple condition matching
            if condition in task_desc or condition in task_type:
                # Find target agent
                target = next((a for a in agent_pool if a.agent_id == target_agent_id), None)
                if target and target.is_active:
                    return target, f"Custom rule match: {condition}", 1.0

        # No rule matched, fallback
        return await self._route_capability_match(task, agent_pool)


# ============================================================================
# Supervisor Execution Service
# ============================================================================

class SupervisorExecutionService:
    """
    Main supervisor execution service.

    Orchestrates multi-agent execution using configured strategy.
    """

    def __init__(self, db: AsyncSession):
        self.db = db
        self.decomposition_service = TaskDecompositionService(db)
        self.routing_service = RoutingService(db)

    async def execute_supervised_task(
        self,
        config: SupervisorConfig,
        input_task: str,
        workflow_execution_id: Optional[UUID] = None
    ) -> SupervisorExecution:
        """
        Execute task using supervisor orchestration.

        Steps:
        1. Decompose task into subtasks (if configured)
        2. Load agent pool
        3. Route subtasks to agents
        4. Execute based on mode (sequential, concurrent, group chat, etc.)
        5. Aggregate results
        """

        # Create execution record
        execution_id = uuid4()
        execution_model = SupervisorExecutionModel(
            execution_id=execution_id,
            config_id=config.config_id,
            workflow_execution_id=workflow_execution_id,
            organization_id=config.organization_id,
            status="running",
            mode=config.mode.value,
            input_task=input_task,
            started_at=datetime.utcnow()
        )
        self.db.add(execution_model)
        await self.db.commit()

        try:
            # Step 1: Load agent pool
            agents = await self._load_agent_pool(config.agent_pool, config.organization_id)

            if not agents:
                raise ValueError("No agents available in pool")

            # Step 2: Decompose task (if enabled)
            if config.auto_decompose_tasks:
                subtasks = await self.decomposition_service.decompose_task(
                    task=input_task,
                    config=config,
                    agent_pool=agents
                )
            else:
                # Single task
                subtasks = [{
                    "id": "main_task",
                    "description": input_task,
                    "type": "general",
                    "dependencies": [],
                    "priority": 5
                }]

            # Step 3: Route tasks to agents
            routing_decisions = []
            agent_assignments = {}

            for subtask in subtasks:
                agent, reason, confidence = await self.routing_service.route_task(
                    task=subtask,
                    agent_pool=agents,
                    strategy=config.routing_strategy,
                    routing_rules=config.routing_rules
                )

                routing_decisions.append({
                    "task_id": subtask["id"],
                    "agent": agent.agent_id,
                    "reason": reason,
                    "confidence": confidence
                })

                if agent.agent_id not in agent_assignments:
                    agent_assignments[agent.agent_id] = {"tasks": [], "status": "active"}
                agent_assignments[agent.agent_id]["tasks"].append(subtask["id"])

            # Update execution with routing info
            execution_model.subtasks = subtasks
            execution_model.agent_assignments = agent_assignments
            execution_model.routing_decisions = routing_decisions
            execution_model.total_agents_used = len(agent_assignments)
            await self.db.commit()

            # Step 4: Execute based on mode
            if config.mode == SupervisorMode.SEQUENTIAL:
                result = await self._execute_sequential(execution_id, subtasks, routing_decisions, agents)
            elif config.mode == SupervisorMode.CONCURRENT:
                result = await self._execute_concurrent(execution_id, subtasks, routing_decisions, agents)
            elif config.mode == SupervisorMode.GROUP_CHAT:
                result = await self._execute_group_chat(execution_id, subtasks, routing_decisions, agents, config)
            elif config.mode == SupervisorMode.HANDOFF:
                result = await self._execute_handoff(execution_id, subtasks, routing_decisions, agents)
            else:
                # Default to sequential
                result = await self._execute_sequential(execution_id, subtasks, routing_decisions, agents)

            # Step 5: Update execution with results
            execution_model.status = "completed"
            execution_model.output_result = result
            execution_model.completed_at = datetime.utcnow()

            if execution_model.started_at:
                duration = (execution_model.completed_at - execution_model.started_at).total_seconds() * 1000
                execution_model.duration_ms = duration

            await self.db.commit()

            # Convert to dataclass
            execution = self._model_to_dataclass(execution_model)
            return execution

        except Exception as e:
            # Handle execution failure
            execution_model.status = "failed"
            execution_model.error_message = str(e)
            execution_model.completed_at = datetime.utcnow()
            await self.db.commit()

            raise

    async def _load_agent_pool(
        self,
        agent_ids: List[str],
        organization_id: str
    ) -> List[Agent]:
        """Load agents from registry."""
        stmt = select(AgentRegistryModel).where(
            and_(
                AgentRegistryModel.agent_id.in_(agent_ids),
                AgentRegistryModel.organization_id == organization_id,
                AgentRegistryModel.is_active == True
            )
        )
        result = await self.db.execute(stmt)
        agent_models = result.scalars().all()

        agents = [self._agent_model_to_dataclass(m) for m in agent_models]
        return agents

    async def _execute_sequential(
        self,
        execution_id: UUID,
        subtasks: List[Dict[str, Any]],
        routing_decisions: List[Dict[str, Any]],
        agents: List[Agent]
    ) -> Dict[str, Any]:
        """Execute tasks sequentially (one after another)."""
        results = []

        # Sort by dependencies (topological sort)
        sorted_tasks = self._topological_sort_tasks(subtasks)

        for task in sorted_tasks:
            # Find assigned agent
            routing = next((r for r in routing_decisions if r["task_id"] == task["id"]), None)
            if not routing:
                continue

            agent_id = routing["agent"]
            agent = next((a for a in agents if a.agent_id == agent_id), None)

            # Create task assignment
            assignment = await self._create_task_assignment(
                execution_id=execution_id,
                task=task,
                agent=agent,
                routing_reason=routing["reason"]
            )

            # Execute task (simulated)
            task_result = await self._simulate_task_execution(assignment, agent)

            results.append({
                "task_id": task["id"],
                "agent": agent_id,
                "result": task_result
            })

        return {"mode": "sequential", "results": results}

    async def _execute_concurrent(
        self,
        execution_id: UUID,
        subtasks: List[Dict[str, Any]],
        routing_decisions: List[Dict[str, Any]],
        agents: List[Agent]
    ) -> Dict[str, Any]:
        """Execute tasks concurrently (in parallel)."""
        # Group tasks by dependency level
        levels = self._group_tasks_by_dependency_level(subtasks)

        all_results = []

        # Execute each level concurrently
        for level_tasks in levels:
            tasks_coroutines = []

            for task in level_tasks:
                routing = next((r for r in routing_decisions if r["task_id"] == task["id"]), None)
                if not routing:
                    continue

                agent_id = routing["agent"]
                agent = next((a for a in agents if a.agent_id == agent_id), None)

                # Create assignment and execute
                async def execute_task(t, a, r):
                    assignment = await self._create_task_assignment(
                        execution_id=execution_id,
                        task=t,
                        agent=a,
                        routing_reason=r["reason"]
                    )
                    result = await self._simulate_task_execution(assignment, a)
                    return {"task_id": t["id"], "agent": a.agent_id, "result": result}

                tasks_coroutines.append(execute_task(task, agent, routing))

            # Execute level concurrently
            level_results = await asyncio.gather(*tasks_coroutines)
            all_results.extend(level_results)

        return {"mode": "concurrent", "results": all_results}

    async def _execute_group_chat(
        self,
        execution_id: UUID,
        subtasks: List[Dict[str, Any]],
        routing_decisions: List[Dict[str, Any]],
        agents: List[Agent],
        config: SupervisorConfig
    ) -> Dict[str, Any]:
        """Execute in group chat mode (AutoGen pattern)."""
        conversation_history = []
        max_turns = config.max_conversation_turns or 10

        # Supervisor starts the conversation
        conversation_history.append({
            "turn": 1,
            "speaker": "supervisor",
            "message": f"Let's work on this task: {subtasks[0]['description'] if subtasks else 'No task specified'}",
            "timestamp": datetime.utcnow().isoformat()
        })

        # Simulate multi-agent conversation
        for turn in range(2, max_turns + 1):
            # Pick agent (round robin for demo)
            agent_idx = (turn - 2) % len(agents)
            agent = agents[agent_idx]

            # Agent responds
            message = f"[{agent.name}] I will work on subtask {turn - 1}"

            conversation_history.append({
                "turn": turn,
                "speaker": agent.agent_id,
                "message": message,
                "timestamp": datetime.utcnow().isoformat()
            })

            # Check if task is complete (simplified)
            if turn >= len(subtasks) + 1:
                break

        # Update execution with conversation
        stmt = update(SupervisorExecutionModel).where(
            SupervisorExecutionModel.execution_id == execution_id
        ).values(
            conversation_history=conversation_history,
            total_turns=len(conversation_history)
        )
        await self.db.execute(stmt)
        await self.db.commit()

        return {
            "mode": "group_chat",
            "turns": len(conversation_history),
            "conversation": conversation_history
        }

    async def _execute_handoff(
        self,
        execution_id: UUID,
        subtasks: List[Dict[str, Any]],
        routing_decisions: List[Dict[str, Any]],
        agents: List[Agent]
    ) -> Dict[str, Any]:
        """Execute with dynamic handoffs."""
        # Similar to sequential but allows re-routing
        return await self._execute_sequential(execution_id, subtasks, routing_decisions, agents)

    async def _create_task_assignment(
        self,
        execution_id: UUID,
        task: Dict[str, Any],
        agent: Agent,
        routing_reason: str
    ) -> TaskAssignment:
        """Create task assignment record."""
        assignment_id = uuid4()
        assignment_model = TaskAssignmentModel(
            assignment_id=assignment_id,
            execution_id=execution_id,
            agent_id=agent.agent_id,
            organization_id=agent.organization_id,
            task_id=task["id"],
            task_description=task["description"],
            task_type=task.get("type"),
            priority=task.get("priority", 5),
            status="pending",
            assigned_at=datetime.utcnow(),
            assigned_by="supervisor",
            routing_reason=routing_reason
        )

        self.db.add(assignment_model)
        await self.db.commit()

        return self._assignment_model_to_dataclass(assignment_model)

    async def _simulate_task_execution(
        self,
        assignment: TaskAssignment,
        agent: Agent
    ) -> Dict[str, Any]:
        """Simulate agent executing task."""
        # In production, this would actually execute the agent
        # For demo, simulate execution with delay
        await asyncio.sleep(0.1)

        return {
            "status": "completed",
            "output": f"Task {assignment.task_id} completed by {agent.name}",
            "agent": agent.agent_id
        }

    def _topological_sort_tasks(self, tasks: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Sort tasks by dependencies."""
        # Simple implementation: tasks without dependencies first
        sorted_tasks = []
        remaining = tasks.copy()

        while remaining:
            # Find tasks with no dependencies or satisfied dependencies
            ready = []
            for task in remaining:
                deps = task.get("dependencies", [])
                if not deps or all(d in [t["id"] for t in sorted_tasks] for d in deps):
                    ready.append(task)

            if not ready:
                # Circular dependency or error
                sorted_tasks.extend(remaining)
                break

            sorted_tasks.extend(ready)
            for task in ready:
                remaining.remove(task)

        return sorted_tasks

    def _group_tasks_by_dependency_level(self, tasks: List[Dict[str, Any]]) -> List[List[Dict[str, Any]]]:
        """Group tasks by dependency level for parallel execution."""
        levels = []
        remaining = tasks.copy()
        completed_ids = set()

        while remaining:
            # Find tasks with no dependencies or satisfied dependencies
            current_level = []
            for task in remaining:
                deps = task.get("dependencies", [])
                if not deps or all(d in completed_ids for d in deps):
                    current_level.append(task)

            if not current_level:
                # Circular dependency - just add remaining
                levels.append(remaining)
                break

            levels.append(current_level)
            for task in current_level:
                completed_ids.add(task["id"])
                remaining.remove(task)

        return levels

    def _model_to_dataclass(self, model: SupervisorExecutionModel) -> SupervisorExecution:
        """Convert model to dataclass."""
        return SupervisorExecution(
            execution_id=model.execution_id,
            config_id=model.config_id,
            organization_id=model.organization_id,
            status=model.status,
            mode=SupervisorMode(model.mode),
            input_task=model.input_task,
            workflow_execution_id=model.workflow_execution_id,
            output_result=model.output_result,
            subtasks=model.subtasks or [],
            agent_assignments=model.agent_assignments or {},
            conversation_history=model.conversation_history or [],
            routing_decisions=model.routing_decisions or [],
            total_agents_used=model.total_agents_used,
            total_turns=model.total_turns,
            duration_ms=model.duration_ms,
            total_cost=model.total_cost,
            cost_by_agent=model.cost_by_agent,
            started_at=model.started_at,
            completed_at=model.completed_at,
            error_message=model.error_message
        )

    def _agent_model_to_dataclass(self, model: AgentRegistryModel) -> Agent:
        """Convert agent model to dataclass."""
        from backend.shared.supervisor_models import Agent, AgentRole
        return Agent(
            agent_id=model.agent_id,
            organization_id=model.organization_id,
            name=model.name,
            role=AgentRole(model.role),
            description=model.description,
            capabilities=model.capabilities or [],
            specialization=model.specialization,
            agent_type=model.agent_type,
            llm_model=model.llm_model,
            system_prompt=model.system_prompt,
            tools=model.tools or [],
            max_concurrent_tasks=model.max_concurrent_tasks,
            average_duration_ms=model.average_duration_ms,
            average_cost_per_task=model.average_cost_per_task,
            is_active=model.is_active,
            current_load=model.current_load,
            total_tasks_completed=model.total_tasks_completed,
            total_tasks_failed=model.total_tasks_failed,
            success_rate=model.success_rate
        )

    def _assignment_model_to_dataclass(self, model: TaskAssignmentModel) -> TaskAssignment:
        """Convert assignment model to dataclass."""
        return TaskAssignment(
            assignment_id=model.assignment_id,
            execution_id=model.execution_id,
            agent_id=model.agent_id,
            task_id=model.task_id,
            task_description=model.task_description,
            status=TaskStatus(model.status),
            task_type=model.task_type,
            priority=model.priority,
            input_data=model.input_data,
            output_data=model.output_data,
            depends_on=model.depends_on or [],
            blocks=model.blocks or [],
            assigned_at=model.assigned_at,
            started_at=model.started_at,
            completed_at=model.completed_at,
            duration_ms=model.duration_ms,
            cost=model.cost,
            tokens_used=model.tokens_used,
            retry_count=model.retry_count,
            max_retries=model.max_retries,
            error_message=model.error_message
        )
