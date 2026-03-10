#!/usr/bin/env python3
"""
Demo: Key Validation Service - 24h API Key Validation Pings

Session 2.3: Key Rotation Detection

This demo showcases:
1. Key Registration - Register keys for periodic validation
2. Validation Lifecycle - Valid → Invalid → Recovered
3. Alert Generation - Automatic alerts on key failures
4. Health Monitoring - Track key health status
5. Overdue Detection - Find keys needing validation
6. Statistics Dashboard - Validation metrics
"""

import asyncio
import sys
from datetime import datetime, timedelta
from uuid import uuid4
from pathlib import Path

# Add parent directory to path so backend.* imports work
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from backend.shared.key_validation_service import (
    KeyValidationService,
    KeyValidator,
    KeyValidationStatus,
    ValidationAlertType,
    AlertSeverity,
)


def print_section(title: str):
    """Print a section header."""
    print(f"\n{'='*60}")
    print(f"  {title}")
    print(f"{'='*60}\n")


def print_result(label: str, value):
    """Print a labeled result."""
    print(f"  {label}: {value}")


async def demo_key_registration():
    """Demo 1: Key Registration."""
    print_section("Demo 1: Key Registration for Validation")

    validator = KeyValidator(simulate=True)
    service = KeyValidationService(validator=validator)

    org_id = uuid4()
    print(f"Organization ID: {org_id}\n")

    # Register multiple keys for different providers
    providers = [
        ("openai", "sk-openai-prod-key-12345"),
        ("anthropic", "sk-ant-enterprise-67890"),
        ("deepseek", "sk-deepseek-default-key"),
    ]

    print("Registering API keys for 24h validation cycle:\n")
    for provider, key_hint in providers:
        key_id = uuid4()
        validator.set_simulated_state(key_id, KeyValidationStatus.VALID)

        health = await service.register_key(
            key_id=key_id,
            org_id=org_id,
            provider=provider,
            interval_hours=24.0,
            validate_immediately=True,
        )

        schedule = service.get_validation_schedule(key_id)

        print(f"  Provider:        {provider}")
        print(f"  Key ID:          {key_id}")
        print(f"  Is Healthy:      {health.is_healthy}")
        print(f"  Last Validated:  {health.last_validation.validated_at.strftime('%H:%M:%S')}")
        print(f"  Response Time:   {health.last_validation.response_time_ms}ms")
        print(f"  Next Validation: {schedule.next_validation.strftime('%Y-%m-%d %H:%M')}")
        print()

    return service, org_id


async def demo_validation_lifecycle(service, org_id):
    """Demo 2: Validation Lifecycle - Valid → Invalid → Recovered."""
    print_section("Demo 2: Key Validation Lifecycle")

    key_id = uuid4()

    # Collect alerts
    alerts_received = []

    async def alert_callback(alert):
        alerts_received.append(alert)
        severity_emoji = {"info": "ℹ️", "warning": "⚠️", "critical": "🚨"}
        print(f"  {severity_emoji.get(alert.severity.value, '•')} ALERT: {alert.message}")

    service.alert_callback = alert_callback

    # Phase 1: Key is valid
    print("Phase 1: Key is initially valid\n")
    service.validator.set_simulated_state(key_id, KeyValidationStatus.VALID)
    await service.register_key(key_id, org_id, "openai", validate_immediately=True)

    health = service.get_health_status(key_id)
    print(f"  Status:       {'Healthy' if health.is_healthy else 'Unhealthy'}")
    print(f"  Failures:     {health.consecutive_failures}")
    print()

    # Phase 2: Key becomes invalid
    print("Phase 2: Key becomes invalid (simulating revoked key)\n")
    service.validator.set_simulated_state(key_id, KeyValidationStatus.INVALID)

    await service.validate_key(key_id)
    health = service.get_health_status(key_id)
    print(f"  After 1st failure - Healthy: {health.is_healthy}, Failures: {health.consecutive_failures}")

    await service.validate_key(key_id)
    health = service.get_health_status(key_id)
    print(f"  After 2nd failure - Healthy: {health.is_healthy}, Failures: {health.consecutive_failures}")
    print()

    # Phase 3: Key is recovered
    print("Phase 3: Key is rotated/recovered\n")
    service.validator.set_simulated_state(key_id, KeyValidationStatus.VALID)

    await service.validate_key(key_id)
    health = service.get_health_status(key_id)
    print(f"  Status:       {'Healthy' if health.is_healthy else 'Unhealthy'}")
    print(f"  Failures:     {health.consecutive_failures}")
    print()

    print(f"Total alerts generated: {len(alerts_received)}")


async def demo_alert_system():
    """Demo 3: Alert Generation and Management."""
    print_section("Demo 3: Alert System")

    validator = KeyValidator(simulate=True)
    service = KeyValidationService(validator=validator)

    org_id = uuid4()
    keys = {}

    # Register keys with different simulated states
    scenarios = [
        ("valid_key", KeyValidationStatus.VALID),
        ("invalid_key", KeyValidationStatus.INVALID),
        ("rate_limited_key", KeyValidationStatus.RATE_LIMITED),
    ]

    print("Simulating various key states:\n")
    for name, status in scenarios:
        key_id = uuid4()
        keys[name] = key_id
        validator.set_simulated_state(key_id, status)
        await service.register_key(key_id, org_id, "openai", validate_immediately=False)

        # Validate multiple times to trigger alerts
        await service.validate_key(key_id)
        if status != KeyValidationStatus.VALID:
            await service.validate_key(key_id)  # Second failure triggers alert

        health = service.get_health_status(key_id)
        print(f"  {name}:")
        print(f"    Status:  {status.value}")
        print(f"    Healthy: {health.is_healthy}")
        print(f"    Alerts:  {len(health.active_alerts)}")
        print()

    # Show all alerts
    all_alerts = service.get_alerts()
    print(f"Total alerts: {len(all_alerts)}\n")

    if all_alerts:
        print("Alert Details:")
        for alert in all_alerts:
            print(f"  - [{alert.severity.value.upper()}] {alert.alert_type.value}: {alert.message}")

        # Acknowledge first alert
        if all_alerts:
            await service.acknowledge_alert(all_alerts[0].alert_id)
            print(f"\n  First alert acknowledged: {all_alerts[0].acknowledged}")


async def demo_health_monitoring():
    """Demo 4: Health Monitoring Dashboard."""
    print_section("Demo 4: Health Monitoring Dashboard")

    validator = KeyValidator(simulate=True)
    service = KeyValidationService(validator=validator)

    org_id = uuid4()

    # Create a mix of healthy and unhealthy keys
    print("Setting up 10 keys with mixed health states...\n")
    for i in range(10):
        key_id = uuid4()

        # 70% healthy, 30% unhealthy
        if i < 7:
            validator.set_simulated_state(key_id, KeyValidationStatus.VALID)
        else:
            validator.set_simulated_state(key_id, KeyValidationStatus.INVALID)

        await service.register_key(key_id, org_id, "openai", validate_immediately=False)
        await service.validate_key(key_id)
        if i >= 7:
            await service.validate_key(key_id)  # Second failure

    # Get statistics
    stats = service.get_validation_stats()

    print("Validation Statistics:")
    print(f"  Total Keys:       {stats['total_keys']}")
    print(f"  Healthy Keys:     {stats['healthy_keys']}")
    print(f"  Unhealthy Keys:   {stats['unhealthy_keys']}")
    print(f"  Health %:         {stats['health_percentage']:.1f}%")
    print(f"  Total Validations: {stats['total_validations']}")
    print(f"  Active Alerts:    {stats['active_alerts']}")
    print()

    # Show unhealthy keys
    unhealthy = service.get_unhealthy_keys()
    if unhealthy:
        print(f"Unhealthy Keys ({len(unhealthy)}):")
        for h in unhealthy:
            print(f"  - {h.key_id} ({h.provider}): {h.consecutive_failures} failures")


async def demo_overdue_detection():
    """Demo 5: Overdue Validation Detection."""
    print_section("Demo 5: Overdue Validation Detection")

    validator = KeyValidator(simulate=True)
    service = KeyValidationService(validator=validator)

    org_id = uuid4()
    keys = []

    # Register keys with different "last validated" times
    print("Simulating keys with different validation ages:\n")
    for hours_ago in [12, 24, 36, 48, 72]:
        key_id = uuid4()
        keys.append((key_id, hours_ago))
        validator.set_simulated_state(key_id, KeyValidationStatus.VALID)
        await service.register_key(key_id, org_id, "openai", validate_immediately=True)

        # Manipulate last validation time
        health = service.get_health_status(key_id)
        health.last_validation.validated_at = datetime.utcnow() - timedelta(hours=hours_ago)

        print(f"  Key validated {hours_ago}h ago: {key_id}")

    print()

    # Find overdue validations (threshold: 48h)
    overdue = service.get_overdue_validations(threshold_hours=48.0)

    print(f"Keys overdue for validation (>48h threshold): {len(overdue)}")
    for h in overdue:
        last_val = h.last_validation.validated_at if h.last_validation else None
        hours_ago = (datetime.utcnow() - last_val).total_seconds() / 3600 if last_val else 999
        print(f"  - {h.key_id}: last validated {hours_ago:.0f}h ago")


async def demo_multi_provider():
    """Demo 6: Multi-Provider Validation."""
    print_section("Demo 6: Multi-Provider Validation")

    validator = KeyValidator(simulate=True)
    service = KeyValidationService(validator=validator)

    org_id = uuid4()
    providers = ["openai", "anthropic", "deepseek", "google"]

    print("Registering keys for multiple providers:\n")
    for provider in providers:
        key_id = uuid4()
        validator.set_simulated_state(key_id, KeyValidationStatus.VALID)
        await service.register_key(
            key_id=key_id,
            org_id=org_id,
            provider=provider,
            interval_hours=24.0 if provider == "openai" else 12.0,
        )

        health = service.get_health_status(key_id)
        schedule = service.get_validation_schedule(key_id)

        print(f"  {provider}:")
        print(f"    Key ID:   {key_id}")
        print(f"    Interval: {schedule.interval_hours}h")
        print(f"    Healthy:  {health.is_healthy}")
        print()

    # Force validate all
    print("Force validating all keys...")
    results = await service.force_validate_all()
    print(f"  Validated {len(results)} keys")

    valid_count = sum(1 for r in results if r.status == KeyValidationStatus.VALID)
    print(f"  Valid: {valid_count}/{len(results)}")


async def demo_validation_history():
    """Demo 7: Validation History."""
    print_section("Demo 7: Validation History")

    validator = KeyValidator(simulate=True)
    service = KeyValidationService(validator=validator)

    org_id = uuid4()
    key_id = uuid4()

    # Simulate various validation outcomes over time
    print("Simulating validation history:\n")
    states = [
        KeyValidationStatus.VALID,
        KeyValidationStatus.VALID,
        KeyValidationStatus.RATE_LIMITED,
        KeyValidationStatus.VALID,
        KeyValidationStatus.INVALID,
        KeyValidationStatus.INVALID,
        KeyValidationStatus.VALID,  # Recovery
        KeyValidationStatus.VALID,
    ]

    await service.register_key(key_id, org_id, "openai", validate_immediately=False)

    for i, status in enumerate(states):
        validator.set_simulated_state(key_id, status)
        result = await service.validate_key(key_id)
        emoji = "✓" if status == KeyValidationStatus.VALID else "✗"
        print(f"  [{i+1}] {emoji} {status.value}")

    # Show validation history
    health = service.get_health_status(key_id)
    print(f"\nValidation History (last {len(health.validation_history)} entries):")
    for i, v in enumerate(health.validation_history[-5:]):  # Last 5
        print(f"  {i+1}. {v.status.value} at {v.validated_at.strftime('%H:%M:%S')} ({v.response_time_ms}ms)")


async def main():
    """Run all demos."""
    print("\n" + "="*60)
    print("  KEY VALIDATION SERVICE DEMO - Session 2.3")
    print("  24h API Key Validation Pings")
    print("="*60)

    # Demo 1: Key Registration
    service, org_id = await demo_key_registration()

    # Demo 2: Validation Lifecycle
    await demo_validation_lifecycle(service, org_id)

    # Demo 3: Alert System
    await demo_alert_system()

    # Demo 4: Health Monitoring
    await demo_health_monitoring()

    # Demo 5: Overdue Detection
    await demo_overdue_detection()

    # Demo 6: Multi-Provider
    await demo_multi_provider()

    # Demo 7: Validation History
    await demo_validation_history()

    print_section("Demo Complete")
    print("Key Validation Service features demonstrated:")
    print("  - 24h periodic key validation cycle")
    print("  - Multi-provider support (OpenAI, Anthropic, DeepSeek, Google)")
    print("  - Automatic alert generation on failures")
    print("  - Alert acknowledgement and recovery tracking")
    print("  - Health status monitoring dashboard")
    print("  - Overdue validation detection")
    print("  - Validation history tracking")
    print("  - Force validation for all keys")
    print()


if __name__ == "__main__":
    asyncio.run(main())
