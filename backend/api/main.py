"""
FastAPI Main Application

REST API for Agent Orchestration Platform.
"""

import sys
from pathlib import Path

# Add agent-orchestration root to path so 'backend' package is importable
# Path: api/main.py -> api -> backend -> agent-orchestration
agent_orchestration_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(agent_orchestration_root))

from contextlib import asynccontextmanager
from fastapi import FastAPI, HTTPException, Header, Response, Depends
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from typing import List, Optional
from uuid import UUID
import secrets

from backend.shared.models import (
    AgentConfig,
    AgentState,
    Task,
    TaskInput,
    TaskOutput,
    LLMRequest,
    LLMResponse,
    TaskStatus,
    TaskPriority,
)
from backend.shared.config import get_settings
from backend.orchestrator import get_registry, get_router, get_queue
from backend.orchestrator.queue import set_queue
try:
    from backend.gateway.llm_proxy import get_gateway
except ImportError:
    get_gateway = None  # core.llm not available (open-source standalone mode)
from backend.observer.metrics_collector import get_collector
from backend.observer.alert_manager import get_alert_manager
from backend.shared.audit_logger import init_audit_logger
from backend.database.session import AsyncSessionLocal
import asyncio


# Global reference for scheduler runner task
_scheduler_task = None
_scheduler_runner = None


async def _seed_marketplace_agents():
    """Seed marketplace with useful pre-built agents if table is empty."""
    from backend.shared.marketplace_models import MarketplaceAgent
    from sqlalchemy import select, func
    from datetime import datetime, timedelta

    async with AsyncSessionLocal() as db:
        count_result = await db.execute(
            select(func.count(MarketplaceAgent.id))
        )
        if count_result.scalar() > 0:
            return  # Already seeded

        now = datetime.utcnow()
        publisher = "user-admin-001"
        publisher_name = "Orchestly"

        agents = [
            # ── Featured Agents (6) ────────────────────────────────────────
            MarketplaceAgent(
                name="Smart Ticket Router",
                slug="smart-ticket-router",
                tagline="Classify and route support tickets by intent, urgency, and required expertise",
                description="Analyzes incoming support tickets using NLP to determine customer intent (billing, technical, account, feature request), urgency level (P0-P3), and required expertise. Routes to the correct team queue with a confidence score. Handles multi-language tickets and learns from routing corrections over time.",
                publisher_id=publisher, publisher_name=publisher_name,
                category="customer_service",
                tags=["support", "routing", "nlp", "classification", "multilingual"],
                visibility="public", pricing="free",
                agent_config={
                    "model": "claude-sonnet-4-5-20250929",
                    "temperature": 0.2,
                    "system_prompt": "You are a support ticket classifier. Given a ticket, output JSON with: intent (billing|technical|account|feature_request|other), urgency (p0|p1|p2|p3), team (billing_team|engineering|account_mgmt|product), confidence (0-1), and a one-line summary.",
                    "tools": ["ticket_fetch", "queue_router", "escalation_trigger"],
                    "max_tokens": 500,
                },
                required_integrations=["zendesk", "slack"],
                required_capabilities=["text_classification"],
                version="2.1.0",
                is_verified=True, is_featured=True, is_active=True,
                install_count=0, rating_avg=0, rating_count=0,
                published_at=now - timedelta(days=120),
                created_at=now - timedelta(days=120),
            ),
            MarketplaceAgent(
                name="Code Review Agent",
                slug="code-review-agent",
                tagline="Automated PR reviews for bugs, security issues, and style violations",
                description="Reviews pull requests by analyzing diffs against your team's coding standards. Detects common bugs (null dereferences, race conditions, resource leaks), security vulnerabilities (injection, auth bypass, secrets in code), and style inconsistencies. Posts inline comments on specific lines and a summary verdict (approve/request changes). Configurable severity thresholds and language support.",
                publisher_id=publisher, publisher_name=publisher_name,
                category="engineering",
                tags=["code-review", "security", "github", "ci-cd", "quality"],
                visibility="public", pricing="free",
                agent_config={
                    "model": "claude-opus-4-6",
                    "temperature": 0.1,
                    "system_prompt": "You are a senior code reviewer. Analyze the PR diff and identify: 1) Bugs (null checks, edge cases, race conditions), 2) Security issues (injection, auth, secrets), 3) Style violations against the project conventions. For each finding, provide the file, line range, severity (critical/warning/info), and a specific fix suggestion. End with an overall verdict.",
                    "tools": ["github_pr_fetch", "github_comment", "github_review"],
                    "max_tokens": 4000,
                },
                required_integrations=["github"],
                required_capabilities=["code_analysis", "long_context"],
                version="3.0.1",
                is_verified=True, is_featured=True, is_active=True,
                install_count=0, rating_avg=0, rating_count=0,
                published_at=now - timedelta(days=90),
                created_at=now - timedelta(days=90),
            ),
            MarketplaceAgent(
                name="Meeting Summarizer",
                slug="meeting-summarizer",
                tagline="Turn meeting transcripts into structured notes with action items and decisions",
                description="Processes meeting transcripts (from Zoom, Teams, or raw text) into structured summaries. Extracts key discussion points, decisions made, action items with owners and deadlines, open questions, and follow-up meeting suggestions. Outputs in your preferred format (Notion, Confluence, Slack, or markdown). Handles multi-speaker attribution and identifies sentiment shifts.",
                publisher_id=publisher, publisher_name=publisher_name,
                category="productivity",
                tags=["meetings", "transcription", "notes", "action-items", "slack"],
                visibility="public", pricing="free",
                agent_config={
                    "model": "claude-sonnet-4-5-20250929",
                    "temperature": 0.3,
                    "system_prompt": "You are a meeting notes assistant. Given a transcript, produce structured output: ## Summary (2-3 sentences), ## Key Decisions (bulleted), ## Action Items (table: owner | task | deadline), ## Open Questions, ## Follow-ups. Attribute statements to speakers when possible.",
                    "tools": ["transcript_fetch", "slack_post", "notion_page_create"],
                    "max_tokens": 3000,
                },
                required_integrations=["slack"],
                required_capabilities=["long_context", "summarization"],
                version="2.3.0",
                is_verified=True, is_featured=True, is_active=True,
                install_count=0, rating_avg=0, rating_count=0,
                published_at=now - timedelta(days=150),
                created_at=now - timedelta(days=150),
            ),
            MarketplaceAgent(
                name="Lead Scoring Engine",
                slug="lead-scoring-engine",
                tagline="Score and prioritize inbound leads based on ICP fit, engagement, and buying signals",
                description="Analyzes incoming leads from multiple sources (website forms, LinkedIn, events) and scores them 0-100 based on: ICP fit (company size, industry, tech stack), engagement signals (page visits, content downloads, email opens), and buying intent (pricing page views, demo requests, competitor mentions). Syncs scores to your CRM and triggers alerts for hot leads above threshold.",
                publisher_id=publisher, publisher_name=publisher_name,
                category="sales_automation",
                tags=["leads", "scoring", "crm", "sales", "automation"],
                visibility="public", pricing="free",
                agent_config={
                    "model": "claude-sonnet-4-5-20250929",
                    "temperature": 0.2,
                    "system_prompt": "You are a lead scoring analyst. Given lead data (company info, engagement history, form submissions), output a JSON score object: { score: 0-100, icp_fit: 0-100, engagement: 0-100, intent: 0-100, tier: 'hot'|'warm'|'cold', reasoning: '...', next_action: '...' }",
                    "tools": ["crm_lookup", "enrichment_api", "slack_notify"],
                    "max_tokens": 800,
                },
                required_integrations=["salesforce", "slack"],
                required_capabilities=["structured_output"],
                version="1.8.0",
                is_verified=True, is_featured=True, is_active=True,
                install_count=0, rating_avg=0, rating_count=0,
                published_at=now - timedelta(days=75),
                created_at=now - timedelta(days=75),
            ),
            MarketplaceAgent(
                name="Incident Responder",
                slug="incident-responder",
                tagline="Correlate alerts, diagnose root cause, and execute runbook actions automatically",
                description="Monitors incoming alerts from PagerDuty, Datadog, and CloudWatch. When an incident fires, correlates related alerts across services, queries logs and metrics to diagnose probable root cause, suggests runbook actions, and can auto-execute safe remediations (restart pods, scale up, toggle feature flags). Posts real-time updates to your incident Slack channel with a structured timeline.",
                publisher_id=publisher, publisher_name=publisher_name,
                category="engineering",
                tags=["incident", "on-call", "sre", "monitoring", "automation"],
                visibility="public", pricing="free",
                agent_config={
                    "model": "claude-opus-4-6",
                    "temperature": 0.1,
                    "system_prompt": "You are an SRE incident responder. When given alert data, 1) Correlate related alerts by service/time, 2) Query logs/metrics for the affected service, 3) Identify probable root cause, 4) Suggest remediation steps from the runbook, 5) Execute approved safe actions. Always post status updates to the incident channel.",
                    "tools": ["pagerduty_api", "datadog_query", "kubernetes_exec", "slack_post", "feature_flag_toggle"],
                    "max_tokens": 2000,
                },
                required_integrations=["pagerduty", "datadog", "slack"],
                required_capabilities=["reasoning", "tool_use"],
                version="2.0.0",
                is_verified=True, is_featured=True, is_active=True,
                install_count=0, rating_avg=0, rating_count=0,
                published_at=now - timedelta(days=60),
                created_at=now - timedelta(days=60),
            ),
            MarketplaceAgent(
                name="Content Repurposer",
                slug="content-repurposer",
                tagline="Transform long-form content into social posts, emails, ad copy, and thread variants",
                description="Takes a blog post, whitepaper, or video transcript and generates multiple derivative content pieces: LinkedIn posts (3 variants), Twitter/X threads, email newsletter snippets, ad copy (Google + Meta), and a short-form summary. Maintains brand voice through a configurable style guide. Includes A/B variant generation for headlines and CTAs.",
                publisher_id=publisher, publisher_name=publisher_name,
                category="marketing",
                tags=["content", "social-media", "copywriting", "repurposing", "brand"],
                visibility="public", pricing="free",
                agent_config={
                    "model": "claude-sonnet-4-5-20250929",
                    "temperature": 0.7,
                    "system_prompt": "You are a content marketing specialist. Given long-form content and a brand voice guide, generate: 1) 3 LinkedIn post variants (hook + body + CTA, each <300 words), 2) Twitter/X thread (5-8 tweets), 3) Email snippet (subject + preview + body, <150 words), 4) Google ad copy (3 headline + 2 description variants), 5) One-paragraph summary. Match the brand voice exactly.",
                    "tools": ["content_fetch", "brand_guide_lookup", "scheduler_post"],
                    "max_tokens": 4000,
                },
                required_integrations=[],
                required_capabilities=["creative_writing", "long_context"],
                version="1.5.0",
                is_verified=True, is_featured=True, is_active=True,
                install_count=0, rating_avg=0, rating_count=0,
                published_at=now - timedelta(days=100),
                created_at=now - timedelta(days=100),
            ),

            # ── Non-Featured Agents (6 more) ─────────────────────────────────
            MarketplaceAgent(
                name="Data Quality Monitor",
                slug="data-quality-monitor",
                tagline="Detect schema drift, null spikes, and volume anomalies in your data pipelines",
                description="Continuously monitors data pipeline health by profiling incoming datasets. Detects schema changes (new/removed/type-changed columns), data quality issues (null rate spikes, duplicate surges, value distribution shifts), and volume anomalies (unexpected drops or spikes vs. historical baseline). Sends alerts with root cause hypotheses and links to the relevant pipeline run.",
                publisher_id=publisher, publisher_name=publisher_name,
                category="data_processing",
                tags=["data-quality", "pipeline", "monitoring", "anomaly-detection", "dbt"],
                visibility="public", pricing="free",
                agent_config={
                    "model": "claude-sonnet-4-5-20250929",
                    "temperature": 0.1,
                    "system_prompt": "You are a data quality analyst. Given dataset profiling results (schema, null rates, row counts, distributions) and historical baselines, identify anomalies and classify them: schema_drift, null_spike, volume_anomaly, distribution_shift. For each, provide severity, affected columns, probable cause, and recommended action.",
                    "tools": ["db_profile", "baseline_lookup", "slack_alert", "jira_create"],
                    "max_tokens": 1500,
                },
                required_integrations=[],
                required_capabilities=["structured_output", "reasoning"],
                version="1.2.0",
                is_verified=True, is_featured=False, is_active=True,
                install_count=0, rating_avg=0, rating_count=0,
                published_at=now - timedelta(days=45),
                created_at=now - timedelta(days=45),
            ),
            MarketplaceAgent(
                name="Contract Analyzer",
                slug="contract-analyzer",
                tagline="Extract key terms, obligations, deadlines, and risk flags from contracts",
                description="Processes legal contracts (NDAs, MSAs, SOWs, vendor agreements) to extract structured data: parties, effective dates, term length, auto-renewal clauses, termination conditions, liability caps, IP ownership, data handling obligations, and SLA commitments. Flags deviations from your standard playbook and highlights unusual or risky clauses with specific recommendations.",
                publisher_id=publisher, publisher_name=publisher_name,
                category="legal",
                tags=["contracts", "legal", "compliance", "extraction", "risk"],
                visibility="public", pricing="free",
                agent_config={
                    "model": "claude-opus-4-6",
                    "temperature": 0.05,
                    "system_prompt": "You are a contract analysis specialist. Extract from the contract: 1) Parties and roles, 2) Key dates (effective, expiry, renewal), 3) Financial terms (fees, caps, penalties), 4) Obligations per party, 5) IP and data clauses, 6) Termination conditions, 7) Risk flags (deviations from standard terms, unusual clauses, missing protections). Output as structured JSON.",
                    "tools": ["document_parse", "playbook_compare", "risk_scorer"],
                    "max_tokens": 5000,
                },
                required_integrations=[],
                required_capabilities=["long_context", "reasoning", "structured_output"],
                version="1.0.0",
                is_verified=True, is_featured=False, is_active=True,
                install_count=0, rating_avg=0, rating_count=0,
                published_at=now - timedelta(days=30),
                created_at=now - timedelta(days=30),
            ),
            MarketplaceAgent(
                name="Churn Prediction Agent",
                slug="churn-prediction-agent",
                tagline="Identify at-risk accounts and suggest personalized retention actions",
                description="Analyzes customer usage patterns, support ticket history, NPS scores, and billing data to identify accounts likely to churn in the next 30/60/90 days. For each at-risk account, generates a risk score, contributing factors (declining usage, unresolved tickets, contract end approaching), and personalized retention recommendations (feature enablement, success call, pricing discussion).",
                publisher_id=publisher, publisher_name=publisher_name,
                category="analytics",
                tags=["churn", "retention", "customer-success", "prediction", "saas"],
                visibility="public", pricing="free",
                agent_config={
                    "model": "claude-sonnet-4-5-20250929",
                    "temperature": 0.2,
                    "system_prompt": "You are a customer success analyst specializing in churn prediction. Given account data (usage metrics, support history, billing, NPS), output: { risk_score: 0-100, churn_window: '30d'|'60d'|'90d', contributing_factors: [...], retention_actions: [...], priority: 'critical'|'high'|'medium'|'low' }",
                    "tools": ["crm_lookup", "usage_analytics", "slack_notify", "task_create"],
                    "max_tokens": 1000,
                },
                required_integrations=["salesforce"],
                required_capabilities=["structured_output", "reasoning"],
                version="1.3.0",
                is_verified=True, is_featured=False, is_active=True,
                install_count=0, rating_avg=0, rating_count=0,
                published_at=now - timedelta(days=55),
                created_at=now - timedelta(days=55),
            ),
            MarketplaceAgent(
                name="Invoice Processor",
                slug="invoice-processor",
                tagline="Extract line items from invoices, match against POs, and route for approval",
                description="Handles end-to-end invoice processing: OCR extraction of vendor, invoice number, dates, line items, taxes, and totals from PDF/image invoices. Matches against existing purchase orders and flags discrepancies (quantity mismatch, price variance, missing PO). Routes to the appropriate approver based on amount thresholds and department. Creates entries in your accounting system.",
                publisher_id=publisher, publisher_name=publisher_name,
                category="finance_accounting",
                tags=["invoices", "ap", "accounting", "ocr", "automation"],
                visibility="public", pricing="free",
                agent_config={
                    "model": "claude-sonnet-4-5-20250929",
                    "temperature": 0.05,
                    "system_prompt": "You are an accounts payable specialist. Extract from the invoice image/PDF: vendor_name, invoice_number, invoice_date, due_date, line_items (description, qty, unit_price, total), subtotal, tax, grand_total, payment_terms. Then match against the provided PO data and flag any discrepancies.",
                    "tools": ["ocr_extract", "po_lookup", "approval_route", "erp_create"],
                    "max_tokens": 2000,
                },
                required_integrations=[],
                required_capabilities=["vision", "structured_output"],
                version="1.1.0",
                is_verified=True, is_featured=False, is_active=True,
                install_count=0, rating_avg=0, rating_count=0,
                published_at=now - timedelta(days=40),
                created_at=now - timedelta(days=40),
            ),
            MarketplaceAgent(
                name="Candidate Screener",
                slug="candidate-screener",
                tagline="Screen resumes against job requirements and generate interview scorecards",
                description="Screens candidate resumes and applications against job descriptions. Evaluates skills match, experience relevance, education fit, and culture indicators. Generates a structured scorecard with pass/fail per requirement, an overall recommendation (strong yes, yes, maybe, no), suggested interview questions tailored to gaps, and talking points for the hiring manager. Handles bias-aware screening with configurable guardrails.",
                publisher_id=publisher, publisher_name=publisher_name,
                category="hr_recruiting",
                tags=["hiring", "resume", "screening", "hr", "interviews"],
                visibility="public", pricing="free",
                agent_config={
                    "model": "claude-sonnet-4-5-20250929",
                    "temperature": 0.3,
                    "system_prompt": "You are an unbiased recruiting assistant. Given a job description and candidate resume, evaluate: 1) Skills match (required vs. nice-to-have), 2) Experience relevance, 3) Education fit. Output a scorecard with per-requirement ratings, overall recommendation (strong_yes|yes|maybe|no), 3 tailored interview questions, and hiring manager talking points. Do NOT use name, age, gender, or ethnicity in scoring.",
                    "tools": ["ats_lookup", "calendar_schedule", "email_send"],
                    "max_tokens": 2000,
                },
                required_integrations=[],
                required_capabilities=["reasoning", "structured_output"],
                version="1.4.0",
                is_verified=True, is_featured=False, is_active=True,
                install_count=0, rating_avg=0, rating_count=0,
                published_at=now - timedelta(days=65),
                created_at=now - timedelta(days=65),
            ),
            MarketplaceAgent(
                name="Competitive Intel Tracker",
                slug="competitive-intel-tracker",
                tagline="Monitor competitor activity across web, social, and job boards — get weekly briefs",
                description="Tracks competitor movements by monitoring their websites (pricing changes, new features, blog posts), social media activity, job postings (hiring signals for new products), press releases, and app store updates. Generates weekly intelligence briefs with key changes, strategic implications, and suggested responses. Configurable competitor list and alert thresholds.",
                publisher_id=publisher, publisher_name=publisher_name,
                category="sales_automation",
                tags=["competitive-intel", "market-research", "sales", "strategy", "monitoring"],
                visibility="public", pricing="free",
                agent_config={
                    "model": "claude-sonnet-4-5-20250929",
                    "temperature": 0.4,
                    "system_prompt": "You are a competitive intelligence analyst. Given monitoring data (website changes, social posts, job listings, press mentions) for tracked competitors, produce a structured brief: ## Key Changes (what changed, when, significance), ## Hiring Signals (roles being hired, what it implies), ## Product Moves (new features, pricing changes), ## Strategic Implications, ## Recommended Actions for our team.",
                    "tools": ["web_scraper", "social_monitor", "job_board_api", "slack_post"],
                    "max_tokens": 3000,
                },
                required_integrations=["slack"],
                required_capabilities=["web_browsing", "summarization"],
                version="1.0.0",
                is_verified=True, is_featured=False, is_active=True,
                install_count=0, rating_avg=0, rating_count=0,
                published_at=now - timedelta(days=20),
                created_at=now - timedelta(days=20),
            ),
        ]

        for agent in agents:
            db.add(agent)

        await db.commit()
        print(f"   Seed: Created {len(agents)} marketplace agents ({sum(1 for a in agents if a.is_featured)} featured)")

    # Seed workflow templates into marketplace
    await _seed_workflow_templates()


async def _seed_workflow_templates():
    """Seed workflow templates into marketplace (item_type='workflow_template')."""
    from backend.shared.marketplace_models import MarketplaceAgent
    from sqlalchemy import select, func
    from datetime import datetime, timedelta

    async with AsyncSessionLocal() as db:
        # Check if any workflow templates exist already
        count_result = await db.execute(
            select(func.count(MarketplaceAgent.id)).where(
                MarketplaceAgent.item_type == 'workflow_template'
            )
        )
        if count_result.scalar() > 0:
            return  # Already seeded

        now = datetime.utcnow()
        publisher = "user-admin-001"
        publisher_name = "Orchestly"

        # Helper functions matching the seed.py format
        def trigger_node(nid, label, pos, trigger_type="webhook"):
            return {"id": nid, "type": "trigger", "position": pos, "data": {
                "label": label, "type": "trigger",
                "triggerConfig": {"triggerType": trigger_type},
            }}

        def worker_node(nid, label, pos, model="gpt-4o", prompt="", temperature=0.7):
            return {"id": nid, "type": "worker", "position": pos, "data": {
                "label": label, "type": "worker",
                "modelSelection": "specific", "llmModel": model,
                "systemPrompt": prompt, "temperature": temperature,
                "capabilities": ["processing"],
            }}

        def integration_node(nid, label, pos, integration_type, action, params=None):
            return {"id": nid, "type": "integration", "position": pos, "data": {
                "label": label, "type": "integration",
                "integrationConfig": {
                    "integrationType": integration_type, "action": action,
                    "parameters": params or {}, "isConnected": False,
                },
            }}

        def condition_node(nid, label, pos):
            return {"id": nid, "type": "condition", "position": pos, "data": {
                "label": label, "type": "condition",
                "conditionConfig": {"conditions": []},
            }}

        def print_node(nid, label, pos):
            return {"id": nid, "type": "print", "position": pos, "data": {
                "label": label, "type": "print",
            }}

        templates_data = [
            {
                "name": "Customer Onboarding Flow",
                "slug": "tpl-customer-onboarding-flow",
                "tagline": "Welcome new customers with personalized email, CRM update, and CSM notification",
                "description": "Automates the full customer onboarding experience: sends a personalized welcome email, updates CRM status, notifies the customer success manager on Slack, and schedules a 30-day check-in.",
                "category": "customer_service",
                "tags": ["onboarding", "customer-success", "email", "crm"],
                "nodes": [
                    trigger_node("trigger-1", "New Customer Signed Up", {"x": 100, "y": 250}, "webhook"),
                    worker_node("personalize-1", "Generate Welcome Email", {"x": 350, "y": 250}, "gpt-4o",
                                "Write a warm, personalized welcome email for a new customer.\n\nCustomer info: {{trigger-1.text}}\n\nInclude: their name, company, plan tier, 3 quick-start tips, and a link to book an onboarding call. Keep it under 200 words.", 0.7),
                    integration_node("email-1", "Send Welcome Email", {"x": 600, "y": 150}, "mailchimp", "send_campaign",
                                     {"subject": "Welcome to Orchestly!", "body": "{{personalize-1.text}}"}),
                    integration_node("crm-1", "Update CRM Status", {"x": 600, "y": 350}, "salesforce", "create_lead",
                                     {"status": "Onboarding", "notes": "Welcome email sent"}),
                    integration_node("slack-1", "Notify CSM", {"x": 850, "y": 150}, "slack", "send_message",
                                     {"channel": "#customer-success", "message": "New customer onboarded: {{trigger-1.text}}"}),
                    worker_node("checkin-1", "Schedule 30-Day Check-in", {"x": 850, "y": 350}, "gpt-4o-mini",
                                "Generate a 30-day check-in reminder task with customer name, key metrics to review, and suggested talking points.\n\nCustomer: {{trigger-1.text}}", 0.5),
                    print_node("done-1", "Complete", {"x": 1100, "y": 250}),
                ],
                "edges": [
                    {"id": "e1", "source": "trigger-1", "target": "personalize-1"},
                    {"id": "e2", "source": "personalize-1", "target": "email-1"},
                    {"id": "e3", "source": "personalize-1", "target": "crm-1"},
                    {"id": "e4", "source": "email-1", "target": "slack-1"},
                    {"id": "e5", "source": "crm-1", "target": "checkin-1"},
                    {"id": "e6", "source": "slack-1", "target": "done-1"},
                    {"id": "e7", "source": "checkin-1", "target": "done-1"},
                ],
                "trigger_type": "webhook",
            },
            {
                "name": "Churn Risk Alert",
                "slug": "tpl-churn-risk-alert",
                "tagline": "Monitor usage metrics, detect churn risk, and alert CSMs with retention plans",
                "description": "Monitors customer usage metrics weekly, runs AI churn analysis, alerts the CSM team with retention recommendations, and creates Jira tickets for follow-up actions on at-risk accounts.",
                "category": "analytics",
                "tags": ["churn", "retention", "customer-success", "analytics"],
                "nodes": [
                    trigger_node("trigger-1", "Weekly Usage Report", {"x": 100, "y": 250}, "cron"),
                    integration_node("fetch-usage", "Fetch Usage Metrics", {"x": 350, "y": 250}, "salesforce", "create_lead",
                                     {"query": "usage_metrics_last_30d"}),
                    worker_node("analyze-1", "Churn Risk Analysis", {"x": 600, "y": 250}, "claude-3-5-sonnet",
                                "Analyze these customer usage metrics for churn risk. For each at-risk account provide:\n1. Risk score (0-100)\n2. Contributing factors\n3. Recommended retention action\n\nMetrics: {{fetch-usage.text}}", 0.2),
                    condition_node("condition-1", "High Risk Detected?", {"x": 850, "y": 250}),
                    integration_node("slack-1", "Alert CSM Team", {"x": 1100, "y": 150}, "slack", "send_message",
                                     {"channel": "#churn-alerts", "message": "CHURN RISK DETECTED:\n{{analyze-1.text}}"}),
                    integration_node("jira-1", "Create Retention Ticket", {"x": 1100, "y": 350}, "jira", "create_ticket",
                                     {"project": "CS", "summary": "Churn risk: {{analyze-1.text}}", "priority": "High"}),
                    print_node("done-1", "Complete", {"x": 1350, "y": 250}),
                ],
                "edges": [
                    {"id": "e1", "source": "trigger-1", "target": "fetch-usage"},
                    {"id": "e2", "source": "fetch-usage", "target": "analyze-1"},
                    {"id": "e3", "source": "analyze-1", "target": "condition-1"},
                    {"id": "e4", "source": "condition-1", "target": "slack-1", "label": "High Risk"},
                    {"id": "e5", "source": "condition-1", "target": "done-1", "label": "Low Risk"},
                    {"id": "e6", "source": "slack-1", "target": "jira-1"},
                    {"id": "e7", "source": "jira-1", "target": "done-1"},
                ],
                "trigger_type": "schedule",
            },
            {
                "name": "NPS Survey Processor",
                "slug": "tpl-nps-survey-processor",
                "tagline": "Collect NPS feedback, analyze sentiment, and route detractors to support",
                "description": "Processes NPS survey responses with AI sentiment analysis. Routes detractors to support for immediate follow-up, updates CRM sentiment scores, and aggregates weekly insights.",
                "category": "customer_service",
                "tags": ["nps", "feedback", "sentiment", "customer-experience"],
                "nodes": [
                    trigger_node("trigger-1", "NPS Response Received", {"x": 100, "y": 250}, "webhook"),
                    worker_node("sentiment-1", "Sentiment Analysis", {"x": 350, "y": 250}, "gpt-4o-mini",
                                "Analyze this NPS survey response. Extract:\n1. NPS score (0-10)\n2. Sentiment (positive/neutral/negative)\n3. Key themes mentioned\n4. Urgency level\n5. Suggested follow-up action\n\nResponse: {{trigger-1.text}}", 0.2),
                    condition_node("condition-1", "Detractor?", {"x": 600, "y": 250}),
                    integration_node("zendesk-1", "Create Support Ticket", {"x": 850, "y": 100}, "zendesk", "create_ticket",
                                     {"subject": "NPS Detractor Follow-up", "description": "{{sentiment-1.text}}", "priority": "high"}),
                    integration_node("slack-1", "Alert Support Lead", {"x": 1100, "y": 100}, "slack", "send_message",
                                     {"channel": "#nps-detractors", "message": "Detractor alert! Score: {{sentiment-1.text}}"}),
                    integration_node("crm-1", "Update CRM Sentiment", {"x": 850, "y": 400}, "salesforce", "create_lead",
                                     {"nps_score": "{{sentiment-1.text}}", "sentiment": "positive"}),
                    print_node("done-1", "Complete", {"x": 1350, "y": 250}),
                ],
                "edges": [
                    {"id": "e1", "source": "trigger-1", "target": "sentiment-1"},
                    {"id": "e2", "source": "sentiment-1", "target": "condition-1"},
                    {"id": "e3", "source": "condition-1", "target": "zendesk-1", "label": "Score < 7"},
                    {"id": "e4", "source": "condition-1", "target": "crm-1", "label": "Score >= 7"},
                    {"id": "e5", "source": "zendesk-1", "target": "slack-1"},
                    {"id": "e6", "source": "slack-1", "target": "done-1"},
                    {"id": "e7", "source": "crm-1", "target": "done-1"},
                ],
                "trigger_type": "webhook",
            },
            {
                "name": "CI/CD Quality Gate",
                "slug": "tpl-cicd-quality-gate",
                "tagline": "AI code review + security scan on every PR, with auto-approve or block",
                "description": "When a PR is created, runs AI code review for bugs and quality issues, security vulnerability scanning, and auto-approves or blocks the merge based on findings.",
                "category": "engineering",
                "tags": ["ci-cd", "code-review", "security", "github", "quality"],
                "nodes": [
                    trigger_node("trigger-1", "PR Created", {"x": 100, "y": 250}, "webhook"),
                    integration_node("gh-diff", "Fetch PR Diff", {"x": 350, "y": 250}, "github", "create_issue",
                                     {"action": "get_diff"}),
                    worker_node("review-1", "AI Code Review", {"x": 600, "y": 100}, "claude-3-5-sonnet",
                                "Review this PR diff thoroughly for bugs, code quality, performance, and test coverage gaps.\n\nDiff: {{gh-diff.text}}", 0.2),
                    worker_node("security-1", "Security Scan", {"x": 600, "y": 400}, "gpt-4",
                                "Scan this code diff for security vulnerabilities (OWASP Top 10).\n\nDiff: {{gh-diff.text}}", 0.1),
                    worker_node("verdict-1", "Merge Verdict", {"x": 850, "y": 250}, "gpt-4o-mini",
                                "Based on the code review and security scan, decide: APPROVE or REQUEST_CHANGES.\n\nCode Review: {{review-1.text}}\nSecurity Scan: {{security-1.text}}", 0.2),
                    condition_node("condition-1", "Approve or Block?", {"x": 1100, "y": 250}),
                    integration_node("gh-approve", "Approve PR", {"x": 1350, "y": 150}, "github", "create_issue",
                                     {"action": "approve", "comment": "{{verdict-1.text}}"}),
                    integration_node("gh-block", "Request Changes", {"x": 1350, "y": 350}, "github", "create_issue",
                                     {"action": "request_changes", "comment": "{{verdict-1.text}}"}),
                    print_node("done-1", "Complete", {"x": 1600, "y": 250}),
                ],
                "edges": [
                    {"id": "e1", "source": "trigger-1", "target": "gh-diff"},
                    {"id": "e2", "source": "gh-diff", "target": "review-1"},
                    {"id": "e3", "source": "gh-diff", "target": "security-1"},
                    {"id": "e4", "source": "review-1", "target": "verdict-1"},
                    {"id": "e5", "source": "security-1", "target": "verdict-1"},
                    {"id": "e6", "source": "verdict-1", "target": "condition-1"},
                    {"id": "e7", "source": "condition-1", "target": "gh-approve", "label": "Approve"},
                    {"id": "e8", "source": "condition-1", "target": "gh-block", "label": "Block"},
                    {"id": "e9", "source": "gh-approve", "target": "done-1"},
                    {"id": "e10", "source": "gh-block", "target": "done-1"},
                ],
                "trigger_type": "webhook",
            },
            {
                "name": "Incident Post-Mortem Generator",
                "slug": "tpl-incident-postmortem",
                "tagline": "Auto-generate post-mortem docs from PagerDuty timeline and error logs",
                "description": "After an incident resolves, gathers PagerDuty timeline and error logs, generates a structured AI post-mortem document with root cause analysis and action items, and shares it with the team.",
                "category": "engineering",
                "tags": ["incident", "post-mortem", "sre", "documentation"],
                "nodes": [
                    trigger_node("trigger-1", "Incident Resolved", {"x": 100, "y": 250}, "webhook"),
                    integration_node("pd-timeline", "Fetch PagerDuty Timeline", {"x": 350, "y": 150}, "jira", "create_ticket",
                                     {"action": "get_incident_timeline"}),
                    integration_node("logs-1", "Fetch Error Logs", {"x": 350, "y": 350}, "slack", "send_message",
                                     {"action": "search_logs"}),
                    worker_node("postmortem-1", "Generate Post-Mortem", {"x": 650, "y": 250}, "claude-3-5-sonnet",
                                "Write a structured incident post-mortem.\n\nPagerDuty Timeline: {{pd-timeline.text}}\nError Logs: {{logs-1.text}}\n\nSections: Executive Summary, Impact, Timeline, Root Cause (5 Whys), What Went Well/Wrong, Action Items, Lessons Learned.", 0.3),
                    worker_node("actions-1", "Extract Action Items", {"x": 900, "y": 150}, "gpt-4o-mini",
                                "Extract action items from this post-mortem as structured JSON.\n\nPost-mortem: {{postmortem-1.text}}", 0.2),
                    integration_node("jira-actions", "Create Jira Tickets", {"x": 1150, "y": 150}, "jira", "create_ticket",
                                     {"project": "SRE", "summary": "Post-mortem action: {{actions-1.text}}"}),
                    integration_node("slack-1", "Share Post-Mortem", {"x": 900, "y": 350}, "slack", "send_message",
                                     {"channel": "#incidents", "message": "Post-mortem published:\n{{postmortem-1.text}}"}),
                    print_node("done-1", "Complete", {"x": 1350, "y": 250}),
                ],
                "edges": [
                    {"id": "e1", "source": "trigger-1", "target": "pd-timeline"},
                    {"id": "e2", "source": "trigger-1", "target": "logs-1"},
                    {"id": "e3", "source": "pd-timeline", "target": "postmortem-1"},
                    {"id": "e4", "source": "logs-1", "target": "postmortem-1"},
                    {"id": "e5", "source": "postmortem-1", "target": "actions-1"},
                    {"id": "e6", "source": "postmortem-1", "target": "slack-1"},
                    {"id": "e7", "source": "actions-1", "target": "jira-actions"},
                    {"id": "e8", "source": "jira-actions", "target": "done-1"},
                    {"id": "e9", "source": "slack-1", "target": "done-1"},
                ],
                "trigger_type": "webhook",
            },
            {
                "name": "Dependency Update Bot",
                "slug": "tpl-dependency-update-bot",
                "tagline": "Weekly dependency scan, AI risk assessment, and auto-PRs for safe updates",
                "description": "Runs weekly scans for outdated packages, assesses update risk with AI, creates auto-merge PRs for low-risk patches, and flags high-risk updates for manual review.",
                "category": "engineering",
                "tags": ["dependencies", "security", "github", "automation"],
                "nodes": [
                    trigger_node("trigger-1", "Weekly Monday 6 AM", {"x": 100, "y": 250}, "cron"),
                    integration_node("gh-deps", "Check Outdated Deps", {"x": 350, "y": 250}, "github", "create_issue",
                                     {"action": "list_outdated_dependencies"}),
                    worker_node("assess-1", "Risk Assessment", {"x": 600, "y": 250}, "claude-3-5-sonnet",
                                "Assess the risk of updating these dependencies. For each: risk level, security advisories, recommendation.\n\nDependencies: {{gh-deps.text}}", 0.2),
                    condition_node("condition-1", "Safe to Auto-Update?", {"x": 850, "y": 250}),
                    integration_node("gh-pr-auto", "Create Auto-Merge PR", {"x": 1100, "y": 100}, "github", "create_issue",
                                     {"action": "create_pr", "title": "chore(deps): auto-update safe dependencies", "auto_merge": True}),
                    integration_node("gh-pr-review", "Create Review PR", {"x": 1100, "y": 400}, "github", "create_issue",
                                     {"action": "create_pr", "title": "chore(deps): update dependencies (needs review)", "auto_merge": False}),
                    integration_node("slack-1", "Notify Engineering", {"x": 1350, "y": 250}, "slack", "send_message",
                                     {"channel": "#engineering", "message": "Dependency update scan complete:\n{{assess-1.text}}"}),
                    print_node("done-1", "Complete", {"x": 1600, "y": 250}),
                ],
                "edges": [
                    {"id": "e1", "source": "trigger-1", "target": "gh-deps"},
                    {"id": "e2", "source": "gh-deps", "target": "assess-1"},
                    {"id": "e3", "source": "assess-1", "target": "condition-1"},
                    {"id": "e4", "source": "condition-1", "target": "gh-pr-auto", "label": "Low Risk"},
                    {"id": "e5", "source": "condition-1", "target": "gh-pr-review", "label": "Needs Review"},
                    {"id": "e6", "source": "gh-pr-auto", "target": "slack-1"},
                    {"id": "e7", "source": "gh-pr-review", "target": "slack-1"},
                    {"id": "e8", "source": "slack-1", "target": "done-1"},
                ],
                "trigger_type": "schedule",
            },
            {
                "name": "Outbound Email Sequence",
                "slug": "tpl-outbound-email-sequence",
                "tagline": "Enrich leads, generate personalized email sequences, and track engagement",
                "description": "When a new lead is assigned, enriches data from CRM, researches the company, generates a personalized 3-touch email sequence with AI, schedules sends, and logs activity.",
                "category": "sales_automation",
                "tags": ["outbound", "email", "sales", "personalization"],
                "nodes": [
                    trigger_node("trigger-1", "New Lead Assigned", {"x": 100, "y": 250}, "webhook"),
                    integration_node("enrich-1", "Enrich Lead Data", {"x": 350, "y": 250}, "salesforce", "create_lead",
                                     {"action": "get_lead_details"}),
                    worker_node("research-1", "Company Research", {"x": 600, "y": 150}, "gpt-4",
                                "Research this company for sales outreach talking points.\n\nLead data: {{enrich-1.text}}", 0.5),
                    worker_node("sequence-1", "Generate Email Sequence", {"x": 600, "y": 350}, "claude-3-5-sonnet",
                                "Write a 3-email outbound sequence for this prospect using the research.\n\nLead: {{enrich-1.text}}\nResearch: {{research-1.text}}", 0.7),
                    integration_node("mail-1", "Schedule Email 1", {"x": 900, "y": 150}, "mailchimp", "send_campaign",
                                     {"subject": "{{sequence-1.text}}", "send_at": "immediate"}),
                    integration_node("crm-update", "Update CRM Pipeline", {"x": 900, "y": 350}, "salesforce", "create_lead",
                                     {"status": "Outbound Sequence Active"}),
                    integration_node("slack-1", "Log to Sales Channel", {"x": 1150, "y": 250}, "slack", "send_message",
                                     {"channel": "#outbound-log", "message": "Outbound sequence started for {{enrich-1.text}}"}),
                    print_node("done-1", "Complete", {"x": 1400, "y": 250}),
                ],
                "edges": [
                    {"id": "e1", "source": "trigger-1", "target": "enrich-1"},
                    {"id": "e2", "source": "enrich-1", "target": "research-1"},
                    {"id": "e3", "source": "enrich-1", "target": "sequence-1"},
                    {"id": "e4", "source": "research-1", "target": "sequence-1"},
                    {"id": "e5", "source": "sequence-1", "target": "mail-1"},
                    {"id": "e6", "source": "sequence-1", "target": "crm-update"},
                    {"id": "e7", "source": "mail-1", "target": "slack-1"},
                    {"id": "e8", "source": "crm-update", "target": "slack-1"},
                    {"id": "e9", "source": "slack-1", "target": "done-1"},
                ],
                "trigger_type": "webhook",
            },
            {
                "name": "Competitor Pricing Monitor",
                "slug": "tpl-competitor-pricing-monitor",
                "tagline": "Daily competitor pricing analysis with AI-powered battlecard updates",
                "description": "Runs daily analysis of competitor pricing data, detects changes with AI diff analysis, alerts the sales team, and automatically updates competitive battlecards.",
                "category": "sales_automation",
                "tags": ["competitive-intel", "pricing", "sales", "monitoring"],
                "nodes": [
                    trigger_node("trigger-1", "Daily 8 AM Scan", {"x": 100, "y": 250}, "cron"),
                    worker_node("scrape-1", "Analyze Competitor Pages", {"x": 350, "y": 250}, "gpt-4",
                                "Compare current competitor pricing data against yesterday's snapshot. Identify price changes, new plans, feature changes, promotions.\n\nCompetitor data: {{trigger-1.text}}", 0.2),
                    condition_node("condition-1", "Changes Detected?", {"x": 600, "y": 250}),
                    integration_node("slack-alert", "Alert Sales Team", {"x": 850, "y": 100}, "slack", "send_message",
                                     {"channel": "#competitive-intel", "message": "COMPETITOR PRICING CHANGE:\n{{scrape-1.text}}"}),
                    worker_node("battlecard-1", "Update Battlecard", {"x": 850, "y": 350}, "claude-3-5-sonnet",
                                "Update our competitive battlecard based on these pricing changes.\n\nChanges: {{scrape-1.text}}", 0.4),
                    integration_node("slack-battlecard", "Share Updated Battlecard", {"x": 1100, "y": 350}, "slack", "send_message",
                                     {"channel": "#sales-enablement", "message": "Updated battlecard:\n{{battlecard-1.text}}"}),
                    print_node("done-1", "Complete", {"x": 1350, "y": 250}),
                ],
                "edges": [
                    {"id": "e1", "source": "trigger-1", "target": "scrape-1"},
                    {"id": "e2", "source": "scrape-1", "target": "condition-1"},
                    {"id": "e3", "source": "condition-1", "target": "slack-alert", "label": "Changes Found"},
                    {"id": "e4", "source": "condition-1", "target": "done-1", "label": "No Changes"},
                    {"id": "e5", "source": "slack-alert", "target": "battlecard-1"},
                    {"id": "e6", "source": "battlecard-1", "target": "slack-battlecard"},
                    {"id": "e7", "source": "slack-battlecard", "target": "done-1"},
                ],
                "trigger_type": "schedule",
            },
            {
                "name": "Invoice Approval Workflow",
                "slug": "tpl-invoice-approval-workflow",
                "tagline": "Extract invoice data, match POs, route approvals by amount threshold",
                "description": "Extracts invoice data via AI, matches against purchase orders, routes for approval based on amount thresholds ($1K+), and posts to accounting for processing.",
                "category": "finance_accounting",
                "tags": ["finance", "invoices", "approval", "accounting", "ocr"],
                "nodes": [
                    trigger_node("trigger-1", "Invoice Received", {"x": 100, "y": 250}, "webhook"),
                    worker_node("ocr-1", "Extract Invoice Data", {"x": 350, "y": 250}, "gpt-4",
                                "Extract structured data from this invoice: vendor, invoice number, dates, line items, totals, PO number.\n\nInvoice: {{trigger-1.text}}", 0.1),
                    worker_node("match-1", "PO Match & Validation", {"x": 600, "y": 250}, "gpt-4o-mini",
                                "Validate this invoice against purchase order records.\n\nInvoice data: {{ocr-1.text}}", 0.2),
                    condition_node("condition-1", "Amount Threshold", {"x": 850, "y": 250}),
                    integration_node("slack-mgr", "Manager Approval ($1K+)", {"x": 1100, "y": 100}, "slack", "send_message",
                                     {"channel": "#finance-approvals", "message": "Invoice requires approval:\n{{ocr-1.text}}"}),
                    integration_node("auto-approve", "Auto-Approve (< $1K)", {"x": 1100, "y": 400}, "stripe", "create_payment",
                                     {"vendor": "{{ocr-1.text}}", "status": "approved"}),
                    integration_node("slack-finance", "Notify Finance", {"x": 1350, "y": 250}, "slack", "send_message",
                                     {"channel": "#accounts-payable", "message": "Invoice processed: {{ocr-1.text}}"}),
                    print_node("done-1", "Complete", {"x": 1600, "y": 250}),
                ],
                "edges": [
                    {"id": "e1", "source": "trigger-1", "target": "ocr-1"},
                    {"id": "e2", "source": "ocr-1", "target": "match-1"},
                    {"id": "e3", "source": "match-1", "target": "condition-1"},
                    {"id": "e4", "source": "condition-1", "target": "slack-mgr", "label": ">= $1,000"},
                    {"id": "e5", "source": "condition-1", "target": "auto-approve", "label": "< $1,000"},
                    {"id": "e6", "source": "slack-mgr", "target": "slack-finance"},
                    {"id": "e7", "source": "auto-approve", "target": "slack-finance"},
                    {"id": "e8", "source": "slack-finance", "target": "done-1"},
                ],
                "trigger_type": "webhook",
            },
            {
                "name": "Employee Offboarding",
                "slug": "tpl-employee-offboarding",
                "tagline": "Automated offboarding: revoke access, backup data, compliance checklist",
                "description": "Automates the full offboarding process: generates a comprehensive checklist, notifies IT and HR teams, creates Jira tickets for access revocation, runs compliance verification, and sends an exit summary.",
                "category": "hr_recruiting",
                "tags": ["hr", "offboarding", "security", "compliance", "automation"],
                "nodes": [
                    trigger_node("trigger-1", "Offboarding Request", {"x": 100, "y": 300}, "manual"),
                    worker_node("plan-1", "Generate Offboarding Plan", {"x": 350, "y": 300}, "claude-3-5-sonnet",
                                "Generate a comprehensive employee offboarding checklist.\n\nEmployee info: {{trigger-1.text}}\n\nInclude: systems access, data backup, equipment, knowledge transfer, exit interview, payroll, benefits, NDA reminder.", 0.3),
                    integration_node("slack-it", "Notify IT Team", {"x": 600, "y": 100}, "slack", "send_message",
                                     {"channel": "#it-operations", "message": "OFFBOARDING: Revoke access.\n\n{{plan-1.text}}"}),
                    integration_node("slack-hr", "Notify HR Team", {"x": 600, "y": 300}, "slack", "send_message",
                                     {"channel": "#hr-operations", "message": "OFFBOARDING: Exit interview needed.\n\n{{plan-1.text}}"}),
                    integration_node("jira-1", "Create IT Tickets", {"x": 600, "y": 500}, "jira", "create_ticket",
                                     {"project": "IT", "summary": "Offboarding: Revoke access for {{trigger-1.text}}"}),
                    worker_node("compliance-1", "Compliance Verification", {"x": 900, "y": 300}, "gpt-4o-mini",
                                "Generate compliance verification checklist for this offboarding.\n\nEmployee: {{trigger-1.text}}\nPlan: {{plan-1.text}}", 0.2),
                    integration_node("email-1", "Send Exit Summary", {"x": 1150, "y": 300}, "mailchimp", "send_campaign",
                                     {"subject": "Offboarding Summary & Next Steps", "body": "{{compliance-1.text}}"}),
                    print_node("done-1", "Complete", {"x": 1400, "y": 300}),
                ],
                "edges": [
                    {"id": "e1", "source": "trigger-1", "target": "plan-1"},
                    {"id": "e2", "source": "plan-1", "target": "slack-it"},
                    {"id": "e3", "source": "plan-1", "target": "slack-hr"},
                    {"id": "e4", "source": "plan-1", "target": "jira-1"},
                    {"id": "e5", "source": "slack-it", "target": "compliance-1"},
                    {"id": "e6", "source": "slack-hr", "target": "compliance-1"},
                    {"id": "e7", "source": "jira-1", "target": "compliance-1"},
                    {"id": "e8", "source": "compliance-1", "target": "email-1"},
                    {"id": "e9", "source": "email-1", "target": "done-1"},
                ],
                "trigger_type": "manual",
            },
        ]

        template_agents = []
        for tpl in templates_data:
            agent_config = {
                "nodes": tpl["nodes"],
                "edges": tpl["edges"],
                "trigger_type": tpl["trigger_type"],
                "node_count": len(tpl["nodes"]),
            }
            template_agents.append(MarketplaceAgent(
                name=tpl["name"],
                slug=tpl["slug"],
                tagline=tpl["tagline"],
                description=tpl["description"],
                item_type="workflow_template",
                publisher_id=publisher,
                publisher_name=publisher_name,
                category=tpl["category"],
                tags=tpl["tags"],
                visibility="public",
                pricing="free",
                agent_config=agent_config,
                required_integrations=[],
                required_capabilities=[],
                version="1.0.0",
                is_verified=True,
                is_featured=True,
                is_active=True,
                install_count=0,
                rating_avg=0,
                rating_count=0,
                published_at=now - timedelta(days=30),
                created_at=now - timedelta(days=30),
            ))

        for agent in template_agents:
            db.add(agent)

        await db.commit()
        print(f"   Seed: Created {len(template_agents)} marketplace workflow templates")


async def _seed_integrations():
    """Seed integrations registry if table is empty."""
    from backend.shared.integration_models import IntegrationModel
    from sqlalchemy import select, func

    async with AsyncSessionLocal() as db:
        count_result = await db.execute(
            select(func.count(IntegrationModel.integration_id))
        )
        if count_result.scalar() > 0:
            return  # Already seeded

        # Reuse the seed endpoint logic
        from backend.api.seed import seed_integrations as _do_seed
        try:
            result = await _do_seed(db=db)
            print(f"   Seed: Created {result['created_count']} integrations")
        except Exception as e:
            print(f"   Seed: Integration seeding failed - {e}")


# Lifespan context manager for startup/shutdown
@asynccontextmanager
async def lifespan(app: FastAPI):
    """Initialize services on startup, cleanup on shutdown."""
    global _scheduler_task, _scheduler_runner
    print("🚀 Starting Agent Orchestration Platform...")

    # Database mode info
    import os
    if os.environ.get("USE_SQLITE", "").lower() in ("true", "1", "yes"):
        print("   Database: SQLite (local dev mode - using mock data for DB features)")
    else:
        print("   Database: PostgreSQL")

    # Initialize services
    settings = get_settings()
    registry = get_registry()
    router = get_router()
    # Initialize task queue with eager Redis verification
    try:
        queue = get_queue()
        # Eagerly verify Redis is reachable (async ping)
        if hasattr(queue, 'redis'):
            await queue.redis.ping()
            print("   Queue: Redis-backed (connected)")
    except Exception as e:
        print(f"   Queue: Redis unavailable ({e}), switching to in-memory fallback")
        from backend.orchestrator.memory_queue import InMemoryTaskQueue
        queue = InMemoryTaskQueue()
        set_queue(queue)

    # Initialize gateway, collector, alert_manager (if available)
    if get_gateway is not None:
        gateway = get_gateway()
    else:
        gateway = None
        print("   Gateway: Skipped (core.llm not available)")

    collector = get_collector()
    alert_manager = get_alert_manager()

    # Initialize all database tables
    # NOTE: In SQLite mode, session.py registers type adapters so PostgreSQL-
    # specific types (ARRAY, JSONB, INET, UUID) compile to SQLite equivalents.
    # Ensure core models are imported so Base.metadata knows about their tables.
    import backend.database.models  # noqa: F401 — registers AgentModel, TaskModel, etc.
    from backend.database.session import init_db
    await init_db()
    print("   Database: Tables initialized")

    # Inline migrations for columns added after initial schema
    from sqlalchemy import text as _text
    _migrations = [
        ("users", "role", "ALTER TABLE users ADD COLUMN role VARCHAR(50) DEFAULT 'user' NOT NULL"),
        ("marketplace_agents", "item_type", "ALTER TABLE marketplace_agents ADD COLUMN item_type VARCHAR(50) DEFAULT 'agent' NOT NULL"),
    ]
    for _tbl, _col, _sql in _migrations:
        try:
            async with AsyncSessionLocal() as _mig_db:
                try:
                    await _mig_db.execute(_text(f"SELECT {_col} FROM {_tbl} LIMIT 1"))
                except Exception:
                    await _mig_db.rollback()
                    await _mig_db.execute(_text(_sql))
                    await _mig_db.commit()
                    print(f"   Migration: Added {_col} column to {_tbl}")
        except Exception as mig_err:
            print(f"   Migration: {_tbl}.{_col} check skipped ({mig_err})")

    # Seed default organization and admin user
    from backend.shared.rbac_models import UserModel, OrganizationModel
    from backend.shared.auth import hash_password as _hash_password
    from sqlalchemy import select as _select
    async with AsyncSessionLocal() as seed_db:
        # Ensure "default" organization exists
        org_result = await seed_db.execute(
            _select(OrganizationModel).where(OrganizationModel.organization_id == "default")
        )
        if not org_result.scalar_one_or_none():
            seed_db.add(OrganizationModel(
                organization_id="default",
                name="Default Organization",
                slug="default",
                plan="community",
                max_users=1,
                max_agents=5,
                enabled_features=[],
                is_active=True,
            ))
            print("   Seed: Created 'default' organization")

        # Ensure admin user exists with a password_hash
        admin_result = await seed_db.execute(
            _select(UserModel).where(UserModel.email == "admin@example.com")
        )
        existing_admin = admin_result.scalar_one_or_none()
        if not existing_admin:
            from datetime import datetime as _dt
            # Read password from env var or generate a random one
            _admin_password = os.environ.get("ADMIN_PASSWORD", "")
            if not _admin_password:
                _admin_password = secrets.token_urlsafe(16)
                print(f"   Seed: Generated admin password: {_admin_password}")
                print("   Seed: Set ADMIN_PASSWORD env var to use a fixed password.")
            seed_db.add(UserModel(
                user_id="user-admin-001",
                email="admin@example.com",
                full_name="Admin User",
                password_hash=_hash_password(_admin_password),
                role="admin",
                organization_id="default",
                is_active=True,
                is_email_verified=True,
                created_at=_dt.utcnow(),
                updated_at=_dt.utcnow(),
            ))
            print("   Seed: Created admin user (admin@example.com)")
        else:
            # Sync password if ADMIN_PASSWORD env var is explicitly set
            _admin_password = os.environ.get("ADMIN_PASSWORD", "")
            if _admin_password:
                existing_admin.password_hash = _hash_password(_admin_password)
                print("   Seed: Synced admin password from ADMIN_PASSWORD env var")

        await seed_db.commit()

    # Seed marketplace agents if table is empty
    await _seed_marketplace_agents()
    # Seed workflow templates independently (in case agents existed but templates didn't)
    await _seed_workflow_templates()
    # Seed integrations if table is empty
    await _seed_integrations()

    # Initialize audit logger
    audit_logger = init_audit_logger(AsyncSessionLocal)
    print("   Audit Logger: Initialized")

    # Initialize and start scheduler runner (if extended routers enabled)
    if os.environ.get("ENABLE_EXTENDED_ROUTERS", "").lower() in ("true", "1", "yes"):
        try:
            from backend.shared.scheduler_service import SchedulerRunner
            from backend.services.workflow_executor import WorkflowExecutor

            # Create workflow executor for scheduler
            workflow_executor = WorkflowExecutor()

            # Create scheduler runner with session factory
            _scheduler_runner = SchedulerRunner(
                db_session_factory=AsyncSessionLocal,
                workflow_executor=workflow_executor
            )

            # Start scheduler as background task
            _scheduler_task = asyncio.create_task(_scheduler_runner.start())
            print("   Scheduler Runner: Started (polling every 10s)")
        except Exception as e:
            print(f"   Scheduler Runner: Failed to start - {e}")
    else:
        print("   Scheduler Runner: Disabled (ENABLE_EXTENDED_ROUTERS not set)")

    # Register debug customer for development (BYOK billing → bring your own keys)
    try:
        billing_service = get_llm_billing_service()
        from backend.services.llm_billing_service import BillingModel
        from decimal import Decimal
        existing = await billing_service.get_customer_config("debug")
        if not existing:
            await billing_service.create_customer_config(
                customer_id="debug",
                billing_model=BillingModel.BYOK,
                daily_limit_usd=Decimal("100.00"),
            )
            print("   Debug customer: Registered (BYOK billing, bring your own keys)")
        else:
            # Update existing config to BYOK if it was managed
            if existing.billing_model != BillingModel.BYOK:
                existing.billing_model = BillingModel.BYOK
                print("   Debug customer: Updated to BYOK billing")
            else:
                print("   Debug customer: Already registered (BYOK)")
    except Exception as e:
        print(f"   Debug customer: Registration failed - {e}")

    print(f"   API: http://{settings.API_HOST}:{settings.API_PORT}")
    print(f"   Environment: {settings.ENVIRONMENT}")
    print(f"   Debug: {settings.DEBUG}")
    print("✅ Platform ready\n")

    yield

    # Cleanup
    print("\n🛑 Shutting down...")

    # Stop scheduler runner if running
    if _scheduler_runner is not None:
        await _scheduler_runner.stop()
        print("   Scheduler Runner: Stopped")
    if _scheduler_task is not None:
        _scheduler_task.cancel()
        try:
            await _scheduler_task
        except asyncio.CancelledError:
            pass

    await queue.close()
    print("✅ Shutdown complete")


# Create FastAPI app
app = FastAPI(
    title="Orchestly API",
    description="""
**AI-native agent orchestration platform**

Orchestly provides enterprise-ready infrastructure for deploying and managing
autonomous AI agent teams at scale.

## Core Features

- **Agent Management** — Register, monitor, and coordinate AI agents
- **Workflow Engine** — Visual drag-and-drop workflow builder with agent, integration, and logic nodes
- **LLM Gateway** — Multi-provider routing (OpenAI, Anthropic, Google, Groq, Mistral) with BYOK support
- **Task Queue** — Priority-based task routing with capability matching
- **Integrations** — Connect to Slack, GitHub, Salesforce, Stripe, and more via OAuth or API keys
- **Cost Tracking** — Per-agent token usage tracking with budget enforcement
- **A/B Testing** — Statistical experiment framework for agent/model comparison
- **HITL Approvals** — Human-in-the-loop approval workflows for critical actions
- **Prompt Registry** — Versioned prompt template management
- **Observability** — Real-time metrics, alerts, and audit logging

## Authentication

All API endpoints require authentication via the `X-API-Key` header.
In development mode (DEBUG=true), requests without an API key are allowed.

## Quick Start

1. Register an agent: `POST /api/v1/agents`
2. Poll for tasks: `GET /api/v1/agents/{agent_id}/tasks/next`
3. Submit results: `POST /api/v1/tasks/{task_id}/result`
4. Monitor via dashboard: [http://localhost:3051](http://localhost:3051)

## BYOK (Bring Your Own Key)

Customers can register their own LLM API keys for zero-cost passthrough:

1. Configure billing: `POST /api/v1/llm-billing/customers`
2. Add BYOK key: `POST /api/v1/llm-billing/customers/{id}/byok-keys`
3. Make LLM calls: `POST /api/v1/llm/completions` (uses customer's key automatically)
    """,
    version="0.1.0",
    lifespan=lifespan,
    docs_url="/docs",
    redoc_url="/redoc",
    openapi_url="/openapi.json",
    openapi_tags=[
        {
            "name": "auth",
            "description": "User authentication and session management",
        },
        {
            "name": "agents",
            "description": "Agent registration, monitoring, and lifecycle management",
        },
        {
            "name": "tasks",
            "description": "Task submission, polling, and result management",
        },
        {
            "name": "workflows",
            "description": "Visual workflow designer and execution management",
        },
        {
            "name": "integrations",
            "description": "Third-party service connections (Slack, GitHub, Salesforce, etc.)",
        },
        {
            "name": "marketplace",
            "description": "Agent marketplace — browse, install, and publish agents",
        },
        {
            "name": "metrics",
            "description": "System metrics and observability",
        },
        {
            "name": "alerts",
            "description": "Alert management and notifications",
        },
        {
            "name": "gateway",
            "description": "LLM gateway and proxy operations",
        },
        {
            "name": "Model Router",
            "description": "Intelligent LLM routing with health monitoring and cost optimization",
        },
        {
            "name": "llm-billing",
            "description": "Customer billing, BYOK key management, and usage tracking",
        },
        {
            "name": "credentials",
            "description": "BYOK LLM API key management per tenant",
        },
        {
            "name": "ab-testing",
            "description": "A/B testing experiments for agent and model comparison",
        },
        {
            "name": "hitl",
            "description": "Human-in-the-loop approval workflows",
        },
        {
            "name": "cost",
            "description": "Cost tracking, budgets, and forecasting",
        },
        {
            "name": "audit",
            "description": "Audit logging for compliance and security",
        },
        {
            "name": "prompts",
            "description": "Prompt registry — versioned template management",
        },
        {
            "name": "webhooks",
            "description": "Inbound webhook event handling",
        },
        {
            "name": "scheduler",
            "description": "Scheduled workflow execution (cron, interval, one-time)",
        },
        {
            "name": "memory",
            "description": "BYOS — Bring Your Own Storage for agent memory (vector DBs)",
        },
        {
            "name": "rag",
            "description": "BYOD — Bring Your Own Data for RAG connectors",
        },
        {
            "name": "byoc",
            "description": "BYOC — Bring Your Own Compute for self-hosted workers",
        },
        {
            "name": "mcp",
            "description": "Model Context Protocol tool server management",
        },
        {
            "name": "settings",
            "description": "Organization settings, team members, and API keys",
        },
        {
            "name": "seed",
            "description": "Development seed data endpoints",
        },
        {
            "name": "health",
            "description": "Health checks and system status",
        },
    ],
    contact={
        "name": "Orchestly",
        "url": "https://orchestly.ai",
        "email": "support@orchestly.ai",
    },
    license_info={
        "name": "MIT License",
        "url": "https://opensource.org/licenses/MIT",
    },
)

# Get settings
settings = get_settings()

# Note: CORS middleware will be added LAST (after other middleware)
# so it handles preflight OPTIONS requests first
print(f"   CORS Origins: {settings.CORS_ORIGINS}")


# Security headers middleware
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request as StarletteRequest


class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    """Add security headers to all responses."""

    async def dispatch(self, request: StarletteRequest, call_next):
        response = await call_next(request)
        # Prevent MIME type sniffing
        response.headers["X-Content-Type-Options"] = "nosniff"
        # Prevent clickjacking
        response.headers["X-Frame-Options"] = "DENY"
        # XSS protection (legacy but still useful)
        response.headers["X-XSS-Protection"] = "1; mode=block"
        # Referrer policy
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
        # Content Security Policy — permissive for docs UI, restrictive for API
        if request.url.path in ("/docs", "/redoc", "/openapi.json"):
            response.headers["Content-Security-Policy"] = (
                "default-src 'self'; script-src 'self' 'unsafe-inline' https://cdn.jsdelivr.net; "
                "style-src 'self' 'unsafe-inline' https://cdn.jsdelivr.net; "
                "img-src 'self' data:; font-src 'self' https://cdn.jsdelivr.net"
            )
        else:
            response.headers["Content-Security-Policy"] = "default-src 'none'; frame-ancestors 'none'"
        # HSTS — enforce HTTPS (1 year, include subdomains)
        response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"
        # Permissions policy
        response.headers["Permissions-Policy"] = "geolocation=(), microphone=(), camera=()"
        return response


app.add_middleware(SecurityHeadersMiddleware)

# PHI Detection middleware (HIPAA compliance for Business Associate role)
try:
    from backend.shared.phi_middleware import PHIDetectionMiddleware
    app.add_middleware(PHIDetectionMiddleware)
    print("  ✓ PHI Detection middleware enabled (HIPAA)")
except Exception as e:
    print(f"  ✗ PHI Detection middleware: {e}")


# Rate limiting middleware
from backend.shared.auth import get_rate_limiter


class RateLimitMiddleware(BaseHTTPMiddleware):
    """Rate limit requests based on organization or IP."""

    async def dispatch(self, request: StarletteRequest, call_next):
        # Skip rate limiting for health checks
        if request.url.path in ["/health", "/", "/docs", "/openapi.json"]:
            return await call_next(request)

        rate_limiter = get_rate_limiter()

        # Try to get org_id from API key header or use IP as fallback
        org_id = request.headers.get("X-Organization-ID")
        if not org_id:
            # Use client IP as identifier for unauthenticated requests
            org_id = request.client.host if request.client else "unknown"

        # Get tier from header or default to startup
        tier = request.headers.get("X-Rate-Limit-Tier", "startup")

        # Check rate limit
        if not await rate_limiter.check_rate_limit(org_id, tier):
            return JSONResponse(
                status_code=429,
                content={"detail": "Rate limit exceeded. Please retry later."},
                headers={"Retry-After": "60"}
            )

        response = await call_next(request)

        # Add rate limit headers
        response.headers["X-RateLimit-Limit"] = str(rate_limiter._limits.get(tier, 100))
        response.headers["X-RateLimit-Remaining"] = str(
            int(rate_limiter._buckets.get(org_id, {}).get("tokens", 0))
        )

        return response


app.add_middleware(RateLimitMiddleware)


# Request validation middleware
class RequestValidationMiddleware(BaseHTTPMiddleware):
    """Validate incoming requests for security and correctness."""

    # Maximum allowed content length (10MB)
    MAX_CONTENT_LENGTH = 10 * 1024 * 1024

    # Allowed content types for POST/PUT/PATCH
    ALLOWED_CONTENT_TYPES = [
        "application/json",
        "application/x-www-form-urlencoded",
        "multipart/form-data",
    ]

    async def dispatch(self, request: StarletteRequest, call_next):
        # Skip validation for GET, HEAD, OPTIONS
        if request.method in ["GET", "HEAD", "OPTIONS"]:
            return await call_next(request)

        # Check content length
        content_length = request.headers.get("content-length")
        if content_length:
            try:
                length = int(content_length)
                if length > self.MAX_CONTENT_LENGTH:
                    return JSONResponse(
                        status_code=413,
                        content={"detail": "Request body too large"}
                    )
            except ValueError:
                return JSONResponse(
                    status_code=400,
                    content={"detail": "Invalid Content-Length header"}
                )

        # Check content type for requests with body
        if request.method in ["POST", "PUT", "PATCH"]:
            content_type = request.headers.get("content-type", "")

            # Skip check for requests without body or specific endpoints
            if content_type and not any(
                ct in content_type.lower()
                for ct in self.ALLOWED_CONTENT_TYPES
            ):
                # Allow empty content-type for some endpoints
                if content_length and int(content_length) > 0:
                    return JSONResponse(
                        status_code=415,
                        content={"detail": f"Unsupported content type: {content_type}"}
                    )

        return await call_next(request)


app.add_middleware(RequestValidationMiddleware)

# CORS middleware - added LAST so it's outermost and handles OPTIONS preflight first
# Hardcoded origins for debugging - bypasses settings loading issues
_cors_origins = ["http://localhost:3000", "http://localhost:3001", "http://localhost:3040", "http://localhost:3041", "http://localhost:3042", "http://localhost:3051", "http://127.0.0.1:3000", "http://127.0.0.1:3040", "http://127.0.0.1:3041", "http://127.0.0.1:3042", "http://127.0.0.1:3051"]
print(f"   CORS Origins (hardcoded): {_cors_origins}")
app.add_middleware(
    CORSMiddleware,
    allow_origins=_cors_origins,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE", "PATCH", "OPTIONS"],
    allow_headers=[
        "Content-Type", "Authorization", "X-API-Key",
        "X-Organization-ID", "X-API-Version", "X-Rate-Limit-Tier",
        "Accept-Version",
    ],
)

# Include workflow router
from backend.api.workflows import router as workflow_router
app.include_router(workflow_router)  # /api/workflows

# Include agent registry router
from backend.api.agent_registry import router as agent_registry_router
app.include_router(agent_registry_router)

# Include authentication router
from backend.api.auth import router as auth_router
app.include_router(auth_router)

# Include LLM router (providers, routing, settings)
from backend.api.llm import router as llm_router
app.include_router(llm_router)

# Include Model Router (intelligent LLM routing with health monitoring)
from backend.api.router import router as model_router
app.include_router(model_router)
print("  ✓ Model Router enabled")

# Include routing config router (for routing strategy configuration)
try:
    from backend.api.routing_config import router as routing_config_router
    app.include_router(routing_config_router)
    print("  ✓ Routing config router enabled")
except Exception as e:
    import traceback
    print(f"  ✗ Routing config router: {e}")
    print(f"    Traceback: {traceback.format_exc()}")

# Include connections router (for customer integration auth) - always enabled
try:
    from backend.api.connections import router as connections_router
    app.include_router(connections_router)
    print("  ✓ Connections router enabled")
except Exception as e:
    import traceback
    print(f"  ✗ Connections router: {e}")
    print(f"    Traceback: {traceback.format_exc()}")

# Include OAuth router (for OAuth2 integrations)
try:
    from backend.api.oauth import router as oauth_router
    app.include_router(oauth_router)
    print("  ✓ OAuth router enabled")
except Exception as e:
    import traceback
    print(f"  ✗ OAuth router: {e}")
    print(f"    Traceback: {traceback.format_exc()}")

# Include OAuth Settings router (for hybrid OAuth config)
try:
    from backend.api.oauth_settings import router as oauth_settings_router
    app.include_router(oauth_settings_router)
    print("  ✓ OAuth Settings router enabled")
except Exception as e:
    import traceback
    print(f"  ✗ OAuth Settings router: {e}")
    print(f"    Traceback: {traceback.format_exc()}")

# Include Webhooks router (for receiving external webhooks)
try:
    from backend.api.webhooks import router as webhooks_router
    app.include_router(webhooks_router)
    print("  ✓ Webhooks router enabled")
except Exception as e:
    import traceback
    print(f"  ✗ Webhooks router: {e}")
    print(f"    Traceback: {traceback.format_exc()}")

# ============================================================================
# Free-Tier Routers (Apache 2.0 — always loaded)
# ============================================================================
# These routers constitute the open-core free tier. They are always available
# regardless of license status or environment flags.

print("  Loading free-tier routers...")

_free_routers = [
    ("backend.api.hitl", "HITL"),
    ("backend.api.cost", "Cost Tracking"),
    ("backend.api.audit", "Audit Logs"),
    ("backend.api.settings", "Settings & Team"),
    ("backend.api.marketplace", "Marketplace"),
    ("backend.api.integrations", "Integrations"),
    ("backend.api.seed", "Seed Data"),
    ("backend.api.scheduler", "Scheduler"),
    ("backend.api.memory", "Memory (BYOS)"),
    ("backend.api.rag", "RAG (BYOD)"),
    ("backend.api.mcp", "MCP"),
    ("backend.api.prompts", "Prompt Registry"),
    ("backend.api.llm_billing", "LLM Billing"),
    ("backend.api.credentials", "Credentials (BYOK)"),
    ("backend.api.supervisor", "Supervisor"),
    ("backend.api.realtime", "Realtime (WebSocket)"),
]

for _module_path, _label in _free_routers:
    try:
        import importlib as _il
        _mod = _il.import_module(_module_path)
        app.include_router(_mod.router)
        print(f"    ✓ {_label} router enabled")
    except Exception as _e:
        print(f"    ✗ {_label} router: {_e}")

# ============================================================================
# Enterprise Routers (require ORCHESTLY_LICENSE_KEY)
# ============================================================================
# These routers provide enterprise-grade features gated behind a license.
# Without a valid license key, these endpoints are not registered at all.

try:
    from ee.license import has_enterprise_license as _has_ee_license
except ImportError:
    def _has_ee_license() -> bool:
        return False

if _has_ee_license():
    print("  Loading enterprise routers (license active)...")

    _enterprise_routers = [
        ("backend.api.sso", "SSO (SAML/OAuth)"),
        ("backend.api.hipaa", "HIPAA Compliance"),
        ("backend.api.multicloud", "Multi-Cloud Deployment"),
        ("backend.api.partners", "Partners (White Label)"),
        ("backend.api.ab_testing", "A/B Testing"),
        ("backend.api.timetravel", "Time-Travel Debugging"),
        ("backend.api.optimization", "Auto-Optimization"),
        ("backend.api.ml_routing", "ML Routing"),
        ("backend.api.analytics", "Advanced Analytics"),
        ("backend.api.byoc", "BYOC (Bring Your Own Compute)"),
        # NOTE: backend.api.security is excluded — its security_models.UserRole
        # conflicts with rbac_models' user_roles table, poisoning the mapper.
        # Re-add once security_models uses a separate table name or extend_existing.
    ]

    for _module_path, _label in _enterprise_routers:
        try:
            import importlib as _il
            _mod = _il.import_module(_module_path)
            app.include_router(_mod.router)
            print(f"    ✓ {_label} router enabled")
        except Exception as _e:
            print(f"    ✗ {_label} router: {_e}")
else:
    print("  ℹ Enterprise routers not loaded (set ORCHESTLY_LICENSE_KEY to activate)")

# ============================================================================
# License Status Endpoint
# ============================================================================

@app.get("/api/v1/license/status")
async def license_status():
    """Return the current license edition and activation status."""
    try:
        from ee.license import get_license_status
        return get_license_status()
    except ImportError:
        return {
            "edition": "community",
            "licensed": False,
            "message": "Enterprise module not installed.",
        }


# ============================================================================
# Authentication (Database-backed API Key)
# ============================================================================

from backend.services.api_key_service import APIKeyService
from backend.database.session import get_db


def generate_api_key() -> str:
    """Generate a random API key prefix (for display only)."""
    return f"ao_live_{secrets.token_urlsafe(32)[:32]}"


async def verify_api_key(
    api_key: str = Header(None, alias="X-API-Key"),
    organization_id: str = Header(None, alias="X-Organization-ID"),
    authorization: str = Header(None),
) -> dict:
    """
    Verify API key or JWT Bearer token against database.

    Accepts either:
    - X-API-Key header (for SDK/CLI access)
    - Authorization: Bearer <jwt> header (for dashboard access)

    Returns:
        Dict with key metadata including organization_id and permissions.
    """
    # Try JWT Bearer token first (dashboard auth)
    if authorization and authorization.startswith("Bearer "):
        from backend.shared.auth import get_jwt_manager
        from backend.shared.rbac_models import UserModel
        from sqlalchemy import select as _sel
        token = authorization[7:]
        try:
            jwt_mgr = get_jwt_manager()
            payload = jwt_mgr.verify_token(token)
            if payload:
                user_id = payload.get("sub")
                if user_id:
                    async with AsyncSessionLocal() as db:
                        result = await db.execute(
                            _sel(UserModel).where(UserModel.user_id == user_id)
                        )
                        user = result.scalar_one_or_none()
                        if user:
                            return {
                                "user_id": user.user_id,
                                "organization_id": user.organization_id or "default",
                                "permissions": ["*"],
                                "role": user.role or "admin",
                            }
        except Exception:
            pass  # Fall through to API key check

    if not api_key:
        raise HTTPException(status_code=401, detail="API key required")

    # Verify against database (production mode)
    async with AsyncSessionLocal() as db:
        service = APIKeyService(db)
        key_data = await service.verify_key(api_key)

        if not key_data:
            raise HTTPException(status_code=401, detail="Invalid API key")

        # Use the org_id from the API key's database record (authoritative)
        # The X-Organization-ID header is only used in debug mode
        return key_data


# ============================================================================
# Health Check
# ============================================================================

@app.get("/health")
async def health_check():
    """
    Health check endpoint — public surface returns minimal info only.

    Returns overall status and database connectivity.
    Agent counts, queue depths, and capability names are omitted
    to avoid leaking system information to unauthenticated callers.
    """
    from datetime import datetime

    health_status = {
        "status": "healthy",
        "version": "0.1.0",
        "timestamp": datetime.utcnow().isoformat(),
        "checks": {}
    }

    # Database health check
    db_healthy = False
    try:
        async with AsyncSessionLocal() as db:
            from sqlalchemy import text
            await db.execute(text("SELECT 1"))
            db_healthy = True
            health_status["checks"]["database"] = {"status": "healthy"}
    except Exception:
        health_status["checks"]["database"] = {"status": "unhealthy"}

    if not db_healthy:
        health_status["status"] = "unhealthy"
        return JSONResponse(status_code=503, content=health_status)

    return health_status


@app.get("/.well-known/security.txt")
async def security_txt():
    """RFC 9116 security.txt for responsible disclosure."""
    import os
    contact = os.environ.get("SECURITY_CONTACT_EMAIL", "security@orchestly.ai")
    content = (
        f"Contact: mailto:{contact}\n"
        "Preferred-Languages: en\n"
        "Canonical: https://orchestly.ai/.well-known/security.txt\n"
        "Policy: https://orchestly.ai/security-policy\n"
    )
    return Response(content=content, media_type="text/plain")


@app.get("/health/live")
async def liveness_check():
    """Kubernetes liveness probe - just checks if the app is running."""
    return {"status": "alive"}


@app.get("/health/ready")
async def readiness_check():
    """Kubernetes readiness probe - checks if the app can handle traffic."""
    try:
        async with AsyncSessionLocal() as db:
            from sqlalchemy import text
            await db.execute(text("SELECT 1"))
        return {"status": "ready"}
    except Exception:
        return JSONResponse(
            status_code=503,
            content={"status": "not_ready", "reason": "database_unavailable"}
        )


# ============================================================================
# API Versioning
# ============================================================================

# API version constants
API_VERSION = "1.0.0"
API_MIN_VERSION = "1.0.0"
API_SUPPORTED_VERSIONS = ["1.0.0"]


@app.get("/")
async def root():
    """API root - returns version and basic info."""
    return {
        "name": "Agent Orchestration API",
        "version": API_VERSION,
        "min_version": API_MIN_VERSION,
        "supported_versions": API_SUPPORTED_VERSIONS,
        "docs_url": "/docs",
        "health_url": "/health"
    }


@app.get("/api/version")
async def get_api_version():
    """Get detailed API version information."""
    return {
        "version": API_VERSION,
        "min_supported_version": API_MIN_VERSION,
        "supported_versions": API_SUPPORTED_VERSIONS,
        "deprecation_notices": [],
        "changelog_url": None
    }


class APIVersionMiddleware(BaseHTTPMiddleware):
    """
    Add API version headers and validate version requests.

    Supports:
    - X-API-Version header for version negotiation
    - Accept-Version header (alternative)
    - Adds X-API-Version response header
    """

    async def dispatch(self, request: StarletteRequest, call_next):
        # Get requested version from headers
        requested_version = request.headers.get(
            "X-API-Version",
            request.headers.get("Accept-Version", API_VERSION)
        )

        # Validate version
        if requested_version not in API_SUPPORTED_VERSIONS:
            # Check if it's a compatible version (semver major match)
            requested_major = requested_version.split(".")[0] if "." in requested_version else requested_version
            current_major = API_VERSION.split(".")[0]

            if requested_major != current_major:
                return JSONResponse(
                    status_code=400,
                    content={
                        "detail": f"Unsupported API version: {requested_version}",
                        "supported_versions": API_SUPPORTED_VERSIONS,
                        "current_version": API_VERSION
                    }
                )

        response = await call_next(request)

        # Add version headers to response
        response.headers["X-API-Version"] = API_VERSION
        response.headers["X-API-Min-Version"] = API_MIN_VERSION

        return response


# Add API version middleware (must be after other middlewares)
app.add_middleware(APIVersionMiddleware)


# ============================================================================
# Agent Management Endpoints
# ============================================================================

@app.post("/api/v1/agents", status_code=201)
async def register_agent(
    config: AgentConfig,
    api_key: dict = Depends(verify_api_key)
):
    """
    Register a new agent.

    Returns agent ID and API key for authentication.
    The agent is scoped to the authenticated organization.
    """
    registry = get_registry()

    # Ensure the agent is registered under the authenticated organization
    org_id = api_key.get("organization_id")
    if org_id:
        config.organization_id = org_id

    try:
        agent_id = await registry.register_agent(config)

        # Generate API key for this agent
        new_api_key = generate_api_key()
        # Note: In production, this should be stored in the database via APIKeyService

        return {
            "agent_id": str(agent_id),
            "api_key": new_api_key,
            "status": "registered"
        }

    except ValueError as e:
        logger.warning(f"Agent registration validation error: {e}")
        raise HTTPException(status_code=400, detail="Invalid agent configuration")


@app.get("/api/v1/agents")
async def list_agents(
    status: Optional[str] = None,
    api_key: dict = Depends(verify_api_key)
):
    """List agents for the authenticated organization."""
    registry = get_registry()
    org_id = api_key.get("organization_id")

    agents = await registry.list_agents(status=status, organization_id=org_id)

    return {
        "agents": [
            {
                "agent_id": str(agent.agent_id),
                "name": agent.name,
                "capabilities": [c.name for c in agent.capabilities],
                "framework": agent.framework,
                "version": agent.version,
            }
            for agent in agents
        ],
        "total": len(agents)
    }


@app.get("/api/v1/agents/{agent_id}")
async def get_agent(
    agent_id: UUID,
    api_key: dict = Depends(verify_api_key)
):
    """Get agent details and metrics."""
    registry = get_registry()

    metrics = await registry.get_agent_metrics(agent_id)

    if not metrics:
        raise HTTPException(status_code=404, detail="Agent not found")

    return metrics


@app.post("/api/v1/agents/{agent_id}/heartbeat")
async def agent_heartbeat(
    agent_id: UUID,
    api_key: dict = Depends(verify_api_key)
):
    """Update agent heartbeat."""
    registry = get_registry()

    await registry.update_heartbeat(agent_id)

    return {"status": "ok", "timestamp": "updated"}


@app.delete("/api/v1/agents/{agent_id}")
async def deregister_agent(
    agent_id: UUID,
    api_key: dict = Depends(verify_api_key)
):
    """Deregister an agent."""
    registry = get_registry()

    await registry.deregister_agent(agent_id)

    return {"status": "deregistered", "agent_id": str(agent_id)}


# ============================================================================
# Task Management Endpoints
# ============================================================================

@app.post("/api/v1/tasks", status_code=201)
async def submit_task(
    capability: str,
    input_data: dict,
    priority: TaskPriority = TaskPriority.NORMAL,
    timeout_seconds: int = 300,
    max_retries: int = 3,
    api_key: dict = Depends(verify_api_key)
):
    """Submit a new task, scoped to the authenticated organization."""
    queue = get_queue()
    org_id = api_key.get("organization_id")

    # Create task
    task = Task(
        capability=capability,
        input=TaskInput(data=input_data),
        priority=priority,
        timeout_seconds=timeout_seconds,
        max_retries=max_retries,
        organization_id=org_id,
    )

    # Enqueue
    try:
        task_id = await queue.enqueue_task(task)
    except ValueError:
        raise HTTPException(status_code=422, detail="Invalid capability name")

    return {
        "task_id": str(task_id),
        "status": "queued",
        "capability": capability
    }


@app.get("/api/v1/tasks")
async def list_tasks(
    status: Optional[str] = None,
    capability: Optional[str] = None,
    limit: int = 100,
    offset: int = 0,
    api_key: dict = Depends(verify_api_key)
):
    """
    List all tasks with optional filtering.

    Args:
        status: Filter by task status (queued, running, completed, failed)
        capability: Filter by task capability
        limit: Maximum number of tasks to return
        offset: Offset for pagination

    Returns:
        List of tasks with their current status
    """
    queue = get_queue()

    # Get all tasks from queue (this gets tasks from the in-memory queue)
    all_tasks = []

    # Get tasks from each capability queue
    queue_depths = await queue.get_all_queue_depths()
    for cap in queue_depths.keys():
        if capability and cap != capability:
            continue
        # Note: The queue doesn't expose a list method, so we track completed/running tasks
        # In production, this would query a database

    # For now, return queue statistics as task summaries
    # In production, this would query the tasks table
    from backend.database.session import AsyncSessionLocal

    try:
        async with AsyncSessionLocal() as db:
            from sqlalchemy import select, desc
            from backend.database.models import TaskModel

            query = select(TaskModel)

            # Apply organization filter for multi-tenancy
            org_id = api_key.get("organization_id")
            if org_id and org_id != "debug":
                query = query.where(TaskModel.organization_id == org_id)

            if status:
                query = query.where(TaskModel.status == status)
            if capability:
                query = query.where(TaskModel.capability == capability)

            query = query.order_by(desc(TaskModel.created_at))
            query = query.offset(offset).limit(limit)

            result = await db.execute(query)
            tasks = result.scalars().all()

            return {
                "tasks": [
                    {
                        "task_id": str(t.task_id),
                        "capability": t.capability,
                        "status": t.status,
                        "priority": t.priority if hasattr(t, 'priority') else "normal",
                        "created_at": t.created_at.isoformat() if t.created_at else None,
                        "started_at": t.started_at.isoformat() if hasattr(t, 'started_at') and t.started_at else None,
                        "completed_at": t.completed_at.isoformat() if hasattr(t, 'completed_at') and t.completed_at else None,
                        "assigned_agent_id": str(t.assigned_agent_id) if hasattr(t, 'assigned_agent_id') and t.assigned_agent_id else None,
                        "retry_count": t.retry_count if hasattr(t, 'retry_count') else 0,
                    }
                    for t in tasks
                ],
                "total": len(tasks),
                "limit": limit,
                "offset": offset
            }
    except Exception as e:
        # Fallback to queue-based response if database not available
        return {
            "tasks": [],
            "total": 0,
            "limit": limit,
            "offset": offset,
            "note": "Task listing from database not available, showing queue depths instead",
            "queue_depths": await queue.get_all_queue_depths()
        }


@app.get("/api/v1/tasks/{task_id}")
async def get_task(
    task_id: UUID,
    api_key: dict = Depends(verify_api_key)
):
    """Get task status and details."""
    queue = get_queue()

    task = await queue.get_task(task_id)

    if not task:
        raise HTTPException(status_code=404, detail="Task not found")

    return {
        "task_id": str(task.task_id),
        "capability": task.capability,
        "status": task.status.value,
        "assigned_agent_id": str(task.assigned_agent_id) if task.assigned_agent_id else None,
        "created_at": task.created_at.isoformat(),
        "started_at": task.started_at.isoformat() if task.started_at else None,
        "completed_at": task.completed_at.isoformat() if task.completed_at else None,
        "retry_count": task.retry_count,
        "cost": task.actual_cost,
        "output": task.output.data if task.output else None,
        "error": task.error_message,
    }


@app.get("/api/v1/agents/{agent_id}/tasks/next")
async def get_next_task(
    agent_id: UUID,
    capabilities: str,  # Comma-separated list
    api_key: dict = Depends(verify_api_key)
):
    """
    Poll for next task matching agent capabilities.

    Used by SDK for task polling.
    """
    queue = get_queue()

    # Split capabilities
    capability_list = [c.strip() for c in capabilities.split(",")]

    # Try each capability
    for capability in capability_list:
        task = await queue.get_next_task(capability)

        if task:
            return {
                "task_id": str(task.task_id),
                "capability": task.capability,
                "input": task.input.data,
                "timeout_seconds": task.timeout_seconds,
                "assigned_agent_id": str(task.assigned_agent_id),
            }

    # No tasks available
    return Response(status_code=204)


@app.post("/api/v1/tasks/{task_id}/result")
async def submit_task_result(
    task_id: UUID,
    status: str,
    output: Optional[dict] = None,
    error: Optional[str] = None,
    cost: Optional[float] = None,
    api_key: dict = Depends(verify_api_key)
):
    """Submit task result (completion or failure)."""
    queue = get_queue()

    if status == "completed":
        if not output:
            raise HTTPException(status_code=400, detail="Output required for completed task")

        await queue.complete_task(task_id, output, cost)

        return {"status": "completed", "task_id": str(task_id)}

    elif status == "failed":
        if not error:
            raise HTTPException(status_code=400, detail="Error message required for failed task")

        await queue.fail_task(task_id, error)

        return {"status": "failed", "task_id": str(task_id)}

    else:
        raise HTTPException(status_code=400, detail=f"Invalid status: {status}")


# ============================================================================
# LLM Proxy Endpoint (BYOK - Bring Your Own Key)
# ============================================================================

# Import billing service for BYOK key lookup
from backend.services.llm_billing_service import (
    get_llm_billing_service,
    LLMProvider as BillingLLMProvider,
)

from fastapi import Body, Query

@app.post("/api/v1/llm/completions")
async def llm_completion(
    agent_id: UUID = Query(..., description="Agent ID making the request"),
    provider: str = Query(..., description="LLM provider (openai, anthropic, groq, etc.)"),
    model: str = Query(..., description="Model name (e.g., gpt-4o, llama-3.3-70b-versatile)"),
    messages: List[dict] = Body(..., description="Messages array with role and content"),
    temperature: float = Query(0.7, description="Sampling temperature"),
    max_tokens: Optional[int] = Query(None, description="Max tokens to generate"),
    task_id: Optional[UUID] = Query(None, description="Optional task ID for tracking"),
    api_key: dict = Depends(verify_api_key)
):
    """
    Proxy LLM request through gateway with BYOK (Bring Your Own Key) support.

    BYOK Architecture:
    - Customer registers their LLM API key via /api/v1/llm-billing/customers/{id}/byok-keys
    - This endpoint looks up the customer's registered key
    - Uses customer's key to make the LLM call
    - Tracks usage for billing/observability

    Supported billing models:
    - BYOK: Customer provides their own API keys (zero LLM cost to platform)
    - Managed: Platform manages keys, charges usage + markup
    - Prepaid: Customer buys credits upfront

    Used by SDK's LLMClient and customer applications like supply-chain.
    """
    import time
    from uuid import uuid4

    gateway = get_gateway()
    billing_service = get_llm_billing_service()

    # Get customer/organization ID from API key auth
    # In production, this comes from the API key's associated organization
    customer_id = api_key.get("organization_id", "default")

    # Map provider string to enum
    provider_map = {
        "openai": BillingLLMProvider.OPENAI,
        "anthropic": BillingLLMProvider.ANTHROPIC,
        "google": BillingLLMProvider.GOOGLE,
        "azure_openai": BillingLLMProvider.AZURE_OPENAI,
        "groq": BillingLLMProvider.GROQ,
        "mistral": BillingLLMProvider.MISTRAL,
    }
    billing_provider = provider_map.get(provider.lower())

    # Try to get customer's API key based on their billing model
    customer_api_key = None
    billing_model_used = "platform"  # Track which billing model was used

    if billing_provider:
        # First check if customer exists in billing service
        config = await billing_service.get_customer_config(customer_id)

        if config:
            # Customer has config, try to get their API key
            customer_api_key, error = await billing_service.get_api_key_for_request(
                customer_id=customer_id,
                provider=billing_provider,
                model=model,
                estimated_tokens=max_tokens or 1000
            )

            if error:
                # SECURITY: For BYOK customers, do NOT fall back to platform keys
                # This prevents rogue customers from using platform keys for free
                from backend.services.llm_billing_service import BillingModel

                if config.billing_model == BillingModel.BYOK:
                    # BYOK customers MUST provide their own keys - no fallback
                    raise HTTPException(
                        status_code=403,
                        detail=f"BYOK key required: {error}. Please configure your API key for {billing_provider.value} in BYOK Settings."
                    )
                else:
                    # Managed/Prepaid/Enterprise can fall back to platform keys
                    print(f"API key lookup for {customer_id}: {error} - using platform keys (billing model: {config.billing_model.value})")
                    billing_model_used = "platform_fallback"
            else:
                billing_model_used = config.billing_model.value
        else:
            # No customer config - require registration for API access
            # This prevents unregistered users from getting free LLM access
            raise HTTPException(
                status_code=403,
                detail=f"Customer '{customer_id}' not configured for LLM access. Please register in BYOK Settings first."
            )

    try:
        start_time = time.time()

        # Use customer's key if available, otherwise gateway uses env vars
        if customer_api_key:
            # Direct LLM call with customer's BYOK key
            from core.llm.async_providers import create_async_provider

            # Extract prompts from messages
            system_prompt = ""
            user_prompt = ""
            for msg in messages:
                if msg.get("role") == "system":
                    system_prompt = msg.get("content", "")
                elif msg.get("role") == "user":
                    user_prompt = msg.get("content", "")

            # Normalize provider for async_provider
            provider_normalized = "groq" if provider.lower() == "groq" else provider.lower()
            if provider_normalized == "anthropic":
                provider_normalized = "claude"

            llm_provider = create_async_provider(
                provider_name=provider_normalized,
                model=model,
                max_tokens=max_tokens or 1000,
                temperature=temperature,
                api_key=customer_api_key,
            )

            async_response = await llm_provider.complete(
                prompt=user_prompt,
                system_prompt=system_prompt,
                temperature=temperature,
                max_tokens=max_tokens or 1000,
            )

            latency_ms = int((time.time() - start_time) * 1000)

            # Record usage for billing
            if billing_provider:
                await billing_service.record_request_usage(
                    customer_id=customer_id,
                    provider=billing_provider,
                    model=model,
                    input_tokens=async_response.input_tokens,
                    output_tokens=async_response.output_tokens,
                    agent_name=str(agent_id),
                    latency_ms=latency_ms,
                )

            return {
                "content": async_response.content,
                "finish_reason": async_response.finish_reason,
                "usage": {
                    "prompt_tokens": async_response.input_tokens,
                    "completion_tokens": async_response.output_tokens,
                    "total_tokens": async_response.input_tokens + async_response.output_tokens,
                },
                "cost": async_response.cost or 0.0,
                "latency_ms": latency_ms,
                "billing_model": billing_model_used,
            }
        else:
            # Fall back to gateway with platform keys (env vars)
            # This path is only reached for:
            # - Managed/Prepaid/Enterprise customers (platform fallback allowed)
            # - Unsupported providers (billing_provider is None)
            response = await gateway.proxy_request(
                agent_id=agent_id,
                provider=provider,
                model=model,
                messages=messages,
                temperature=temperature,
                max_tokens=max_tokens,
                task_id=task_id,
            )

            return {
                "content": response.content,
                "finish_reason": response.finish_reason,
                "usage": {
                    "prompt_tokens": response.prompt_tokens,
                    "completion_tokens": response.completion_tokens,
                    "total_tokens": response.total_tokens,
                },
                "cost": response.estimated_cost,
                "latency_ms": response.latency_ms,
                "billing_model": billing_model_used,
            }

    except ValueError as e:
        # Cost limit exceeded
        logger.warning(f"LLM cost limit exceeded: {e}")
        raise HTTPException(status_code=429, detail="Cost limit exceeded")
    except RuntimeError as e:
        # LLM request failed
        logger.error(f"LLM request failed: {e}")
        raise HTTPException(status_code=500, detail="LLM request failed")


# ============================================================================
# Metrics Endpoints
# ============================================================================

@app.get("/api/v1/metrics/system")
async def get_system_metrics(api_key: dict = Depends(verify_api_key)):
    """Get comprehensive system metrics for the authenticated organization."""
    collector = get_collector()
    org_id = api_key.get("organization_id")
    return await collector.collect_metrics(organization_id=org_id)


@app.get("/api/v1/metrics/capabilities/{capability}")
async def get_capability_metrics(
    capability: str,
    api_key: dict = Depends(verify_api_key)
):
    """Get detailed metrics for a specific capability."""
    collector = get_collector()
    return await collector.get_capability_metrics(capability)


@app.get("/api/v1/metrics/agents/{agent_id}")
async def get_agent_performance_metrics(
    agent_id: UUID,
    api_key: dict = Depends(verify_api_key)
):
    """Get detailed performance metrics for an agent."""
    collector = get_collector()
    metrics = await collector.get_agent_performance(agent_id)

    if not metrics:
        raise HTTPException(status_code=404, detail="Agent not found")

    return metrics


@app.get("/api/v1/metrics/timeseries")
async def get_time_series(
    metric: str,
    capability: Optional[str] = None,
    window_minutes: int = 60,
    api_key: dict = Depends(verify_api_key)
):
    """
    Get time-series data for a metric.

    Args:
        metric: Metric name (latency, cost, queue_depth)
        capability: Capability to filter by (optional)
        window_minutes: Time window in minutes
    """
    collector = get_collector()

    if metric not in ["latency", "cost", "queue_depth"]:
        raise HTTPException(status_code=400, detail=f"Invalid metric: {metric}")

    return await collector.get_time_series(metric, capability, window_minutes)


# ============================================================================
# Alert Endpoints
# ============================================================================

@app.get("/api/v1/alerts")
async def get_alerts(
    severity: Optional[str] = None,
    alert_type: Optional[str] = None,
    api_key: dict = Depends(verify_api_key)
):
    """Get active alerts for the authenticated organization."""
    alert_manager = get_alert_manager()
    org_id = api_key.get("organization_id")

    alerts = alert_manager.get_active_alerts(
        severity=severity,
        alert_type=alert_type,
        organization_id=org_id,
    )

    return {
        "alerts": [alert.to_dict() for alert in alerts],
        "total": len(alerts)
    }


@app.get("/api/v1/alerts/history")
async def get_alert_history(
    hours: int = 24,
    severity: Optional[str] = None,
    api_key: dict = Depends(verify_api_key)
):
    """Get alert history for the authenticated organization."""
    alert_manager = get_alert_manager()
    org_id = api_key.get("organization_id")

    alerts = alert_manager.get_alert_history(hours=hours, severity=severity, organization_id=org_id)

    return {
        "alerts": [alert.to_dict() for alert in alerts],
        "total": len(alerts)
    }


@app.get("/api/v1/alerts/stats")
async def get_alert_stats(api_key: dict = Depends(verify_api_key)):
    """Get alert statistics."""
    alert_manager = get_alert_manager()
    return alert_manager.get_alert_stats()


@app.post("/api/v1/alerts/{alert_id}/acknowledge")
async def acknowledge_alert(
    alert_id: UUID,
    api_key: dict = Depends(verify_api_key)
):
    """Acknowledge an alert."""
    alert_manager = get_alert_manager()

    success = await alert_manager.acknowledge_alert(alert_id)

    if not success:
        raise HTTPException(status_code=404, detail="Alert not found")

    return {"status": "acknowledged", "alert_id": str(alert_id)}


@app.post("/api/v1/alerts/{alert_id}/resolve")
async def resolve_alert(
    alert_id: UUID,
    api_key: dict = Depends(verify_api_key)
):
    """Resolve an alert."""
    alert_manager = get_alert_manager()

    success = await alert_manager.resolve_alert(alert_id)

    if not success:
        raise HTTPException(status_code=404, detail="Alert not found")

    return {"status": "resolved", "alert_id": str(alert_id)}


# ============================================================================
# Run Server
# ============================================================================

if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "backend.api.main:app",
        host=settings.API_HOST,
        port=settings.API_PORT,
        reload=settings.DEBUG,
        log_level="info",
    )
