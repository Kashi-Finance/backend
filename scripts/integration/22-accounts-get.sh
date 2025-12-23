#!/bin/zsh
# Test: GET /accounts/{account_id} (requires authentication)
# Retrieve details of a specific account

cd "$(dirname "$0")/../.."
source scripts/integration/setup-env.sh || exit 1

ACCOUNT_ID="${1:-}"

if [ -z "$ACCOUNT_ID" ]; then
  echo "❌ Usage: $0 <account_id>"
  echo ""
  echo "Example:"
  echo "  $0 550e8400-e29b-41d4-a716-446655440000"
  exit 1
fi

echo ""
echo "💰 Testing: GET /accounts/{account_id}"
echo ""
echo "Account ID: $ACCOUNT_ID"
echo ""

curl -X GET "http://localhost:8000/accounts/$ACCOUNT_ID" \
  -H "Authorization: Bearer $REAL_TEST_TOKEN" \
  -H "Content-Type: application/json" \
  -w "\n\n📊 Status Code: %{http_code}\n" \
  -s | jq . 2>/dev/null || curl -X GET "http://localhost:8000/accounts/$ACCOUNT_ID" \
  -H "Authorization: Bearer $REAL_TEST_TOKEN" \
  -H "Content-Type: application/json" \
  -w "\n\n📊 Status Code: %{http_code}\n" \
  -s

echo ""
