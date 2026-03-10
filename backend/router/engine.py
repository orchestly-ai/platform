"""
Routing Engine

Main orchestrator for intelligent LLM routing.
"""

import json
from typing import Dict, List, Optional
from uuid import uuid4

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.database.models import RoutingStrategyModel, StrategyModelWeightModel
from backend.router.registry import ModelRegistry, get_model_registry
from backend.router.monitor import HealthMonitor, get_health_monitor
from backend.router.strategies import (
    RoutingRequest,
    RoutingStrategy,
    get_strategy,
)


class RoutingDecision:
    """Result of a routing decision."""

    def __init__(
        self,
        model_id: str,
        provider: str,
        model_name: str,
        strategy_used: str,
        fallback_used: bool = False,
    ):
        self.model_id = model_id
        self.provider = provider
        self.model_name = model_name
        self.strategy_used = strategy_used
        self.fallback_used = fallback_used

    def to_dict(self) -> Dict:
        """Convert to dictionary."""
        return {
            "model_id": self.model_id,
            "provider": self.provider,
            "model_name": self.model_name,
            "strategy_used": self.strategy_used,
            "fallback_used": self.fallback_used,
        }


class RoutingEngine:
    """
    Main routing engine.

    Coordinates model selection using strategies, health monitoring, and registry.
    """

    def __init__(
        self,
        db: AsyncSession,
        registry: Optional[ModelRegistry] = None,
        monitor: Optional[HealthMonitor] = None,
    ):
        """Initialize routing engine."""
        self.db = db
        self.registry = registry or get_model_registry(db)
        self.monitor = monitor or get_health_monitor(db)

    async def route(
        self,
        organization_id: str,
        request: RoutingRequest,
        scope_type: str = "organization",
        scope_id: Optional[str] = None,
    ) -> Optional[RoutingDecision]:
        """
        Route a request to the best model.

        Args:
            organization_id: Organization ID
            request: Routing request with constraints
            scope_type: Scope type ('organization', 'workflow', 'agent')
            scope_id: Scope ID (for workflow or agent level)

        Returns:
            RoutingDecision or None if no suitable model
        """
        # Get active strategy for scope
        strategy_config = await self._get_strategy_for_scope(
            organization_id, scope_type, scope_id
        )

        if not strategy_config:
            # Fall back to organization-level strategy
            if scope_type != "organization":
                strategy_config = await self._get_strategy_for_scope(
                    organization_id, "organization", None
                )

        if not strategy_config:
            # No strategy configured, use cost-optimized by default
            strategy_config = {
                "strategy_type": "cost",
                "config": {},
            }

        # Get strategy instance
        strategy = get_strategy(
            strategy_config["strategy_type"],
            strategy_config.get("config"),
        )

        # Get available models
        models = await self.registry.list_models(organization_id, enabled_only=True)

        if not models:
            return None

        # Get health metrics
        model_ids = [m.id for m in models]
        health = self.monitor.get_all_health(model_ids)

        # Select model using strategy
        selected_model = strategy.select(request, models, health)

        if not selected_model:
            # Try fallback strategy if configured
            if "fallback_strategy_id" in strategy_config:
                fallback_id = strategy_config["fallback_strategy_id"]
                fallback_config = await self._get_strategy_by_id(fallback_id)

                if fallback_config:
                    fallback_strategy = get_strategy(
                        fallback_config["strategy_type"],
                        fallback_config.get("config"),
                    )
                    selected_model = fallback_strategy.select(request, models, health)

                    if selected_model:
                        return RoutingDecision(
                            model_id=selected_model.id,
                            provider=selected_model.provider,
                            model_name=selected_model.model_name,
                            strategy_used=fallback_config["strategy_type"],
                            fallback_used=True,
                        )

            return None

        return RoutingDecision(
            model_id=selected_model.id,
            provider=selected_model.provider,
            model_name=selected_model.model_name,
            strategy_used=strategy_config["strategy_type"],
            fallback_used=False,
        )

    async def _get_strategy_for_scope(
        self,
        organization_id: str,
        scope_type: str,
        scope_id: Optional[str],
    ) -> Optional[Dict]:
        """Get active strategy configuration for a scope."""
        stmt = select(RoutingStrategyModel).where(
            RoutingStrategyModel.organization_id == organization_id,
            RoutingStrategyModel.scope_type == scope_type,
            RoutingStrategyModel.is_active == True,
        )

        if scope_id:
            stmt = stmt.where(RoutingStrategyModel.scope_id == scope_id)
        else:
            stmt = stmt.where(RoutingStrategyModel.scope_id.is_(None))

        result = await self.db.execute(stmt)
        strategy = result.scalar_one_or_none()

        if not strategy:
            return None

        config = {}
        if strategy.config:
            try:
                config = json.loads(strategy.config)
            except:
                config = {}

        # Get model weights if weighted strategy
        if strategy.strategy_type == "weighted_rr":
            weights = await self.db.execute(select(StrategyModelWeightModel).where(
                StrategyModelWeightModel.strategy_id == strategy.id,
                StrategyModelWeightModel.is_enabled == True,
            )).scalars().all()

            config["weights"] = {
                w.model_id: w.weight
                for w in weights
            }

        return {
            "id": strategy.id,
            "strategy_type": strategy.strategy_type,
            "config": config,
            "fallback_strategy_id": strategy.fallback_strategy_id,
        }

    async def _get_strategy_by_id(self, strategy_id: str) -> Optional[Dict]:
        """Get strategy configuration by ID."""
        strategy = await self.db.execute(select(RoutingStrategyModel).where(
            RoutingStrategyModel.id == strategy_id
        )).scalar_one_or_none()

        if not strategy:
            return None

        config = {}
        if strategy.config:
            try:
                config = json.loads(strategy.config)
            except:
                config = {}

        return {
            "id": strategy.id,
            "strategy_type": strategy.strategy_type,
            "config": config,
        }

    async def create_strategy(
        self,
        organization_id: str,
        strategy_type: str,
        scope_type: str = "organization",
        scope_id: Optional[str] = None,
        config: Optional[Dict] = None,
        fallback_strategy_id: Optional[str] = None,
    ) -> str:
        """
        Create a new routing strategy.

        Args:
            organization_id: Organization ID
            strategy_type: Strategy type
            scope_type: Scope type
            scope_id: Optional scope ID
            config: Optional strategy config
            fallback_strategy_id: Optional fallback strategy

        Returns:
            Strategy ID
        """
        strategy_id = str(uuid4())

        # Deactivate existing strategies for this scope
        stmt = select(RoutingStrategyModel).where(
            RoutingStrategyModel.organization_id == organization_id,
            RoutingStrategyModel.scope_type == scope_type,
        )

        if scope_id:
            stmt = stmt.where(RoutingStrategyModel.scope_id == scope_id)
        else:
            stmt = stmt.where(RoutingStrategyModel.scope_id.is_(None))

        result = await self.db.execute(stmt)
        existing = result.scalars().all()

        for s in existing:
            s.is_active = False

        # Create new strategy
        strategy = RoutingStrategyModel(
            id=strategy_id,
            organization_id=organization_id,
            scope_type=scope_type,
            scope_id=scope_id,
            strategy_type=strategy_type,
            config=json.dumps(config) if config else None,
            fallback_strategy_id=fallback_strategy_id,
            is_active=True,
        )

        self.db.add(strategy)
        await self.db.flush()

        return strategy_id

    async def update_strategy(
        self,
        strategy_id: str,
        **kwargs
    ) -> bool:
        """
        Update a routing strategy.

        Args:
            strategy_id: Strategy ID
            **kwargs: Fields to update

        Returns:
            True if updated, False if not found
        """
        result = await self.db.execute(
            select(RoutingStrategyModel).where(RoutingStrategyModel.id == strategy_id)
        )
        strategy = result.scalar_one_or_none()

        if not strategy:
            return False

        # Update allowed fields
        allowed_fields = {
            'strategy_type', 'config', 'fallback_strategy_id', 'is_active'
        }

        for key, value in kwargs.items():
            if key in allowed_fields:
                if key == 'config' and isinstance(value, dict):
                    setattr(strategy, key, json.dumps(value))
                else:
                    setattr(strategy, key, value)

        await self.db.flush()
        return True

    async def add_model_weight(
        self,
        strategy_id: str,
        model_id: str,
        weight: float = 1.0,
        priority: int = 0,
    ) -> str:
        """
        Add model weight to a strategy.

        Args:
            strategy_id: Strategy ID
            model_id: Model ID
            weight: Weight for weighted routing
            priority: Priority for priority-based routing

        Returns:
            Weight ID
        """
        weight_id = str(uuid4())

        weight_record = StrategyModelWeightModel(
            id=weight_id,
            strategy_id=strategy_id,
            model_id=model_id,
            weight=weight,
            priority=priority,
            is_enabled=True,
        )

        self.db.add(weight_record)
        await self.db.flush()

        return weight_id

    async def list_strategies(
        self,
        organization_id: str,
        scope_type: Optional[str] = None,
    ) -> List[Dict]:
        """
        List routing strategies.

        Args:
            organization_id: Organization ID
            scope_type: Optional scope type filter

        Returns:
            List of strategy configurations
        """
        stmt = select(RoutingStrategyModel).where(
            RoutingStrategyModel.organization_id == organization_id
        )

        if scope_type:
            stmt = stmt.where(RoutingStrategyModel.scope_type == scope_type)

        result = await self.db.execute(stmt)
        strategies = result.scalars().all()

        result = []
        for s in strategies:
            config = {}
            if s.config:
                try:
                    config = json.loads(s.config)
                except:
                    config = {}

            result.append({
                "id": s.id,
                "organization_id": s.organization_id,
                "scope_type": s.scope_type,
                "scope_id": s.scope_id,
                "strategy_type": s.strategy_type,
                "config": config,
                "fallback_strategy_id": s.fallback_strategy_id,
                "is_active": s.is_active,
                "created_at": s.created_at.isoformat(),
                "updated_at": s.updated_at.isoformat(),
            })

        return result


def get_routing_engine(db: AsyncSession) -> RoutingEngine:
    """Get routing engine instance."""
    return RoutingEngine(db)
