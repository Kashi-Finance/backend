#!/bin/zsh
# Test: GET /budgets/{budget_id} (requires authentication)
# Retrieve details of a specific budget

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
echo "💰 Testing: GET /budgets/{budget_id}"
echo ""
echo "Budget ID: $BUDGET_ID"
echo ""

curl -X GET "http://localhost:8000/budgets/$BUDGET_ID" \
  -H "Authorization: Bearer $REAL_TEST_TOKEN" \
  -H "Content-Type: application/json" \
  -w "\n\n📊 Status Code: %{http_code}\n" \
  -s | jq . 2>/dev/null || curl -X GET "http://localhost:8000/budgets/$BUDGET_ID" \
  -H "Authorization: Bearer $REAL_TEST_TOKEN" \
  -H "Content-Type: application/json" \
  -w "\n\n📊 Status Code: %{http_code}\n" \
  -s

echo ""
