"""
BYOC Workflow Executor

Executes workflow definitions using configured LLM providers.
Supports the same workflow format as the hosted platform.
"""

import asyncio
import logging
from typing import Dict, Any, List, Optional, Tuple
from datetime import datetime

import httpx

from .models import LLMProviderConfig

logger = logging.getLogger(__name__)


class WorkflowExecutor:
    """
    Executes workflow definitions on BYOC infrastructure.

    Uses customer-provided LLM API keys (BYOK) for LLM calls.
    """

    def __init__(self, llm_providers: List[LLMProviderConfig]):
        self.llm_providers = {p.provider: p for p in llm_providers}
        self.total_tokens = 0
        self.total_cost = 0.0

    async def execute(
        self,
        workflow_definition: Dict[str, Any],
        input_data: Optional[Dict[str, Any]] = None,
        context: Optional[Dict[str, Any]] = None,
        timeout_seconds: int = 3600,
    ) -> Tuple[Dict[str, Any], List[Dict[str, Any]]]:
        """
        Execute a workflow definition.

        Returns:
            Tuple of (output_data, step_results)
        """
        self.total_tokens = 0
        self.total_cost = 0.0

        # Parse workflow
        nodes = workflow_definition.get("nodes", [])
        edges = workflow_definition.get("edges", [])

        # Build execution graph
        node_map = {n["id"]: n for n in nodes}
        dependencies = self._build_dependencies(edges)

        # Execute nodes in order
        step_results = []
        node_outputs: Dict[str, Any] = {}

        # Start with input data
        if input_data:
            node_outputs["input"] = input_data

        # Execute with timeout
        try:
            async with asyncio.timeout(timeout_seconds):
                # Get execution order (topological sort)
                execution_order = self._topological_sort(nodes, dependencies)

                for node_id in execution_order:
                    node = node_map[node_id]
                    node_type = node.get("type", "")

                    # Gather inputs from dependencies
                    node_inputs = self._gather_inputs(node_id, dependencies, node_outputs, edges)

                    # Execute node
                    started_at = datetime.utcnow()
                    try:
                        output = await self._execute_node(node, node_inputs, context)
                        status = "completed"
                        error = None
                    except Exception as e:
                        output = None
                        status = "failed"
                        error = str(e)
                        logger.error(f"Node {node_id} failed: {e}")

                    completed_at = datetime.utcnow()

                    # Store output
                    node_outputs[node_id] = output

                    # Record step result
                    step_results.append({
                        "node_id": node_id,
                        "node_type": node_type,
                        "status": status,
                        "output": output,
                        "error": error,
                        "started_at": started_at.isoformat(),
                        "completed_at": completed_at.isoformat(),
                        "duration_seconds": (completed_at - started_at).total_seconds(),
                    })

                    if status == "failed":
                        # Stop execution on failure (could be configurable)
                        break

        except asyncio.TimeoutError:
            raise

        # Find output node
        output_data = self._get_final_output(nodes, node_outputs)

        return output_data, step_results

    async def _execute_node(
        self,
        node: Dict[str, Any],
        inputs: Dict[str, Any],
        context: Optional[Dict[str, Any]],
    ) -> Any:
        """Execute a single node."""
        node_type = node.get("type", "")
        node_data = node.get("data", {})

        if node_type == "llm" or node_type == "agent_llm":
            return await self._execute_llm_node(node_data, inputs, context)
        elif node_type == "transform":
            return self._execute_transform_node(node_data, inputs)
        elif node_type == "condition":
            return self._execute_condition_node(node_data, inputs)
        elif node_type == "data_input":
            return inputs.get("input", node_data.get("default_value"))
        elif node_type == "data_output":
            return inputs
        else:
            logger.warning(f"Unknown node type: {node_type}")
            return inputs

    async def _execute_llm_node(
        self,
        node_data: Dict[str, Any],
        inputs: Dict[str, Any],
        context: Optional[Dict[str, Any]],
    ) -> Dict[str, Any]:
        """Execute an LLM node."""
        provider = node_data.get("provider", "openai")
        model = node_data.get("model", "gpt-4")
        prompt_template = node_data.get("prompt", "")
        system_prompt = node_data.get("system_prompt", "")
        temperature = node_data.get("temperature", 0.7)
        max_tokens = node_data.get("max_tokens", 1000)

        # Get provider config
        provider_config = self.llm_providers.get(provider)
        if not provider_config:
            raise ValueError(f"LLM provider not configured: {provider}")

        # Format prompt with inputs
        prompt = self._format_template(prompt_template, inputs)

        # Make LLM call
        if provider == "openai":
            return await self._call_openai(
                provider_config,
                model,
                prompt,
                system_prompt,
                temperature,
                max_tokens,
            )
        elif provider == "anthropic":
            return await self._call_anthropic(
                provider_config,
                model,
                prompt,
                system_prompt,
                temperature,
                max_tokens,
            )
        else:
            raise ValueError(f"Unsupported LLM provider: {provider}")

    async def _call_openai(
        self,
        config: LLMProviderConfig,
        model: str,
        prompt: str,
        system_prompt: str,
        temperature: float,
        max_tokens: int,
    ) -> Dict[str, Any]:
        """Call OpenAI API."""
        messages = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        messages.append({"role": "user", "content": prompt})

        base_url = config.base_url or "https://api.openai.com/v1"

        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"{base_url}/chat/completions",
                headers={
                    "Authorization": f"Bearer {config.api_key}",
                    "Content-Type": "application/json",
                },
                json={
                    "model": config.model or model,
                    "messages": messages,
                    "temperature": temperature,
                    "max_tokens": max_tokens,
                },
                timeout=120.0,
            )

            if response.status_code != 200:
                raise Exception(f"OpenAI API error: {response.text}")

            data = response.json()

            # Track usage
            usage = data.get("usage", {})
            self.total_tokens += usage.get("total_tokens", 0)
            # Approximate cost (varies by model)
            self.total_cost += usage.get("total_tokens", 0) * 0.00003

            return {
                "content": data["choices"][0]["message"]["content"],
                "model": data.get("model"),
                "usage": usage,
            }

    async def _call_anthropic(
        self,
        config: LLMProviderConfig,
        model: str,
        prompt: str,
        system_prompt: str,
        temperature: float,
        max_tokens: int,
    ) -> Dict[str, Any]:
        """Call Anthropic API."""
        base_url = config.base_url or "https://api.anthropic.com"

        async with httpx.AsyncClient() as client:
            body = {
                "model": config.model or model,
                "messages": [{"role": "user", "content": prompt}],
                "max_tokens": max_tokens,
                "temperature": temperature,
            }

            if system_prompt:
                body["system"] = system_prompt

            response = await client.post(
                f"{base_url}/v1/messages",
                headers={
                    "x-api-key": config.api_key,
                    "anthropic-version": "2023-06-01",
                    "Content-Type": "application/json",
                },
                json=body,
                timeout=120.0,
            )

            if response.status_code != 200:
                raise Exception(f"Anthropic API error: {response.text}")

            data = response.json()

            # Track usage
            usage = data.get("usage", {})
            input_tokens = usage.get("input_tokens", 0)
            output_tokens = usage.get("output_tokens", 0)
            self.total_tokens += input_tokens + output_tokens
            # Approximate cost
            self.total_cost += input_tokens * 0.00001 + output_tokens * 0.00003

            return {
                "content": data["content"][0]["text"],
                "model": data.get("model"),
                "usage": usage,
            }

    def _execute_transform_node(
        self,
        node_data: Dict[str, Any],
        inputs: Dict[str, Any],
    ) -> Any:
        """Execute a transform node."""
        transform_type = node_data.get("transform_type", "passthrough")

        if transform_type == "passthrough":
            return inputs
        elif transform_type == "extract":
            key = node_data.get("key", "")
            return inputs.get(key)
        elif transform_type == "combine":
            return inputs
        elif transform_type == "template":
            template = node_data.get("template", "")
            return self._format_template(template, inputs)
        else:
            return inputs

    def _execute_condition_node(
        self,
        node_data: Dict[str, Any],
        inputs: Dict[str, Any],
    ) -> Dict[str, Any]:
        """Execute a condition node."""
        condition = node_data.get("condition", "")
        # Simple condition evaluation (production would use proper expression parser)
        # For now, just return inputs with condition result
        return {
            "result": True,  # Simplified
            "inputs": inputs,
        }

    def _format_template(self, template: str, data: Dict[str, Any]) -> str:
        """Format a template string with data."""
        result = template
        for key, value in data.items():
            if isinstance(value, dict) and "content" in value:
                value = value["content"]
            result = result.replace(f"{{{{{key}}}}}", str(value))
            result = result.replace(f"${{{key}}}", str(value))
        return result

    def _build_dependencies(
        self,
        edges: List[Dict[str, Any]],
    ) -> Dict[str, List[str]]:
        """Build dependency graph from edges."""
        dependencies: Dict[str, List[str]] = {}
        for edge in edges:
            target = edge.get("target")
            source = edge.get("source")
            if target not in dependencies:
                dependencies[target] = []
            dependencies[target].append(source)
        return dependencies

    def _topological_sort(
        self,
        nodes: List[Dict[str, Any]],
        dependencies: Dict[str, List[str]],
    ) -> List[str]:
        """Topological sort of nodes."""
        # Simple implementation
        result = []
        visited = set()
        node_ids = [n["id"] for n in nodes]

        def visit(node_id: str):
            if node_id in visited:
                return
            visited.add(node_id)
            for dep in dependencies.get(node_id, []):
                visit(dep)
            result.append(node_id)

        for node_id in node_ids:
            visit(node_id)

        return result

    def _gather_inputs(
        self,
        node_id: str,
        dependencies: Dict[str, List[str]],
        node_outputs: Dict[str, Any],
        edges: List[Dict[str, Any]],
    ) -> Dict[str, Any]:
        """Gather inputs for a node from its dependencies."""
        inputs = {}
        for dep_id in dependencies.get(node_id, []):
            output = node_outputs.get(dep_id)
            if output is not None:
                # Find the edge to get handle names
                for edge in edges:
                    if edge.get("source") == dep_id and edge.get("target") == node_id:
                        source_handle = edge.get("sourceHandle", "output")
                        target_handle = edge.get("targetHandle", "input")
                        inputs[target_handle] = output
                        break
                else:
                    inputs[dep_id] = output
        return inputs

    def _get_final_output(
        self,
        nodes: List[Dict[str, Any]],
        node_outputs: Dict[str, Any],
    ) -> Dict[str, Any]:
        """Get the final output from output nodes."""
        output = {}
        for node in nodes:
            if node.get("type") == "data_output":
                node_id = node["id"]
                if node_id in node_outputs:
                    label = node.get("data", {}).get("label", node_id)
                    output[label] = node_outputs[node_id]

        # If no output nodes, return last node output
        if not output and node_outputs:
            last_key = list(node_outputs.keys())[-1]
            output["result"] = node_outputs[last_key]

        return output
