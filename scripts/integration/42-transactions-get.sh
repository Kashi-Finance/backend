#!/bin/zsh
# Test: GET /transactions/{transaction_id} (requires authentication)
# Retrieve a single transaction's details

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
echo "💸 Testing: GET /transactions/{transaction_id}"
echo ""
echo "Transaction ID: $TRANSACTION_ID"
echo ""

curl -X GET "http://localhost:8000/transactions/$TRANSACTION_ID" \
  -H "Authorization: Bearer $REAL_TEST_TOKEN" \
  -H "Content-Type: application/json" \
  -w "\n\n📊 Status Code: %{http_code}\n" \
  -s | jq . 2>/dev/null || curl -X GET "http://localhost:8000/transactions/$TRANSACTION_ID" \
  -H "Authorization: Bearer $REAL_TEST_TOKEN" \
  -H "Content-Type: application/json" \
  -w "\n\n📊 Status Code: %{http_code}\n" \
  -s

echo ""
