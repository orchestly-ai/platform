#!/usr/bin/env python3
"""
End-to-End Customer Support Demo

Demonstrates the complete ticket workflow through the agent orchestration platform:
1. Submit tickets (mix of FAQ, Technical, Billing)
2. Triage classifies each ticket
3. Route to appropriate specialist agent
4. Collect metrics and results
5. Display comprehensive summary

This shows the full power of the platform with real multi-agent coordination.
"""

import asyncio
import json
from datetime import datetime
from typing import List, Dict
import sys
import os

# Add parent directory to path for imports
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '../../..'))

from examples.customer_support.agents.triage_agent import TriageAgent
from examples.customer_support.agents.faq_agent import FAQAgent
from examples.customer_support.agents.technical_agent import TechnicalSupportAgent
from examples.customer_support.agents.billing_agent import BillingSupportAgent


# Demo ticket set (realistic mix)
DEMO_TICKETS = [
    {
        "id": "TICKET-001",
        "subject": "How do I reset my password?",
        "body": "I forgot my password and need to reset it. Can you help?",
        "priority": "normal",
        "customer_email": "user1@example.com",
        "metadata": {"customer_id": "cust_001"}
    },
    {
        "id": "TICKET-002",
        "subject": "Application is very slow",
        "body": "The app has been really slow for the past 2 days. Pages take forever to load and sometimes freeze completely.",
        "priority": "high",
        "customer_email": "user2@example.com",
        "metadata": {"customer_id": "cust_002"}
    },
    {
        "id": "TICKET-003",
        "subject": "Request refund for last charge",
        "body": "I was charged $99 last week but I haven't been using the service. Can I get a refund?",
        "priority": "normal",
        "customer_email": "user3@example.com",
        "metadata": {"customer_id": "cust_001"}
    },
    {
        "id": "TICKET-004",
        "subject": "Cannot login to my account",
        "body": "I keep getting 'authentication error' when trying to login. I've tried 5 times with the correct password.",
        "priority": "high",
        "customer_email": "user4@example.com",
        "metadata": {"customer_id": "cust_002"}
    },
    {
        "id": "TICKET-005",
        "subject": "How do I export my data?",
        "body": "I need to export all my data to CSV. Where is that option?",
        "priority": "low",
        "customer_email": "user5@example.com",
        "metadata": {"customer_id": "cust_001"}
    },
    {
        "id": "TICKET-006",
        "subject": "Upgrade to Enterprise plan",
        "body": "My team is growing and I need to upgrade to Enterprise. What's the pricing and how do I upgrade?",
        "priority": "normal",
        "customer_email": "user6@example.com",
        "metadata": {"customer_id": "cust_002"}
    },
    {
        "id": "TICKET-007",
        "subject": "API integration not working",
        "body": "Getting 401 errors when calling the API. My API key should be valid. Getting error: 'Invalid authentication token'",
        "priority": "high",
        "customer_email": "developer@company.com",
        "metadata": {"customer_id": "cust_001"}
    },
    {
        "id": "TICKET-008",
        "subject": "What's your mobile app support?",
        "body": "Do you have iOS and Android apps? I can't find them in the app stores.",
        "priority": "low",
        "customer_email": "user8@example.com",
        "metadata": {"customer_id": "cust_002"}
    },
]


class DemoOrchestrator:
    """
    Orchestrates the complete demo workflow.

    In production, this logic would be in the platform's orchestrator service.
    For the demo, we're simulating the full workflow locally.
    """

    def __init__(self):
        self.triage_agent = TriageAgent()
        self.faq_agent = FAQAgent()
        self.technical_agent = TechnicalSupportAgent()
        self.billing_agent = BillingSupportAgent()

        # Metrics
        self.metrics = {
            "total_tickets": 0,
            "auto_resolved": 0,
            "routed_to_specialist": 0,
            "by_category": {},
            "by_priority": {},
            "total_cost": 0.0,
            "avg_resolution_time": 0.0,
            "results": []
        }

    async def process_ticket(self, ticket: Dict) -> Dict:
        """
        Process a single ticket through the complete workflow.

        Args:
            ticket: Ticket data

        Returns:
            Processing result with routing and resolution
        """
        start_time = datetime.now()

        print(f"\n{'='*80}")
        print(f"Processing: {ticket['id']} - {ticket['subject']}")
        print(f"{'='*80}")

        # Step 1: Triage
        print("\n[1/3] 🎯 Triage Agent - Classifying ticket...")
        triage_result = await self.triage_agent.ticket_triage(ticket)

        category = triage_result["category"]
        route_to = triage_result["route_to"]

        print(f"      Category: {category}")
        print(f"      Route to: {route_to}")
        print(f"      Urgency: {triage_result['urgency']}")

        # Step 2: Route to appropriate agent
        specialist_result = None
        auto_resolved = False

        if route_to == "faq_handling":
            print("\n[2/3] 💡 FAQ Agent - Attempting auto-resolution...")
            specialist_result = await self.faq_agent.faq_handling(ticket)
            auto_resolved = specialist_result.get("auto_resolved", False)

            if auto_resolved:
                print(f"      ✅ Auto-resolved!")
                print(f"      Resolution: {specialist_result['resolution'][:100]}...")
            else:
                print(f"      ⚠️  Could not auto-resolve, needs human review")

        elif route_to == "technical_support":
            print("\n[2/3] 🔧 Technical Support Agent - Investigating...")
            specialist_result = await self.technical_agent.technical_support(ticket)

            issue_type = specialist_result.get('issue_type', 'unknown')
            print(f"      Issue type: {issue_type}")
            print(f"      Severity: {specialist_result.get('severity', 'N/A')}")
            print(f"      Est. time: {specialist_result.get('estimated_resolution_time', 'N/A')}")

        elif route_to == "billing_support":
            print("\n[2/3] 💳 Billing Agent - Processing...")
            specialist_result = await self.billing_agent.billing_support(ticket)

            inquiry_type = specialist_result.get('inquiry_type', 'unknown')
            print(f"      Inquiry type: {inquiry_type}")
            print(f"      Status: {specialist_result.get('status', 'N/A')}")

        # Step 3: Final result
        end_time = datetime.now()
        duration = (end_time - start_time).total_seconds()

        print(f"\n[3/3] 📊 Result Summary")
        print(f"      Duration: {duration:.2f}s")
        print(f"      Auto-resolved: {'Yes' if auto_resolved else 'No'}")

        # Estimate cost (simplified - based on agent type and LLM calls)
        estimated_cost = self._estimate_cost(route_to, auto_resolved)
        print(f"      Estimated cost: ${estimated_cost:.4f}")

        return {
            "ticket_id": ticket["id"],
            "subject": ticket["subject"],
            "category": category,
            "route_to": route_to,
            "auto_resolved": auto_resolved,
            "triage_result": triage_result,
            "specialist_result": specialist_result,
            "duration_seconds": duration,
            "estimated_cost": estimated_cost,
            "timestamp": start_time.isoformat()
        }

    def _estimate_cost(self, route_to: str, auto_resolved: bool) -> float:
        """Estimate cost based on agent and resolution path."""
        # Base costs (rough estimates)
        costs = {
            "faq_handling": 0.001 if auto_resolved else 0.01,  # Keyword match vs LLM
            "technical_support": 0.05,  # GPT-4 for diagnostics
            "billing_support": 0.02,  # GPT-4-mini
        }
        return costs.get(route_to, 0.01)

    async def run_demo(self, tickets: List[Dict]):
        """
        Run complete demo with all tickets.

        Args:
            tickets: List of tickets to process
        """
        print("\n" + "="*80)
        print(" 🤖 AGENT ORCHESTRATION PLATFORM - CUSTOMER SUPPORT DEMO")
        print("="*80)
        print(f"\nProcessing {len(tickets)} tickets through multi-agent workflow...\n")

        results = []

        # Process each ticket
        for ticket in tickets:
            result = await self.process_ticket(ticket)
            results.append(result)

            # Update metrics
            self.metrics["total_tickets"] += 1
            if result["auto_resolved"]:
                self.metrics["auto_resolved"] += 1
            else:
                self.metrics["routed_to_specialist"] += 1

            category = result["category"]
            self.metrics["by_category"][category] = self.metrics["by_category"].get(category, 0) + 1

            self.metrics["total_cost"] += result["estimated_cost"]

            # Small delay between tickets
            await asyncio.sleep(0.5)

        # Calculate final metrics
        self.metrics["results"] = results
        self.metrics["avg_resolution_time"] = sum(r["duration_seconds"] for r in results) / len(results)
        self.metrics["auto_resolution_rate"] = (self.metrics["auto_resolved"] / self.metrics["total_tickets"]) * 100

        # Display summary
        self._display_summary()

    def _display_summary(self):
        """Display comprehensive demo summary."""
        print("\n\n" + "="*80)
        print(" 📊 DEMO SUMMARY - METRICS & RESULTS")
        print("="*80)

        print(f"\n📈 Overall Metrics:")
        print(f"   Total Tickets Processed: {self.metrics['total_tickets']}")
        print(f"   Auto-Resolved (FAQ): {self.metrics['auto_resolved']} ({self.metrics['auto_resolution_rate']:.1f}%)")
        print(f"   Routed to Specialists: {self.metrics['routed_to_specialist']}")
        print(f"   Average Resolution Time: {self.metrics['avg_resolution_time']:.2f}s")
        print(f"   Total Estimated Cost: ${self.metrics['total_cost']:.4f}")

        print(f"\n📋 By Category:")
        for category, count in sorted(self.metrics['by_category'].items()):
            percentage = (count / self.metrics['total_tickets']) * 100
            print(f"   {category}: {count} ({percentage:.1f}%)")

        print(f"\n🎯 Routing Breakdown:")
        routing_stats = {}
        for result in self.metrics['results']:
            route = result['route_to']
            routing_stats[route] = routing_stats.get(route, 0) + 1

        for route, count in sorted(routing_stats.items()):
            percentage = (count / self.metrics['total_tickets']) * 100
            print(f"   {route}: {count} ({percentage:.1f}%)")

        print(f"\n💰 Cost Analysis:")
        print(f"   Cost per ticket: ${self.metrics['total_cost'] / self.metrics['total_tickets']:.4f}")
        print(f"   Estimated monthly cost (1000 tickets): ${(self.metrics['total_cost'] / self.metrics['total_tickets']) * 1000:.2f}")

        print(f"\n⚡ Performance Impact:")
        time_saved_hours = (self.metrics['auto_resolved'] * 0.25)  # 15 min per ticket
        print(f"   Agent hours saved (auto-resolution): {time_saved_hours:.1f} hours")
        print(f"   Equivalent cost savings (@$50/hr): ${time_saved_hours * 50:.2f}")

        # ROI calculation
        platform_cost = self.metrics['total_cost']
        agent_savings = time_saved_hours * 50
        roi = ((agent_savings - platform_cost) / platform_cost) * 100 if platform_cost > 0 else 0

        print(f"\n💎 Return on Investment:")
        print(f"   Platform cost: ${platform_cost:.2f}")
        print(f"   Agent savings: ${agent_savings:.2f}")
        print(f"   Net savings: ${agent_savings - platform_cost:.2f}")
        print(f"   ROI: {roi:.0f}%")

        print("\n" + "="*80)
        print(" ✅ DEMO COMPLETE")
        print("="*80)
        print("\nKey Takeaways:")
        print(f"  • {self.metrics['auto_resolution_rate']:.0f}% of tickets auto-resolved (no human needed)")
        print(f"  • Average response time: {self.metrics['avg_resolution_time']:.1f} seconds")
        print(f"  • Cost: ${self.metrics['total_cost']:.4f} for {self.metrics['total_tickets']} tickets")
        print(f"  • ROI: {roi:.0f}% (platform saves {roi/100:.1f}x its cost in agent time)")
        print("\nThis is the power of intelligent agent orchestration! 🚀")
        print("="*80 + "\n")

    def export_results(self, filename: str = "demo_results.json"):
        """Export results to JSON file."""
        with open(filename, 'w') as f:
            json.dump(self.metrics, f, indent=2, default=str)
        print(f"\n📄 Results exported to: {filename}")


async def main():
    """Run the demo."""
    orchestrator = DemoOrchestrator()

    # Run demo with all tickets
    await orchestrator.run_demo(DEMO_TICKETS)

    # Export results
    orchestrator.export_results()


if __name__ == "__main__":
    # Run the demo
    asyncio.run(main())
