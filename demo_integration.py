#!/usr/bin/env python3
"""
Demo: How Integrations and Agents Work Together

This demo shows the complete flow:
1. Install an integration (Discord)
2. Configure credentials
3. Execute an action (send a message)

Run with: python demo_integration.py
"""

import asyncio
import os
import sys
from uuid import uuid4

# Add the backend to the path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

async def demo_without_database():
    """Demo that works without database - directly uses the integration SDK."""
    print("=" * 60)
    print("DEMO: Direct Integration Usage (No Database Required)")
    print("=" * 60)

    # Check for Discord bot token
    discord_token = os.environ.get("DISCORD_BOT_TOKEN")

    if not discord_token:
        print("\n⚠️  No DISCORD_BOT_TOKEN found in environment.")
        print("\nTo test with Discord:")
        print("1. Create a bot at https://discord.com/developers/applications")
        print("2. Copy the bot token")
        print("3. Run: DISCORD_BOT_TOKEN='your-token' python demo_integration.py")
        print("\n" + "=" * 60)
        print("Running in SIMULATION mode instead...")
        print("=" * 60)
        await demo_simulated()
        return

    print(f"\n✅ Found Discord bot token: {discord_token[:20]}...")

    try:
        from backend.shared.integrations.discord_integration import DiscordIntegration

        # Create the integration instance
        integration = DiscordIntegration(credentials={"bot_token": discord_token})

        # Validate credentials
        print("\n📡 Validating Discord credentials...")
        is_valid = await integration.validate_credentials()

        if is_valid:
            print("✅ Credentials are valid!")

            # Get available actions
            print("\n📋 Available Discord actions:")
            for action in integration.get_available_actions():
                print(f"   - {action['name']}: {action['description']}")

            # Note: To actually send a message, you'd need a channel ID
            print("\n💡 To send a message, you would call:")
            print('   await integration.execute_action("send_message", {')
            print('       "channel_id": "YOUR_CHANNEL_ID",')
            print('       "content": "Hello from the agent!"')
            print('   })')
        else:
            print("❌ Invalid credentials")

    except ImportError as e:
        print(f"❌ Could not import Discord integration: {e}")
        print("   Make sure all dependencies are installed")


async def demo_simulated():
    """Simulated demo showing the flow without real credentials."""
    print("\n🎭 SIMULATED DEMO")
    print("-" * 40)

    print("\n1️⃣  Step 1: User browses Integrations page")
    print("   → Sees Discord integration available")
    print("   → Clicks 'Install'")

    print("\n2️⃣  Step 2: User configures credentials")
    print("   → Clicks 'Configure'")
    print("   → Enters Discord Bot Token")
    print("   → Clicks 'Save'")

    print("\n3️⃣  Step 3: User tests the connection")
    print("   → Clicks 'Test'")
    print("   → System validates the bot token with Discord API")
    print("   → Shows '✅ Connected' if valid")

    print("\n4️⃣  Step 4: Integration is ready to use")
    print("   → Agents can now use Discord actions:")
    print("      • send_message - Send message to channel")
    print("      • send_embed - Send rich embed")
    print("      • create_channel - Create new channel")
    print("      • list_channels - List server channels")

    print("\n5️⃣  Step 5: Agent uses the integration")
    print("   → Agent receives task: 'Notify team about deployment'")
    print("   → Agent calls: discord.send_message(channel, 'Deployment complete!')")
    print("   → Message appears in Discord")

    print("\n" + "=" * 60)
    print("HOW TO DO THIS FOR REAL:")
    print("=" * 60)
    print("""
1. Create Discord bot:
   → https://discord.com/developers/applications
   → New Application → Bot → Copy Token

2. Add bot to your server:
   → OAuth2 → URL Generator
   → Scopes: bot
   → Permissions: Send Messages, Read Message History
   → Open generated URL to add bot

3. Set environment variable:
   → export DISCORD_BOT_TOKEN='your-token-here'

4. Run this demo again:
   → python demo_integration.py

5. Or use the Dashboard:
   → Go to Integrations page
   → Find Discord → Click Configure
   → Paste your bot token
   → Click Test to verify
""")


async def demo_workflow_concept():
    """Show how a workflow would use integrations."""
    print("\n" + "=" * 60)
    print("CONCEPT: How Workflows Use Integrations")
    print("=" * 60)

    print("""
┌─────────────────────────────────────────────────────────────┐
│                    WORKFLOW EXECUTION                        │
├─────────────────────────────────────────────────────────────┤
│                                                              │
│   1. Trigger (e.g., schedule, webhook, manual)              │
│          ↓                                                   │
│   2. Workflow Engine starts                                  │
│          ↓                                                   │
│   3. For each step in workflow:                             │
│          ↓                                                   │
│      ┌─────────────────────────────────────┐                │
│      │ Step: "Send Discord Notification"   │                │
│      │ Integration: discord                │                │
│      │ Action: send_message                │                │
│      │ Params: {channel, message}          │                │
│      └─────────────────────────────────────┘                │
│          ↓                                                   │
│   4. Integration Executor:                                   │
│      • Loads user's Discord credentials                     │
│      • Calls Discord API                                     │
│      • Returns result                                        │
│          ↓                                                   │
│   5. Continue to next step or finish                        │
│                                                              │
└─────────────────────────────────────────────────────────────┘

EXAMPLE WORKFLOW: "Daily Standup Reminder"
──────────────────────────────────────────
Trigger: Every day at 9:00 AM
Steps:
  1. Send Discord message to #general: "Time for standup! 🎯"
  2. Send Gmail to team@company.com with standup template
  3. Create GitHub issue for standup notes
""")


async def main():
    print("\n🚀 Agent Orchestration Platform - Integration Demo")
    print("=" * 60)

    await demo_without_database()
    await demo_workflow_concept()

    print("\n✨ Demo complete!")
    print("\nNext steps:")
    print("1. Set up a real integration (Discord is easiest)")
    print("2. Go to Dashboard → Integrations → Configure credentials")
    print("3. Go to Dashboard → Workflows → Create a workflow using integrations")


if __name__ == "__main__":
    asyncio.run(main())
