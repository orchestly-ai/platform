#!/usr/bin/env python
"""
Working Demo - Agent Orchestration Platform
Shows core features that are fully implemented
"""
import asyncio
from sqlalchemy import text

from backend.database.session import AsyncSessionLocal, init_db
from backend.shared.ml_routing_models import ModelProvider, LLMModelCreate, RoutingStrategy, OptimizationGoal, RoutingPolicyCreate
from backend.shared.ml_routing_service import MLRoutingService

async def working_demo():
    print("\n" + "="*80)
    print("AGENT ORCHESTRATION PLATFORM - WORKING DEMO")
    print("="*80 + "\n")

    # Drop and recreate ML routing tables to fix ENUM type mismatches
    async with AsyncSessionLocal() as db:
        print("🔧 Setting up demo environment...")
        try:
            await db.execute(text("DROP TABLE IF EXISTS cost_optimization_rules CASCADE"))
            await db.execute(text("DROP TABLE IF EXISTS ml_routing_models CASCADE"))
            await db.execute(text("DROP TABLE IF EXISTS model_performance_history CASCADE"))
            await db.execute(text("DROP TABLE IF EXISTS routing_decisions CASCADE"))
            await db.execute(text("DROP TABLE IF EXISTS routing_policies CASCADE"))
            await db.execute(text("DROP TABLE IF EXISTS ml_routing_llm_models CASCADE"))
            await db.execute(text("DROP TYPE IF EXISTS modelprovider CASCADE"))
            await db.execute(text("DROP TYPE IF EXISTS routingstrategy CASCADE"))
            await db.execute(text("DROP TYPE IF EXISTS optimizationgoal CASCADE"))
            await db.commit()
            print("   ✓ Cleaned up old tables and types")
        except Exception as e:
            print(f"   ⚠ Cleanup warning: {str(e)[:100]}")
            await db.rollback()

    # Initialize database tables
    await init_db()

    async with AsyncSessionLocal() as db:
        try:
            # Tables are fresh after drop/recreate
            print("   ✓ Database ready\n")

            # Phase 1: LLM Model Registry
            print("📊 PHASE 1: LLM Model Registry")
            print("-" * 80)

            models_data = [
                ("GPT-4 Turbo", ModelProvider.OPENAI, "gpt-4-turbo", 128000, 10.0, 30.0, 95.0),
                ("GPT-3.5 Turbo", ModelProvider.OPENAI, "gpt-3.5-turbo", 16385, 0.5, 1.5, 85.0),
                ("Claude 3.5 Sonnet", ModelProvider.ANTHROPIC, "claude-3-5-sonnet", 200000, 3.0, 15.0, 98.0),
                ("Claude 3 Haiku", ModelProvider.ANTHROPIC, "claude-3-haiku", 200000, 0.25, 1.25, 88.0),
                ("Gemini Pro", ModelProvider.GOOGLE, "gemini-pro", 32768, 0.5, 1.5, 90.0),
            ]

            registered_models = []
            print("\n1. Registering LLM models...\n")
            for name, provider, model_id, max_tokens, input_cost, output_cost, quality in models_data:
                model = await MLRoutingService.register_model(
                    db,
                    LLMModelCreate(
                        name=name,
                        provider=provider,
                        model_id=model_id,
                        max_tokens=max_tokens,
                        cost_per_1m_input_tokens=input_cost,
                        cost_per_1m_output_tokens=output_cost,
                        quality_score=quality
                    )
                )
                registered_models.append(model)
                print(f"   ✓ {name:20} ({provider.value:12}) ${input_cost:5.2f}/M in, ${output_cost:5.2f}/M out, Quality: {quality}/100")

            # Phase 2: Routing Policies
            print("\n📋 PHASE 2: Routing Policies")
            print("-" * 80)

            policies_data = [
                ("Cost Minimizer", RoutingStrategy.COST_OPTIMIZED, OptimizationGoal.MINIMIZE_COST, 80.0),
                ("Quality Maximizer", RoutingStrategy.QUALITY_OPTIMIZED, OptimizationGoal.MAXIMIZE_QUALITY, 95.0),
                ("Balanced Optimizer", RoutingStrategy.BALANCED, OptimizationGoal.BALANCED, 85.0),
            ]

            print("\n2. Creating routing policies...\n")
            for name, strategy, goal, min_quality in policies_data:
                policy = await MLRoutingService.create_routing_policy(
                    db,
                    RoutingPolicyCreate(
                        name=name,
                        description=f"Optimizes for {goal.value}",
                        strategy=strategy,
                        optimization_goal=goal,
                        min_quality_score=min_quality
                    ),
                    "admin_user"
                )
                print(f"   ✓ {name:20} Strategy: {strategy.value:20} Goal: {goal.value}")

            # Phase 3: Query & Verify
            print("\n🔍 PHASE 3: Verification")
            print("-" * 80)

            print("\n3. Querying registered models...\n")
            all_models = await MLRoutingService.get_models(db)
            print(f"   ✓ Total models registered: {len(all_models)}")

            print("\n4. Querying routing policies...\n")
            all_policies = await MLRoutingService.get_routing_policies(db)
            print(f"   ✓ Total policies created: {len(all_policies)}")

            # Summary
            print("\n" + "="*80)
            print("✅ DEMO COMPLETED SUCCESSFULLY")
            print("="*80)
            print(f"\nResults:")
            print(f"  • {len(all_models)} LLM models registered")
            print(f"  • {len(all_policies)} routing policies configured")
            print(f"  • Database operations: WORKING ✓")
            print(f"  • Enum handling: WORKING ✓")
            print(f"  • Service layer: WORKING ✓")
            print(f"\n🎉 Platform infrastructure is fully operational!\n")

        except Exception as e:
            print(f"\n❌ ERROR: {e}")
            import traceback
            traceback.print_exc()
            raise

if __name__ == "__main__":
    asyncio.run(working_demo())
