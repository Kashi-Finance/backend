#!/bin/zsh
# Test: POST /recurring-transactions (requires authentication)
# Create a new recurring transaction rule

cd "$(dirname "$0")/../.."
source scripts/integration/setup-env.sh || exit 1

echo ""
echo "🔄 Testing: POST /recurring-transactions"
echo ""
echo "Creating a new recurring transaction rule..."
echo ""

# Sample recurring transaction payload
read -r -d '' RECURRING_DATA << 'JSON' || true
{
  "account_id": "550e8400-e29b-41d4-a716-446655440000",
  "category_id": "550e8400-e29b-41d4-a716-446655440001",
  "flow_type": "outcome",
  "amount": 100.00,
  "description": "Monthly Rent",
  "frequency": "monthly",
  "interval": 1,
  "start_date": "2025-11-01",
  "end_date": null,
  "is_active": true
}
JSON

echo "Payload:"
echo "$RECURRING_DATA" | jq .
echo ""
echo "⚠️  Note: Replace account_id and category_id with real values from your database"
echo ""

RESPONSE=$(curl -X POST http://localhost:8000/recurring-transactions \
  -H "Authorization: Bearer $REAL_TEST_TOKEN" \
  -H "Content-Type: application/json" \
  -d "$RECURRING_DATA" \
  -w "\n%{http_code}" \
  -s)

# Extract body and status code
HTTP_STATUS=$(echo "$RESPONSE" | tail -n1)
BODY=$(echo "$RESPONSE" | sed '$d')

echo "$BODY" | jq . 2>/dev/null || echo "$BODY"
echo ""
echo "📊 Status Code: $HTTP_STATUS"
echo ""

# Save recurring_id for use in other scripts
if [ "$HTTP_STATUS" = "201" ]; then
  RECURRING_ID=$(echo "$BODY" | jq -r '.recurring_transaction.id' 2>/dev/null)
  if [ -n "$RECURRING_ID" ] && [ "$RECURRING_ID" != "null" ]; then
    echo "✅ Recurring transaction created with ID: $RECURRING_ID"
    echo "   Save this ID for testing GET, PATCH, DELETE operations."
  fi
fi
