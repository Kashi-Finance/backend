#!/bin/zsh
# Test: POST /transactions (requires authentication)
# Insert a transaction manually

cd "$(dirname "$0")/../.."
source scripts/integration/setup-env.sh || exit 1

echo ""
echo "💸 Testing: POST /transactions"
echo ""
echo "Creating a new manual transaction..."
echo ""

# Sample transaction payload - you'll need real IDs from your database
# Get account_id and category_id from running 20-accounts-list.sh and 30-categories-list.sh first
read -r -d '' TRANSACTION_DATA << 'JSON' || true
{
  "account_id": "550e8400-e29b-41d4-a716-446655440000",
  "category_id": "550e8400-e29b-41d4-a716-446655440001",
  "flow_type": "outcome",
  "amount": 128.50,
  "date": "2025-11-06T14:30:00-06:00",
  "description": "Super Despensa Familiar"
}
JSON

echo "Payload:"
echo "$TRANSACTION_DATA" | jq .
echo ""
echo "⚠️  Note: Replace account_id and category_id with real values from your account/category list"
echo ""

RESPONSE=$(curl -X POST http://localhost:8000/transactions \
  -H "Authorization: Bearer $REAL_TEST_TOKEN" \
  -H "Content-Type: application/json" \
  -d "$TRANSACTION_DATA" \
  -w "\n%{http_code}" \
  -s)

# Extract body and status code
HTTP_STATUS=$(echo "$RESPONSE" | tail -n1)
BODY=$(echo "$RESPONSE" | sed '$d')

echo "$BODY" | jq . 2>/dev/null || echo "$BODY"
echo ""
echo "📊 Status Code: $HTTP_STATUS"
echo ""

# Save transaction_id for use in other scripts
if [ "$HTTP_STATUS" = "201" ]; then
  TRANSACTION_ID=$(echo "$BODY" | jq -r '.transaction.id' 2>/dev/null)
  if [ -n "$TRANSACTION_ID" ] && [ "$TRANSACTION_ID" != "null" ]; then
    echo "✅ Transaction created with ID: $TRANSACTION_ID"
    echo "   Save this ID for testing GET, PATCH, DELETE operations."
  fi
fi
