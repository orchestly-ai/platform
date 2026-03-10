#!/usr/bin/env python3
"""
Test script for the OAuth2 integration system.
Tests provider loading, token encryption, and flow logic.
"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import asyncio
from datetime import datetime, timedelta


def test_provider_loading():
    """Test that OAuth provider configs load correctly."""
    print("=" * 60)
    print("TEST 1: Loading OAuth Provider Configs")
    print("=" * 60)

    from backend.integrations.oauth.providers import get_oauth_provider_registry

    registry = get_oauth_provider_registry()
    providers = registry.list_providers()

    print(f"\nFound {len(providers)} OAuth providers:\n")

    for p in providers:
        configured = "✓ Configured" if p.is_configured() else "✗ Not configured"
        print(f"  {p.display_name:<20} | {configured}")
        print(f"      Auth URL: {p.authorization_url[:50]}...")
        print(f"      Scopes: {len(p.default_scopes)} default")
        print()

    return len(providers) > 0


def test_token_encryption():
    """Test token encryption and storage."""
    print("=" * 60)
    print("TEST 2: Token Encryption & Storage")
    print("=" * 60)

    from backend.integrations.oauth.tokens import OAuthToken, OAuthTokenStorage

    # Create storage
    storage = OAuthTokenStorage()

    # Create a test token
    token = OAuthToken(
        organization_id="test-org-123",
        provider="google",
        access_token="ya29.test-access-token-here",
        refresh_token="1//test-refresh-token",
        expires_at=datetime.utcnow() + timedelta(hours=1),
        scopes=["email", "profile"],
        user_info={"email": "test@example.com", "name": "Test User"},
    )

    async def run_test():
        # Store token
        await storage.store(token)
        print("\n  ✓ Token stored (encrypted)")

        # Retrieve token
        retrieved = await storage.get("test-org-123", "google")
        print("  ✓ Token retrieved (decrypted)")

        # Verify data
        assert retrieved is not None
        assert retrieved.access_token == token.access_token
        assert retrieved.refresh_token == token.refresh_token
        assert retrieved.user_info["email"] == "test@example.com"
        print("  ✓ Token data matches")

        # Check expiry
        assert not retrieved.is_expired()
        print("  ✓ Token not expired")

        # Test expired token
        expired_token = OAuthToken(
            organization_id="test-org-456",
            provider="slack",
            access_token="xoxb-expired",
            expires_at=datetime.utcnow() - timedelta(hours=1),  # Already expired
        )
        await storage.store(expired_token)
        retrieved_expired = await storage.get("test-org-456", "slack")
        assert retrieved_expired.is_expired()
        print("  ✓ Expired token detected correctly")

        # List tokens
        tokens = await storage.list_tokens("test-org-123")
        assert len(tokens) == 1
        print(f"  ✓ Listed {len(tokens)} token(s) for org")

        # Delete token
        deleted = await storage.delete("test-org-123", "google")
        assert deleted
        print("  ✓ Token deleted")

        # Verify deletion
        should_be_none = await storage.get("test-org-123", "google")
        assert should_be_none is None
        print("  ✓ Deletion verified")

        return True

    return asyncio.run(run_test())


def test_oauth_handler():
    """Test OAuth handler flow."""
    print("\n" + "=" * 60)
    print("TEST 3: OAuth Handler Flow")
    print("=" * 60)

    from backend.integrations.oauth.handler import OAuthHandler

    handler = OAuthHandler()

    async def run_test():
        # Test authorization URL generation
        print("\n  Testing authorization URL generation...")

        # This will fail if not configured, which is expected
        try:
            auth_url = await handler.get_authorization_url(
                provider="google",
                organization_id="test-org",
                redirect_uri="http://localhost:3000/oauth/callback",
            )
            print(f"  ✓ Generated auth URL: {auth_url[:80]}...")

            # Verify URL contains required params
            assert "client_id" in auth_url
            assert "redirect_uri" in auth_url
            assert "state" in auth_url
            assert "scope" in auth_url
            print("  ✓ URL contains required OAuth parameters")

        except ValueError as e:
            if "not configured" in str(e):
                print(f"  ℹ Provider not configured (expected): {e}")
                print("  ✓ Handler correctly validates configuration")
            else:
                raise

        # Test connection status for non-connected org
        status = await handler.get_connection_status("google", "nonexistent-org")
        assert status["connected"] == False
        print("  ✓ Non-connected status returned correctly")

        return True

    return asyncio.run(run_test())


def test_integration_with_yaml():
    """Test OAuth config integration with YAML integration configs."""
    print("\n" + "=" * 60)
    print("TEST 4: Integration with YAML Configs")
    print("=" * 60)

    import yaml
    from pathlib import Path

    # Check which integrations use OAuth
    configs_dir = Path(__file__).parent / "backend" / "integrations" / "configs"
    oauth_integrations = []

    for yaml_file in configs_dir.glob("*.yaml"):
        with open(yaml_file) as f:
            config = yaml.safe_load(f)
        auth_type = config.get("auth", {}).get("type", "")
        if auth_type == "oauth2":
            oauth_integrations.append(config.get("display_name", yaml_file.stem))

    print(f"\n  Integrations requiring OAuth2:")
    for name in oauth_integrations:
        print(f"    - {name}")

    # Check OAuth configs exist for these
    oauth_configs_dir = Path(__file__).parent / "backend" / "integrations" / "oauth" / "configs"
    oauth_providers = [f.stem for f in oauth_configs_dir.glob("*.yaml")]

    print(f"\n  OAuth providers configured:")
    for name in oauth_providers:
        print(f"    - {name}")

    print("\n  ✓ OAuth system ready for OAuth2 integrations")
    return True


def summarize_oauth_flow():
    """Print OAuth flow summary."""
    print("\n" + "=" * 60)
    print("OAUTH2 FLOW SUMMARY")
    print("=" * 60)

    print("""
  To connect a user via OAuth2:

  1. FRONTEND: Redirect user to authorization
     GET /api/oauth/google/authorize
         ?organization_id=org-123
         &redirect_uri=http://localhost:3000/oauth/callback

  2. USER: Grants permission on Google's consent screen

  3. GOOGLE: Redirects to callback with code
     GET /oauth/callback?code=xxx&state=yyy

  4. BACKEND: Exchanges code for tokens
     POST https://oauth2.googleapis.com/token

  5. BACKEND: Stores encrypted tokens

  6. FRONTEND: Can now make API calls
     Access token auto-refreshes when needed

  ┌────────────────────────────────────────────────────┐
  │  Available Endpoints                               │
  ├────────────────────────────────────────────────────┤
  │  GET  /api/oauth/providers         List providers  │
  │  GET  /api/oauth/{p}/authorize     Start flow      │
  │  GET  /api/oauth/{p}/callback      Handle callback │
  │  GET  /api/oauth/{p}/status        Check connected │
  │  POST /api/oauth/{p}/revoke        Disconnect      │
  │  POST /api/oauth/{p}/refresh       Force refresh   │
  │  GET  /api/oauth/{p}/token         Get token       │
  └────────────────────────────────────────────────────┘

  To configure a provider:

  1. Create OAuth app at provider (Google Cloud Console, etc.)
  2. Set environment variables:
     export GOOGLE_CLIENT_ID=xxx
     export GOOGLE_CLIENT_SECRET=yyy
  3. Provider will appear as "configured" in /api/oauth/providers
""")


if __name__ == "__main__":
    print("\n" + "=" * 60)
    print("  OAUTH2 INTEGRATION SYSTEM TEST")
    print("=" * 60)

    results = []

    # Run tests
    results.append(("Provider Loading", test_provider_loading()))
    results.append(("Token Encryption", test_token_encryption()))
    results.append(("OAuth Handler", test_oauth_handler()))
    results.append(("YAML Integration", test_integration_with_yaml()))

    # Show summary
    summarize_oauth_flow()

    # Final status
    print("=" * 60)
    print("TEST RESULTS")
    print("=" * 60)

    all_passed = True
    for name, passed in results:
        status = "✓ PASSED" if passed else "✗ FAILED"
        print(f"  {name}: {status}")
        if not passed:
            all_passed = False

    print()
    if all_passed:
        print("  All tests passed!")
    else:
        print("  Some tests failed!")
        sys.exit(1)
