#!/bin/zsh
# Test: GET /recurring-transactions (requires authentication)
# List all recurring transaction rules

cd "$(dirname "$0")/../.."
source scripts/integration/setup-env.sh || exit 1

echo ""
echo "🔄 Testing: GET /recurring-transactions"
echo ""

curl -X GET http://localhost:8000/recurring-transactions \
  -H "Authorization: Bearer $REAL_TEST_TOKEN" \
  -H "Content-Type: application/json" \
  -w "\n\n📊 Status Code: %{http_code}\n" \
  -s | jq . 2>/dev/null || curl -X GET http://localhost:8000/recurring-transactions \
  -H "Authorization: Bearer $REAL_TEST_TOKEN" \
  -H "Content-Type: application/json" \
  -w "\n\n📊 Status Code: %{http_code}\n" \
  -s

echo ""
