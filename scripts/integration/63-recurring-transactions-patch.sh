#!/bin/zsh
# Test: PATCH /recurring-transactions/{id} (requires authentication)
# Update a recurring transaction rule

cd "$(dirname "$0")/../.."
source scripts/integration/setup-env.sh || exit 1

RECURRING_ID="${1:-}"

if [ -z "$RECURRING_ID" ]; then
  echo "❌ Usage: $0 <recurring_transaction_id>"
  echo ""
  echo "Example:"
  echo "  $0 550e8400-e29b-41d4-a716-446655440000"
  exit 1
fi

echo ""
echo "🔄 Testing: PATCH /recurring-transactions/{id}"
echo ""
echo "Recurring Transaction ID: $RECURRING_ID"
echo ""

read -r -d '' UPDATE_DATA << 'JSON' || true
{
  "amount": 120.00,
  "description": "Updated Monthly Rent",
  "is_active": false
}
JSON

echo "Payload:"
echo "$UPDATE_DATA" | jq .
echo ""

curl -X PATCH "http://localhost:8000/recurring-transactions/$RECURRING_ID" \
  -H "Authorization: Bearer $REAL_TEST_TOKEN" \
  -H "Content-Type: application/json" \
  -d "$UPDATE_DATA" \
  -w "\n\n📊 Status Code: %{http_code}\n" \
  -s | jq . 2>/dev/null || curl -X PATCH "http://localhost:8000/recurring-transactions/$RECURRING_ID" \
  -H "Authorization: Bearer $REAL_TEST_TOKEN" \
  -H "Content-Type: application/json" \
  -d "$UPDATE_DATA" \
  -w "\n\n📊 Status Code: %{http_code}\n" \
  -s

echo ""
