"""
Multi-LLM Routing Demo Script - P1 Feature #3

Demonstrates intelligent LLM routing and cost optimization:
- Provider and model registration
- Smart routing strategies
- Cost tracking and analytics
- A/B testing
- Failover scenarios

Run: python backend/demo_multi_llm_routing.py
"""

import sys
from pathlib import Path

# Add parent directory to path so backend.* imports work
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

import asyncio
from sqlalchemy import text

from backend.database.session import AsyncSessionLocal, init_db
from backend.shared.llm_models import (
    LLMProviderCreate,
    LLMModelCreate,
    LLMRequestCreate,
    LLMRoutingRequest,
    ModelComparisonCreate,
    LLMProvider,
    RoutingStrategy,
    ModelCapability,
)
from backend.shared.llm_service import LLMRoutingService
from backend.llm.provider_configs import PROVIDER_CONFIGS


async def demo_multi_llm_routing():
    """Run complete demonstration of multi-LLM routing."""

    async with AsyncSessionLocal() as db:
        print("=" * 80)
        print("MULTI-LLM ROUTING & COST OPTIMIZATION DEMO")
        print("=" * 80)
        print()

        # Drop and recreate LLM tables to fix ENUM type mismatches
        print("Setting up demo environment...")
        try:
            await db.execute(text("DROP TABLE IF EXISTS llm_model_comparisons CASCADE"))
            await db.execute(text("DROP TABLE IF EXISTS llm_routing_rules CASCADE"))
            await db.execute(text("DROP TABLE IF EXISTS llm_requests CASCADE"))
            await db.execute(text("DROP TABLE IF EXISTS llm_models CASCADE"))
            await db.execute(text("DROP TABLE IF EXISTS llm_providers CASCADE"))
            await db.execute(text("DROP TYPE IF EXISTS llmprovider CASCADE"))
            await db.execute(text("DROP TYPE IF EXISTS routingstrategy CASCADE"))
            await db.execute(text("DROP TYPE IF EXISTS modelcapability CASCADE"))
            await db.commit()
            print("✓ Cleaned up old tables and types")
        except Exception as e:
            print(f"⚠ Cleanup warning: {str(e)[:100]}")
            await db.rollback()

    # Reinitialize database tables
    await init_db()

    async with AsyncSessionLocal() as db:
        # Tables are fresh after drop/recreate, no cleanup needed
        print("✓ Database ready\n")

        # Demo 1: Register LLM Providers
        print("📦 DEMO 1: Registering LLM Providers")
        print("-" * 80)

        providers = {}
        for provider_type in [LLMProvider.OPENAI, LLMProvider.ANTHROPIC, LLMProvider.GOOGLE]:
            config = PROVIDER_CONFIGS[provider_type]
            print(f"\n1. Registering {config['name']}...")

            provider_data = LLMProviderCreate(
                provider=provider_type,
                name=config["name"],
                description=config["description"],
                api_key=f"sk-test-{provider_type.value}",  # Demo key
                api_endpoint=config["api_endpoint"],
                is_default=(provider_type == LLMProvider.OPENAI),
            )

            provider = await LLMRoutingService.create_provider(
                db, provider_data, user_id="user_1", organization_id=1
            )

            providers[provider_type] = provider
            print(f"   ✓ Provider ID: {provider.id}")
            print(f"   ✓ Endpoint: {provider.api_endpoint}")
            print(f"   ✓ Default: {provider.is_default}")

        print(f"\n✅ Registered {len(providers)} providers")
        print()

        # Demo 2: Register Models
        print("🤖 DEMO 2: Registering LLM Models")
        print("-" * 80)

        models = []
        for provider_type, provider in providers.items():
            config = PROVIDER_CONFIGS[provider_type]
            print(f"\n{config['name']} models:")

            for model_config in config["models"]:
                model_data = LLMModelCreate(
                    provider_id=provider.id,
                    **model_config
                )

                model = await LLMRoutingService.create_model(db, model_data, user_id="user_1")
                models.append(model)

                print(f"  - {model.display_name}")
                print(f"    Cost: ${model.input_cost_per_1m_tokens:.2f}/${model.output_cost_per_1m_tokens:.2f} per 1M tokens")
                print(f"    Max tokens: {model.max_tokens:,}")
                print(f"    Capabilities: {len(model.capabilities)}")

        print(f"\n✅ Registered {len(models)} models")
        print()

        # Demo 3: Smart Routing
        print("🧠 DEMO 3: Smart Routing Strategies")
        print("-" * 80)

        test_cases = [
            {
                "task": "Simple customer support response",
                "strategy": RoutingStrategy.COST_OPTIMIZED,
                "prompt": "Thank you for contacting us! How can I help you today?",
            },
            {
                "task": "Complex code generation",
                "strategy": RoutingStrategy.BEST_AVAILABLE,
                "prompt": "Write a Python function to implement quicksort",
                "required_capabilities": [ModelCapability.CODE_GENERATION],
            },
            {
                "task": "Balanced content creation",
                "strategy": RoutingStrategy.PRIMARY_WITH_BACKUP,
                "prompt": "Write a blog post about AI in healthcare",
            },
            {
                "task": "Vision task",
                "strategy": RoutingStrategy.BEST_AVAILABLE,
                "prompt": "Describe this image",
                "required_capabilities": [ModelCapability.VISION],
            },
        ]

        for i, test_case in enumerate(test_cases, 1):
            print(f"\n{i}. {test_case['task']}")
            print(f"   Strategy: {test_case['strategy'].value}")

            routing_request = LLMRoutingRequest(
                prompt=test_case["prompt"],
                max_tokens=500,
                routing_strategy=test_case["strategy"],
                required_capabilities=test_case.get("required_capabilities", []),
            )

            try:
                routing = await LLMRoutingService.route_llm_request(
                    db, routing_request, user_id="user_1", organization_id=1
                )

                print(f"   ✓ Selected: {routing.selected_model_name}")
                print(f"   ✓ Provider: {routing.provider if isinstance(routing.provider, str) else routing.provider.value}")
                print(f"   ✓ Est. cost: ${routing.estimated_cost:.6f}")
                print(f"   ✓ Est. latency: {routing.estimated_latency_ms:.0f}ms")
                print(f"   ✓ Reasoning: {routing.reasoning}")
                print(f"   ✓ Fallbacks: {len(routing.fallback_model_ids)} models")
            except ValueError as e:
                print(f"   ❌ Error: {e}")

        print()

        # Demo 4: Request Logging & Cost Tracking
        print("💰 DEMO 4: Request Logging & Cost Tracking")
        print("-" * 80)

        print("\n1. Simulating API requests...")

        # Simulate some requests
        for model in models[:3]:  # Use first 3 models
            for _ in range(5):  # 5 requests per model
                request_data = LLMRequestCreate(
                    model_id=model.id,
                    prompt_tokens=500,
                    completion_tokens=300,
                    latency_ms=850.0,
                    status="success",
                    routing_strategy=RoutingStrategy.PRIMARY_WITH_BACKUP,
                )

                await LLMRoutingService.log_request(
                    db, request_data, user_id="user_1", organization_id=1
                )

        print("   ✓ Logged 15 requests")

        # Get analytics
        print("\n2. Cost analytics:")
        analytics = await LLMRoutingService.get_cost_analytics(db, organization_id=1)

        print(f"   Total cost: ${analytics['total_cost']:.4f}")
        print(f"   Total tokens: {analytics['total_tokens']:,}")
        print(f"   Total requests: {analytics['total_requests']}")
        print(f"   Avg latency: {analytics['avg_latency_ms']:.0f}ms")

        print("\n3. Cost by model:")
        for model_cost in analytics['cost_by_model']:
            print(f"   - {model_cost['model']}: ${model_cost['cost']:.4f} ({model_cost['requests']} requests)")

        print()

        # Demo 5: A/B Testing
        print("🔬 DEMO 5: A/B Testing Framework")
        print("-" * 80)

        if len(models) >= 2:
            model_a = models[0]  # GPT-4 Turbo
            model_b = models[1]  # GPT-4

            print(f"\n1. Creating comparison: {model_a.display_name} vs {model_b.display_name}")

            comparison_data = ModelComparisonCreate(
                name="GPT-4 Turbo vs GPT-4 for code generation",
                description="Compare models for code generation tasks",
                model_a_id=model_a.id,
                model_b_id=model_b.id,
                test_cases=[
                    {"prompt": "Write a Python function to sort a list", "expected_quality": 0.9},
                    {"prompt": "Create a React component for a login form", "expected_quality": 0.85},
                    {"prompt": "Implement binary search in JavaScript", "expected_quality": 0.9},
                ],
                evaluation_criteria=["correctness", "efficiency", "readability"],
            )

            comparison = await LLMRoutingService.create_model_comparison(
                db, comparison_data, user_id="user_1", organization_id=1
            )

            print(f"   ✓ Comparison created: ID {comparison.id}")
            print(f"   ✓ Test cases: {len(comparison.test_cases)}")
            print(f"   ✓ Status: {comparison.status}")

            # Execute comparison
            print("\n2. Executing A/B test...")
            result = await LLMRoutingService.execute_comparison(db, comparison.id)

            print(f"   ✓ Status: {result.status}")
            print(f"\n3. Results:")
            print(f"   Model A ({model_a.display_name}):")
            print(f"     - Avg cost: ${result.model_a_avg_cost:.4f}")
            print(f"     - Avg latency: {result.model_a_avg_latency:.0f}ms")
            print(f"     - Avg quality: {result.model_a_avg_quality:.2f}")

            print(f"\n   Model B ({model_b.display_name}):")
            print(f"     - Avg cost: ${result.model_b_avg_cost:.4f}")
            print(f"     - Avg latency: {result.model_b_avg_latency:.0f}ms")
            print(f"     - Avg quality: {result.model_b_avg_quality:.2f}")

            winner = models[0] if result.winner_model_id == model_a.id else models[1]
            print(f"\n   🏆 Winner: {winner.display_name}")
            print(f"   Confidence: {result.confidence_score:.0%}")

        print()

        # Demo 6: Model Recommendations
        print("💡 DEMO 6: Model Recommendations")
        print("-" * 80)

        task_types = ["code", "vision", "reasoning"]
        for task_type in task_types:
            print(f"\n1. Best models for '{task_type}' tasks:")

            recommendations = await LLMRoutingService.get_model_recommendations(
                db, task_type, organization_id=1
            )

            for i, model in enumerate(recommendations[:3], 1):
                print(f"   {i}. {model.display_name}")
                provider_val = model.provider.provider if isinstance(model.provider.provider, str) else model.provider.provider.value
                print(f"      Provider: {provider_val}")
                print(f"      Quality: {model.avg_quality_score:.2f}")
                print(f"      Cost: ${model.input_cost_per_1m_tokens + model.output_cost_per_1m_tokens:.2f}/1M tokens")

        print()

        # Demo 7: Routing Summary
        print("📊 DEMO 7: Routing Strategy Comparison")
        print("-" * 80)

        print("\nFor a typical 1000-token request:")
        print()

        strategies = [
            RoutingStrategy.COST_OPTIMIZED,
            RoutingStrategy.LATENCY_OPTIMIZED,
            RoutingStrategy.BEST_AVAILABLE,
            RoutingStrategy.PRIMARY_WITH_BACKUP,
        ]

        routing_request = LLMRoutingRequest(
            prompt="Analyze this data and provide insights",
            max_tokens=1000,
            routing_strategy=RoutingStrategy.PRIMARY_WITH_BACKUP,  # Will be overridden
        )

        print(f"{'Strategy':<20} {'Model':<25} {'Est. Cost':<12} {'Latency':<10}")
        print("-" * 70)

        for strategy in strategies:
            routing_request.routing_strategy = strategy
            try:
                routing = await LLMRoutingService.route_llm_request(
                    db, routing_request, user_id="user_1", organization_id=1
                )

                print(f"{strategy.value:<20} {routing.selected_model_name:<25} "
                      f"${routing.estimated_cost:<11.6f} {routing.estimated_latency_ms:<9.0f}ms")
            except ValueError:
                print(f"{strategy.value:<20} {'No suitable model':<25}")

        print()

        # Summary
        print("=" * 80)
        print("DEMO SUMMARY")
        print("=" * 80)
        print()
        print("✅ Provider Registration: 3 providers (OpenAI, Anthropic, Google)")
        print("✅ Model Registration: 7 models with pricing and capabilities")
        print("✅ Smart Routing: 4 strategies demonstrated (cost, quality, balanced, capability)")
        print("✅ Cost Tracking: Real-time analytics with model-level breakdown")
        print("✅ A/B Testing: Compare models on quality, cost, and latency")
        print("✅ Recommendations: Get best models for specific tasks")
        print("✅ Failover: Automatic fallback options for reliability")
        print()
        print("🎉 Multi-LLM routing enables:")
        print("   - No vendor lock-in (use any provider)")
        print("   - Cost optimization (route to cheapest suitable model)")
        print("   - High reliability (automatic failover)")
        print("   - Performance tuning (A/B test different models)")
        print()


if __name__ == "__main__":
    asyncio.run(demo_multi_llm_routing())
