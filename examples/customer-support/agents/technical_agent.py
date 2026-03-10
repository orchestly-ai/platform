"""
Technical Support Agent

Handles technical issues that require investigation and troubleshooting.
Uses knowledge base and diagnostic tools to resolve technical problems.
"""

import asyncio
from agent_orchestrator import register_agent, task
from agent_orchestrator.llm import LLMClient


# Technical knowledge base with common issues and solutions
TECHNICAL_KB = {
    "login_error": {
        "symptoms": ["cannot login", "login failed", "authentication error", "credentials rejected"],
        "diagnostic_steps": [
            "Check if account is active",
            "Verify email/username is correct",
            "Check for CAPS LOCK on password",
            "Clear browser cache and cookies",
            "Try password reset"
        ],
        "common_causes": [
            "Expired password",
            "Account locked after failed attempts",
            "Browser cookie issues",
            "VPN interference"
        ],
        "resolution_time": "15-30 minutes"
    },
    "performance_issue": {
        "symptoms": ["slow", "laggy", "freezing", "performance", "loading"],
        "diagnostic_steps": [
            "Check browser version (Chrome 90+, Firefox 88+, Safari 14+)",
            "Measure page load time",
            "Check network latency",
            "Verify no large data operations in progress",
            "Test with browser extensions disabled"
        ],
        "common_causes": [
            "Outdated browser",
            "Poor network connection",
            "Large dataset in view",
            "Browser extensions conflict"
        ],
        "resolution_time": "20-45 minutes"
    },
    "api_integration": {
        "symptoms": ["api error", "integration", "webhook", "connection failed", "timeout"],
        "diagnostic_steps": [
            "Verify API key is valid and not expired",
            "Check API endpoint URL is correct",
            "Validate request payload format",
            "Check rate limiting status",
            "Review API logs for error codes"
        ],
        "common_causes": [
            "Invalid or expired API key",
            "Incorrect endpoint URL",
            "Malformed request payload",
            "Rate limit exceeded",
            "IP not whitelisted"
        ],
        "resolution_time": "30-60 minutes"
    },
    "data_sync": {
        "symptoms": ["sync", "data missing", "not updating", "stale data", "refresh"],
        "diagnostic_steps": [
            "Check last successful sync timestamp",
            "Verify sync service is running",
            "Check for data conflicts",
            "Review sync error logs",
            "Force manual sync"
        ],
        "common_causes": [
            "Sync service paused or failed",
            "Data conflicts preventing merge",
            "Network interruption during sync",
            "Exceeding data quota"
        ],
        "resolution_time": "20-40 minutes"
    },
    "export_import": {
        "symptoms": ["export", "import", "csv", "download failed", "upload error"],
        "diagnostic_steps": [
            "Check file size limits (max 50MB)",
            "Verify file format is supported",
            "Check for special characters in data",
            "Ensure required columns present",
            "Test with smaller dataset"
        ],
        "common_causes": [
            "File size exceeds limit",
            "Unsupported file format",
            "Invalid characters in data",
            "Missing required fields",
            "Timeout on large files"
        ],
        "resolution_time": "15-30 minutes"
    }
}


@register_agent(
    name="technical_support_agent",
    capabilities=["technical_support"],
    cost_limit_daily=75.0,  # Higher limit for technical investigations
    llm_model="gpt-4o",  # Use GPT-4 for complex troubleshooting
)
class TechnicalSupportAgent:
    """
    Technical support agent for investigating and resolving technical issues.

    Workflow:
    1. Analyze issue description
    2. Match to known issues in knowledge base
    3. Execute diagnostic steps
    4. Generate resolution plan
    5. Provide detailed technical guidance
    """

    def __init__(self):
        self.llm = LLMClient(provider="openai", model="gpt-4o")
        self.kb = TECHNICAL_KB

    @task(timeout=120)  # Technical issues may take longer
    async def technical_support(self, ticket: dict) -> dict:
        """
        Handle technical support ticket.

        Args:
            ticket: Ticket data with subject, body, priority, metadata

        Returns:
            Resolution plan with diagnostic steps and guidance
        """
        print(f"\n🔧 Technical Support Agent processing ticket: {ticket['id']}")
        print(f"   Issue: {ticket['subject']}")

        # Step 1: Match to known technical issue
        issue_type = self._match_issue_type(ticket)

        if issue_type:
            print(f"   Matched issue type: {issue_type}")

            # Get knowledge base entry
            kb_entry = self.kb[issue_type]

            # Step 2: Use LLM to customize diagnostic plan
            diagnostic_plan = await self._generate_diagnostic_plan(
                ticket,
                kb_entry
            )

            # Step 3: Estimate resolution
            estimated_time = kb_entry["resolution_time"]

            return {
                "status": "in_progress",
                "issue_type": issue_type,
                "diagnostic_plan": diagnostic_plan,
                "estimated_resolution_time": estimated_time,
                "severity": self._assess_severity(ticket),
                "escalation_needed": False,
                "next_steps": [
                    f"Execute diagnostic step {i+1}: {step}"
                    for i, step in enumerate(diagnostic_plan["steps"][:3])
                ],
                "customer_communication": diagnostic_plan["customer_message"]
            }

        else:
            # Unknown issue - use LLM to analyze
            print("   Unknown issue, using LLM analysis...")

            analysis = await self._analyze_unknown_issue(ticket)

            return {
                "status": "investigating",
                "issue_type": "unknown",
                "llm_analysis": analysis["analysis"],
                "recommended_steps": analysis["steps"],
                "escalation_needed": analysis["should_escalate"],
                "estimated_resolution_time": "1-2 hours",
                "severity": "medium",
                "customer_communication": analysis["customer_message"]
            }

    def _match_issue_type(self, ticket: dict) -> str:
        """
        Match ticket to known issue type based on symptoms.

        Args:
            ticket: Ticket data

        Returns:
            Issue type key or None
        """
        text = f"{ticket['subject']} {ticket['body']}".lower()

        # Score each issue type
        scores = {}
        for issue_type, data in self.kb.items():
            score = sum(
                1 for symptom in data["symptoms"]
                if symptom in text
            )
            if score > 0:
                scores[issue_type] = score

        # Return highest scoring match
        if scores:
            return max(scores.items(), key=lambda x: x[1])[0]

        return None

    async def _generate_diagnostic_plan(
        self,
        ticket: dict,
        kb_entry: dict
    ) -> dict:
        """
        Generate customized diagnostic plan using LLM.

        Args:
            ticket: Ticket data
            kb_entry: Knowledge base entry

        Returns:
            Diagnostic plan with steps and customer message
        """
        prompt = f"""
You are a technical support expert. A customer reported this issue:

Subject: {ticket['subject']}
Description: {ticket['body']}
Priority: {ticket.get('priority', 'normal')}

This matches our known issue type with these diagnostic steps:
{chr(10).join(f"- {step}" for step in kb_entry['diagnostic_steps'])}

Common causes:
{chr(10).join(f"- {cause}" for cause in kb_entry['common_causes'])}

Generate:
1. A customized diagnostic plan (5-7 specific steps for THIS customer's situation)
2. A friendly message to send the customer explaining what we're doing

Return as JSON:
{{
    "steps": ["step 1", "step 2", ...],
    "customer_message": "friendly explanation of our investigation plan"
}}
"""

        response = await self.llm.generate(prompt, temperature=0.4)

        # Parse LLM response
        import json
        try:
            return json.loads(response)
        except json.JSONDecodeError:
            # Fallback if LLM doesn't return valid JSON
            return {
                "steps": kb_entry["diagnostic_steps"],
                "customer_message": f"We've identified your issue and are investigating. Estimated time: {kb_entry['resolution_time']}."
            }

    async def _analyze_unknown_issue(self, ticket: dict) -> dict:
        """
        Analyze unknown issue using LLM.

        Args:
            ticket: Ticket data

        Returns:
            Analysis with recommended steps
        """
        prompt = f"""
You are a senior technical support engineer. Analyze this customer issue:

Subject: {ticket['subject']}
Description: {ticket['body']}
Priority: {ticket.get('priority', 'normal')}

This doesn't match any known issue. Analyze and provide:
1. Your analysis of the likely problem
2. 5-7 diagnostic steps to investigate
3. Whether this should be escalated to engineering
4. A message to send the customer

Return as JSON:
{{
    "analysis": "your technical analysis",
    "steps": ["step 1", "step 2", ...],
    "should_escalate": true/false,
    "customer_message": "friendly message explaining our plan"
}}
"""

        response = await self.llm.generate(prompt, temperature=0.5)

        # Parse LLM response
        import json
        try:
            return json.loads(response)
        except json.JSONDecodeError:
            # Fallback
            return {
                "analysis": "Complex technical issue requiring investigation",
                "steps": [
                    "Gather system logs",
                    "Reproduce issue in test environment",
                    "Check recent system changes",
                    "Consult engineering team"
                ],
                "should_escalate": True,
                "customer_message": "We're investigating this technical issue and will update you within 2 hours."
            }

    def _assess_severity(self, ticket: dict) -> str:
        """
        Assess issue severity.

        Args:
            ticket: Ticket data

        Returns:
            Severity level (low, medium, high, critical)
        """
        text = f"{ticket['subject']} {ticket['body']}".lower()

        # Critical keywords
        if any(word in text for word in ['down', 'outage', 'critical', 'production', 'urgent', 'emergency']):
            return "critical"

        # High severity keywords
        if any(word in text for word in ['error', 'failed', 'broken', 'cannot', 'unable']):
            return "high"

        # Medium severity (default for technical issues)
        if any(word in text for word in ['slow', 'issue', 'problem', 'bug']):
            return "medium"

        return "low"


if __name__ == "__main__":
    # Test the agent
    agent = TechnicalSupportAgent()

    async def test():
        # Test case 1: Known issue (login)
        ticket1 = {
            "id": "TECH-001",
            "subject": "Cannot login to my account",
            "body": "I keep getting 'authentication error' when I try to login. I've tried 3 times.",
            "priority": "high"
        }

        result1 = await agent.technical_support(ticket1)
        print("\n" + "="*60)
        print("TEST 1: Login Issue")
        print("="*60)
        print(f"Status: {result1['status']}")
        print(f"Issue Type: {result1.get('issue_type')}")
        print(f"Severity: {result1.get('severity')}")
        print(f"Resolution Time: {result1.get('estimated_resolution_time')}")
        print(f"\nDiagnostic Plan:")
        for i, step in enumerate(result1.get('diagnostic_plan', {}).get('steps', []), 1):
            print(f"  {i}. {step}")
        print(f"\nCustomer Message: {result1.get('customer_communication')}")

        # Test case 2: Unknown complex issue
        ticket2 = {
            "id": "TECH-002",
            "subject": "Weird behavior with nested filters",
            "body": "When I apply a filter, then apply another filter on top, the results don't make sense. Sometimes it works, sometimes it doesn't. Only happens on Tuesdays.",
            "priority": "normal"
        }

        result2 = await agent.technical_support(ticket2)
        print("\n" + "="*60)
        print("TEST 2: Unknown Issue")
        print("="*60)
        print(f"Status: {result2['status']}")
        print(f"Escalation Needed: {result2.get('escalation_needed')}")
        print(f"\nLLM Analysis: {result2.get('llm_analysis')}")
        print(f"\nRecommended Steps:")
        for i, step in enumerate(result2.get('recommended_steps', []), 1):
            print(f"  {i}. {step}")

    asyncio.run(test())
