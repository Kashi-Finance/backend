#!/bin/zsh
# Test: GET /invoices (requires authentication)
# List all invoices for the authenticated user

cd "$(dirname "$0")/../.."

# Load environment
source scripts/integration/setup-env.sh || exit 1

echo ""
echo "📋 Testing: GET /invoices"
echo ""
echo "Parameters (optional):"
echo "  - limit: max invoices to return (default: 50)"
echo "  - offset: skip N invoices for pagination (default: 0)"
echo ""
echo "Fetching invoices for authenticated user..."
echo ""

# Optional query parameters
LIMIT="${1:-50}"
OFFSET="${2:-0}"

curl -X GET "http://localhost:8000/invoices?limit=$LIMIT&offset=$OFFSET" \
  -H "Authorization: Bearer $REAL_TEST_TOKEN" \
  -H "Content-Type: application/json" \
  -w "\n\n📊 Status Code: %{http_code}\n" \
  -s | jq . 2>/dev/null || curl -X GET "http://localhost:8000/invoices?limit=$LIMIT&offset=$OFFSET" \
  -H "Authorization: Bearer $REAL_TEST_TOKEN" \
  -H "Content-Type: application/json" \
  -w "\n\n📊 Status Code: %{http_code}\n" \
  -s

echo ""
echo "Tip: Use pagination with limit and offset:"
echo "  ./04-invoice-list.sh 10 0   # First 10"
echo "  ./04-invoice-list.sh 10 10  # Next 10"
echo ""
