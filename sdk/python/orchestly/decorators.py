"""Decorators for easy agent registration and task definition."""

import asyncio
import functools
import inspect
import logging
import signal
from typing import Any, Callable, Dict, List, Optional

from .client import OrchestlyClient, AgentConfig

logger = logging.getLogger(__name__)


def register_agent(
    name: str,
    capabilities: List[str],
    description: Optional[str] = None,
    cost_limit_daily: float = 100.0,
    cost_limit_monthly: float = 3000.0,
    llm_provider: str = "openai",
    llm_model: str = "gpt-4o-mini",
    framework: str = "custom",
    version: str = "1.0.0",
    tags: Optional[List[str]] = None,
    metadata: Optional[Dict[str, Any]] = None,
):
    """
    Decorator to register an agent class with the Orchestly platform.

    Usage:
        @register_agent(
            name="email_classifier",
            capabilities=["email_triage", "sentiment_analysis"],
            cost_limit_daily=100.0
        )
        class EmailAgent:
            @task(timeout=30)
            async def classify(self, email: dict) -> dict:
                # Agent logic here
                pass

    Args:
        name: Unique agent name
        capabilities: List of capabilities this agent provides
        description: Agent description
        cost_limit_daily: Max daily cost in USD
        cost_limit_monthly: Max monthly cost in USD
        llm_provider: LLM provider (openai, anthropic, etc)
        llm_model: Model name
        framework: Framework name (langchain, crewai, custom)
        version: Agent version
        tags: Tags for categorization
        metadata: Additional metadata
    """
    def decorator(cls):
        """Class decorator."""

        # Store config on class
        config = AgentConfig(
            name=name,
            description=description or cls.__doc__,
            capabilities=capabilities,
            cost_limit_daily=cost_limit_daily,
            cost_limit_monthly=cost_limit_monthly,
            llm_provider=llm_provider,
            llm_model=llm_model,
            framework=framework,
            version=version,
            tags=tags or [],
            metadata=metadata or {},
        )

        # Add config to class
        cls._agent_config = config

        # Wrap __init__ to set instance-level state (not class-level)
        original_init = cls.__init__ if hasattr(cls, '__init__') and cls.__init__ is not object.__init__ else None

        def __init__(self_inst, *args, **kwargs):
            self_inst._agent_client = None
            self_inst._registered = False
            self_inst._agent_id = None
            if original_init:
                original_init(self_inst, *args, **kwargs)

        cls.__init__ = __init__

        # Add helper methods to class
        async def _register(self):
            """Register this agent with the platform."""
            if not self._agent_client:
                self._agent_client = OrchestlyClient()

            if not self._registered:
                self._agent_id = await self._agent_client.register_agent(config)
                self._registered = True
                logger.info(f"Agent '{name}' registered with ID: {self._agent_id}")

            return self._agent_id

        async def _run_forever(self):
            """Run agent in polling mode, processing tasks as they arrive."""
            await self._register()

            logger.info(f"Agent '{name}' started. Polling for tasks: {', '.join(capabilities)}")

            # Graceful shutdown via signal handlers
            stop_event = asyncio.Event()
            loop = asyncio.get_running_loop()
            for sig in (signal.SIGINT, signal.SIGTERM):
                try:
                    loop.add_signal_handler(sig, stop_event.set)
                except NotImplementedError:
                    pass  # Windows doesn't support add_signal_handler

            heartbeat_interval = 30  # seconds
            last_heartbeat = loop.time()

            while not stop_event.is_set():
                try:
                    # Send heartbeat periodically
                    current_time = loop.time()
                    if current_time - last_heartbeat >= heartbeat_interval:
                        await self._agent_client.send_heartbeat()
                        last_heartbeat = current_time

                    # Poll for next task
                    task_data = await self._agent_client.get_next_task(capabilities)

                    if task_data:
                        task_id = task_data["task_id"]
                        capability = task_data["capability"]
                        input_data = task_data["input"]

                        logger.info(f"Received task {task_id}: {capability}")

                        # Find method that handles this capability
                        method_name = capability.replace("-", "_")
                        if hasattr(self, method_name):
                            method = getattr(self, method_name)

                            try:
                                # Check the original function, not the @task wrapper
                                original = getattr(method, '_original_func', method)
                                if inspect.iscoroutinefunction(original) or inspect.iscoroutinefunction(method):
                                    result = await method(input_data)
                                else:
                                    result = method(input_data)

                                # Submit result
                                await self._agent_client.submit_result(
                                    task_id=task_id,
                                    output=result if isinstance(result, dict) else {"result": result},
                                )
                                logger.info(f"Task {task_id} completed")

                            except Exception as e:
                                # Submit error
                                await self._agent_client.submit_error(
                                    task_id=task_id,
                                    error=str(e),
                                )
                                logger.error(f"Task {task_id} failed: {e}")
                        else:
                            logger.warning(f"No handler found for capability: {capability}")

                    else:
                        # No tasks available, wait before polling again
                        await asyncio.sleep(2)

                except Exception as e:
                    logger.error(f"Error in agent loop: {e}")
                    await asyncio.sleep(5)  # Wait before retrying

            logger.info(f"Agent '{name}' shutting down...")
            await self._agent_client.close()

        # Attach methods to class
        cls._register = _register
        cls.run_forever = _run_forever

        return cls

    return decorator


def task(
    timeout: int = 300,
    max_retries: int = 3,
    input_schema: Optional[Dict[str, Any]] = None,
    output_schema: Optional[Dict[str, Any]] = None,
):
    """
    Decorator to mark a method as a task handler.

    Usage:
        @task(timeout=60)
        async def classify_email(self, email: dict) -> dict:
            # Task logic
            pass

    Args:
        timeout: Task timeout in seconds
        max_retries: Maximum retry attempts
        input_schema: JSON schema for input validation
        output_schema: JSON schema for output validation
    """
    def decorator(func: Callable) -> Callable:
        """Function decorator."""

        # Store task metadata
        func._is_task = True
        func._task_timeout = timeout
        func._task_max_retries = max_retries
        func._task_input_schema = input_schema
        func._task_output_schema = output_schema

        @functools.wraps(func)
        async def wrapper(*args, **kwargs):
            """Wrapped function with timeout."""
            if inspect.iscoroutinefunction(func):
                # Async function - apply timeout
                try:
                    return await asyncio.wait_for(
                        func(*args, **kwargs),
                        timeout=timeout
                    )
                except asyncio.TimeoutError:
                    raise TimeoutError(f"Task exceeded timeout of {timeout}s")
            else:
                # Sync function - run in executor
                loop = asyncio.get_running_loop()
                return await loop.run_in_executor(
                    None,
                    functools.partial(func, *args, **kwargs)
                )

        # Preserve reference to original function for dispatch logic
        wrapper._original_func = func
        return wrapper

    return decorator
