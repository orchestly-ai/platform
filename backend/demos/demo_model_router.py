#!/usr/bin/env python3
"""
Demo: Model Router Backend

Demonstrates the model router with health monitoring and routing strategies.
"""

import asyncio
import sys
from pathlib import Path

# Add parent directory to path so backend.* imports work
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from backend.database.session import AsyncSessionLocal, init_db
from backend.router import (
    get_model_registry,
    get_health_monitor,
    get_routing_engine,
)
from backend.router.strategies import RoutingRequest


def print_header(title: str):
    """Print a formatted header."""
    print("\n" + "=" * 80)
    print(f"  {title}")
    print("=" * 80 + "\n")


def print_section(title: str):
    """Print a section header."""
    print(f"\n--- {title} ---\n")


async def main():
    """Run the model router demo."""
    print_header("MODEL ROUTER DEMO")

    # Initialize database
    await init_db()

    # Get database session using async context manager
    async with AsyncSessionLocal() as db:
        # Initialize components
        registry = get_model_registry(db)
        monitor = get_health_monitor(db)
        engine = get_routing_engine(db)

        # Test organization
        org_id = "demo-org-001"

        # ====================================================================
        # 1. Seed Default Models
        # ====================================================================
        print_section("1. Seeding Default Models")

        registry.seed_default_models(org_id)
        print("✅ Seeded default models for organization")

        # List models
        models = registry.list_models(org_id)
        print(f"\n📋 Available Models ({len(models)}):")
        for model in models:
            print(f"   • {model.display_name} ({model.provider})")
            print(f"     Cost: ${model.cost_per_1k_input_tokens:.6f}/1K input, "
                  f"${model.cost_per_1k_output_tokens:.6f}/1K output")
            print(f"     Quality: {model.quality_score:.2f}, Max tokens: {model.max_tokens}")

        # ====================================================================
        # 2. Simulate Health Metrics
        # ====================================================================
        print_section("2. Simulating Health Metrics")

        # Simulate some requests for health tracking
        print("Simulating requests to build health metrics...")

        for model in models[:3]:  # Simulate for first 3 models
            # Simulate 10 successful requests
            for i in range(10):
                latency = 500 + i * 100  # Varying latency
                await monitor.track_request(
                    model_id=model.id,
                    latency_ms=latency,
                    success=True,
                )

        # Simulate some failures for one model
        unhealthy_model = models[0]
        for i in range(5):
            await monitor.track_request(
                model_id=unhealthy_model.id,
                latency_ms=15000,  # Very high latency
                success=False,
                error="Timeout",
            )

        print("✅ Simulated health metrics")

        # Show health status
        print("\n📊 Health Status:")
        for model in models[:3]:
            health = monitor.get_health(model.id)
            status = "✅ Healthy" if health.is_healthy else "❌ Unhealthy"
            print(f"   {status} {model.display_name}")
            if health.latency_p50_ms:
                print(f"     P50: {health.latency_p50_ms}ms, "
                      f"P95: {health.latency_p95_ms}ms, "
                      f"P99: {health.latency_p99_ms}ms")
            if health.success_rate is not None:
                print(f"     Success rate: {health.success_rate*100:.1f}%")

        # ====================================================================
        # 3. Create Routing Strategies
        # ====================================================================
        print_section("3. Creating Routing Strategies")

        # Create cost-optimized strategy for organization
        cost_strategy_id = engine.create_strategy(
            organization_id=org_id,
            strategy_type="cost",
            scope_type="organization",
            config={"min_quality": 0.7},
        )
        print(f"✅ Created cost-optimized strategy: {cost_strategy_id}")

        # Create latency-optimized strategy for a workflow
        latency_strategy_id = engine.create_strategy(
            organization_id=org_id,
            strategy_type="latency",
            scope_type="workflow",
            scope_id="workflow-123",
        )
        print(f"✅ Created latency-optimized strategy for workflow: {latency_strategy_id}")

        # Create quality-first strategy for a specific agent
        quality_strategy_id = engine.create_strategy(
            organization_id=org_id,
            strategy_type="quality",
            scope_type="agent",
            scope_id="agent-456",
        )
        print(f"✅ Created quality-first strategy for agent: {quality_strategy_id}")

        # Create weighted round-robin strategy
        weighted_strategy_id = engine.create_strategy(
            organization_id=org_id,
            strategy_type="weighted_rr",
            scope_type="organization",
            config={},
        )

        # Add model weights for A/B testing
        if len(models) >= 2:
            engine.add_model_weight(weighted_strategy_id, models[0].id, weight=0.8)
            engine.add_model_weight(weighted_strategy_id, models[1].id, weight=0.2)
            print(f"✅ Created weighted round-robin strategy with A/B weights")

        # ====================================================================
        # 4. Test Routing Decisions
        # ====================================================================
        print_section("4. Testing Routing Decisions")

        # Test 1: Cost-optimized routing
        print("Test 1: Cost-optimized routing (organization-level)")
        request = RoutingRequest(min_quality=0.7)
        decision = engine.route(org_id, request, scope_type="organization")

        if decision:
            print(f"   ✅ Selected: {decision.provider}/{decision.model_name}")
            print(f"      Strategy: {decision.strategy_used}")
        else:
            print("   ❌ No suitable model found")

        # Test 2: Latency-optimized for workflow
        print("\nTest 2: Latency-optimized routing (workflow-level)")
        request = RoutingRequest()
        decision = engine.route(
            org_id, request, scope_type="workflow", scope_id="workflow-123"
        )

        if decision:
            print(f"   ✅ Selected: {decision.provider}/{decision.model_name}")
            print(f"      Strategy: {decision.strategy_used}")
        else:
            print("   ❌ No suitable model found")

        # Test 3: Quality-first for agent
        print("\nTest 3: Quality-first routing (agent-level)")
        request = RoutingRequest()
        decision = engine.route(
            org_id, request, scope_type="agent", scope_id="agent-456"
        )

        if decision:
            print(f"   ✅ Selected: {decision.provider}/{decision.model_name}")
            print(f"      Strategy: {decision.strategy_used}")
        else:
            print("   ❌ No suitable model found")

        # Test 4: Routing with constraints
        print("\nTest 4: Routing with vision requirement")
        request = RoutingRequest(require_vision=True, max_cost=0.01)
        decision = engine.route(org_id, request, scope_type="organization")

        if decision:
            print(f"   ✅ Selected: {decision.provider}/{decision.model_name}")
            print(f"      Strategy: {decision.strategy_used}")
        else:
            print("   ❌ No suitable model found")

        # Test 5: Routing with strict constraints (may fail)
        print("\nTest 5: Routing with very strict constraints")
        request = RoutingRequest(
            min_quality=0.99,
            max_cost=0.0001,  # Very low cost
            require_vision=True,
            require_tools=True,
            max_latency_ms=100,  # Very low latency
        )
        decision = engine.route(org_id, request, scope_type="organization")

        if decision:
            print(f"   ✅ Selected: {decision.provider}/{decision.model_name}")
        else:
            print("   ℹ️  No model meets all constraints (expected)")

        # ====================================================================
        # 5. Health Dashboard
        # ====================================================================
        print_section("5. Health Dashboard")

        dashboard = monitor.get_dashboard_data(org_id)
        print(f"Total models: {dashboard['total_models']}")
        print(f"Healthy models: {dashboard['healthy_models']}")
        print(f"Unhealthy models: {dashboard['unhealthy_models']}")
        print(f"Total requests: {dashboard['total_requests']}")

        # ====================================================================
        # 6. List All Strategies
        # ====================================================================
        print_section("6. All Routing Strategies")

        strategies = engine.list_strategies(org_id)
        print(f"Total strategies: {len(strategies)}")

        for strategy in strategies[:5]:  # Show first 5
            status = "✅ Active" if strategy['is_active'] else "❌ Inactive"
            print(f"\n{status} {strategy['strategy_type']}")
            print(f"   ID: {strategy['id']}")
            print(f"   Scope: {strategy['scope_type']}")
            if strategy['scope_id']:
                print(f"   Scope ID: {strategy['scope_id']}")

        # ====================================================================
        # Summary
        # ====================================================================
        print_section("Summary")

        print("✅ Model Router Demo Complete!")
        print(f"\nComponents tested:")
        print(f"   • ModelRegistry: {len(models)} models registered")
        print(f"   • HealthMonitor: Tracking {len(models)} models")
        print(f"   • RoutingEngine: {len(strategies)} strategies configured")
        print(f"   • Routing Strategies: cost, latency, quality, weighted_rr")
        print()
        print("Architecture verified:")
        print("   Request → RoutingEngine → Strategy → ModelSelector → LLMGateway")
        print("                  ↑              ↑")
        print("           HealthMonitor   ModelRegistry")

        print_header("DEMO COMPLETE")


if __name__ == "__main__":
    asyncio.run(main())
