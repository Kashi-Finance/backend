#!/bin/zsh
# Test: PATCH /accounts/{account_id} (requires authentication)
# Update an existing account

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
echo "💰 Testing: PATCH /accounts/{account_id}"
echo ""
echo "Account ID: $ACCOUNT_ID"
echo ""

read -r -d '' UPDATE_DATA << 'JSON' || true
{
  "name": "Updated Savings Account",
  "type": "cash",
  "currency": "USD"
}
JSON

echo "Payload:"
echo "$UPDATE_DATA" | jq .
echo ""

curl -X PATCH "http://localhost:8000/accounts/$ACCOUNT_ID" \
  -H "Authorization: Bearer $REAL_TEST_TOKEN" \
  -H "Content-Type: application/json" \
  -d "$UPDATE_DATA" \
  -w "\n\n📊 Status Code: %{http_code}\n" \
  -s | jq . 2>/dev/null || curl -X PATCH "http://localhost:8000/accounts/$ACCOUNT_ID" \
  -H "Authorization: Bearer $REAL_TEST_TOKEN" \
  -H "Content-Type: application/json" \
  -d "$UPDATE_DATA" \
  -w "\n\n📊 Status Code: %{http_code}\n" \
  -s

echo ""
