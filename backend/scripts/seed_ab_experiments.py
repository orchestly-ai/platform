#!/usr/bin/env python3
"""
Seed A/B Testing Experiments with Realistic Data

Creates two experiments via the API and populates them with simulated results
so the dashboard shows meaningful data:

Experiment 1: "Ticket Summarization: GPT-4o vs Claude Sonnet"
  - Control (GPT-4o): 50% traffic, ~88% success, ~1200ms latency, ~$0.012/call
  - Treatment (Claude Sonnet): 50% traffic, ~92% success, ~900ms latency, ~$0.008/call
  => Claude Sonnet wins on all metrics

Experiment 2: "Customer Tone: Formal vs Friendly prompt"
  - Control (Formal prompt): 50% traffic, ~78% success, ~800ms latency
  - Treatment (Friendly prompt): 50% traffic, ~84% success, ~820ms latency
  => Friendly prompt has higher success (customer satisfaction)

Usage:
    python backend/scripts/seed_ab_experiments.py
"""

import asyncio
import random
import sys
import os
import math

# Add project root to path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../..")))

import httpx

BASE_URL = "http://localhost:8000"

# ============================================================================
# Experiment 1: Model comparison (GPT-4o vs Claude Sonnet)
# ============================================================================
EXPERIMENT_1 = {
    "name": "Ticket Summarization: GPT-4o vs Claude Sonnet",
    "slug": "ticket-summarization-model-compare",
    "description": (
        "Compare GPT-4o and Claude 3.5 Sonnet for support ticket summarization. "
        "Hypothesis: Claude Sonnet produces more accurate summaries at lower cost."
    ),
    "task_type": "ticket_summarization",
    "traffic_split_strategy": "random",
    "total_traffic_percentage": 100.0,
    "hypothesis": "Claude 3.5 Sonnet will achieve higher summary accuracy at lower per-call cost than GPT-4o",
    "success_criteria": {"target_success_rate": 90, "max_avg_latency_ms": 2000},
    "minimum_sample_size": 30,
    "confidence_level": 0.95,
    "minimum_effect_size": 0.05,
    "winner_selection_criteria": "composite_score",
    "auto_promote_winner": False,
    "tags": ["model-comparison", "summarization", "customer-support"],
    "variants": [
        {
            "name": "GPT-4o (Control)",
            "variant_key": "gpt4o_control",
            "variant_type": "control",
            "description": "OpenAI GPT-4o for ticket summarization",
            "config": {"temperature": 0.3, "max_tokens": 500},
            "traffic_percentage": 50.0,
            "model_name": "openai/gpt-4o",
            "prompt_template": None,
        },
        {
            "name": "Claude Sonnet (Treatment)",
            "variant_key": "claude_sonnet_treatment",
            "variant_type": "treatment",
            "description": "Anthropic Claude 3.5 Sonnet for ticket summarization",
            "config": {"temperature": 0.3, "max_tokens": 500},
            "traffic_percentage": 50.0,
            "model_name": "anthropic/claude-3-5-sonnet-20241022",
            "prompt_template": None,
        },
    ],
}

# Simulated metrics for experiment 1
EXP1_VARIANT_STATS = {
    "gpt4o_control": {
        "success_rate": 0.88,
        "latency_mean": 1200,
        "latency_stddev": 300,
        "cost_mean": 0.012,
        "cost_stddev": 0.003,
    },
    "claude_sonnet_treatment": {
        "success_rate": 0.92,
        "latency_mean": 900,
        "latency_stddev": 200,
        "cost_mean": 0.008,
        "cost_stddev": 0.002,
    },
}

# ============================================================================
# Experiment 2: Prompt comparison (Formal vs Friendly tone)
# ============================================================================
EXPERIMENT_2 = {
    "name": "Customer Response Tone: Formal vs Friendly",
    "slug": "customer-tone-formal-vs-friendly",
    "description": (
        "Test whether a friendly, conversational tone in AI-generated customer "
        "responses leads to higher customer satisfaction vs formal tone."
    ),
    "task_type": "customer_response",
    "traffic_split_strategy": "random",
    "total_traffic_percentage": 100.0,
    "hypothesis": "Friendly tone will increase customer satisfaction (measured by positive feedback) by 5%+",
    "success_criteria": {"target_success_rate": 80, "metric": "customer_satisfaction"},
    "minimum_sample_size": 30,
    "confidence_level": 0.95,
    "minimum_effect_size": 0.05,
    "winner_selection_criteria": "highest_success_rate",
    "auto_promote_winner": False,
    "tags": ["prompt-comparison", "tone", "customer-support"],
    "variants": [
        {
            "name": "Formal Tone (Control)",
            "variant_key": "formal_control",
            "variant_type": "control",
            "description": "Professional, formal language for customer responses",
            "config": {"temperature": 0.5},
            "traffic_percentage": 50.0,
            "model_name": None,
            "prompt_template": (
                "You are a professional customer support agent. Respond to the customer's "
                "issue in a formal, business-appropriate tone. Be precise and solution-oriented. "
                "Use proper salutations and sign-offs."
            ),
        },
        {
            "name": "Friendly Tone (Treatment)",
            "variant_key": "friendly_treatment",
            "variant_type": "treatment",
            "description": "Warm, conversational language for customer responses",
            "config": {"temperature": 0.7},
            "traffic_percentage": 50.0,
            "model_name": None,
            "prompt_template": (
                "You are a helpful, friendly customer support agent. Respond to the customer's "
                "issue in a warm, conversational tone. Use their first name, show empathy, "
                "and make them feel heard. Keep it natural and approachable."
            ),
        },
    ],
}

EXP2_VARIANT_STATS = {
    "formal_control": {
        "success_rate": 0.78,
        "latency_mean": 800,
        "latency_stddev": 150,
        "cost_mean": 0.006,
        "cost_stddev": 0.001,
    },
    "friendly_treatment": {
        "success_rate": 0.84,
        "latency_mean": 820,
        "latency_stddev": 160,
        "cost_mean": 0.007,
        "cost_stddev": 0.001,
    },
}


async def create_experiment(client: httpx.AsyncClient, experiment_data: dict) -> dict:
    """Create an experiment via API."""
    print(f"\n  Creating experiment: {experiment_data['name']}")
    resp = await client.post(f"{BASE_URL}/api/v1/experiments", json=experiment_data)
    if resp.status_code == 201:
        data = resp.json()
        print(f"  Created experiment id={data['id']}")
        return data
    elif resp.status_code == 400 and "unique" in resp.text.lower():
        # Experiment with this slug already exists, find it
        print(f"  Experiment already exists, fetching...")
        resp2 = await client.get(f"{BASE_URL}/api/v1/experiments")
        experiments = resp2.json()
        for exp in experiments:
            if exp["slug"] == experiment_data["slug"]:
                print(f"  Found existing experiment id={exp['id']}")
                return exp
        raise RuntimeError(f"Could not find experiment with slug {experiment_data['slug']}")
    else:
        raise RuntimeError(f"Failed to create experiment: {resp.status_code} {resp.text}")


async def start_experiment(client: httpx.AsyncClient, experiment_id: int) -> dict:
    """Start an experiment."""
    resp = await client.post(f"{BASE_URL}/api/v1/experiments/{experiment_id}/start")
    if resp.status_code == 200:
        data = resp.json()
        print(f"  Started experiment id={experiment_id}, status={data.get('status')}")
        return data
    elif resp.status_code == 400:
        # Already running or completed
        print(f"  Experiment {experiment_id} already started: {resp.json().get('detail', '')}")
        resp2 = await client.get(f"{BASE_URL}/api/v1/experiments/{experiment_id}")
        return resp2.json()
    else:
        raise RuntimeError(f"Failed to start experiment: {resp.status_code} {resp.text}")


async def simulate_assignments(
    client: httpx.AsyncClient,
    experiment_id: int,
    variant_stats: dict,
    num_samples: int = 50,
):
    """
    Simulate variant assignments and completions.

    For each sample:
    1. Assign a variant via the API
    2. Record a completion with simulated metrics
    """
    print(f"  Simulating {num_samples} assignments for experiment {experiment_id}...")

    success_count = 0
    fail_count = 0

    for i in range(num_samples):
        # Rate limit protection: small delay between requests
        await asyncio.sleep(0.15)

        # Assign variant (with retry on 429)
        user_id = f"sim_user_{experiment_id}_{i:04d}"
        for attempt in range(3):
            resp = await client.post(
                f"{BASE_URL}/api/v1/experiments/{experiment_id}/assign",
                json={"user_id": user_id, "session_id": f"sim_session_{experiment_id}_{i:04d}"},
            )
            if resp.status_code == 429:
                await asyncio.sleep(2.0 * (attempt + 1))
                continue
            break

        if resp.status_code != 200:
            print(f"    Assignment {i} failed: {resp.status_code}")
            continue

        assignment = resp.json()
        assignment_id = assignment["id"]
        variant_key = assignment["variant_key"]

        # Get variant stats
        stats = variant_stats.get(variant_key, {})
        if not stats:
            print(f"    No stats for variant_key={variant_key}, skipping")
            continue

        # Simulate outcome
        success = random.random() < stats["success_rate"]
        latency_ms = max(100, random.gauss(stats["latency_mean"], stats["latency_stddev"]))
        cost = max(0.001, random.gauss(stats["cost_mean"], stats["cost_stddev"]))

        error_msg = None if success else "Simulated: incomplete or irrelevant summary"

        await asyncio.sleep(0.1)

        # Record completion (with retry on 429)
        for attempt in range(3):
            resp2 = await client.post(
                f"{BASE_URL}/api/v1/experiments/assignments/{assignment_id}/complete",
                json={
                    "assignment_id": assignment_id,
                    "success": success,
                    "latency_ms": round(latency_ms, 1),
                    "cost": round(cost, 6),
                    "error_message": error_msg,
                    "custom_metrics": {},
                },
            )
            if resp2.status_code == 429:
                await asyncio.sleep(2.0 * (attempt + 1))
                continue
            break

        if resp2.status_code == 200:
            if success:
                success_count += 1
            else:
                fail_count += 1
        else:
            print(f"    Completion {i} failed: {resp2.status_code}")

        # Print progress every 10
        if (i + 1) % 10 == 0:
            print(f"    Progress: {i + 1}/{num_samples}")

    print(f"  Done: {success_count} successes, {fail_count} failures")


async def main():
    print("=" * 60)
    print("A/B Testing Seed Script")
    print("=" * 60)
    print(f"Target: {BASE_URL}")

    # Check server is running
    async with httpx.AsyncClient(timeout=10) as client:
        try:
            resp = await client.get(f"{BASE_URL}/health")
            print(f"Server health: {resp.status_code}")
        except Exception as e:
            print(f"ERROR: Cannot reach server at {BASE_URL}: {e}")
            print("Make sure the orchestration backend is running on port 8000")
            sys.exit(1)

        # ---- Experiment 1: Model comparison ----
        print("\n" + "=" * 60)
        print("Experiment 1: Ticket Summarization Model Comparison")
        print("=" * 60)

        exp1 = await create_experiment(client, EXPERIMENT_1)
        exp1_id = exp1["id"]

        exp1 = await start_experiment(client, exp1_id)

        await simulate_assignments(client, exp1_id, EXP1_VARIANT_STATS, num_samples=50)

        # ---- Experiment 2: Prompt comparison ----
        print("\n" + "=" * 60)
        print("Experiment 2: Customer Response Tone Comparison")
        print("=" * 60)

        exp2 = await create_experiment(client, EXPERIMENT_2)
        exp2_id = exp2["id"]

        exp2 = await start_experiment(client, exp2_id)

        await simulate_assignments(client, exp2_id, EXP2_VARIANT_STATS, num_samples=50)

        # ---- Show final stats ----
        print("\n" + "=" * 60)
        print("Final Results")
        print("=" * 60)

        await asyncio.sleep(1.0)  # Wait for rate limit window to reset

        for exp_id, exp_name in [(exp1_id, "Model Comparison"), (exp2_id, "Tone Comparison")]:
            resp = await client.get(f"{BASE_URL}/api/v1/experiments/{exp_id}")
            if resp.status_code != 200:
                print(f"\n  {exp_name} (id={exp_id}): failed to fetch ({resp.status_code})")
                continue
            exp = resp.json()

            print(f"\n  {exp_name} (id={exp_id}):")
            print(f"    Status: {exp.get('status', 'unknown')}")
            print(f"    Total Samples: {exp.get('total_samples', 0)}")
            print(f"    Significant: {exp.get('is_statistically_significant', False)}")
            print(f"    P-value: {exp.get('p_value', 'N/A')}")

            for v in exp.get("variants", []):
                print(
                    f"    Variant '{v['name']}': "
                    f"samples={v.get('sample_count', 0)}, "
                    f"success={v.get('success_rate', 0):.1f}%, "
                    f"avg_latency={v.get('avg_latency_ms', 0):.0f}ms, "
                    f"avg_cost=${v.get('avg_cost', 0):.4f}"
                )

        # Try to analyze
        for exp_id in [exp1_id, exp2_id]:
            try:
                resp = await client.get(f"{BASE_URL}/api/v1/experiments/{exp_id}/analyze")
                if resp.status_code == 200:
                    analysis = resp.json()
                    print(f"\n  Analysis for experiment {exp_id}:")
                    print(f"    Significant: {analysis.get('is_statistically_significant')}")
                    print(f"    P-value: {analysis.get('p_value')}")
                    print(f"    Recommendation: {analysis.get('recommendation')}")
                    for insight in analysis.get("insights", []):
                        print(f"    - {insight}")
            except Exception as e:
                print(f"  Analysis failed for {exp_id}: {e}")

    print("\n" + "=" * 60)
    print("Seed complete! Open http://localhost:3000 and go to A/B Testing.")
    print("=" * 60)


if __name__ == "__main__":
    asyncio.run(main())
