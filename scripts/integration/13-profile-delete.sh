#!/bin/zsh
cd "$(dirname "$0")/../.."
source scripts/integration/setup-env.sh || exit 1
echo ""
echo "🗑️  Testing: DELETE /profile"
echo "⚠️  WARNING: This anonymizes the profile (does not fully delete)"
echo ""
curl -X DELETE http://localhost:8000/profile \
  -H "Authorization: Bearer $REAL_TEST_TOKEN" \
  -H "Content-Type: application/json" \
  -w "\n\n📊 Status Code: %{http_code}\n" \
  -s | jq . 2>/dev/null || curl -X DELETE http://localhost:8000/profile \
  -H "Authorization: Bearer $REAL_TEST_TOKEN" \
  -H "Content-Type: application/json" \
  -w "\n\n📊 Status Code: %{http_code}\n" \
  -s
echo ""
