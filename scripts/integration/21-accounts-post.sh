#!/bin/zsh
# Test: POST /accounts (requires authentication)
# Create a new financial account

cd "$(dirname "$0")/../.."
source scripts/integration/setup-env.sh || exit 1

echo ""
echo "💰 Testing: POST /accounts"
echo ""
echo "Creating a new financial account..."
echo ""

# Sample account creation payload
read -r -d '' ACCOUNT_DATA << 'JSON' || true
{
  "name": "Main Checking Account",
  "type": "bank",
  "currency": "GTQ"
}
JSON

echo "Payload:"
echo "$ACCOUNT_DATA" | jq .
echo ""

RESPONSE=$(curl -X POST http://localhost:8000/accounts \
  -H "Authorization: Bearer $REAL_TEST_TOKEN" \
  -H "Content-Type: application/json" \
  -d "$ACCOUNT_DATA" \
  -w "\n%{http_code}" \
  -s)

# Extract body and status code
HTTP_STATUS=$(echo "$RESPONSE" | tail -n1)
BODY=$(echo "$RESPONSE" | sed '$d')

echo "$BODY" | jq . 2>/dev/null || echo "$BODY"
echo ""
echo "📊 Status Code: $HTTP_STATUS"
echo ""

# Save account_id for use in other scripts
if [ "$HTTP_STATUS" = "201" ]; then
  ACCOUNT_ID=$(echo "$BODY" | jq -r '.account.id' 2>/dev/null)
  if [ -n "$ACCOUNT_ID" ] && [ "$ACCOUNT_ID" != "null" ]; then
    echo "✅ Account created with ID: $ACCOUNT_ID"
    echo "   Save this ID for testing GET, PATCH, DELETE operations."
  fi
fi
