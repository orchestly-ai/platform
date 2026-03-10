"""
Triage Agent - First point of contact for all support tickets.

Classifies tickets and routes them to appropriate specialist agents.
"""

import asyncio
import sys
sys.path.insert(0, "../../../sdk/python")

from agent_orchestrator import register_agent, task, LLMClient


@register_agent(
    name="triage_agent",
    capabilities=["ticket_triage"],
    description="Classifies and routes incoming support tickets",
    cost_limit_daily=50.0,
    llm_provider="openai",
    llm_model="gpt-4o-mini",
    tags=["support", "routing"],
)
class TriageAgent:
    """Agent that triages incoming support tickets."""

    def __init__(self):
        self.llm = LLMClient(provider="openai", model="gpt-4o-mini")

    @task(timeout=20)
    async def ticket_triage(self, ticket: dict) -> dict:
        """
        Triage a support ticket.

        Input:
            {
                "ticket_id": str,
                "subject": str,
                "body": str,
                "from": str,
                "channel": str  # "email", "chat", "phone"
            }

        Output:
            {
                "ticket_id": str,
                "category": str,  # FAQ, Technical, Billing, Other
                "priority": str,  # Low, Normal, High, Critical
                "route_to": str,  # Next agent capability
                "summary": str,
                "key_points": list[str]
            }
        """
        subject = ticket.get("subject", "")
        body = ticket.get("body", "")

        # Use LLM to classify ticket
        prompt = f"""
Analyze this support ticket and provide a JSON response with:
1. category: FAQ, Technical, Billing, or Other
2. priority: Low, Normal, High, or Critical
3. summary: One sentence summary
4. key_points: List of 2-3 key points

Ticket Subject: {subject}
Ticket Body: {body}

Respond with ONLY valid JSON, no markdown formatting:
"""

        response = await self.llm.generate(
            prompt=prompt,
            temperature=0.3,
            max_tokens=300
        )

        # Parse LLM response
        import json
        try:
            classification = json.loads(response.strip())
        except json.JSONDecodeError:
            # Fallback if LLM doesn't return valid JSON
            classification = {
                "category": "Other",
                "priority": "Normal",
                "summary": subject,
                "key_points": [body[:100]]
            }

        # Determine routing based on category
        category = classification.get("category", "Other")
        route_mapping = {
            "FAQ": "faq_handling",
            "Technical": "technical_support",
            "Billing": "billing_support",
            "Other": "human_escalation"
        }

        return {
            "ticket_id": ticket["ticket_id"],
            "category": category,
            "priority": classification.get("priority", "Normal"),
            "route_to": route_mapping.get(category, "human_escalation"),
            "summary": classification.get("summary", subject),
            "key_points": classification.get("key_points", [])
        }


if __name__ == "__main__":
    print("🎯 Starting Triage Agent...")
    print("This agent classifies incoming support tickets\n")

    agent = TriageAgent()
    asyncio.run(agent.run_forever())
