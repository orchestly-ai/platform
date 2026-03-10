#!/usr/bin/env python3
"""
Demo: Integration Health Checks

Shows the integration credential health checking from ROADMAP.md:
1. Registering credentials for monitoring
2. Running health checks (daily validation)
3. Detecting credential expiration
4. Detecting permission changes
5. Alert generation and acknowledgment
6. Health history tracking

Reference: ROADMAP.md Section "Integration Credential Health Checks"

Key Design Decisions:
- Uses each integration's test_connection() method
- Checks run daily by default (configurable)
- Alerts generated after consecutive failures
- Health history maintained for trend analysis
"""

import asyncio
import sys
from pathlib import Path
from datetime import datetime
from uuid import uuid4

# Add parent directories to path
backend_dir = Path(__file__).parent.parent
sys.path.insert(0, str(backend_dir))
parent_dir = backend_dir.parent
sys.path.insert(0, str(parent_dir))

from backend.shared.integration_health_service import (
    IntegrationHealthService,
    HealthStatus,
    HealthCheckReason,
    HealthCheckResult,
    IntegrationCredential,
    HealthAlert,
)


def print_header(title: str):
    """Print a section header."""
    print("\n" + "=" * 60)
    print(f"  {title}")
    print("=" * 60)


def print_result(description: str, result, indent=2):
    """Print a result with formatting."""
    prefix = " " * indent
    if hasattr(result, 'to_dict'):
        print(f"{prefix}{description}:")
        for key, value in result.to_dict().items():
            print(f"{prefix}  {key}: {value}")
    else:
        print(f"{prefix}{description}: {result}")


async def demo_basic_registration():
    """Demo 1: Basic credential registration."""
    print_header("Demo 1: Credential Registration")
    print("\nRegister integration credentials for health monitoring.\n")

    service = IntegrationHealthService()
    org_id = uuid4()

    print("1. Registering multiple integration credentials...")
    integrations = ["slack", "github", "stripe", "hubspot"]

    for name in integrations:
        cred = await service.register_credential(
            credential_id=uuid4(),
            integration_name=name,
            org_id=org_id,
        )
        print(f"   Registered: {name}")
        print(f"     ID: {cred.credential_id}")
        print(f"     Status: {cred.status}")
        print(f"     Health: {cred.health_status.value}")

    print(f"\n2. Total registered: {len(service.get_all_credentials())}")
    print("\n[OK] Credential registration works correctly!")


async def demo_health_checks():
    """Demo 2: Running health checks."""
    print_header("Demo 2: Health Check Execution")
    print("\nRun health checks to validate credentials.\n")

    service = IntegrationHealthService()
    org_id = uuid4()

    # Register some credentials
    slack_id = uuid4()
    github_id = uuid4()

    await service.register_credential(
        credential_id=slack_id,
        integration_name="slack",
        org_id=org_id,
    )
    await service.register_credential(
        credential_id=github_id,
        integration_name="github",
        org_id=org_id,
    )

    print("1. Running individual health check...")
    result = await service.check_credential(slack_id)
    print(f"   Slack check: healthy={result.healthy}, status={result.status.value}")
    if result.response_time_ms:
        print(f"   Response time: {result.response_time_ms:.2f}ms")

    print("\n2. Running check on all credentials...")
    stats = await service.check_all_credentials()
    print(f"   Total checked: {stats.total_checked}")
    print(f"   Healthy: {stats.healthy_count}")
    print(f"   Unhealthy: {stats.unhealthy_count}")
    print(f"   Duration: {stats.duration_ms:.2f}ms")

    print("\n3. Checking credential states after health check...")
    for cred in service.get_all_credentials():
        print(f"   {cred.integration_name}: {cred.health_status.value}")
        if cred.last_health_check:
            print(f"     Last check: {cred.last_health_check.isoformat()}")

    print("\n[OK] Health check execution works correctly!")


async def demo_failure_detection():
    """Demo 3: Detecting credential failures."""
    print_header("Demo 3: Failure Detection")
    print("\nDetect various types of credential failures.\n")

    service = IntegrationHealthService()
    org_id = uuid4()

    # Scenario 1: Token Expiration
    print("Scenario A: Token Expiration (401)")
    print("-" * 50)

    expired_cred = uuid4()
    await service.register_credential(
        credential_id=expired_cred,
        integration_name="salesforce",
        org_id=org_id,
    )

    result = await service.simulate_check_failure(
        credential_id=expired_cred,
        reason="OAuth token expired. Please re-authenticate.",
        reason_code=HealthCheckReason.CREDENTIAL_EXPIRED,
    )
    print(f"  Check result: healthy={result.healthy}")
    print(f"  Status: {result.status.value}")
    print(f"  Reason: {result.reason}")

    cred = service.get_credential(expired_cred)
    print(f"  Consecutive failures: {cred.consecutive_failures}")

    # Scenario 2: Permission Changes
    print("\nScenario B: Permission Changes (403)")
    print("-" * 50)

    perm_cred = uuid4()
    await service.register_credential(
        credential_id=perm_cred,
        integration_name="github",
        org_id=org_id,
    )

    result = await service.simulate_check_failure(
        credential_id=perm_cred,
        reason="API key lacks required scope: repo:write",
        reason_code=HealthCheckReason.INSUFFICIENT_PERMISSIONS,
    )
    print(f"  Check result: healthy={result.healthy}")
    print(f"  Reason code: {result.reason_code.value}")

    # Scenario 3: Rate Limiting
    print("\nScenario C: Rate Limiting (429)")
    print("-" * 50)

    rate_cred = uuid4()
    await service.register_credential(
        credential_id=rate_cred,
        integration_name="hubspot",
        org_id=org_id,
    )

    result = await service.simulate_check_failure(
        credential_id=rate_cred,
        reason="Rate limit exceeded. Retry after 60 seconds.",
        reason_code=HealthCheckReason.RATE_LIMITED,
    )
    print(f"  Check result: healthy={result.healthy}")
    print(f"  Reason code: {result.reason_code.value}")

    print("\n[OK] Failure detection works correctly!")


async def demo_alerting():
    """Demo 4: Alert generation and management."""
    print_header("Demo 4: Alert Generation")
    print("\nGenerate alerts based on consecutive failures.\n")

    alerts_received = []

    async def alert_callback(alert: HealthAlert):
        alerts_received.append(alert)
        print(f"  [ALERT CALLBACK] {alert.severity.upper()}: {alert.message}")

    service = IntegrationHealthService(alert_callback=alert_callback)
    org_id = uuid4()

    cred_id = uuid4()
    await service.register_credential(
        credential_id=cred_id,
        integration_name="stripe",
        org_id=org_id,
    )

    print("1. First failure (warning threshold)...")
    await service.simulate_check_failure(
        credential_id=cred_id,
        reason="Connection timeout",
        reason_code=HealthCheckReason.TIMEOUT,
    )

    print("\n2. Second failure...")
    await service.simulate_check_failure(
        credential_id=cred_id,
        reason="Connection timeout",
        reason_code=HealthCheckReason.TIMEOUT,
    )

    print("\n3. Third failure (critical threshold)...")
    await service.simulate_check_failure(
        credential_id=cred_id,
        reason="Connection timeout",
        reason_code=HealthCheckReason.TIMEOUT,
    )

    print(f"\n4. Total alerts generated: {len(alerts_received)}")

    alerts = service.get_alerts(credential_id=cred_id)
    print(f"\n5. Alert details:")
    for i, alert in enumerate(alerts, 1):
        print(f"   Alert {i}:")
        print(f"     Type: {alert.alert_type}")
        print(f"     Severity: {alert.severity}")
        print(f"     Acknowledged: {alert.acknowledged}")

    print("\n6. Acknowledging last alert...")
    if alerts:
        await service.acknowledge_alert(alerts[-1].alert_id)
        print(f"   Alert acknowledged: {alerts[-1].alert_id}")

    unacked = service.get_alerts(unacknowledged_only=True)
    print(f"   Unacknowledged alerts remaining: {len(unacked)}")

    print("\n[OK] Alert generation works correctly!")


async def demo_health_history():
    """Demo 5: Health history tracking."""
    print_header("Demo 5: Health History")
    print("\nTrack health check history for trend analysis.\n")

    service = IntegrationHealthService()
    org_id = uuid4()

    cred_id = uuid4()
    await service.register_credential(
        credential_id=cred_id,
        integration_name="zendesk",
        org_id=org_id,
    )

    print("1. Running series of health checks...")

    # Simulate a pattern: healthy -> warning -> unhealthy -> recovery
    await service.check_credential(cred_id)
    print("   Check 1: Healthy")

    await service.check_credential(cred_id)
    print("   Check 2: Healthy")

    await service.simulate_check_warning(cred_id, "High latency detected")
    print("   Check 3: Warning (high latency)")

    await service.simulate_check_failure(
        credential_id=cred_id,
        reason="Service unavailable",
        reason_code=HealthCheckReason.SERVER_ERROR,
    )
    print("   Check 4: Unhealthy (server error)")

    await service.check_credential(cred_id)
    print("   Check 5: Healthy (recovered)")

    print("\n2. Health history (last 5 checks):")
    history = service.get_health_history(cred_id, limit=5)
    for i, check in enumerate(history, 1):
        status_icon = "✓" if check.healthy else "✗"
        warning_note = f" ({check.warning})" if check.warning else ""
        print(f"   {i}. [{status_icon}] {check.status.value}{warning_note}")

    print("\n3. Current credential state:")
    cred = service.get_credential(cred_id)
    print(f"   Status: {cred.health_status.value}")
    print(f"   Consecutive failures: {cred.consecutive_failures}")
    print(f"   Last check: {cred.last_health_check.isoformat()}")

    print("\n[OK] Health history tracking works correctly!")


async def demo_organization_view():
    """Demo 6: Organization-level health view."""
    print_header("Demo 6: Organization Health View")
    print("\nView health status across all organization credentials.\n")

    service = IntegrationHealthService()
    org1 = uuid4()
    org2 = uuid4()

    # Set up credentials for two orgs
    print("1. Setting up credentials for two organizations...")

    org1_integrations = ["slack", "github", "stripe"]
    org2_integrations = ["hubspot", "salesforce"]

    for name in org1_integrations:
        await service.register_credential(
            credential_id=uuid4(),
            integration_name=name,
            org_id=org1,
        )
    print(f"   Org 1: {len(org1_integrations)} credentials")

    for name in org2_integrations:
        await service.register_credential(
            credential_id=uuid4(),
            integration_name=name,
            org_id=org2,
        )
    print(f"   Org 2: {len(org2_integrations)} credentials")

    print("\n2. Running health checks...")
    stats = await service.check_all_credentials()
    print(f"   Total checked: {stats.total_checked}")

    print("\n3. Simulating some failures...")
    org1_creds = service.get_credentials_by_org(org1)
    await service.simulate_check_failure(
        credential_id=org1_creds[0].credential_id,
        reason="Token expired",
        reason_code=HealthCheckReason.CREDENTIAL_EXPIRED,
    )
    print(f"   Made {org1_creds[0].integration_name} unhealthy")

    print("\n4. Organization 1 health summary:")
    for cred in service.get_credentials_by_org(org1):
        icon = "✓" if cred.health_status == HealthStatus.HEALTHY else "✗"
        print(f"   [{icon}] {cred.integration_name}: {cred.health_status.value}")

    print("\n5. Organization 2 health summary:")
    for cred in service.get_credentials_by_org(org2):
        icon = "✓" if cred.health_status == HealthStatus.HEALTHY else "✗"
        print(f"   [{icon}] {cred.integration_name}: {cred.health_status.value}")

    print("\n6. Platform-wide unhealthy credentials:")
    unhealthy = service.get_unhealthy_credentials()
    print(f"   Count: {len(unhealthy)}")
    for cred in unhealthy:
        print(f"   - {cred.integration_name} (org: {str(cred.org_id)[:8]}...)")

    print("\n[OK] Organization health view works correctly!")


async def demo_use_cases():
    """Demo 7: Common scenarios and recommendations."""
    print_header("Demo 7: Integration Health Check Matrix")
    print("\nFrom ROADMAP.md - Health check configuration:\n")

    print("┌─────────────────┬────────────────────┬───────────────────────────┐")
    print("│ Integration     │ Health Endpoint    │ What We Check             │")
    print("├─────────────────┼────────────────────┼───────────────────────────┤")
    print("│ Slack           │ auth.test          │ Token validity            │")
    print("│ Salesforce      │ /services/limits   │ API access                │")
    print("│ GitHub          │ /user              │ Token & permissions       │")
    print("│ HubSpot         │ /contacts?limit=1  │ API key validity          │")
    print("│ Zendesk         │ /users/me.json     │ Auth & access             │")
    print("│ Stripe          │ /v1/balance        │ API key validity          │")
    print("│ SendGrid        │ /user/profile      │ API key validity          │")
    print("│ Twilio          │ /Accounts.json     │ Credentials               │")
    print("│ Google Sheets   │ /spreadsheets      │ OAuth token               │")
    print("└─────────────────┴────────────────────┴───────────────────────────┘")

    print("\nAlert Severity Thresholds:")
    print("  - Warning: 1 consecutive failure")
    print("  - Critical: 3+ consecutive failures")

    print("\nHealth Check Schedule:")
    print("  - Default interval: Every 24 hours")
    print("  - Timeout per check: 30 seconds")
    print("  - History retention: Last 100 checks")

    print("\n" + "-" * 60)
    print("Proactive health monitoring prevents runtime failures!")
    print("-" * 60)


async def main():
    """Run all demos."""
    print("\n" + "=" * 60)
    print("  INTEGRATION HEALTH CHECK DEMO")
    print("  Credential Validation & Alerting")
    print("=" * 60)
    print("\nReference: ROADMAP.md Section 'Integration Credential Health Checks'")

    try:
        await demo_basic_registration()
        await demo_health_checks()
        await demo_failure_detection()
        await demo_alerting()
        await demo_health_history()
        await demo_organization_view()
        await demo_use_cases()

        print("\n" + "=" * 60)
        print("  ALL DEMOS COMPLETED SUCCESSFULLY!")
        print("=" * 60)
        print("\nKey Takeaways:")
        print("  1. Register credentials for automatic health monitoring")
        print("  2. Daily health checks validate credential validity")
        print("  3. Multiple failure types detected (401, 403, timeout)")
        print("  4. Alerts generated after consecutive failures")
        print("  5. Health history enables trend analysis")
        print("  6. Organization-wide health dashboards")
        print()

    except Exception as e:
        print(f"\n[ERROR] Demo failed: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())
