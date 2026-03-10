"""
ML-Based Routing Optimization Service - P2 Feature #6

Intelligent LLM routing using machine learning to optimize cost and performance.
"""

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_, func
from typing import List, Optional, Dict, Any, Tuple
from datetime import datetime, timedelta
import random
import math

from backend.shared.ml_routing_models import *


class MLRoutingService:
    """Service for ML-based LLM routing optimization"""

    # LLM Model Management
    @staticmethod
    async def register_model(
        db: AsyncSession,
        model_data: LLMModelCreate,
    ) -> LLMModel:
        """Register a new LLM model"""
        # Use mode='python' to get enum values, not names
        data = model_data.model_dump(mode='python')
        # Convert enum objects to their string values
        if 'provider' in data and hasattr(data['provider'], 'value'):
            data['provider'] = data['provider'].value
        model = LLMModel(**data)
        db.add(model)
        await db.commit()
        await db.refresh(model)
        return model

    @staticmethod
    async def get_models(
        db: AsyncSession,
        provider: Optional[ModelProvider] = None,
        is_active: bool = True,
    ) -> List[LLMModel]:
        """Get available LLM models"""
        query = select(LLMModel).where(LLMModel.is_active == is_active)
        if provider:
            query = query.where(LLMModel.provider == provider)
        
        result = await db.execute(query.order_by(LLMModel.quality_score.desc()))
        return list(result.scalars().all())

    @staticmethod
    async def update_model_stats(
        db: AsyncSession,
        model_id: int,
        latency_ms: float,
        tokens_processed: int,
        cost_usd: float,
        success: bool,
    ) -> None:
        """Update model performance statistics"""
        result = await db.execute(select(LLMModel).where(LLMModel.id == model_id))
        model = result.scalar_one_or_none()
        if not model:
            return

        # Update running averages
        total_requests = model.total_requests + 1
        model.avg_latency_ms = (
            (model.avg_latency_ms * model.total_requests + latency_ms) / total_requests
        )
        
        if success:
            model.success_rate = (
                (model.success_rate * model.total_requests + 100.0) / total_requests
            )
        else:
            model.success_rate = (
                (model.success_rate * model.total_requests) / total_requests
            )

        model.total_requests = total_requests
        model.total_tokens_processed += tokens_processed
        model.total_cost_usd += cost_usd

        await db.commit()

    # Routing Policy Management
    @staticmethod
    async def create_routing_policy(
        db: AsyncSession,
        policy_data: RoutingPolicyCreate,
        created_by: str,
    ) -> RoutingPolicy:
        """Create a routing policy"""
        data = policy_data.model_dump(mode='python')
        # Convert enum objects to their string values
        for key in ['strategy', 'optimization_goal']:
            if key in data and hasattr(data[key], 'value'):
                data[key] = data[key].value
        # Convert allowed_providers list of enums to list of strings
        if 'allowed_providers' in data and data['allowed_providers']:
            data['allowed_providers'] = [
                p.value if hasattr(p, 'value') else p
                for p in data['allowed_providers']
            ]
        policy = RoutingPolicy(
            **data,
            created_by=created_by,
        )
        db.add(policy)
        await db.commit()
        await db.refresh(policy)
        return policy

    @staticmethod
    async def get_routing_policies(
        db: AsyncSession,
        is_active: bool = True,
    ) -> List[RoutingPolicy]:
        """List routing policies"""
        result = await db.execute(
            select(RoutingPolicy)
            .where(RoutingPolicy.is_active == is_active)
            .order_by(RoutingPolicy.created_at.desc())
        )
        return list(result.scalars().all())

    # Core Routing Logic
    @staticmethod
    async def route_request(
        db: AsyncSession,
        route_request: RouteRequest,
    ) -> RouteResponse:
        """Route request to optimal LLM model using ML"""
        # Get policy
        result = await db.execute(
            select(RoutingPolicy).where(RoutingPolicy.id == route_request.policy_id)
        )
        policy = result.scalar_one_or_none()
        if not policy:
            raise ValueError(f"Policy {route_request.policy_id} not found")

        # Get candidate models
        candidates = await MLRoutingService._get_candidate_models(db, policy, route_request)
        if not candidates:
            raise ValueError("No candidate models available")

        # ML-based prediction or rule-based selection
        if policy.use_ml_prediction:
            selected_model, confidence, reasoning = await MLRoutingService._ml_predict_model(
                db, policy, route_request, candidates
            )
        else:
            selected_model, confidence, reasoning = await MLRoutingService._rule_based_select(
                db, policy, route_request, candidates
            )

        # Estimate cost and latency
        estimated_cost = MLRoutingService._estimate_cost(
            selected_model,
            route_request.input_length_tokens,
            route_request.expected_output_tokens,
        )
        estimated_latency = selected_model.avg_latency_ms

        # Map numeric confidence to enum
        confidence_enum = MLRoutingService._get_confidence_enum(confidence)

        # Create routing decision record
        decision = RoutingDecision(
            policy_id=policy.id,
            request_id=route_request.request_id,
            workflow_id=route_request.workflow_id,
            agent_id=route_request.agent_id,
            input_length_tokens=route_request.input_length_tokens,
            expected_output_tokens=route_request.expected_output_tokens,
            task_type=route_request.task_type,
            task_complexity=route_request.task_complexity,
            requires_functions=route_request.requires_functions,
            requires_vision=route_request.requires_vision,
            predicted_model_id=selected_model.id,
            actual_model_id=selected_model.id,
            prediction_confidence=confidence_enum,
            confidence_score=confidence,
            predicted_cost_usd=estimated_cost,
            predicted_latency_ms=estimated_latency,
            prediction_features=reasoning,
            candidate_models=[{"model_id": c.id, "name": c.name} for c in candidates],
        )
        db.add(decision)
        await db.commit()
        await db.refresh(decision)

        return RouteResponse(
            model_id=selected_model.id,
            model_name=selected_model.name,
            provider=selected_model.provider if isinstance(selected_model.provider, str) else selected_model.provider.value,
            prediction_confidence=confidence_enum,
            confidence_score=confidence,
            estimated_latency_ms=estimated_latency,
            estimated_cost_usd=estimated_cost,
            decision_id=decision.id,
            reasoning=reasoning,
        )

    @staticmethod
    async def record_execution(
        db: AsyncSession,
        decision_id: int,
        actual_latency_ms: float,
        actual_input_tokens: int,
        actual_output_tokens: int,
        success: bool,
        error_message: Optional[str] = None,
    ) -> RoutingDecision:
        """Record actual execution results"""
        result = await db.execute(
            select(RoutingDecision).where(RoutingDecision.id == decision_id)
        )
        decision = result.scalar_one_or_none()
        if not decision:
            raise ValueError(f"Decision {decision_id} not found")

        # Get model for cost calculation
        result = await db.execute(
            select(LLMModel).where(LLMModel.id == decision.actual_model_id)
        )
        model = result.scalar_one_or_none()

        # Calculate actual cost
        actual_cost = MLRoutingService._estimate_cost(
            model, actual_input_tokens, actual_output_tokens
        )

        # Calculate baseline cost (e.g., using most expensive model)
        result = await db.execute(
            select(LLMModel).order_by(LLMModel.cost_per_1m_output_tokens.desc()).limit(1)
        )
        baseline_model = result.scalar_one_or_none()
        baseline_cost = MLRoutingService._estimate_cost(
            baseline_model, actual_input_tokens, actual_output_tokens
        ) if baseline_model else actual_cost

        cost_saved = baseline_cost - actual_cost
        cost_reduction = ((baseline_cost - actual_cost) / baseline_cost * 100) if baseline_cost > 0 else 0

        # Update decision
        decision.actual_latency_ms = actual_latency_ms
        decision.actual_input_tokens = actual_input_tokens
        decision.actual_output_tokens = actual_output_tokens
        decision.actual_cost_usd = actual_cost
        decision.success = success
        decision.error_message = error_message
        decision.baseline_cost_usd = baseline_cost
        decision.cost_saved_usd = cost_saved
        decision.cost_reduction_percent = cost_reduction

        # Calculate prediction errors
        if decision.predicted_latency_ms:
            decision.latency_error_percent = (
                abs(actual_latency_ms - decision.predicted_latency_ms) /
                decision.predicted_latency_ms * 100
            )
        if decision.predicted_cost_usd:
            decision.cost_error_percent = (
                abs(actual_cost - decision.predicted_cost_usd) /
                decision.predicted_cost_usd * 100
            )

        await db.commit()

        # Update model statistics
        await MLRoutingService.update_model_stats(
            db,
            decision.actual_model_id,
            actual_latency_ms,
            actual_input_tokens + actual_output_tokens,
            actual_cost,
            success,
        )

        # Record in performance history
        await MLRoutingService._record_performance_history(
            db, decision, model, actual_latency_ms, actual_cost, success
        )

        # Update policy statistics
        await MLRoutingService._update_policy_stats(db, decision.policy_id, cost_saved, cost_reduction)

        return decision

    # Analytics
    @staticmethod
    async def get_optimization_stats(
        db: AsyncSession,
        hours: int = 24,
    ) -> Dict[str, Any]:
        """Get optimization statistics"""
        since = datetime.utcnow() - timedelta(hours=hours)

        # Total requests and savings
        result = await db.execute(
            select(
                func.count(RoutingDecision.id),
                func.sum(RoutingDecision.cost_saved_usd),
                func.avg(RoutingDecision.cost_reduction_percent),
            ).where(RoutingDecision.created_at >= since)
        )
        row = result.one()
        total_requests = row[0] or 0
        total_saved = float(row[1] or 0)
        avg_reduction = float(row[2] or 0)

        # Requests by provider
        result = await db.execute(
            select(
                LLMModel.provider,
                func.count(RoutingDecision.id).label("count"),
            )
            .join(LLMModel, LLMModel.id == RoutingDecision.actual_model_id)
            .where(RoutingDecision.created_at >= since)
            .group_by(LLMModel.provider)
        )
        requests_by_provider = {(row[0] if isinstance(row[0], str) else row[0].value): row[1] for row in result.all()}

        # Avg latency by provider
        result = await db.execute(
            select(
                LLMModel.provider,
                func.avg(RoutingDecision.actual_latency_ms).label("avg_latency"),
            )
            .join(LLMModel, LLMModel.id == RoutingDecision.actual_model_id)
            .where(
                and_(
                    RoutingDecision.created_at >= since,
                    RoutingDecision.actual_latency_ms.isnot(None),
                )
            )
            .group_by(LLMModel.provider)
        )
        latency_by_provider = {(row[0] if isinstance(row[0], str) else row[0].value): float(row[1] or 0) for row in result.all()}

        # Success rate by provider
        result = await db.execute(
            select(
                LLMModel.provider,
                func.avg(func.cast(RoutingDecision.success, Integer)).label("success_rate"),
            )
            .join(LLMModel, LLMModel.id == RoutingDecision.actual_model_id)
            .where(
                and_(
                    RoutingDecision.created_at >= since,
                    RoutingDecision.success.isnot(None),
                )
            )
            .group_by(LLMModel.provider)
        )
        success_by_provider = {(row[0] if isinstance(row[0], str) else row[0].value): float(row[1] or 0) * 100 for row in result.all()}

        return {
            "total_requests": total_requests,
            "total_cost_saved_usd": total_saved,
            "avg_cost_reduction_percent": avg_reduction,
            "total_requests_by_provider": requests_by_provider,
            "avg_latency_by_provider": latency_by_provider,
            "success_rate_by_provider": success_by_provider,
        }

    # Helper Methods
    @staticmethod
    async def _get_candidate_models(
        db: AsyncSession,
        policy: RoutingPolicy,
        request: RouteRequest,
    ) -> List[LLMModel]:
        """Get candidate models based on policy constraints"""
        query = select(LLMModel).where(
            and_(
                LLMModel.is_active == True,
                LLMModel.is_available == True,
            )
        )

        # Provider filtering
        if policy.allowed_providers:
            query = query.where(LLMModel.provider.in_(policy.allowed_providers))

        # Model filtering
        if policy.allowed_models:
            query = query.where(LLMModel.id.in_(policy.allowed_models))
        if policy.excluded_models:
            query = query.where(~LLMModel.id.in_(policy.excluded_models))

        # Feature requirements
        if request.requires_functions:
            query = query.where(LLMModel.supports_functions == True)
        if request.requires_vision:
            query = query.where(LLMModel.supports_vision == True)

        # Quality constraints
        if policy.min_quality_score:
            query = query.where(LLMModel.quality_score >= policy.min_quality_score)
        if policy.min_success_rate:
            query = query.where(LLMModel.success_rate >= policy.min_success_rate)

        result = await db.execute(query)
        return list(result.scalars().all())

    @staticmethod
    async def _ml_predict_model(
        db: AsyncSession,
        policy: RoutingPolicy,
        request: RouteRequest,
        candidates: List[LLMModel],
    ) -> Tuple[LLMModel, float, Dict]:
        """Use ML model to predict best LLM (simplified simulation)"""
        # In production, this would use a trained ML model
        # For now, we'll simulate intelligent selection based on optimization goal
        
        scores = []
        for model in candidates:
            score = 0.0
            
            # Calculate estimated cost
            cost = MLRoutingService._estimate_cost(
                model, request.input_length_tokens, request.expected_output_tokens
            )
            
            if policy.optimization_goal == OptimizationGoal.MINIMIZE_COST:
                # Prefer cheaper models
                max_cost = max(
                    MLRoutingService._estimate_cost(m, request.input_length_tokens, request.expected_output_tokens)
                    for m in candidates
                )
                score = (1 - cost / max_cost) * 100 if max_cost > 0 else 50
                
            elif policy.optimization_goal == OptimizationGoal.MAXIMIZE_QUALITY:
                # Prefer high quality models
                score = model.quality_score
                
            elif policy.optimization_goal == OptimizationGoal.MINIMIZE_LATENCY:
                # Prefer low latency models
                max_latency = max(m.avg_latency_ms for m in candidates)
                score = (1 - model.avg_latency_ms / max_latency) * 100 if max_latency > 0 else 50
                
            elif policy.optimization_goal == OptimizationGoal.BALANCED:
                # Balance cost, quality, and latency
                max_cost = max(
                    MLRoutingService._estimate_cost(m, request.input_length_tokens, request.expected_output_tokens)
                    for m in candidates
                )
                max_latency = max(m.avg_latency_ms for m in candidates)
                
                cost_score = (1 - cost / max_cost) * 100 if max_cost > 0 else 50
                quality_score = model.quality_score
                latency_score = (1 - model.avg_latency_ms / max_latency) * 100 if max_latency > 0 else 50
                
                score = (cost_score * 0.4 + quality_score * 0.3 + latency_score * 0.3)
            
            scores.append((model, score, cost))

        # Select best model
        best = max(scores, key=lambda x: x[1])
        selected_model = best[0]
        confidence = min(best[1] / 100.0, 0.95)  # Convert to 0-1, cap at 0.95

        reasoning = {
            "optimization_goal": policy.optimization_goal if isinstance(policy.optimization_goal, str) else policy.optimization_goal.value,
            "score": best[1],
            "estimated_cost": best[2],
            "alternatives_considered": len(candidates),
            "selection_method": "ml_prediction",
        }

        return selected_model, confidence, reasoning

    @staticmethod
    async def _rule_based_select(
        db: AsyncSession,
        policy: RoutingPolicy,
        request: RouteRequest,
        candidates: List[LLMModel],
    ) -> Tuple[LLMModel, float, Dict]:
        """Rule-based model selection"""
        # Simple rule: select cheapest model that meets constraints
        costs = [
            (
                model,
                MLRoutingService._estimate_cost(
                    model, request.input_length_tokens, request.expected_output_tokens
                ),
            )
            for model in candidates
        ]
        
        # Filter by latency constraint
        if policy.max_latency_ms:
            costs = [(m, c) for m, c in costs if m.avg_latency_ms <= policy.max_latency_ms]
        
        # Filter by cost constraint
        if policy.max_cost_per_request_usd:
            costs = [(m, c) for m, c in costs if c <= policy.max_cost_per_request_usd]

        if not costs:
            costs = [
                (
                    model,
                    MLRoutingService._estimate_cost(
                        model, request.input_length_tokens, request.expected_output_tokens
                    ),
                )
                for model in candidates
            ]

        selected = min(costs, key=lambda x: x[1])
        
        return selected[0], 0.8, {
            "selection_method": "rule_based",
            "estimated_cost": selected[1],
        }

    @staticmethod
    def _estimate_cost(
        model: LLMModel,
        input_tokens: int,
        output_tokens: int,
    ) -> float:
        """Estimate cost for request"""
        input_cost = (input_tokens / 1_000_000) * model.cost_per_1m_input_tokens
        output_cost = (output_tokens / 1_000_000) * model.cost_per_1m_output_tokens
        return input_cost + output_cost

    @staticmethod
    def _get_confidence_enum(confidence: float) -> PredictionConfidence:
        """Convert numeric confidence to enum"""
        if confidence >= 0.9:
            return PredictionConfidence.VERY_HIGH
        elif confidence >= 0.75:
            return PredictionConfidence.HIGH
        elif confidence >= 0.6:
            return PredictionConfidence.MEDIUM
        elif confidence >= 0.4:
            return PredictionConfidence.LOW
        else:
            return PredictionConfidence.VERY_LOW

    @staticmethod
    async def _record_performance_history(
        db: AsyncSession,
        decision: RoutingDecision,
        model: LLMModel,
        latency_ms: float,
        cost_usd: float,
        success: bool,
    ) -> None:
        """Record performance for ML training"""
        now = datetime.utcnow()
        history = ModelPerformanceHistory(
            model_id=model.id,
            task_type=decision.task_type,
            input_tokens=decision.actual_input_tokens or 0,
            output_tokens=decision.actual_output_tokens or 0,
            latency_ms=latency_ms,
            cost_usd=cost_usd,
            success=success,
            time_of_day=now.hour,
            day_of_week=now.weekday(),
        )
        db.add(history)
        await db.commit()

    @staticmethod
    async def _update_policy_stats(
        db: AsyncSession,
        policy_id: int,
        cost_saved: float,
        cost_reduction_percent: float,
    ) -> None:
        """Update policy statistics"""
        result = await db.execute(select(RoutingPolicy).where(RoutingPolicy.id == policy_id))
        policy = result.scalar_one_or_none()
        if not policy:
            return

        total = policy.total_requests + 1
        policy.total_requests = total
        policy.total_cost_saved_usd += cost_saved
        policy.avg_cost_reduction_percent = (
            (policy.avg_cost_reduction_percent * (total - 1) + cost_reduction_percent) / total
        )

        await db.commit()
