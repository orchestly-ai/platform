"""
Pre-built Demo Workflows for Sandbox

Contains 5 impressive demo workflows that showcase AgentOrch capabilities:

1. Customer Support Triage - Classify and route support tickets
2. Sales Lead Qualification - Score and qualify sales leads
3. Content Generation Pipeline - Multi-model content generation
4. Multi-Agent Collaboration - Coordinated agent workflow
5. Time-Travel Debug Scenario - Debugging demonstration
"""

from dataclasses import dataclass, field
from typing import List, Dict, Any, Optional


@dataclass
class DemoWorkflow:
    """A pre-built demo workflow."""
    id: str
    name: str
    description: str
    category: str
    steps: List[Dict[str, Any]]
    estimated_cost: float = 0.01
    estimated_duration_ms: int = 2000
    sample_inputs: Dict[str, Any] = field(default_factory=dict)
    showcase_features: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "name": self.name,
            "description": self.description,
            "category": self.category,
            "steps": self.steps,
            "estimated_cost": self.estimated_cost,
            "estimated_duration_ms": self.estimated_duration_ms,
            "sample_inputs": self.sample_inputs,
            "showcase_features": self.showcase_features,
        }


# ============================================================================
# Demo Workflow 1: Customer Support Triage
# ============================================================================

CUSTOMER_SUPPORT_TRIAGE = DemoWorkflow(
    id="demo-customer-support-triage",
    name="Customer Support Triage",
    description="Automatically classify support tickets by priority and category, then route to appropriate channels",
    category="Customer Support",
    estimated_cost=0.008,
    estimated_duration_ms=1500,
    sample_inputs={
        "ticket": "I've been overcharged $500 on my last invoice and I need this fixed immediately! I've been a customer for 5 years and this is unacceptable.",
        "customer_id": "CUST-12345",
        "channel": "#support-urgent",
    },
    showcase_features=["LLM Classification", "Cost Tracking", "Integration Routing"],
    steps=[
        {
            "name": "classify_ticket",
            "type": "llm",
            "model": "gpt-4",
            "provider": "openai",
            "system_prompt": "You are a support ticket classifier. Analyze tickets and determine priority (high/medium/low), category, and sentiment.",
            "prompt": "Classify this support ticket:\n\n{ticket}\n\nProvide priority, category, sentiment, and recommended actions.",
            "scenario": "classify_ticket",
            "variant": "high_priority",
        },
        {
            "name": "check_priority",
            "type": "conditional",
            "condition": "classify_ticket.priority == 'high'",
            "true_path": ["escalate_to_manager", "notify_slack"],
            "false_path": ["add_to_queue"],
        },
        {
            "name": "notify_slack",
            "type": "integration",
            "connector": "slack",
            "action": "send_message",
            "params": {
                "channel": "{channel}",
                "message": "🚨 High priority ticket from {customer_id}: {ticket[:100]}...",
            },
        },
        {
            "name": "create_zendesk_ticket",
            "type": "integration",
            "connector": "zendesk",
            "action": "create_ticket",
            "params": {
                "subject": "Support Request - {customer_id}",
                "priority": "high",
                "description": "{ticket}",
            },
        },
        {
            "name": "generate_response",
            "type": "llm",
            "model": "gpt-4",
            "provider": "openai",
            "system_prompt": "You are a helpful customer support agent. Generate empathetic and professional responses.",
            "prompt": "Based on this classification:\n{classify_ticket}\n\nGenerate a response for this ticket:\n{ticket}",
        },
    ],
)


# ============================================================================
# Demo Workflow 2: Sales Lead Qualification
# ============================================================================

SALES_LEAD_QUALIFICATION = DemoWorkflow(
    id="demo-sales-lead-qualification",
    name="Sales Lead Qualification",
    description="Automatically score and qualify inbound sales leads with enrichment and CRM integration",
    category="Sales",
    estimated_cost=0.012,
    estimated_duration_ms=2000,
    sample_inputs={
        "lead_email": "cto@enterprise-corp.com",
        "lead_name": "Sarah Johnson",
        "company": "Enterprise Corp",
        "message": "We're evaluating AI orchestration platforms for our 500-person engineering team. Would love to learn more about enterprise pricing.",
    },
    showcase_features=["Lead Scoring", "Data Enrichment", "CRM Integration", "Multi-step Workflows"],
    steps=[
        {
            "name": "enrich_company",
            "type": "integration",
            "connector": "database",
            "action": "query",
            "params": {
                "query": "SELECT * FROM company_data WHERE domain = '{lead_email.split('@')[1]}'",
            },
        },
        {
            "name": "score_lead",
            "type": "llm",
            "model": "gpt-4",
            "provider": "openai",
            "system_prompt": "You are a lead scoring expert. Analyze lead information and provide a qualification score with reasoning.",
            "prompt": """Score this sales lead:

Name: {lead_name}
Email: {lead_email}
Company: {company}
Message: {message}

Company enrichment data: {enrich_company}

Provide:
1. Lead score (0-100)
2. Qualification status (Hot/Warm/Cold)
3. Key buying signals
4. Recommended next steps
5. Estimated deal size""",
            "scenario": "lead_qualification",
            "variant": "hot_lead",
        },
        {
            "name": "create_salesforce_lead",
            "type": "integration",
            "connector": "salesforce",
            "action": "create_lead",
            "params": {
                "FirstName": "{lead_name.split()[0]}",
                "LastName": "{lead_name.split()[-1]}",
                "Email": "{lead_email}",
                "Company": "{company}",
                "LeadSource": "Website",
                "Status": "New",
            },
        },
        {
            "name": "check_hot_lead",
            "type": "conditional",
            "condition": "score_lead.score >= 80",
            "description": "Route hot leads immediately",
        },
        {
            "name": "notify_sales_team",
            "type": "integration",
            "connector": "slack",
            "action": "send_message",
            "params": {
                "channel": "#sales-hot-leads",
                "message": "🔥 Hot lead: {lead_name} from {company}\nScore: {score_lead.score}\n{score_lead.summary}",
            },
        },
        {
            "name": "send_email",
            "type": "integration",
            "connector": "email",
            "action": "send_template",
            "params": {
                "template_id": "enterprise_welcome",
                "to": "{lead_email}",
                "variables": {
                    "name": "{lead_name}",
                    "company": "{company}",
                },
            },
        },
    ],
)


# ============================================================================
# Demo Workflow 3: Content Generation Pipeline
# ============================================================================

CONTENT_GENERATION_PIPELINE = DemoWorkflow(
    id="demo-content-generation",
    name="Content Generation Pipeline",
    description="Generate content using multiple LLM providers with cost comparison and quality optimization",
    category="Content",
    estimated_cost=0.025,
    estimated_duration_ms=3000,
    sample_inputs={
        "topic": "The Future of AI Agent Orchestration",
        "content_type": "blog_post",
        "target_audience": "Enterprise CTOs and Engineering Leaders",
        "word_count": 800,
    },
    showcase_features=["Multi-Provider Routing", "Cost Comparison", "Provider Failover", "Quality Optimization"],
    steps=[
        {
            "name": "generate_outline",
            "type": "llm",
            "model": "gpt-3.5-turbo",
            "provider": "openai",
            "system_prompt": "You are a content strategist. Create detailed outlines for technical blog posts.",
            "prompt": """Create an outline for a {content_type} about:

Topic: {topic}
Target Audience: {target_audience}
Word Count Target: {word_count}

Include:
- Main thesis
- 4-5 key sections
- Key points for each section
- Call to action""",
        },
        {
            "name": "generate_draft_gpt4",
            "type": "llm",
            "model": "gpt-4",
            "provider": "openai",
            "system_prompt": "You are an expert technical writer specializing in enterprise software.",
            "prompt": "Write a {content_type} based on this outline:\n\n{generate_outline}\n\nTopic: {topic}\nTarget: {target_audience}",
            "scenario": "content_generation",
            "variant": "blog_post",
        },
        {
            "name": "generate_draft_claude",
            "type": "llm",
            "model": "claude-3-sonnet",
            "provider": "anthropic",
            "system_prompt": "You are an expert technical writer specializing in enterprise software.",
            "prompt": "Write a {content_type} based on this outline:\n\n{generate_outline}\n\nTopic: {topic}\nTarget: {target_audience}",
            "scenario": "content_generation",
            "variant": "blog_post",
        },
        {
            "name": "compare_and_select",
            "type": "llm",
            "model": "gpt-4",
            "provider": "openai",
            "system_prompt": "You are an editor. Compare two drafts and select the best one with improvements.",
            "prompt": """Compare these two drafts and create the best final version:

Draft 1 (GPT-4):
{generate_draft_gpt4}

Draft 2 (Claude):
{generate_draft_claude}

Select the best elements and create the final polished version.""",
        },
        {
            "name": "save_to_notion",
            "type": "integration",
            "connector": "notion",
            "action": "create_page",
            "params": {
                "database_id": "content-calendar",
                "title": "{topic}",
                "content": "{compare_and_select}",
                "status": "Draft",
            },
        },
    ],
)


# ============================================================================
# Demo Workflow 4: Multi-Agent Collaboration
# ============================================================================

MULTI_AGENT_COLLABORATION = DemoWorkflow(
    id="demo-multi-agent-collaboration",
    name="Multi-Agent Collaboration",
    description="Demonstrate coordinated multi-agent workflow with researcher, analyst, and writer agents",
    category="Advanced",
    estimated_cost=0.035,
    estimated_duration_ms=4000,
    sample_inputs={
        "research_topic": "Competitive landscape of AI orchestration platforms in 2025",
        "output_format": "executive_briefing",
    },
    showcase_features=["Multi-Agent Coordination", "Agent Handoffs", "Parallel Processing", "State Management"],
    steps=[
        {
            "name": "researcher_agent",
            "type": "llm",
            "model": "gpt-4",
            "provider": "openai",
            "system_prompt": """You are a Research Agent. Your job is to:
- Gather comprehensive information on topics
- Identify key players and trends
- Collect data points and statistics
- Cite sources where possible""",
            "prompt": """Research the following topic comprehensively:

Topic: {research_topic}

Provide:
1. Overview of the space
2. Key players and their offerings
3. Market trends
4. Technology evolution
5. Data points and statistics""",
        },
        {
            "name": "analyst_agent",
            "type": "llm",
            "model": "gpt-4",
            "provider": "openai",
            "system_prompt": """You are an Analysis Agent. Your job is to:
- Synthesize research into insights
- Identify patterns and opportunities
- Make strategic recommendations
- Quantify business impact""",
            "prompt": """Analyze this research and provide strategic insights:

Research:
{researcher_agent}

Provide:
1. Key insights and patterns
2. Market opportunities
3. Competitive positioning recommendations
4. Risk assessment
5. Strategic recommendations""",
        },
        {
            "name": "writer_agent",
            "type": "llm",
            "model": "claude-3-sonnet",
            "provider": "anthropic",
            "system_prompt": """You are a Writer Agent. Your job is to:
- Transform analysis into compelling narratives
- Create executive-ready documents
- Ensure clarity and impact
- Adapt tone for target audience""",
            "prompt": """Create an {output_format} from this analysis:

Research:
{researcher_agent}

Analysis:
{analyst_agent}

Format as an executive briefing with:
- Executive Summary (3 bullets)
- Key Findings
- Strategic Recommendations
- Next Steps""",
        },
        {
            "name": "reviewer_agent",
            "type": "llm",
            "model": "gpt-4",
            "provider": "openai",
            "system_prompt": "You are a Quality Reviewer. Check for accuracy, clarity, and completeness.",
            "prompt": """Review this executive briefing for quality:

{writer_agent}

Check for:
1. Factual accuracy
2. Logical flow
3. Actionable recommendations
4. Executive readiness

Provide the final polished version with any corrections.""",
        },
        {
            "name": "distribute_results",
            "type": "integration",
            "connector": "slack",
            "action": "send_message",
            "params": {
                "channel": "#research-outputs",
                "message": "📊 New Research Complete: {research_topic}\n\n{reviewer_agent[:500]}...",
            },
        },
    ],
)


# ============================================================================
# Demo Workflow 5: Time-Travel Debug Scenario
# ============================================================================

TIME_TRAVEL_DEBUG_SCENARIO = DemoWorkflow(
    id="demo-time-travel-debug",
    name="Time-Travel Debug Scenario",
    description="Demonstrate time-travel debugging by showing a workflow that fails midway and how to debug it",
    category="Debugging",
    estimated_cost=0.015,
    estimated_duration_ms=2500,
    sample_inputs={
        "user_query": "Calculate the ROI for switching to AgentOrch",
        "context": "Enterprise customer with 50 agents, $10k/month current LLM spend",
    },
    showcase_features=["Time-Travel Debugging", "State Inspection", "Replay Capability", "Error Recovery"],
    steps=[
        {
            "name": "parse_query",
            "type": "llm",
            "model": "gpt-3.5-turbo",
            "provider": "openai",
            "system_prompt": "Parse user queries and extract key parameters.",
            "prompt": "Parse this query and extract parameters:\n\n{user_query}\n\nContext: {context}",
        },
        {
            "name": "fetch_pricing_data",
            "type": "integration",
            "connector": "database",
            "action": "query",
            "params": {
                "query": "SELECT * FROM pricing_tiers WHERE tier = 'enterprise'",
            },
        },
        {
            "name": "calculate_current_costs",
            "type": "llm",
            "model": "gpt-4",
            "provider": "openai",
            "system_prompt": "You are a financial analyst. Calculate costs accurately.",
            "prompt": """Calculate current monthly costs:

Query parsed: {parse_query}
Context: {context}

Provide breakdown of current spend.""",
        },
        {
            "name": "simulate_failure",
            "type": "llm",
            "model": "gpt-4",
            "provider": "openai",
            "system_prompt": "Calculate projected costs with AgentOrch.",
            "prompt": """Based on:
- Current costs: {calculate_current_costs}
- Pricing data: {fetch_pricing_data}

Calculate projected AgentOrch costs and ROI.

Note: This step demonstrates a calculation point where errors might occur.
In the demo, users can time-travel back to inspect the state at this step.""",
        },
        {
            "name": "generate_roi_report",
            "type": "llm",
            "model": "gpt-4",
            "provider": "openai",
            "system_prompt": "Generate clear, compelling ROI reports.",
            "prompt": """Create an ROI report:

Current State: {calculate_current_costs}
Projected State: {simulate_failure}

Include:
- Monthly savings
- Annual savings
- Break-even timeline
- Additional benefits""",
        },
        {
            "name": "send_report",
            "type": "integration",
            "connector": "email",
            "action": "send",
            "params": {
                "to": "prospect@example.com",
                "subject": "Your AgentOrch ROI Analysis",
                "body": "{generate_roi_report}",
            },
        },
    ],
)


# ============================================================================
# Export All Workflows
# ============================================================================

_DEMO_WORKFLOWS = [
    CUSTOMER_SUPPORT_TRIAGE,
    SALES_LEAD_QUALIFICATION,
    CONTENT_GENERATION_PIPELINE,
    MULTI_AGENT_COLLABORATION,
    TIME_TRAVEL_DEBUG_SCENARIO,
]


def get_demo_workflows() -> List[DemoWorkflow]:
    """Get all demo workflows."""
    return _DEMO_WORKFLOWS


def get_demo_workflow(workflow_id: str) -> Optional[DemoWorkflow]:
    """Get a specific demo workflow by ID."""
    for w in _DEMO_WORKFLOWS:
        if w.id == workflow_id:
            return w
    return None


__all__ = [
    "DemoWorkflow",
    "get_demo_workflows",
    "get_demo_workflow",
    "CUSTOMER_SUPPORT_TRIAGE",
    "SALES_LEAD_QUALIFICATION",
    "CONTENT_GENERATION_PIPELINE",
    "MULTI_AGENT_COLLABORATION",
    "TIME_TRAVEL_DEBUG_SCENARIO",
]
