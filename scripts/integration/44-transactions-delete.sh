#!/bin/zsh
# Test: DELETE /transactions/{transaction_id} (requires authentication)
# Delete a transaction. If part of a transfer, deletes both sides.

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
echo "🗑️  Testing: DELETE /transactions/{transaction_id}"
echo ""
echo "Transaction ID: $TRANSACTION_ID"
echo "Note: If this is part of a transfer, both sides will be deleted"
echo ""

curl -X DELETE "http://localhost:8000/transactions/$TRANSACTION_ID" \
  -H "Authorization: Bearer $REAL_TEST_TOKEN" \
  -H "Content-Type: application/json" \
  -w "\n\n📊 Status Code: %{http_code}\n" \
  -s | jq . 2>/dev/null || curl -X DELETE "http://localhost:8000/transactions/$TRANSACTION_ID" \
  -H "Authorization: Bearer $REAL_TEST_TOKEN" \
  -H "Content-Type: application/json" \
  -w "\n\n📊 Status Code: %{http_code}\n" \
  -s

echo ""
