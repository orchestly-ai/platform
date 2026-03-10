"""
Unit Tests for Auto-Optimization Engine

Tests for the optimization recommendation and application system.
"""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from datetime import datetime, timedelta
from uuid import uuid4

from backend.shared.auto_optimization_engine import (
    AutoOptimizationEngine,
    OptimizationRecommendation,
    OptimizationType,
    OptimizationStatus,
    ConfidenceLevel,
    WorkflowAnalysis,
    ModelCostProfile,
    get_optimization_engine
)


class TestModelCostProfile:
    """Tests for ModelCostProfile."""

    def test_profile_creation(self):
        """Test creating a model cost profile."""
        profile = ModelCostProfile(
            model_id="gpt-4o",
            provider="openai",
            cost_per_1k_tokens=0.005,
            avg_latency_ms=800,
            capability_tier=4
        )
        assert profile.model_id == "gpt-4o"
        assert profile.provider == "openai"
        assert profile.capability_tier == 4

    def test_builtin_profiles_exist(self):
        """Test that the engine has built-in model profiles."""
        assert "gpt-4o" in AutoOptimizationEngine.MODEL_PROFILES
        assert "claude-3-5-sonnet" in AutoOptimizationEngine.MODEL_PROFILES
        assert "gemini-1.5-flash" in AutoOptimizationEngine.MODEL_PROFILES


class TestWorkflowAnalysis:
    """Tests for WorkflowAnalysis dataclass."""

    def test_analysis_creation(self):
        """Test creating workflow analysis."""
        analysis = WorkflowAnalysis(
            workflow_id=uuid4(),
            execution_count=100,
            avg_cost=0.05,
            avg_latency_ms=500,
            p95_latency_ms=800,
            success_rate=98.5,
            primary_model="gpt-4o-mini",
            token_usage_pattern="consistent",
            complexity_level="simple"
        )
        assert analysis.execution_count == 100
        assert analysis.success_rate == 98.5
        assert analysis.complexity_level == "simple"


class TestOptimizationRecommendation:
    """Tests for OptimizationRecommendation dataclass."""

    def test_recommendation_creation(self):
        """Test creating an optimization recommendation."""
        rec = OptimizationRecommendation(
            recommendation_id=uuid4(),
            organization_id="org-123",
            optimization_type=OptimizationType.MODEL_DOWNGRADE,
            title="Switch to cheaper model",
            description="Workflow is simple enough for a cheaper model",
            confidence=ConfidenceLevel.HIGH,
            estimated_savings=50.0,
            affected_workflows=[uuid4()],
            current_config={"model": "gpt-4o"},
            recommended_config={"model": "gpt-4o-mini"}
        )
        assert rec.optimization_type == OptimizationType.MODEL_DOWNGRADE
        assert rec.confidence == ConfidenceLevel.HIGH
        assert rec.estimated_savings == 50.0

    def test_recommendation_to_dict(self):
        """Test converting recommendation to dictionary."""
        workflow_id = uuid4()
        rec_id = uuid4()
        rec = OptimizationRecommendation(
            recommendation_id=rec_id,
            organization_id="org-123",
            optimization_type=OptimizationType.COST_REDUCTION,
            title="Test recommendation",
            description="Test description",
            confidence=ConfidenceLevel.MEDIUM,
            estimated_savings=25.0,
            affected_workflows=[workflow_id]
        )
        result = rec.to_dict()

        assert result["recommendation_id"] == str(rec_id)
        assert result["organization_id"] == "org-123"
        assert result["type"] == "cost_reduction"
        assert result["confidence"] == "medium"
        assert str(workflow_id) in result["affected_workflows"]

    def test_recommendation_status_transitions(self):
        """Test recommendation status transitions."""
        rec = OptimizationRecommendation(
            recommendation_id=uuid4(),
            organization_id="org-123",
            optimization_type=OptimizationType.CACHE_ENABLEMENT,
            title="Enable caching",
            description="Enable response caching",
            confidence=ConfidenceLevel.LOW
        )

        assert rec.status == OptimizationStatus.SUGGESTED

        rec.status = OptimizationStatus.APPROVED
        assert rec.status == OptimizationStatus.APPROVED

        rec.status = OptimizationStatus.APPLIED
        rec.applied_at = datetime.utcnow()
        assert rec.status == OptimizationStatus.APPLIED
        assert rec.applied_at is not None


class TestOptimizationType:
    """Tests for OptimizationType enum."""

    def test_all_types_exist(self):
        """Test that all optimization types are defined."""
        assert OptimizationType.COST_REDUCTION.value == "cost_reduction"
        assert OptimizationType.LATENCY_IMPROVEMENT.value == "latency_improvement"
        assert OptimizationType.AB_TEST_GRADUATION.value == "ab_test_graduation"
        assert OptimizationType.MODEL_UPGRADE.value == "model_upgrade"
        assert OptimizationType.MODEL_DOWNGRADE.value == "model_downgrade"
        assert OptimizationType.ROUTING_CHANGE.value == "routing_change"
        assert OptimizationType.CACHE_ENABLEMENT.value == "cache_enablement"


class TestConfidenceLevel:
    """Tests for ConfidenceLevel enum."""

    def test_confidence_levels(self):
        """Test confidence level values."""
        assert ConfidenceLevel.LOW.value == "low"
        assert ConfidenceLevel.MEDIUM.value == "medium"
        assert ConfidenceLevel.HIGH.value == "high"


class TestAutoOptimizationEngine:
    """Tests for AutoOptimizationEngine class."""

    @pytest.fixture
    def mock_db(self):
        """Create mock database session."""
        db = AsyncMock()
        db.execute = AsyncMock()
        db.commit = AsyncMock()
        return db

    @pytest.fixture
    def engine(self, mock_db):
        """Create engine instance."""
        return AutoOptimizationEngine(mock_db)

    @pytest.fixture
    def sample_workflows(self):
        """Create sample workflow analyses."""
        return [
            WorkflowAnalysis(
                workflow_id=uuid4(),
                execution_count=100,
                avg_cost=0.10,
                avg_latency_ms=800,
                p95_latency_ms=1200,
                success_rate=99.0,
                primary_model="gpt-4o",
                token_usage_pattern="consistent",
                complexity_level="simple"
            ),
            WorkflowAnalysis(
                workflow_id=uuid4(),
                execution_count=50,
                avg_cost=0.05,
                avg_latency_ms=500,
                p95_latency_ms=700,
                success_rate=95.0,
                primary_model="gpt-4o-mini",
                token_usage_pattern="variable",
                complexity_level="moderate"
            ),
        ]

    @pytest.mark.asyncio
    async def test_analyze_cost_optimization_detects_downgrade(self, engine, sample_workflows):
        """Test that cost optimization detects model downgrade opportunities."""
        recommendations = await engine._analyze_cost_optimization(
            "org-123",
            sample_workflows
        )

        # First workflow is simple with premium model - should recommend downgrade
        downgrade_recs = [
            r for r in recommendations
            if r.optimization_type == OptimizationType.MODEL_DOWNGRADE
        ]

        assert len(downgrade_recs) >= 1
        assert downgrade_recs[0].estimated_savings > 0

    @pytest.mark.asyncio
    async def test_analyze_model_downgrades_high_success_rate(self, engine):
        """Test model downgrade analysis for high success rate workflows."""
        workflows = [
            WorkflowAnalysis(
                workflow_id=uuid4(),
                execution_count=200,
                avg_cost=0.15,
                avg_latency_ms=1000,
                p95_latency_ms=1500,
                success_rate=99.5,  # Very high success rate
                primary_model="claude-3-opus",  # Tier 4 premium model
                token_usage_pattern="consistent",
                complexity_level="moderate"  # But only moderate complexity
            )
        ]

        recommendations = await engine._analyze_model_downgrades("org-123", workflows)

        # Should recommend downgrade from tier 4 to tier 3 for moderate complexity
        assert len(recommendations) >= 1
        assert recommendations[0].confidence == ConfidenceLevel.HIGH

    @pytest.mark.asyncio
    async def test_analyze_latency_optimization(self, engine):
        """Test latency optimization detection."""
        workflows = [
            WorkflowAnalysis(
                workflow_id=uuid4(),
                execution_count=100,
                avg_cost=0.10,
                avg_latency_ms=2500,  # High latency
                p95_latency_ms=3500,  # >2s threshold
                success_rate=95.0,
                primary_model="gpt-4-turbo",  # Slower model
                token_usage_pattern="consistent",
                complexity_level="moderate"
            )
        ]

        recommendations = await engine._analyze_latency_optimization("org-123", workflows)

        # Should recommend faster model
        latency_recs = [
            r for r in recommendations
            if r.optimization_type == OptimizationType.LATENCY_IMPROVEMENT
        ]

        assert len(latency_recs) >= 1
        assert latency_recs[0].estimated_latency_improvement_ms > 0

    @pytest.mark.asyncio
    async def test_analyze_cache_opportunities(self, engine):
        """Test cache opportunity detection."""
        # Need avg_cost * execution_count * 0.6 > 5 for recommendation
        # Using avg_cost=0.1, execution_count=100: 0.1 * 100 * 0.6 = 6 > 5
        workflows = [
            WorkflowAnalysis(
                workflow_id=uuid4(),
                execution_count=100,
                avg_cost=0.10,  # Higher cost to trigger recommendation threshold
                avg_latency_ms=400,
                p95_latency_ms=600,
                success_rate=98.0,
                primary_model="gpt-4o-mini",
                token_usage_pattern="consistent",  # Consistent = good for caching
                complexity_level="simple"  # Simple = good for caching
            )
        ]

        recommendations = await engine._analyze_cache_opportunities("org-123", workflows)

        cache_recs = [
            r for r in recommendations
            if r.optimization_type == OptimizationType.CACHE_ENABLEMENT
        ]

        assert len(cache_recs) >= 1
        assert cache_recs[0].recommended_config.get("caching_enabled") is True

    def test_get_cached_recommendations(self, engine):
        """Test getting cached recommendations."""
        # Add to cache
        rec = OptimizationRecommendation(
            recommendation_id=uuid4(),
            organization_id="org-test",
            optimization_type=OptimizationType.COST_REDUCTION,
            title="Test",
            description="Test rec",
            confidence=ConfidenceLevel.MEDIUM
        )
        engine._recommendations_cache["org-test"] = [rec]

        # Retrieve
        cached = engine.get_cached_recommendations("org-test")
        assert len(cached) == 1
        assert cached[0].title == "Test"

        # Non-existent org returns empty
        empty = engine.get_cached_recommendations("org-nonexistent")
        assert len(empty) == 0


class TestOptimizationApplication:
    """Tests for applying optimizations."""

    @pytest.fixture
    def mock_db(self):
        db = AsyncMock()
        db.execute = AsyncMock()
        db.commit = AsyncMock()
        return db

    @pytest.fixture
    def engine(self, mock_db):
        return AutoOptimizationEngine(mock_db)

    @pytest.mark.asyncio
    async def test_apply_recommendation_requires_approval(self, engine):
        """Test that applying requires APPROVED status."""
        rec_id = uuid4()
        rec = OptimizationRecommendation(
            recommendation_id=rec_id,
            organization_id="org-123",
            optimization_type=OptimizationType.MODEL_DOWNGRADE,
            title="Test",
            description="Test",
            confidence=ConfidenceLevel.HIGH,
            status=OptimizationStatus.SUGGESTED  # Not approved
        )
        engine._recommendations_cache["org-123"] = [rec]

        result = await engine.apply_recommendation(rec_id, "admin-user")
        assert result is False  # Should fail because not approved

    @pytest.mark.asyncio
    async def test_apply_recommendation_not_found(self, engine):
        """Test applying non-existent recommendation."""
        result = await engine.apply_recommendation(uuid4(), "admin-user")
        assert result is False


class TestGetOptimizationEngine:
    """Tests for singleton pattern."""

    def test_get_returns_instance(self):
        """Test that get_optimization_engine returns an instance."""
        mock_db = AsyncMock()
        engine = get_optimization_engine(mock_db)
        assert isinstance(engine, AutoOptimizationEngine)

    def test_get_returns_same_instance_for_same_db(self):
        """Test singleton behavior with same db."""
        mock_db = AsyncMock()
        engine1 = get_optimization_engine(mock_db)
        engine2 = get_optimization_engine(mock_db)
        assert engine1 is engine2
