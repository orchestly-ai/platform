#!/usr/bin/env python3
"""
Tests for BYOK Gateway and Quota Guard

Session 2.2: BYOK Gateway
- Key Vault encryption/decryption
- Customer API key management
- Quota checking and rate limiting
- Usage tracking and spend reports
- Quota Guard sliding windows
- Budget management and alerts
"""

import pytest
import asyncio
from datetime import datetime, timedelta
from uuid import uuid4, UUID

from backend.shared.byok_gateway import (
    BYOKGateway,
    KeyVault,
    KeyProvider,
    KeyStatus,
    CustomerTier,
    CustomerAPIKey,
    UsageBucket,
    QuotaCheckResult,
    SpendReport,
    DEFAULT_TIERS,
    get_byok_gateway,
    reset_byok_gateway,
)

from backend.shared.quota_guard import (
    QuotaGuard,
    QuotaLimit,
    BudgetConfig,
    UsageWindow,
    QuotaAlert,
    ThrottleDecision,
    ThrottleAction,
    AlertSeverity,
    UsagePrediction,
    get_quota_guard,
    reset_quota_guard,
)


# ============================================================================
# Key Vault Tests
# ============================================================================

class TestKeyVault:
    """Tests for KeyVault encryption/decryption."""

    def test_encrypt_decrypt_roundtrip(self):
        """Test that encryption and decryption are reversible."""
        vault = KeyVault(encryption_key="test-encryption-key")
        original_key = "sk-proj-abc123xyz789"

        encrypted = vault.encrypt_key(original_key)
        decrypted = vault.decrypt_key(encrypted)

        assert decrypted == original_key
        assert encrypted != original_key

    def test_encrypt_produces_different_output(self):
        """Test that encrypted key differs from original."""
        vault = KeyVault()
        original_key = "sk-test-key"

        encrypted = vault.encrypt_key(original_key)

        assert encrypted != original_key
        assert len(encrypted) > 0

    def test_different_keys_produce_different_encryptions(self):
        """Test that different encryption keys produce different results."""
        vault1 = KeyVault(encryption_key="key1")
        vault2 = KeyVault(encryption_key="key2")
        original = "sk-original"

        encrypted1 = vault1.encrypt_key(original)
        encrypted2 = vault2.encrypt_key(original)

        assert encrypted1 != encrypted2

    def test_key_prefix_short_key(self):
        """Test key prefix for short keys."""
        vault = KeyVault()

        prefix = vault.get_key_prefix("sk-abc")

        assert prefix == "sk-a..."

    def test_key_prefix_long_key(self):
        """Test key prefix for long keys."""
        vault = KeyVault()

        prefix = vault.get_key_prefix("sk-proj-verylongapikey123456789")

        assert prefix == "sk-proj-very..."
        assert len(prefix) == 15  # 12 chars + "..."


# ============================================================================
# Customer Tier Tests
# ============================================================================

class TestCustomerTier:
    """Tests for CustomerTier configuration."""

    def test_tier_to_dict(self):
        """Test tier serialization."""
        tier = CustomerTier(
            tier_name="premium",
            rate_limit_rpm=5000,
            rate_limit_tpm=200000,
            rate_limit_rpd=100000,
            pricing_per_1m_input=3.0,
            pricing_per_1m_output=15.0,
        )

        result = tier.to_dict()

        assert result["tier_name"] == "premium"
        assert result["rate_limit_rpm"] == 5000
        assert result["rate_limit_tpm"] == 200000
        assert result["rate_limit_rpd"] == 100000
        assert result["pricing_per_1m_input"] == 3.0

    def test_default_tiers_exist(self):
        """Test that default tiers are defined for each provider."""
        assert KeyProvider.OPENAI in DEFAULT_TIERS
        assert KeyProvider.ANTHROPIC in DEFAULT_TIERS
        assert KeyProvider.DEEPSEEK in DEFAULT_TIERS

    def test_openai_tier_levels(self):
        """Test OpenAI tier configurations."""
        openai_tiers = DEFAULT_TIERS[KeyProvider.OPENAI]

        assert "tier_1" in openai_tiers
        assert "tier_5" in openai_tiers
        assert openai_tiers["tier_1"].rate_limit_rpm < openai_tiers["tier_5"].rate_limit_rpm


# ============================================================================
# BYOK Gateway Tests
# ============================================================================

class TestBYOKGateway:
    """Tests for BYOKGateway functionality."""

    @pytest.fixture
    def gateway(self):
        """Create a fresh gateway instance."""
        return BYOKGateway(encryption_key="test-key")

    @pytest.fixture
    def org_id(self):
        """Create a test organization ID."""
        return uuid4()

    @pytest.mark.asyncio
    async def test_register_key_basic(self, gateway, org_id):
        """Test basic key registration."""
        api_key = "sk-test-apikey-12345"

        result = await gateway.register_key(
            org_id=org_id,
            provider=KeyProvider.OPENAI,
            api_key=api_key,
            tier_name="tier_1",
        )

        assert result.org_id == org_id
        assert result.provider == KeyProvider.OPENAI
        assert result.status == KeyStatus.ACTIVE
        assert result.key_prefix == "sk-test-apik..."
        assert result.key_id is not None

    @pytest.mark.asyncio
    async def test_register_key_with_custom_tier(self, gateway, org_id):
        """Test key registration with custom tier."""
        custom_tier = CustomerTier(
            tier_name="enterprise",
            rate_limit_rpm=10000,
            rate_limit_tpm=500000,
            pricing_per_1m_input=2.5,
            pricing_per_1m_output=12.5,
        )

        result = await gateway.register_key(
            org_id=org_id,
            provider=KeyProvider.ANTHROPIC,
            api_key="sk-ant-custom",
            custom_tier=custom_tier,
        )

        assert result.tier.tier_name == "enterprise"
        assert result.tier.rate_limit_rpm == 10000

    @pytest.mark.asyncio
    async def test_get_key(self, gateway, org_id):
        """Test retrieving a registered key."""
        key = await gateway.register_key(
            org_id=org_id,
            provider=KeyProvider.OPENAI,
            api_key="sk-test-key",
        )

        result = await gateway.get_key(key.key_id)

        assert result is not None
        assert result.key_id == key.key_id

    @pytest.mark.asyncio
    async def test_get_key_not_found(self, gateway):
        """Test getting a non-existent key."""
        result = await gateway.get_key(uuid4())

        assert result is None

    @pytest.mark.asyncio
    async def test_get_keys_by_org(self, gateway, org_id):
        """Test retrieving all keys for an organization."""
        # Register multiple keys
        await gateway.register_key(org_id, KeyProvider.OPENAI, "key1")
        await gateway.register_key(org_id, KeyProvider.ANTHROPIC, "key2")

        other_org = uuid4()
        await gateway.register_key(other_org, KeyProvider.OPENAI, "key3")

        result = await gateway.get_keys_by_org(org_id)

        assert len(result) == 2
        assert all(k.org_id == org_id for k in result)

    @pytest.mark.asyncio
    async def test_get_decrypted_key(self, gateway, org_id):
        """Test decrypting a registered key."""
        original_key = "sk-original-secret-key"
        key = await gateway.register_key(org_id, KeyProvider.OPENAI, original_key)

        result = await gateway.get_decrypted_key(key.key_id)

        assert result == original_key

    @pytest.mark.asyncio
    async def test_get_decrypted_key_inactive(self, gateway, org_id):
        """Test that inactive keys cannot be decrypted."""
        key = await gateway.register_key(org_id, KeyProvider.OPENAI, "secret")
        await gateway.update_key_status(key.key_id, KeyStatus.INACTIVE)

        result = await gateway.get_decrypted_key(key.key_id)

        assert result is None

    @pytest.mark.asyncio
    async def test_update_key_status(self, gateway, org_id):
        """Test updating key status."""
        key = await gateway.register_key(org_id, KeyProvider.OPENAI, "key")

        result = await gateway.update_key_status(key.key_id, KeyStatus.EXPIRED)

        assert result is True
        updated = await gateway.get_key(key.key_id)
        assert updated.status == KeyStatus.EXPIRED

    @pytest.mark.asyncio
    async def test_update_key_status_not_found(self, gateway):
        """Test updating status for non-existent key."""
        result = await gateway.update_key_status(uuid4(), KeyStatus.INACTIVE)

        assert result is False

    @pytest.mark.asyncio
    async def test_check_quota_allowed(self, gateway, org_id):
        """Test quota check when within limits."""
        key = await gateway.register_key(org_id, KeyProvider.OPENAI, "key")

        result = await gateway.check_quota(key.key_id, estimated_tokens=1000)

        assert result.allowed is True
        assert result.remaining_rpm > 0
        assert result.remaining_tpm > 0

    @pytest.mark.asyncio
    async def test_check_quota_key_not_found(self, gateway):
        """Test quota check for non-existent key."""
        result = await gateway.check_quota(uuid4())

        assert result.allowed is False
        assert "not found" in result.reason

    @pytest.mark.asyncio
    async def test_check_quota_key_inactive(self, gateway, org_id):
        """Test quota check for inactive key."""
        key = await gateway.register_key(org_id, KeyProvider.OPENAI, "key")
        await gateway.update_key_status(key.key_id, KeyStatus.INACTIVE)

        result = await gateway.check_quota(key.key_id)

        assert result.allowed is False
        assert "inactive" in result.reason.lower()

    @pytest.mark.asyncio
    async def test_check_quota_rpm_exceeded(self, gateway, org_id):
        """Test quota check when RPM limit exceeded."""
        # Create key with low RPM limit
        tier = CustomerTier("test", rate_limit_rpm=5, rate_limit_tpm=100000)
        key = await gateway.register_key(org_id, KeyProvider.OPENAI, "key", custom_tier=tier)

        # Record usage to exceed limit
        for _ in range(10):
            await gateway.record_usage(key.key_id, 100, 100)

        result = await gateway.check_quota(key.key_id)

        assert result.allowed is False
        assert "requests per minute" in result.reason

    @pytest.mark.asyncio
    async def test_check_quota_tpm_exceeded(self, gateway, org_id):
        """Test quota check when TPM limit would be exceeded."""
        # Create key with low TPM limit
        tier = CustomerTier("test", rate_limit_rpm=1000, rate_limit_tpm=1000)
        key = await gateway.register_key(org_id, KeyProvider.OPENAI, "key", custom_tier=tier)

        # Record some token usage
        await gateway.record_usage(key.key_id, 500, 400)

        # Try to request more tokens than remaining
        result = await gateway.check_quota(key.key_id, estimated_tokens=500)

        assert result.allowed is False
        assert "token limit" in result.reason

    @pytest.mark.asyncio
    async def test_check_quota_throttle_recommended(self, gateway, org_id):
        """Test that throttle is recommended when approaching limits."""
        tier = CustomerTier("test", rate_limit_rpm=100, rate_limit_tpm=10000)
        key = await gateway.register_key(org_id, KeyProvider.OPENAI, "key", custom_tier=tier)

        # Use 75% of limit (triggering 80% threshold check after adding request)
        for _ in range(75):
            await gateway.record_usage(key.key_id, 10, 10)

        result = await gateway.check_quota(key.key_id, estimated_tokens=100)

        assert result.allowed is True
        assert result.throttle_recommended is True

    @pytest.mark.asyncio
    async def test_record_usage_basic(self, gateway, org_id):
        """Test basic usage recording."""
        key = await gateway.register_key(org_id, KeyProvider.OPENAI, "key")

        result = await gateway.record_usage(
            key.key_id,
            input_tokens=100,
            output_tokens=200,
        )

        assert result.requests_count == 1
        assert result.tokens_input == 100
        assert result.tokens_output == 200

    @pytest.mark.asyncio
    async def test_record_usage_accumulates(self, gateway, org_id):
        """Test that usage accumulates in the same bucket."""
        key = await gateway.register_key(org_id, KeyProvider.OPENAI, "key")

        await gateway.record_usage(key.key_id, 100, 100)
        result = await gateway.record_usage(key.key_id, 200, 200)

        assert result.requests_count == 2
        assert result.tokens_input == 300
        assert result.tokens_output == 300

    @pytest.mark.asyncio
    async def test_record_usage_with_errors(self, gateway, org_id):
        """Test recording failed requests."""
        key = await gateway.register_key(org_id, KeyProvider.OPENAI, "key")

        result = await gateway.record_usage(
            key.key_id, 100, 0, success=False, rate_limited=True
        )

        assert result.errors_count == 1
        assert result.rate_limit_hits == 1

    @pytest.mark.asyncio
    async def test_record_usage_key_not_found(self, gateway):
        """Test recording usage for non-existent key."""
        with pytest.raises(ValueError) as exc:
            await gateway.record_usage(uuid4(), 100, 100)

        assert "not found" in str(exc.value)

    @pytest.mark.asyncio
    async def test_get_spend_report_basic(self, gateway, org_id):
        """Test basic spend report generation."""
        tier = CustomerTier(
            "test", 1000, 100000,
            pricing_per_1m_input=3.0,
            pricing_per_1m_output=15.0,
        )
        key = await gateway.register_key(org_id, KeyProvider.OPENAI, "key", custom_tier=tier)

        await gateway.record_usage(key.key_id, 1_000_000, 500_000)

        # Use date range that includes the current hour bucket
        now = datetime.utcnow()
        report = await gateway.get_spend_report(
            org_id,
            start_date=now - timedelta(hours=1),
            end_date=now + timedelta(hours=2),
        )

        assert report.org_id == org_id
        assert report.total_requests == 1
        assert report.total_input_tokens == 1_000_000
        assert report.total_output_tokens == 500_000
        assert report.total_cost == 3.0 + 7.5  # $3 input + $7.5 output

    @pytest.mark.asyncio
    async def test_get_spend_report_multiple_keys(self, gateway, org_id):
        """Test spend report with multiple keys."""
        tier = CustomerTier("test", 1000, 100000, pricing_per_1m_input=1.0, pricing_per_1m_output=2.0)
        key1 = await gateway.register_key(org_id, KeyProvider.OPENAI, "key1", custom_tier=tier)
        key2 = await gateway.register_key(org_id, KeyProvider.ANTHROPIC, "key2", custom_tier=tier)

        await gateway.record_usage(key1.key_id, 1_000_000, 500_000)
        await gateway.record_usage(key2.key_id, 500_000, 250_000)

        # Use date range that includes current hour bucket
        now = datetime.utcnow()
        report = await gateway.get_spend_report(
            org_id,
            start_date=now - timedelta(hours=1),
            end_date=now + timedelta(hours=2),
        )

        assert report.total_requests == 2
        assert "openai" in report.cost_by_provider
        assert "anthropic" in report.cost_by_provider

    @pytest.mark.asyncio
    async def test_get_spend_report_burn_rate(self, gateway, org_id):
        """Test that burn rate is calculated."""
        tier = CustomerTier("test", 1000, 100000, pricing_per_1m_input=1.0, pricing_per_1m_output=1.0)
        key = await gateway.register_key(org_id, KeyProvider.OPENAI, "key", custom_tier=tier)

        await gateway.record_usage(key.key_id, 1_000_000, 0)

        # Use date range that includes current hour bucket
        now = datetime.utcnow()
        report = await gateway.get_spend_report(
            org_id,
            start_date=now - timedelta(hours=1),
            end_date=now + timedelta(hours=2),
        )

        assert report.burn_rate_per_hour > 0
        assert report.projected_monthly_cost > 0

    @pytest.mark.asyncio
    async def test_validate_key_active(self, gateway, org_id):
        """Test validating an active key."""
        key = await gateway.register_key(org_id, KeyProvider.OPENAI, "key")

        result = await gateway.validate_key(key.key_id)

        assert result is True
        updated = await gateway.get_key(key.key_id)
        assert updated.last_validated_at is not None

    @pytest.mark.asyncio
    async def test_validate_key_not_found(self, gateway):
        """Test validating non-existent key."""
        result = await gateway.validate_key(uuid4())

        assert result is False

    @pytest.mark.asyncio
    async def test_rotate_key(self, gateway, org_id):
        """Test rotating a key."""
        key = await gateway.register_key(org_id, KeyProvider.OPENAI, "old-key")
        new_key = "sk-new-rotated-key"

        result = await gateway.rotate_key(key.key_id, new_key)

        # Key prefix is first 12 chars + "..." = "sk-new-rotat..."
        assert result.key_prefix == "sk-new-rotat..."
        decrypted = await gateway.get_decrypted_key(key.key_id)
        assert decrypted == new_key

    @pytest.mark.asyncio
    async def test_rotate_key_not_found(self, gateway):
        """Test rotating non-existent key."""
        with pytest.raises(ValueError):
            await gateway.rotate_key(uuid4(), "new-key")

    @pytest.mark.asyncio
    async def test_delete_key(self, gateway, org_id):
        """Test deleting a key."""
        key = await gateway.register_key(org_id, KeyProvider.OPENAI, "key")

        result = await gateway.delete_key(key.key_id)

        assert result is True
        assert await gateway.get_key(key.key_id) is None

    @pytest.mark.asyncio
    async def test_delete_key_not_found(self, gateway):
        """Test deleting non-existent key."""
        result = await gateway.delete_key(uuid4())

        assert result is False

    @pytest.mark.asyncio
    async def test_get_all_keys(self, gateway, org_id):
        """Test getting all registered keys."""
        await gateway.register_key(org_id, KeyProvider.OPENAI, "key1")
        await gateway.register_key(org_id, KeyProvider.ANTHROPIC, "key2")

        result = gateway.get_all_keys()

        assert len(result) == 2

    @pytest.mark.asyncio
    async def test_get_usage_history(self, gateway, org_id):
        """Test getting usage history."""
        key = await gateway.register_key(org_id, KeyProvider.OPENAI, "key")

        await gateway.record_usage(key.key_id, 100, 100)
        await gateway.record_usage(key.key_id, 200, 200)

        history = await gateway.get_usage_history(key.key_id, hours=24)

        assert len(history) == 1  # Same hour bucket
        assert history[0].requests_count == 2

    def test_customer_api_key_to_dict(self, gateway):
        """Test CustomerAPIKey serialization."""
        tier = CustomerTier("test", 1000, 100000)
        key = CustomerAPIKey(
            key_id=uuid4(),
            org_id=uuid4(),
            provider=KeyProvider.OPENAI,
            encrypted_key="encrypted",
            key_prefix="sk-...",
            tier=tier,
        )

        result = key.to_dict()

        assert "key_id" in result
        assert "provider" in result
        assert result["provider"] == "openai"

    def test_usage_bucket_to_dict(self):
        """Test UsageBucket serialization."""
        now = datetime.utcnow()
        bucket = UsageBucket(
            bucket_id=uuid4(),
            key_id=uuid4(),
            org_id=uuid4(),
            period_start=now,
            period_end=now + timedelta(hours=1),
            requests_count=10,
            tokens_input=1000,
            tokens_output=500,
        )

        result = bucket.to_dict()

        assert result["requests_count"] == 10
        assert "period_start" in result

    def test_quota_check_result_to_dict(self):
        """Test QuotaCheckResult serialization."""
        result = QuotaCheckResult(
            allowed=True,
            current_rpm=50,
            remaining_rpm=450,
        )

        output = result.to_dict()

        assert output["allowed"] is True
        assert output["current_rpm"] == 50

    def test_spend_report_to_dict(self):
        """Test SpendReport serialization."""
        report = SpendReport(
            org_id=uuid4(),
            period_start=datetime.utcnow() - timedelta(days=30),
            period_end=datetime.utcnow(),
            total_requests=100,
            total_input_tokens=1000000,
            total_output_tokens=500000,
            total_cost=10.50,
        )

        result = report.to_dict()

        assert result["total_cost"] == 10.50
        assert "org_id" in result


# ============================================================================
# Quota Guard Tests
# ============================================================================

class TestQuotaGuard:
    """Tests for QuotaGuard functionality."""

    @pytest.fixture
    def guard(self):
        """Create a fresh quota guard instance."""
        return QuotaGuard()

    @pytest.fixture
    def entity_id(self):
        """Create a test entity ID."""
        return uuid4()

    @pytest.fixture
    def org_id(self):
        """Create a test organization ID."""
        return uuid4()

    @pytest.mark.asyncio
    async def test_check_quota_allowed(self, guard, entity_id):
        """Test quota check when within limits."""
        result = await guard.check_quota(entity_id, request_value=1)

        assert result.allowed is True
        assert result.action == ThrottleAction.ALLOW

    @pytest.mark.asyncio
    async def test_check_quota_with_limits(self, guard, entity_id):
        """Test quota check with custom limits."""
        limits = [QuotaLimit("rpm", 100, 60)]
        guard.set_limits(entity_id, limits)

        result = await guard.check_quota(entity_id, request_value=1)

        assert result.allowed is True

    @pytest.mark.asyncio
    async def test_check_quota_soft_limit_warning(self, guard, entity_id):
        """Test that soft limit generates warning."""
        limits = [QuotaLimit("rpm", 10, 60, soft_limit_percent=0.5)]
        guard.set_limits(entity_id, limits)

        # Record 60% usage
        for _ in range(6):
            await guard.record_usage(entity_id, request_value=1)

        result = await guard.check_quota(entity_id, request_value=1)

        assert result.allowed is True
        assert len(result.alerts) > 0
        assert result.alerts[0].severity == AlertSeverity.WARNING

    @pytest.mark.asyncio
    async def test_check_quota_hard_limit_reject(self, guard, entity_id):
        """Test that hard limit causes rejection."""
        limits = [QuotaLimit("rpm", 10, 60, burst_multiplier=1.0)]
        guard.set_limits(entity_id, limits)

        # Record 100% usage
        for _ in range(10):
            await guard.record_usage(entity_id, request_value=1)

        result = await guard.check_quota(entity_id, request_value=1)

        assert result.allowed is False
        assert result.action == ThrottleAction.REJECT
        assert "exceeded" in result.reason

    @pytest.mark.asyncio
    async def test_check_quota_burst_allowed(self, guard, entity_id):
        """Test that burst capacity is allowed."""
        limits = [QuotaLimit("rpm", 10, 60, burst_multiplier=1.5)]
        guard.set_limits(entity_id, limits)

        # Record 100% usage (10 requests)
        for _ in range(10):
            await guard.record_usage(entity_id, request_value=1)

        # Should allow burst up to 15 (150%)
        result = await guard.check_quota(entity_id, request_value=1)

        assert result.allowed is True
        assert "burst" in " ".join(result.recommendations).lower()

    @pytest.mark.asyncio
    async def test_check_quota_token_limits(self, guard, entity_id):
        """Test token-based limits."""
        # Disable burst by setting burst_multiplier=1.0
        limits = [QuotaLimit("tpm", 1000, 60, burst_multiplier=1.0)]
        guard.set_limits(entity_id, limits)

        # Record 900 tokens
        await guard.record_usage(entity_id, request_tokens=900)

        # Try to add 200 more tokens (would be 1100, exceeding 1000 limit)
        result = await guard.check_quota(entity_id, request_tokens=200)

        assert result.allowed is False
        assert "exceeded" in result.reason

    @pytest.mark.asyncio
    async def test_check_quota_with_budget(self, guard, entity_id, org_id):
        """Test quota check with budget constraints."""
        budget = BudgetConfig(org_id=org_id, daily_budget=10.0)
        guard.set_budget(budget)

        result = await guard.check_quota(
            entity_id,
            estimated_cost=1.0,
            org_id=org_id,
        )

        assert result.allowed is True

    @pytest.mark.asyncio
    async def test_check_quota_budget_exceeded(self, guard, entity_id, org_id):
        """Test quota check when budget is exceeded."""
        budget = BudgetConfig(org_id=org_id, daily_budget=1.0, hard_stop_at=1.0)
        guard.set_budget(budget)

        # Record $1.50 in spending
        await guard.record_usage(entity_id, cost=1.5, org_id=org_id)

        result = await guard.check_quota(
            entity_id,
            estimated_cost=0.1,
            org_id=org_id,
        )

        assert result.allowed is False
        assert "budget" in result.reason.lower()

    @pytest.mark.asyncio
    async def test_check_quota_budget_warning(self, guard, entity_id, org_id):
        """Test budget warning alerts."""
        budget = BudgetConfig(
            org_id=org_id,
            daily_budget=10.0,
            alert_thresholds=[0.5, 0.8],
        )
        guard.set_budget(budget)

        # Spend $6 (60%)
        await guard.record_usage(entity_id, cost=6.0, org_id=org_id)

        result = await guard.check_quota(
            entity_id,
            estimated_cost=0.1,
            org_id=org_id,
        )

        assert result.allowed is True
        assert len(result.alerts) > 0

    @pytest.mark.asyncio
    async def test_record_usage_basic(self, guard, entity_id):
        """Test basic usage recording."""
        limits = [QuotaLimit("rpm", 100, 60)]
        guard.set_limits(entity_id, limits)

        await guard.record_usage(entity_id, request_value=1)

        usage = guard.get_current_usage(entity_id)
        assert usage["rpm"] == 1

    @pytest.mark.asyncio
    async def test_record_usage_accumulates(self, guard, entity_id):
        """Test that usage accumulates."""
        limits = [QuotaLimit("rpm", 100, 60)]
        guard.set_limits(entity_id, limits)

        await guard.record_usage(entity_id, request_value=1)
        await guard.record_usage(entity_id, request_value=1)
        await guard.record_usage(entity_id, request_value=1)

        usage = guard.get_current_usage(entity_id)
        assert usage["rpm"] == 3

    @pytest.mark.asyncio
    async def test_record_usage_with_cost(self, guard, entity_id, org_id):
        """Test recording usage with cost tracking."""
        await guard.record_usage(entity_id, cost=5.0, org_id=org_id)

        spend = guard.get_spend(org_id, period="daily")
        assert spend == 5.0

    @pytest.mark.asyncio
    async def test_predict_usage_no_data(self, guard, org_id):
        """Test prediction with no historical data."""
        prediction = await guard.predict_usage(org_id)

        assert prediction.confidence == 0.0
        assert prediction.predicted_hourly_cost == 0

    @pytest.mark.asyncio
    async def test_predict_usage_with_budget(self, guard, entity_id, org_id):
        """Test prediction with budget set."""
        budget = BudgetConfig(org_id=org_id, daily_budget=100.0, monthly_budget=3000.0)
        guard.set_budget(budget)

        # Record some spending
        now = datetime.utcnow()
        for h in range(5):
            hour_key = f"{org_id}:{(now - timedelta(hours=h)).strftime('%Y%m%d%H')}"
            guard._spend_tracking[hour_key] = 2.0  # $2/hour

        prediction = await guard.predict_usage(org_id)

        assert prediction.predicted_hourly_cost > 0
        assert prediction.predicted_daily_cost == prediction.predicted_hourly_cost * 24

    def test_set_budget(self, guard, org_id):
        """Test setting budget configuration."""
        budget = BudgetConfig(org_id=org_id, daily_budget=50.0)

        guard.set_budget(budget)

        retrieved = guard.get_budget(org_id)
        assert retrieved is not None
        assert retrieved.daily_budget == 50.0

    def test_get_budget_not_found(self, guard, org_id):
        """Test getting budget for org with no budget set."""
        result = guard.get_budget(org_id)

        assert result is None

    @pytest.mark.asyncio
    async def test_get_alerts(self, guard, entity_id):
        """Test retrieving alerts."""
        limits = [QuotaLimit("rpm", 10, 60, soft_limit_percent=0.5)]
        guard.set_limits(entity_id, limits)

        # Generate alert
        for _ in range(6):
            await guard.record_usage(entity_id, request_value=1)
        await guard.check_quota(entity_id, request_value=1)

        alerts = guard.get_alerts(entity_id=entity_id)

        assert len(alerts) > 0

    @pytest.mark.asyncio
    async def test_get_alerts_unacknowledged(self, guard, entity_id):
        """Test filtering unacknowledged alerts."""
        limits = [QuotaLimit("rpm", 10, 60, soft_limit_percent=0.5)]
        guard.set_limits(entity_id, limits)

        # Generate alert
        for _ in range(6):
            await guard.record_usage(entity_id, request_value=1)
        await guard.check_quota(entity_id, request_value=1)

        alerts = guard.get_alerts(unacknowledged_only=True)

        assert all(not a.acknowledged for a in alerts)

    @pytest.mark.asyncio
    async def test_acknowledge_alert(self, guard, entity_id):
        """Test acknowledging an alert."""
        limits = [QuotaLimit("rpm", 10, 60, soft_limit_percent=0.5)]
        guard.set_limits(entity_id, limits)

        # Generate alert
        for _ in range(6):
            await guard.record_usage(entity_id, request_value=1)
        await guard.check_quota(entity_id, request_value=1)

        alerts = guard.get_alerts()
        assert len(alerts) > 0

        result = await guard.acknowledge_alert(alerts[0].alert_id)

        assert result is True
        assert alerts[0].acknowledged is True

    @pytest.mark.asyncio
    async def test_acknowledge_alert_not_found(self, guard):
        """Test acknowledging non-existent alert."""
        result = await guard.acknowledge_alert(uuid4())

        assert result is False

    def test_get_current_usage_default_limits(self, guard, entity_id):
        """Test getting usage with default limits."""
        usage = guard.get_current_usage(entity_id)

        assert "rpm" in usage
        assert "tpm" in usage

    def test_get_spend_daily(self, guard, org_id):
        """Test getting daily spend."""
        now = datetime.utcnow()
        key = f"{org_id}:{now.strftime('%Y%m%d')}"
        guard._spend_tracking[key] = 25.50

        spend = guard.get_spend(org_id, period="daily")

        assert spend == 25.50

    def test_get_spend_monthly(self, guard, org_id):
        """Test getting monthly spend."""
        now = datetime.utcnow()
        key = f"{org_id}:{now.strftime('%Y%m')}"
        guard._spend_tracking[key] = 250.00

        spend = guard.get_spend(org_id, period="monthly")

        assert spend == 250.00


# ============================================================================
# UsageWindow Tests
# ============================================================================

class TestUsageWindow:
    """Tests for UsageWindow sliding window."""

    def test_add_request(self):
        """Test adding a request to the window."""
        now = datetime.utcnow()
        window = UsageWindow(
            window_id="test",
            entity_id=uuid4(),
            limit_name="rpm",
            window_start=now,
            window_end=now + timedelta(seconds=60),
        )

        window.add_request(1)

        assert window.current_value == 1
        assert len(window.requests) == 1

    def test_get_current_usage(self):
        """Test getting current usage."""
        now = datetime.utcnow()
        window = UsageWindow(
            window_id="test",
            entity_id=uuid4(),
            limit_name="rpm",
            window_start=now,
            window_end=now + timedelta(seconds=60),
        )

        window.add_request(5)
        window.add_request(3)

        assert window.get_current_usage() == 8


# ============================================================================
# Data Class Tests
# ============================================================================

class TestDataClasses:
    """Tests for various data class serialization."""

    def test_quota_limit_to_dict(self):
        """Test QuotaLimit serialization."""
        limit = QuotaLimit("rpm", 1000, 60, soft_limit_percent=0.8)

        result = limit.to_dict()

        assert result["name"] == "rpm"
        assert result["limit_value"] == 1000

    def test_budget_config_to_dict(self):
        """Test BudgetConfig serialization."""
        budget = BudgetConfig(
            org_id=uuid4(),
            daily_budget=100.0,
            monthly_budget=3000.0,
        )

        result = budget.to_dict()

        assert result["daily_budget"] == 100.0
        assert result["monthly_budget"] == 3000.0

    def test_quota_alert_to_dict(self):
        """Test QuotaAlert serialization."""
        alert = QuotaAlert(
            alert_id=uuid4(),
            entity_id=uuid4(),
            entity_type="key",
            alert_type="rate_limit",
            severity=AlertSeverity.WARNING,
            message="Approaching limit",
            threshold_percent=0.8,
            current_value=80,
            limit_value=100,
        )

        result = alert.to_dict()

        assert result["severity"] == "warning"
        assert result["message"] == "Approaching limit"

    def test_throttle_decision_to_dict(self):
        """Test ThrottleDecision serialization."""
        decision = ThrottleDecision(
            action=ThrottleAction.THROTTLE,
            allowed=True,
            delay_ms=100,
            usage_percent=0.85,
        )

        result = decision.to_dict()

        assert result["action"] == "throttle"
        assert result["delay_ms"] == 100

    def test_usage_prediction_to_dict(self):
        """Test UsagePrediction serialization."""
        prediction = UsagePrediction(
            org_id=uuid4(),
            prediction_time=datetime.utcnow(),
            predicted_hourly_cost=5.0,
            predicted_daily_cost=120.0,
            predicted_monthly_cost=3600.0,
            confidence=0.85,
            trend="stable",
        )

        result = prediction.to_dict()

        assert result["predicted_daily_cost"] == 120.0
        assert result["trend"] == "stable"


# ============================================================================
# Singleton Tests
# ============================================================================

class TestSingletons:
    """Tests for singleton patterns."""

    def test_get_byok_gateway_singleton(self):
        """Test BYOK gateway singleton."""
        reset_byok_gateway()

        gw1 = get_byok_gateway()
        gw2 = get_byok_gateway()

        assert gw1 is gw2
        reset_byok_gateway()

    def test_get_quota_guard_singleton(self):
        """Test quota guard singleton."""
        reset_quota_guard()

        qg1 = get_quota_guard()
        qg2 = get_quota_guard()

        assert qg1 is qg2
        reset_quota_guard()


# ============================================================================
# Integration Tests
# ============================================================================

class TestBYOKQuotaIntegration:
    """Integration tests for BYOK Gateway with Quota Guard."""

    @pytest.fixture
    def gateway(self):
        return BYOKGateway(encryption_key="test-key")

    @pytest.fixture
    def guard(self):
        return QuotaGuard()

    @pytest.fixture
    def org_id(self):
        return uuid4()

    @pytest.mark.asyncio
    async def test_end_to_end_usage_tracking(self, gateway, guard, org_id):
        """Test end-to-end usage tracking flow."""
        # Setup
        tier = CustomerTier("test", 100, 10000, pricing_per_1m_input=3.0, pricing_per_1m_output=15.0)
        key = await gateway.register_key(org_id, KeyProvider.OPENAI, "sk-test", custom_tier=tier)

        budget = BudgetConfig(org_id=org_id, daily_budget=100.0)
        guard.set_budget(budget)

        limits = [QuotaLimit("rpm", tier.rate_limit_rpm, 60)]
        guard.set_limits(key.key_id, limits)

        # Simulate API calls
        for _ in range(5):
            # Check quota before request
            quota_result = await gateway.check_quota(key.key_id, estimated_tokens=500)
            assert quota_result.allowed

            guard_result = await guard.check_quota(
                key.key_id,
                request_tokens=500,
                estimated_cost=0.50,
                org_id=org_id,
            )
            assert guard_result.allowed

            # Record usage after request
            await gateway.record_usage(key.key_id, 500, 200)
            await guard.record_usage(key.key_id, request_tokens=700, cost=0.50, org_id=org_id)

        # Verify tracking - use date range that includes current hour bucket
        now = datetime.utcnow()
        report = await gateway.get_spend_report(
            org_id,
            start_date=now - timedelta(hours=1),
            end_date=now + timedelta(hours=2),
        )
        assert report.total_requests == 5
        assert report.total_input_tokens == 2500

        spend = guard.get_spend(org_id, period="daily")
        assert spend == 2.50

    @pytest.mark.asyncio
    async def test_rate_limit_coordination(self, gateway, guard, org_id):
        """Test that gateway and guard coordinate on rate limits."""
        tier = CustomerTier("test", 5, 10000)  # Only 5 RPM
        key = await gateway.register_key(org_id, KeyProvider.OPENAI, "sk-test", custom_tier=tier)

        # Disable burst by setting burst_multiplier=1.0
        limits = [QuotaLimit("rpm", 5, 60, burst_multiplier=1.0)]
        guard.set_limits(key.key_id, limits)

        # Make 5 requests (at limit)
        for _ in range(5):
            await gateway.record_usage(key.key_id, 100, 100)
            await guard.record_usage(key.key_id, request_value=1)

        # Both should now reject
        gw_result = await gateway.check_quota(key.key_id)
        guard_result = await guard.check_quota(key.key_id)

        assert gw_result.allowed is False
        assert guard_result.allowed is False

    @pytest.mark.asyncio
    async def test_budget_tracking_with_gateway(self, gateway, guard, org_id):
        """Test budget tracking integration."""
        tier = CustomerTier("test", 1000, 100000, pricing_per_1m_input=1.0, pricing_per_1m_output=1.0)
        key = await gateway.register_key(org_id, KeyProvider.OPENAI, "sk-test", custom_tier=tier)

        budget = BudgetConfig(org_id=org_id, daily_budget=5.0, hard_stop_at=1.0)
        guard.set_budget(budget)

        # Use $4 of budget
        for _ in range(4):
            await gateway.record_usage(key.key_id, 500_000, 500_000)  # $1 per call
            await guard.record_usage(key.key_id, cost=1.0, org_id=org_id)

        # Should still be allowed
        result = await guard.check_quota(key.key_id, estimated_cost=0.50, org_id=org_id)
        assert result.allowed

        # Use remaining budget
        await guard.record_usage(key.key_id, cost=1.5, org_id=org_id)

        # Now should be rejected
        result = await guard.check_quota(key.key_id, estimated_cost=0.10, org_id=org_id)
        assert result.allowed is False


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
