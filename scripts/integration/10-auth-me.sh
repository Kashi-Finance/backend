#!/bin/zsh
# Test: GET /auth/me (requires authentication)
# Return the authenticated user's core identity and profile

cd "$(dirname "$0")/../.."
source scripts/integration/setup-env.sh || exit 1

echo ""
echo "👤 Testing: GET /auth/me"
echo ""

curl -X GET http://localhost:8000/auth/me \
  -H "Authorization: Bearer $REAL_TEST_TOKEN" \
  -H "Content-Type: application/json" \
  -w "\n\n📊 Status Code: %{http_code}\n" \
  -s | jq . 2>/dev/null || curl -X GET http://localhost:8000/auth/me \
  -H "Authorization: Bearer $REAL_TEST_TOKEN" \
  -H "Content-Type: application/json" \
  -w "\n\n📊 Status Code: %{http_code}\n" \
  -s

echo ""
