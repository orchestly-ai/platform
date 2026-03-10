"""
Enterprise Pricing Configuration Demo

Demonstrates how enterprises can configure custom LLM pricing rates:
- Viewing public list pricing for all providers
- Configuring organization-specific negotiated rates
- Cost estimation using custom pricing vs public pricing
- Managing multiple pricing configurations per organization

This addresses the requirement that each enterprise has different negotiated
LLM pricing, so hardcoded dollar costs don't work.
"""

import asyncio
import sys
from datetime import datetime, timedelta
from decimal import Decimal
from uuid import uuid4
from typing import Dict, List
from pathlib import Path

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from backend.database.session import AsyncSessionLocal
from backend.shared.llm_pricing import (
    PUBLIC_LIST_PRICING,
    OrganizationPricingConfig,
    calculate_cost_estimate,
    get_available_models,
    get_model_pricing,
    CostEstimate
)
from sqlalchemy import select, func


# =============================================================================
# DEMO SCENARIOS
# =============================================================================

def print_section(title: str):
    """Print a formatted section header"""
    print(f"\n{'='*80}")
    print(f"  {title}")
    print(f"{'='*80}\n")


def print_cost_comparison(public_cost: CostEstimate, custom_cost: CostEstimate):
    """Print side-by-side cost comparison"""
    print(f"\n📊 Cost Comparison:")
    print(f"┌{'─'*78}┐")
    print(f"│ {'Metric':<30} │ {'Public Pricing':>20} │ {'Custom Pricing':>20} │")
    print(f"├{'─'*78}┤")

    # Cost comparison
    savings = public_cost.estimated_cost_usd - custom_cost.estimated_cost_usd
    savings_pct = (savings / public_cost.estimated_cost_usd * 100) if public_cost.estimated_cost_usd > 0 else 0

    print(f"│ {'Total Cost':<30} │ ${public_cost.estimated_cost_usd:>19.4f} │ ${custom_cost.estimated_cost_usd:>19.4f} │")
    print(f"│ {'Input Rate (/M tokens)':<30} │ ${public_cost.input_rate_per_million:>19.2f} │ ${custom_cost.input_rate_per_million:>19.2f} │")
    print(f"│ {'Output Rate (/M tokens)':<30} │ ${public_cost.output_rate_per_million:>19.2f} │ ${custom_cost.output_rate_per_million:>19.2f} │")
    print(f"│ {'Savings':<30} │ ${savings:>19.4f} │ {savings_pct:>18.1f}% │")
    print(f"└{'─'*78}┘")


async def demo_view_public_pricing():
    """Demo 1: View public list pricing for all providers"""
    print_section("Demo 1: Public List Pricing (December 2025)")

    print("Available LLM Providers and Models:\n")

    providers = get_available_models()

    for provider, models in providers.items():
        print(f"\n🏢 {provider.upper()}")
        print(f"   Available models: {len(models)}")

        # Show pricing for each model
        for model in sorted(models)[:5]:  # Show first 5 models
            pricing = get_model_pricing(provider, model)
            print(f"   ├─ {model:<25} "
                  f"Input: ${pricing['input_per_million']:>6.2f}/M  "
                  f"Output: ${pricing['output_per_million']:>6.2f}/M")

        if len(models) > 5:
            print(f"   └─ ... and {len(models) - 5} more models")

    # Summary
    total_providers = len(providers)
    total_models = sum(len(models) for models in providers.values())
    print(f"\n📈 Summary: {total_providers} providers, {total_models} models supported")


async def demo_configure_custom_pricing(db):
    """Demo 2: Configure organization-specific custom pricing"""
    print_section("Demo 2: Configure Custom Enterprise Pricing")

    org_id = "acme-corp"
    user_id = "admin@acme-corp.com"

    print(f"Organization: {org_id}")
    print(f"Administrator: {user_id}\n")

    # Scenario: Acme Corp has negotiated better rates with OpenAI and Anthropic
    custom_configs = [
        {
            "provider": "openai",
            "model_name": "gpt-4o",
            "input_cost_per_million": Decimal("4.00"),  # 20% discount from $5.00
            "output_cost_per_million": Decimal("12.00"),  # 20% discount from $15.00
            "notes": "Enterprise agreement - 20% discount, valid through 2026"
        },
        {
            "provider": "anthropic",
            "model_name": "claude-4.5-sonnet",
            "input_cost_per_million": Decimal("2.40"),  # 20% discount from $3.00
            "output_cost_per_million": Decimal("12.00"),  # 20% discount from $15.00
            "notes": "Annual commitment - 20% discount, minimum $100K spend"
        },
        {
            "provider": "google",
            "model_name": "gemini-2.5-pro",
            "input_cost_per_million": Decimal("1.00"),  # 20% discount from $1.25
            "output_cost_per_million": Decimal("8.00"),  # 20% discount from $10.00
            "notes": "Google Cloud Enterprise agreement - 20% discount"
        }
    ]

    print("Configuring custom pricing rates:\n")

    for config in custom_configs:
        # Get public pricing for comparison
        public_pricing = get_model_pricing(config["provider"], config["model_name"])

        # Create configuration
        pricing_config = OrganizationPricingConfig(
            config_id=str(uuid4()),
            organization_id=org_id,
            provider=config["provider"],
            model_name=config["model_name"],
            input_cost_per_million=config["input_cost_per_million"],
            output_cost_per_million=config["output_cost_per_million"],
            notes=config["notes"],
            effective_date=datetime.now(),
            expiry_date=datetime.now() + timedelta(days=365),
            created_by=user_id,
            is_active=True
        )

        db.add(pricing_config)

        # Calculate discount percentages
        input_discount = ((public_pricing["input_per_million"] - float(config["input_cost_per_million"]))
                         / public_pricing["input_per_million"] * 100)
        output_discount = ((public_pricing["output_per_million"] - float(config["output_cost_per_million"]))
                          / public_pricing["output_per_million"] * 100)

        print(f"✅ {config['provider'].upper()} - {config['model_name']}")
        print(f"   Public:  ${public_pricing['input_per_million']:.2f}/M input, "
              f"${public_pricing['output_per_million']:.2f}/M output")
        print(f"   Custom:  ${float(config['input_cost_per_million']):.2f}/M input ({input_discount:.0f}% off), "
              f"${float(config['output_cost_per_million']):.2f}/M output ({output_discount:.0f}% off)")
        print(f"   Notes:   {config['notes']}\n")

    await db.commit()
    print(f"✅ Successfully configured {len(custom_configs)} custom pricing rates for {org_id}")


async def demo_cost_estimation_comparison():
    """Demo 3: Compare cost estimates with public vs custom pricing"""
    print_section("Demo 3: Cost Estimation - Public vs Custom Pricing")

    # Scenario: Large agent processing job
    input_tokens = 2_500_000  # 2.5M input tokens
    output_tokens = 1_800_000  # 1.8M output tokens

    print(f"📝 Scenario: Large-scale document processing agent")
    print(f"   Input tokens:  {input_tokens:,}")
    print(f"   Output tokens: {output_tokens:,}\n")

    # Test with different models
    test_cases = [
        ("openai", "gpt-4o"),
        ("anthropic", "claude-4.5-sonnet"),
        ("google", "gemini-2.5-pro"),
    ]

    for provider, model in test_cases:
        print(f"\n🔍 Model: {provider.upper()} {model}")

        # Public pricing
        public_cost = calculate_cost_estimate(
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            model_name=model,
            provider=provider
        )

        # Custom pricing (20% discount)
        public_pricing = get_model_pricing(provider, model)
        custom_pricing = {
            "input_per_million": public_pricing["input_per_million"] * 0.8,  # 20% discount
            "output_per_million": public_pricing["output_per_million"] * 0.8
        }

        custom_cost = calculate_cost_estimate(
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            model_name=model,
            provider=provider,
            custom_pricing=custom_pricing
        )

        print_cost_comparison(public_cost, custom_cost)


async def demo_monthly_cost_projection():
    """Demo 4: Monthly cost projection with custom pricing"""
    print_section("Demo 4: Monthly Cost Projection")

    print("📊 Acme Corp Monthly Usage Projection\n")

    # Simulated monthly usage across different agents
    usage_scenarios = [
        {
            "agent": "Customer Support Bot",
            "provider": "openai",
            "model": "gpt-4o",
            "executions": 50000,
            "avg_input_tokens": 800,
            "avg_output_tokens": 400
        },
        {
            "agent": "Document Analyzer",
            "provider": "anthropic",
            "model": "claude-4.5-sonnet",
            "executions": 10000,
            "avg_input_tokens": 4000,
            "avg_output_tokens": 1200
        },
        {
            "agent": "Code Review Assistant",
            "provider": "google",
            "model": "gemini-2.5-pro",
            "executions": 25000,
            "avg_input_tokens": 2500,
            "avg_output_tokens": 800
        }
    ]

    total_public_cost = 0.0
    total_custom_cost = 0.0

    print(f"{'Agent':<25} {'Model':<25} {'Executions':>12} {'Public Cost':>15} {'Custom Cost':>15} {'Savings':>12}")
    print(f"{'-'*105}")

    for scenario in usage_scenarios:
        # Calculate total tokens
        total_input = scenario["executions"] * scenario["avg_input_tokens"]
        total_output = scenario["executions"] * scenario["avg_output_tokens"]

        # Public cost
        public_cost = calculate_cost_estimate(
            input_tokens=total_input,
            output_tokens=total_output,
            model_name=scenario["model"],
            provider=scenario["provider"]
        )

        # Custom cost (20% discount)
        public_pricing = get_model_pricing(scenario["provider"], scenario["model"])
        custom_pricing = {
            "input_per_million": public_pricing["input_per_million"] * 0.8,
            "output_per_million": public_pricing["output_per_million"] * 0.8
        }

        custom_cost = calculate_cost_estimate(
            input_tokens=total_input,
            output_tokens=total_output,
            model_name=scenario["model"],
            provider=scenario["provider"],
            custom_pricing=custom_pricing
        )

        savings = public_cost.estimated_cost_usd - custom_cost.estimated_cost_usd
        total_public_cost += public_cost.estimated_cost_usd
        total_custom_cost += custom_cost.estimated_cost_usd

        model_display = f"{scenario['provider']}/{scenario['model']}"
        print(f"{scenario['agent']:<25} {model_display:<25} {scenario['executions']:>12,} "
              f"${public_cost.estimated_cost_usd:>14.2f} ${custom_cost.estimated_cost_usd:>14.2f} "
              f"${savings:>11.2f}")

    print(f"{'-'*105}")
    total_savings = total_public_cost - total_custom_cost
    savings_pct = (total_savings / total_public_cost * 100) if total_public_cost > 0 else 0

    print(f"{'TOTAL MONTHLY COST':<51} "
          f"${total_public_cost:>14.2f} ${total_custom_cost:>14.2f} "
          f"${total_savings:>11.2f}")
    print(f"\n💰 Monthly Savings: ${total_savings:,.2f} ({savings_pct:.1f}%)")
    print(f"📈 Annual Savings: ${total_savings * 12:,.2f}")


async def demo_list_org_pricing_configs(db):
    """Demo 5: List all pricing configurations for organization"""
    print_section("Demo 5: Organization Pricing Configuration Report")

    org_id = "acme-corp"

    # Query configurations
    stmt = select(OrganizationPricingConfig).where(
        OrganizationPricingConfig.organization_id == org_id,
        OrganizationPricingConfig.is_active == True
    ).order_by(OrganizationPricingConfig.provider, OrganizationPricingConfig.model_name)

    result = await db.execute(stmt)
    configs = result.scalars().all()

    print(f"Organization: {org_id}")
    print(f"Active Pricing Configurations: {len(configs)}\n")

    if not configs:
        print("⚠️  No custom pricing configurations found. Using public list pricing.")
        return

    print(f"{'Provider':<15} {'Model':<25} {'Input ($/M)':<15} {'Output ($/M)':<15} {'Valid Until':<15}")
    print(f"{'-'*90}")

    for config in configs:
        expiry = config.expiry_date.strftime("%Y-%m-%d") if config.expiry_date else "Indefinite"
        print(f"{config.provider:<15} {config.model_name:<25} "
              f"${float(config.input_cost_per_million):<14.2f} "
              f"${float(config.output_cost_per_million):<14.2f} "
              f"{expiry:<15}")

    print(f"\n✅ All configurations active and ready for use")
    print(f"\n💡 Tip: Cost estimates will automatically use these custom rates when available")


# =============================================================================
# MAIN DEMO
# =============================================================================

async def main():
    """Run all enterprise pricing demos"""
    print("\n" + "="*80)
    print("  ENTERPRISE LLM PRICING CONFIGURATION DEMO")
    print("  Demonstrating custom pricing rates for cost-conscious enterprises")
    print("="*80)

    # Initialize database session
    async with AsyncSessionLocal() as db:
        try:
            # Demo 1: View public pricing
            await demo_view_public_pricing()

            # Demo 2: Configure custom pricing
            await demo_configure_custom_pricing(db)

            # Demo 3: Cost estimation comparison
            await demo_cost_estimation_comparison()

            # Demo 4: Monthly cost projection
            await demo_monthly_cost_projection()

            # Demo 5: List configurations
            await demo_list_org_pricing_configs(db)

            # Summary
            print_section("DEMO COMPLETE")
            print("✅ Demonstrated:")
            print("   • Public list pricing for 8 LLM providers (40+ models)")
            print("   • Custom pricing configuration for enterprises")
            print("   • Cost estimation with public vs custom pricing")
            print("   • Monthly cost projections and savings analysis")
            print("   • Organization pricing configuration management")
            print("\n💡 Key Benefits:")
            print("   • Flexible token-based cost tracking")
            print("   • Support for negotiated enterprise rates")
            print("   • Accurate cost estimates with disclaimers")
            print("   • Multi-provider support (OpenAI, Anthropic, Google, Meta, etc.)")
            print("   • Easy configuration and management")
            print("\n" + "="*80)

        except Exception as e:
            print(f"\n❌ Error during demo: {e}")
            import traceback
            traceback.print_exc()
            await db.rollback()
        finally:
            await db.close()


if __name__ == "__main__":
    asyncio.run(main())
