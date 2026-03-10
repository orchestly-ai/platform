#!/usr/bin/env python
"""
Simple test to verify platform infrastructure works
"""
import asyncio
from backend.database.session import AsyncSessionLocal
from backend.shared.ml_routing_models import ModelProvider, LLMModelCreate, RoutingStrategy, OptimizationGoal, RoutingPolicyCreate
from backend.shared.ml_routing_service import MLRoutingService

async def test_platform():
    print("\n" + "="*80)
    print("AGENT ORCHESTRATION PLATFORM - INFRASTRUCTURE TEST")
    print("="*80 + "\n")

    async with AsyncSessionLocal() as db:
        try:
            # Clean up old test data first
            print("Cleaning up old test data...")
            from sqlalchemy import delete
            from backend.shared.ml_routing_models import LLMModel, RoutingPolicy
            await db.execute(delete(RoutingPolicy))
            await db.execute(delete(LLMModel))
            await db.commit()
            print("✓ Database cleaned\n")

            # Test 1: Register LLM Models
            print("✓ Test 1: Registering LLM models...")
            gpt4 = await MLRoutingService.register_model(
                db,
                LLMModelCreate(
                    name="GPT-4 Turbo",
                    provider=ModelProvider.OPENAI,
                    model_id="gpt-4-turbo",
                    max_tokens=128000,
                    supports_functions=True,
                    cost_per_1m_input_tokens=10.0,
                    cost_per_1m_output_tokens=30.0,
                    quality_score=95.0
                )
            )
            print(f"  → Registered: {gpt4.name} (ID: {gpt4.id})")

            claude = await MLRoutingService.register_model(
                db,
                LLMModelCreate(
                    name="Claude 3 Haiku",
                    provider=ModelProvider.ANTHROPIC,
                    model_id="claude-3-haiku",
                    max_tokens=200000,
                    cost_per_1m_input_tokens=0.25,
                    cost_per_1m_output_tokens=1.25,
                    quality_score=85.0
                )
            )
            print(f"  → Registered: {claude.name} (ID: {claude.id})")

            # Test 2: Create Routing Policy
            print("\n✓ Test 2: Creating routing policy...")
            policy = await MLRoutingService.create_routing_policy(
                db,
                RoutingPolicyCreate(
                    name="Cost Optimizer",
                    description="Balance cost and quality",
                    strategy=RoutingStrategy.BALANCED,
                    optimization_goal=OptimizationGoal.MINIMIZE_COST,
                    min_quality_score=85.0
                ),
                created_by="test_user"
            )
            print(f"  → Created policy: {policy.name} (ID: {policy.id})")
            print(f"  → Strategy: {policy.strategy}")
            print(f"  → Goal: {policy.optimization_goal}")

            # Test 3: Query models
            print("\n✓ Test 3: Querying registered models...")
            models = await MLRoutingService.get_models(db)
            print(f"  → Found {len(models)} models:")
            for m in models:
                print(f"     • {m.name} ({m.provider}) - ${m.cost_per_1m_input_tokens}/M tokens")

            print("\n" + "="*80)
            print("ALL TESTS PASSED! ✓")
            print("="*80 + "\n")

        except Exception as e:
            print(f"\n❌ ERROR: {e}")
            import traceback
            traceback.print_exc()
            raise

if __name__ == "__main__":
    asyncio.run(test_platform())
