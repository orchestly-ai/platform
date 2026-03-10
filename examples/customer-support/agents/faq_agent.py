"""
FAQ Agent - Handles frequently asked questions.

Auto-resolves common support questions with instant responses.
"""

import asyncio
import sys
sys.path.insert(0, "../../../sdk/python")

from agent_orchestrator import register_agent, task, LLMClient


# Common FAQ database
FAQ_DATABASE = {
    "password_reset": {
        "keywords": ["password", "forgot", "reset", "login", "can't sign in"],
        "response": """
To reset your password:

1. Go to https://example.com/forgot-password
2. Enter your email address
3. Check your email for a reset link (arrives within 5 minutes)
4. Click the link and create a new password
5. Password must be at least 8 characters with one number and one symbol

If you don't receive the email, check your spam folder or contact us for assistance.
"""
    },
    "account_activation": {
        "keywords": ["activate", "verification", "confirm email", "not activated"],
        "response": """
To activate your account:

1. Check your email for our welcome message
2. Click the "Activate Account" button in the email
3. Your account will be immediately activated

Didn't receive the email?
- Check your spam/junk folder
- Request a new activation email at https://example.com/resend-activation
- Allow up to 10 minutes for delivery

Still having issues? Reply to this ticket and we'll help you directly.
"""
    },
    "billing_cycle": {
        "keywords": ["billing date", "when charged", "next payment", "billing cycle"],
        "response": """
Your billing cycle information:

- Billing occurs on the same day each month (based on your signup date)
- You'll receive an invoice email 3 days before charging
- Payment is processed via the card on file
- You can view upcoming charges in Settings > Billing

To change your billing date or payment method, visit your account settings or reply to this ticket.
"""
    },
    "feature_request": {
        "keywords": ["feature", "add", "new functionality", "can you", "would like"],
        "response": """
Thank you for your feature suggestion!

We track all feature requests and consider them for future updates. Here's what happens next:

1. Your request is logged in our product roadmap
2. Our product team reviews it during quarterly planning
3. Popular requests are prioritized for development
4. You'll be notified if/when the feature is released

In the meantime, you can:
- Vote for similar requests in our community forum
- See our public roadmap at https://example.com/roadmap
- Check if a workaround exists in our knowledge base

Thank you for helping us improve!
"""
    },
    "cancel_subscription": {
        "keywords": ["cancel", "unsubscribe", "stop billing", "end subscription"],
        "response": """
We're sorry to see you go! Here's how to cancel your subscription:

**To cancel immediately:**
1. Go to Settings > Subscription
2. Click "Cancel Subscription"
3. Confirm cancellation
4. You'll retain access until the end of your current billing period

**What happens after:**
- No further charges will be made
- Your data is retained for 30 days (in case you change your mind)
- You can export your data before cancellation
- Reactivation is instant if you return

**Before you cancel:** Would you like to discuss any issues? We may be able to help or offer alternatives.

Reply to this ticket if you'd like to talk about it first.
"""
    },
}


@register_agent(
    name="faq_agent",
    capabilities=["faq_handling"],
    description="Handles frequently asked questions with instant responses",
    cost_limit_daily=30.0,
    llm_provider="openai",
    llm_model="gpt-4o-mini",
    tags=["support", "faq", "self-service"],
)
class FAQAgent:
    """Agent that handles FAQ-type support tickets."""

    def __init__(self):
        self.llm = LLMClient(provider="openai", model="gpt-4o-mini")
        self.faq_db = FAQ_DATABASE

    @task(timeout=15)
    async def faq_handling(self, ticket: dict) -> dict:
        """
        Handle FAQ tickets with instant responses.

        Input:
            {
                "ticket_id": str,
                "subject": str,
                "body": str,
                "summary": str,
                "key_points": list[str]
            }

        Output:
            {
                "ticket_id": str,
                "resolution": str,
                "matched_faq": str | null,
                "confidence": float,
                "status": "resolved" | "escalate",
                "auto_resolved": bool
            }
        """
        subject = ticket.get("subject", "").lower()
        body = ticket.get("body", "").lower()
        combined_text = f"{subject} {body}"

        # Match against FAQ database
        best_match = None
        best_match_score = 0

        for faq_key, faq_data in self.faq_db.items():
            # Simple keyword matching
            matched_keywords = sum(
                1 for keyword in faq_data["keywords"]
                if keyword.lower() in combined_text
            )

            if matched_keywords > best_match_score:
                best_match_score = matched_keywords
                best_match = faq_key

        # If we have a good match, use the canned response
        if best_match and best_match_score >= 2:
            response = self.faq_db[best_match]["response"]
            confidence = min(0.95, 0.6 + (best_match_score * 0.1))

            return {
                "ticket_id": ticket["ticket_id"],
                "resolution": response.strip(),
                "matched_faq": best_match,
                "confidence": confidence,
                "status": "resolved",
                "auto_resolved": True
            }

        # If no good match, use LLM to generate response
        else:
            # Check if it's FAQ-like using LLM
            prompt = f"""
You are a customer support agent. Analyze if this is a common question you can answer:

Subject: {ticket.get('subject', '')}
Question: {ticket.get('body', '')}

If you can provide a helpful answer, respond with "YES: [your answer]"
If this needs specialist help, respond with "NO: [reason]"

Keep responses concise (2-3 paragraphs max).
"""

            llm_response = await self.llm.generate(
                prompt=prompt,
                temperature=0.5,
                max_tokens=400
            )

            if llm_response.startswith("YES:"):
                answer = llm_response[4:].strip()
                return {
                    "ticket_id": ticket["ticket_id"],
                    "resolution": answer,
                    "matched_faq": None,
                    "confidence": 0.7,
                    "status": "resolved",
                    "auto_resolved": True
                }
            else:
                # Escalate to human
                return {
                    "ticket_id": ticket["ticket_id"],
                    "resolution": None,
                    "matched_faq": None,
                    "confidence": 0.3,
                    "status": "escalate",
                    "auto_resolved": False,
                    "escalation_reason": llm_response[3:].strip() if llm_response.startswith("NO:") else "Unable to provide automated response"
                }


if __name__ == "__main__":
    print("💬 Starting FAQ Agent...")
    print("This agent handles common support questions\n")
    print(f"FAQ Database: {len(FAQ_DATABASE)} topics loaded")
    print()

    agent = FAQAgent()
    asyncio.run(agent.run_forever())
