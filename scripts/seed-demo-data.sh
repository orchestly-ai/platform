#!/usr/bin/env bash
# Seed the Orchestly platform with demo data.
# Run after starting the API server.
#
# Usage:
#   ./scripts/seed-demo-data.sh              # defaults to localhost:8000
#   ./scripts/seed-demo-data.sh http://myhost:9000

set -euo pipefail

API="${1:-http://localhost:8000}"

echo "Orchestly — Seeding demo data against $API"
echo ""

# 1. Login
echo "→ Logging in as admin@example.com …"
TOKEN=$(curl -sf -X POST "$API/api/v1/auth/login" \
  -H "Content-Type: application/json" \
  -d '{"email":"admin@example.com","password":"admin123"}' \
  | python3 -c "import sys,json; print(json.load(sys.stdin)['access_token'])")
echo "  ✓ Authenticated"

AUTH="Authorization: Bearer $TOKEN"

# 2. Dismiss onboarding
curl -sf -X PUT "$API/api/v1/auth/me" \
  -H "Content-Type: application/json" \
  -H "$AUTH" \
  -d '{"preferences":{"onboarding_completed":true}}' > /dev/null
echo "  ✓ Onboarding dismissed"

# 3. Seed integrations
echo "→ Seeding integrations …"
curl -sf -X POST "$API/api/v1/seed/integrations" \
  -H "Content-Type: application/json" \
  -H "$AUTH" > /dev/null
echo "  ✓ Integrations seeded"

# 4. Seed marketplace agents
echo "→ Seeding marketplace agents …"
curl -sf -X POST "$API/api/v1/seed/marketplace-agents" \
  -H "Content-Type: application/json" \
  -H "$AUTH" > /dev/null
echo "  ✓ Marketplace agents seeded"

# 5. Seed workflows
echo "→ Seeding workflows …"
curl -sf -X POST "$API/api/v1/seed/workflows" \
  -H "Content-Type: application/json" \
  -H "$AUTH" > /dev/null
echo "  ✓ Workflows seeded"

echo ""
echo "✓ Done! Open http://localhost:3000 to see the populated dashboard."
echo "  Login: admin@example.com / admin123"
