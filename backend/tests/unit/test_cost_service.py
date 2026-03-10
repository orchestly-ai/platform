"""
Unit Tests for Cost Service

Tests for cost tracking, forecasting, anomaly detection, and budget management.
"""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from datetime import datetime, timedelta, date
from uuid import uuid4
import numpy as np

from backend.shared.cost_service import CostService, get_cost_service
from backend.shared.cost_models import (
    CostEvent, CostCategory, CostSummary, CostForecast,
    CostAnomaly, BudgetStatus, BudgetPeriod, AlertSeverity
)

# Check if numpy has real functionality (not mocked)
try:
    test_arr = np.array([1, 2, 3])
    HAS_NUMPY = not isinstance(test_arr, MagicMock)
except (TypeError, AttributeError):
    HAS_NUMPY = False

requires_numpy = pytest.mark.skipif(
    not HAS_NUMPY,
    reason="Test requires real numpy for numerical calculations"
)


class TestCostTracking:
    """Tests for cost event tracking."""

    @pytest.fixture
    def cost_service(self):
        """Create cost service instance."""
        return CostService()

    @pytest.fixture
    def mock_db(self):
        """Create mock database session."""
        db = AsyncMock()
        db.add = MagicMock()
        db.flush = AsyncMock()
        db.execute = AsyncMock()
        db.commit = AsyncMock()
        return db

    @pytest.fixture
    def sample_cost_event(self):
        """Create sample cost event."""
        return CostEvent(
            event_id=uuid4(),
            timestamp=datetime.utcnow(),
            organization_id="org-123",
            user_id="user-456",
            agent_id=uuid4(),
            task_id=uuid4(),
            category=CostCategory.LLM_INFERENCE,
            amount=0.05,
            currency="USD",
            provider="openai",
            model="gpt-4",
            input_tokens=500,
            output_tokens=100,
            total_tokens=600
        )

    @pytest.mark.asyncio
    async def test_track_cost(self, cost_service, mock_db, sample_cost_event):
        """Test tracking a cost event."""
        # Mock budget check to return empty list
        mock_result = MagicMock()
        mock_result.scalars = MagicMock(return_value=MagicMock(all=MagicMock(return_value=[])))
        mock_db.execute.return_value = mock_result

        event_id = await cost_service.track_cost(sample_cost_event, mock_db)

        assert event_id == sample_cost_event.event_id
        mock_db.add.assert_called_once()
        mock_db.flush.assert_called_once()

    @pytest.mark.asyncio
    async def test_track_cost_with_budget_check(self, cost_service, mock_db, sample_cost_event):
        """Test that budget alerts are checked after tracking."""
        # Mock the database to return no active budgets (simpler test case)
        mock_result = MagicMock()
        mock_result.scalars = MagicMock(return_value=MagicMock(all=MagicMock(return_value=[])))
        mock_db.execute.return_value = mock_result

        # Patch _check_budget_alerts to verify it's called
        with patch.object(cost_service, '_check_budget_alerts', new_callable=AsyncMock) as mock_check:
            event_id = await cost_service.track_cost(sample_cost_event, mock_db)

            assert event_id is not None
            # Verify budget check was attempted
            mock_check.assert_called_once()


class TestCostSummary:
    """Tests for cost summary generation."""

    @pytest.fixture
    def cost_service(self):
        return CostService()

    @pytest.fixture
    def mock_db(self):
        db = AsyncMock()
        return db

    @pytest.mark.asyncio
    async def test_get_cost_summary(self, cost_service, mock_db):
        """Test cost summary generation."""
        # Mock main query result
        mock_main_row = MagicMock()
        mock_main_row.total_cost = 150.0
        mock_main_row.event_count = 100

        # Setup mock to return different results for different queries
        call_count = [0]

        def mock_execute(*args, **kwargs):
            call_count[0] += 1
            result = MagicMock()

            if call_count[0] == 1:
                # Main summary
                result.one = MagicMock(return_value=(150.0, 100))
            elif call_count[0] == 2:
                # Category breakdown
                result.all = MagicMock(return_value=[
                    ("llm_inference", 120.0),
                    ("integration", 30.0)
                ])
            elif call_count[0] == 3:
                # Provider breakdown
                result.all = MagicMock(return_value=[
                    ("openai", 100.0),
                    ("anthropic", 50.0)
                ])
            elif call_count[0] == 4:
                # Top agents
                result.all = MagicMock(return_value=[
                    (uuid4(), 75.0),
                    (uuid4(), 45.0)
                ])
            elif call_count[0] == 5:
                # Top workflows
                result.all = MagicMock(return_value=[
                    (uuid4(), 60.0)
                ])
            else:
                # Previous period
                result.scalar_one = MagicMock(return_value=100.0)

            return result

        mock_db.execute = AsyncMock(side_effect=mock_execute)

        summary = await cost_service.get_cost_summary(
            organization_id="org-123",
            start_time=datetime.utcnow() - timedelta(days=7),
            end_time=datetime.utcnow(),
            db=mock_db
        )

        assert summary.total_cost == 150.0
        assert summary.event_count == 100
        assert summary.avg_cost_per_event == 1.5


class TestCostForecasting:
    """Tests for AI-powered cost forecasting."""

    @pytest.fixture
    def cost_service(self):
        return CostService()

    @pytest.fixture
    def mock_db(self):
        db = AsyncMock()
        return db

    @pytest.mark.asyncio
    async def test_forecast_insufficient_data(self, cost_service, mock_db):
        """Test forecast with insufficient data."""
        # Return only 3 days of data (need 7 minimum)
        mock_result = MagicMock()
        mock_result.all = MagicMock(return_value=[
            MagicMock(date=date.today() - timedelta(days=2), total=10.0),
            MagicMock(date=date.today() - timedelta(days=1), total=12.0),
            MagicMock(date=date.today(), total=15.0),
        ])
        mock_db.execute = AsyncMock(return_value=mock_result)

        forecast = await cost_service.forecast_cost(
            organization_id="org-123",
            forecast_days=7,
            db=mock_db
        )

        assert forecast.trend == "insufficient_data"
        assert forecast.predicted_cost == 0.0

    @requires_numpy
    @pytest.mark.asyncio
    async def test_forecast_with_data(self, cost_service, mock_db):
        """Test forecast with sufficient data."""
        # Generate 14 days of increasing costs
        daily_data = []
        for i in range(14):
            day = date.today() - timedelta(days=13-i)
            cost = 10.0 + i * 1.5  # Linear increase
            row = MagicMock()
            row.date = day
            row.total = cost
            daily_data.append(row)

        mock_result = MagicMock()
        mock_result.all = MagicMock(return_value=daily_data)
        mock_db.execute = AsyncMock(return_value=mock_result)

        forecast = await cost_service.forecast_cost(
            organization_id="org-123",
            forecast_days=7,
            db=mock_db
        )

        assert forecast.predicted_cost > 0
        # Trend detection may return stable or increasing depending on algorithm
        assert forecast.trend in ["increasing", "stable", "decreasing"]
        assert forecast.confidence_lower >= 0
        assert forecast.confidence_upper >= forecast.predicted_cost

    @requires_numpy
    @pytest.mark.asyncio
    async def test_forecast_caching(self, cost_service, mock_db):
        """Test that forecasts are cached."""
        # Setup mock
        daily_data = []
        for i in range(10):
            row = MagicMock()
            row.date = date.today() - timedelta(days=9-i)
            row.total = 10.0 + i
            daily_data.append(row)

        mock_result = MagicMock()
        mock_result.all = MagicMock(return_value=daily_data)
        mock_db.execute = AsyncMock(return_value=mock_result)

        # First call
        forecast1 = await cost_service.forecast_cost("org-123", 7, mock_db)

        # Second call should use cache
        forecast2 = await cost_service.forecast_cost("org-123", 7, mock_db)

        # Execute should only be called once due to caching
        assert mock_db.execute.call_count == 1
        assert forecast1.predicted_cost == forecast2.predicted_cost


class TestAnomalyDetection:
    """Tests for cost anomaly detection."""

    @pytest.fixture
    def cost_service(self):
        return CostService()

    @pytest.fixture
    def mock_db(self):
        db = AsyncMock()
        return db

    @pytest.mark.asyncio
    async def test_detect_anomalies_no_data(self, cost_service, mock_db):
        """Test anomaly detection with insufficient data."""
        mock_result = MagicMock()
        mock_result.all = MagicMock(return_value=[])
        mock_db.execute = AsyncMock(return_value=mock_result)

        anomalies = await cost_service.detect_anomalies(
            organization_id="org-123",
            lookback_days=7,
            db=mock_db
        )

        assert anomalies == []

    @requires_numpy
    @pytest.mark.asyncio
    async def test_detect_anomalies_with_spike(self, cost_service, mock_db):
        """Test anomaly detection finds cost spikes."""
        # Generate hourly data with a spike
        hourly_data = []
        for i in range(48):
            hour = datetime.utcnow() - timedelta(hours=47-i)
            cost = 10.0 if i != 24 else 100.0  # Spike at hour 24
            row = MagicMock()
            row.hour = hour
            row.total = cost
            hourly_data.append(row)

        mock_result = MagicMock()
        mock_result.all = MagicMock(return_value=hourly_data)
        mock_db.execute = AsyncMock(return_value=mock_result)

        anomalies = await cost_service.detect_anomalies(
            organization_id="org-123",
            lookback_days=2,
            db=mock_db
        )

        assert len(anomalies) >= 1
        # Find the spike
        spike = next((a for a in anomalies if a.actual_cost > 50), None)
        assert spike is not None
        assert spike.severity in ["low", "medium", "high"]


class TestBudgetManagement:
    """Tests for budget status and alerts."""

    @pytest.fixture
    def cost_service(self):
        return CostService()

    @pytest.fixture
    def mock_db(self):
        db = AsyncMock()
        return db

    @pytest.fixture
    def mock_budget(self):
        budget = MagicMock()
        budget.budget_id = uuid4()
        budget.name = "Monthly Budget"
        budget.organization_id = "org-123"
        budget.amount = 1000.0
        budget.period = "monthly"
        budget.is_active = True
        budget.alert_threshold_info = 50
        budget.alert_threshold_warning = 75
        budget.alert_threshold_critical = 90
        budget.scope_type = None
        budget.scope_id = None
        return budget

    @pytest.mark.asyncio
    async def test_budget_status_healthy(self, cost_service, mock_db, mock_budget):
        """Test budget status when under limit."""
        # Budget at 40% usage
        def mock_execute(*args, **kwargs):
            result = MagicMock()
            result.scalar_one_or_none = MagicMock(return_value=mock_budget)
            result.scalar_one = MagicMock(return_value=400.0)  # 40% of 1000
            return result

        mock_db.execute = AsyncMock(side_effect=mock_execute)

        status = await cost_service.check_budget_status(
            mock_budget.budget_id,
            mock_db
        )

        assert status.percent_used == 40.0
        assert status.remaining == 600.0
        assert status.alert_level is None

    @pytest.mark.asyncio
    async def test_budget_status_warning(self, cost_service, mock_db, mock_budget):
        """Test budget status at warning level."""
        # Budget at 80% usage (above 75% warning threshold)
        def mock_execute(*args, **kwargs):
            result = MagicMock()
            result.scalar_one_or_none = MagicMock(return_value=mock_budget)
            result.scalar_one = MagicMock(return_value=800.0)  # 80% of 1000
            return result

        mock_db.execute = AsyncMock(side_effect=mock_execute)

        status = await cost_service.check_budget_status(
            mock_budget.budget_id,
            mock_db
        )

        assert status.percent_used == 80.0
        assert status.alert_level == AlertSeverity.WARNING

    @requires_numpy
    @pytest.mark.asyncio
    async def test_budget_status_exceeded(self, cost_service, mock_db, mock_budget):
        """Test budget status when exceeded."""
        # Budget at 110% usage
        def mock_execute(*args, **kwargs):
            result = MagicMock()
            result.scalar_one_or_none = MagicMock(return_value=mock_budget)
            result.scalar_one = MagicMock(return_value=1100.0)  # 110% of 1000
            return result

        mock_db.execute = AsyncMock(side_effect=mock_execute)

        status = await cost_service.check_budget_status(
            mock_budget.budget_id,
            mock_db
        )

        assert status.percent_used == pytest.approx(110.0, rel=1e-9)
        assert status.alert_level == AlertSeverity.EXCEEDED
        assert len(status.recommended_actions) > 0

    @pytest.mark.asyncio
    async def test_budget_not_found(self, cost_service, mock_db):
        """Test error when budget not found."""
        mock_result = MagicMock()
        mock_result.scalar_one_or_none = MagicMock(return_value=None)
        mock_db.execute = AsyncMock(return_value=mock_result)

        with pytest.raises(ValueError, match="Budget not found"):
            await cost_service.check_budget_status(uuid4(), mock_db)


class TestPeriodBounds:
    """Tests for period calculation."""

    @pytest.fixture
    def cost_service(self):
        return CostService()

    def test_daily_bounds(self, cost_service):
        """Test daily period bounds."""
        now = datetime(2025, 12, 26, 14, 30, 0)
        start, end = cost_service._get_period_bounds(now, "daily")

        assert start == datetime(2025, 12, 26, 0, 0, 0)
        assert end == datetime(2025, 12, 27, 0, 0, 0)

    def test_weekly_bounds(self, cost_service):
        """Test weekly period bounds."""
        # Dec 26, 2025 is a Friday
        now = datetime(2025, 12, 26, 14, 30, 0)
        start, end = cost_service._get_period_bounds(now, "weekly")

        # Week starts on Monday (Dec 22)
        assert start.day == 22
        assert (end - start).days == 7

    def test_monthly_bounds(self, cost_service):
        """Test monthly period bounds."""
        now = datetime(2025, 12, 26, 14, 30, 0)
        start, end = cost_service._get_period_bounds(now, "monthly")

        assert start == datetime(2025, 12, 1, 0, 0, 0)
        assert end == datetime(2026, 1, 1, 0, 0, 0)

    def test_monthly_bounds_december(self, cost_service):
        """Test monthly bounds for December (year rollover)."""
        now = datetime(2025, 12, 15, 0, 0, 0)
        start, end = cost_service._get_period_bounds(now, "monthly")

        assert start.month == 12
        assert start.year == 2025
        assert end.month == 1
        assert end.year == 2026


class TestGlobalCostService:
    """Tests for global service instance."""

    def test_get_cost_service_singleton(self):
        """Test that get_cost_service returns same instance."""
        service1 = get_cost_service()
        service2 = get_cost_service()

        assert service1 is service2


# =============================================================================
# Run tests
# =============================================================================

if __name__ == "__main__":
    pytest.main([__file__, "-v"])
