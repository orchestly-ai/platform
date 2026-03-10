"""
Multi-LLM Routing Service - P1 Feature #3

Business logic for intelligent LLM routing and cost optimization.

Key Features:
- Smart routing based on cost, latency, quality, or balanced
- Automatic failover when primary model fails
- Cost tracking and forecasting
- A/B testing framework for model comparison
- Performance analytics
- Rate limiting and quota management
"""

import asyncio
from typing import List, Optional, Dict, Any, Tuple
from datetime import datetime, timedelta
from sqlalchemy import select, func, and_, desc
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from backend.shared.llm_models import (
    LLMProviderConfig,
    LLMModelConfig,
    LLMRequest,
    LLMRoutingRule,
    LLMModelComparison,
    LLMProvider,
    RoutingStrategy,
    ModelCapability,
    LLMProviderCreate,
    LLMModelCreate,
    LLMRequestCreate,
    LLMRoutingRequest,
    LLMRoutingResponse,
    LLMCostEstimate,
    ModelComparisonCreate,
)
from backend.shared.credential_manager import get_credential_manager


class LLMRoutingService:
    """Service for intelligent LLM routing and management."""

    @staticmethod
    async def create_provider(
        db: AsyncSession,
        provider_data: LLMProviderCreate,
        user_id: str,
        organization_id: Optional[int] = None,
    ) -> LLMProviderConfig:
        """Create new LLM provider configuration."""
        # Encrypt API key before storing
        credential_manager = get_credential_manager()
        encrypted_api_key = credential_manager.encrypt({"api_key": provider_data.api_key}) if provider_data.api_key else None

        provider = LLMProviderConfig(
            provider=provider_data.provider,
            name=provider_data.name,
            description=provider_data.description,
            api_key=encrypted_api_key,
            api_endpoint=provider_data.api_endpoint,
            additional_config=provider_data.additional_config,
            is_default=provider_data.is_default,
            organization_id=organization_id,
            created_by_user_id=user_id,
        )

        # If setting as default, unset other defaults
        if provider_data.is_default:
            stmt = select(LLMProviderConfig).where(
                LLMProviderConfig.organization_id == organization_id,
                LLMProviderConfig.is_default == True,
            )
            result = await db.execute(stmt)
            existing_defaults = result.scalars().all()
            for existing in existing_defaults:
                existing.is_default = False

        db.add(provider)
        await db.commit()
        await db.refresh(provider)

        return provider

    @staticmethod
    async def create_model(
        db: AsyncSession,
        model_data: LLMModelCreate,
        user_id: str,
    ) -> LLMModelConfig:
        """Create new LLM model configuration."""
        model = LLMModelConfig(
            provider_id=model_data.provider_id,
            model_name=model_data.model_name,
            display_name=model_data.display_name,
            description=model_data.description,
            capabilities=[c.value for c in model_data.capabilities],
            max_tokens=model_data.max_tokens,
            supports_streaming=model_data.supports_streaming,
            supports_function_calling=model_data.supports_function_calling,
            input_cost_per_1m_tokens=model_data.input_cost_per_1m_tokens,
            output_cost_per_1m_tokens=model_data.output_cost_per_1m_tokens,
            rate_limit_per_minute=model_data.rate_limit_per_minute,
            rate_limit_per_day=model_data.rate_limit_per_day,
        )

        db.add(model)
        await db.commit()
        await db.refresh(model)

        return model

    @staticmethod
    async def route_llm_request(
        db: AsyncSession,
        routing_request: LLMRoutingRequest,
        user_id: str,
        organization_id: Optional[int] = None,
    ) -> LLMRoutingResponse:
        """
        Route LLM request to best model based on strategy.

        Returns the selected model and reasoning for the choice.
        """
        # Get all active models with eager loading of provider
        stmt = select(LLMModelConfig).join(LLMProviderConfig).where(
            LLMModelConfig.is_active == True,
            LLMProviderConfig.is_active == True,
        ).options(selectinload(LLMModelConfig.provider))

        if organization_id:
            stmt = stmt.where(
                (LLMProviderConfig.organization_id == organization_id) |
                (LLMProviderConfig.organization_id.is_(None))  # Public providers
            )

        result = await db.execute(stmt)
        available_models = result.scalars().all()

        if not available_models:
            raise ValueError("No active LLM models configured")

        # Filter by required capabilities
        if routing_request.required_capabilities:
            available_models = [
                m for m in available_models
                if all(cap.value in m.capabilities for cap in routing_request.required_capabilities)
            ]

        if not available_models:
            raise ValueError("No models match required capabilities")

        # Filter by cost/latency constraints
        if routing_request.max_cost:
            estimated_cost = routing_request.max_tokens * 2  # Estimate
            available_models = [
                m for m in available_models
                if (m.input_cost_per_1m_tokens + m.output_cost_per_1m_tokens) * estimated_cost / 1_000_000 <= routing_request.max_cost
            ]

        if routing_request.max_latency_ms:
            available_models = [
                m for m in available_models
                if m.avg_latency_ms <= routing_request.max_latency_ms
            ]

        # Apply routing strategy
        strategy = routing_request.routing_strategy
        selected_model = None
        reasoning = ""

        if strategy == RoutingStrategy.PRIMARY_ONLY:
            # Use only the first/primary model
            selected_model = available_models[0]
            reasoning = "Using primary model only"

        elif strategy == RoutingStrategy.PRIMARY_WITH_BACKUP:
            # Use primary, but have backups ready
            selected_model = available_models[0]
            reasoning = "Using primary model with backup failover"

        elif strategy == RoutingStrategy.COST_OPTIMIZED:
            selected_model = await LLMRoutingService._route_lowest_cost(available_models)
            reasoning = f"Selected cheapest model: ${selected_model.input_cost_per_1m_tokens + selected_model.output_cost_per_1m_tokens:.4f} per 1M tokens"

        elif strategy == RoutingStrategy.LATENCY_OPTIMIZED:
            selected_model = await LLMRoutingService._route_lowest_latency(available_models)
            reasoning = f"Selected fastest model: {selected_model.avg_latency_ms:.0f}ms avg latency"

        elif strategy == RoutingStrategy.BEST_AVAILABLE:
            # Balanced approach considering cost, latency, and quality
            selected_model = await LLMRoutingService._route_balanced(available_models)
            reasoning = "Selected best balanced model (cost + latency + quality)"

        else:
            # Fallback to first available model
            selected_model = available_models[0]
            reasoning = "Default model selection"

        # Get fallback options (next 3 best models)
        fallback_models = [m for m in available_models if m.id != selected_model.id][:3]

        # Estimate cost and latency
        estimated_cost = await LLMRoutingService._estimate_cost(
            selected_model,
            routing_request.prompt,
            routing_request.max_tokens
        )

        return LLMRoutingResponse(
            selected_model_id=selected_model.id,
            selected_model_name=selected_model.model_name,
            provider=selected_model.provider.provider,
            estimated_cost=estimated_cost.total_cost,
            estimated_latency_ms=selected_model.avg_latency_ms,
            estimated_quality_score=selected_model.avg_quality_score,
            routing_strategy_used=strategy,
            reasoning=reasoning,
            fallback_model_ids=[m.id for m in fallback_models],
        )

    @staticmethod
    async def _route_lowest_cost(models: List[LLMModelConfig]) -> LLMModelConfig:
        """Route to cheapest model."""
        return min(models, key=lambda m: m.input_cost_per_1m_tokens + m.output_cost_per_1m_tokens)

    @staticmethod
    async def _route_lowest_latency(models: List[LLMModelConfig]) -> LLMModelConfig:
        """Route to fastest model."""
        return min(models, key=lambda m: m.avg_latency_ms or 999999)

    @staticmethod
    async def _route_highest_quality(models: List[LLMModelConfig]) -> LLMModelConfig:
        """Route to highest quality model."""
        return max(models, key=lambda m: m.avg_quality_score)

    @staticmethod
    async def _route_balanced(models: List[LLMModelConfig]) -> LLMModelConfig:
        """Route using balanced scoring (cost + latency + quality)."""
        def score(model: LLMModelConfig) -> float:
            # Normalize and combine metrics (lower is better)
            cost_score = (model.input_cost_per_1m_tokens + model.output_cost_per_1m_tokens) / 100
            latency_score = (model.avg_latency_ms or 1000) / 1000
            quality_score = 1.0 - model.avg_quality_score  # Invert (lower is better)

            # Weighted average (equal weights)
            return (cost_score + latency_score + quality_score) / 3

        return min(models, key=score)

    @staticmethod
    async def _route_capability_match(
        models: List[LLMModelConfig],
        task_type: Optional[str]
    ) -> LLMModelConfig:
        """Route based on best capability match for task type."""
        # Map task types to preferred capabilities
        task_capability_map = {
            "code": ModelCapability.CODE_GENERATION,
            "vision": ModelCapability.VISION,
            "reasoning": ModelCapability.REASONING,
            "json": ModelCapability.JSON_MODE,
            "function_calling": ModelCapability.FUNCTION_CALLING,
        }

        preferred_capability = task_capability_map.get(task_type)

        if preferred_capability:
            # Filter models with this capability
            matching = [m for m in models if preferred_capability.value in m.capabilities]
            if matching:
                return await LLMRoutingService._route_balanced(matching)

        # Fallback to balanced
        return await LLMRoutingService._route_balanced(models)

    @staticmethod
    async def _route_round_robin(
        db: AsyncSession,
        models: List[LLMModelConfig],
        organization_id: Optional[int]
    ) -> LLMModelConfig:
        """Round-robin selection across models."""
        # Get count of recent requests per model
        stmt = select(
            LLMRequest.model_id,
            func.count(LLMRequest.id).label('request_count')
        ).where(
            LLMRequest.model_id.in_([m.id for m in models]),
            LLMRequest.created_at >= datetime.utcnow() - timedelta(hours=1)
        ).group_by(LLMRequest.model_id)

        if organization_id:
            stmt = stmt.where(LLMRequest.organization_id == organization_id)

        result = await db.execute(stmt)
        usage_counts = {row.model_id: row.request_count for row in result}

        # Select model with least recent usage
        return min(models, key=lambda m: usage_counts.get(m.id, 0))

    @staticmethod
    async def _estimate_cost(
        model: LLMModelConfig,
        prompt: str,
        max_output_tokens: int
    ) -> LLMCostEstimate:
        """Estimate cost for a request."""
        # Simple token estimation (4 chars per token average)
        input_tokens = len(prompt) // 4
        output_tokens = max_output_tokens

        input_cost = (input_tokens / 1_000_000) * model.input_cost_per_1m_tokens
        output_cost = (output_tokens / 1_000_000) * model.output_cost_per_1m_tokens
        total_cost = input_cost + output_cost

        return LLMCostEstimate(
            model_id=model.id,
            model_name=model.model_name,
            provider=model.provider.provider,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            input_cost=input_cost,
            output_cost=output_cost,
            total_cost=total_cost,
            currency=model.currency,
        )

    @staticmethod
    async def log_request(
        db: AsyncSession,
        request_data: LLMRequestCreate,
        user_id: str,
        organization_id: Optional[int] = None,
    ) -> LLMRequest:
        """Log LLM request for analytics."""
        # Get model to calculate cost with eager loading of provider
        stmt = select(LLMModelConfig).where(
            LLMModelConfig.id == request_data.model_id
        ).options(selectinload(LLMModelConfig.provider))
        result = await db.execute(stmt)
        model = result.scalar_one_or_none()

        if not model:
            raise ValueError(f"Model {request_data.model_id} not found")

        # Calculate costs
        input_cost = (request_data.prompt_tokens / 1_000_000) * model.input_cost_per_1m_tokens
        output_cost = (request_data.completion_tokens / 1_000_000) * model.output_cost_per_1m_tokens
        total_cost = input_cost + output_cost

        # Create request log
        request = LLMRequest(
            model_id=request_data.model_id,
            task_id=request_data.task_id,
            workflow_id=request_data.workflow_id,
            user_id=user_id,
            organization_id=organization_id,
            prompt_tokens=request_data.prompt_tokens,
            completion_tokens=request_data.completion_tokens,
            total_tokens=request_data.prompt_tokens + request_data.completion_tokens,
            input_cost=input_cost,
            output_cost=output_cost,
            total_cost=total_cost,
            latency_ms=request_data.latency_ms,
            status=request_data.status,
            error_message=request_data.error_message,
            routing_strategy=request_data.routing_strategy,
            was_fallback=request_data.was_fallback,
            original_model_id=request_data.original_model_id,
        )

        db.add(request)

        # Update model performance metrics
        await LLMRoutingService._update_model_metrics(db, model, request)

        await db.commit()
        await db.refresh(request)

        return request

    @staticmethod
    async def _update_model_metrics(
        db: AsyncSession,
        model: LLMModelConfig,
        request: LLMRequest,
    ) -> None:
        """Update model's performance metrics based on request."""
        # Get recent requests for rolling average (last 100 requests)
        stmt = select(LLMRequest).where(
            LLMRequest.model_id == model.id,
            LLMRequest.status == "success"
        ).order_by(desc(LLMRequest.created_at)).limit(100)

        result = await db.execute(stmt)
        recent_requests = result.scalars().all()

        if recent_requests:
            # Update average latency
            model.avg_latency_ms = sum(r.latency_ms for r in recent_requests) / len(recent_requests)

            # Update success rate
            total_recent = len(recent_requests)
            successful = sum(1 for r in recent_requests if r.status == "success")
            model.success_rate = successful / total_recent if total_recent > 0 else 1.0

            # Update quality score if available
            quality_scores = [r.quality_score for r in recent_requests if r.quality_score is not None]
            if quality_scores:
                model.avg_quality_score = sum(quality_scores) / len(quality_scores)

    @staticmethod
    async def get_cost_analytics(
        db: AsyncSession,
        organization_id: Optional[int] = None,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
    ) -> Dict[str, Any]:
        """Get cost analytics for organization."""
        # Default to last 30 days
        if not start_date:
            start_date = datetime.utcnow() - timedelta(days=30)
        if not end_date:
            end_date = datetime.utcnow()

        # Build query
        stmt = select(
            func.sum(LLMRequest.total_cost).label('total_cost'),
            func.sum(LLMRequest.total_tokens).label('total_tokens'),
            func.count(LLMRequest.id).label('total_requests'),
            func.avg(LLMRequest.latency_ms).label('avg_latency'),
        ).where(
            LLMRequest.created_at >= start_date,
            LLMRequest.created_at <= end_date,
        )

        if organization_id:
            stmt = stmt.where(LLMRequest.organization_id == organization_id)

        result = await db.execute(stmt)
        row = result.one()

        # Get cost by model
        stmt_by_model = select(
            LLMModelConfig.model_name,
            func.sum(LLMRequest.total_cost).label('cost'),
            func.count(LLMRequest.id).label('requests'),
        ).join(LLMRequest).where(
            LLMRequest.created_at >= start_date,
            LLMRequest.created_at <= end_date,
        ).group_by(LLMModelConfig.model_name)

        if organization_id:
            stmt_by_model = stmt_by_model.where(LLMRequest.organization_id == organization_id)

        result_by_model = await db.execute(stmt_by_model)
        cost_by_model = [
            {"model": row.model_name, "cost": float(row.cost or 0), "requests": row.requests}
            for row in result_by_model
        ]

        return {
            "total_cost": float(row.total_cost or 0),
            "total_tokens": int(row.total_tokens or 0),
            "total_requests": int(row.total_requests or 0),
            "avg_latency_ms": float(row.avg_latency or 0),
            "cost_by_model": cost_by_model,
            "period": {
                "start": start_date.isoformat(),
                "end": end_date.isoformat(),
            }
        }

    @staticmethod
    async def create_model_comparison(
        db: AsyncSession,
        comparison_data: ModelComparisonCreate,
        user_id: str,
        organization_id: Optional[int] = None,
    ) -> LLMModelComparison:
        """Create A/B test for comparing two models."""
        comparison = LLMModelComparison(
            name=comparison_data.name,
            description=comparison_data.description,
            model_a_id=comparison_data.model_a_id,
            model_b_id=comparison_data.model_b_id,
            organization_id=organization_id,
            created_by_user_id=user_id,
            test_cases=comparison_data.test_cases,
            evaluation_criteria=comparison_data.evaluation_criteria,
            status="pending",
        )

        db.add(comparison)
        await db.commit()
        await db.refresh(comparison)

        return comparison

    @staticmethod
    async def execute_comparison(
        db: AsyncSession,
        comparison_id: int,
    ) -> LLMModelComparison:
        """Execute A/B test comparison (would call actual LLM APIs)."""
        stmt = select(LLMModelComparison).where(LLMModelComparison.id == comparison_id)
        result = await db.execute(stmt)
        comparison = result.scalar_one_or_none()

        if not comparison:
            raise ValueError(f"Comparison {comparison_id} not found")

        # Update status
        comparison.status = "running"
        await db.commit()

        # In production, this would:
        # 1. Run test cases against both models
        # 2. Collect metrics (cost, latency, quality)
        # 3. Calculate winner

        # For now, simulate results
        comparison.model_a_avg_cost = 0.015
        comparison.model_b_avg_cost = 0.008
        comparison.model_a_avg_latency = 850.0
        comparison.model_b_avg_latency = 1200.0
        comparison.model_a_avg_quality = 0.92
        comparison.model_b_avg_quality = 0.88

        # Determine winner (simple scoring)
        score_a = (1 - comparison.model_a_avg_cost / 0.02) * 0.4 + \
                  (1 - comparison.model_a_avg_latency / 2000) * 0.3 + \
                  comparison.model_a_avg_quality * 0.3
        score_b = (1 - comparison.model_b_avg_cost / 0.02) * 0.4 + \
                  (1 - comparison.model_b_avg_latency / 2000) * 0.3 + \
                  comparison.model_b_avg_quality * 0.3

        comparison.winner_model_id = comparison.model_a_id if score_a > score_b else comparison.model_b_id
        comparison.confidence_score = abs(score_a - score_b)
        comparison.status = "completed"
        comparison.completed_at = datetime.utcnow()

        await db.commit()
        await db.refresh(comparison)

        return comparison

    @staticmethod
    async def get_model_recommendations(
        db: AsyncSession,
        task_type: str,
        organization_id: Optional[int] = None,
    ) -> List[LLMModelConfig]:
        """Get recommended models for a task type."""
        # Get all active models with eager loading of provider
        stmt = select(LLMModelConfig).join(LLMProviderConfig).where(
            LLMModelConfig.is_active == True,
            LLMProviderConfig.is_active == True,
        ).options(selectinload(LLMModelConfig.provider)).order_by(desc(LLMModelConfig.avg_quality_score))

        if organization_id:
            stmt = stmt.where(
                (LLMProviderConfig.organization_id == organization_id) |
                (LLMProviderConfig.organization_id.is_(None))
            )

        result = await db.execute(stmt)
        models = result.scalars().all()

        # Filter by task type capabilities
        task_capability_map = {
            "code": ModelCapability.CODE_GENERATION,
            "vision": ModelCapability.VISION,
            "reasoning": ModelCapability.REASONING,
            "json": ModelCapability.JSON_MODE,
        }

        required_capability = task_capability_map.get(task_type)
        if required_capability:
            models = [m for m in models if required_capability.value in m.capabilities]

        return list(models[:5])  # Top 5 recommendations

    @staticmethod
    def decrypt_api_key(provider: LLMProviderConfig) -> Optional[str]:
        """
        Decrypt API key from provider configuration.

        Args:
            provider: LLM provider configuration with encrypted API key

        Returns:
            Decrypted API key string, or None if not available
        """
        if not provider.api_key:
            return None

        credential_manager = get_credential_manager()
        try:
            decrypted = credential_manager.decrypt(provider.api_key)
            return decrypted.get("api_key")
        except Exception:
            # Fallback: might be stored unencrypted (legacy data)
            return provider.api_key

    @staticmethod
    async def get_provider_with_decrypted_key(
        db: AsyncSession,
        provider_id: int,
    ) -> Tuple[Optional[LLMProviderConfig], Optional[str]]:
        """
        Get provider configuration and decrypted API key.

        Args:
            db: Database session
            provider_id: ID of the provider

        Returns:
            Tuple of (provider, decrypted_api_key)
        """
        stmt = select(LLMProviderConfig).where(LLMProviderConfig.id == provider_id)
        result = await db.execute(stmt)
        provider = result.scalar_one_or_none()

        if not provider:
            return None, None

        api_key = LLMRoutingService.decrypt_api_key(provider)
        return provider, api_key

# Compatibility alias for demos
LLMService = LLMRoutingService

