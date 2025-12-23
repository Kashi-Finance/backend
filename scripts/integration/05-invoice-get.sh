#!/bin/zsh
# Test: GET /invoices/{invoice_id} (requires authentication)
# Retrieve details of a specific invoice

cd "$(dirname "$0")/../.."

# Load environment
source scripts/integration/setup-env.sh || exit 1

echo ""
echo "🔍 Testing: GET /invoices/{invoice_id}"
echo ""

if [ -z "$1" ]; then
    echo "❌ Usage: ./05-invoice-get.sh <invoice_id>"
    echo ""
    echo "Example:"
    echo "  ./05-invoice-get.sh 550e8400-e29b-41d4-a716-446655440000"
    echo ""
    echo "To get invoice IDs, first run:"
    echo "  ./04-invoice-list.sh"
    echo ""
    exit 1
fi

INVOICE_ID="$1"
echo "Fetching invoice: $INVOICE_ID"
echo ""

curl -X GET "http://localhost:8000/invoices/$INVOICE_ID" \
  -H "Authorization: Bearer $REAL_TEST_TOKEN" \
  -H "Content-Type: application/json" \
  -w "\n\n📊 Status Code: %{http_code}\n" \
  -s | jq . 2>/dev/null || curl -X GET "http://localhost:8000/invoices/$INVOICE_ID" \
  -H "Authorization: Bearer $REAL_TEST_TOKEN" \
  -H "Content-Type: application/json" \
  -w "\n\n📊 Status Code: %{http_code}\n" \
  -s

echo ""
