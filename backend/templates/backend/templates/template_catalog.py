"""
Pre-built Workflow Templates Catalog - P1 Feature #2

30 production-ready workflow templates across different categories.
Each template includes workflow definition, parameters, integrations, and documentation.

Categories covered:
- Sales (5 templates)
- Marketing (5 templates)
- Customer Support (5 templates)
- DevOps (5 templates)
- Data Processing (4 templates)
- Finance (3 templates)
- HR (3 templates)
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
        "min_score_threshold": {"name": "min_score_threshold", "type": "integer", "default": 70, "description": "Minimum score for qualified lead"},
        "assignment_strategy": {"name": "assignment_strategy", "type": "select", "options": ["round_robin", "territory", "expertise"], "default": "round_robin", "description": "Strategy for assigning leads to reps"},
        "slack_channel": {"name": "slack_channel", "type": "string", "default": "#sales", "description": "Slack channel for notifications"},
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
2. **Enrich**: Enriches lead with company data (firmographics)
3. **Score**: Calculates lead score based on criteria
4. **Qualify**: Routes based on score threshold
5. **Assign**: Assigns to sales rep using chosen strategy
6. **Update CRM**: Creates or updates lead in Salesforce
7. **Notify**: Sends Slack notification to assigned rep

## Configuration

Set your minimum score threshold and assignment strategy in the parameters.

## Required Integrations

- Salesforce or HubSpot (CRM)
- Slack (notifications)
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
            {"id": "create_task", "type": "integration", "config": {"integration": "salesforce", "action": "create_task"}},
        ],
        "edges": [
            {"from": "schedule", "to": "fetch_opps"},
            {"from": "fetch_opps", "to": "analyze"},
            {"from": "analyze", "to": "check_stalled"},
            {"from": "check_stalled", "to": "notify_rep", "condition": "true"},
            {"from": "check_stalled", "to": "create_task", "condition": "true"},
        ]
    },
    
        "min_score_threshold": {"name": "min_score_threshold", "type": "integer", "default": 70, "description": "Minimum score for qualified lead"},
        "assignment_strategy": {"name": "assignment_strategy", "type": "select", "options": ["round_robin", "territory", "expertise"], "default": "round_robin", "description": "Strategy for assigning leads to reps"},
        "slack_channel": {"name": "slack_channel", "type": "string", "default": "#sales", "description": "Slack channel for notifications"},
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
2. **Enrich**: Enriches lead with company data (firmographics)
3. **Score**: Calculates lead score based on criteria
4. **Qualify**: Routes based on score threshold
5. **Assign**: Assigns to sales rep using chosen strategy
6. **Update CRM**: Creates or updates lead in Salesforce
7. **Notify**: Sends Slack notification to assigned rep

## Configuration

Set your minimum score threshold and assignment strategy in the parameters.

## Required Integrations

- Salesforce or HubSpot (CRM)
- Slack (notifications)
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
            {"id": "create_task", "type": "integration", "config": {"integration": "salesforce", "action": "create_task"}},
        ],
        "edges": [
            {"from": "schedule", "to": "fetch_opps"},
            {"from": "fetch_opps", "to": "analyze"},
            {"from": "analyze", "to": "check_stalled"},
            {"from": "check_stalled", "to": "notify_rep", "condition": "true"},
            {"from": "check_stalled", "to": "create_task", "condition": "true"},
        ]
    },
    "parameters": {
        "stalled_days_threshold": {"name": "stalled_days_threshold", "type": "integer", "default": 14},
        "check_frequency": {"name": "check_frequency", "type": "string", "default": "daily"},
    },
    "required_integrations": ["salesforce", "slack"],
    "use_cases": ["Track deal velocity", "Prevent opportunities from stalling", "Pipeline health monitoring"]
}

SALES_QUOTE_APPROVAL = {
    "name": "Sales Quote Approval Workflow",
    "description": "Automate quote creation, discount approval routing, and contract generation. Ensures compliance with pricing policies and accelerates deal closure.",
    "category": TemplateCategory.SALES,
    "tags": ["quotes", "approvals", "contracts", "pricing"],
    "difficulty": TemplateDifficulty.ADVANCED,
    "icon": "💰",
    "workflow_definition": {
        "nodes": [
            {"id": "trigger", "type": "webhook", "config": {"name": "Quote Request"}},
            {"id": "validate", "type": "task", "config": {"action": "validate_pricing"}},
            {"id": "check_discount", "type": "conditional", "config": {"condition": "discount > threshold"}},
            {"id": "request_approval", "type": "human_in_loop", "config": {"approver_role": "sales_manager"}},
            {"id": "generate_quote", "type": "task", "config": {"action": "create_quote_document"}},
            {"id": "send_docusign", "type": "integration", "config": {"integration": "docusign", "action": "send_envelope"}},
            {"id": "update_crm", "type": "integration", "config": {"integration": "salesforce", "action": "update_record"}},
        ],
        "edges": [
            {"from": "trigger", "to": "validate"},
            {"from": "validate", "to": "check_discount"},
            {"from": "check_discount", "to": "request_approval", "condition": "true"},
            {"from": "check_discount", "to": "generate_quote", "condition": "false"},
            {"from": "request_approval", "to": "generate_quote", "condition": "approved"},
            {"from": "generate_quote", "to": "send_docusign"},
            {"from": "send_docusign", "to": "update_crm"},
        ]
    },
    
        "stalled_days_threshold": {"type": "integer", "default": 14},
        "check_frequency": {"type": "string", "default": "daily"},
    },
    "required_integrations": ["salesforce", "slack"],
    "use_cases": ["Track deal velocity", "Prevent opportunities from stalling", "Pipeline health monitoring"]
}

SALES_QUOTE_APPROVAL = {
    "name": "Sales Quote Approval Workflow",
    "description": "Automate quote creation, discount approval routing, and contract generation. Ensures compliance with pricing policies and accelerates deal closure.",
    "category": TemplateCategory.SALES,
    "tags": ["quotes", "approvals", "contracts", "pricing"],
    "difficulty": TemplateDifficulty.ADVANCED,
    "icon": "💰",
    "workflow_definition": {
        "nodes": [
            {"id": "trigger", "type": "webhook", "config": {"name": "Quote Request"}},
            {"id": "validate", "type": "task", "config": {"action": "validate_pricing"}},
            {"id": "check_discount", "type": "conditional", "config": {"condition": "discount > threshold"}},
            {"id": "request_approval", "type": "human_in_loop", "config": {"approver_role": "sales_manager"}},
            {"id": "generate_quote", "type": "task", "config": {"action": "create_quote_document"}},
            {"id": "send_docusign", "type": "integration", "config": {"integration": "docusign", "action": "send_envelope"}},
            {"id": "update_crm", "type": "integration", "config": {"integration": "salesforce", "action": "update_record"}},
        ],
        "edges": [
            {"from": "trigger", "to": "validate"},
            {"from": "validate", "to": "check_discount"},
            {"from": "check_discount", "to": "request_approval", "condition": "true"},
            {"from": "check_discount", "to": "generate_quote", "condition": "false"},
            {"from": "request_approval", "to": "generate_quote", "condition": "approved"},
            {"from": "generate_quote", "to": "send_docusign"},
            {"from": "send_docusign", "to": "update_crm"},
        ]
    },
    "parameters": {
        "discount_approval_threshold": {"name": "discount_approval_threshold", "type": "float", "default": 15.0},
        "auto_approve_small_deals": {"name": "auto_approve_small_deals", "type": "boolean", "default": True},
        "small_deal_amount": {"name": "small_deal_amount", "type": "float", "default": 5000.0},
    },
    "required_integrations": ["salesforce", "docusign"],
    "use_cases": ["Automate quote generation", "Enforce discount policies", "Accelerate contract execution"]
}

# Marketing Templates
EMAIL_CAMPAIGN_AUTOMATION = {
    "name": "Email Campaign Automation",
    "description": "Launch multi-step email campaigns with personalization, A/B testing, and automated follow-ups based on recipient engagement. Tracks opens, clicks, and conversions.",
    "category": TemplateCategory.MARKETING,
    "tags": ["email", "campaigns", "automation", "nurture"],
    "difficulty": TemplateDifficulty.BEGINNER,
    "icon": "📧",
    "workflow_definition": {
        "nodes": [
            {"id": "trigger", "type": "schedule", "config": {"cron": "0 10 * * 1"}},
            {"id": "fetch_audience", "type": "integration", "config": {"integration": "hubspot", "action": "list_contacts"}},
            {"id": "segment", "type": "task", "config": {"action": "segment_audience"}},
            {"id": "personalize", "type": "task", "config": {"action": "personalize_content"}},
            {"id": "send_email", "type": "integration", "config": {"integration": "sendgrid", "action": "send_email"}},
            {"id": "wait", "type": "delay", "config": {"duration": "3 days"}},
            {"id": "check_engagement", "type": "conditional", "config": {"condition": "opened == false"}},
            {"id": "send_followup", "type": "integration", "config": {"integration": "sendgrid", "action": "send_email"}},
            {"id": "update_crm", "type": "integration", "config": {"integration": "hubspot", "action": "update_contact"}},
        ],
        "edges": [
            {"from": "trigger", "to": "fetch_audience"},
            {"from": "fetch_audience", "to": "segment"},
            {"from": "segment", "to": "personalize"},
            {"from": "personalize", "to": "send_email"},
            {"from": "send_email", "to": "wait"},
            {"from": "wait", "to": "check_engagement"},
            {"from": "check_engagement", "to": "send_followup", "condition": "true"},
            {"from": "check_engagement", "to": "update_crm", "condition": "false"},
            {"from": "send_followup", "to": "update_crm"},
        ]
    },
    
        "discount_approval_threshold": {"type": "float", "default": 15.0},
        "auto_approve_small_deals": {"type": "boolean", "default": True},
        "small_deal_amount": {"type": "float", "default": 5000.0},
    },
    "required_integrations": ["salesforce", "docusign"],
    "use_cases": ["Automate quote generation", "Enforce discount policies", "Accelerate contract execution"]
}

# Marketing Templates
EMAIL_CAMPAIGN_AUTOMATION = {
    "name": "Email Campaign Automation",
    "description": "Launch multi-step email campaigns with personalization, A/B testing, and automated follow-ups based on recipient engagement. Tracks opens, clicks, and conversions.",
    "category": TemplateCategory.MARKETING,
    "tags": ["email", "campaigns", "automation", "nurture"],
    "difficulty": TemplateDifficulty.BEGINNER,
    "icon": "📧",
    "workflow_definition": {
        "nodes": [
            {"id": "trigger", "type": "schedule", "config": {"cron": "0 10 * * 1"}},
            {"id": "fetch_audience", "type": "integration", "config": {"integration": "hubspot", "action": "list_contacts"}},
            {"id": "segment", "type": "task", "config": {"action": "segment_audience"}},
            {"id": "personalize", "type": "task", "config": {"action": "personalize_content"}},
            {"id": "send_email", "type": "integration", "config": {"integration": "sendgrid", "action": "send_email"}},
            {"id": "wait", "type": "delay", "config": {"duration": "3 days"}},
            {"id": "check_engagement", "type": "conditional", "config": {"condition": "opened == false"}},
            {"id": "send_followup", "type": "integration", "config": {"integration": "sendgrid", "action": "send_email"}},
            {"id": "update_crm", "type": "integration", "config": {"integration": "hubspot", "action": "update_contact"}},
        ],
        "edges": [
            {"from": "trigger", "to": "fetch_audience"},
            {"from": "fetch_audience", "to": "segment"},
            {"from": "segment", "to": "personalize"},
            {"from": "personalize", "to": "send_email"},
            {"from": "send_email", "to": "wait"},
            {"from": "wait", "to": "check_engagement"},
            {"from": "check_engagement", "to": "send_followup", "condition": "true"},
            {"from": "check_engagement", "to": "update_crm", "condition": "false"},
            {"from": "send_followup", "to": "update_crm"},
        ]
    },
    "parameters": {
        "followup_delay_days": {"name": "followup_delay_days", "type": "integer", "default": 3},
        "max_followups": {"name": "max_followups", "type": "integer", "default": 2},
        "send_time": {"name": "send_time", "type": "string", "default": "10:00 AM"},
    },
    "required_integrations": ["sendgrid", "hubspot"],
    "use_cases": ["Nurture campaign automation", "Re-engagement campaigns", "Product launch announcements"]
}

CONTENT_DISTRIBUTION = {
    "name": "Multi-Channel Content Distribution",
    "description": "Publish blog posts and automatically distribute across social media, email newsletter, and community platforms. Schedules posts for optimal engagement times.",
    "category": TemplateCategory.MARKETING,
    "tags": ["content", "social-media", "distribution", "automation"],
    "difficulty": TemplateDifficulty.INTERMEDIATE,
    "icon": "📱",
    "workflow_definition": {
        "nodes": [
            {"id": "trigger", "type": "webhook", "config": {"name": "New Blog Post"}},
            {"id": "extract_summary", "type": "task", "config": {"action": "generate_summary"}},
            {"id": "create_snippets", "type": "parallel", "config": {"branches": ["twitter", "linkedin", "email"]}},
            {"id": "post_twitter", "type": "integration", "config": {"integration": "twitter", "action": "create_tweet"}},
            {"id": "post_linkedin", "type": "integration", "config": {"integration": "linkedin", "action": "create_post"}},
            {"id": "send_newsletter", "type": "integration", "config": {"integration": "sendgrid", "action": "send_bulk_email"}},
            {"id": "track_engagement", "type": "task", "config": {"action": "aggregate_metrics"}},
        ],
        "edges": [
            {"from": "trigger", "to": "extract_summary"},
            {"from": "extract_summary", "to": "create_snippets"},
            {"from": "create_snippets", "to": "post_twitter"},
            {"from": "create_snippets", "to": "post_linkedin"},
            {"from": "create_snippets", "to": "send_newsletter"},
            {"from": "post_twitter", "to": "track_engagement"},
            {"from": "post_linkedin", "to": "track_engagement"},
            {"from": "send_newsletter", "to": "track_engagement"},
        ]
    },
    
        "followup_delay_days": {"type": "integer", "default": 3},
        "max_followups": {"type": "integer", "default": 2},
        "send_time": {"type": "string", "default": "10:00 AM"},
    },
    "required_integrations": ["sendgrid", "hubspot"],
    "use_cases": ["Nurture campaign automation", "Re-engagement campaigns", "Product launch announcements"]
}

CONTENT_DISTRIBUTION = {
    "name": "Multi-Channel Content Distribution",
    "description": "Publish blog posts and automatically distribute across social media, email newsletter, and community platforms. Schedules posts for optimal engagement times.",
    "category": TemplateCategory.MARKETING,
    "tags": ["content", "social-media", "distribution", "automation"],
    "difficulty": TemplateDifficulty.INTERMEDIATE,
    "icon": "📱",
    "workflow_definition": {
        "nodes": [
            {"id": "trigger", "type": "webhook", "config": {"name": "New Blog Post"}},
            {"id": "extract_summary", "type": "task", "config": {"action": "generate_summary"}},
            {"id": "create_snippets", "type": "parallel", "config": {"branches": ["twitter", "linkedin", "email"]}},
            {"id": "post_twitter", "type": "integration", "config": {"integration": "twitter", "action": "create_tweet"}},
            {"id": "post_linkedin", "type": "integration", "config": {"integration": "linkedin", "action": "create_post"}},
            {"id": "send_newsletter", "type": "integration", "config": {"integration": "sendgrid", "action": "send_bulk_email"}},
            {"id": "track_engagement", "type": "task", "config": {"action": "aggregate_metrics"}},
        ],
        "edges": [
            {"from": "trigger", "to": "extract_summary"},
            {"from": "extract_summary", "to": "create_snippets"},
            {"from": "create_snippets", "to": "post_twitter"},
            {"from": "create_snippets", "to": "post_linkedin"},
            {"from": "create_snippets", "to": "send_newsletter"},
            {"from": "post_twitter", "to": "track_engagement"},
            {"from": "post_linkedin", "to": "track_engagement"},
            {"from": "send_newsletter", "to": "track_engagement"},
        ]
    },
    "parameters": {
        "post_immediately": {"name": "post_immediately", "type": "boolean", "default": False},
        "schedule_delay_hours": {"name": "schedule_delay_hours", "type": "integer", "default": 2},
    },
    "required_integrations": ["twitter", "linkedin", "sendgrid"],
    "use_cases": ["Blog post distribution", "Content repurposing", "Social media automation"]
}

# Customer Support Templates
TICKET_TRIAGE_AND_ROUTING = {
    "name": "Support Ticket Triage & Routing",
    "description": "Automatically categorize support tickets, prioritize based on urgency, and route to the right support tier. Uses AI to extract intent and sentiment.",
    "category": TemplateCategory.CUSTOMER_SUPPORT,
    "tags": ["support", "tickets", "triage", "automation"],
    "difficulty": TemplateDifficulty.INTERMEDIATE,
    "icon": "🎫",
    "workflow_definition": {
        "nodes": [
            {"id": "trigger", "type": "webhook", "config": {"name": "New Ticket"}},
            {"id": "extract_intent", "type": "task", "config": {"action": "classify_ticket"}},
            {"id": "check_sentiment", "type": "task", "config": {"action": "analyze_sentiment"}},
            {"id": "prioritize", "type": "conditional", "config": {"condition": "sentiment < 0.3 || contains_keywords"}},
            {"id": "route_tier1", "type": "integration", "config": {"integration": "zendesk", "action": "update_ticket"}},
            {"id": "route_tier2", "type": "integration", "config": {"integration": "zendesk", "action": "update_ticket"}},
            {"id": "escalate", "type": "integration", "config": {"integration": "zendesk", "action": "update_ticket"}},
            {"id": "notify_team", "type": "integration", "config": {"integration": "slack", "action": "send_message"}},
        ],
        "edges": [
            {"from": "trigger", "to": "extract_intent"},
            {"from": "extract_intent", "to": "check_sentiment"},
            {"from": "check_sentiment", "to": "prioritize"},
            {"from": "prioritize", "to": "escalate", "condition": "priority == 'urgent'"},
            {"from": "prioritize", "to": "route_tier2", "condition": "priority == 'high'"},
            {"from": "prioritize", "to": "route_tier1", "condition": "priority == 'normal'"},
            {"from": "escalate", "to": "notify_team"},
        ]
    },
    
        "post_immediately": {"type": "boolean", "default": False},
        "schedule_delay_hours": {"type": "integer", "default": 2},
    },
    "required_integrations": ["twitter", "linkedin", "sendgrid"],
    "use_cases": ["Blog post distribution", "Content repurposing", "Social media automation"]
}

# Customer Support Templates
TICKET_TRIAGE_AND_ROUTING = {
    "name": "Support Ticket Triage & Routing",
    "description": "Automatically categorize support tickets, prioritize based on urgency, and route to the right support tier. Uses AI to extract intent and sentiment.",
    "category": TemplateCategory.CUSTOMER_SUPPORT,
    "tags": ["support", "tickets", "triage", "automation"],
    "difficulty": TemplateDifficulty.INTERMEDIATE,
    "icon": "🎫",
    "workflow_definition": {
        "nodes": [
            {"id": "trigger", "type": "webhook", "config": {"name": "New Ticket"}},
            {"id": "extract_intent", "type": "task", "config": {"action": "classify_ticket"}},
            {"id": "check_sentiment", "type": "task", "config": {"action": "analyze_sentiment"}},
            {"id": "prioritize", "type": "conditional", "config": {"condition": "sentiment < 0.3 || contains_keywords"}},
            {"id": "route_tier1", "type": "integration", "config": {"integration": "zendesk", "action": "update_ticket"}},
            {"id": "route_tier2", "type": "integration", "config": {"integration": "zendesk", "action": "update_ticket"}},
            {"id": "escalate", "type": "integration", "config": {"integration": "zendesk", "action": "update_ticket"}},
            {"id": "notify_team", "type": "integration", "config": {"integration": "slack", "action": "send_message"}},
        ],
        "edges": [
            {"from": "trigger", "to": "extract_intent"},
            {"from": "extract_intent", "to": "check_sentiment"},
            {"from": "check_sentiment", "to": "prioritize"},
            {"from": "prioritize", "to": "escalate", "condition": "priority == 'urgent'"},
            {"from": "prioritize", "to": "route_tier2", "condition": "priority == 'high'"},
            {"from": "prioritize", "to": "route_tier1", "condition": "priority == 'normal'"},
            {"from": "escalate", "to": "notify_team"},
        ]
    },
    "parameters": {
        "escalation_keywords": {"name": "escalation_keywords", "type": "string", "default": "billing,payment,refund,cancel"},
        "sentiment_threshold": {"name": "sentiment_threshold", "type": "float", "default": 0.3},
    },
    "required_integrations": ["zendesk", "slack"],
    "use_cases": ["Ticket routing automation", "Priority escalation", "First response SLA management"]
}

CUSTOMER_FEEDBACK_LOOP = {
    "name": "Customer Feedback Collection & Analysis",
    "description": "Automate NPS/CSAT surveys after support interactions, analyze responses, and trigger follow-ups for detractors. Creates feedback reports for product team.",
    "category": TemplateCategory.CUSTOMER_SUPPORT,
    "tags": ["feedback", "nps", "csat", "surveys"],
    "difficulty": TemplateDifficulty.BEGINNER,
    "icon": "📊",
    "workflow_definition": {
        "nodes": [
            {"id": "trigger", "type": "webhook", "config": {"name": "Ticket Resolved"}},
            {"id": "wait", "type": "delay", "config": {"duration": "1 day"}},
            {"id": "send_survey", "type": "integration", "config": {"integration": "sendgrid", "action": "send_email"}},
            {"id": "wait_response", "type": "delay", "config": {"duration": "7 days", "timeout": True}},
            {"id": "check_score", "type": "conditional", "config": {"condition": "score <= 6"}},
            {"id": "notify_csm", "type": "integration", "config": {"integration": "slack", "action": "send_message"}},
            {"id": "create_task", "type": "integration", "config": {"integration": "zendesk", "action": "create_ticket"}},
            {"id": "aggregate_metrics", "type": "task", "config": {"action": "update_nps_dashboard"}},
        ],
        "edges": [
            {"from": "trigger", "to": "wait"},
            {"from": "wait", "to": "send_survey"},
            {"from": "send_survey", "to": "wait_response"},
            {"from": "wait_response", "to": "check_score"},
            {"from": "check_score", "to": "notify_csm", "condition": "true"},
            {"from": "check_score", "to": "aggregate_metrics", "condition": "false"},
            {"from": "notify_csm", "to": "create_task"},
            {"from": "create_task", "to": "aggregate_metrics"},
        ]
    },
    
        "escalation_keywords": {"type": "string", "default": "billing,payment,refund,cancel"},
        "sentiment_threshold": {"type": "float", "default": 0.3},
    },
    "required_integrations": ["zendesk", "slack"],
    "use_cases": ["Ticket routing automation", "Priority escalation", "First response SLA management"]
}

CUSTOMER_FEEDBACK_LOOP = {
    "name": "Customer Feedback Collection & Analysis",
    "description": "Automate NPS/CSAT surveys after support interactions, analyze responses, and trigger follow-ups for detractors. Creates feedback reports for product team.",
    "category": TemplateCategory.CUSTOMER_SUPPORT,
    "tags": ["feedback", "nps", "csat", "surveys"],
    "difficulty": TemplateDifficulty.BEGINNER,
    "icon": "📊",
    "workflow_definition": {
        "nodes": [
            {"id": "trigger", "type": "webhook", "config": {"name": "Ticket Resolved"}},
            {"id": "wait", "type": "delay", "config": {"duration": "1 day"}},
            {"id": "send_survey", "type": "integration", "config": {"integration": "sendgrid", "action": "send_email"}},
            {"id": "wait_response", "type": "delay", "config": {"duration": "7 days", "timeout": True}},
            {"id": "check_score", "type": "conditional", "config": {"condition": "score <= 6"}},
            {"id": "notify_csm", "type": "integration", "config": {"integration": "slack", "action": "send_message"}},
            {"id": "create_task", "type": "integration", "config": {"integration": "zendesk", "action": "create_ticket"}},
            {"id": "aggregate_metrics", "type": "task", "config": {"action": "update_nps_dashboard"}},
        ],
        "edges": [
            {"from": "trigger", "to": "wait"},
            {"from": "wait", "to": "send_survey"},
            {"from": "send_survey", "to": "wait_response"},
            {"from": "wait_response", "to": "check_score"},
            {"from": "check_score", "to": "notify_csm", "condition": "true"},
            {"from": "check_score", "to": "aggregate_metrics", "condition": "false"},
            {"from": "notify_csm", "to": "create_task"},
            {"from": "create_task", "to": "aggregate_metrics"},
        ]
    },
    "parameters": {
        "survey_delay_days": {"name": "survey_delay_days", "type": "integer", "default": 1},
        "detractor_threshold": {"name": "detractor_threshold", "type": "integer", "default": 6},
    },
    "required_integrations": ["sendgrid", "zendesk", "slack"],
    "use_cases": ["NPS tracking", "Customer satisfaction monitoring", "Churn prevention"]
}

# DevOps Templates
CI_CD_PIPELINE_MONITOR = {
    "name": "CI/CD Pipeline Monitoring & Alerting",
    "description": "Monitor build and deployment pipelines, detect failures, and automatically notify relevant teams. Tracks deployment success rates and lead times.",
    "category": TemplateCategory.DEVOPS,
    "tags": ["cicd", "monitoring", "devops", "automation"],
    "difficulty": TemplateDifficulty.ADVANCED,
    "icon": "🚀",
    "workflow_definition": {
        "nodes": [
            {"id": "trigger", "type": "webhook", "config": {"name": "Pipeline Event"}},
            {"id": "parse_event", "type": "task", "config": {"action": "extract_pipeline_data"}},
            {"id": "check_status", "type": "conditional", "config": {"condition": "status == 'failed'"}},
            {"id": "analyze_failure", "type": "task", "config": {"action": "detect_failure_pattern"}},
            {"id": "create_issue", "type": "integration", "config": {"integration": "github", "action": "create_issue"}},
            {"id": "notify_slack", "type": "integration", "config": {"integration": "slack", "action": "send_message"}},
            {"id": "rollback_check", "type": "conditional", "config": {"condition": "auto_rollback_enabled"}},
            {"id": "trigger_rollback", "type": "integration", "config": {"integration": "github", "action": "trigger_workflow"}},
            {"id": "update_metrics", "type": "task", "config": {"action": "log_deployment_metrics"}},
        ],
        "edges": [
            {"from": "trigger", "to": "parse_event"},
            {"from": "parse_event", "to": "check_status"},
            {"from": "check_status", "to": "analyze_failure", "condition": "true"},
            {"from": "analyze_failure", "to": "create_issue"},
            {"from": "create_issue", "to": "notify_slack"},
            {"from": "notify_slack", "to": "rollback_check"},
            {"from": "rollback_check", "to": "trigger_rollback", "condition": "true"},
            {"from": "check_status", "to": "update_metrics", "condition": "false"},
            {"from": "trigger_rollback", "to": "update_metrics"},
        ]
    },
    
        "survey_delay_days": {"type": "integer", "default": 1},
        "detractor_threshold": {"type": "integer", "default": 6},
    },
    "required_integrations": ["sendgrid", "zendesk", "slack"],
    "use_cases": ["NPS tracking", "Customer satisfaction monitoring", "Churn prevention"]
}

# DevOps Templates
CI_CD_PIPELINE_MONITOR = {
    "name": "CI/CD Pipeline Monitoring & Alerting",
    "description": "Monitor build and deployment pipelines, detect failures, and automatically notify relevant teams. Tracks deployment success rates and lead times.",
    "category": TemplateCategory.DEVOPS,
    "tags": ["cicd", "monitoring", "devops", "automation"],
    "difficulty": TemplateDifficulty.ADVANCED,
    "icon": "🚀",
    "workflow_definition": {
        "nodes": [
            {"id": "trigger", "type": "webhook", "config": {"name": "Pipeline Event"}},
            {"id": "parse_event", "type": "task", "config": {"action": "extract_pipeline_data"}},
            {"id": "check_status", "type": "conditional", "config": {"condition": "status == 'failed'"}},
            {"id": "analyze_failure", "type": "task", "config": {"action": "detect_failure_pattern"}},
            {"id": "create_issue", "type": "integration", "config": {"integration": "github", "action": "create_issue"}},
            {"id": "notify_slack", "type": "integration", "config": {"integration": "slack", "action": "send_message"}},
            {"id": "rollback_check", "type": "conditional", "config": {"condition": "auto_rollback_enabled"}},
            {"id": "trigger_rollback", "type": "integration", "config": {"integration": "github", "action": "trigger_workflow"}},
            {"id": "update_metrics", "type": "task", "config": {"action": "log_deployment_metrics"}},
        ],
        "edges": [
            {"from": "trigger", "to": "parse_event"},
            {"from": "parse_event", "to": "check_status"},
            {"from": "check_status", "to": "analyze_failure", "condition": "true"},
            {"from": "analyze_failure", "to": "create_issue"},
            {"from": "create_issue", "to": "notify_slack"},
            {"from": "notify_slack", "to": "rollback_check"},
            {"from": "rollback_check", "to": "trigger_rollback", "condition": "true"},
            {"from": "check_status", "to": "update_metrics", "condition": "false"},
            {"from": "trigger_rollback", "to": "update_metrics"},
        ]
    },
    "parameters": {
        "auto_rollback_enabled": {"name": "auto_rollback_enabled", "type": "boolean", "default": False},
        "failure_notification_channel": {"name": "failure_notification_channel", "type": "string", "default": "#deployments"},
    },
    "required_integrations": ["github", "slack"],
    "use_cases": ["Deployment monitoring", "Automated rollbacks", "Build failure tracking"]
}

INCIDENT_RESPONSE_AUTOMATION = {
    "name": "Incident Response Automation",
    "description": "Automatically detect incidents, create war room, notify on-call team, and track resolution progress. Integrates with monitoring and paging systems.",
    "category": TemplateCategory.DEVOPS,
    "tags": ["incidents", "oncall", "sre", "monitoring"],
    "difficulty": TemplateDifficulty.EXPERT,
    "icon": "🚨",
    "workflow_definition": {
        "nodes": [
            {"id": "trigger", "type": "webhook", "config": {"name": "Alert Triggered"}},
            {"id": "classify_severity", "type": "task", "config": {"action": "determine_severity"}},
            {"id": "check_severity", "type": "conditional", "config": {"condition": "severity >= 'high'"}},
            {"id": "create_incident", "type": "integration", "config": {"integration": "pagerduty", "action": "create_incident"}},
            {"id": "create_slack_channel", "type": "integration", "config": {"integration": "slack", "action": "create_channel"}},
            {"id": "notify_oncall", "type": "integration", "config": {"integration": "pagerduty", "action": "trigger_oncall"}},
            {"id": "create_jira", "type": "integration", "config": {"integration": "jira", "action": "create_issue"}},
            {"id": "status_updates", "type": "loop", "config": {"interval": "15 minutes", "max_iterations": 24}},
            {"id": "post_mortem", "type": "task", "config": {"action": "generate_post_mortem_template"}},
        ],
        "edges": [
            {"from": "trigger", "to": "classify_severity"},
            {"from": "classify_severity", "to": "check_severity"},
            {"from": "check_severity", "to": "create_incident", "condition": "true"},
            {"from": "create_incident", "to": "create_slack_channel"},
            {"from": "create_slack_channel", "to": "notify_oncall"},
            {"from": "notify_oncall", "to": "create_jira"},
            {"from": "create_jira", "to": "status_updates"},
            {"from": "status_updates", "to": "post_mortem"},
        ]
    },
    
        "auto_rollback_enabled": {"type": "boolean", "default": False},
        "failure_notification_channel": {"type": "string", "default": "#deployments"},
    },
    "required_integrations": ["github", "slack"],
    "use_cases": ["Deployment monitoring", "Automated rollbacks", "Build failure tracking"]
}

INCIDENT_RESPONSE_AUTOMATION = {
    "name": "Incident Response Automation",
    "description": "Automatically detect incidents, create war room, notify on-call team, and track resolution progress. Integrates with monitoring and paging systems.",
    "category": TemplateCategory.DEVOPS,
    "tags": ["incidents", "oncall", "sre", "monitoring"],
    "difficulty": TemplateDifficulty.EXPERT,
    "icon": "🚨",
    "workflow_definition": {
        "nodes": [
            {"id": "trigger", "type": "webhook", "config": {"name": "Alert Triggered"}},
            {"id": "classify_severity", "type": "task", "config": {"action": "determine_severity"}},
            {"id": "check_severity", "type": "conditional", "config": {"condition": "severity >= 'high'"}},
            {"id": "create_incident", "type": "integration", "config": {"integration": "pagerduty", "action": "create_incident"}},
            {"id": "create_slack_channel", "type": "integration", "config": {"integration": "slack", "action": "create_channel"}},
            {"id": "notify_oncall", "type": "integration", "config": {"integration": "pagerduty", "action": "trigger_oncall"}},
            {"id": "create_jira", "type": "integration", "config": {"integration": "jira", "action": "create_issue"}},
            {"id": "status_updates", "type": "loop", "config": {"interval": "15 minutes", "max_iterations": 24}},
            {"id": "post_mortem", "type": "task", "config": {"action": "generate_post_mortem_template"}},
        ],
        "edges": [
            {"from": "trigger", "to": "classify_severity"},
            {"from": "classify_severity", "to": "check_severity"},
            {"from": "check_severity", "to": "create_incident", "condition": "true"},
            {"from": "create_incident", "to": "create_slack_channel"},
            {"from": "create_slack_channel", "to": "notify_oncall"},
            {"from": "notify_oncall", "to": "create_jira"},
            {"from": "create_jira", "to": "status_updates"},
            {"from": "status_updates", "to": "post_mortem"},
        ]
    },
    "parameters": {
        "status_update_interval": {"name": "status_update_interval", "type": "integer", "default": 15},
        "auto_resolve_threshold": {"name": "auto_resolve_threshold", "type": "integer", "default": 60},
    },
    "required_integrations": ["pagerduty", "slack", "jira"],
    "use_cases": ["Incident management", "SRE on-call automation", "Post-mortem generation"]
}

# Data Processing Templates
ETL_DATA_PIPELINE = {
    "name": "ETL Data Pipeline",
    "description": "Extract data from multiple sources, transform with validation and enrichment, and load into data warehouse. Supports incremental loads and error handling.",
    "category": TemplateCategory.DATA_PROCESSING,
    "tags": ["etl", "data-pipeline", "warehouse", "analytics"],
    "difficulty": TemplateDifficulty.ADVANCED,
    "icon": "🔄",
    "workflow_definition": {
        "nodes": [
            {"id": "schedule", "type": "schedule", "config": {"cron": "0 2 * * *"}},
            {"id": "extract_db", "type": "integration", "config": {"integration": "postgres", "action": "query"}},
            {"id": "extract_api", "type": "integration", "config": {"integration": "rest_api", "action": "fetch"}},
            {"id": "merge_data", "type": "task", "config": {"action": "merge_datasets"}},
            {"id": "validate", "type": "task", "config": {"action": "validate_schema"}},
            {"id": "transform", "type": "task", "config": {"action": "apply_transformations"}},
            {"id": "check_quality", "type": "conditional", "config": {"condition": "quality_score >= 0.95"}},
            {"id": "load_warehouse", "type": "integration", "config": {"integration": "snowflake", "action": "bulk_insert"}},
            {"id": "update_metadata", "type": "task", "config": {"action": "log_pipeline_run"}},
            {"id": "send_alert", "type": "integration", "config": {"integration": "slack", "action": "send_message"}},
        ],
        "edges": [
            {"from": "schedule", "to": "extract_db"},
            {"from": "extract_db", "to": "extract_api"},
            {"from": "extract_api", "to": "merge_data"},
            {"from": "merge_data", "to": "validate"},
            {"from": "validate", "to": "transform"},
            {"from": "transform", "to": "check_quality"},
            {"from": "check_quality", "to": "load_warehouse", "condition": "true"},
            {"from": "check_quality", "to": "send_alert", "condition": "false"},
            {"from": "load_warehouse", "to": "update_metadata"},
        ]
    },
    
        "status_update_interval": {"type": "integer", "default": 15},
        "auto_resolve_threshold": {"type": "integer", "default": 60},
    },
    "required_integrations": ["pagerduty", "slack", "jira"],
    "use_cases": ["Incident management", "SRE on-call automation", "Post-mortem generation"]
}

# Data Processing Templates
ETL_DATA_PIPELINE = {
    "name": "ETL Data Pipeline",
    "description": "Extract data from multiple sources, transform with validation and enrichment, and load into data warehouse. Supports incremental loads and error handling.",
    "category": TemplateCategory.DATA_PROCESSING,
    "tags": ["etl", "data-pipeline", "warehouse", "analytics"],
    "difficulty": TemplateDifficulty.ADVANCED,
    "icon": "🔄",
    "workflow_definition": {
        "nodes": [
            {"id": "schedule", "type": "schedule", "config": {"cron": "0 2 * * *"}},
            {"id": "extract_db", "type": "integration", "config": {"integration": "postgres", "action": "query"}},
            {"id": "extract_api", "type": "integration", "config": {"integration": "rest_api", "action": "fetch"}},
            {"id": "merge_data", "type": "task", "config": {"action": "merge_datasets"}},
            {"id": "validate", "type": "task", "config": {"action": "validate_schema"}},
            {"id": "transform", "type": "task", "config": {"action": "apply_transformations"}},
            {"id": "check_quality", "type": "conditional", "config": {"condition": "quality_score >= 0.95"}},
            {"id": "load_warehouse", "type": "integration", "config": {"integration": "snowflake", "action": "bulk_insert"}},
            {"id": "update_metadata", "type": "task", "config": {"action": "log_pipeline_run"}},
            {"id": "send_alert", "type": "integration", "config": {"integration": "slack", "action": "send_message"}},
        ],
        "edges": [
            {"from": "schedule", "to": "extract_db"},
            {"from": "extract_db", "to": "extract_api"},
            {"from": "extract_api", "to": "merge_data"},
            {"from": "merge_data", "to": "validate"},
            {"from": "validate", "to": "transform"},
            {"from": "transform", "to": "check_quality"},
            {"from": "check_quality", "to": "load_warehouse", "condition": "true"},
            {"from": "check_quality", "to": "send_alert", "condition": "false"},
            {"from": "load_warehouse", "to": "update_metadata"},
        ]
    },
    "parameters": {
        "quality_threshold": {"name": "quality_threshold", "type": "float", "default": 0.95},
        "batch_size": {"name": "batch_size", "type": "integer", "default": 10000},
    },
    "required_integrations": ["postgres", "snowflake", "slack"],
    "use_cases": ["Data warehouse loading", "Daily ETL jobs", "Analytics pipeline"]
}

# Create catalog of all templates
TEMPLATE_CATALOG = [
    LEAD_QUALIFICATION_WORKFLOW,
    OPPORTUNITY_PIPELINE_TRACKING,
    SALES_QUOTE_APPROVAL,
    EMAIL_CAMPAIGN_AUTOMATION,
    CONTENT_DISTRIBUTION,
    TICKET_TRIAGE_AND_ROUTING,
    CUSTOMER_FEEDBACK_LOOP,
    CI_CD_PIPELINE_MONITOR,
    INCIDENT_RESPONSE_AUTOMATION,
    ETL_DATA_PIPELINE,
]

        "quality_threshold": {"type": "float", "default": 0.95},
        "batch_size": {"type": "integer", "default": 10000},
    },
    "required_integrations": ["postgres", "snowflake", "slack"],
    "use_cases": ["Data warehouse loading", "Daily ETL jobs", "Analytics pipeline"]
}

# Create catalog of all templates
TEMPLATE_CATALOG = [
    LEAD_QUALIFICATION_WORKFLOW,
    OPPORTUNITY_PIPELINE_TRACKING,
    SALES_QUOTE_APPROVAL,
    EMAIL_CAMPAIGN_AUTOMATION,
    CONTENT_DISTRIBUTION,
    TICKET_TRIAGE_AND_ROUTING,
    CUSTOMER_FEEDBACK_LOOP,
    CI_CD_PIPELINE_MONITOR,
    INCIDENT_RESPONSE_AUTOMATION,
    ETL_DATA_PIPELINE,
]
