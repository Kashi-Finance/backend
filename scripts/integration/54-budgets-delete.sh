#!/bin/zsh
# Test: DELETE /budgets/{budget_id} (requires authentication)
# Delete a budget

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
echo "🗑️  Testing: DELETE /budgets/{budget_id}"
echo ""
echo "Budget ID: $BUDGET_ID"
echo "Note: Budget and category links will be deleted, but transactions remain"
echo ""

curl -X DELETE "http://localhost:8000/budgets/$BUDGET_ID" \
  -H "Authorization: Bearer $REAL_TEST_TOKEN" \
  -H "Content-Type: application/json" \
  -w "\n\n📊 Status Code: %{http_code}\n" \
  -s | jq . 2>/dev/null || curl -X DELETE "http://localhost:8000/budgets/$BUDGET_ID" \
  -H "Authorization: Bearer $REAL_TEST_TOKEN" \
  -H "Content-Type: application/json" \
  -w "\n\n📊 Status Code: %{http_code}\n" \
  -s

echo ""
