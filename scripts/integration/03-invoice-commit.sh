#!/bin/zsh
# Test: POST /invoices/commit (requires authentication)
# Persist an invoice to the database

cd "$(dirname "$0")/../.."

# Load environment
source scripts/integration/setup-env.sh || exit 1

echo ""
echo "💾 Testing: POST /invoices/commit"
echo ""
echo "This endpoint persists an invoice to Supabase with the following data:"
echo ""

# Create sample invoice data (from a successful OCR response)
read -r -d '' INVOICE_DATA << 'JSON' || true
{
  "store_name": "Super Despensa Familiar",
  "transaction_time": "2025-11-06T14:30:00Z",
  "total_amount": "128.50",
  "currency": "GTQ",
  "purchased_items": "- Leche 1L (2x) @ Q12.50 = Q25.00\n- Pan integral @ Q15.00 = Q15.00\n- Huevos docena @ Q35.00 = Q35.00",
  "storage_path": "receipts/test-user/test-image.jpg"
}
JSON

echo "Payload:"
echo "$INVOICE_DATA" | jq .
echo ""

curl -X POST http://localhost:8000/invoices/commit \
  -H "Authorization: Bearer $REAL_TEST_TOKEN" \
  -H "Content-Type: application/json" \
  -d "$INVOICE_DATA" \
  -w "\n\n📊 Status Code: %{http_code}\n" \
  -s | jq . 2>/dev/null || curl -X POST http://localhost:8000/invoices/commit \
  -H "Authorization: Bearer $REAL_TEST_TOKEN" \
  -H "Content-Type: application/json" \
  -d "$INVOICE_DATA" \
  -w "\n\n📊 Status Code: %{http_code}\n" \
  -s

echo ""
