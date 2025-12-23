#!/bin/zsh
# Test: PATCH /budgets/{budget_id} (requires authentication)
# Update budget details

cd "$(dirname "$0")/../.."
source scripts/integration/setup-env.sh || exit 1

BUDGET_ID="${1:-}"

if [ -z "$BUDGET_ID" ]; then
  echo "❌ Usage: $0 <budget_id>"
  echo ""
  echo "Example:"
  echo "  $0 550e8400-e29b-41d4-a716-446655440000"
  exit 1
fi

echo ""
echo "💰 Testing: PATCH /budgets/{budget_id}"
echo ""
echo "Budget ID: $BUDGET_ID"
echo ""

read -r -d '' UPDATE_DATA << 'JSON' || true
{
  "limit_amount": 600.00,
  "is_active": false
}
JSON

echo "Payload:"
echo "$UPDATE_DATA" | jq .
echo ""

curl -X PATCH "http://localhost:8000/budgets/$BUDGET_ID" \
  -H "Authorization: Bearer $REAL_TEST_TOKEN" \
  -H "Content-Type: application/json" \
  -d "$UPDATE_DATA" \
  -w "\n\n📊 Status Code: %{http_code}\n" \
  -s | jq . 2>/dev/null || curl -X PATCH "http://localhost:8000/budgets/$BUDGET_ID" \
  -H "Authorization: Bearer $REAL_TEST_TOKEN" \
  -H "Content-Type: application/json" \
  -d "$UPDATE_DATA" \
  -w "\n\n📊 Status Code: %{http_code}\n" \
  -s

echo ""
