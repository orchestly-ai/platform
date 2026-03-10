#!/usr/bin/env python3
"""
Demo: BYOK Gateway - Customer-Managed API Keys

Session 2.2: BYOK Gateway

This demo showcases:
1. Key Vault - Encrypted customer API key storage
2. Quota Guard - Sliding window rate limiting with budget management
3. Usage Tracking - Per-key usage monitoring
4. Spend Reports - Cost transparency with projections
5. Key Rotation - Secure key updates
"""

import asyncio
import sys
from datetime import datetime, timedelta
from uuid import uuid4
from pathlib import Path

# Add parent directory to path so backend.* imports work
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from backend.shared.byok_gateway import (
    BYOKGateway,
    KeyVault,
    KeyProvider,
    KeyStatus,
    CustomerTier,
)
from backend.shared.quota_guard import (
    QuotaGuard,
    QuotaLimit,
    BudgetConfig,
    ThrottleAction,
)


def print_section(title: str):
    """Print a section header."""
    print(f"\n{'='*60}")
    print(f"  {title}")
    print(f"{'='*60}\n")


def print_result(label: str, value):
    """Print a labeled result."""
    print(f"  {label}: {value}")


async def demo_key_vault():
    """Demo 1: Key Vault Encryption."""
    print_section("Demo 1: Key Vault Encryption")

    vault = KeyVault(encryption_key="secure-encryption-key-256bit")

    # Encrypt API keys
    api_keys = [
        "sk-openai-abc123xyz789longapikey",
        "sk-ant-anthropic-secret-key",
        "sk-deepseek-production-key",
    ]

    print("Encrypting customer API keys:\n")
    for key in api_keys:
        encrypted = vault.encrypt_key(key)
        prefix = vault.get_key_prefix(key)
        decrypted = vault.decrypt_key(encrypted)

        print(f"  Original:  {key}")
        print(f"  Prefix:    {prefix}")
        print(f"  Encrypted: {encrypted[:40]}...")
        print(f"  Decrypted: {decrypted}")
        print(f"  Match:     {decrypted == key}")
        print()


async def demo_key_registration():
    """Demo 2: Key Registration and Management."""
    print_section("Demo 2: Key Registration and Management")

    gateway = BYOKGateway(encryption_key="demo-encryption-key")
    org_id = uuid4()

    print(f"Organization ID: {org_id}\n")

    # Register keys with different providers and tiers
    keys_to_register = [
        (KeyProvider.OPENAI, "sk-openai-production-key-1234", "tier_3"),
        (KeyProvider.ANTHROPIC, "sk-ant-enterprise-key-5678", "tier_2"),
        (KeyProvider.DEEPSEEK, "sk-deepseek-default-key-9012", "default"),
    ]

    registered_keys = []
    print("Registering API keys:\n")
    for provider, api_key, tier_name in keys_to_register:
        key = await gateway.register_key(
            org_id=org_id,
            provider=provider,
            api_key=api_key,
            tier_name=tier_name,
        )
        registered_keys.append(key)

        print(f"  Provider: {provider.value}")
        print(f"  Key ID:   {key.key_id}")
        print(f"  Prefix:   {key.key_prefix}")
        print(f"  Tier:     {key.tier.tier_name}")
        print(f"  RPM:      {key.tier.rate_limit_rpm:,}")
        print(f"  TPM:      {key.tier.rate_limit_tpm:,}")
        print(f"  Status:   {key.status.value}")
        print()

    # Get all keys for org
    org_keys = await gateway.get_keys_by_org(org_id)
    print(f"Total keys registered for org: {len(org_keys)}")

    return gateway, org_id, registered_keys


async def demo_quota_checking(gateway, org_id, keys):
    """Demo 3: Quota Checking and Rate Limiting."""
    print_section("Demo 3: Quota Checking and Rate Limiting")

    key = keys[0]  # Use OpenAI key
    print(f"Testing quota for key: {key.key_prefix} ({key.provider.value})\n")

    # Check quota before any usage
    print("Initial quota check (no prior usage):")
    result = await gateway.check_quota(key.key_id, estimated_tokens=1000)
    print(f"  Allowed:         {result.allowed}")
    print(f"  Remaining RPM:   {result.remaining_rpm}")
    print(f"  Remaining TPM:   {result.remaining_tpm}")
    print(f"  Throttle recommended: {result.throttle_recommended}")
    print()

    # Simulate some usage
    print("Simulating 50 API calls with ~1000 tokens each...")
    for i in range(50):
        await gateway.record_usage(key.key_id, input_tokens=500, output_tokens=500)

    # Check quota after usage
    print("\nQuota check after 50 calls:")
    result = await gateway.check_quota(key.key_id, estimated_tokens=1000)
    print(f"  Allowed:         {result.allowed}")
    print(f"  Current RPM:     {result.current_rpm}")
    print(f"  Current TPM:     {result.current_tpm}")
    print(f"  Remaining RPM:   {result.remaining_rpm}")
    print(f"  Remaining TPM:   {result.remaining_tpm}")
    print(f"  Throttle recommended: {result.throttle_recommended}")


async def demo_quota_guard():
    """Demo 4: Advanced Quota Guard with Budget Management."""
    print_section("Demo 4: Quota Guard with Budget Management")

    guard = QuotaGuard()
    org_id = uuid4()
    key_id = uuid4()

    print(f"Organization ID: {org_id}")
    print(f"Key ID:          {key_id}\n")

    # Set up budget
    budget = BudgetConfig(
        org_id=org_id,
        daily_budget=50.0,
        monthly_budget=1000.0,
        alert_thresholds=[0.5, 0.75, 0.9, 1.0],
    )
    guard.set_budget(budget)
    print("Budget configured:")
    print(f"  Daily:   ${budget.daily_budget:.2f}")
    print(f"  Monthly: ${budget.monthly_budget:.2f}")
    print(f"  Alerts:  {[f'{t*100}%' for t in budget.alert_thresholds]}")
    print()

    # Set up rate limits
    limits = [
        QuotaLimit("rpm", 100, 60, soft_limit_percent=0.8),
        QuotaLimit("tpm", 50000, 60, soft_limit_percent=0.8),
        QuotaLimit("rpd", 10000, 86400, soft_limit_percent=0.9),
    ]
    guard.set_limits(key_id, limits)
    print("Rate limits configured:")
    for limit in limits:
        print(f"  {limit.name}: {limit.limit_value:,} per {limit.window_seconds}s")
    print()

    # Simulate usage and check for throttling
    print("Simulating API usage and checking throttle decisions:\n")
    costs = [0.50, 0.75, 1.00, 2.00, 3.00]  # Increasing costs

    for i, cost in enumerate(costs):
        result = await guard.check_quota(
            key_id,
            request_value=1,
            request_tokens=1000,
            estimated_cost=cost,
            org_id=org_id,
        )

        await guard.record_usage(
            key_id,
            request_value=1,
            request_tokens=1000,
            cost=cost,
            org_id=org_id,
        )

        print(f"  Request {i+1}: ${cost:.2f}")
        print(f"    Action:      {result.action.value}")
        print(f"    Allowed:     {result.allowed}")
        print(f"    Usage %:     {result.usage_percent*100:.1f}%")
        print(f"    Delay:       {result.delay_ms}ms")

        if result.alerts:
            print(f"    Alerts:      {len(result.alerts)}")
            for alert in result.alerts:
                print(f"      - {alert.severity.value}: {alert.message}")
        print()

    # Check spend
    daily_spend = guard.get_spend(org_id, period="daily")
    monthly_spend = guard.get_spend(org_id, period="monthly")
    print(f"Current spend:")
    print(f"  Daily:   ${daily_spend:.2f} / ${budget.daily_budget:.2f}")
    print(f"  Monthly: ${monthly_spend:.2f} / ${budget.monthly_budget:.2f}")


async def demo_spend_report(gateway, org_id, keys):
    """Demo 5: Spend Report Generation."""
    print_section("Demo 5: Spend Report Generation")

    # Add pricing to a key's tier for cost calculation
    tier = CustomerTier(
        tier_name="enterprise",
        rate_limit_rpm=5000,
        rate_limit_tpm=200000,
        pricing_per_1m_input=3.00,
        pricing_per_1m_output=15.00,
    )

    # Register a new key with pricing
    enterprise_key = await gateway.register_key(
        org_id=org_id,
        provider=KeyProvider.OPENAI,
        api_key="sk-enterprise-with-pricing",
        custom_tier=tier,
    )

    # Simulate significant usage
    print("Simulating enterprise usage over multiple requests...\n")
    for i in range(100):
        await gateway.record_usage(
            enterprise_key.key_id,
            input_tokens=10000,  # 10k tokens per request
            output_tokens=5000,  # 5k tokens per request
        )

    # Generate spend report
    now = datetime.utcnow()
    report = await gateway.get_spend_report(
        org_id,
        start_date=now - timedelta(hours=1),
        end_date=now + timedelta(hours=2),
    )

    print("Spend Report:")
    print(f"  Period:              {report.period_start.date()} to {report.period_end.date()}")
    print(f"  Total Requests:      {report.total_requests:,}")
    print(f"  Total Input Tokens:  {report.total_input_tokens:,}")
    print(f"  Total Output Tokens: {report.total_output_tokens:,}")
    print(f"  Total Cost:          ${report.total_cost:.2f}")
    print(f"  Burn Rate/Hour:      ${report.burn_rate_per_hour:.4f}")
    print(f"  Projected Monthly:   ${report.projected_monthly_cost:.2f}")
    print()

    if report.cost_by_provider:
        print("  Cost by Provider:")
        for provider, cost in report.cost_by_provider.items():
            print(f"    {provider}: ${cost:.2f}")


async def demo_key_rotation(gateway, org_id, keys):
    """Demo 6: Key Rotation."""
    print_section("Demo 6: Key Rotation")

    key = keys[1]  # Use Anthropic key
    print(f"Rotating key: {key.key_prefix} ({key.provider.value})\n")

    # Get current key
    old_decrypted = await gateway.get_decrypted_key(key.key_id)
    print(f"  Current key:     {old_decrypted}")
    print(f"  Current prefix:  {key.key_prefix}")
    print(f"  Status:          {key.status.value}")
    print()

    # Rotate to new key
    new_api_key = "sk-ant-new-rotated-production-key"
    rotated = await gateway.rotate_key(key.key_id, new_api_key)

    new_decrypted = await gateway.get_decrypted_key(key.key_id)
    print("After rotation:")
    print(f"  New key:         {new_decrypted}")
    print(f"  New prefix:      {rotated.key_prefix}")
    print(f"  Status:          {rotated.status.value}")
    print(f"  Last validated:  {rotated.last_validated_at}")


async def demo_usage_prediction():
    """Demo 7: Usage Prediction."""
    print_section("Demo 7: Usage Prediction")

    guard = QuotaGuard()
    org_id = uuid4()
    key_id = uuid4()

    # Set up budget
    budget = BudgetConfig(
        org_id=org_id,
        daily_budget=100.0,
        monthly_budget=2000.0,
    )
    guard.set_budget(budget)

    # Simulate hourly spending pattern
    print("Simulating 12 hours of usage data...\n")
    now = datetime.utcnow()
    for h in range(12):
        hour_time = now - timedelta(hours=h)
        hour_key = f"{org_id}:{hour_time.strftime('%Y%m%d%H')}"
        # Increasing usage pattern
        guard._spend_tracking[hour_key] = 2.0 + (h * 0.5)

    # Get prediction
    prediction = await guard.predict_usage(org_id)

    print("Usage Prediction:")
    print(f"  Predicted hourly:    ${prediction.predicted_hourly_cost:.2f}")
    print(f"  Predicted daily:     ${prediction.predicted_daily_cost:.2f}")
    print(f"  Predicted monthly:   ${prediction.predicted_monthly_cost:.2f}")
    print(f"  Confidence:          {prediction.confidence*100:.0f}%")
    print(f"  Trend:               {prediction.trend}")
    print(f"  Will exceed daily:   {prediction.will_exceed_daily_budget}")
    print(f"  Will exceed monthly: {prediction.will_exceed_monthly_budget}")

    if prediction.hours_until_daily_limit:
        print(f"  Hours until daily limit: {prediction.hours_until_daily_limit:.1f}")
    if prediction.days_until_monthly_limit:
        print(f"  Days until monthly limit: {prediction.days_until_monthly_limit:.1f}")


async def demo_multi_key_workflow():
    """Demo 8: Multi-Key Workflow with Failover."""
    print_section("Demo 8: Multi-Key Workflow")

    gateway = BYOKGateway(encryption_key="workflow-demo-key")
    org_id = uuid4()

    print("Setting up multi-provider key configuration...\n")

    # Register primary and backup keys
    primary = await gateway.register_key(
        org_id=org_id,
        provider=KeyProvider.OPENAI,
        api_key="sk-primary-openai-key",
        tier_name="tier_4",
    )
    print(f"Primary:  {primary.key_prefix} ({primary.provider.value})")

    backup1 = await gateway.register_key(
        org_id=org_id,
        provider=KeyProvider.ANTHROPIC,
        api_key="sk-backup-anthropic-key",
        tier_name="tier_3",
    )
    print(f"Backup 1: {backup1.key_prefix} ({backup1.provider.value})")

    backup2 = await gateway.register_key(
        org_id=org_id,
        provider=KeyProvider.DEEPSEEK,
        api_key="sk-backup-deepseek-key",
        tier_name="default",
    )
    print(f"Backup 2: {backup2.key_prefix} ({backup2.provider.value})")
    print()

    # Simulate primary hitting rate limit
    print("Simulating primary key hitting rate limits...")
    for _ in range(50):
        await gateway.record_usage(primary.key_id, 1000, 1000)

    # Check each key's quota
    print("\nKey availability status:")
    for key in [primary, backup1, backup2]:
        result = await gateway.check_quota(key.key_id, estimated_tokens=1000)
        status = "AVAILABLE" if result.allowed else "RATE LIMITED"
        print(f"  {key.provider.value:10} ({key.key_prefix}): {status}")
        if not result.allowed:
            print(f"    Retry after: {result.retry_after_seconds}s")
            print(f"    Reason: {result.reason}")

    # Simulate failover decision
    print("\nFailover logic:")
    keys = [primary, backup1, backup2]
    for key in keys:
        result = await gateway.check_quota(key.key_id, estimated_tokens=1000)
        if result.allowed:
            print(f"  Using: {key.provider.value} ({key.key_prefix})")
            break
    else:
        print("  All keys rate limited - request must wait")


async def main():
    """Run all demos."""
    print("\n" + "="*60)
    print("  BYOK GATEWAY DEMO - Session 2.2")
    print("  Customer-Managed API Keys & Quota Management")
    print("="*60)

    # Demo 1: Key Vault
    await demo_key_vault()

    # Demo 2: Key Registration
    gateway, org_id, keys = await demo_key_registration()

    # Demo 3: Quota Checking
    await demo_quota_checking(gateway, org_id, keys)

    # Demo 4: Quota Guard with Budget
    await demo_quota_guard()

    # Demo 5: Spend Reports
    await demo_spend_report(gateway, org_id, keys)

    # Demo 6: Key Rotation
    await demo_key_rotation(gateway, org_id, keys)

    # Demo 7: Usage Prediction
    await demo_usage_prediction()

    # Demo 8: Multi-Key Workflow
    await demo_multi_key_workflow()

    print_section("Demo Complete")
    print("BYOK Gateway features demonstrated:")
    print("  - Secure key encryption/decryption")
    print("  - Multi-provider key registration")
    print("  - Quota checking and rate limiting")
    print("  - Budget management with alerts")
    print("  - Usage tracking and spend reports")
    print("  - Key rotation")
    print("  - Usage prediction")
    print("  - Multi-key failover workflow")
    print()


if __name__ == "__main__":
    asyncio.run(main())
