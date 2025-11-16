#!/bin/zsh
# Test: GET /transactions with sorting
# Tests sort_by (date|amount) and sort_order (asc|desc) query parameters

cd "$(dirname "$0")/../.."
source scripts/integration/setup-env.sh || exit 1

echo ""
echo "💸 Testing: GET /transactions with sorting"
echo ""

SORT_BY="${1:-date}"
SORT_ORDER="${2:-desc}"
LIMIT="${3:-10}"

echo "🔍 Testing sort_by=$SORT_BY, sort_order=$SORT_ORDER, limit=$LIMIT"
echo ""

curl -X GET "http://localhost:8000/transactions?sort_by=$SORT_BY&sort_order=$SORT_ORDER&limit=$LIMIT" \
  -H "Authorization: Bearer $REAL_TEST_TOKEN" \
  -H "Content-Type: application/json" \
  -w "\n\n📊 Status Code: %{http_code}\n" \
  -s | jq . 2>/dev/null || curl -X GET "http://localhost:8000/transactions?sort_by=$SORT_BY&sort_order=$SORT_ORDER&limit=$LIMIT" \
  -H "Authorization: Bearer $REAL_TEST_TOKEN" \
  -H "Content-Type: application/json" \
  -w "\n\n📊 Status Code: %{http_code}\n" \
  -s

echo ""
echo "💡 Usage examples:"
echo "  ./41b-transactions-list-sort.sh date desc 10  # Sort by date descending (default)"
echo "  ./41b-transactions-list-sort.sh date asc 10   # Sort by date ascending"
echo "  ./41b-transactions-list-sort.sh amount desc 10  # Sort by amount descending"
echo "  ./41b-transactions-list-sort.sh amount asc 10   # Sort by amount ascending"
echo ""
