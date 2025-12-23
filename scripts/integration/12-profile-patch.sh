#!/bin/zsh
cd "$(dirname "$0")/../.."
source scripts/integration/setup-env.sh || exit 1
echo ""
echo "✏️  Testing: PATCH /profile"
echo ""
read -r -d '' DATA << 'JSON' || true
{
  "first_name": "Samuel",
  "last_name": "Test User",
  "country": "GT"
}
JSON
echo "Payload:"
echo "$DATA" | jq .
echo ""
curl -X PATCH http://localhost:8000/profile \
  -H "Authorization: Bearer $REAL_TEST_TOKEN" \
  -H "Content-Type: application/json" \
  -d "$DATA" \
  -w "\n\n📊 Status Code: %{http_code}\n" \
  -s | jq . 2>/dev/null || curl -X PATCH http://localhost:8000/profile \
  -H "Authorization: Bearer $REAL_TEST_TOKEN" \
  -H "Content-Type: application/json" \
  -d "$DATA" \
  -w "\n\n📊 Status Code: %{http_code}\n" \
  -s
echo ""
