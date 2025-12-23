#!/bin/zsh
# Test: GET /budgets with filtering
# Tests frequency and is_active query parameters

cd "$(dirname "$0")/../.."
source scripts/integration/setup-env.sh || exit 1

echo ""
echo "💰 Testing: GET /budgets with filtering"
echo ""

FREQUENCY="${1:-}"
IS_ACTIVE="${2:-}"

# Build query string
QUERY=""
if [ -n "$FREQUENCY" ]; then
  QUERY="?frequency=$FREQUENCY"
fi

if [ -n "$IS_ACTIVE" ]; then
  if [ -n "$QUERY" ]; then
    QUERY="$QUERY&is_active=$IS_ACTIVE"
  else
    QUERY="?is_active=$IS_ACTIVE"
  fi
fi

echo "🔍 Testing filters: frequency=$FREQUENCY, is_active=$IS_ACTIVE"
echo ""

curl -X GET "http://localhost:8000/budgets$QUERY" \
  -H "Authorization: Bearer $REAL_TEST_TOKEN" \
  -H "Content-Type: application/json" \
  -w "\n\n📊 Status Code: %{http_code}\n" \
  -s | jq . 2>/dev/null || curl -X GET "http://localhost:8000/budgets$QUERY" \
  -H "Authorization: Bearer $REAL_TEST_TOKEN" \
  -H "Content-Type: application/json" \
  -w "\n\n📊 Status Code: %{http_code}\n" \
  -s

echo ""
echo "💡 Usage examples:"
echo "  ./50b-budgets-list-filter.sh                    # No filters (all budgets)"
echo "  ./50b-budgets-list-filter.sh monthly            # Filter by monthly frequency"
echo "  ./50b-budgets-list-filter.sh weekly true        # Filter by weekly and active"
echo "  ./50b-budgets-list-filter.sh '' true            # Filter only by active status"
echo "  ./50b-budgets-list-filter.sh '' false           # Filter only by inactive status"
echo ""
echo "📝 Valid frequency values: daily, weekly, monthly, yearly, once"
echo ""
