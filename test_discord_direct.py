#!/usr/bin/env python3
"""
Direct Discord Integration Test

This script tests your Discord integration directly without going through
the workflow engine. Run it to verify your Discord bot is working.

Usage:
  python test_discord_direct.py <channel_id> "Your message here"

Example:
  python test_discord_direct.py 1234567890123456789 "Hello from my test!"
"""

import asyncio
import sys
import os
import httpx

# Configuration - Update these if your backend runs on different port
BACKEND_URL = "http://localhost:8000"
API_KEY = "debug"  # Development API key

async def get_discord_installation():
    """Find the Discord integration installation."""
    async with httpx.AsyncClient() as client:
        response = await client.get(
            f"{BACKEND_URL}/api/v1/integrations/installed",
            params={"organization_id": "default-org"},
            headers={"X-API-Key": API_KEY}
        )

        if response.status_code != 200:
            print(f"Error fetching installations: {response.status_code}")
            print(response.text)
            return None

        installations = response.json()
        for inst in installations:
            if inst.get("integration_id", "").lower() == "discord":
                return inst.get("installation_id")

        return None

async def execute_discord_action(installation_id: str, channel_id: str, message: str):
    """Execute Discord send_message action."""
    async with httpx.AsyncClient() as client:
        payload = {
            "installation_id": installation_id,
            "action_name": "send_message",
            "parameters": {
                "channel_id": channel_id,
                "content": message
            }
        }

        # Try the execute endpoint
        response = await client.post(
            f"{BACKEND_URL}/api/v1/integrations/discord/execute",
            json=payload,
            headers={
                "X-API-Key": API_KEY,
                "Content-Type": "application/json"
            },
            timeout=30.0
        )

        return response

async def test_discord_directly(channel_id: str, message: str):
    """Test Discord by calling the API directly."""
    print("=" * 60)
    print("Discord Direct Test")
    print("=" * 60)

    # Step 1: Find Discord installation
    print("\n1. Finding Discord installation...")
    installation_id = await get_discord_installation()

    if not installation_id:
        print("   ❌ No Discord installation found!")
        print("   → Go to Integrations page and install Discord first")
        print("   → Then configure it with your bot token")
        return False

    print(f"   ✅ Found installation: {installation_id}")

    # Step 2: Execute send_message
    print(f"\n2. Sending message to channel {channel_id}...")
    print(f"   Message: {message}")

    response = await execute_discord_action(installation_id, channel_id, message)

    print(f"\n3. Response:")
    print(f"   Status: {response.status_code}")

    if response.status_code == 200:
        print("   ✅ SUCCESS! Check your Discord channel.")
        result = response.json()
        print(f"   Response: {result}")
        return True
    else:
        print(f"   ❌ Failed: {response.text}")
        return False

async def test_discord_sdk_directly(bot_token: str, channel_id: str, message: str):
    """Test Discord SDK directly (bypasses database/API)."""
    print("=" * 60)
    print("Discord SDK Direct Test (No Database)")
    print("=" * 60)

    try:
        # Import the Discord integration directly
        sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
        from backend.shared.integrations.discord_integration import DiscordIntegration

        print("\n1. Creating Discord integration instance...")
        integration = DiscordIntegration(credentials={"bot_token": bot_token})

        print("\n2. Validating credentials...")
        is_valid = await integration.validate_credentials()

        if not is_valid:
            print("   ❌ Bot token is invalid!")
            return False

        print("   ✅ Bot token is valid")

        print(f"\n3. Sending message to channel {channel_id}...")
        result = await integration.execute_action("send_message", {
            "channel_id": channel_id,
            "content": message
        })

        if result.success:
            print("   ✅ SUCCESS! Check your Discord channel.")
            print(f"   Response: {result.data}")
            return True
        else:
            print(f"   ❌ Failed: {result.error}")
            return False

    except ImportError as e:
        print(f"   ❌ Import error: {e}")
        print("   Make sure you're in the right directory")
        return False
    except Exception as e:
        print(f"   ❌ Error: {e}")
        return False

def main():
    print("\n" + "=" * 60)
    print("🤖 Discord Integration Tester")
    print("=" * 60)

    # Check for bot token in environment
    bot_token = os.environ.get("DISCORD_BOT_TOKEN")

    if len(sys.argv) >= 3:
        channel_id = sys.argv[1]
        message = sys.argv[2]
    else:
        print("\nUsage: python test_discord_direct.py <channel_id> \"message\"")
        print("\nExample:")
        print("  python test_discord_direct.py 1234567890123456789 \"Hello World!\"")
        print("\nHow to get channel_id:")
        print("  1. In Discord: Settings → Advanced → Enable Developer Mode")
        print("  2. Right-click channel → Copy Channel ID")

        if bot_token:
            print(f"\n✅ DISCORD_BOT_TOKEN found in environment")
            print("   Running with default test message...")
            channel_id = input("\nEnter your Discord channel ID: ").strip()
            message = "Hello from the test script! 🎉"
        else:
            print(f"\n⚠️  DISCORD_BOT_TOKEN not found in environment")
            print("   Set it with: export DISCORD_BOT_TOKEN='your-token'")
            return

    if bot_token:
        # Direct SDK test (most reliable)
        asyncio.run(test_discord_sdk_directly(bot_token, channel_id, message))
    else:
        # Try via API (requires backend running and Discord configured)
        asyncio.run(test_discord_directly(channel_id, message))

if __name__ == "__main__":
    main()
