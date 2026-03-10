"""
Seed Script: Customer Support Response Tone A/B Experiment

Creates an A/B experiment to test formal vs conversational response tones
for customer support responses.

Run:
    cd platform/agent-orchestration
    source backend/venv/bin/activate
    python -m backend.scripts.seed_cs_response_tone_experiment

This creates:
- Experiment: "cs-response-tone"
- Variant A (Control): Formal professional tone
- Variant B (Treatment): Friendly conversational tone
"""

import asyncio
import os
import sys

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from sqlalchemy import select

from backend.shared.ab_testing_models import ABExperiment, ABVariant
from backend.database.session import AsyncSessionLocal
from backend.shared.config import get_settings


# Prompt templates for each variant
FORMAL_PROMPT = """You are a professional customer support representative for an e-commerce company. Your communication style should be:

**Formal and Professional:**
- Use complete sentences with proper grammar
- Address the customer with "Dear" and formal salutations
- Use phrases like "I sincerely apologize", "Please be assured", "We appreciate your patience"
- Maintain a courteous, business-like tone throughout
- End with "Best regards" or "Sincerely"

**Guidelines:**
- Acknowledge the customer's concern
- Provide clear, structured information
- Offer specific solutions with timelines
- Close with an offer for further assistance

Context will include the customer's name, issue category, and their message. Generate a helpful, professional response."""

CONVERSATIONAL_PROMPT = """You are a friendly customer support agent for an e-commerce company. Your communication style should be:

**Warm and Conversational:**
- Use a friendly, approachable tone like talking to a friend
- Use contractions (we're, you'll, that's)
- Address the customer by first name
- Use phrases like "I totally get it", "No worries!", "I'm here to help"
- Show empathy with casual language
- End with something like "Let me know if you need anything else!"

**Guidelines:**
- Acknowledge how they're feeling
- Keep explanations simple and friendly
- Be enthusiastic about helping
- Use emojis sparingly if appropriate (e.g., one thumbs up)

Context will include the customer's name, issue category, and their message. Generate a helpful, friendly response."""


async def seed_experiment():
    """Create the response tone A/B experiment"""

    async with AsyncSessionLocal() as session:
        # Check if experiment already exists
        stmt = select(ABExperiment).where(ABExperiment.slug == "cs-response-tone")
        result = await session.execute(stmt)
        existing = result.scalar_one_or_none()

        if existing:
            print(f"Experiment 'cs-response-tone' already exists (ID: {existing.id})")
            print(f"Status: {existing.status}")

            # Show variants
            stmt = select(ABVariant).where(ABVariant.experiment_id == existing.id)
            result = await session.execute(stmt)
            variants = result.scalars().all()

            for v in variants:
                print(f"  - {v.name} ({v.variant_key}): {v.sample_count} samples, {v.success_rate:.1f}% conversion")

            return existing.id

        # Create experiment
        experiment = ABExperiment(
            name="Customer Support Response Tone Test",
            slug="cs-response-tone",
            description="Testing formal vs conversational tone in customer support responses to measure customer satisfaction.",
            task_type="cs-response-tone",  # Used by CS service to find this experiment
            organization_id=1,
            created_by_user_id="admin",
            traffic_split_strategy="user_hash",  # Consistent per user
            total_traffic_percentage=100.0,
            hypothesis="Conversational tone will increase customer satisfaction scores by 10-15% compared to formal tone",
            success_criteria={
                "primary_metric": "positive_feedback_rate",
                "target_improvement": 0.10,  # 10% improvement
            },
            minimum_sample_size=50,  # Per variant
            confidence_level=0.95,
            minimum_effect_size=0.05,
            winner_selection_criteria="highest_success_rate",
            auto_promote_winner=False,
            tags=["customer-support", "tone", "response-generation"],
            status="draft",
        )

        session.add(experiment)
        await session.flush()  # Get experiment ID

        print(f"Created experiment: {experiment.name} (ID: {experiment.id})")

        # Create Variant A: Formal (Control)
        variant_formal = ABVariant(
            experiment_id=experiment.id,
            name="Formal Professional",
            variant_key="formal",
            variant_type="control",
            description="Professional, formal communication style",
            config={
                "tone": "formal",
                "use_emojis": False,
                "greeting_style": "formal",  # "Dear Customer" style
            },
            traffic_percentage=50,
            prompt_template=FORMAL_PROMPT,
            model_name="llama-3.3-70b-versatile",  # Same model for fair comparison
            is_active=True,
        )
        session.add(variant_formal)

        # Create Variant B: Conversational (Treatment)
        variant_conversational = ABVariant(
            experiment_id=experiment.id,
            name="Friendly Conversational",
            variant_key="conversational",
            variant_type="treatment",
            description="Warm, friendly conversational style",
            config={
                "tone": "conversational",
                "use_emojis": True,
                "greeting_style": "casual",  # First name style
            },
            traffic_percentage=50,
            prompt_template=CONVERSATIONAL_PROMPT,
            model_name="llama-3.3-70b-versatile",  # Same model for fair comparison
            is_active=True,
        )
        session.add(variant_conversational)

        await session.commit()

        print(f"Created variants:")
        print(f"  - Formal Professional (control): 50% traffic")
        print(f"  - Friendly Conversational (treatment): 50% traffic")
        print()
        print("Experiment is in DRAFT status.")
        print("To start the experiment, use the dashboard or API:")
        print(f"  POST /api/v1/experiments/{experiment.id}/start")

        return experiment.id


if __name__ == "__main__":
    asyncio.run(seed_experiment())
