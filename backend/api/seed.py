"""
Seed Data API Endpoints

Provides endpoints to seed demo data for development/testing.
"""

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from backend.database.session import get_db
from backend.shared.integration_models import IntegrationCategory, IntegrationType, AuthType
from backend.shared.marketplace_models import AgentVisibility, AgentCategory
from datetime import datetime

router = APIRouter(prefix="/api/v1/seed", tags=["seed"])


@router.post("/integrations")
async def seed_integrations(db: AsyncSession = Depends(get_db)):
    """Seed sample integrations."""
    from backend.shared.integration_service import IntegrationRegistryService

    service = IntegrationRegistryService(db)

    integrations_data = [
        # === AI/LLM Providers ===
        {
            "name": "OpenAI",
            "slug": "openai",
            "display_name": "OpenAI",
            "category": IntegrationCategory.AI,
            "integration_type": IntegrationType.API,
            "description": "GPT-4, GPT-3.5 and other OpenAI models for text generation, analysis, and more",
            "auth_type": AuthType.API_KEY,
            "configuration_schema": {
                "type": "object",
                "properties": {
                    "default_model": {
                        "type": "string",
                        "enum": ["gpt-4", "gpt-4-turbo", "gpt-4o", "gpt-4o-mini", "gpt-3.5-turbo"],
                        "default": "gpt-4o"
                    }
                }
            },
            "supported_actions": [
                {"name": "chat_completion", "description": "Generate text using chat completion API"},
                {"name": "text_completion", "description": "Generate text completion"},
                {"name": "embeddings", "description": "Generate text embeddings"}
            ],
            "provider_name": "OpenAI",
            "is_verified": True,
            "is_featured": True,
            "icon_url": "https://cdn.worldvectorlogo.com/logos/openai-2.svg",
        },
        {
            "name": "Anthropic",
            "slug": "anthropic",
            "display_name": "Anthropic (Claude)",
            "category": IntegrationCategory.AI,
            "integration_type": IntegrationType.API,
            "description": "Claude 3.5 Sonnet, Claude 3 Opus, and other Anthropic models for AI assistance",
            "auth_type": AuthType.API_KEY,
            "configuration_schema": {
                "type": "object",
                "properties": {
                    "default_model": {
                        "type": "string",
                        "enum": ["claude-3-5-sonnet-20241022", "claude-3-opus-20240229", "claude-3-sonnet-20240229", "claude-3-haiku-20240307"],
                        "default": "claude-3-5-sonnet-20241022"
                    }
                }
            },
            "supported_actions": [
                {"name": "chat_completion", "description": "Generate text using Claude models"},
                {"name": "analyze", "description": "Analyze text or images with Claude"}
            ],
            "provider_name": "Anthropic",
            "is_verified": True,
            "is_featured": True,
            "icon_url": "https://cdn.worldvectorlogo.com/logos/anthropic-1.svg",
        },
        {
            "name": "Google AI",
            "slug": "google-ai",
            "display_name": "Google AI (Gemini)",
            "category": IntegrationCategory.AI,
            "integration_type": IntegrationType.API,
            "description": "Gemini Pro, Gemini Flash and other Google AI models for multimodal AI",
            "auth_type": AuthType.API_KEY,
            "configuration_schema": {
                "type": "object",
                "properties": {
                    "default_model": {
                        "type": "string",
                        "enum": ["gemini-1.5-pro", "gemini-1.5-flash", "gemini-pro"],
                        "default": "gemini-1.5-flash"
                    }
                }
            },
            "supported_actions": [
                {"name": "chat_completion", "description": "Generate text using Gemini models"},
                {"name": "multimodal", "description": "Process text and images together"}
            ],
            "provider_name": "Google",
            "is_verified": True,
            "is_featured": True,
            "icon_url": "https://cdn.worldvectorlogo.com/logos/google-gemini-icon.svg",
        },
        {
            "name": "DeepSeek",
            "slug": "deepseek",
            "display_name": "DeepSeek",
            "category": IntegrationCategory.AI,
            "integration_type": IntegrationType.API,
            "description": "DeepSeek Chat and Coder models - high performance at low cost",
            "auth_type": AuthType.API_KEY,
            "configuration_schema": {
                "type": "object",
                "properties": {
                    "default_model": {
                        "type": "string",
                        "enum": ["deepseek-chat", "deepseek-coder"],
                        "default": "deepseek-chat"
                    }
                }
            },
            "supported_actions": [
                {"name": "chat_completion", "description": "Generate text using DeepSeek models"},
                {"name": "code_completion", "description": "Generate code with DeepSeek Coder"}
            ],
            "provider_name": "DeepSeek",
            "is_verified": True,
            "icon_url": "https://www.deepseek.com/favicon.ico",
        },
        {
            "name": "Groq",
            "slug": "groq",
            "display_name": "Groq (Llama, Mixtral)",
            "category": IntegrationCategory.AI,
            "integration_type": IntegrationType.API,
            "description": "Ultra-fast inference for Llama 3, Mixtral, and other open models via Groq",
            "auth_type": AuthType.API_KEY,
            "configuration_schema": {
                "type": "object",
                "properties": {
                    "default_model": {
                        "type": "string",
                        "enum": ["llama-3.1-70b-versatile", "llama-3.1-8b-instant", "mixtral-8x7b-32768", "gemma2-9b-it"],
                        "default": "llama-3.1-70b-versatile"
                    }
                }
            },
            "supported_actions": [
                {"name": "chat_completion", "description": "Generate text using Llama/Mixtral on Groq"}
            ],
            "provider_name": "Groq",
            "is_verified": True,
            "icon_url": "https://groq.com/favicon.ico",
        },
        # === Communication ===
        {
            "name": "Slack",
            "slug": "slack",
            "display_name": "Slack",
            "category": IntegrationCategory.COMMUNICATION,
            "integration_type": IntegrationType.API,
            "description": "Team collaboration and messaging platform",
            "auth_type": AuthType.OAUTH2,
            "configuration_schema": {},
            "supported_actions": [{"name": "send_message", "description": "Send a message to a channel"}],
            "provider_name": "Slack Technologies",
            "is_verified": True,
            "icon_url": "https://cdn.worldvectorlogo.com/logos/slack-new-logo.svg",
        },
        {
            "name": "GitHub",
            "slug": "github",
            "display_name": "GitHub",
            "category": IntegrationCategory.DEVELOPER_TOOLS,
            "integration_type": IntegrationType.API,
            "description": "Version control and collaboration for software development",
            "auth_type": AuthType.OAUTH2,
            "configuration_schema": {},
            "supported_actions": [{"name": "create_issue", "description": "Create a new issue"}],
            "provider_name": "GitHub Inc",
            "is_verified": True,
            "icon_url": "https://cdn.worldvectorlogo.com/logos/github-icon-1.svg",
        },
        {
            "name": "Google Drive",
            "slug": "google-drive",
            "display_name": "Google Drive",
            "category": IntegrationCategory.CLOUD_STORAGE,
            "integration_type": IntegrationType.API,
            "description": "Cloud storage and file synchronization",
            "auth_type": AuthType.OAUTH2,
            "configuration_schema": {},
            "supported_actions": [{"name": "upload_file", "description": "Upload a file to Drive"}],
            "provider_name": "Google LLC",
            "is_verified": True,
            "icon_url": "https://cdn.worldvectorlogo.com/logos/google-drive-2020.svg",
        },
        {
            "name": "Salesforce",
            "slug": "salesforce",
            "display_name": "Salesforce",
            "category": IntegrationCategory.CRM,
            "integration_type": IntegrationType.API,
            "description": "Customer relationship management platform",
            "auth_type": AuthType.OAUTH2,
            "configuration_schema": {},
            "supported_actions": [{"name": "create_lead", "description": "Create a new lead"}],
            "provider_name": "Salesforce Inc",
            "is_verified": True,
            "icon_url": "https://cdn.worldvectorlogo.com/logos/salesforce-2.svg",
        },
        {
            "name": "Stripe",
            "slug": "stripe",
            "display_name": "Stripe",
            "category": IntegrationCategory.FINANCE,
            "integration_type": IntegrationType.API,
            "description": "Payment processing platform",
            "auth_type": AuthType.API_KEY,
            "configuration_schema": {},
            "supported_actions": [{"name": "create_charge", "description": "Create a payment charge"}],
            "provider_name": "Stripe Inc",
            "is_verified": True,
            "icon_url": "https://cdn.worldvectorlogo.com/logos/stripe-4.svg",
        },
        {
            "name": "Mailchimp",
            "slug": "mailchimp",
            "display_name": "Mailchimp",
            "category": IntegrationCategory.MARKETING,
            "integration_type": IntegrationType.API,
            "description": "Email marketing automation platform",
            "auth_type": AuthType.API_KEY,
            "configuration_schema": {},
            "supported_actions": [{"name": "add_subscriber", "description": "Add subscriber to list"}],
            "provider_name": "Intuit Mailchimp",
            "is_verified": True,
            "icon_url": "https://cdn.worldvectorlogo.com/logos/mailchimp-freddie-icon.svg",
        },
        {
            "name": "Jira",
            "slug": "jira",
            "display_name": "Jira",
            "category": IntegrationCategory.PROJECT_MANAGEMENT,
            "integration_type": IntegrationType.API,
            "description": "Project tracking and agile management",
            "auth_type": AuthType.API_KEY,
            "configuration_schema": {},
            "supported_actions": [{"name": "create_ticket", "description": "Create a new ticket"}],
            "provider_name": "Atlassian",
            "is_verified": True,
            "icon_url": "https://cdn.worldvectorlogo.com/logos/jira-1.svg",
        },
        {
            "name": "Zendesk",
            "slug": "zendesk",
            "display_name": "Zendesk",
            "category": IntegrationCategory.SUPPORT,
            "integration_type": IntegrationType.API,
            "description": "Customer support and ticketing system",
            "auth_type": AuthType.API_KEY,
            "configuration_schema": {},
            "supported_actions": [{"name": "create_ticket", "description": "Create a support ticket"}],
            "provider_name": "Zendesk Inc",
            "is_verified": True,
            "icon_url": "https://cdn.worldvectorlogo.com/logos/zendesk.svg",
        }
    ]

    created = []
    skipped = []
    for data in integrations_data:
        try:
            # Check if integration already exists
            from sqlalchemy import select
            from backend.shared.integration_models import IntegrationModel

            stmt = select(IntegrationModel).where(IntegrationModel.slug == data["slug"])
            result = await db.execute(stmt)
            existing = result.scalar_one_or_none()

            if existing:
                skipped.append(data["name"])
                continue

            integration = await service.register_integration(**data)
            await db.commit()
            created.append(integration.name)
        except Exception as e:
            await db.rollback()
            print(f"Error creating {data['name']}: {e}")

    return {
        "success": True,
        "created_count": len(created),
        "skipped_count": len(skipped),
        "created": created,
        "skipped": skipped
    }


@router.post("/marketplace-agents")
async def seed_marketplace_agents(db: AsyncSession = Depends(get_db)):
    """Seed sample marketplace agents."""
    from sqlalchemy import text
    import json

    agents_data = [
        # Customer Service
        {
            "name": "Customer Support Agent",
            "slug": "customer-support-agent",
            "tagline": "AI-powered customer support automation",
            "description": "Automatically handle customer inquiries, tickets, and support requests with natural language understanding. Perfect for e-commerce, SaaS, and service businesses.",
            "category": "customer_service",
            "visibility": "public",
            "pricing": "free",
            "agent_config": {
                "model": "gpt-4",
                "temperature": 0.7,
                "system_prompt": """You are a professional customer support agent. Follow these guidelines:

RESPONSE FRAMEWORK:
1. Acknowledge the customer's concern with empathy
2. Identify the core issue from their message
3. Provide a clear, actionable solution
4. Offer additional help proactively

TONE: Friendly but professional. Use "I" not "we". Be concise - aim for 3-4 sentences max unless complex.

ESCALATION TRIGGERS - Flag for human review if:
- Customer mentions legal action, BBB, or social media complaints
- Refund request over $500
- Repeated contacts (3+) about same issue
- Abusive language detected

OUTPUT FORMAT:
{
  "response": "Your reply to the customer",
  "sentiment": "positive|neutral|negative|angry",
  "category": "billing|technical|shipping|product|general",
  "escalate": true/false,
  "escalation_reason": "reason if escalate is true"
}""",
                "tools": ["knowledge_base_search", "order_lookup", "refund_process"]
            },
            "tags": ["support", "automation", "customer-service", "tickets"],
        },
        {
            "name": "Ticket Classifier",
            "slug": "ticket-classifier",
            "tagline": "Auto-route and prioritize support tickets",
            "description": "Automatically classify, prioritize, and route incoming support tickets to the right team. Reduces response times and improves customer satisfaction.",
            "category": "customer_service",
            "visibility": "public",
            "pricing": "freemium",
            "agent_config": {
                "model": "gpt-4o-mini",
                "temperature": 0.2,
                "system_prompt": """You are a ticket classification system. Analyze incoming support tickets and output structured classification.

CLASSIFICATION SCHEMA:

Categories:
- billing: Payments, invoices, refunds, subscriptions, pricing
- technical: Bugs, errors, integrations, API issues, performance
- account: Login, password, permissions, profile, security
- product: Features, how-to, documentation, feedback
- shipping: Delivery, tracking, returns, address changes
- urgent: Outages, security incidents, data loss, legal

Priority (P1-P4):
- P1 CRITICAL: Service down, security breach, data loss, legal threats
- P2 HIGH: Major feature broken, billing errors, angry customer
- P3 MEDIUM: Feature request, how-to questions, minor bugs
- P4 LOW: General feedback, documentation, nice-to-have

Teams:
- engineering: Technical issues, bugs, integrations
- billing: Payment, subscription, refunds
- success: Onboarding, training, account management
- security: Access issues, compliance, data requests
- escalations: VIP customers, legal, executive complaints

OUTPUT JSON:
{
  "category": "string",
  "priority": "P1|P2|P3|P4",
  "team": "string",
  "tags": ["array", "of", "tags"],
  "summary": "One-line summary of the issue",
  "suggested_response_template": "template_name or null"
}"""
            },
            "tags": ["support", "classification", "routing", "helpdesk"],
        },
        # Sales
        {
            "name": "Sales Outreach Agent",
            "slug": "sales-outreach-agent",
            "tagline": "Personalized sales outreach at scale",
            "description": "Generate personalized sales emails and follow-ups based on prospect data and engagement patterns. Increase reply rates by 3x.",
            "category": "sales_automation",
            "visibility": "public",
            "pricing": "paid",
            "price_usd": 99.0,
            "agent_config": {
                "model": "gpt-4",
                "temperature": 0.8,
                "system_prompt": """You are an expert B2B sales copywriter. Generate personalized outreach emails that get responses.

PERSONALIZATION REQUIREMENTS:
- Reference specific company details (funding, news, job posts, tech stack)
- Connect their challenges to your solution
- Use their language/terminology from their website
- Mention mutual connections or shared experiences if available

EMAIL STRUCTURE (keep under 150 words):
1. Hook: Personalized opener referencing something specific about them
2. Problem: One sentence about a challenge they likely face
3. Bridge: How you've helped similar companies
4. CTA: Soft ask (not a demo request on first touch)

SUBJECT LINE RULES:
- Under 6 words
- Lowercase (except proper nouns)
- No spam triggers (free, guarantee, act now)
- Personalized when possible

FOLLOW-UP SEQUENCE:
- Email 2 (Day 3): Add value (case study, insight)
- Email 3 (Day 7): Different angle or social proof
- Email 4 (Day 14): Breakup email

INPUT: Prospect data (name, company, role, company info)
OUTPUT JSON:
{
  "subject": "subject line",
  "body": "email body with {{first_name}} merge tags",
  "follow_ups": [{"day": 3, "subject": "...", "body": "..."}],
  "personalization_points": ["what was personalized"]
}""",
                "tools": ["linkedin_lookup", "company_research", "email_validator"]
            },
            "tags": ["sales", "outreach", "automation", "email"],
        },
        {
            "name": "Lead Qualifier",
            "slug": "lead-qualifier",
            "tagline": "Score and qualify leads automatically",
            "description": "AI-powered lead scoring based on firmographic data, engagement signals, and behavioral patterns. Focus your sales team on the hottest leads.",
            "category": "sales_automation",
            "visibility": "public",
            "pricing": "paid",
            "price_usd": 149.0,
            "agent_config": {
                "model": "claude-3-sonnet",
                "temperature": 0.3,
                "system_prompt": """You are a lead qualification expert using the BANT+C framework.

SCORING MODEL (0-100 points):

BUDGET (25 pts max):
- Enterprise ($100K+): 25 pts
- Mid-market ($25-100K): 20 pts
- SMB ($5-25K): 15 pts
- Startup (<$5K): 10 pts
- Unknown: 5 pts

AUTHORITY (20 pts max):
- C-level/VP: 20 pts
- Director: 15 pts
- Manager: 10 pts
- Individual contributor: 5 pts

NEED (25 pts max):
- Explicit pain point mentioned: 25 pts
- Implicit need from behavior: 15 pts
- General interest: 10 pts
- Unknown: 5 pts

TIMELINE (15 pts max):
- Immediate (this month): 15 pts
- Short-term (this quarter): 12 pts
- Medium-term (this year): 8 pts
- Long-term/Unknown: 3 pts

COMPANY FIT (15 pts max):
- Ideal ICP match: 15 pts
- Good fit: 12 pts
- Moderate fit: 8 pts
- Poor fit: 3 pts

QUALIFICATION TIERS:
- 80-100: HOT - Immediate outreach, fast-track to AE
- 60-79: WARM - Nurture with high-value content, SDR follow-up
- 40-59: COOL - Add to nurture sequence, monitor engagement
- 0-39: COLD - Marketing automation only

OUTPUT JSON:
{
  "score": 0-100,
  "tier": "HOT|WARM|COOL|COLD",
  "scores": {"budget": X, "authority": X, "need": X, "timeline": X, "fit": X},
  "qualification_notes": "Key insights",
  "recommended_action": "Specific next step",
  "missing_info": ["data points to gather"]
}"""
            },
            "tags": ["sales", "leads", "scoring", "crm"],
        },
        # Engineering
        {
            "name": "Code Review Agent",
            "slug": "code-review-agent",
            "tagline": "Automated code review and suggestions",
            "description": "Review pull requests, suggest improvements, and catch potential bugs before they reach production. Supports Python, JavaScript, TypeScript, and more.",
            "category": "engineering",
            "visibility": "public",
            "pricing": "free",
            "agent_config": {
                "model": "claude-3-opus",
                "temperature": 0.2,
                "system_prompt": """You are a senior software engineer conducting code reviews. Be thorough but constructive.

REVIEW CHECKLIST:

1. SECURITY (Critical)
   - SQL injection, XSS, CSRF vulnerabilities
   - Hardcoded secrets or credentials
   - Unsafe deserialization
   - Missing input validation
   - Insecure dependencies

2. BUGS & LOGIC
   - Null pointer / undefined access
   - Off-by-one errors
   - Race conditions
   - Resource leaks (memory, file handles, connections)
   - Error handling gaps

3. PERFORMANCE
   - N+1 queries
   - Missing indexes
   - Unnecessary computation in loops
   - Memory-inefficient patterns
   - Missing caching opportunities

4. CODE QUALITY
   - Function length (flag >50 lines)
   - Complexity (flag nested >3 levels)
   - DRY violations
   - Unclear naming
   - Missing or outdated comments

5. TESTING
   - Test coverage for new code
   - Edge cases covered
   - Mocking appropriateness

SEVERITY LEVELS:
- BLOCKER: Must fix before merge (security, data loss risk)
- MAJOR: Should fix, creates tech debt
- MINOR: Nice to fix, style/readability
- NIT: Optional, personal preference

OUTPUT FORMAT:
{
  "summary": "Overall assessment in 2-3 sentences",
  "approval": "APPROVE|REQUEST_CHANGES|COMMENT",
  "issues": [
    {
      "file": "path/to/file.py",
      "line": 42,
      "severity": "BLOCKER|MAJOR|MINOR|NIT",
      "category": "security|bug|performance|quality|testing",
      "issue": "What's wrong",
      "suggestion": "How to fix it",
      "code_suggestion": "optional code snippet"
    }
  ],
  "praise": ["Things done well - be specific"]
}""",
                "tools": ["github_api", "dependency_check", "code_search"]
            },
            "tags": ["developer", "code-review", "quality", "github"],
        },
        {
            "name": "Documentation Generator",
            "slug": "documentation-generator",
            "tagline": "Auto-generate code documentation",
            "description": "Automatically generate comprehensive documentation for your codebase, including API docs, README files, and inline comments.",
            "category": "engineering",
            "visibility": "public",
            "pricing": "freemium",
            "agent_config": {
                "model": "gpt-4o",
                "temperature": 0.4,
                "system_prompt": """You are a technical writer specializing in developer documentation.

DOCUMENTATION TYPES:

1. FUNCTION/METHOD DOCSTRINGS:
   - One-line summary (what it does, not how)
   - Args with types and descriptions
   - Returns with type and description
   - Raises for exceptions
   - Example usage for complex functions

2. CLASS DOCUMENTATION:
   - Purpose and responsibility
   - Key attributes
   - Usage example
   - Relationship to other classes

3. API ENDPOINT DOCS:
   - HTTP method and path
   - Description of what it does
   - Request parameters (path, query, body)
   - Response schema with examples
   - Error responses
   - Authentication requirements

4. README STRUCTURE:
   - Project name and one-line description
   - Badges (build, coverage, version)
   - Quick start (install + basic usage)
   - Features list
   - Configuration
   - API reference link
   - Contributing guidelines
   - License

STYLE GUIDELINES:
- Use active voice
- Keep sentences short (<20 words)
- Lead with the most important information
- Use code formatting for code references
- Include examples for anything non-obvious

OUTPUT: Generate documentation in the appropriate format (docstring, markdown, OpenAPI) based on input."""
            },
            "tags": ["developer", "documentation", "api-docs", "automation"],
        },
        # Marketing
        {
            "name": "Content Marketing Agent",
            "slug": "content-marketing-agent",
            "tagline": "Generate blog posts and social media content",
            "description": "Create SEO-optimized blog posts, social media content, and marketing materials tailored to your brand voice. Includes keyword research and competitor analysis.",
            "category": "marketing",
            "visibility": "public",
            "pricing": "paid",
            "price_usd": 49.0,
            "agent_config": {
                "model": "gpt-4",
                "temperature": 0.8,
                "system_prompt": """You are a content marketing strategist who creates engaging, SEO-optimized content.

BLOG POST FRAMEWORK:

1. HEADLINE (follow these formulas):
   - How to [Achieve Desired Outcome] in [Timeframe]
   - [Number] [Adjective] Ways to [Achieve Goal]
   - The Complete Guide to [Topic]
   - Why [Common Belief] Is Wrong (And What to Do Instead)

2. STRUCTURE:
   - Hook (first 100 words must grab attention)
   - Promise (what reader will learn)
   - Body (H2s every 300 words, bullet points, examples)
   - Conclusion with CTA

3. SEO REQUIREMENTS:
   - Primary keyword in title, H1, first paragraph, conclusion
   - Secondary keywords in H2s naturally
   - Meta description: 155 chars, includes keyword, has CTA
   - Internal links: 2-3 to related content
   - External links: 1-2 to authoritative sources

4. READABILITY:
   - Grade level: 8th grade or below
   - Sentences: 20 words max average
   - Paragraphs: 3-4 sentences max
   - Use transition words

CONTENT TYPES OUTPUT:
{
  "blog_post": {
    "title": "...",
    "meta_description": "...",
    "slug": "url-friendly-slug",
    "content": "Full markdown content",
    "word_count": 1500,
    "primary_keyword": "...",
    "secondary_keywords": []
  },
  "social_posts": {
    "linkedin": "...",
    "twitter": "...",
    "facebook": "..."
  },
  "email_snippet": "Newsletter teaser"
}"""
            },
            "tags": ["marketing", "content", "seo", "social-media"],
        },
        {
            "name": "Social Media Manager",
            "slug": "social-media-manager",
            "tagline": "Automate your social media presence",
            "description": "Schedule posts, engage with followers, and analyze performance across all major social platforms. Maintain a consistent brand voice automatically.",
            "category": "marketing",
            "visibility": "public",
            "pricing": "paid",
            "price_usd": 79.0,
            "agent_config": {
                "model": "gpt-4o-mini",
                "temperature": 0.8,
                "system_prompt": """You are a social media manager who creates platform-optimized content.

PLATFORM SPECIFICATIONS:

LINKEDIN:
- Tone: Professional, insightful, thought leadership
- Length: 1300 chars optimal (up to 3000)
- Format: Hook line, line break, body with line breaks, CTA
- Best content: Industry insights, career advice, company news
- Hashtags: 3-5 relevant ones at end

TWITTER/X:
- Tone: Conversational, punchy, shareable
- Length: 280 chars max (240 optimal for engagement)
- Format: One strong point per tweet, thread for complex topics
- Best content: Hot takes, tips, quotes, engagement questions
- Hashtags: 1-2 max, only if trending/relevant

INSTAGRAM:
- Tone: Visual-first, authentic, community-focused
- Caption: 125 chars visible (2200 max)
- Format: Hook in first line, value in body, CTA at end
- Hashtags: 20-30 in first comment (research-backed)
- Best content: Behind-scenes, user content, tutorials

ENGAGEMENT REPLIES:
- Respond within brand voice
- Add value (don't just say "thanks!")
- Ask follow-up questions to continue conversation
- Flag negative sentiment for human review

OUTPUT FORMAT:
{
  "posts": {
    "linkedin": {"content": "...", "hashtags": [], "best_time": "Tuesday 10am"},
    "twitter": {"content": "...", "hashtags": [], "best_time": "..."},
    "instagram": {"caption": "...", "hashtags": [], "alt_text": "..."}
  },
  "content_calendar_slot": "suggested date/time",
  "engagement_priority": "high|medium|low"
}"""
            },
            "tags": ["marketing", "social-media", "scheduling", "engagement"],
        },
        # Analytics
        {
            "name": "Data Analysis Agent",
            "slug": "data-analysis-agent",
            "tagline": "Analyze data and generate insights",
            "description": "Process datasets, generate visualizations, and provide actionable insights from your business data. Supports SQL, Python, and natural language queries.",
            "category": "analytics",
            "visibility": "public",
            "pricing": "free",
            "agent_config": {
                "model": "gpt-4",
                "temperature": 0.3,
                "system_prompt": """You are a data analyst who transforms raw data into actionable insights.

ANALYSIS FRAMEWORK:

1. UNDERSTAND THE QUESTION
   - Clarify what decision this analysis will inform
   - Identify the key metrics that matter
   - Note any constraints or assumptions

2. DATA EXPLORATION
   - Check data quality (nulls, outliers, distributions)
   - Identify relevant columns and relationships
   - Note any data limitations

3. ANALYSIS APPROACH
   - Descriptive: What happened? (trends, patterns)
   - Diagnostic: Why did it happen? (correlations, segments)
   - Predictive: What might happen? (forecasts, probabilities)
   - Prescriptive: What should we do? (recommendations)

4. INSIGHTS STRUCTURE
   - Lead with the "so what" - the business implication
   - Support with specific numbers
   - Provide context (vs. last period, vs. benchmark)
   - Include confidence level

SQL QUERY GUIDELINES:
- Always use explicit JOINs (not implicit)
- Include WHERE clauses to limit data when exploring
- Use CTEs for readability on complex queries
- Add comments explaining business logic

OUTPUT FORMAT:
{
  "summary": "2-3 sentence executive summary",
  "key_findings": [
    {"insight": "...", "metric": "...", "change": "+/-X%", "significance": "high|medium|low"}
  ],
  "sql_query": "The query used if applicable",
  "visualization_recommendation": "chart type and what to show",
  "recommended_actions": ["Specific action items"],
  "caveats": ["Data limitations or assumptions"],
  "follow_up_questions": ["What to investigate next"]
}""",
                "tools": ["sql_executor", "python_executor", "chart_generator"]
            },
            "tags": ["analytics", "data", "insights", "visualization"],
        },
        # Productivity
        {
            "name": "Meeting Summarizer",
            "slug": "meeting-summarizer",
            "tagline": "Summarize meetings and extract action items",
            "description": "Automatically transcribe meetings, generate summaries, and extract action items and decisions. Integrates with Zoom, Teams, and Google Meet.",
            "category": "productivity",
            "visibility": "public",
            "pricing": "paid",
            "price_usd": 29.0,
            "agent_config": {
                "model": "claude-3-sonnet",
                "temperature": 0.3,
                "system_prompt": """You are an expert meeting analyst who extracts maximum value from meeting transcripts.

EXTRACTION FRAMEWORK:

1. MEETING METADATA
   - Type: standup, planning, review, 1:1, all-hands, client call
   - Duration and participants
   - Meeting effectiveness score (1-10)

2. SUMMARY (Executive Brief)
   - 3-5 bullet points max
   - Lead with outcomes, not process
   - Highlight any decisions made
   - Note any blockers raised

3. ACTION ITEMS (be specific)
   - WHO: Specific person assigned
   - WHAT: Clear, actionable task (verb + object)
   - WHEN: Due date if mentioned, otherwise flag as "TBD"
   - Context: Why this matters

4. DECISIONS MADE
   - The decision itself
   - Key reasoning/factors considered
   - Who made or approved the decision
   - Impact/next steps

5. KEY DISCUSSION POINTS
   - Topics debated but not resolved
   - Open questions that need follow-up
   - Risks or concerns raised

6. PARKING LOT
   - Topics mentioned but deferred
   - Ideas for future consideration

OUTPUT FORMAT:
{
  "meeting_type": "...",
  "duration_minutes": X,
  "participants": ["..."],
  "effectiveness_score": X,
  "executive_summary": ["bullet points"],
  "action_items": [
    {"owner": "Name", "task": "...", "due": "date or TBD", "priority": "high|medium|low"}
  ],
  "decisions": [
    {"decision": "...", "made_by": "...", "rationale": "..."}
  ],
  "open_questions": ["..."],
  "parking_lot": ["..."],
  "follow_up_meeting_needed": true/false,
  "suggested_attendees_for_followup": ["..."]
}"""
            },
            "tags": ["productivity", "meetings", "automation", "transcription"],
        },
        {
            "name": "Email Assistant",
            "slug": "email-assistant",
            "tagline": "Smart email drafting and organization",
            "description": "Draft professional emails, sort your inbox, and automate common email workflows. Save 2+ hours per day on email management.",
            "category": "productivity",
            "visibility": "public",
            "pricing": "freemium",
            "agent_config": {
                "model": "gpt-4o-mini",
                "temperature": 0.6,
                "system_prompt": """You are an executive assistant specializing in email communication.

EMAIL DRAFTING:

1. TONE MATCHING
   - Formal: External clients, executives, first contact
   - Professional: Colleagues, vendors, ongoing relationships
   - Casual: Team members, established relationships

2. LENGTH GUIDELINES
   - Request/ask: 3-5 sentences
   - Information sharing: 5-7 sentences with bullets
   - Complex topics: Use numbered sections

3. STRUCTURE
   - Subject: Action-oriented, specific (not "Quick question")
   - Opening: Context or purpose immediately
   - Body: One idea per paragraph, most important first
   - Close: Clear next step or CTA
   - Sign-off: Match formality to relationship

4. COMMON SCENARIOS
   - Meeting request: Purpose, proposed times, duration
   - Follow-up: Reference previous conversation, new info/ask
   - Decline gracefully: Appreciate, decline with brief reason, offer alternative
   - Deliver bad news: Direct but empathetic, explain why, next steps

EMAIL TRIAGE CLASSIFICATION:
- URGENT: Needs response today (client escalation, exec request, deadline)
- IMPORTANT: Needs response within 48h (business decisions, project updates)
- ROUTINE: Weekly batch okay (newsletters, FYIs, low-priority requests)
- DELEGATE: Someone else should handle
- ARCHIVE: No action needed, just FYI

OUTPUT FORMAT (drafting):
{
  "subject": "...",
  "body": "...",
  "tone": "formal|professional|casual",
  "send_time_suggestion": "now|schedule for X",
  "cc_suggestion": ["if applicable"],
  "follow_up_reminder": "date if needed"
}

OUTPUT FORMAT (triage):
{
  "classification": "urgent|important|routine|delegate|archive",
  "summary": "one line",
  "suggested_action": "...",
  "delegate_to": "name if applicable",
  "response_needed_by": "date/time"
}"""
            },
            "tags": ["productivity", "email", "automation", "organization"],
        },
        # Data Processing
        {
            "name": "Document Processor",
            "slug": "document-processor",
            "tagline": "Extract data from PDFs and documents",
            "description": "Automatically extract structured data from invoices, contracts, forms, and other documents. Supports OCR for scanned documents.",
            "category": "data_processing",
            "visibility": "public",
            "pricing": "paid",
            "price_usd": 59.0,
            "agent_config": {
                "model": "gpt-4-vision",
                "temperature": 0.1,
                "system_prompt": """You are a document processing specialist who extracts structured data from unstructured documents.

DOCUMENT TYPES & EXTRACTION SCHEMAS:

1. INVOICES
{
  "vendor": {"name": "", "address": "", "tax_id": ""},
  "invoice_number": "",
  "invoice_date": "YYYY-MM-DD",
  "due_date": "YYYY-MM-DD",
  "line_items": [{"description": "", "quantity": 0, "unit_price": 0.00, "total": 0.00}],
  "subtotal": 0.00,
  "tax": 0.00,
  "total": 0.00,
  "payment_terms": "",
  "currency": "USD"
}

2. CONTRACTS
{
  "contract_type": "NDA|MSA|SOW|Employment|Other",
  "parties": [{"name": "", "role": "Party A|Party B", "address": ""}],
  "effective_date": "YYYY-MM-DD",
  "expiration_date": "YYYY-MM-DD or null if perpetual",
  "key_terms": ["summary of important clauses"],
  "payment_terms": "",
  "termination_clause": "",
  "governing_law": "",
  "signatures": [{"name": "", "title": "", "date": ""}]
}

3. RECEIPTS
{
  "merchant": "",
  "date": "YYYY-MM-DD",
  "items": [{"description": "", "amount": 0.00}],
  "subtotal": 0.00,
  "tax": 0.00,
  "total": 0.00,
  "payment_method": "",
  "category": "meals|travel|office|software|other"
}

EXTRACTION GUIDELINES:
- If a field is not found, use null (not empty string)
- Normalize dates to YYYY-MM-DD format
- Normalize currency amounts to 2 decimal places
- Flag low-confidence extractions with confidence score
- Preserve original text for ambiguous fields

OUTPUT:
{
  "document_type": "invoice|contract|receipt|form|other",
  "confidence": 0.0-1.0,
  "extracted_data": {schema based on type},
  "warnings": ["any extraction issues"],
  "raw_text": "full text if OCR was needed"
}""",
                "tools": ["ocr_processor", "pdf_parser", "table_extractor"]
            },
            "tags": ["data", "documents", "extraction", "ocr"],
        },
    ]

    created = []
    skipped = []
    for data in agents_data:
        try:
            # Check if agent already exists
            from sqlalchemy import select
            from backend.shared.marketplace_models import MarketplaceAgent

            stmt = select(MarketplaceAgent).where(MarketplaceAgent.slug == data["slug"])
            result = await db.execute(stmt)
            existing = result.scalar_one_or_none()

            if existing:
                skipped.append(data["name"])
                continue

            # Use raw SQL (columns are VARCHAR, not enum types)
            sql = text("""
                INSERT INTO marketplace_agents (
                    name, slug, tagline, description,
                    publisher_id, publisher_name,
                    category, visibility, pricing, price_usd,
                    agent_config, tags,
                    version, is_verified, is_featured, is_active, is_deprecated,
                    published_at, required_integrations, required_capabilities, screenshots
                ) VALUES (
                    :name, :slug, :tagline, :description,
                    :publisher_id, :publisher_name,
                    :category, :visibility,
                    :pricing, :price_usd,
                    CAST(:agent_config AS jsonb), CAST(:tags AS jsonb),
                    :version, :is_verified, :is_featured, :is_active, false,
                    NOW(), CAST(:required_integrations AS jsonb), CAST(:required_capabilities AS jsonb), CAST(:screenshots AS jsonb)
                )
            """)

            await db.execute(sql, {
                "name": data["name"],
                "slug": data["slug"],
                "tagline": data["tagline"],
                "description": data["description"],
                "publisher_id": "demo_publisher",
                "publisher_name": "Demo Publisher",
                "category": data["category"],
                "visibility": data["visibility"],
                "pricing": data["pricing"],
                "price_usd": data.get("price_usd"),
                "agent_config": json.dumps(data["agent_config"]),
                "tags": json.dumps(data["tags"]),
                "version": "1.0.0",
                "is_verified": True,
                "is_featured": True,
                "is_active": True,
                "required_integrations": "[]",
                "required_capabilities": "[]",
                "screenshots": "[]",
            })
            await db.commit()
            created.append(data["name"])
        except Exception as e:
            await db.rollback()
            print(f"Error creating {data['name']}: {e}")

    return {
        "success": True,
        "created_count": len(created),
        "skipped_count": len(skipped),
        "created": created,
        "skipped": skipped
    }


@router.post("/workflows")
async def seed_workflows(db: AsyncSession = Depends(get_db)):
    """Seed sample workflows with nodes, edges, and execution history."""
    from sqlalchemy import text
    import json
    import uuid

    # Deterministic UUIDs from names so re-seeding is idempotent
    def name_to_uuid(name: str) -> str:
        import hashlib
        h = hashlib.md5(name.encode()).hexdigest()
        return f"{h[:8]}-{h[8:12]}-{h[12:16]}-{h[16:20]}-{h[20:32]}"

    # Node data helper — matches the frontend's AgentNodeData shape
    def worker_node(nid, label, pos, model="gpt-4o", prompt="", temperature=0.7):
        return {"id": nid, "type": "worker", "position": pos, "data": {
            "label": label, "type": "worker",
            "modelSelection": "specific", "llmModel": model,
            "systemPrompt": prompt, "temperature": temperature,
            "capabilities": ["processing"],
        }}

    def trigger_node(nid, label, pos, trigger_type="webhook"):
        return {"id": nid, "type": "trigger", "position": pos, "data": {
            "label": label, "type": "trigger",
            "triggerConfig": {"triggerType": trigger_type},
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

    workflows_data = [
        {
            "workflow_id": name_to_uuid("Customer Support Triage"),
            "name": "Customer Support Triage",
            "description": "Automatically classify incoming support tickets, route to the right team, and send an acknowledgment to the customer via Slack.",
            "tags": ["support", "automation", "slack", "triage"],
            "status": "active",
            "nodes": [
                trigger_node("trigger-1", "New Ticket Received", {"x": 100, "y": 200}, "webhook"),
                worker_node("classify-1", "Classify Ticket", {"x": 350, "y": 200}, "gpt-4o-mini",
                            "Classify this support ticket into: billing, technical, account, or product. Also assign priority P1-P4.\n\nTicket: {{trigger-1.text}}", 0.2),
                condition_node("condition-1", "Priority Check", {"x": 600, "y": 200}),
                integration_node("slack-1", "Alert On-Call (P1)", {"x": 850, "y": 100}, "slack", "send_message",
                                 {"channel": "#urgent-support", "message": "P1 ALERT: {{classify-1.text}}"}),
                integration_node("slack-2", "Notify Team", {"x": 850, "y": 300}, "slack", "send_message",
                                 {"channel": "#support-queue", "message": "New ticket: {{classify-1.text}}"}),
                print_node("done-1", "Complete", {"x": 1100, "y": 200}),
            ],
            "edges": [
                {"id": "e1", "source": "trigger-1", "target": "classify-1"},
                {"id": "e2", "source": "classify-1", "target": "condition-1"},
                {"id": "e3", "source": "condition-1", "target": "slack-1", "label": "P1"},
                {"id": "e4", "source": "condition-1", "target": "slack-2", "label": "Other"},
                {"id": "e5", "source": "slack-1", "target": "done-1"},
                {"id": "e6", "source": "slack-2", "target": "done-1"},
            ],
            "trigger_type": "webhook",
            "total_executions": 847,
            "successful_executions": 823,
            "failed_executions": 24,
            "avg_execution_time_seconds": 3.2,
        },
        {
            "workflow_id": name_to_uuid("Content Publishing Pipeline"),
            "name": "Content Publishing Pipeline",
            "description": "Generate a blog post from a topic, review it with AI, then publish to CMS and share on social media channels.",
            "tags": ["content", "marketing", "blog", "social-media"],
            "status": "active",
            "nodes": [
                trigger_node("trigger-1", "New Topic Submitted", {"x": 100, "y": 200}, "manual"),
                worker_node("draft-1", "Generate Draft", {"x": 350, "y": 200}, "gpt-4",
                            "Write a 1500-word SEO-optimized blog post about: {{trigger-1.text}}. Include H2 headers, bullet points, and a conclusion with CTA.", 0.8),
                worker_node("review-1", "Editorial Review", {"x": 600, "y": 200}, "claude-3-5-sonnet",
                            "Review this blog post for grammar, tone, factual accuracy, and SEO. Return corrected version.\n\nDraft: {{draft-1.text}}", 0.3),
                worker_node("social-1", "Generate Social Posts", {"x": 850, "y": 100}, "gpt-4o-mini",
                            "Create social media posts for this article:\n1. LinkedIn (1300 chars)\n2. Twitter (280 chars)\n3. Instagram caption (125 chars)\n\nArticle: {{review-1.text}}", 0.7),
                integration_node("slack-1", "Notify Marketing Team", {"x": 850, "y": 300}, "slack", "send_message",
                                 {"channel": "#content-published", "message": "New blog post published: {{trigger-1.text}}"}),
                print_node("done-1", "Complete", {"x": 1100, "y": 200}),
            ],
            "edges": [
                {"id": "e1", "source": "trigger-1", "target": "draft-1"},
                {"id": "e2", "source": "draft-1", "target": "review-1"},
                {"id": "e3", "source": "review-1", "target": "social-1"},
                {"id": "e4", "source": "review-1", "target": "slack-1"},
                {"id": "e5", "source": "social-1", "target": "done-1"},
                {"id": "e6", "source": "slack-1", "target": "done-1"},
            ],
            "trigger_type": "manual",
            "total_executions": 156,
            "successful_executions": 148,
            "failed_executions": 8,
            "avg_execution_time_seconds": 45.7,
        },
        {
            "workflow_id": name_to_uuid("Lead Enrichment & Scoring"),
            "name": "Lead Enrichment & Scoring",
            "description": "When a new lead comes in from Salesforce, enrich with company data, score using AI, and route to the right sales rep.",
            "tags": ["sales", "leads", "crm", "automation"],
            "status": "active",
            "nodes": [
                trigger_node("trigger-1", "New Salesforce Lead", {"x": 100, "y": 200}, "webhook"),
                integration_node("enrich-1", "Enrich Company Data", {"x": 350, "y": 200}, "salesforce", "create_lead",
                                 {"domain": "{{trigger-1.text}}"}),
                worker_node("score-1", "Score & Qualify Lead", {"x": 600, "y": 200}, "claude-3-5-sonnet",
                            "Score this lead 0-100 using BANT framework.\n\nLead: {{trigger-1.text}}\nCompany info: {{enrich-1.text}}\n\nReturn JSON with score, tier (HOT/WARM/COOL/COLD), and recommended action.", 0.3),
                condition_node("condition-1", "Route by Score", {"x": 850, "y": 200}),
                integration_node("sf-hot", "Assign to AE (Hot)", {"x": 1100, "y": 100}, "salesforce", "create_lead",
                                 {"status": "Qualified"}),
                integration_node("sf-nurture", "Add to Nurture", {"x": 1100, "y": 300}, "salesforce", "create_lead",
                                 {"status": "Nurturing"}),
                print_node("done-1", "Complete", {"x": 1350, "y": 200}),
            ],
            "edges": [
                {"id": "e1", "source": "trigger-1", "target": "enrich-1"},
                {"id": "e2", "source": "enrich-1", "target": "score-1"},
                {"id": "e3", "source": "score-1", "target": "condition-1"},
                {"id": "e4", "source": "condition-1", "target": "sf-hot", "label": "Hot"},
                {"id": "e5", "source": "condition-1", "target": "sf-nurture", "label": "Warm/Cold"},
                {"id": "e6", "source": "sf-hot", "target": "done-1"},
                {"id": "e7", "source": "sf-nurture", "target": "done-1"},
            ],
            "trigger_type": "webhook",
            "total_executions": 2341,
            "successful_executions": 2298,
            "failed_executions": 43,
            "avg_execution_time_seconds": 8.4,
        },
        {
            "workflow_id": name_to_uuid("Incident Response Automation"),
            "name": "Incident Response Automation",
            "description": "When PagerDuty triggers an alert, analyze logs, create a Jira ticket, notify the team on Slack, and start a Zoom bridge.",
            "tags": ["devops", "incident", "pagerduty", "automation"],
            "status": "active",
            "nodes": [
                trigger_node("trigger-1", "PagerDuty Alert", {"x": 100, "y": 200}, "webhook"),
                worker_node("analyze-1", "Analyze Incident", {"x": 350, "y": 200}, "gpt-4",
                            "Analyze this PagerDuty alert and recent logs. Determine severity (SEV1-SEV4), likely root cause, and suggested remediation steps.\n\nAlert: {{trigger-1.text}}", 0.2),
                integration_node("jira-1", "Create Jira Incident", {"x": 600, "y": 100}, "jira", "create_ticket",
                                 {"project": "INC", "summary": "{{analyze-1.text}}"}),
                integration_node("slack-1", "Alert #incidents", {"x": 600, "y": 300}, "slack", "send_message",
                                 {"channel": "#incidents", "message": "{{analyze-1.text}}"}),
                print_node("done-1", "Complete", {"x": 850, "y": 200}),
            ],
            "edges": [
                {"id": "e1", "source": "trigger-1", "target": "analyze-1"},
                {"id": "e2", "source": "analyze-1", "target": "jira-1"},
                {"id": "e3", "source": "analyze-1", "target": "slack-1"},
                {"id": "e4", "source": "jira-1", "target": "done-1"},
                {"id": "e5", "source": "slack-1", "target": "done-1"},
            ],
            "trigger_type": "webhook",
            "total_executions": 89,
            "successful_executions": 85,
            "failed_executions": 4,
            "avg_execution_time_seconds": 5.1,
        },
        {
            "workflow_id": name_to_uuid("AI Code Review Pipeline"),
            "name": "AI Code Review Pipeline",
            "description": "Triggered by GitHub PR webhook — runs AI code review, checks for security vulnerabilities, and posts review comments back to the PR.",
            "tags": ["developer", "github", "code-review", "security"],
            "status": "active",
            "nodes": [
                trigger_node("trigger-1", "GitHub PR Opened", {"x": 100, "y": 200}, "webhook"),
                integration_node("gh-fetch", "Fetch PR Diff", {"x": 350, "y": 200}, "github", "create_issue",
                                 {"repo": "{{trigger-1.text}}"}),
                worker_node("review-1", "Code Review", {"x": 600, "y": 100}, "claude-3-5-sonnet",
                            "Review this PR diff for bugs, code quality, and improvements. Be constructive.\n\nDiff: {{gh-fetch.text}}", 0.2),
                worker_node("security-1", "Security Scan", {"x": 600, "y": 300}, "gpt-4",
                            "Scan this code for security vulnerabilities (OWASP Top 10, injection, XSS, etc).\n\nDiff: {{gh-fetch.text}}", 0.1),
                integration_node("gh-comment", "Post Review Comment", {"x": 850, "y": 200}, "github", "create_issue",
                                 {"body": "## AI Code Review\n{{review-1.text}}\n\n## Security Scan\n{{security-1.text}}"}),
                print_node("done-1", "Complete", {"x": 1100, "y": 200}),
            ],
            "edges": [
                {"id": "e1", "source": "trigger-1", "target": "gh-fetch"},
                {"id": "e2", "source": "gh-fetch", "target": "review-1"},
                {"id": "e3", "source": "gh-fetch", "target": "security-1"},
                {"id": "e4", "source": "review-1", "target": "gh-comment"},
                {"id": "e5", "source": "security-1", "target": "gh-comment"},
                {"id": "e6", "source": "gh-comment", "target": "done-1"},
            ],
            "trigger_type": "webhook",
            "total_executions": 512,
            "successful_executions": 503,
            "failed_executions": 9,
            "avg_execution_time_seconds": 12.3,
        },
        {
            "workflow_id": name_to_uuid("Daily Standup Summarizer"),
            "name": "Daily Standup Summarizer",
            "description": "Collect standup updates from Slack, summarize with AI, identify blockers, and post a team summary to the project channel.",
            "tags": ["productivity", "standup", "slack", "team"],
            "status": "active",
            "nodes": [
                trigger_node("trigger-1", "Daily 9:30 AM", {"x": 100, "y": 200}, "cron"),
                integration_node("slack-fetch", "Fetch Standup Messages", {"x": 350, "y": 200}, "slack", "send_message",
                                 {"channel": "#standups"}),
                worker_node("summarize-1", "Summarize Updates", {"x": 600, "y": 200}, "gpt-4o-mini",
                            "Summarize these standup updates. Group by person. Highlight blockers and dependencies.\n\nUpdates: {{slack-fetch.text}}", 0.3),
                integration_node("slack-post", "Post Summary", {"x": 850, "y": 200}, "slack", "send_message",
                                 {"channel": "#engineering", "message": "Daily Standup Summary\n{{summarize-1.text}}"}),
                print_node("done-1", "Complete", {"x": 1100, "y": 200}),
            ],
            "edges": [
                {"id": "e1", "source": "trigger-1", "target": "slack-fetch"},
                {"id": "e2", "source": "slack-fetch", "target": "summarize-1"},
                {"id": "e3", "source": "summarize-1", "target": "slack-post"},
                {"id": "e4", "source": "slack-post", "target": "done-1"},
            ],
            "trigger_type": "schedule",
            "total_executions": 234,
            "successful_executions": 230,
            "failed_executions": 4,
            "avg_execution_time_seconds": 6.8,
        },
        # ====================================================================
        # NEW TEMPLATES — 10 additional workflow templates
        # ====================================================================
        {
            "workflow_id": name_to_uuid("Customer Onboarding Flow"),
            "name": "Customer Onboarding Flow",
            "description": "Welcome new customers with a personalized email, update CRM record, notify the CSM on Slack, and schedule a 30-day check-in.",
            "tags": ["onboarding", "customer-success", "email", "crm"],
            "status": "active",
            "is_template": True,
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
                            "Generate a 30-day check-in reminder task with the customer name, key metrics to review, and suggested talking points.\n\nCustomer: {{trigger-1.text}}", 0.5),
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
            "total_executions": 423,
            "successful_executions": 418,
            "failed_executions": 5,
            "avg_execution_time_seconds": 4.2,
        },
        {
            "workflow_id": name_to_uuid("Churn Risk Alert"),
            "name": "Churn Risk Alert",
            "description": "Monitor customer usage metrics, run AI churn analysis, alert the CSM with retention recommendations, and create a Jira ticket for follow-up.",
            "tags": ["churn", "retention", "customer-success", "analytics"],
            "status": "active",
            "is_template": True,
            "nodes": [
                trigger_node("trigger-1", "Weekly Usage Report", {"x": 100, "y": 250}, "cron"),
                integration_node("fetch-usage", "Fetch Usage Metrics", {"x": 350, "y": 250}, "salesforce", "create_lead",
                                 {"query": "usage_metrics_last_30d"}),
                worker_node("analyze-1", "Churn Risk Analysis", {"x": 600, "y": 250}, "claude-3-5-sonnet",
                            "Analyze these customer usage metrics for churn risk. For each at-risk account (declining usage >20%, no logins in 7+ days, unresolved support tickets), provide:\n1. Risk score (0-100)\n2. Contributing factors\n3. Recommended retention action\n\nMetrics: {{fetch-usage.text}}", 0.2),
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
            "total_executions": 52,
            "successful_executions": 51,
            "failed_executions": 1,
            "avg_execution_time_seconds": 12.5,
        },
        {
            "workflow_id": name_to_uuid("NPS Survey Processor"),
            "name": "NPS Survey Processor",
            "description": "Collect NPS feedback, run sentiment analysis, route detractors to support for immediate follow-up, and aggregate weekly insights.",
            "tags": ["nps", "feedback", "sentiment", "customer-experience"],
            "status": "active",
            "is_template": True,
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
            "total_executions": 1847,
            "successful_executions": 1839,
            "failed_executions": 8,
            "avg_execution_time_seconds": 2.8,
        },
        {
            "workflow_id": name_to_uuid("CI/CD Quality Gate"),
            "name": "CI/CD Quality Gate",
            "description": "When a PR is created, run AI code review, security vulnerability scan, and auto-approve or block the merge based on findings.",
            "tags": ["ci-cd", "code-review", "security", "github", "quality"],
            "status": "active",
            "is_template": True,
            "nodes": [
                trigger_node("trigger-1", "PR Created", {"x": 100, "y": 250}, "webhook"),
                integration_node("gh-diff", "Fetch PR Diff", {"x": 350, "y": 250}, "github", "create_issue",
                                 {"action": "get_diff", "pr_number": "{{trigger-1.text}}"}),
                worker_node("review-1", "AI Code Review", {"x": 600, "y": 100}, "claude-3-5-sonnet",
                            "Review this PR diff thoroughly. Check for:\n1. Logic bugs (null checks, off-by-one, race conditions)\n2. Code quality (readability, naming, DRY)\n3. Performance issues (N+1 queries, memory leaks)\n4. Test coverage gaps\n\nReturn a structured review with severity (critical/warning/info) per finding.\n\nDiff: {{gh-diff.text}}", 0.2),
                worker_node("security-1", "Security Scan", {"x": 600, "y": 400}, "gpt-4",
                            "Scan this code diff for security vulnerabilities. Check OWASP Top 10:\n- SQL/NoSQL injection\n- XSS / output encoding\n- Auth/authz bypass\n- Secrets in code\n- Insecure deserialization\n- SSRF\n- Path traversal\n\nReturn PASS or FAIL with specific line references.\n\nDiff: {{gh-diff.text}}", 0.1),
                worker_node("verdict-1", "Merge Verdict", {"x": 850, "y": 250}, "gpt-4o-mini",
                            "Based on the code review and security scan results, decide:\n- APPROVE: No critical issues found\n- REQUEST_CHANGES: Critical issues need fixing\n\nCode Review: {{review-1.text}}\nSecurity Scan: {{security-1.text}}\n\nReturn the verdict and a summary comment for the PR.", 0.2),
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
            "total_executions": 1256,
            "successful_executions": 1241,
            "failed_executions": 15,
            "avg_execution_time_seconds": 18.4,
        },
        {
            "workflow_id": name_to_uuid("Incident Post-Mortem Generator"),
            "name": "Incident Post-Mortem Generator",
            "description": "After an incident resolves, gather PagerDuty timeline and Datadog metrics, generate an AI post-mortem document, and publish to Confluence.",
            "tags": ["incident", "post-mortem", "sre", "documentation"],
            "status": "active",
            "is_template": True,
            "nodes": [
                trigger_node("trigger-1", "Incident Resolved", {"x": 100, "y": 250}, "webhook"),
                integration_node("pd-timeline", "Fetch PagerDuty Timeline", {"x": 350, "y": 150}, "jira", "create_ticket",
                                 {"action": "get_incident_timeline", "incident_id": "{{trigger-1.text}}"}),
                integration_node("logs-1", "Fetch Error Logs", {"x": 350, "y": 350}, "slack", "send_message",
                                 {"action": "search_logs", "query": "error incident={{trigger-1.text}}"}),
                worker_node("postmortem-1", "Generate Post-Mortem", {"x": 650, "y": 250}, "claude-3-5-sonnet",
                            "Write a structured incident post-mortem document using the following data.\n\nPagerDuty Timeline: {{pd-timeline.text}}\nError Logs: {{logs-1.text}}\n\nInclude these sections:\n1. Executive Summary (2-3 sentences)\n2. Impact (users affected, duration, revenue impact)\n3. Timeline of Events\n4. Root Cause Analysis (5 Whys)\n5. What Went Well\n6. What Went Wrong\n7. Action Items (with owners and due dates)\n8. Lessons Learned\n\nBe specific and data-driven.", 0.3),
                worker_node("actions-1", "Extract Action Items", {"x": 900, "y": 150}, "gpt-4o-mini",
                            "Extract action items from this post-mortem as structured JSON. Each item should have: title, owner, due_date, priority (P0-P3), category (prevention/detection/response).\n\nPost-mortem: {{postmortem-1.text}}", 0.2),
                integration_node("jira-actions", "Create Jira Tickets", {"x": 1150, "y": 150}, "jira", "create_ticket",
                                 {"project": "SRE", "summary": "Post-mortem action: {{actions-1.text}}"}),
                integration_node("slack-1", "Share Post-Mortem", {"x": 900, "y": 350}, "slack", "send_message",
                                 {"channel": "#incidents", "message": "Post-mortem published for incident {{trigger-1.text}}:\n{{postmortem-1.text}}"}),
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
            "total_executions": 34,
            "successful_executions": 33,
            "failed_executions": 1,
            "avg_execution_time_seconds": 25.7,
        },
        {
            "workflow_id": name_to_uuid("Dependency Update Bot"),
            "name": "Dependency Update Bot",
            "description": "Weekly scan for outdated packages, assess risk with AI, create PRs for safe updates, and auto-merge low-risk patches.",
            "tags": ["dependencies", "security", "github", "automation"],
            "status": "active",
            "is_template": True,
            "nodes": [
                trigger_node("trigger-1", "Weekly Monday 6 AM", {"x": 100, "y": 250}, "cron"),
                integration_node("gh-deps", "Check Outdated Deps", {"x": 350, "y": 250}, "github", "create_issue",
                                 {"action": "list_outdated_dependencies"}),
                worker_node("assess-1", "Risk Assessment", {"x": 600, "y": 250}, "claude-3-5-sonnet",
                            "Assess the risk of updating these dependencies. For each package:\n1. Current vs latest version\n2. Breaking change risk (high/medium/low)\n3. Security advisories\n4. Recommendation: auto-update, manual-review, or skip\n\nDependencies: {{gh-deps.text}}\n\nReturn as JSON array with package_name, current_version, target_version, risk_level, recommendation, and reason.", 0.2),
                condition_node("condition-1", "Safe to Auto-Update?", {"x": 850, "y": 250}),
                integration_node("gh-pr-auto", "Create Auto-Merge PR", {"x": 1100, "y": 100}, "github", "create_issue",
                                 {"action": "create_pr", "title": "chore(deps): auto-update safe dependencies", "body": "{{assess-1.text}}", "auto_merge": True}),
                integration_node("gh-pr-review", "Create Review PR", {"x": 1100, "y": 400}, "github", "create_issue",
                                 {"action": "create_pr", "title": "chore(deps): update dependencies (needs review)", "body": "{{assess-1.text}}", "auto_merge": False}),
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
            "total_executions": 18,
            "successful_executions": 17,
            "failed_executions": 1,
            "avg_execution_time_seconds": 42.3,
        },
        {
            "workflow_id": name_to_uuid("Outbound Email Sequence"),
            "name": "Outbound Email Sequence",
            "description": "Enrich lead data from CRM, generate a personalized multi-touch email sequence with AI, schedule sends, and track engagement.",
            "tags": ["outbound", "email", "sales", "personalization"],
            "status": "active",
            "is_template": True,
            "nodes": [
                trigger_node("trigger-1", "New Lead Assigned", {"x": 100, "y": 250}, "webhook"),
                integration_node("enrich-1", "Enrich Lead Data", {"x": 350, "y": 250}, "salesforce", "create_lead",
                                 {"action": "get_lead_details", "lead_id": "{{trigger-1.text}}"}),
                worker_node("research-1", "Company Research", {"x": 600, "y": 150}, "gpt-4",
                            "Research this company and find relevant talking points for a sales outreach:\n\nLead data: {{enrich-1.text}}\n\nFind: recent news, tech stack signals, hiring patterns, pain points in their industry, and any competitive intelligence. Return structured research brief.", 0.5),
                worker_node("sequence-1", "Generate Email Sequence", {"x": 600, "y": 350}, "claude-3-5-sonnet",
                            "Write a 3-email outbound sequence for this prospect. Use the research to personalize.\n\nLead: {{enrich-1.text}}\nResearch: {{research-1.text}}\n\nEmail 1 (Day 0): Cold intro — pain point hook, 2 sentences max, single CTA\nEmail 2 (Day 3): Value add — share relevant case study or insight\nEmail 3 (Day 7): Breakup — last touch, create urgency\n\nEach email: subject line, body (under 100 words), CTA. Tone: professional but human.", 0.7),
                integration_node("mail-1", "Schedule Email 1", {"x": 900, "y": 150}, "mailchimp", "send_campaign",
                                 {"subject": "{{sequence-1.text}}", "send_at": "immediate"}),
                integration_node("crm-update", "Update CRM Pipeline", {"x": 900, "y": 350}, "salesforce", "create_lead",
                                 {"status": "Outbound Sequence Active", "notes": "3-email sequence started"}),
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
            "total_executions": 678,
            "successful_executions": 661,
            "failed_executions": 17,
            "avg_execution_time_seconds": 9.8,
        },
        {
            "workflow_id": name_to_uuid("Competitor Pricing Monitor"),
            "name": "Competitor Pricing Monitor",
            "description": "Daily scrape of competitor pricing pages, detect changes with AI diff analysis, alert sales team, and update competitive battlecards.",
            "tags": ["competitive-intel", "pricing", "sales", "monitoring"],
            "status": "active",
            "is_template": True,
            "nodes": [
                trigger_node("trigger-1", "Daily 8 AM Scan", {"x": 100, "y": 250}, "cron"),
                worker_node("scrape-1", "Analyze Competitor Pages", {"x": 350, "y": 250}, "gpt-4",
                            "Compare the current competitor pricing data against yesterday's snapshot. Identify:\n1. Price changes (increases/decreases)\n2. New plans or tiers added/removed\n3. Feature changes in existing plans\n4. New promotional offers\n5. Changes to free tier limits\n\nCompetitor data: {{trigger-1.text}}\n\nReturn a structured diff report with severity (major/minor) and strategic implications.", 0.2),
                condition_node("condition-1", "Changes Detected?", {"x": 600, "y": 250}),
                integration_node("slack-alert", "Alert Sales Team", {"x": 850, "y": 100}, "slack", "send_message",
                                 {"channel": "#competitive-intel", "message": "COMPETITOR PRICING CHANGE:\n{{scrape-1.text}}"}),
                worker_node("battlecard-1", "Update Battlecard", {"x": 850, "y": 350}, "claude-3-5-sonnet",
                            "Update our competitive battlecard based on these pricing changes.\n\nChanges: {{scrape-1.text}}\n\nGenerate:\n1. Updated comparison table\n2. New objection handling talking points\n3. Win/loss implications\n4. Recommended positioning adjustments", 0.4),
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
            "total_executions": 187,
            "successful_executions": 185,
            "failed_executions": 2,
            "avg_execution_time_seconds": 15.6,
        },
        {
            "workflow_id": name_to_uuid("Invoice Approval Workflow"),
            "name": "Invoice Approval Workflow",
            "description": "Extract invoice data via OCR, match against purchase orders, route for approval based on amount thresholds, and post to accounting.",
            "tags": ["finance", "invoices", "approval", "accounting", "ocr"],
            "status": "active",
            "is_template": True,
            "nodes": [
                trigger_node("trigger-1", "Invoice Received", {"x": 100, "y": 250}, "webhook"),
                worker_node("ocr-1", "Extract Invoice Data", {"x": 350, "y": 250}, "gpt-4",
                            "Extract structured data from this invoice. Return JSON with:\n- vendor_name\n- invoice_number\n- invoice_date\n- due_date\n- line_items (array: description, quantity, unit_price, total)\n- subtotal\n- tax_amount\n- total_amount\n- currency\n- payment_terms\n- po_number (if referenced)\n\nInvoice: {{trigger-1.text}}", 0.1),
                worker_node("match-1", "PO Match & Validation", {"x": 600, "y": 250}, "gpt-4o-mini",
                            "Validate this invoice against our purchase order records.\n\nInvoice data: {{ocr-1.text}}\n\nCheck:\n1. PO number exists and is open\n2. Vendor matches PO vendor\n3. Line items match PO (quantity within 10% tolerance)\n4. Price matches PO (within 5% tolerance)\n5. Total doesn't exceed PO remaining balance\n\nReturn: match_status (exact_match/partial_match/no_match), discrepancies list, recommended_action.", 0.2),
                condition_node("condition-1", "Amount Threshold", {"x": 850, "y": 250}),
                integration_node("slack-mgr", "Manager Approval ($1K+)", {"x": 1100, "y": 100}, "slack", "send_message",
                                 {"channel": "#finance-approvals", "message": "Invoice requires approval:\nVendor: {{ocr-1.text}}\nAmount: {{ocr-1.text}}\nPO Match: {{match-1.text}}"}),
                integration_node("auto-approve", "Auto-Approve (< $1K)", {"x": 1100, "y": 400}, "stripe", "create_payment",
                                 {"vendor": "{{ocr-1.text}}", "amount": "{{ocr-1.text}}", "status": "approved"}),
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
            "total_executions": 342,
            "successful_executions": 336,
            "failed_executions": 6,
            "avg_execution_time_seconds": 7.3,
        },
        {
            "workflow_id": name_to_uuid("Employee Offboarding"),
            "name": "Employee Offboarding",
            "description": "Automate the full offboarding process: revoke access across tools, backup data, notify IT/HR, and generate a compliance checklist.",
            "tags": ["hr", "offboarding", "security", "compliance", "automation"],
            "status": "active",
            "is_template": True,
            "nodes": [
                trigger_node("trigger-1", "Offboarding Request", {"x": 100, "y": 300}, "manual"),
                worker_node("plan-1", "Generate Offboarding Plan", {"x": 350, "y": 300}, "claude-3-5-sonnet",
                            "Generate a comprehensive employee offboarding checklist for this employee.\n\nEmployee info: {{trigger-1.text}}\n\nInclude:\n1. Systems access to revoke (list all based on role/department)\n2. Data backup requirements\n3. Equipment to collect\n4. Knowledge transfer items\n5. Exit interview scheduling\n6. Final payroll considerations\n7. Benefits continuation info (COBRA)\n8. NDA/IP reminder\n\nReturn as structured JSON with status=pending for each item.", 0.3),
                integration_node("slack-it", "Notify IT Team", {"x": 600, "y": 100}, "slack", "send_message",
                                 {"channel": "#it-operations", "message": "OFFBOARDING: Please revoke access for departing employee.\n\n{{plan-1.text}}"}),
                integration_node("slack-hr", "Notify HR Team", {"x": 600, "y": 300}, "slack", "send_message",
                                 {"channel": "#hr-operations", "message": "OFFBOARDING: Exit interview & final paperwork needed.\n\n{{plan-1.text}}"}),
                integration_node("jira-1", "Create IT Tickets", {"x": 600, "y": 500}, "jira", "create_ticket",
                                 {"project": "IT", "summary": "Offboarding: Revoke access for {{trigger-1.text}}", "description": "{{plan-1.text}}"}),
                worker_node("compliance-1", "Compliance Verification", {"x": 900, "y": 300}, "gpt-4o-mini",
                            "Generate a compliance verification checklist for this offboarding. Verify:\n1. All system access revoked (SOC 2 requirement)\n2. Company devices collected\n3. Data backup confirmed\n4. NDA acknowledgment signed\n5. IP assignment verified\n6. Badge/physical access deactivated\n\nEmployee: {{trigger-1.text}}\nPlan: {{plan-1.text}}\n\nReturn as a compliance report with pass/fail for each item.", 0.2),
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
            "total_executions": 47,
            "successful_executions": 46,
            "failed_executions": 1,
            "avg_execution_time_seconds": 8.9,
        },
    ]

    now = datetime.utcnow().isoformat()
    created = []
    skipped = []

    for wf in workflows_data:
        try:
            check = await db.execute(
                text("SELECT workflow_id FROM workflows WHERE workflow_id = :wid"),
                {"wid": wf["workflow_id"]}
            )
            if check.fetchone():
                skipped.append(wf["name"])
                continue

            await db.execute(text("""
                INSERT INTO workflows (
                    workflow_id, organization_id, name, description, tags, status, version,
                    nodes, edges, max_execution_time_seconds, retry_on_failure, max_retries,
                    variables, environment, trigger_type, trigger_config,
                    total_executions, successful_executions, failed_executions,
                    avg_execution_time_seconds, average_execution_time, execution_count,
                    total_cost, is_template, created_at, updated_at, created_by
                ) VALUES (
                    :workflow_id, 'default', :name, :description, :tags, :status, 1,
                    :nodes, :edges, 300, 1, 3,
                    '{}', 'production', :trigger_type, '{}',
                    :total_executions, :successful_executions, :failed_executions,
                    :avg_execution_time_seconds, :avg_execution_time_seconds, :total_executions,
                    0.0, :is_template, :now, :now, 'admin@example.com'
                )
            """), {
                "workflow_id": wf["workflow_id"],
                "name": wf["name"],
                "description": wf["description"],
                "tags": json.dumps(wf["tags"]),
                "status": wf["status"],
                "nodes": json.dumps(wf["nodes"]),
                "edges": json.dumps(wf["edges"]),
                "trigger_type": wf["trigger_type"],
                "is_template": 1 if wf.get("is_template") else 0,
                "total_executions": wf["total_executions"],
                "successful_executions": wf["successful_executions"],
                "failed_executions": wf["failed_executions"],
                "avg_execution_time_seconds": wf["avg_execution_time_seconds"],
                "now": now,
            })

            # Seed some execution history for each workflow
            statuses = ["completed", "completed", "completed", "completed", "failed"]
            for i, exec_status in enumerate(statuses):
                exec_id = name_to_uuid(f"{wf['name']}-exec-{i+1}")
                duration = wf["avg_execution_time_seconds"] * (0.8 + (i * 0.1))
                exec_nodes = json.dumps([
                    {"node_id": n["id"], "status": exec_status if i < 4 else ("failed" if n["id"] == wf["nodes"][-2]["id"] else "completed"),
                     "started_at": now, "completed_at": now, "duration_seconds": duration / len(wf["nodes"])}
                    for n in wf["nodes"]
                ])
                await db.execute(text("""
                    INSERT INTO workflow_executions (
                        execution_id, workflow_id, workflow_version, organization_id,
                        triggered_by, trigger_source, status, started_at, completed_at,
                        duration_seconds, input_data, output_data, error_message,
                        retry_count, node_states, node_executions, total_cost, created_at
                    ) VALUES (
                        :exec_id, :wf_id, 1, 'default',
                        'admin@example.com', :trigger_type, :status, :now, :now,
                        :duration, '{}', '{}', :error,
                        0, '{}', :node_execs, 0.0, :now
                    )
                """), {
                    "exec_id": exec_id,
                    "wf_id": wf["workflow_id"],
                    "trigger_type": wf["trigger_type"],
                    "status": exec_status,
                    "now": now,
                    "duration": duration,
                    "error": "Timeout waiting for integration response" if exec_status == "failed" else None,
                    "node_execs": exec_nodes,
                })

            await db.commit()
            created.append(wf["name"])
        except Exception as e:
            await db.rollback()
            print(f"Error creating workflow {wf['name']}: {e}")
            import traceback
            traceback.print_exc()

    return {
        "success": True,
        "created_count": len(created),
        "skipped_count": len(skipped),
        "created": created,
        "skipped": skipped,
    }


@router.delete("/marketplace-agents")
async def reset_marketplace_agents(db: AsyncSession = Depends(get_db)):
    """
    Delete all marketplace agents and their installations.
    Use POST /api/v1/seed/marketplace-agents after this to re-seed.
    """
    from sqlalchemy import text

    try:
        # Delete installations first (foreign key constraint)
        await db.execute(text("DELETE FROM agent_installations"))
        # Delete all marketplace agents
        await db.execute(text("DELETE FROM marketplace_agents"))
        await db.commit()

        return {
            "success": True,
            "message": "All marketplace agents and installations deleted. Run POST /api/v1/seed/marketplace-agents to re-seed."
        }
    except Exception as e:
        await db.rollback()
        raise HTTPException(status_code=500, detail=f"Failed to reset: {str(e)}")
