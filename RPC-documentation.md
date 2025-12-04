# Kashi Finances — RPC Functions Index

> **Quick reference for PostgreSQL RPC functions with pointers to detailed documentation.**
>
> This file follows Anthropic's progressive disclosure pattern: concise index here, full details in [docs/rpc/](./docs/rpc/).

**Last Updated:** December 1, 2025  
**Total RPCs:** 25  
**Architecture:** Supabase + PostgreSQL + SECURITY DEFINER functions

---

## Navigation

| Category | Quick Ref | Full Docs |
|----------|-----------|-----------|
| Accounts | [Section 2](#2-account-management) | [docs/rpc/accounts.md](./docs/rpc/accounts.md) |
| Transactions | [Section 3](#3-transaction-management) | [docs/rpc/transactions.md](./docs/rpc/transactions.md) |
| Categories | [Section 4](#4-category-management) | [docs/rpc/categories.md](./docs/rpc/categories.md) |
| Transfers | [Section 5](#5-transfer-management) | [docs/rpc/transfers.md](./docs/rpc/transfers.md) |
| Recurring | [Section 6](#6-recurring-transaction-management) | [docs/rpc/recurring.md](./docs/rpc/recurring.md) |
| Wishlists | [Section 7](#7-wishlist-management) | [docs/rpc/wishlists.md](./docs/rpc/wishlists.md) |
| Invoices | [Section 8](#8-invoice-management) | [docs/rpc/invoices.md](./docs/rpc/invoices.md) |
| Budgets | [Section 9](#9-budget-management) | [docs/rpc/budgets.md](./docs/rpc/budgets.md) |
| Cache | [Section 10](#10-cache-recomputation) | [docs/rpc/guidelines.md](./docs/rpc/guidelines.md) |
| Currency | [Section 11](#11-currency-validation) | [docs/rpc/currency.md](./docs/rpc/currency.md) |
| Favorites | [Section 12](#12-favorite-account-management) | [docs/rpc/favorites.md](./docs/rpc/favorites.md) |
| Engagement | [Section 13](#13-engagement--streak) | [docs/rpc/engagement.md](./docs/rpc/engagement.md) |
| Guidelines | [Section 0](#0-rpc-principles--guidelines) | [docs/rpc/guidelines.md](./docs/rpc/guidelines.md) |

---

## 0. RPC Principles & Guidelines

**Core Principles:**

1. **Always pass `user_id`** — Extract from Supabase Auth token, never trust client
2. **SECURITY DEFINER** — All RPCs bypass RLS but validate ownership explicitly  
3. **Atomicity** — All operations wrapped in single DB transaction
4. **Soft-delete by default** — Used for accounts, transactions, invoices, budgets, recurring
5. **Hard-delete when simple** — Used for categories, wishlists (no audit needed)
6. **RLS validation** — Every RPC validates `user_id = auth.uid()` before proceeding

**Error Handling:**
- RPCs raise `EXCEPTION` on validation failure
- Backend converts to HTTP 400/403/404
- Never expose raw exception messages to client

**Testing Requirements:**
- Happy path: valid inputs, successful operations
- Ownership validation: reject wrong `user_id`
- Edge cases: empty results, zero amounts, null fields
- Atomicity: verify transaction consistency on rollback

📖 **Full guidelines:** [docs/rpc/guidelines.md](./docs/rpc/guidelines.md)

---

## 1. Quick Reference by Function

| Function | Purpose | Returns | Status |
|----------|---------|---------|--------|
| **Account Management** |
| `delete_account_reassign` | Soft-delete + reassign transactions | `(count, count, boolean, timestamptz)` | ✅ Active |
| `delete_account_cascade` | Soft-delete + cascade all data | `(count, count, boolean, timestamptz)` | ✅ Active |
| `set_favorite_account` | Set favorite account (max 1) | `(uuid, uuid, boolean)` | ✅ Active |
| `clear_favorite_account` | Clear favorite status | `(boolean)` | ✅ Active |
| `get_favorite_account` | Get user's favorite account | `uuid` or `NULL` | ✅ Active |
| **Transaction Management** |
| `delete_transaction` | Soft-delete single transaction | `(boolean, timestamptz)` | ✅ Active |
| **Category Management** |
| `delete_category_reassign` | Delete + reassign transactions | `(count, boolean)` | ✅ Active |
| **Transfer Management** |
| `create_transfer` | Create paired transactions | `(uuid, uuid)` | ✅ Active |
| `update_transfer` | Update both paired transactions | `(uuid, uuid, count)` | ✅ Active |
| `delete_transfer` | Soft-delete both paired transactions | `(count)` | ✅ Active |
| **Recurring Transactions** |
| `sync_recurring_transactions` | Generate pending transactions | `(count, count)` | ✅ Active |
| `create_recurring_transfer` | Create paired templates | `(uuid, uuid)` | ✅ Active |
| `delete_recurring_transaction` | Soft-delete template | `(boolean, timestamptz)` | ✅ Active |
| `delete_recurring_and_pair` | Soft-delete both templates | `(count)` | ✅ Active |
| **Wishlist Management** |
| `create_wishlist_with_items` | Create + add items atomically | `(uuid, count)` | ✅ Active |
| **Invoice Management** |
| `delete_invoice` | Soft-delete invoice | `(boolean, timestamptz)` | ✅ Active |
| **Budget Management** |
| `delete_budget` | Soft-delete budget | `(boolean, timestamptz)` | ✅ Active |
| `recompute_budget_consumption` | Recalculate cached consumption | `numeric(12,2)` | ✅ Active |
| **Cache Recomputation** |
| `recompute_account_balance` | Recalculate cached balance | `numeric(12,2)` | ✅ Active |
| **Currency Validation** |
| `validate_user_currency` | Validate currency matches profile | `boolean` | ✅ Active |
| `get_user_currency` | Get user's currency preference | `text` | ✅ Active |
| `can_change_user_currency` | Check if currency can be changed | `boolean` | ✅ Active |
| **Engagement & Streak** |
| `update_user_streak` | Update streak after activity | `(count, count, boolean, boolean, boolean)` | ✅ Active |
| `get_user_streak` | Get streak status with risk | `(count, count, date, boolean, boolean, count)` | ✅ Active |
| `reset_weekly_streak_freezes` | Reset all user freezes (cron job) | `count` | ✅ Active |

---

## 2. Account Management

### Overview

**RPCs:** 5 total (2 deletion strategies, 3 favorite management)

| Function | Purpose | Quick Signature |
|----------|---------|-----------------|
| `delete_account_reassign` | Soft-delete after reassigning transactions | `(uuid, uuid, uuid) → (int, int, bool, timestamptz)` |
| `delete_account_cascade` | Soft-delete with cascade | `(uuid, uuid) → (int, int, bool, timestamptz)` |
| `set_favorite_account` | Set as favorite (1 per user) | `(uuid, uuid) → (uuid, uuid, bool)` |
| `clear_favorite_account` | Clear favorite status | `(uuid, uuid) → (bool)` |
| `get_favorite_account` | Retrieve favorite account ID | `(uuid) → uuid or NULL` |

**Common Usage Pattern:**
```python
# Delete with reassignment
result = supabase.rpc('delete_account_reassign', {
    'p_account_id': source_uuid,
    'p_user_id': user_uuid,
    'p_target_account_id': dest_uuid
}).execute()

# Set favorite
result = supabase.rpc('set_favorite_account', {
    'p_account_id': account_uuid,
    'p_user_id': user_uuid
}).execute()
```

**Key Details:**
- `delete_account_reassign` vs `delete_account_cascade` choose different strategies
- Source account becomes invisible (RLS filters `deleted_at IS NULL`)
- Paired transfers properly handled (FK references cleared)
- Only 1 favorite per user (automatically unsets previous)

📖 **Full details:** [docs/rpc/accounts.md](./docs/rpc/accounts.md)

---

## 3. Transaction Management

### Overview

**RPCs:** 1 total (soft-delete)

| Function | Purpose | Quick Signature |
|----------|---------|-----------------|
| `delete_transaction` | Soft-delete single transaction | `(uuid, uuid) → (bool, timestamptz)` |

**Common Usage Pattern:**
```python
result = supabase.rpc('delete_transaction', {
    'p_transaction_id': transaction_uuid,
    'p_user_id': user_uuid
}).execute()
```

**Key Details:**
- Transaction becomes invisible to user queries (RLS)
- Account balance caches may need recomputation
- Does NOT clear `paired_transaction_id` (use `delete_transfer` for transfers)

📖 **Full details:** [docs/rpc/transactions.md](./docs/rpc/transactions.md)

---

## 4. Category Management

### Overview

**RPCs:** 1 total (delete with reassignment)

| Function | Purpose | Quick Signature |
|----------|---------|-----------------|
| `delete_category_reassign` | Delete category + reassign transactions | `(uuid, uuid, uuid) → (int, bool)` |

**Common Usage Pattern:**
```python
result = supabase.rpc('delete_category_reassign', {
    'p_category_id': category_uuid,
    'p_user_id': user_uuid,
    'p_fallback_category_id': general_uuid  # Usually "general"
}).execute()
```

**Key Details:**
- **Hard-delete** (not soft-delete) — categories don't need audit trail
- System categories (`key` field set) cannot be deleted
- Typically reassign to flow-specific "general" category

�� **Full details:** [docs/rpc/categories.md](./docs/rpc/categories.md)

---

## 5. Transfer Management

### Overview

**RPCs:** 3 total (create, update, delete)

| Function | Purpose | Quick Signature |
|----------|---------|-----------------|
| `create_transfer` | Atomically create paired transactions | `(uuid, uuid, uuid, numeric, text, timestamptz) → (uuid, uuid)` |
| `update_transfer` | Update both paired transactions | `(uuid, uuid, ...) → (uuid, uuid, int)` |
| `delete_transfer` | Soft-delete both paired transactions | `(uuid, uuid) → (int)` |

**Common Usage Pattern:**
```python
# Create transfer
result = supabase.rpc('create_transfer', {
    'p_user_id': user_uuid,
    'p_from_account_id': source_uuid,
    'p_to_account_id': dest_uuid,
    'p_amount': 150.00,
    'p_description': 'Transfer to savings',
    'p_date': '2025-11-15T14:30:00Z'
}).execute()

# Delete transfer (pass either transaction UUID)
result = supabase.rpc('delete_transfer', {
    'p_transaction_id': either_transaction_uuid,
    'p_user_id': user_uuid
}).execute()
```

**Key Details:**
- Both transactions created atomically
- Uses system "transfer" category automatically
- Paired transactions linked via `paired_transaction_id`
- `delete_transfer` finds and deletes both (pass either UUID)

📖 **Full details:** [docs/rpc/transfers.md](./docs/rpc/transfers.md)

---

## 6. Recurring Transaction Management

### Overview

**RPCs:** 4 total (sync, create recurring transfer, delete single, delete paired)

| Function | Purpose | Quick Signature |
|----------|---------|-----------------|
| `sync_recurring_transactions` | Generate pending transactions up to date | `(uuid, date) → (int, int)` |
| `create_recurring_transfer` | Create paired recurring templates | `(uuid, uuid, uuid, numeric, ...) → (uuid, uuid)` |
| `delete_recurring_transaction` | Soft-delete single template | `(uuid, uuid) → (bool, timestamptz)` |
| `delete_recurring_and_pair` | Soft-delete both templates | `(uuid, uuid) → (int)` |

**Common Usage Pattern:**
```python
# Sync pending recurring transactions
result = supabase.rpc('sync_recurring_transactions', {
    'p_user_id': user_uuid,
    'p_today': '2025-11-15'  # ISO date
}).execute()

# Create recurring transfer
result = supabase.rpc('create_recurring_transfer', {
    'p_user_id': user_uuid,
    'p_from_account_id': checking_uuid,
    'p_to_account_id': savings_uuid,
    'p_amount': 500.00,
    'p_description': 'Monthly savings',
    'p_frequency': 'monthly',
    'p_interval': 1,
    'p_start_date': '2025-12-01',
    'p_end_date': None
}).execute()
```

**Key Details:**
- `sync_recurring_transactions` should be called daily by scheduler
- Idempotent: safe to call multiple times for same date
- Supports: daily, weekly, monthly, yearly frequencies
- Generated transactions marked with `system_generated_key = 'recurring_sync'`

📖 **Full details:** [docs/rpc/recurring.md](./docs/rpc/recurring.md)

---

## 7. Wishlist Management

### Overview

**RPCs:** 1 total (create with items atomically)

| Function | Purpose | Quick Signature |
|----------|---------|-----------------|
| `create_wishlist_with_items` | Create wishlist + add items atomically | `(uuid, text, jsonb) → (uuid, int)` |

**Common Usage Pattern:**
```python
result = supabase.rpc('create_wishlist_with_items', {
    'p_user_id': user_uuid,
    'p_name': 'Tech purchases 2025',
    'p_items': [
        {
            'description': 'Gaming laptop',
            'estimated_price': 1200.00,
            'priority': 'high',
            'url': 'https://example.com/laptop'
        }
    ]
}).execute()
```

**Key Details:**
- All items inserted atomically with wishlist
- `wishlist_item` has FK cascade on wishlist deletion

📖 **Full details:** [docs/rpc/wishlists.md](./docs/rpc/wishlists.md)

---

## 8. Invoice Management

### Overview

**RPCs:** 1 total (soft-delete)

| Function | Purpose | Quick Signature |
|----------|---------|-----------------|
| `delete_invoice` | Soft-delete invoice (set deleted_at) | `(uuid, uuid) → (bool, timestamptz)` |

**Common Usage Pattern:**
```python
result = supabase.rpc('delete_invoice', {
    'p_invoice_id': invoice_uuid,
    'p_user_id': user_uuid
}).execute()
```

**Key Details:**
- Invoice becomes invisible (RLS filters `deleted_at IS NULL`)
- Storage cleanup should be handled by backend service layer
- Related transactions remain intact

📖 **Full details:** [docs/rpc/invoices.md](./docs/rpc/invoices.md)

---

## 9. Budget Management

### Overview

**RPCs:** 2 total (soft-delete, recompute consumption)

| Function | Purpose | Quick Signature |
|----------|---------|-----------------|
| `delete_budget` | Soft-delete budget | `(uuid, uuid) → (bool, timestamptz)` |
| `recompute_budget_consumption` | Recalculate cached consumption for period | `(uuid, uuid, date, date) → numeric(12,2)` |

**Common Usage Pattern:**
```python
# Delete budget
result = supabase.rpc('delete_budget', {
    'p_budget_id': budget_uuid,
    'p_user_id': user_uuid
}).execute()

# Recompute consumption
result = supabase.rpc('recompute_budget_consumption', {
    'p_budget_id': budget_uuid,
    'p_user_id': user_uuid,
    'p_period_start': '2025-11-01',
    'p_period_end': '2025-11-30'
}).execute()

consumption = result.data  # numeric value
```

**Key Details:**
- `delete_budget` keeps `budget_category` junction for audit
- `recompute_budget_consumption` only sums **outcome** transactions
- Date range is inclusive: `[p_period_start, p_period_end]`

📖 **Full details:** [docs/rpc/budgets.md](./docs/rpc/budgets.md)

---

## 10. Cache Recomputation

### Overview

**RPCs:** 2 total (account balance, budget consumption)

**Cached Fields:**
- `account.cached_balance` — Sum of all account transactions
- `budget.cached_consumption` — Sum of category transactions in period

**When to Call:**
- After bulk reassignment operations
- After soft-deleting transactions
- After restoring soft-deleted data
- Periodic verification (recommended: daily background job)

| Function | Purpose | Quick Signature |
|----------|---------|-----------------|
| `recompute_account_balance` | Recalculate account balance from transactions | `(uuid, uuid) → numeric(12,2)` |
| `recompute_budget_consumption` | Recalculate budget consumption for period | `(uuid, uuid, date, date) → numeric(12,2)` |
| `recompute_budgets_for_category` | Recalculate all budgets tracking a category | `(uuid, uuid) → TABLE(budget_id, budget_name, old_consumption, new_consumption)` |

**Common Usage Pattern:**
```python
# Recompute account balance
result = supabase.rpc('recompute_account_balance', {
    'p_account_id': account_uuid,
    'p_user_id': user_uuid
}).execute()

new_balance = result.data  # numeric value

# Recompute all budgets tracking a category (after transaction CRUD)
result = supabase.rpc('recompute_budgets_for_category', {
    'p_user_id': user_uuid,
    'p_category_id': category_uuid
}).execute()
# Returns list of affected budgets with old/new consumption values
```

**Key Details:**
- Only counts transactions where `deleted_at IS NULL`
- Updates `updated_at` timestamp on affected row
- Atomic operation (transaction-safe)

📖 **Full details:** [docs/rpc/guidelines.md](./docs/rpc/guidelines.md)

---

## 11. Currency Validation

### Overview

**RPCs:** 3 total (validate, get, check if changeable)

| Function | Purpose | Quick Signature |
|----------|---------|-----------------|
| `validate_user_currency` | Validate currency matches profile | `(uuid, text) → bool` |
| `get_user_currency` | Get user's currency preference | `(uuid) → text` |
| `can_change_user_currency` | Check if currency can be changed | `(uuid) → bool` |

**Enforces single-currency-per-user policy.**

**Common Usage Pattern:**
```python
# Validate currency
try:
    supabase.rpc('validate_user_currency', {
        'p_user_id': user_uuid,
        'p_currency': 'USD'
    }).execute()
except Exception as e:
    if "Currency mismatch" in str(e):
        raise ValueError("Currency doesn't match profile")

# Get user's currency
result = supabase.rpc('get_user_currency', {
    'p_user_id': user_uuid
}).execute()
currency = result.data  # e.g., "GTQ"

# Check if currency can be changed
result = supabase.rpc('can_change_user_currency', {
    'p_user_id': user_uuid
}).execute()
can_change = result.data  # bool
```

**Key Details:**
- `can_change_user_currency` returns false if user has accounts, wishlists, or budgets
- Enforces single currency across all financial data

📖 **Full details:** [docs/rpc/currency.md](./docs/rpc/currency.md)

---

## 12. Favorite Account Management

### Overview

**RPCs:** 3 total (set, clear, get)

| Function | Purpose | Quick Signature |
|----------|---------|-----------------|
| `set_favorite_account` | Set account as favorite (1 per user) | `(uuid, uuid) → (uuid, uuid, bool)` |
| `clear_favorite_account` | Clear favorite status | `(uuid, uuid) → (bool)` |
| `get_favorite_account` | Get user's favorite account | `(uuid) → uuid or NULL` |

**Used for auto-selecting account in manual transaction creation.**

**Common Usage Pattern:**
```python
# Set favorite
result = supabase.rpc('set_favorite_account', {
    'p_account_id': account_uuid,
    'p_user_id': user_uuid
}).execute()
row = result.data[0]
# row['previous_favorite_id'] - previous favorite (or None)
# row['new_favorite_id'] - newly favorited account
# row['success'] - always True if no exception

# Get favorite
result = supabase.rpc('get_favorite_account', {
    'p_user_id': user_uuid
}).execute()
favorite_account_id = result.data  # UUID or None
```

**Key Details:**
- Only one account per user can be favorite
- Atomically unsets previous favorite when setting new one
- Safe for concurrent calls
- Returns `NULL` if no favorite set

📖 **Full details:** [docs/rpc/favorites.md](./docs/rpc/favorites.md)

---

## 13. Engagement & Streak

### Overview

**RPCs:** 3 total (update after activity, get status, reset weekly freezes)

| Function | Purpose | Quick Signature |
|----------|---------|-----------------|
| `update_user_streak` | Update streak after transaction/invoice | `(uuid) → (int, int, bool, bool, bool)` |
| `get_user_streak` | Get streak status with risk assessment | `(uuid) → (int, int, date, bool, bool, int)` |
| `reset_weekly_streak_freezes` | Reset all freezes (cron job only) | `() → int` |

**Implements gamification: daily activity streaks with freeze protection.**

**Common Usage Pattern:**
```python
# Update after transaction creation (non-blocking)
try:
    result = supabase.rpc('update_user_streak', {
        'p_user_id': user_uuid
    }).execute()
    streak_data = result.data[0]
    # {
    #   'current_streak': 8,
    #   'longest_streak': 14,
    #   'streak_continued': True,
    #   'streak_frozen': False,
    #   'new_personal_best': False
    # }
except Exception:
    logger.warning("Streak update failed, but transaction succeeded")

# Get streak for display
result = supabase.rpc('get_user_streak', {
    'p_user_id': user_uuid
}).execute()
streak_status = result.data[0]
# {
#   'current_streak': 7,
#   'longest_streak': 14,
#   'last_activity_date': '2025-12-01',
#   'streak_freeze_available': True,
#   'streak_at_risk': False,
#   'days_until_streak_break': 2
# }
```

**Streak Mechanics:**
- **First activity** → streak = 1
- **Logged today** → no change
- **Logged yesterday** → streak++
- **Missed 1 day + freeze available** → use freeze, streak++
- **Missed 1+ days + no freeze** → reset to 1

**Key Details:**
- `update_user_streak` called automatically after transactions/invoices
- Non-blocking: transaction succeeds even if streak update fails
- `reset_weekly_streak_freezes` called by pg_cron every Monday
- All 5 profile streak fields updated atomically

📖 **Full details:** [docs/rpc/engagement.md](./docs/rpc/engagement.md)

---

## Related Documentation

- [`API-endpoints.md`](API-endpoints.md) — HTTP endpoints that call these RPCs
- [`DB-documentation.md`](DB-documentation.md) — Database schema and RLS policies
- [`docs/api/`](docs/api/) — Detailed API endpoint documentation
- [`docs/db/`](docs/db/) — Detailed database documentation
- [`docs/rpc/`](docs/rpc/) — Detailed RPC function documentation
- [`DB-DDL.txt`](DB-DDL.txt) — Complete RPC function source code

---

**Maintainer:** Backend Team  
**Last Updated:** December 1, 2025  
**Pattern:** Progressive Disclosure (Anthropic pattern)
