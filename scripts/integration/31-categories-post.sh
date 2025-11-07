#!/bin/zsh
# Test: POST /categories (requires authentication)
# Create a new personal category

cd "$(dirname "$0")/../.."
source scripts/integration/setup-env.sh || exit 1

echo ""
echo "📂 Testing: POST /categories"
echo ""
echo "Creating a new personal category..."
echo ""

read -r -d '' CATEGORY_DATA << 'JSON' || true
{
  "name": "Groceries",
  "flow_type": "outcome"
}
JSON

echo "Payload:"
echo "$CATEGORY_DATA" | jq .
echo ""

RESPONSE=$(curl -X POST http://localhost:8000/categories \
  -H "Authorization: Bearer $REAL_TEST_TOKEN" \
  -H "Content-Type: application/json" \
  -d "$CATEGORY_DATA" \
  -w "\n%{http_code}" \
  -s)

# Extract body and status code
HTTP_STATUS=$(echo "$RESPONSE" | tail -n1)
BODY=$(echo "$RESPONSE" | sed '$d')

echo "$BODY" | jq . 2>/dev/null || echo "$BODY"
echo ""
echo "📊 Status Code: $HTTP_STATUS"
echo ""

# Save category_id for use in other scripts
if [ "$HTTP_STATUS" = "201" ]; then
  CATEGORY_ID=$(echo "$BODY" | jq -r '.category.id' 2>/dev/null)
  if [ -n "$CATEGORY_ID" ] && [ "$CATEGORY_ID" != "null" ]; then
    echo "✅ Category created with ID: $CATEGORY_ID"
    echo "   Save this ID for testing GET, PATCH, DELETE operations."
  fi
fi
