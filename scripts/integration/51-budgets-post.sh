#!/bin/zsh
# Test: POST /budgets (requires authentication)
# Create a new budget

cd "$(dirname "$0")/../.."
source scripts/integration/setup-env.sh || exit 1

echo ""
echo "💰 Testing: POST /budgets"
echo ""
echo "Creating a new budget..."
echo ""

# Sample budget payload - category_ids should be from your database
read -r -d '' BUDGET_DATA << 'JSON' || true
{
  "limit_amount": 500.00,
  "frequency": "monthly",
  "interval": 1,
  "start_date": "2025-11-01",
  "end_date": null,
  "is_active": true,
  "category_ids": ["550e8400-e29b-41d4-a716-446655440000", "550e8400-e29b-41d4-a716-446655440001"]
}
JSON

echo "Payload:"
echo "$BUDGET_DATA" | jq .
echo ""
echo "⚠️  Note: Replace category_ids with real values from your category list"
echo ""

RESPONSE=$(curl -X POST http://localhost:8000/budgets \
  -H "Authorization: Bearer $REAL_TEST_TOKEN" \
  -H "Content-Type: application/json" \
  -d "$BUDGET_DATA" \
  -w "\n%{http_code}" \
  -s)

# Extract body and status code
HTTP_STATUS=$(echo "$RESPONSE" | tail -n1)
BODY=$(echo "$RESPONSE" | sed '$d')

echo "$BODY" | jq . 2>/dev/null || echo "$BODY"
echo ""
echo "📊 Status Code: $HTTP_STATUS"
echo ""

# Save budget_id for use in other scripts
if [ "$HTTP_STATUS" = "201" ]; then
  BUDGET_ID=$(echo "$BODY" | jq -r '.budget.id' 2>/dev/null)
  if [ -n "$BUDGET_ID" ] && [ "$BUDGET_ID" != "null" ]; then
    echo "✅ Budget created with ID: $BUDGET_ID"
    echo "   Save this ID for testing GET, PATCH, DELETE operations."
  fi
fi
