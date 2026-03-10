"""
Pre-built Workflow Templates Catalog - P1 Feature #2

Production-ready workflow templates across different categories.
"""

from backend.shared.template_models import TemplateCategory, TemplateDifficulty


# Sales Templates
LEAD_QUALIFICATION_WORKFLOW = {
    "name": "Lead Qualification & Routing",
    "description": "Automatically qualify inbound leads, score them based on criteria, and route to the right sales rep. Integrates with your CRM to update lead status and assign ownership.",
    "category": TemplateCategory.SALES,
    "tags": ["crm", "lead-scoring", "automation", "salesforce", "hubspot"],
    "difficulty": TemplateDifficulty.BEGINNER,
    "icon": "🎯",
    "workflow_definition": {
        "nodes": [
            {"id": "trigger", "type": "webhook", "config": {"name": "New Lead"}},
            {"id": "enrich", "type": "task", "config": {"action": "enrich_lead_data"}},
            {"id": "score", "type": "task", "config": {"action": "calculate_lead_score"}},
            {"id": "qualify", "type": "conditional", "config": {"condition": "score >= 70"}},
            {"id": "assign", "type": "task", "config": {"action": "assign_to_sales_rep"}},
            {"id": "update_crm", "type": "integration", "config": {"integration": "salesforce", "action": "create_lead"}},
            {"id": "notify", "type": "integration", "config": {"integration": "slack", "action": "send_message"}},
        ],
        "edges": [
            {"from": "trigger", "to": "enrich"},
            {"from": "enrich", "to": "score"},
            {"from": "score", "to": "qualify"},
            {"from": "qualify", "to": "assign", "condition": "true"},
            {"from": "assign", "to": "update_crm"},
            {"from": "update_crm", "to": "notify"},
        ]
    },
    "parameters": {
        "min_score_threshold": {
            "name": "min_score_threshold",
            "type": "integer",
            "description": "Minimum score for qualified lead",
            "default": 70
        },
        "assignment_strategy": {
            "name": "assignment_strategy",
            "type": "select",
            "description": "Strategy for assigning leads to reps",
            "options": ["round_robin", "territory", "expertise"],
            "default": "round_robin"
        },
        "slack_channel": {
            "name": "slack_channel",
            "type": "string",
            "description": "Slack channel for notifications",
            "default": "#sales"
        },
    },
    "required_integrations": ["salesforce", "slack"],
    "use_cases": [
        "Qualify inbound leads from website forms",
        "Route high-value leads to senior reps",
        "Automate lead distribution across sales team"
    ],
    "documentation": """# Lead Qualification & Routing

This workflow automatically processes inbound leads, scores them based on your criteria, and routes them to the appropriate sales representative.

## How it Works

1. **Trigger**: Webhook receives new lead data
2. **Enrich**: Enriches lead with company data
3. **Score**: Calculates lead score based on criteria
4. **Qualify**: Routes based on score threshold
5. **Assign**: Assigns to sales rep using chosen strategy
6. **Update CRM**: Creates or updates lead in Salesforce
7. **Notify**: Sends Slack notification to assigned rep
"""
}

OPPORTUNITY_PIPELINE_TRACKING = {
    "name": "Opportunity Pipeline Tracker",
    "description": "Monitor deal progression, send alerts for stalled opportunities, and automate follow-ups. Tracks deal velocity and provides insights on pipeline health.",
    "category": TemplateCategory.SALES,
    "tags": ["pipeline", "deals", "crm", "automation"],
    "difficulty": TemplateDifficulty.INTERMEDIATE,
    "icon": "📊",
    "workflow_definition": {
        "nodes": [
            {"id": "schedule", "type": "schedule", "config": {"cron": "0 9 * * *"}},
            {"id": "fetch_opps", "type": "integration", "config": {"integration": "salesforce", "action": "query_records"}},
            {"id": "analyze", "type": "task", "config": {"action": "analyze_pipeline_health"}},
            {"id": "check_stalled", "type": "conditional", "config": {"condition": "days_in_stage > threshold"}},
            {"id": "notify_rep", "type": "integration", "config": {"integration": "slack", "action": "send_message"}},
        ],
        "edges": [
            {"from": "schedule", "to": "fetch_opps"},
            {"from": "fetch_opps", "to": "analyze"},
            {"from": "analyze", "to": "check_stalled"},
            {"from": "check_stalled", "to": "notify_rep", "condition": "true"},
        ]
    },
    "parameters": {
        "stalled_days_threshold": {
            "name": "stalled_days_threshold",
            "type": "integer",
            "description": "Days in stage before considered stalled",
            "default": 14
        },
        "check_frequency": {
            "name": "check_frequency",
            "type": "string",
            "description": "How often to check pipeline",
            "default": "daily"
        },
    },
    "required_integrations": ["salesforce", "slack"],
    "use_cases": ["Track deal velocity", "Prevent opportunities from stalling", "Pipeline health monitoring"]
}

EMAIL_CAMPAIGN_AUTOMATION = {
    "name": "Email Campaign Automation",
    "description": "Launch multi-step email campaigns with personalization, A/B testing, and automated follow-ups based on recipient engagement.",
    "category": TemplateCategory.MARKETING,
    "tags": ["email", "campaigns", "automation", "nurture"],
    "difficulty": TemplateDifficulty.BEGINNER,
    "icon": "📧",
    "workflow_definition": {
        "nodes": [
            {"id": "trigger", "type": "schedule", "config": {"cron": "0 10 * * 1"}},
            {"id": "fetch_audience", "type": "integration", "config": {"integration": "hubspot", "action": "list_contacts"}},
            {"id": "send_email", "type": "integration", "config": {"integration": "sendgrid", "action": "send_email"}},
        ],
        "edges": [
            {"from": "trigger", "to": "fetch_audience"},
            {"from": "fetch_audience", "to": "send_email"},
        ]
    },
    "parameters": {
        "followup_delay_days": {
            "name": "followup_delay_days",
            "type": "integer",
            "description": "Days to wait before sending follow-up",
            "default": 3
        },
        "max_followups": {
            "name": "max_followups",
            "type": "integer",
            "description": "Maximum number of follow-up emails",
            "default": 2
        },
    },
    "required_integrations": ["sendgrid", "hubspot"],
    "use_cases": ["Nurture campaign automation", "Re-engagement campaigns"]
}

# Create catalog
TEMPLATE_CATALOG = [
    LEAD_QUALIFICATION_WORKFLOW,
    OPPORTUNITY_PIPELINE_TRACKING,
    EMAIL_CAMPAIGN_AUTOMATION,
]
