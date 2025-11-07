#!/bin/zsh
# Run all integration tests in sequence

cd "$(dirname "$0")/../.."

echo "═══════════════════════════════════════════════════════════════════════════════"
echo "                    🚀 Running Integration Test Suite                          "
echo "═══════════════════════════════════════════════════════════════════════════════"
echo ""

# Load environment
source scripts/integration/setup-env.sh || exit 1

# Helper function to run test with pause
run_test() {
  local script=$1
  local name=$2
  echo ""
  echo "═══════════════════════════════════════════════════════════════════════════════"
  echo "$name"
  echo "═══════════════════════════════════════════════════════════════════════════════"
  "$script" || { echo "❌ Test failed"; }
  read -p "Press Enter to continue..."
}

# Health Check
echo ""
echo "═══════════════════════════════════════════════════════════════════════════════"
echo "0️⃣  HEALTH CHECK"
echo "═══════════════════════════════════════════════════════════════════════════════"
./scripts/integration/01-health-check.sh || { echo "❌ Health check failed"; exit 1; }
read -p "Press Enter to continue..."

# Invoice Tests
echo ""
echo "═══════════════════════════════════════════════════════════════════════════════"
echo "📋 INVOICE ENDPOINTS"
echo "═══════════════════════════════════════════════════════════════════════════════"
run_test "./scripts/integration/02-invoice-ocr.sh" "1️⃣  Invoice OCR"
run_test "./scripts/integration/03-invoice-commit.sh" "2️⃣  Invoice Commit"
run_test "./scripts/integration/04-invoice-list.sh" "3️⃣  Invoice List"

# Auth & Profile Tests
echo ""
echo "═══════════════════════════════════════════════════════════════════════════════"
echo "👤 AUTH & PROFILE ENDPOINTS"
echo "═══════════════════════════════════════════════════════════════════════════════"
run_test "./scripts/integration/10-auth-me.sh" "4️⃣  Auth Me"
run_test "./scripts/integration/11-profile-get.sh" "5️⃣  Profile Get"

# Account Tests
echo ""
echo "═══════════════════════════════════════════════════════════════════════════════"
echo "💰 ACCOUNT ENDPOINTS"
echo "═══════════════════════════════════════════════════════════════════════════════"
run_test "./scripts/integration/20-accounts-list.sh" "6️⃣  Accounts List"
run_test "./scripts/integration/21-accounts-post.sh" "7️⃣  Accounts Create"

# Category Tests
echo ""
echo "═══════════════════════════════════════════════════════════════════════════════"
echo "📂 CATEGORY ENDPOINTS"
echo "═══════════════════════════════════════════════════════════════════════════════"
run_test "./scripts/integration/30-categories-list.sh" "8️⃣  Categories List"
run_test "./scripts/integration/31-categories-post.sh" "9️⃣  Categories Create"

# Transaction Tests
echo ""
echo "═══════════════════════════════════════════════════════════════════════════════"
echo "💸 TRANSACTION ENDPOINTS"
echo "═══════════════════════════════════════════════════════════════════════════════"
run_test "./scripts/integration/41-transactions-list.sh" "🔟 Transactions List"

# Budget Tests
echo ""
echo "═══════════════════════════════════════════════════════════════════════════════"
echo "📊 BUDGET ENDPOINTS"
echo "═══════════════════════════════════════════════════════════════════════════════"
run_test "./scripts/integration/50-budgets-list.sh" "1️⃣0️⃣ Budgets List"

# Recurring Transactions Tests
echo ""
echo "═══════════════════════════════════════════════════════════════════════════════"
echo "🔄 RECURRING TRANSACTION ENDPOINTS"
echo "═══════════════════════════════════════════════════════════════════════════════"
run_test "./scripts/integration/60-recurring-transactions-list.sh" "1️⃣1️⃣ Recurring Transactions List"

# Transfers Tests
echo ""
echo "═══════════════════════════════════════════════════════════════════════════════"
echo "🔁 TRANSFER ENDPOINTS"
echo "═══════════════════════════════════════════════════════════════════════════════"
run_test "./scripts/integration/71-transfers-list.sh" "1️⃣2️⃣ Transfers List"

echo ""
echo "═══════════════════════════════════════════════════════════════════════════════"
echo "✅ Integration Test Suite Complete!"
echo "═══════════════════════════════════════════════════════════════════════════════"
echo ""
echo "📝 Available individual test scripts:"
echo ""
echo "   INVOICES:"
echo "   - ./scripts/integration/05-invoice-get.sh <invoice_id>"
echo ""
echo "   PROFILE:"
echo "   - ./scripts/integration/12-profile-patch.sh"
echo "   - ./scripts/integration/13-profile-delete.sh"
echo ""
echo "   ACCOUNTS:"
echo "   - ./scripts/integration/22-accounts-get.sh <account_id>"
echo "   - ./scripts/integration/23-accounts-patch.sh <account_id>"
echo "   - ./scripts/integration/24-accounts-delete.sh <account_id>"
echo ""
echo "   CATEGORIES:"
echo "   - ./scripts/integration/32-categories-get.sh <category_id>"
echo "   - ./scripts/integration/33-categories-patch.sh <category_id>"
echo "   - ./scripts/integration/34-categories-delete.sh <category_id>"
echo ""
echo "   TRANSACTIONS:"
echo "   - ./scripts/integration/40-transactions-post.sh"
echo "   - ./scripts/integration/42-transactions-get.sh <transaction_id>"
echo "   - ./scripts/integration/43-transactions-patch.sh <transaction_id>"
echo "   - ./scripts/integration/44-transactions-delete.sh <transaction_id>"
echo ""
echo "   BUDGETS:"
echo "   - ./scripts/integration/51-budgets-post.sh"
echo "   - ./scripts/integration/52-budgets-get.sh <budget_id>"
echo "   - ./scripts/integration/53-budgets-patch.sh <budget_id>"
echo "   - ./scripts/integration/54-budgets-delete.sh <budget_id>"
echo ""
echo "   RECURRING TRANSACTIONS:"
echo "   - ./scripts/integration/61-recurring-transactions-post.sh"
echo "   - ./scripts/integration/62-recurring-transactions-get.sh <recurring_id>"
echo "   - ./scripts/integration/63-recurring-transactions-patch.sh <recurring_id>"
echo "   - ./scripts/integration/64-recurring-transactions-delete.sh <recurring_id>"
echo ""
echo "   TRANSFERS:"
echo "   - ./scripts/integration/70-transfers-post.sh"
echo ""
