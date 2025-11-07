#!/bin/zsh
# Test: PATCH /transactions/{transaction_id} (requires authentication)
# Edit a transaction

cd "$(dirname "$0")/../.."
source scripts/integration/setup-env.sh || exit 1

TRANSACTION_ID="${1:-}"

if [ -z "$TRANSACTION_ID" ]; then
  echo "❌ Usage: $0 <transaction_id>"
  echo ""
  echo "Example:"
  echo "  $0 550e8400-e29b-41d4-a716-446655440000"
  exit 1
fi

echo ""
echo "💸 Testing: PATCH /transactions/{transaction_id}"
echo ""
echo "Transaction ID: $TRANSACTION_ID"
echo ""

read -r -d '' UPDATE_DATA << 'JSON' || true
{
  "amount": 150.00,
  "description": "Updated transaction description"
}
JSON

echo "Payload:"
echo "$UPDATE_DATA" | jq .
echo ""

curl -X PATCH "http://localhost:8000/transactions/$TRANSACTION_ID" \
  -H "Authorization: Bearer $REAL_TEST_TOKEN" \
  -H "Content-Type: application/json" \
  -d "$UPDATE_DATA" \
  -w "\n\n📊 Status Code: %{http_code}\n" \
  -s | jq . 2>/dev/null || curl -X PATCH "http://localhost:8000/transactions/$TRANSACTION_ID" \
  -H "Authorization: Bearer $REAL_TEST_TOKEN" \
  -H "Content-Type: application/json" \
  -d "$UPDATE_DATA" \
  -w "\n\n📊 Status Code: %{http_code}\n" \
  -s

echo ""
