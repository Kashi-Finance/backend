#!/bin/zsh
# Test: GET /transactions (requires authentication)
# Fetch user's transactions with optional filters

cd "$(dirname "$0")/../.."
source scripts/integration/setup-env.sh || exit 1

echo ""
echo "💸 Testing: GET /transactions"
echo ""

LIMIT="${1:-50}"
OFFSET="${2:-0}"

# Build query string
QUERY="?limit=$LIMIT&offset=$OFFSET"

# Optional filters (pass as additional arguments)
# Usage: ./41-transactions-list.sh 50 0 account_id=<id> category_id=<id> flow_type=outcome
shift 2 2>/dev/null
while [ $# -gt 0 ]; do
  QUERY="$QUERY&$1"
  shift
done

curl -X GET "http://localhost:8000/transactions$QUERY" \
  -H "Authorization: Bearer $REAL_TEST_TOKEN" \
  -H "Content-Type: application/json" \
  -w "\n\n📊 Status Code: %{http_code}\n" \
  -s | jq . 2>/dev/null || curl -X GET "http://localhost:8000/transactions$QUERY" \
  -H "Authorization: Bearer $REAL_TEST_TOKEN" \
  -H "Content-Type: application/json" \
  -w "\n\n📊 Status Code: %{http_code}\n" \
  -s

echo ""
