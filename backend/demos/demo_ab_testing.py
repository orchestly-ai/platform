"""
A/B Testing Framework Demo - P1 Feature #2

Demonstrates complete A/B testing workflow:
- Creating experiments with multiple variants
- Traffic splitting and variant assignment  
- Recording outcomes and metrics
- Statistical analysis and winner selection
- Gradual rollout

Run: python backend/demo_ab_testing.py
"""

import sys
from pathlib import Path

# Add parent directory to path so backend.* imports work
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

import asyncio
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker
from sqlalchemy import text

from backend.database.session import AsyncSessionLocal, init_db
from backend.shared.ab_testing_models import *
from backend.shared.ab_testing_service import ABTestingService

DATABASE_URL = "postgresql+asyncpg://localhost/agent_orchestration"

async def demo_ab_testing():
    async with AsyncSessionLocal() as db:
        print("=" * 80)
        print("A/B TESTING FRAMEWORK DEMO")
        print("=" * 80)
        print()

        # Drop and recreate tables to fix ENUM type mismatches
        print("Setting up demo environment...")
        try:
            await db.execute(text("DROP TABLE IF EXISTS ab_metrics CASCADE"))
            await db.execute(text("DROP TABLE IF EXISTS ab_assignments CASCADE"))
            await db.execute(text("DROP TABLE IF EXISTS ab_variants CASCADE"))
            await db.execute(text("DROP TABLE IF EXISTS ab_experiments CASCADE"))
            # Drop old ENUM types if they exist
            await db.execute(text("DROP TYPE IF EXISTS experimentstatus CASCADE"))
            await db.execute(text("DROP TYPE IF EXISTS trafficsplittype CASCADE"))
            await db.execute(text("DROP TYPE IF EXISTS varianttype CASCADE"))
            await db.execute(text("DROP TYPE IF EXISTS winnerselectioncriteria CASCADE"))
            await db.commit()
            print("✓ Cleaned up old tables and types")
        except Exception as e:
            print(f"⚠ Cleanup warning: {str(e)[:100]}")
            await db.rollback()

    await init_db()

    async with AsyncSessionLocal() as db:
        # Tables are fresh after drop/recreate, no cleanup needed
        print("✓ Database ready\n")

        # Demo 1: Create Experiment
        print("🧪 DEMO 1: Create A/B Test Experiment")
        print("-" * 80)
        
        print("\n1. Testing GPT-4 vs Claude-3 for code generation...")
        exp_data = ABExperimentCreate(
            name="GPT-4 vs Claude-3 for Code Generation",
            slug="gpt4-vs-claude3-codegen",
            description="Compare cost and quality for code generation tasks",
            task_type="code_generation",
            traffic_split_strategy=TrafficSplitStrategy.RANDOM,
            hypothesis="Claude-3 provides similar quality at 60% lower cost",
            success_criteria={"min_quality_score": 0.8, "max_cost_increase": 0.1},
            minimum_sample_size=100,
            confidence_level=0.95,
            winner_selection_criteria=WinnerSelectionCriteria.COMPOSITE_SCORE,
            variants=[
                ABVariantCreate(
                    name="Control (GPT-4)",
                    variant_key="control_gpt4",
                    variant_type=VariantType.CONTROL,
                    traffic_percentage=50.0,
                    model_name="gpt-4-turbo",
                    config={"temperature": 0.7, "max_tokens": 2000}
                ),
                ABVariantCreate(
                    name="Treatment (Claude-3)",
                    variant_key="treatment_claude3",
                    variant_type=VariantType.TREATMENT,
                    traffic_percentage=50.0,
                    model_name="claude-3-opus",
                    config={"temperature": 0.7, "max_tokens": 2000}
                )
            ]
        )
        
        exp = await ABTestingService.create_experiment(db, exp_data, "data_scientist", 1)
        print(f"   ✓ Experiment created: {exp.name}")
        print(f"   ✓ Variants: {len(exp_data.variants)}")
        print(f"   ✓ Traffic split: {exp.traffic_split_strategy}")
        print(f"   ✓ Status: {exp.status}")
        
        # Demo 2: Start Experiment
        print("\n\n▶️  DEMO 2: Start Experiment")
        print("-" * 80)
        exp = await ABTestingService.start_experiment(db, exp.id)
        print(f"   ✓ Status changed to: {exp.status}")
        print(f"   ✓ Started at: {exp.started_at}")
        
        # Demo 3: Traffic Assignment
        print("\n\n👥 DEMO 3: Variant Assignment (Traffic Splitting)")
        print("-" * 80)
        print("\n1. Simulating 200 user assignments...")
        
        assignments = []
        for i in range(200):
            assignment = await ABTestingService.assign_variant(
                db, exp.id,
                ABAssignmentCreate(user_id=f"user_{i}", execution_id=1000+i)
            )
            assignments.append(assignment)
        
        # Count assignments per variant
        from collections import Counter
        from sqlalchemy import select
        variant_counts = Counter(a.variant_id for a in assignments)
        print(f"   ✓ Assigned 200 users")
        print(f"   ✓ Distribution:")

        # Get variants separately to avoid lazy loading
        stmt = select(ABVariant).where(ABVariant.experiment_id == exp.id)
        result = await db.execute(stmt)
        variants = result.scalars().all()

        for v in variants:
            count = variant_counts.get(v.id, 0)
            pct = (count / 200) * 100
            print(f"      - {v.name}: {count} ({pct:.1f}%)")
        
        # Demo 4: Record Outcomes
        print("\n\n📊 DEMO 4: Record Experiment Outcomes")
        print("-" * 80)
        print("\n1. Simulating execution results...")
        
        import random
        # Create variant lookup dict to avoid lazy loading
        variant_lookup = {v.id: v for v in variants}

        for assignment in assignments:
            # Get variant to simulate realistic outcomes
            variant = variant_lookup[assignment.variant_id]
            
            # Simulate results (Claude-3 cheaper but similar success)
            if "gpt4" in variant.variant_key:
                success = random.random() < 0.85  # 85% success
                latency = random.uniform(800, 1500)  # 0.8-1.5s
                cost = random.uniform(0.015, 0.025)  # $0.015-0.025
            else:  # Claude-3
                success = random.random() < 0.83  # 83% success (slightly lower)
                latency = random.uniform(700, 1300)  # Faster
                cost = random.uniform(0.006, 0.012)  # 60% cheaper
            
            await ABTestingService.record_completion(
                db,
                ABCompletionRequest(
                    assignment_id=assignment.id,
                    success=success,
                    latency_ms=latency,
                    cost=cost,
                    custom_metrics={"code_quality_score": random.uniform(0.7, 0.95)}
                )
            )
        
        print("   ✓ Recorded 200 execution outcomes")
        
        # Refresh variants to see updated metrics
        from sqlalchemy import select
        stmt = select(ABVariant).where(ABVariant.experiment_id == exp.id)
        result = await db.execute(stmt)
        variants = result.scalars().all()
        
        print("\n2. Variant performance:")
        for v in variants:
            print(f"\n   {v.name}:")
            print(f"      Samples: {v.sample_count}")
            print(f"      Success rate: {v.success_rate:.1f}%")
            print(f"      Avg latency: {v.avg_latency_ms:.0f}ms")
            print(f"      Avg cost: ${v.avg_cost:.4f}")
        
        # Demo 5: Statistical Analysis
        print("\n\n📈 DEMO 5: Statistical Analysis & Winner Selection")
        print("-" * 80)
        
        results = await ABTestingService.analyze_experiment(db, exp.id)
        
        print(f"\n1. Statistical significance:")
        print(f"   ✓ Statistically significant: {results.is_statistically_significant}")
        print(f"   ✓ P-value: {results.p_value:.4f}" if results.p_value else "   - P-value: N/A")
        print(f"   ✓ Confidence level: {results.confidence_level:.0%}")
        
        print(f"\n2. Winner:")
        if results.winner_variant_id:
            winner = next(v for v in variants if v.id == results.winner_variant_id)
            print(f"   🏆 {winner.name}")
            print(f"   ✓ Confidence: {results.winner_confidence:.0%}")
        
        print(f"\n3. Recommendation:")
        print(f"   {results.recommendation}")
        
        print(f"\n4. Insights:")
        for insight in results.insights:
            print(f"   - {insight}")
        
        # Demo 6: Complete & Promote Winner
        print("\n\n✅ DEMO 6: Complete Experiment & Promote Winner")
        print("-" * 80)
        
        exp = await ABTestingService.complete_experiment(db, exp.id, promote_winner=True)
        print(f"   ✓ Status: {exp.status}")
        print(f"   ✓ Completed at: {exp.completed_at}")
        print(f"   ✓ Winner promoted: {exp.promoted_at is not None}")
        
        # Summary
        print("\n\n" + "=" * 80)
        print("DEMO SUMMARY")
        print("=" * 80)
        print("\n✅ A/B Testing Features:")
        print("   - Experiment creation with multiple variants")
        print("   - Traffic splitting (random, weighted, user-hash, round-robin)")
        print("   - Variant assignment and outcome tracking")
        print("   - Statistical significance testing")
        print("   - Automatic winner selection")
        print("   - Performance metrics comparison")
        print()
        print("✅ Metrics Tracked:")
        print("   - Success rate (%)")
        print("   - Latency (ms)")
        print("   - Cost ($)")
        print("   - Custom metrics (quality scores, etc.)")
        print()
        print("✅ Business Impact:")
        print("   - Data-driven decisions (no guessing)")
        print("   - Risk mitigation (test before full rollout)")
        print("   - Cost optimization (find cheapest effective variant)")
        print("   - Continuous improvement (always testing)")
        print()
        print("🎉 A/B testing enables scientific agent optimization!")
        print()

if __name__ == "__main__":
    asyncio.run(demo_ab_testing())
