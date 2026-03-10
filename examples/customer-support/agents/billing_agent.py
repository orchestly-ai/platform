"""
Billing Support Agent

Handles billing inquiries, payment issues, and subscription management.
Can process refunds, update payment methods, and explain charges.
"""

import asyncio
from datetime import datetime, timedelta
from agent_orchestrator import register_agent, task
from agent_orchestrator.llm import LLMClient


# Simulated billing database (in production, this would be Stripe/payment gateway)
CUSTOMER_BILLING_DATA = {
    "cust_001": {
        "customer_id": "cust_001",
        "plan": "Professional",
        "monthly_price": 99.00,
        "billing_cycle": "monthly",
        "next_billing_date": "2024-12-15",
        "payment_method": "Visa **** 4242",
        "payment_status": "active",
        "recent_invoices": [
            {"date": "2024-11-15", "amount": 99.00, "status": "paid"},
            {"date": "2024-10-15", "amount": 99.00, "status": "paid"},
            {"date": "2024-09-15", "amount": 99.00, "status": "paid"},
        ],
        "overage_charges": 0.00,
        "credit_balance": 0.00
    },
    "cust_002": {
        "customer_id": "cust_002",
        "plan": "Enterprise",
        "monthly_price": 499.00,
        "billing_cycle": "annual",
        "next_billing_date": "2025-03-01",
        "payment_method": "MasterCard **** 5555",
        "payment_status": "active",
        "recent_invoices": [
            {"date": "2024-03-01", "amount": 5988.00, "status": "paid"},
        ],
        "overage_charges": 150.00,
        "credit_balance": 50.00
    }
}


@register_agent(
    name="billing_support_agent",
    capabilities=["billing_support"],
    cost_limit_daily=50.0,
    llm_model="gpt-4o-mini",  # Billing is more structured, mini is sufficient
)
class BillingSupportAgent:
    """
    Billing support agent for handling payment and subscription inquiries.

    Capabilities:
    - Explain charges and invoices
    - Process refund requests
    - Update payment methods
    - Change subscription plans
    - Handle failed payments
    - Provide billing history
    """

    def __init__(self):
        self.llm = LLMClient(provider="openai", model="gpt-4o-mini")
        self.billing_db = CUSTOMER_BILLING_DATA

    @task(timeout=60)
    async def billing_support(self, ticket: dict) -> dict:
        """
        Handle billing support ticket.

        Args:
            ticket: Ticket data with subject, body, customer_id

        Returns:
            Resolution with billing information and actions taken
        """
        print(f"\n💳 Billing Support Agent processing ticket: {ticket['id']}")
        print(f"   Issue: {ticket['subject']}")

        # Extract customer ID from ticket metadata
        customer_id = ticket.get('metadata', {}).get('customer_id', 'cust_001')

        # Get customer billing data
        billing_data = self.billing_db.get(customer_id)

        if not billing_data:
            return {
                "status": "error",
                "message": "Customer not found",
                "escalation_needed": True
            }

        # Classify billing inquiry type
        inquiry_type = self._classify_inquiry(ticket)
        print(f"   Inquiry type: {inquiry_type}")

        # Handle based on type
        if inquiry_type == "explain_charge":
            return await self._explain_charge(ticket, billing_data)

        elif inquiry_type == "refund_request":
            return await self._handle_refund(ticket, billing_data)

        elif inquiry_type == "payment_failed":
            return await self._handle_payment_failure(ticket, billing_data)

        elif inquiry_type == "plan_change":
            return await self._handle_plan_change(ticket, billing_data)

        elif inquiry_type == "cancel_subscription":
            return await self._handle_cancellation(ticket, billing_data)

        elif inquiry_type == "billing_history":
            return self._provide_billing_history(billing_data)

        else:
            # General inquiry - use LLM
            return await self._handle_general_billing(ticket, billing_data)

    def _classify_inquiry(self, ticket: dict) -> str:
        """
        Classify the type of billing inquiry.

        Args:
            ticket: Ticket data

        Returns:
            Inquiry type
        """
        text = f"{ticket['subject']} {ticket['body']}".lower()

        if any(word in text for word in ['refund', 'charge back', 'money back', 'return']):
            return "refund_request"

        if any(word in text for word in ['failed', 'declined', 'payment error', 'card declined']):
            return "payment_failed"

        if any(word in text for word in ['upgrade', 'downgrade', 'change plan', 'switch plan']):
            return "plan_change"

        if any(word in text for word in ['cancel', 'close account', 'terminate', 'stop billing']):
            return "cancel_subscription"

        if any(word in text for word in ['invoice', 'history', 'past charges', 'previous']):
            return "billing_history"

        if any(word in text for word in ['why', 'what is', 'explain', 'charge for', 'billed']):
            return "explain_charge"

        return "general"

    async def _explain_charge(self, ticket: dict, billing_data: dict) -> dict:
        """Explain a charge to the customer."""

        # Use LLM to generate friendly explanation
        prompt = f"""
You are a helpful billing support agent. Explain this charge to the customer:

Customer's question: {ticket['body']}

Their billing info:
- Plan: {billing_data['plan']} (${billing_data['monthly_price']}/{billing_data['billing_cycle']})
- Last invoice: ${billing_data['recent_invoices'][0]['amount']} on {billing_data['recent_invoices'][0]['date']}
- Overage charges: ${billing_data['overage_charges']}
- Next billing: {billing_data['next_billing_date']}

Provide a clear, friendly explanation of their charges.
"""

        explanation = await self.llm.generate(prompt, temperature=0.3)

        return {
            "status": "resolved",
            "inquiry_type": "explain_charge",
            "explanation": explanation,
            "current_plan": billing_data['plan'],
            "next_billing_date": billing_data['next_billing_date'],
            "next_charge_amount": billing_data['monthly_price'] + billing_data['overage_charges'],
            "auto_resolved": True,
            "customer_communication": explanation
        }

    async def _handle_refund(self, ticket: dict, billing_data: dict) -> dict:
        """Handle refund request."""

        # Analyze refund eligibility
        last_invoice = billing_data['recent_invoices'][0]
        invoice_date = datetime.strptime(last_invoice['date'], "%Y-%m-%d")
        days_since = (datetime.now() - invoice_date).days

        # Refund policy: within 30 days
        eligible = days_since <= 30

        if eligible:
            # Use LLM to draft refund approval message
            prompt = f"""
Customer requested a refund for: {ticket['body']}

Their last charge was ${last_invoice['amount']} on {last_invoice['date']} ({days_since} days ago).
This is within our 30-day refund policy.

Draft a friendly message approving their refund and explaining:
1. Refund amount
2. Processing time (5-7 business days)
3. What happens to their account
"""

            message = await self.llm.generate(prompt, temperature=0.4)

            return {
                "status": "approved",
                "inquiry_type": "refund_request",
                "refund_amount": last_invoice['amount'],
                "processing_days": "5-7",
                "account_action": "downgrade_to_free",
                "auto_resolved": False,  # Requires manual processing
                "requires_approval": True,  # Manager approval needed
                "customer_communication": message
            }
        else:
            # Outside refund window
            prompt = f"""
Customer requested a refund for: {ticket['body']}

Their last charge was ${last_invoice['amount']} on {last_invoice['date']} ({days_since} days ago).
This is outside our 30-day refund policy.

Draft a polite message declining the refund but offering:
1. Prorated credit for next month
2. Option to cancel to avoid future charges
3. Willingness to discuss if there were service issues
"""

            message = await self.llm.generate(prompt, temperature=0.4)

            return {
                "status": "declined",
                "inquiry_type": "refund_request",
                "reason": "outside_refund_window",
                "days_since_charge": days_since,
                "alternative_offered": "prorated_credit",
                "customer_communication": message
            }

    async def _handle_payment_failure(self, ticket: dict, billing_data: dict) -> dict:
        """Handle failed payment."""

        # Generate resolution steps
        return {
            "status": "action_required",
            "inquiry_type": "payment_failed",
            "current_payment_method": billing_data['payment_method'],
            "amount_due": billing_data['monthly_price'],
            "retry_date": (datetime.now() + timedelta(days=3)).strftime("%Y-%m-%d"),
            "actions_required": [
                "Update payment method",
                "Verify card has sufficient funds",
                "Check card expiration date",
                "Contact bank if issue persists"
            ],
            "grace_period_days": 7,
            "customer_communication": f"""
We had trouble processing your payment of ${billing_data['monthly_price']} with {billing_data['payment_method']}.

To avoid service interruption:
1. Update your payment method in Account Settings
2. We'll retry in 3 days
3. You have a 7-day grace period

If you need help, we're here to assist!
"""
        }

    async def _handle_plan_change(self, ticket: dict, billing_data: dict) -> dict:
        """Handle plan change request."""

        # Use LLM to understand the desired change
        prompt = f"""
Customer wants to change their plan: {ticket['body']}

Current plan: {billing_data['plan']} (${billing_data['monthly_price']}/{billing_data['billing_cycle']})
Available plans:
- Starter: $29/month
- Professional: $99/month
- Enterprise: $499/month

What plan do they want? Return just the plan name.
"""

        desired_plan = await self.llm.generate(prompt, temperature=0.1)
        desired_plan = desired_plan.strip()

        # Plan prices
        plan_prices = {
            "Starter": 29.00,
            "Professional": 99.00,
            "Enterprise": 499.00
        }

        new_price = plan_prices.get(desired_plan, billing_data['monthly_price'])
        is_upgrade = new_price > billing_data['monthly_price']

        # Calculate prorated amount
        days_remaining = 15  # Simplified
        prorated_charge = (new_price - billing_data['monthly_price']) * (days_remaining / 30)

        return {
            "status": "ready_to_process",
            "inquiry_type": "plan_change",
            "current_plan": billing_data['plan'],
            "desired_plan": desired_plan,
            "is_upgrade": is_upgrade,
            "new_monthly_price": new_price,
            "prorated_charge": max(0, prorated_charge),
            "effective_date": "immediate",
            "customer_communication": f"""
Great! {'Upgrading' if is_upgrade else 'Downgrading'} your plan from {billing_data['plan']} to {desired_plan}.

New monthly price: ${new_price}
{'Prorated charge today: $' + str(round(prorated_charge, 2)) if is_upgrade else 'Credit applied: $' + str(abs(round(prorated_charge, 2)))}
Change takes effect: Immediately

Ready to proceed?
"""
        }

    async def _handle_cancellation(self, ticket: dict, billing_data: dict) -> dict:
        """Handle subscription cancellation."""

        # Calculate remaining value
        days_remaining = (
            datetime.strptime(billing_data['next_billing_date'], "%Y-%m-%d") - datetime.now()
        ).days

        # Use LLM to understand reason and offer retention
        prompt = f"""
Customer wants to cancel: {ticket['body']}

Their plan: {billing_data['plan']} (${billing_data['monthly_price']}/{billing_data['billing_cycle']})
Days until next bill: {days_remaining}

1. Understand their reason for canceling
2. Offer one retention option (discount, pause subscription, or downgrade)
3. If they still want to cancel, explain the process kindly

Be empathetic and helpful.
"""

        response = await self.llm.generate(prompt, temperature=0.5)

        return {
            "status": "retention_attempt",
            "inquiry_type": "cancel_subscription",
            "current_plan": billing_data['plan'],
            "days_until_next_bill": days_remaining,
            "access_until": billing_data['next_billing_date'],
            "retention_offer": "3 months at 50% off",
            "cancellation_process": [
                "Cancel anytime before " + billing_data['next_billing_date'],
                "Keep access until end of billing period",
                "Data retained for 90 days",
                "Can reactivate anytime"
            ],
            "customer_communication": response
        }

    def _provide_billing_history(self, billing_data: dict) -> dict:
        """Provide billing history."""

        # Format invoice history
        invoice_summary = "\n".join([
            f"- {inv['date']}: ${inv['amount']} ({inv['status']})"
            for inv in billing_data['recent_invoices']
        ])

        return {
            "status": "resolved",
            "inquiry_type": "billing_history",
            "current_plan": billing_data['plan'],
            "total_spent": sum(inv['amount'] for inv in billing_data['recent_invoices']),
            "invoices": billing_data['recent_invoices'],
            "credit_balance": billing_data['credit_balance'],
            "auto_resolved": True,
            "customer_communication": f"""
Here's your billing history:

Current Plan: {billing_data['plan']} (${billing_data['monthly_price']}/{billing_data['billing_cycle']})
Next Billing: {billing_data['next_billing_date']}
Payment Method: {billing_data['payment_method']}

Recent Invoices:
{invoice_summary}

Account Credit: ${billing_data['credit_balance']}

Need a detailed invoice? Let me know which date!
"""
        }

    async def _handle_general_billing(self, ticket: dict, billing_data: dict) -> dict:
        """Handle general billing inquiry with LLM."""

        prompt = f"""
Customer billing question: {ticket['body']}

Their account info:
- Plan: {billing_data['plan']} (${billing_data['monthly_price']}/{billing_data['billing_cycle']})
- Payment method: {billing_data['payment_method']}
- Next billing: {billing_data['next_billing_date']}
- Credit balance: ${billing_data['credit_balance']}

Provide a helpful answer to their question.
"""

        response = await self.llm.generate(prompt, temperature=0.4)

        return {
            "status": "resolved",
            "inquiry_type": "general",
            "auto_resolved": True,
            "customer_communication": response
        }


if __name__ == "__main__":
    # Test the agent
    agent = BillingSupportAgent()

    async def test():
        # Test case 1: Refund request
        ticket1 = {
            "id": "BILL-001",
            "subject": "Request refund for last charge",
            "body": "I was charged $99 last month but I barely used the service. Can I get a refund?",
            "metadata": {"customer_id": "cust_001"}
        }

        result1 = await agent.billing_support(ticket1)
        print("\n" + "="*60)
        print("TEST 1: Refund Request")
        print("="*60)
        print(f"Status: {result1['status']}")
        print(f"Refund Amount: ${result1.get('refund_amount', 0)}")
        print(f"\nCustomer Message:\n{result1['customer_communication']}")

        # Test case 2: Plan change
        ticket2 = {
            "id": "BILL-002",
            "subject": "Upgrade to Enterprise",
            "body": "My team is growing and I need to upgrade to Enterprise plan. How does that work?",
            "metadata": {"customer_id": "cust_001"}
        }

        result2 = await agent.billing_support(ticket2)
        print("\n" + "="*60)
        print("TEST 2: Plan Change")
        print("="*60)
        print(f"Current: {result2['current_plan']}")
        print(f"Desired: {result2['desired_plan']}")
        print(f"New Price: ${result2['new_monthly_price']}")
        print(f"\nCustomer Message:\n{result2['customer_communication']}")

    asyncio.run(test())
