#!/bin/zsh
# Test: POST /transfers (requires authentication)
# Create a transfer between two accounts

cd "$(dirname "$0")/../.."
source scripts/integration/setup-env.sh || exit 1

echo ""
echo "🔄 Testing: POST /transfers"
echo ""
echo "Creating a transfer between two accounts..."
echo ""

# Sample transfer payload
read -r -d '' TRANSFER_DATA << 'JSON' || true
{
  "from_account_id": "550e8400-e29b-41d4-a716-446655440000",
  "to_account_id": "550e8400-e29b-41d4-a716-446655440001",
  "amount": 500.00,
  "date": "2025-11-06T14:30:00-06:00",
  "description": "Transfer between accounts"
}
JSON

echo "Payload:"
echo "$TRANSFER_DATA" | jq .
echo ""
echo "⚠️  Note: Replace from_account_id and to_account_id with real values from your account list"
echo ""

RESPONSE=$(curl -X POST http://localhost:8000/transfers \
  -H "Authorization: Bearer $REAL_TEST_TOKEN" \
  -H "Content-Type: application/json" \
  -d "$TRANSFER_DATA" \
  -w "\n%{http_code}" \
  -s)

# Extract body and status code
HTTP_STATUS=$(echo "$RESPONSE" | tail -n1)
BODY=$(echo "$RESPONSE" | sed '$d')

echo "$BODY" | jq . 2>/dev/null || echo "$BODY"
echo ""
echo "📊 Status Code: $HTTP_STATUS"
echo ""

# Save transaction IDs for use in other scripts
if [ "$HTTP_STATUS" = "201" ]; then
  FROM_TXN=$(echo "$BODY" | jq -r '.from_transaction_id' 2>/dev/null)
  TO_TXN=$(echo "$BODY" | jq -r '.to_transaction_id' 2>/dev/null)
  if [ -n "$FROM_TXN" ] && [ "$FROM_TXN" != "null" ]; then
    echo "✅ Transfer created"
    echo "   From Transaction ID: $FROM_TXN"
    echo "   To Transaction ID: $TO_TXN"
    echo "   These are linked transactions (paired_transaction_id)"
  fi
fi
