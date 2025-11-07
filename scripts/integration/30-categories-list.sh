#!/bin/zsh
# Test: GET /categories (requires authentication)
# List all categories available to the authenticated user

cd "$(dirname "$0")/../.."
source scripts/integration/setup-env.sh || exit 1

echo ""
echo "📂 Testing: GET /categories"
echo ""

LIMIT="${1:-100}"
OFFSET="${2:-0}"

curl -X GET "http://localhost:8000/categories?limit=$LIMIT&offset=$OFFSET" \
  -H "Authorization: Bearer $REAL_TEST_TOKEN" \
  -H "Content-Type: application/json" \
  -w "\n\n📊 Status Code: %{http_code}\n" \
  -s | jq . 2>/dev/null || curl -X GET "http://localhost:8000/categories?limit=$LIMIT&offset=$OFFSET" \
  -H "Authorization: Bearer $REAL_TEST_TOKEN" \
  -H "Content-Type: application/json" \
  -w "\n\n📊 Status Code: %{http_code}\n" \
  -s

echo ""
