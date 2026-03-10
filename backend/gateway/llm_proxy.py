"""
LLM Gateway V2 - Using Core LLM Module

Proxy for all LLM API calls with cost tracking and enforcement using core/llm.
"""
import sys
import os

# Add project root to path so we can import core modules
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../../../..")))

import time
import json
import logging
from datetime import datetime
from typing import Any, Dict, List, Optional
from uuid import UUID, uuid4

from core.llm import get_llm_client_compat, LLMClientCompat
from core.llm.async_providers import create_async_provider, AsyncLLMResponse
from core.monitoring import get_metrics_manager

from backend.shared.models import LLMResponse
from backend.shared.config import get_settings

logger = logging.getLogger(__name__)


# ============================================================================
# Redis-Backed Cache with In-Memory Fallback
# ============================================================================

class AgentCostCache:
    """
    Cache for agent cost tracking with Redis support and in-memory fallback.

    Uses Redis when available for horizontal scaling, falls back to in-memory
    for single-instance deployments or when Redis is unavailable.
    """

    def __init__(self):
        self._redis_client = None
        self._local_cache: Dict[str, float] = {}
        self._local_limits: Dict[str, float] = {}
        self._cache_prefix = "agent_cost:"
        self._limit_prefix = "agent_limit:"
        self._ttl = 86400  # 24 hours
        self._init_redis()

    def _init_redis(self):
        """Initialize Redis connection if available."""
        try:
            import redis.asyncio as redis
            settings = get_settings()
            redis_url = getattr(settings, 'REDIS_URL', None) or os.environ.get('REDIS_URL')
            if redis_url:
                self._redis_client = redis.from_url(redis_url, decode_responses=True)
                logger.info("Redis cache initialized for agent cost tracking")
            else:
                logger.info("No REDIS_URL configured, using in-memory cache")
        except ImportError:
            logger.info("redis package not installed, using in-memory cache")
        except Exception as e:
            logger.warning(f"Failed to initialize Redis: {e}, using in-memory cache")

    async def get_cost(self, agent_id: UUID) -> float:
        """Get current cost for agent."""
        key = str(agent_id)

        if self._redis_client:
            try:
                value = await self._redis_client.get(f"{self._cache_prefix}{key}")
                return float(value) if value else 0.0
            except Exception as e:
                logger.warning(f"Redis get failed: {e}, falling back to local")

        return self._local_cache.get(key, 0.0)

    async def add_cost(self, agent_id: UUID, amount: float) -> float:
        """Add cost to agent's total and return new total."""
        key = str(agent_id)

        if self._redis_client:
            try:
                # Use INCRBYFLOAT for atomic increment
                new_total = await self._redis_client.incrbyfloat(
                    f"{self._cache_prefix}{key}",
                    amount
                )
                await self._redis_client.expire(f"{self._cache_prefix}{key}", self._ttl)
                return float(new_total)
            except Exception as e:
                logger.warning(f"Redis incr failed: {e}, falling back to local")

        # Local fallback
        current = self._local_cache.get(key, 0.0)
        new_total = current + amount
        self._local_cache[key] = new_total
        return new_total

    async def set_limit(self, agent_id: UUID, limit: float):
        """Set cost limit for agent."""
        key = str(agent_id)

        if self._redis_client:
            try:
                await self._redis_client.set(
                    f"{self._limit_prefix}{key}",
                    str(limit),
                    ex=self._ttl
                )
                return
            except Exception as e:
                logger.warning(f"Redis set failed: {e}, falling back to local")

        self._local_limits[key] = limit

    async def get_limit(self, agent_id: UUID) -> Optional[float]:
        """Get cost limit for agent."""
        key = str(agent_id)

        if self._redis_client:
            try:
                value = await self._redis_client.get(f"{self._limit_prefix}{key}")
                return float(value) if value else None
            except Exception as e:
                logger.warning(f"Redis get failed: {e}, falling back to local")

        return self._local_limits.get(key)

    async def reset_costs(self, agent_id: Optional[UUID] = None):
        """Reset costs for agent or all agents."""
        if agent_id:
            key = str(agent_id)
            if self._redis_client:
                try:
                    await self._redis_client.delete(f"{self._cache_prefix}{key}")
                    return
                except Exception:
                    pass
            self._local_cache.pop(key, None)
        else:
            if self._redis_client:
                try:
                    # Get all cost keys and delete
                    keys = []
                    async for key in self._redis_client.scan_iter(f"{self._cache_prefix}*"):
                        keys.append(key)
                    if keys:
                        await self._redis_client.delete(*keys)
                    return
                except Exception:
                    pass
            self._local_cache.clear()


# Global cache instance
_agent_cost_cache: Optional[AgentCostCache] = None


def get_agent_cost_cache() -> AgentCostCache:
    """Get or create global agent cost cache."""
    global _agent_cost_cache
    if _agent_cost_cache is None:
        _agent_cost_cache = AgentCostCache()
    return _agent_cost_cache


# ============================================================================
# LLM Gateway V2
# ============================================================================

class LLMGateway:
    """
    Gateway for proxying LLM API calls using core/llm module.

    Features:
    - Cost tracking per agent (Redis-backed with in-memory fallback)
    - Cost limit enforcement
    - Request/response logging
    - Unified LLM routing
    - Monitoring integration
    """

    def __init__(self):
        """Initialize LLM gateway."""
        self.settings = get_settings()

        # Log available API keys (masked for security)
        groq_key = self.settings.GROQ_API_KEY
        openai_key = self.settings.OPENAI_API_KEY
        anthropic_key = self.settings.ANTHROPIC_API_KEY
        logger.info(f"LLM Gateway initialized with API keys: "
                    f"GROQ={'***' + groq_key[-4:] if groq_key else 'NOT SET'}, "
                    f"OPENAI={'***' + openai_key[-4:] if openai_key else 'NOT SET'}, "
                    f"ANTHROPIC={'***' + anthropic_key[-4:] if anthropic_key else 'NOT SET'}")

        # Use core LLM compatibility client
        self.llm_client: LLMClientCompat = get_llm_client_compat()

        # Use core metrics
        self.metrics = get_metrics_manager()

        # Use Redis-backed cost cache
        self._cost_cache = get_agent_cost_cache()

        # In-memory fallbacks for cost tracking (used when Redis is unavailable)
        # Note: These are kept for compatibility but _cost_cache is preferred
        self.agent_costs: Dict[UUID, float] = {}
        self.agent_cost_limits: Dict[UUID, float] = {}

    def set_agent_cost_limit(self, agent_id: UUID, limit: float):
        """Set daily cost limit for an agent."""
        import asyncio
        asyncio.create_task(self._cost_cache.set_limit(agent_id, limit))

    def get_agent_cost_today(self, agent_id: UUID) -> float:
        """Get total cost for agent today."""
        import asyncio
        try:
            loop = asyncio.get_event_loop()
            if loop.is_running():
                # Can't await in sync context, return cached value
                return self._cost_cache._local_cache.get(str(agent_id), 0.0)
            return loop.run_until_complete(self._cost_cache.get_cost(agent_id))
        except Exception:
            return self._cost_cache._local_cache.get(str(agent_id), 0.0)

    def _extract_prompts_from_messages(
        self,
        messages: List[Dict[str, str]]
    ) -> tuple[str, str]:
        """
        Extract system and user prompts from chat messages.

        Args:
            messages: List of message dicts with 'role' and 'content'

        Returns:
            Tuple of (system_prompt, user_prompt)
        """
        system_prompt = ""
        user_prompt = ""

        for msg in messages:
            role = msg.get("role", "")
            content = msg.get("content", "")

            if role == "system":
                system_prompt = content
            elif role == "user":
                # Take the last user message as the prompt
                user_prompt = content
            elif role == "assistant":
                # For multi-turn, we'd need to handle this differently
                # For now, append assistant context to user prompt
                if user_prompt:
                    user_prompt = f"Previous response: {content}\n\nUser: {user_prompt}"

        return system_prompt, user_prompt

    async def proxy_request(
        self,
        agent_id: UUID,
        provider: str,
        model: str,
        messages: List[Dict[str, str]],
        temperature: float = 0.7,
        max_tokens: Optional[int] = None,
        task_id: Optional[UUID] = None,
    ) -> LLMResponse:
        """
        Proxy an LLM API request with cost tracking.

        Args:
            agent_id: Agent making the request
            provider: LLM provider ("openai" or "anthropic")
            model: Model name
            messages: Chat messages
            temperature: Sampling temperature
            max_tokens: Max completion tokens
            task_id: Optional task ID for tracking

        Returns:
            LLMResponse with completion and metadata

        Raises:
            ValueError: If cost limit exceeded
            RuntimeError: If request fails
        """
        start_time = time.time()
        request_id = uuid4()

        # Check cost limit - use async cache with in-memory fallback
        current_cost = await self._cost_cache.get_cost(agent_id)
        cost_limit = await self._cost_cache.get_limit(agent_id)
        if cost_limit is None:
            cost_limit = self.agent_cost_limits.get(agent_id, float('inf'))

        if current_cost >= cost_limit:
            raise ValueError(
                f"Agent {agent_id} has exceeded daily cost limit "
                f"(${current_cost:.4f} >= ${cost_limit:.2f})"
            )

        try:
            # Extract system and user prompts from messages
            system_prompt, user_prompt = self._extract_prompts_from_messages(messages)

            # Map provider names to standard names
            provider_map = {
                "groq": "groq",
                "openai": "openai",
                "anthropic": "claude",
                "claude": "claude",
            }
            normalized_provider = provider_map.get(provider.lower(), provider.lower())

            # Get API key from settings based on provider, with env fallback
            api_key = None
            if normalized_provider == "groq":
                api_key = self.settings.GROQ_API_KEY or os.environ.get("GROQ_API_KEY")
            elif normalized_provider == "openai":
                api_key = self.settings.OPENAI_API_KEY or os.environ.get("OPENAI_API_KEY")
            elif normalized_provider == "claude":
                api_key = self.settings.ANTHROPIC_API_KEY or os.environ.get("ANTHROPIC_API_KEY")

            logger.info(f"Creating {normalized_provider} provider with model={model}, "
                        f"api_key={'SET' if api_key else 'NOT SET'}, "
                        f"settings_key={'SET' if getattr(self.settings, f'{normalized_provider.upper()}_API_KEY', None) else 'NOT SET'}")

            if not api_key:
                # Log more details for debugging
                logger.error(f"API key not found for {normalized_provider}. "
                            f"Settings DEBUG={self.settings.DEBUG}, "
                            f"env GROQ_API_KEY={'SET' if os.environ.get('GROQ_API_KEY') else 'NOT SET'}")
                raise ValueError(f"API key not configured for provider: {normalized_provider}. "
                               f"Set {normalized_provider.upper()}_API_KEY in .env or environment.")

            # Create async provider and make request directly
            # This properly supports groq, openai, and claude
            try:
                llm_provider = create_async_provider(
                    provider_name=normalized_provider,
                    model=model,
                    max_tokens=max_tokens or 1000,
                    temperature=temperature,
                    api_key=api_key,  # Pass API key from settings
                )

                async_response: AsyncLLMResponse = await llm_provider.complete(
                    prompt=user_prompt,
                    system_prompt=system_prompt,
                    temperature=temperature,
                    max_tokens=max_tokens or 1000,
                )

                # Extract response data from async response
                content = async_response.content
                tokens_used = async_response.input_tokens + async_response.output_tokens
                cost = async_response.cost or 0.0
                finish_reason = async_response.finish_reason
                latency_ms = int(async_response.latency_ms)
                prompt_tokens = async_response.input_tokens
                completion_tokens = async_response.output_tokens

            except ValueError as provider_error:
                # Fallback to compat layer for unsupported providers
                logger.warning(f"Provider {provider} not directly supported, using compat layer: {provider_error}")
                response = await self.llm_client.generate(
                    system=system_prompt,
                    user=user_prompt,
                    model=model,
                    temperature=temperature,
                    max_tokens=max_tokens or 1000,
                )

                # Calculate latency
                latency_ms = int((time.time() - start_time) * 1000)

                # Extract response data
                content = response.get('content', '')
                tokens_used = response.get('tokens_used', 0)
                cost = response.get('cost', 0.0)
                finish_reason = response.get('finish_reason', 'stop')

                # Estimate token split (rough approximation)
                prompt_tokens = int(tokens_used * 0.3)  # ~30% input
                completion_tokens = tokens_used - prompt_tokens

            # Update cost tracking (Redis-backed with fallback)
            await self._cost_cache.add_cost(agent_id, cost)

            # Track metrics using core/monitoring
            self.metrics.track_llm_request(
                service="agent-orchestration",
                provider=provider,
                model=model,
                duration=latency_ms / 1000.0,
                input_tokens=prompt_tokens,
                output_tokens=completion_tokens,
                cost=cost
            )

            # Build response
            return LLMResponse(
                request_id=request_id,
                content=content,
                finish_reason=finish_reason,
                prompt_tokens=prompt_tokens,
                completion_tokens=completion_tokens,
                total_tokens=tokens_used,
                estimated_cost=cost,
                latency_ms=latency_ms,
            )

        except Exception as e:
            # Track error
            latency_ms = int((time.time() - start_time) * 1000)

            # Log error with full details
            import traceback
            logger.error(f"LLM request failed for agent {agent_id}: {e}")
            logger.error(f"Provider: {provider}, Model: {model}")
            logger.error(f"Traceback: {traceback.format_exc()}")

            raise RuntimeError(f"LLM request failed: {e}")

    async def embed(
        self,
        text: str,
        agent_id: UUID,
        provider: str = "openai",
        model: str = "text-embedding-3-small",
    ) -> List[float]:
        """
        Generate embedding for text.

        Args:
            text: Text to embed
            agent_id: Agent requesting embedding
            provider: LLM provider (currently only openai supported)
            model: Embedding model

        Returns:
            Embedding vector
        """
        try:
            # Use core/llm for embeddings
            embedding = await self.llm_client.embed(text=text, model=model)

            # Track cost (embeddings are cheap)
            cost = len(text) / 1000 * 0.00002  # Approximate
            if agent_id not in self.agent_costs:
                self.agent_costs[agent_id] = 0.0
            self.agent_costs[agent_id] += cost

            return embedding

        except Exception as e:
            raise RuntimeError(f"Embedding failed: {e}")

    async def batch_embed(
        self,
        texts: List[str],
        agent_id: UUID,
        provider: str = "openai",
        model: str = "text-embedding-3-small",
    ) -> List[List[float]]:
        """
        Generate embeddings for multiple texts.

        Args:
            texts: List of texts to embed
            agent_id: Agent requesting embeddings
            provider: LLM provider
            model: Embedding model

        Returns:
            List of embedding vectors
        """
        try:
            embeddings = await self.llm_client.batch_embed(texts=texts, model=model)

            # Track cost
            total_chars = sum(len(t) for t in texts)
            cost = total_chars / 1000 * 0.00002
            if agent_id not in self.agent_costs:
                self.agent_costs[agent_id] = 0.0
            self.agent_costs[agent_id] += cost

            return embeddings

        except Exception as e:
            raise RuntimeError(f"Batch embedding failed: {e}")

    def reset_daily_costs(self):
        """Reset daily cost tracking (call at midnight)."""
        self.agent_costs.clear()


# Singleton instance
_gateway: Optional[LLMGateway] = None


def get_gateway() -> LLMGateway:
    """Get or create the LLM gateway singleton."""
    global _gateway
    if _gateway is None:
        _gateway = LLMGateway()
    return _gateway
