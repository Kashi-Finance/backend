#!/bin/zsh
# Test: DELETE /accounts/{account_id} (requires authentication)
# Delete an account with a specified strategy

cd "$(dirname "$0")/../.."
source scripts/integration/setup-env.sh || exit 1

ACCOUNT_ID="${1:-}"
STRATEGY="${2:-delete_transactions}"
TARGET_ACCOUNT="${3:-}"

if [ -z "$ACCOUNT_ID" ]; then
  echo "❌ Usage: $0 <account_id> [strategy] [target_account_id]"
  echo ""
  echo "Strategies:"
  echo "  delete_transactions - Delete all transactions in this account (DESTRUCTIVE)"
  echo "  reassign <target_id> - Reassign transactions to another account"
  echo ""
  echo "Examples:"
  echo "  $0 550e8400-e29b-41d4-a716-446655440000 delete_transactions"
  echo "  $0 550e8400-e29b-41d4-a716-446655440000 reassign 660e8400-e29b-41d4-a716-446655440001"
  exit 1
fi

echo ""
echo "🗑️  Testing: DELETE /accounts/{account_id}"
echo ""
echo "Account ID: $ACCOUNT_ID"
echo "Strategy: $STRATEGY"
echo ""

if [ "$STRATEGY" = "reassign" ]; then
  if [ -z "$TARGET_ACCOUNT" ]; then
    echo "❌ Target account ID required for reassign strategy"
    exit 1
  fi
  
  read -r -d '' DELETE_DATA << JSON || true
{
  "strategy": "reassign",
  "target_account_id": "$TARGET_ACCOUNT"
}
JSON
else
  read -r -d '' DELETE_DATA << 'JSON' || true
{
  "strategy": "delete_transactions",
  "target_account_id": null
}
JSON
fi

echo "Payload:"
echo "$DELETE_DATA" | jq .
echo ""

curl -X DELETE "http://localhost:8000/accounts/$ACCOUNT_ID" \
  -H "Authorization: Bearer $REAL_TEST_TOKEN" \
  -H "Content-Type: application/json" \
  -d "$DELETE_DATA" \
  -w "\n\n📊 Status Code: %{http_code}\n" \
  -s | jq . 2>/dev/null || curl -X DELETE "http://localhost:8000/accounts/$ACCOUNT_ID" \
  -H "Authorization: Bearer $REAL_TEST_TOKEN" \
  -H "Content-Type: application/json" \
  -d "$DELETE_DATA" \
  -w "\n\n📊 Status Code: %{http_code}\n" \
  -s

echo ""
