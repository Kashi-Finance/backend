#!/bin/zsh
# Test: DELETE /categories/{category_id} (requires authentication)
# Delete a user category and reassign transactions to 'general'

cd "$(dirname "$0")/../.."
source scripts/integration/setup-env.sh || exit 1

CATEGORY_ID="${1:-}"

if [ -z "$CATEGORY_ID" ]; then
  echo "❌ Usage: $0 <category_id>"
  echo ""
  echo "Example:"
  echo "  $0 550e8400-e29b-41d4-a716-446655440000"
  exit 1
fi

echo ""
echo "🗑️  Testing: DELETE /categories/{category_id}"
echo ""
echo "Category ID: $CATEGORY_ID"
echo "Note: Transactions will be reassigned to 'general' category"
echo ""

curl -X DELETE "http://localhost:8000/categories/$CATEGORY_ID" \
  -H "Authorization: Bearer $REAL_TEST_TOKEN" \
  -H "Content-Type: application/json" \
  -w "\n\n📊 Status Code: %{http_code}\n" \
  -s | jq . 2>/dev/null || curl -X DELETE "http://localhost:8000/categories/$CATEGORY_ID" \
  -H "Authorization: Bearer $REAL_TEST_TOKEN" \
  -H "Content-Type: application/json" \
  -w "\n\n📊 Status Code: %{http_code}\n" \
  -s

echo ""
