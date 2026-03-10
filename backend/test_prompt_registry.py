#!/usr/bin/env python3
"""
Test Prompt Registry functionality

Tests the Prompt Registry service and models without requiring the full API server.
"""

import sys
import os
from pathlib import Path
from uuid import uuid4
import asyncio
from datetime import datetime

# Set up Python path
backend_dir = Path(__file__).parent
parent_dir = backend_dir.parent
sys.path.insert(0, str(parent_dir))

# Enable SQLite mode
os.environ['USE_SQLITE'] = 'true'

from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from backend.shared.prompt_service import PromptService

# Create async engine for SQLite
DATABASE_URL = f"sqlite+aiosqlite:///{backend_dir}/test_workflow.db"
engine = create_async_engine(DATABASE_URL, echo=False)
async_session_factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)


async def test_prompt_registry():
    """Test all Prompt Registry functionality."""

    print("🧪 Testing Prompt Registry Service\n")
    print("=" * 60)

    # Test organization and user IDs
    org_id = uuid4()
    user_id = uuid4()

    async with async_session_factory() as session:
        # Test 1: Create a prompt template
        print("\n1️⃣ Testing: Create Prompt Template")
        print("-" * 60)

        template = await PromptService.create_template(
            db=session,
            organization_id=org_id,
            name="Customer Support Agent",
            description="Prompt for customer support interactions",
            category="customer_support",
            created_by=user_id,
        )

        print(f"✅ Created template:")
        print(f"   - ID: {template.id}")
        print(f"   - Name: {template.name}")
        print(f"   - Slug: {template.slug}")
        print(f"   - Category: {template.category}")

        # Test 2: Create version 1.0.0
        print("\n2️⃣ Testing: Create Version 1.0.0")
        print("-" * 60)

        content_v1 = """You are a helpful customer support agent.

Customer: {{customer_name}}
Issue: {{issue_type}}
Priority: {{priority}}

Please provide a professional and empathetic response to help resolve the customer's issue."""

        version_1_0_0 = await PromptService.create_version(
            db=session,
            organization_id=org_id,
            slug=template.slug,
            version="1.0.0",
            content=content_v1,
            model_hint="gpt-4o",
            metadata={"tested": True, "author": "team"},
            created_by=user_id,
        )

        print(f"✅ Created version 1.0.0:")
        print(f"   - ID: {version_1_0_0.id}")
        print(f"   - Version: {version_1_0_0.version}")
        print(f"   - Variables: {version_1_0_0.variables}")
        print(f"   - Model Hint: {version_1_0_0.model_hint}")

        # Test 3: Create version 1.1.0
        print("\n3️⃣ Testing: Create Version 1.1.0")
        print("-" * 60)

        content_v1_1 = """You are a helpful customer support agent specialized in {{product_category}}.

Customer: {{customer_name}}
Issue: {{issue_type}}
Priority: {{priority}}
Order ID: {{order_id}}

Please provide a professional and empathetic response to help resolve the customer's issue.
Use your knowledge of {{product_category}} to provide specific guidance."""

        version_1_1_0 = await PromptService.create_version(
            db=session,
            organization_id=org_id,
            slug=template.slug,
            version="1.1.0",
            content=content_v1_1,
            model_hint="gpt-4o",
            metadata={"tested": True, "author": "team", "changelog": "Added product_category and order_id support"},
            created_by=user_id,
        )

        print(f"✅ Created version 1.1.0:")
        print(f"   - ID: {version_1_1_0.id}")
        print(f"   - Version: {version_1_1_0.version}")
        print(f"   - Variables: {version_1_1_0.variables}")
        print(f"   - Model Hint: {version_1_1_0.model_hint}")

        # Test 4: Publish version 1.1.0
        print("\n4️⃣ Testing: Publish Version 1.1.0")
        print("-" * 60)

        published_version = await PromptService.publish_version(
            db=session,
            organization_id=org_id,
            slug=template.slug,
            version="1.1.0",
        )

        print(f"✅ Published version 1.1.0:")
        print(f"   - Published: {published_version.is_published}")
        print(f"   - Published At: {published_version.published_at}")

        # Test 5: Render prompt with variables
        print("\n5️⃣ Testing: Render Prompt with Variables")
        print("-" * 60)

        variables = {
            "customer_name": "John Doe",
            "issue_type": "Product not received",
            "priority": "High",
            "order_id": "ORD-12345",
            "product_category": "Electronics",
        }

        rendered = await PromptService.render_prompt(
            db=session,
            organization_id=org_id,
            slug=template.slug,
            variables=variables,
        )

        print(f"✅ Rendered prompt:")
        print(f"   - Template ID: {rendered['template_id']}")
        print(f"   - Version: {rendered['version']}")
        print(f"   - Model Hint: {rendered['model_hint']}")
        print(f"\n📝 Rendered Content:")
        print("-" * 60)
        print(rendered['rendered_content'])
        print("-" * 60)

        # Test 6: List all versions
        print("\n6️⃣ Testing: List All Versions")
        print("-" * 60)

        versions = await PromptService.list_versions(
            db=session,
            organization_id=org_id,
            slug=template.slug,
        )

        print(f"✅ Found {len(versions)} versions:")
        for v in versions:
            print(f"   - {v.version} (Published: {v.is_published})")

        # Test 7: Get specific version
        print("\n7️⃣ Testing: Get Specific Version")
        print("-" * 60)

        specific_version = await PromptService.get_version(
            db=session,
            organization_id=org_id,
            slug=template.slug,
            version="1.0.0",
        )

        print(f"✅ Retrieved version 1.0.0:")
        print(f"   - Variables: {specific_version.variables}")
        print(f"   - Published: {specific_version.is_published}")

        # Test 8: List templates
        print("\n8️⃣ Testing: List Templates")
        print("-" * 60)

        templates, total = await PromptService.list_templates(
            db=session,
            organization_id=org_id,
        )

        print(f"✅ Found {total} template(s):")
        for t in templates:
            print(f"   - {t.name} ({t.slug})")
            print(f"     Category: {t.category}")
            print(f"     Active: {t.is_active}")

        # Test 9: Track usage
        print("\n9️⃣ Testing: Track Usage Statistics")
        print("-" * 60)

        await PromptService.track_usage(
            db=session,
            version_id=published_version.id,
            latency_ms=125.5,
            tokens=450,
            success=True,
        )

        await PromptService.track_usage(
            db=session,
            version_id=published_version.id,
            latency_ms=98.3,
            tokens=425,
            success=True,
        )

        await PromptService.track_usage(
            db=session,
            version_id=published_version.id,
            latency_ms=150.0,
            tokens=500,
            success=False,
        )

        print(f"✅ Tracked 3 usage events")

        # Test 10: Get usage stats
        print("\n🔟 Testing: Get Usage Statistics")
        print("-" * 60)

        stats = await PromptService.get_usage_stats(
            db=session,
            version_id=published_version.id,
            days=7,
        )

        print(f"✅ Usage statistics for version {published_version.version}:")
        for s in stats:
            print(f"   Date: {s.date}")
            print(f"   - Invocations: {s.invocations}")
            print(f"   - Avg Latency: {s.avg_latency_ms:.2f}ms")
            print(f"   - Avg Tokens: {s.avg_tokens}")
            print(f"   - Success Rate: {s.success_rate:.2%}")

    print("\n" + "=" * 60)
    print("✅ All tests completed successfully!\n")


if __name__ == "__main__":
    asyncio.run(test_prompt_registry())
