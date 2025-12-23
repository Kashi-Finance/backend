#!/bin/bash
# Integration test: Reject transfer edits via PATCH /transactions
# Tests that PATCH /transactions/{id} properly rejects transfer transactions

set -e

source "$(dirname "$0")/00-create-test-user.sh"

echo "========================================="
echo "Test: Reject Transfer Edit via PATCH /transactions"
echo "========================================="
echo ""

# Step 1: Get or create accounts
echo "Step 1: Getting accounts..."
ACCOUNTS_RESPONSE=$(curl -s -X GET "$API_BASE/accounts" \
  -H "Authorization: Bearer $ACCESS_TOKEN" \
  -H "Content-Type: application/json")

ACCOUNT1_ID=$(echo $ACCOUNTS_RESPONSE | jq -r '.accounts[0].id // empty')
ACCOUNT2_ID=$(echo $ACCOUNTS_RESPONSE | jq -r '.accounts[1].id // empty')

if [ -z "$ACCOUNT1_ID" ] || [ -z "$ACCOUNT2_ID" ]; then
  echo "Creating test accounts..."
  
  ACC1_RESPONSE=$(curl -s -X POST "$API_BASE/accounts" \
    -H "Authorization: Bearer $ACCESS_TOKEN" \
    -H "Content-Type: application/json" \
    -d '{
      "name": "Test Account 1",
      "initial_balance": 1000.0
    }')
  ACCOUNT1_ID=$(echo $ACC1_RESPONSE | jq -r '.id')
  
  ACC2_RESPONSE=$(curl -s -X POST "$API_BASE/accounts" \
    -H "Authorization: Bearer $ACCESS_TOKEN" \
    -H "Content-Type: application/json" \
    -d '{
      "name": "Test Account 2",
      "initial_balance": 500.0
    }')
  ACCOUNT2_ID=$(echo $ACC2_RESPONSE | jq -r '.id')
fi

echo "Using accounts: $ACCOUNT1_ID, $ACCOUNT2_ID"
echo ""

# Step 2: Create a transfer
echo "Step 2: Creating a transfer..."
TRANSFER_CREATE=$(curl -s -X POST "$API_BASE/transfers" \
  -H "Authorization: Bearer $ACCESS_TOKEN" \
  -H "Content-Type: application/json" \
  -d "{
    \"from_account_id\": \"$ACCOUNT1_ID\",
    \"to_account_id\": \"$ACCOUNT2_ID\",
    \"amount\": 100.0,
    \"date\": \"2025-11-15\",
    \"description\": \"Transfer to test rejection\"
  }")

TRANSACTION_ID=$(echo $TRANSFER_CREATE | jq -r '.transactions[0].id')

if [ -z "$TRANSACTION_ID" ] || [ "$TRANSACTION_ID" = "null" ]; then
  echo "❌ Failed to create transfer"
  exit 1
fi

echo "Transfer created with transaction ID: $TRANSACTION_ID"
echo ""

# Step 3: Attempt to edit via PATCH /transactions (should be rejected)
echo "Step 3: Attempting to edit transfer via PATCH /transactions (should fail)..."
EDIT_RESPONSE=$(curl -s -w "\n%{http_code}" -X PATCH "$API_BASE/transactions/$TRANSACTION_ID" \
  -H "Authorization: Bearer $ACCESS_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "amount": 150.0,
    "description": "Trying to edit via wrong endpoint"
  }')

HTTP_CODE=$(echo "$EDIT_RESPONSE" | tail -n1)
RESPONSE_BODY=$(echo "$EDIT_RESPONSE" | sed '$d')

echo "HTTP Status: $HTTP_CODE"
echo "Response: $RESPONSE_BODY"
echo ""

# Validate rejection
ERROR_CODE=$(echo $RESPONSE_BODY | jq -r '.detail.error // empty')

if [ "$HTTP_CODE" = "400" ] && [ "$ERROR_CODE" = "cannot_edit_transfer" ]; then
  echo "✅ Transfer edit rejection test PASSED"
  echo "   Transfer transactions correctly blocked from PATCH /transactions"
else
  echo "❌ Transfer edit rejection test FAILED"
  echo "   Expected HTTP 400 with error 'cannot_edit_transfer'"
  echo "   Got HTTP $HTTP_CODE with error '$ERROR_CODE'"
  exit 1
fi

echo ""
echo "========================================="
echo "✅ Transfer Edit Rejection Test PASSED"
echo "========================================="
