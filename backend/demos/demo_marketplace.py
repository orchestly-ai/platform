"""
Agent Marketplace Demo - P2 Feature #3

Demonstrates agent marketplace features:
- Publishing agents to marketplace
- Searching and discovering agents
- One-click installation
- Rating and reviews
- Agent collections
- Version management
- Usage analytics

Run: python backend/demo_marketplace.py
"""

import sys
from pathlib import Path

# Add parent directory to path so backend.* imports work
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

import asyncio
from sqlalchemy import text
from datetime import datetime

from backend.database.session import AsyncSessionLocal, init_db
from backend.shared.marketplace_models import *
from backend.shared.marketplace_service import MarketplaceService


async def demo_marketplace():
    async with AsyncSessionLocal() as db:
        print("=" * 80)
        print("AGENT MARKETPLACE DEMO")
        print("=" * 80)
        print()

        # Drop and recreate tables to fix ENUM type mismatches
        print("Setting up demo environment...")
        try:
            await db.execute(text("DROP TABLE IF EXISTS agent_analytics CASCADE"))
            await db.execute(text("DROP TABLE IF EXISTS agent_collection_items CASCADE"))
            await db.execute(text("DROP TABLE IF EXISTS agent_collections CASCADE"))
            await db.execute(text("DROP TABLE IF EXISTS agent_reviews CASCADE"))
            await db.execute(text("DROP TABLE IF EXISTS agent_installations CASCADE"))
            await db.execute(text("DROP TABLE IF EXISTS agent_versions CASCADE"))
            await db.execute(text("DROP TABLE IF EXISTS marketplace_agents CASCADE"))
            # Drop old ENUM types
            await db.execute(text("DROP TYPE IF EXISTS agentvisibility CASCADE"))
            await db.execute(text("DROP TYPE IF EXISTS agentcategory CASCADE"))
            await db.execute(text("DROP TYPE IF EXISTS agentpricing CASCADE"))
            await db.execute(text("DROP TYPE IF EXISTS installationstatus CASCADE"))
            await db.execute(text("DROP TYPE IF EXISTS reviewstatus CASCADE"))
            await db.commit()
            print("✓ Cleaned up old tables and types")
        except Exception as e:
            print(f"⚠ Cleanup warning: {str(e)[:100]}")
            await db.rollback()

    await init_db()

    async with AsyncSessionLocal() as db:
        print("✓ Database ready\n")

        print("=" * 80)
        print("AGENT MARKETPLACE DEMO")
        print("=" * 80)
        print()

        publisher_id = "publisher_123"
        publisher_name = "Acme AI Corp"
        user_id = "user_demo"
        user_name = "Jane Smith"
        org_id = 1

        # Demo 1: Publishing Agents
        print("📦 DEMO 1: Publishing Agents to Marketplace")
        print("-" * 80)

        print("\n1. Publishing 'Customer Service Bot' agent...")
        agent1 = await MarketplaceService.publish_agent(
            db,
            AgentPublish(
                name="Customer Service Bot",
                slug="customer-service-bot",
                tagline="AI-powered customer support automation",
                description="""
# Customer Service Bot

Automated customer service agent that handles common inquiries, ticket routing, and FAQs.

## Features
- Natural language understanding
- Multi-channel support (email, chat, phone)
- Automatic ticket routing
- FAQ answering
- Sentiment analysis
- Escalation to human agents

## Use Cases
- E-commerce customer support
- SaaS helpdesk automation
- Call center augmentation
                """,
                category=AgentCategory.CUSTOMER_SERVICE,
                tags=["customer-service", "support", "chatbot", "automation"],
                visibility=AgentVisibility.PUBLIC,
                pricing=AgentPricing.FREEMIUM,
                agent_config={
                    "model": "gpt-4",
                    "temperature": 0.7,
                    "max_tokens": 500,
                    "system_prompt": "You are a helpful customer service agent...",
                },
                required_integrations=["zendesk", "slack"],
                required_capabilities=["chat", "sentiment-analysis"],
                version="1.0.0",
                changelog="Initial release",
            ),
            publisher_id,
            publisher_name,
            org_id,
        )
        print(f"   ✓ Published: {agent1.name} (ID: {agent1.id})")
        print(f"   ✓ Slug: {agent1.slug}")
        print(f"   ✓ Category: {agent1.category}")
        print(f"   ✓ Version: {agent1.version}")

        print("\n2. Publishing 'Sales Lead Qualifier' agent...")
        agent2 = await MarketplaceService.publish_agent(
            db,
            AgentPublish(
                name="Sales Lead Qualifier",
                slug="sales-lead-qualifier",
                tagline="Automatically qualify and score sales leads",
                description="AI agent that analyzes and qualifies inbound sales leads based on firmographics, intent signals, and scoring criteria.",
                category=AgentCategory.SALES_AUTOMATION,
                tags=["sales", "lead-qualification", "scoring", "crm"],
                visibility=AgentVisibility.PUBLIC,
                pricing=AgentPricing.PAID,
                price_usd=49.99,
                agent_config={
                    "model": "claude-3-opus",
                    "scoring_criteria": ["company_size", "industry", "budget", "timeline"],
                },
                required_integrations=["salesforce", "hubspot"],
                version="2.1.0",
            ),
            publisher_id,
            publisher_name,
            org_id,
        )
        print(f"   ✓ Published: {agent2.name} (ID: {agent2.id})")
        print(f"   ✓ Pricing: {agent2.pricing} (${agent2.price_usd}/month)")

        print("\n3. Publishing 'Data Analytics Assistant' agent...")
        agent3 = await MarketplaceService.publish_agent(
            db,
            AgentPublish(
                name="Data Analytics Assistant",
                slug="data-analytics-assistant",
                tagline="Natural language data querying and visualization",
                description="Query your data warehouse using natural language and get instant visualizations and insights.",
                category=AgentCategory.ANALYTICS,
                tags=["analytics", "data", "visualization", "sql"],
                visibility=AgentVisibility.PUBLIC,
                pricing=AgentPricing.FREE,
                agent_config={
                    "model": "gpt-4",
                    "capabilities": ["sql-generation", "chart-generation"],
                },
                required_integrations=["snowflake", "bigquery"],
                version="1.5.2",
            ),
            publisher_id,
            publisher_name,
            org_id,
        )
        print(f"   ✓ Published: {agent3.name} (ID: {agent3.id})")

        print(f"\n   Total agents published: 3")

        # Demo 2: Marketplace Discovery
        print("\n\n🔍 DEMO 2: Discovering Agents")
        print("-" * 80)

        print("\n1. Searching all public agents...")
        results = await MarketplaceService.search_agents(
            db,
            AgentSearchFilters(page=1, page_size=10, sort_by="popular"),
        )
        print(f"   ✓ Found {results.total_count} agents")
        print(f"   ✓ Page {results.page} of {results.total_pages}")
        for i, agent in enumerate(results.agents, 1):
            print(f"      {i}. {agent.name} - {agent.category} ({agent.pricing})")

        print("\n2. Searching for 'customer service' agents...")
        results = await MarketplaceService.search_agents(
            db,
            AgentSearchFilters(
                query="customer service",
                page=1,
                page_size=10,
            ),
        )
        print(f"   ✓ Found {results.total_count} results")
        for agent in results.agents:
            print(f"      - {agent.name}: {agent.tagline}")

        print("\n3. Filtering by category: Sales Automation...")
        results = await MarketplaceService.search_agents(
            db,
            AgentSearchFilters(
                category=AgentCategory.SALES_AUTOMATION,
                page=1,
                page_size=10,
            ),
        )
        print(f"   ✓ Found {results.total_count} sales automation agents")

        print("\n4. Filtering by pricing: Free agents only...")
        results = await MarketplaceService.search_agents(
            db,
            AgentSearchFilters(
                pricing=AgentPricing.FREE,
                page=1,
                page_size=10,
            ),
        )
        print(f"   ✓ Found {results.total_count} free agents")

        print("\n5. Getting agent by slug...")
        agent = await MarketplaceService.get_agent_by_slug(db, "customer-service-bot")
        print(f"   ✓ {agent.name}")
        print(f"   ✓ Publisher: {agent.publisher_name}")
        print(f"   ✓ Installs: {agent.install_count}")
        print(f"   ✓ Rating: {agent.rating_avg:.1f}/5.0 ({agent.rating_count} reviews)")

        # Demo 3: Agent Installation
        print("\n\n💿 DEMO 3: Installing Agents")
        print("-" * 80)

        print("\n1. Installing 'Customer Service Bot'...")
        installation1 = await MarketplaceService.install_agent(
            db,
            AgentInstall(agent_id=agent1.id),
            user_id,
            org_id,
        )
        print(f"   ✓ Installation ID: {installation1.id}")
        print(f"   ✓ Status: {installation1.status}")
        print(f"   ✓ Version: {installation1.version}")
        print(f"   ✓ Installed agent ID: {installation1.installed_agent_id}")
        print(f"   ✓ Auto-update: {installation1.auto_update}")

        print("\n2. Installing 'Data Analytics Assistant' with config overrides...")
        installation2 = await MarketplaceService.install_agent(
            db,
            AgentInstall(
                agent_id=agent3.id,
                config_overrides={
                    "temperature": 0.5,
                    "custom_prompt": "Focus on revenue metrics",
                },
            ),
            user_id,
            org_id,
        )
        print(f"   ✓ Installation ID: {installation2.id}")
        print(f"   ✓ Config overrides: {installation2.config_overrides}")

        print("\n3. Listing user's installed agents...")
        installations = await MarketplaceService.get_user_installations(db, user_id, org_id)
        print(f"   ✓ Total installations: {len(installations)}")
        for install in installations:
            print(f"      - ID {install.id}: Agent {install.agent_id} (v{install.version})")

        # Demo 4: Reviews and Ratings
        print("\n\n⭐ DEMO 4: Reviews and Ratings")
        print("-" * 80)

        print("\n1. Creating 5-star review for 'Customer Service Bot'...")
        review1 = await MarketplaceService.create_review(
            db,
            ReviewCreate(
                agent_id=agent1.id,
                rating=5,
                title="Game changer for our support team!",
                review_text="This agent reduced our ticket response time by 70%. Highly recommend!",
                version="1.0.0",
            ),
            user_id,
            user_name,
            org_id,
        )
        print(f"   ✓ Review ID: {review1.id}")
        print(f"   ✓ Rating: {review1.rating}/5")
        print(f"   ✓ Status: {review1.status}")

        print("\n2. Creating another review from different user...")
        user2_id = "user_demo_2"
        user2_name = "Bob Johnson"

        # Install first (required to review)
        await MarketplaceService.install_agent(
            db,
            AgentInstall(agent_id=agent1.id),
            user2_id,
            org_id,
        )

        review2 = await MarketplaceService.create_review(
            db,
            ReviewCreate(
                agent_id=agent1.id,
                rating=4,
                title="Great agent, minor issues",
                review_text="Works well overall, but occasionally misunderstands complex queries.",
            ),
            user2_id,
            user2_name,
            org_id,
        )
        print(f"   ✓ Review ID: {review2.id}")
        print(f"   ✓ Rating: {review2.rating}/5")

        print("\n3. Getting all reviews for agent...")
        reviews = await MarketplaceService.get_agent_reviews(db, agent1.id)
        print(f"   ✓ Total reviews: {len(reviews)}")
        for review in reviews:
            print(f"      - {review.user_name}: {review.rating}/5 - {review.title}")

        print("\n4. Checking updated agent rating...")
        agent = await MarketplaceService.get_agent(db, agent1.id)
        print(f"   ✓ Average rating: {agent.rating_avg:.1f}/5.0")
        print(f"   ✓ Total reviews: {agent.rating_count}")

        # Demo 5: Agent Versions
        print("\n\n📌 DEMO 5: Version Management")
        print("-" * 80)

        print("\n1. Publishing new version 2.0.0 of 'Sales Lead Qualifier'...")
        new_version = await MarketplaceService.publish_version(
            db,
            agent2.id,
            "2.2.0",
            {
                "model": "claude-3-opus",
                "new_feature": "predictive_scoring",
                "scoring_criteria": ["company_size", "industry", "budget", "timeline", "engagement"],
            },
            "Added predictive scoring and engagement tracking",
            publisher_id,
        )
        print(f"   ✓ Version ID: {new_version.id}")
        print(f"   ✓ Version: {new_version.version}")
        print(f"   ✓ Is latest: {new_version.is_latest}")
        print(f"   ✓ Release notes: {new_version.release_notes}")

        # Demo 6: Agent Collections
        print("\n\n📚 DEMO 6: Agent Collections")
        print("-" * 80)

        print("\n1. Creating 'Customer Support Suite' collection...")
        collection = await MarketplaceService.create_collection(
            db,
            CollectionCreate(
                name="Customer Support Suite",
                slug="customer-support-suite",
                description="Complete toolkit for customer service automation",
                agent_ids=[agent1.id, agent3.id],
                is_public=True,
            ),
            publisher_id,
            is_official=True,
        )
        print(f"   ✓ Collection ID: {collection.id}")
        print(f"   ✓ Name: {collection.name}")
        print(f"   ✓ Agents: {len(collection.agent_ids)}")
        print(f"   ✓ Official: {collection.is_official}")

        print("\n2. Installing entire collection...")
        user3_id = "user_demo_3"
        collection_installs = await MarketplaceService.install_collection(
            db,
            collection.id,
            user3_id,
            org_id,
        )
        print(f"   ✓ Installed {len(collection_installs)} agents")
        for install in collection_installs:
            print(f"      - Agent {install.agent_id}: {install.status}")

        # Demo 7: Featured and Trending
        print("\n\n🔥 DEMO 7: Featured and Trending Agents")
        print("-" * 80)

        # Mark agent as featured
        agent1.is_featured = True
        agent1.is_verified = True
        await db.commit()

        print("\n1. Getting featured agents...")
        featured = await MarketplaceService.get_featured_agents(db, limit=5)
        print(f"   ✓ Found {len(featured)} featured agents")
        for agent in featured:
            print(f"      - {agent.name} ({agent.avg_rating:.1f}⭐, {agent.install_count} installs)")

        print("\n2. Getting trending agents (last 7 days)...")
        trending = await MarketplaceService.get_trending_agents(db, days=7, limit=5)
        print(f"   ✓ Found {len(trending)} trending agents")
        for agent in trending:
            print(f"      - {agent.name} ({agent.install_count} installs)")

        # Demo 8: Agent Statistics
        print("\n\n📊 DEMO 8: Agent Usage Statistics")
        print("-" * 80)

        print(f"\n1. Getting stats for '{agent1.name}'...")
        stats = await MarketplaceService.get_agent_stats(db, agent1.id)
        print(f"   Total installations: {stats.total_installations}")
        print(f"   Active installations: {stats.active_installations}")
        print(f"   Total executions: {stats.total_executions}")
        print(f"   Success rate: {stats.success_rate:.1f}%")
        print(f"   Average rating: {stats.avg_rating:.1f}/5.0")
        print(f"   Total reviews: {stats.total_reviews}")
        if stats.total_revenue_usd:
            print(f"   Revenue: ${stats.total_revenue_usd:.2f}")

        # Demo 9: Uninstalling
        print("\n\n🗑️  DEMO 9: Uninstalling Agents")
        print("-" * 80)

        print("\n1. Uninstalling agent...")
        await MarketplaceService.uninstall_agent(db, installation2.id, user_id)
        print(f"   ✓ Agent uninstalled: Installation {installation2.id}")

        print("\n2. Verifying installation status...")
        installations = await MarketplaceService.get_user_installations(db, user_id, org_id)
        print(f"   ✓ Active installations: {len(installations)}")

        # Summary
        print("\n\n" + "=" * 80)
        print("DEMO SUMMARY")
        print("=" * 80)
        print("\n✅ Marketplace Features Demonstrated:")
        print("   - Agent publishing with full metadata")
        print("   - Rich agent descriptions (markdown support)")
        print("   - Agent discovery and search")
        print("   - Category and pricing filters")
        print("   - One-click agent installation")
        print("   - Config override support")
        print("   - Rating and review system")
        print("   - Version management")
        print("   - Agent collections (bundles)")
        print("   - Featured and trending agents")
        print("   - Usage analytics")
        print("   - Agent uninstallation")
        print()
        print("✅ Agent Categories:")
        print("   - data_processing, customer_service, sales_automation")
        print("   - marketing, hr_recruiting, finance_accounting")
        print("   - legal, engineering, analytics")
        print("   - integration, communication, productivity")
        print()
        print("✅ Pricing Models:")
        print("   - Free (0 cost)")
        print("   - Freemium (free with premium features)")
        print("   - Paid (monthly subscription)")
        print("   - Enterprise (contact sales)")
        print()
        print("✅ Visibility Options:")
        print("   - Public (everyone can see)")
        print("   - Private (only creator)")
        print("   - Organization (team members)")
        print("   - Unlisted (link-only access)")
        print()
        print("✅ Search and Filter:")
        print("   - Text search (name, tagline, description)")
        print("   - Category filter")
        print("   - Pricing filter")
        print("   - Tag-based search")
        print("   - Verified agents only")
        print("   - Minimum rating filter")
        print("   - Sort by: popular, newest, rating, name")
        print()
        print("✅ Installation Features:")
        print("   - One-click install")
        print("   - Version pinning")
        print("   - Config overrides")
        print("   - Auto-update option")
        print("   - Dependency checking (integrations, capabilities)")
        print()
        print("✅ Review System:")
        print("   - 5-star ratings")
        print("   - Written reviews")
        print("   - Version-specific reviews")
        print("   - Review moderation")
        print("   - Publisher responses")
        print("   - Helpful/unhelpful voting")
        print()
        print("✅ Collections:")
        print("   - Curated agent bundles")
        print("   - Official collections")
        print("   - One-click collection install")
        print("   - Featured collections")
        print()
        print("✅ Business Impact:")
        print("   - Faster time-to-value (pre-built agents)")
        print("   - Community knowledge sharing")
        print("   - Agent ecosystem growth")
        print("   - Reduced development costs")
        print("   - Revenue opportunity for publishers")
        print()
        print("✅ Competitive Differentiation:")
        print("   - GitHub-style agent marketplace")
        print("   - Rich metadata and documentation")
        print("   - Version management")
        print("   - Collections for common use cases")
        print("   - Revenue sharing for publishers")
        print()
        print("🎉 Agent Marketplace enables rapid agent deployment and sharing!")
        print()

if __name__ == "__main__":
    asyncio.run(demo_marketplace())
