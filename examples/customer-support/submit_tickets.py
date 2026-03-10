"""
Submit test support tickets to demonstrate the multi-agent workflow.
"""

import asyncio
import sys
from uuid import uuid4

sys.path.insert(0, "../../sdk/python")

# Test tickets covering different categories
TEST_TICKETS = [
    {
        "ticket_id": str(uuid4()),
        "subject": "Can't login to my account",
        "body": "I forgot my password and can't access my account. How do I reset it?",
        "from": "customer@example.com",
        "channel": "email"
    },
    {
        "ticket_id": str(uuid4()),
        "subject": "Error 500 when uploading files",
        "body": "Every time I try to upload a file larger than 10MB, I get an Error 500. This is blocking my work. Please help ASAP!",
        "from": "urgent@company.com",
        "channel": "chat"
    },
    {
        "ticket_id": str(uuid4()),
        "subject": "Double charged on my credit card",
        "body": "I was charged twice this month - once on the 1st and again on the 3rd. My card shows two transactions of $49.99. Please refund the duplicate charge.",
        "from": "billing@customer.com",
        "channel": "email"
    },
    {
        "ticket_id": str(uuid4()),
        "subject": "How to export my data?",
        "body": "I need to export all my project data to CSV format. Is there a bulk export feature? The UI only shows individual file downloads.",
        "from": "user@startup.com",
        "channel": "chat"
    },
    {
        "ticket_id": str(uuid4()),
        "subject": "Account not activated",
        "body": "I signed up 2 hours ago but haven't received the activation email. I checked spam folder too. Can you help?",
        "from": "newuser@email.com",
        "channel": "email"
    },
    {
        "ticket_id": str(uuid4()),
        "subject": "Feature request: Dark mode",
        "body": "Would love to see a dark mode option for the dashboard. I work late nights and the bright UI strains my eyes.",
        "from": "designer@agency.com",
        "channel": "chat"
    },
    {
        "ticket_id": str(uuid4()),
        "subject": "Want to cancel my subscription",
        "body": "I'm not using the service anymore and would like to cancel my subscription. How do I do that?",
        "from": "cancelme@domain.com",
        "channel": "email"
    },
]


async def submit_ticket(ticket: dict):
    """Submit a single ticket to the triage agent."""
    # In production, this would call the platform API
    # For now, we'll just print the ticket

    print(f"\n{'='*60}")
    print(f"📧 New Ticket: {ticket['ticket_id'][:8]}...")
    print(f"   Subject: {ticket['subject']}")
    print(f"   From: {ticket['from']}")
    print(f"   Channel: {ticket['channel']}")
    print(f"{'='*60}\n")

    # TODO: Actually submit via API when orchestrator is ready
    # await client.submit_task(
    #     capability="ticket_triage",
    #     input=ticket
    # )


async def main():
    """Submit all test tickets."""
    print("🎫 Submitting Test Support Tickets")
    print(f"Total tickets: {len(TEST_TICKETS)}\n")

    for i, ticket in enumerate(TEST_TICKETS, 1):
        print(f"[{i}/{len(TEST_TICKETS)}] Submitting ticket...")
        await submit_ticket(ticket)
        await asyncio.sleep(1)  # Stagger submissions

    print("\n✅ All tickets submitted!")
    print("\nExpected workflow:")
    print("  1. Triage Agent classifies each ticket")
    print("  2. Routes to FAQ, Technical, or Billing agent")
    print("  3. Specialist agent processes and resolves")
    print("  4. Check dashboard for real-time updates")
    print("\nMonitor progress at: http://localhost:3000")


if __name__ == "__main__":
    asyncio.run(main())
