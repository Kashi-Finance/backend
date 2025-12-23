#!/bin/bash
# Integration test: Update transfer
# Tests PATCH /transfers/{id} endpoint

set -e

source "$(dirname "$0")/00-create-test-user.sh"

echo "========================================="
echo "Test: Update Transfer"
echo "========================================="
echo ""

# Step 1: Get user profile to find accounts
echo "Step 1: Fetching user profile to get accounts..."
PROFILE_RESPONSE=$(curl -s -X GET "$API_BASE/profile" \
  -H "Authorization: Bearer $ACCESS_TOKEN" \
  -H "Content-Type: application/json")

echo "Profile response: $PROFILE_RESPONSE"
echo ""

# Extract account IDs (assuming accounts are returned in profile or separate endpoint)
ACCOUNT1_ID=$(echo $PROFILE_RESPONSE | jq -r '.accounts[0].id // empty')
ACCOUNT2_ID=$(echo $PROFILE_RESPONSE | jq -r '.accounts[1].id // empty')

if [ -z "$ACCOUNT1_ID" ] || [ -z "$ACCOUNT2_ID" ]; then
  echo "Error: Need at least 2 accounts to test transfers"
  echo "Fetching accounts list..."
  
  ACCOUNTS_RESPONSE=$(curl -s -X GET "$API_BASE/accounts" \
    -H "Authorization: Bearer $ACCESS_TOKEN" \
    -H "Content-Type: application/json")
  
  echo "Accounts response: $ACCOUNTS_RESPONSE"
  
  ACCOUNT1_ID=$(echo $ACCOUNTS_RESPONSE | jq -r '.accounts[0].id // empty')
  ACCOUNT2_ID=$(echo $ACCOUNTS_RESPONSE | jq -r '.accounts[1].id // empty')
  
  if [ -z "$ACCOUNT1_ID" ] || [ -z "$ACCOUNT2_ID" ]; then
    echo "Still not enough accounts. Creating test accounts..."
    
    # Create account 1
    ACC1_RESPONSE=$(curl -s -X POST "$API_BASE/accounts" \
      -H "Authorization: Bearer $ACCESS_TOKEN" \
      -H "Content-Type: application/json" \
      -d '{
        "name": "Test Account 1",
        "initial_balance": 1000.0
      }')
    
    ACCOUNT1_ID=$(echo $ACC1_RESPONSE | jq -r '.id')
    
    # Create account 2
    ACC2_RESPONSE=$(curl -s -X POST "$API_BASE/accounts" \
      -H "Authorization: Bearer $ACCESS_TOKEN" \
      -H "Content-Type: application/json" \
      -d '{
        "name": "Test Account 2",
        "initial_balance": 500.0
      }')
    
    ACCOUNT2_ID=$(echo $ACC2_RESPONSE | jq -r '.id')
  fi
fi

echo "Using accounts:"
echo "  Account 1: $ACCOUNT1_ID"
echo "  Account 2: $ACCOUNT2_ID"
echo ""

# Step 2: Create a transfer
echo "Step 2: Creating initial transfer (200.00 from Account 1 to Account 2)..."
TRANSFER_CREATE=$(curl -s -X POST "$API_BASE/transfers" \
  -H "Authorization: Bearer $ACCESS_TOKEN" \
  -H "Content-Type: application/json" \
  -d "{
    \"from_account_id\": \"$ACCOUNT1_ID\",
    \"to_account_id\": \"$ACCOUNT2_ID\",
    \"amount\": 200.0,
    \"date\": \"2025-11-15\",
    \"description\": \"Initial transfer for testing\"
  }")

echo "Transfer created: $TRANSFER_CREATE"
echo ""

# Extract transaction ID (either leg)
TRANSACTION_ID=$(echo $TRANSFER_CREATE | jq -r '.transactions[0].id')

if [ -z "$TRANSACTION_ID" ] || [ "$TRANSACTION_ID" = "null" ]; then
  echo "❌ Failed to create transfer"
  exit 1
fi

echo "Transfer transaction ID: $TRANSACTION_ID"
echo ""

# Step 3: Update the transfer
echo "Step 3: Updating transfer (new amount: 250.00, new date, new description)..."
UPDATE_RESPONSE=$(curl -s -X PATCH "$API_BASE/transfers/$TRANSACTION_ID" \
  -H "Authorization: Bearer $ACCESS_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "amount": 250.0,
    "date": "2025-11-16",
    "description": "Updated transfer amount and date"
  }')

echo "Update response: $UPDATE_RESPONSE"
echo ""

# Validate response
STATUS=$(echo $UPDATE_RESPONSE | jq -r '.status')
UPDATED_AMOUNT=$(echo $UPDATE_RESPONSE | jq -r '.transactions[0].amount')
UPDATED_DATE=$(echo $UPDATE_RESPONSE | jq -r '.transactions[0].date')
UPDATED_DESC=$(echo $UPDATE_RESPONSE | jq -r '.transactions[0].description')

echo "Status: $STATUS"
echo "Updated amount: $UPDATED_AMOUNT"
echo "Updated date: $UPDATED_DATE"
echo "Updated description: $UPDATED_DESC"
echo ""

if [ "$STATUS" = "UPDATED" ] && [ "$UPDATED_AMOUNT" = "250" ]; then
  echo "✅ Transfer update test PASSED"
else
  echo "❌ Transfer update test FAILED"
  exit 1
fi

# Step 4: Verify both legs have the same values
echo "Step 4: Verifying both transaction legs have identical values..."
TXN1_AMOUNT=$(echo $UPDATE_RESPONSE | jq -r '.transactions[0].amount')
TXN2_AMOUNT=$(echo $UPDATE_RESPONSE | jq -r '.transactions[1].amount')
TXN1_DATE=$(echo $UPDATE_RESPONSE | jq -r '.transactions[0].date')
TXN2_DATE=$(echo $UPDATE_RESPONSE | jq -r '.transactions[1].date')
TXN1_DESC=$(echo $UPDATE_RESPONSE | jq -r '.transactions[0].description')
TXN2_DESC=$(echo $UPDATE_RESPONSE | jq -r '.transactions[1].description')

echo "Transaction 1: amount=$TXN1_AMOUNT, date=$TXN1_DATE, desc=$TXN1_DESC"
echo "Transaction 2: amount=$TXN2_AMOUNT, date=$TXN2_DATE, desc=$TXN2_DESC"
echo ""

if [ "$TXN1_AMOUNT" = "$TXN2_AMOUNT" ] && [ "$TXN1_DATE" = "$TXN2_DATE" ] && [ "$TXN1_DESC" = "$TXN2_DESC" ]; then
  echo "✅ Both transaction legs are synchronized"
else
  echo "❌ Transaction legs are NOT synchronized"
  exit 1
fi

# Step 5: Test partial update (only description)
echo "Step 5: Testing partial update (only description)..."
PARTIAL_UPDATE=$(curl -s -X PATCH "$API_BASE/transfers/$TRANSACTION_ID" \
  -H "Authorization: Bearer $ACCESS_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "description": "Only description changed"
  }')

echo "Partial update response: $PARTIAL_UPDATE"
echo ""

PARTIAL_DESC=$(echo $PARTIAL_UPDATE | jq -r '.transactions[0].description')
PARTIAL_AMOUNT=$(echo $PARTIAL_UPDATE | jq -r '.transactions[0].amount')

echo "Description after partial update: $PARTIAL_DESC"
echo "Amount after partial update (should remain 250): $PARTIAL_AMOUNT"
echo ""

if [ "$PARTIAL_DESC" = "Only description changed" ] && [ "$PARTIAL_AMOUNT" = "250" ]; then
  echo "✅ Partial update test PASSED"
else
  echo "❌ Partial update test FAILED"
  exit 1
fi

echo ""
echo "========================================="
echo "✅ All Transfer Update Tests PASSED"
echo "========================================="
