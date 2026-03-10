"""
Routing Strategies

Strategy pattern implementations for intelligent LLM routing.
"""

import random
from abc import ABC, abstractmethod
from typing import Dict, List, Optional

from backend.router.registry import ModelInfo
from backend.router.monitor import HealthMetrics


class RoutingRequest:
    """Request for model routing."""

    def __init__(
        self,
        min_quality: Optional[float] = None,
        max_cost: Optional[float] = None,
        require_vision: bool = False,
        require_tools: bool = False,
        max_latency_ms: Optional[int] = None,
    ):
        self.min_quality = min_quality or 0.0
        self.max_cost = max_cost
        self.require_vision = require_vision
        self.require_tools = require_tools
        self.max_latency_ms = max_latency_ms


class RoutingStrategy(ABC):
    """Base class for routing strategies."""

    @abstractmethod
    def select(
        self,
        request: RoutingRequest,
        models: List[ModelInfo],
        health: Dict[str, HealthMetrics],
    ) -> Optional[ModelInfo]:
        """
        Select the best model for a request.

        Args:
            request: Routing request with constraints
            models: Available models
            health: Health metrics for each model

        Returns:
            Selected model or None if no suitable model
        """
        pass

    def _filter_eligible(
        self,
        request: RoutingRequest,
        models: List[ModelInfo],
        health: Dict[str, HealthMetrics],
    ) -> List[ModelInfo]:
        """
        Filter models to only eligible ones based on requirements.

        Args:
            request: Routing request
            models: Available models
            health: Health metrics

        Returns:
            List of eligible models
        """
        eligible = []

        for model in models:
            # Check if enabled
            if not model.is_enabled:
                continue

            # Check health
            if model.id in health and not health[model.id].is_healthy:
                continue

            # Check quality requirement
            if model.quality_score < request.min_quality:
                continue

            # Check cost requirement
            if request.max_cost is not None:
                if model.cost_per_1k_input_tokens is None:
                    continue  # Can't verify cost
                if model.cost_per_1k_input_tokens > request.max_cost:
                    continue

            # Check vision requirement
            if request.require_vision and not model.supports_vision:
                continue

            # Check tools requirement
            if request.require_tools and not model.supports_tools:
                continue

            # Check latency requirement
            if request.max_latency_ms is not None and model.id in health:
                metrics = health[model.id]
                if metrics.latency_p95_ms is not None:
                    if metrics.latency_p95_ms > request.max_latency_ms:
                        continue

            eligible.append(model)

        return eligible


class CostOptimizedStrategy(RoutingStrategy):
    """
    Cost-Optimized Strategy.

    Selects the cheapest model that meets quality threshold.
    """

    def select(
        self,
        request: RoutingRequest,
        models: List[ModelInfo],
        health: Dict[str, HealthMetrics],
    ) -> Optional[ModelInfo]:
        """Select cheapest eligible model."""
        eligible = self._filter_eligible(request, models, health)

        if not eligible:
            return None

        # Filter to models with cost data
        with_cost = [m for m in eligible if m.cost_per_1k_input_tokens is not None]

        if not with_cost:
            # Fall back to first eligible if no cost data
            return eligible[0]

        # Return cheapest
        return min(with_cost, key=lambda m: m.cost_per_1k_input_tokens)


class LatencyOptimizedStrategy(RoutingStrategy):
    """
    Latency-Optimized Strategy.

    Selects the fastest model based on recent P50 latency.
    """

    def select(
        self,
        request: RoutingRequest,
        models: List[ModelInfo],
        health: Dict[str, HealthMetrics],
    ) -> Optional[ModelInfo]:
        """Select fastest eligible model."""
        eligible = self._filter_eligible(request, models, health)

        if not eligible:
            return None

        # Filter to models with latency data
        with_latency = [
            m for m in eligible
            if m.id in health and health[m.id].latency_p50_ms is not None
        ]

        if not with_latency:
            # Fall back to first eligible if no latency data
            return eligible[0]

        # Return fastest (lowest P50 latency)
        return min(with_latency, key=lambda m: health[m.id].latency_p50_ms)


class QualityFirstStrategy(RoutingStrategy):
    """
    Quality-First Strategy.

    Selects the highest quality model within budget.
    """

    def select(
        self,
        request: RoutingRequest,
        models: List[ModelInfo],
        health: Dict[str, HealthMetrics],
    ) -> Optional[ModelInfo]:
        """Select highest quality eligible model."""
        eligible = self._filter_eligible(request, models, health)

        if not eligible:
            return None

        # Return highest quality
        return max(eligible, key=lambda m: m.quality_score)


class WeightedRoundRobinStrategy(RoutingStrategy):
    """
    Weighted Round-Robin Strategy.

    Distributes load based on configured weights.
    Useful for A/B testing or gradual rollouts.
    """

    def __init__(self, weights: Optional[Dict[str, float]] = None):
        """
        Initialize weighted round-robin strategy.

        Args:
            weights: Dictionary mapping model_id to weight (default: equal weights)
        """
        self.weights = weights or {}
        self._counters: Dict[str, int] = {}

    def select(
        self,
        request: RoutingRequest,
        models: List[ModelInfo],
        health: Dict[str, HealthMetrics],
    ) -> Optional[ModelInfo]:
        """Select model using weighted round-robin."""
        eligible = self._filter_eligible(request, models, health)

        if not eligible:
            return None

        # Use configured weights or default to 1.0
        model_weights = {
            m.id: self.weights.get(m.id, 1.0)
            for m in eligible
        }

        # Weighted random selection
        total_weight = sum(model_weights.values())
        if total_weight == 0:
            return eligible[0]

        # Generate random value and select based on weight
        r = random.uniform(0, total_weight)
        cumulative = 0

        for model in eligible:
            cumulative += model_weights[model.id]
            if r <= cumulative:
                return model

        # Fallback (shouldn't happen)
        return eligible[-1]


class RoundRobinStrategy(RoutingStrategy):
    """
    Simple Round-Robin Strategy.

    Distributes load evenly across all eligible models.
    """

    def __init__(self):
        """Initialize round-robin strategy."""
        self._index = 0

    def select(
        self,
        request: RoutingRequest,
        models: List[ModelInfo],
        health: Dict[str, HealthMetrics],
    ) -> Optional[ModelInfo]:
        """Select model using round-robin."""
        eligible = self._filter_eligible(request, models, health)

        if not eligible:
            return None

        # Simple round-robin
        selected = eligible[self._index % len(eligible)]
        self._index += 1

        return selected


class BalancedStrategy(RoutingStrategy):
    """
    Balanced Strategy.

    Balances cost, latency, and quality with configurable weights.
    """

    def __init__(
        self,
        cost_weight: float = 0.33,
        latency_weight: float = 0.33,
        quality_weight: float = 0.34,
    ):
        """
        Initialize balanced strategy.

        Args:
            cost_weight: Weight for cost optimization (0-1)
            latency_weight: Weight for latency optimization (0-1)
            quality_weight: Weight for quality optimization (0-1)
        """
        total = cost_weight + latency_weight + quality_weight
        self.cost_weight = cost_weight / total
        self.latency_weight = latency_weight / total
        self.quality_weight = quality_weight / total

    def select(
        self,
        request: RoutingRequest,
        models: List[ModelInfo],
        health: Dict[str, HealthMetrics],
    ) -> Optional[ModelInfo]:
        """Select model using balanced scoring."""
        eligible = self._filter_eligible(request, models, health)

        if not eligible:
            return None

        # Calculate normalized scores for each dimension
        scores = []

        for model in eligible:
            # Cost score (lower is better, normalize to 0-1)
            cost_score = 0.0
            if model.cost_per_1k_input_tokens is not None:
                max_cost = max(
                    m.cost_per_1k_input_tokens
                    for m in eligible
                    if m.cost_per_1k_input_tokens is not None
                )
                if max_cost > 0:
                    # Invert: lower cost = higher score
                    cost_score = 1 - (model.cost_per_1k_input_tokens / max_cost)

            # Latency score (lower is better, normalize to 0-1)
            latency_score = 0.0
            if model.id in health and health[model.id].latency_p50_ms is not None:
                latencies = [
                    health[m.id].latency_p50_ms
                    for m in eligible
                    if m.id in health and health[m.id].latency_p50_ms is not None
                ]
                if latencies:
                    max_latency = max(latencies)
                    if max_latency > 0:
                        # Invert: lower latency = higher score
                        latency_score = 1 - (health[model.id].latency_p50_ms / max_latency)

            # Quality score (higher is better, already 0-1)
            quality_score = model.quality_score

            # Weighted combination
            total_score = (
                cost_score * self.cost_weight +
                latency_score * self.latency_weight +
                quality_score * self.quality_weight
            )

            scores.append((model, total_score))

        # Return model with highest score
        return max(scores, key=lambda x: x[1])[0]


# Strategy registry
STRATEGIES = {
    "cost": CostOptimizedStrategy,
    "latency": LatencyOptimizedStrategy,
    "quality": QualityFirstStrategy,
    "weighted_rr": WeightedRoundRobinStrategy,
    "round_robin": RoundRobinStrategy,
    "balanced": BalancedStrategy,
}


def get_strategy(strategy_type: str, config: Optional[Dict] = None) -> RoutingStrategy:
    """
    Get a routing strategy instance.

    Args:
        strategy_type: Strategy type name
        config: Optional configuration for the strategy

    Returns:
        RoutingStrategy instance

    Raises:
        ValueError: If strategy type is unknown
    """
    if strategy_type not in STRATEGIES:
        raise ValueError(f"Unknown strategy type: {strategy_type}")

    strategy_class = STRATEGIES[strategy_type]

    # Instantiate with config if supported
    if config and strategy_type in ["weighted_rr", "balanced"]:
        return strategy_class(**config)
    else:
        return strategy_class()
