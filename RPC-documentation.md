# RPC Documentation

**Date:** November 15, 2025  
**Purpose:** Comprehensive reference for all PostgreSQL RPC functions in the Kashi Finances backend

---

## Table of Contents

1. [Account Management RPCs](#account-management-rpcs)
2. [Transaction Management RPCs](#transaction-management-rpcs)
3. [Category Management RPCs](#category-management-rpcs)
4. [Transfer RPCs](#transfer-rpcs)
5. [Recurring Transaction RPCs](#recurring-transaction-rpcs)
6. [Wishlist RPCs](#wishlist-rpcs)
7. [Soft-Delete RPCs](#soft-delete-rpcs)
8. [Cache Recomputation RPCs](#cache-recomputation-rpcs)
9. [RPC Usage Guidelines](#rpc-usage-guidelines)

---

## Account Management RPCs

### `delete_account_reassign`

**Purpose:** Soft-delete an account after reassigning all transactions and recurring templates to a target account.

**Signature:**
```sql
CREATE OR REPLACE FUNCTION delete_account_reassign(
  p_account_id uuid,
  p_user_id uuid,
  p_target_account_id uuid
)
RETURNS TABLE(
  recurring_templates_reassigned INT,
  transactions_reassigned INT,
  account_soft_deleted BOOLEAN,
  deleted_at TIMESTAMPTZ
)
```

**Security:** `SECURITY DEFINER` (runs with creator privileges, validates `user_id`)

**Behavior:**
1. Validates both `p_account_id` and `p_target_account_id` belong to `p_user_id`
2. Reassigns all `recurring_transaction` rows to target account
3. Reassigns all `transaction` rows to target account
4. Soft-deletes source account (sets `deleted_at`)
5. Returns counts and soft-delete status

**Usage:**
```python
# Python (via Supabase client)
result = supabase_client.rpc(
    'delete_account_reassign',
    {
        'p_account_id': source_account_uuid,
        'p_user_id': user_uuid,
        'p_target_account_id': target_account_uuid
    }
).execute()
```

**Notes:**
- All operations are atomic (single transaction)
- Source account becomes invisible to user queries (RLS filters `deleted_at IS NULL`)
- Transactions remain queryable and linked to target account

---

### `delete_account_cascade`

**Purpose:** Soft-delete an account along with all its transactions and recurring templates.

**Signature:**
```sql
CREATE OR REPLACE FUNCTION delete_account_cascade(
  p_account_id uuid,
  p_user_id uuid
)
RETURNS TABLE(
  recurring_templates_soft_deleted INT,
  transactions_soft_deleted INT,
  account_soft_deleted BOOLEAN,
  deleted_at TIMESTAMPTZ
)
```

**Security:** `SECURITY DEFINER` (runs with creator privileges, validates `user_id`)

**Behavior:**
1. Validates `p_account_id` belongs to `p_user_id`
2. Soft-deletes all `recurring_transaction` rows for this account
3. Soft-deletes all `transaction` rows for this account
4. Clears `paired_transaction_id` on any paired transfers (orphan handling)
5. Soft-deletes the account
6. Returns counts and soft-delete status

**Usage:**
```python
# Python (via Supabase client)
result = supabase_client.rpc(
    'delete_account_cascade',
    {
        'p_account_id': account_uuid,
        'p_user_id': user_uuid
    }
).execute()
```

**Notes:**
- All soft-deleted records invisible to user queries (RLS enforcement)
- Paired transaction references cleared to prevent orphan FK issues
- Data remains in database for audit/recovery

---

## Transaction Management RPCs

### `delete_transaction`

**Purpose:** Soft-delete a single transaction (set `deleted_at`).

**Signature:**
```sql
CREATE OR REPLACE FUNCTION delete_transaction(
  p_transaction_id uuid,
  p_user_id uuid
)
RETURNS TABLE(
  transaction_soft_deleted BOOLEAN,
  deleted_at TIMESTAMPTZ
)
```

**Security:** `SECURITY DEFINER` (validates ownership via `user_id`)

**Behavior:**
1. Validates `p_transaction_id` belongs to `p_user_id`
2. Sets `deleted_at = now()` on the transaction
3. Returns soft-delete status and timestamp

**Usage:**
```python
# Python (via Supabase client)
result = supabase_client.rpc(
    'delete_transaction',
    {
        'p_transaction_id': transaction_uuid,
        'p_user_id': user_uuid
    }
).execute()
```

**Notes:**
- Transaction becomes invisible to user queries (RLS filters `deleted_at IS NULL`)
- Account balance caches may need recomputation after this operation
- Does NOT clear `paired_transaction_id` (use `delete_transfer` for transfers)

---

## Category Management RPCs

### `delete_category_reassign`

**Purpose:** Delete a user category after reassigning all transactions to a fallback category.

**Signature:**
```sql
CREATE OR REPLACE FUNCTION delete_category_reassign(
  p_category_id uuid,
  p_user_id uuid,
  p_fallback_category_id uuid
)
RETURNS TABLE(
  transactions_reassigned INT,
  category_deleted BOOLEAN
)
```

**Security:** `SECURITY DEFINER` (validates ownership)

**Behavior:**
1. Validates `p_category_id` is a user category (not system category)
2. Validates `p_category_id` belongs to `p_user_id`
3. Reassigns all transactions from `p_category_id` to `p_fallback_category_id`
4. Physically deletes the category (hard-delete, no soft-delete for categories)
5. Returns count and delete status

**Usage:**
```python
# Python (via Supabase client)
result = supabase_client.rpc(
    'delete_category_reassign',
    {
        'p_category_id': category_uuid,
        'p_user_id': user_uuid,
        'p_fallback_category_id': fallback_uuid  # Usually "general" category
    }
).execute()
```

**Notes:**
- Categories use **hard-delete** (not soft-delete) for simplicity
- System categories (with `key` field) cannot be deleted
- Typically reassign to flow-specific "general" category

---

## Transfer RPCs

### `create_transfer`

**Purpose:** Atomically create a transfer (two paired transactions: one outcome, one income).

**Signature:**
```sql
CREATE OR REPLACE FUNCTION create_transfer(
  p_user_id uuid,
  p_from_account_id uuid,
  p_to_account_id uuid,
  p_amount numeric(12,2),
  p_description text,
  p_date timestamptz
)
RETURNS TABLE(
  from_transaction_id uuid,
  to_transaction_id uuid
)
```

**Security:** `SECURITY DEFINER` (validates accounts belong to `user_id`)

**Behavior:**
1. Validates both accounts belong to `p_user_id`
2. Inserts "outcome" transaction in `p_from_account_id` with `flow_type='outcome'`
3. Inserts "income" transaction in `p_to_account_id` with `flow_type='income'`
4. Sets `paired_transaction_id` on both transactions to link them
5. Uses "transfer" system category (looked up by `key='transfer'`)
6. Returns both transaction UUIDs

**Usage:**
```python
# Python (via Supabase client)
result = supabase_client.rpc(
    'create_transfer',
    {
        'p_user_id': user_uuid,
        'p_from_account_id': source_account_uuid,
        'p_to_account_id': dest_account_uuid,
        'p_amount': 150.00,
        'p_description': 'Transfer to savings',
        'p_date': '2025-11-15T14:30:00Z'
    }
).execute()
```

**Notes:**
- Both transactions created atomically (single DB transaction)
- Paired transactions linked via `paired_transaction_id`
- Always uses system "transfer" category

---

### `delete_transfer`

**Purpose:** Delete a transfer by soft-deleting both paired transactions.

**Signature:**
```sql
CREATE OR REPLACE FUNCTION delete_transfer(
  p_transaction_id uuid,
  p_user_id uuid
)
RETURNS TABLE(
  transactions_soft_deleted INT
)
```

**Security:** `SECURITY DEFINER` (validates ownership)

**Behavior:**
1. Validates `p_transaction_id` belongs to `p_user_id`
2. Finds the paired transaction via `paired_transaction_id`
3. Soft-deletes both transactions (sets `deleted_at`)
4. Returns count (should be 2 for valid transfer)

**Usage:**
```python
# Python (via Supabase client)
result = supabase_client.rpc(
    'delete_transfer',
    {
        'p_transaction_id': either_transaction_uuid,  # Can be from or to transaction
        'p_user_id': user_uuid
    }
).execute()
```

**Notes:**
- Can pass either transaction UUID (finds paired automatically)
- Both transactions soft-deleted atomically
- Account balances may need recomputation after this

---

## Recurring Transaction RPCs

### `sync_recurring_transactions`

**Purpose:** Generate all pending transactions from recurring transaction templates up to a given date.

**Signature:**
```sql
CREATE OR REPLACE FUNCTION sync_recurring_transactions(
  p_user_id uuid,
  p_today date
)
RETURNS TABLE(
  transactions_generated INT,
  rules_processed INT
)
```

**Security:** `SECURITY DEFINER` (runs with creator privileges)

**Behavior:**
1. Fetches all active recurring rules for `p_user_id` where `next_run_date <= p_today`
2. For each rule, generates transactions for all pending occurrences
3. Inserts transactions with:
   - `recurring_transaction_id` set to template UUID
   - `system_generated_key = 'recurring_sync'`
   - `date` set to scheduled occurrence date
4. Updates `next_run_date` on each template to next future occurrence
5. Respects `end_date` constraint (stops generating when reached)
6. Returns count of transactions generated and rules processed

**Usage:**
```python
# Python (via Supabase client)
result = supabase_client.rpc(
    'sync_recurring_transactions',
    {
        'p_user_id': user_uuid,
        'p_today': '2025-11-15'  # ISO date string
    }
).execute()
```

**Notes:**
- Should be called daily by backend scheduler
- Idempotent: safe to call multiple times for same date
- Handles daily, weekly, monthly, yearly frequencies
- Generated transactions marked with `system_generated_key = 'recurring_sync'`

---

### `create_recurring_transfer`

**Purpose:** Create a recurring transfer template (two paired recurring transaction templates).

**Signature:**
```sql
CREATE OR REPLACE FUNCTION create_recurring_transfer(
  p_user_id uuid,
  p_from_account_id uuid,
  p_to_account_id uuid,
  p_amount numeric(12,2),
  p_description text,
  p_frequency recurring_frequency_enum,
  p_interval integer,
  p_start_date date,
  p_end_date date
)
RETURNS TABLE(
  from_recurring_id uuid,
  to_recurring_id uuid
)
```

**Security:** `SECURITY DEFINER` (validates accounts belong to `user_id`)

**Behavior:**
1. Validates both accounts belong to `p_user_id`
2. Creates "outcome" recurring template for `p_from_account_id`
3. Creates "income" recurring template for `p_to_account_id`
4. Links templates via `paired_recurring_transaction_id`
5. Sets `next_run_date = p_start_date` for both
6. Returns both recurring template UUIDs

**Usage:**
```python
# Python (via Supabase client)
result = supabase_client.rpc(
    'create_recurring_transfer',
    {
        'p_user_id': user_uuid,
        'p_from_account_id': checking_uuid,
        'p_to_account_id': savings_uuid,
        'p_amount': 500.00,
        'p_description': 'Monthly savings transfer',
        'p_frequency': 'monthly',
        'p_interval': 1,
        'p_start_date': '2025-12-01',
        'p_end_date': None  # Optional
    }
).execute()
```

**Notes:**
- Creates paired templates for recurring transfers
- `sync_recurring_transactions` will generate paired transactions automatically
- Both templates marked as `is_active = true` by default

---

### `delete_recurring_transaction`

**Purpose:** Soft-delete a recurring transaction template (stops future generation).

**Signature:**
```sql
CREATE OR REPLACE FUNCTION delete_recurring_transaction(
  p_recurring_id uuid,
  p_user_id uuid
)
RETURNS TABLE(
  recurring_soft_deleted BOOLEAN,
  deleted_at TIMESTAMPTZ
)
```

**Security:** `SECURITY DEFINER` (validates ownership)

**Behavior:**
1. Validates `p_recurring_id` belongs to `p_user_id`
2. Sets `deleted_at = now()` on the recurring template
3. Returns soft-delete status and timestamp

**Usage:**
```python
# Python (via Supabase client)
result = supabase_client.rpc(
    'delete_recurring_transaction',
    {
        'p_recurring_id': recurring_uuid,
        'p_user_id': user_uuid
    }
).execute()
```

**Notes:**
- Template becomes inactive (no future transactions generated)
- Already-generated transactions remain untouched
- Does NOT soft-delete paired template (use `delete_recurring_and_pair` for transfers)

---

### `delete_recurring_and_pair`

**Purpose:** Soft-delete a recurring template AND its paired template (for recurring transfers).

**Signature:**
```sql
CREATE OR REPLACE FUNCTION delete_recurring_and_pair(
  p_recurring_id uuid,
  p_user_id uuid
)
RETURNS TABLE(
  recurring_templates_soft_deleted INT
)
```

**Security:** `SECURITY DEFINER` (validates ownership)

**Behavior:**
1. Validates `p_recurring_id` belongs to `p_user_id`
2. Finds paired template via `paired_recurring_transaction_id`
3. Soft-deletes both templates (sets `deleted_at`)
4. Returns count (should be 2 for valid paired templates)

**Usage:**
```python
# Python (via Supabase client)
result = supabase_client.rpc(
    'delete_recurring_and_pair',
    {
        'p_recurring_id': either_recurring_uuid,  # Can be from or to template
        'p_user_id': user_uuid
    }
).execute()
```

**Notes:**
- Can pass either template UUID (finds paired automatically)
- Both templates soft-deleted atomically
- Already-generated transactions remain

---

## Wishlist RPCs

### `create_wishlist_with_items`

**Purpose:** Atomically create a wishlist and add initial items.

**Signature:**
```sql
CREATE OR REPLACE FUNCTION create_wishlist_with_items(
  p_user_id uuid,
  p_name text,
  p_items jsonb
)
RETURNS TABLE(
  wishlist_id uuid,
  items_created INT
)
```

**Security:** `SECURITY DEFINER` (validates ownership)

**Behavior:**
1. Inserts wishlist row for `p_user_id` with `p_name`
2. Parses `p_items` JSONB array and inserts each item
3. Returns wishlist UUID and count of items created

**Input Format (p_items):**
```json
[
  {
    "description": "Gaming laptop",
    "estimated_price": 1200.00,
    "priority": "high",
    "url": "https://example.com/laptop"
  },
  {
    "description": "Wireless headphones",
    "estimated_price": 150.00,
    "priority": "medium"
  }
]
```

**Usage:**
```python
# Python (via Supabase client)
result = supabase_client.rpc(
    'create_wishlist_with_items',
    {
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
    }
).execute()
```

**Notes:**
- All items inserted atomically with wishlist creation
- `wishlist_item` has FK cascade on wishlist deletion

---

## Soft-Delete RPCs

### `delete_account_soft_delete` (DEPRECATED)

**Status:** DEPRECATED as of Nov 15, 2025

**Purpose:** Standalone soft-delete function (superseded by `delete_account_reassign` and `delete_account_cascade`).

**Migration Note:**
This RPC is deprecated. Use:
- `delete_account_reassign` for reassignment strategy
- `delete_account_cascade` for cascade strategy

Both new RPCs perform soft-delete (set `deleted_at`) instead of physical deletion.

---

## Cache Recomputation RPCs

### `recompute_account_balance` (TODO)

**Purpose:** Recalculate `account.cached_balance` from transaction history.

**Planned Signature:**
```sql
CREATE OR REPLACE FUNCTION recompute_account_balance(
  p_account_id uuid
)
RETURNS numeric(12,2)
```

**Planned Behavior:**
1. Sum all non-deleted transactions for `p_account_id`
   - `income` transactions: positive contribution
   - `outcome` transactions: negative contribution
2. Update `account.cached_balance` with result
3. Return new balance

**Status:** Not yet implemented

**Use Cases:**
- After bulk transaction reassignment
- After soft-deleting transactions
- After restoring soft-deleted transactions
- Periodic cache verification

---

### `recompute_budget_consumption` (TODO)

**Purpose:** Recalculate `budget.cached_consumption` for a given budget period.

**Planned Signature:**
```sql
CREATE OR REPLACE FUNCTION recompute_budget_consumption(
  p_budget_id uuid,
  p_period_start date,
  p_period_end date
)
RETURNS numeric(12,2)
```

**Planned Behavior:**
1. Fetch budget and linked categories via `budget_category` junction
2. Sum all non-deleted `outcome` transactions in linked categories
   - Filter by date range: `[p_period_start, p_period_end]`
3. Update `budget.cached_consumption` with result
4. Return new consumption amount

**Status:** Not yet implemented

**Use Cases:**
- After soft-deleting transactions affecting budget categories
- When budget period rolls over
- Periodic cache verification

---

## RPC Usage Guidelines

### General Principles

1. **Always pass `user_id`**
   - All RPCs validate ownership via `user_id` parameter
   - Extract `user_id` from Supabase Auth token (`auth.uid()`)
   - Never allow client to set `user_id` arbitrarily

2. **Use SECURITY DEFINER carefully**
   - All RPCs run with creator privileges (`SECURITY DEFINER`)
   - They bypass RLS internally but validate `user_id` explicitly
   - Never expose raw table access to users

3. **Atomicity**
   - All RPCs wrap operations in single DB transaction
   - Either all changes succeed or all fail (rollback)
   - No partial state possible

4. **Error Handling**
   - RPCs raise `EXCEPTION` on validation failure
   - Backend should catch and convert to HTTP 400/403/404
   - Log errors but don't expose internal details to client

### Soft-Delete vs Hard-Delete

**Soft-Delete (Current Strategy):**
- Used for: accounts, transactions, invoices, budgets, recurring templates
- Mechanism: Set `deleted_at = now()`
- Visibility: RLS filters `WHERE deleted_at IS NULL`
- Recovery: Set `deleted_at = NULL` to restore
- Audit: All historical data preserved

**Hard-Delete:**
- Used for: categories (user categories only), wishlists, wishlist items
- Mechanism: Physical `DELETE FROM ...`
- Rationale: Simpler data with no audit requirements
- No recovery possible

### Cache Management

**Current Cached Fields:**
- `account.cached_balance` - Sum of all transactions
- `budget.cached_consumption` - Sum of category transactions in period

**When to Recompute:**
- After bulk reassignment operations
- After soft-deleting transactions
- After restoring soft-deleted data
- Periodic verification (recommended: daily)

**Future: Triggers vs Explicit Calls**
- Option 1: DB triggers on transaction INSERT/UPDATE/DELETE
- Option 2: Explicit RPC calls after operations
- Current: Manual explicit calls (Option 2)
- Consider triggers for automatic cache updates

### Testing RPCs

**Test Coverage Required:**
- Happy path: valid inputs, successful operation
- Ownership validation: reject wrong `user_id`
- Edge cases: empty results, zero amounts, null fields
- Atomic rollback: verify transaction consistency
- RLS enforcement: verify soft-deleted rows invisible

**Example Test Pattern:**
```python
import pytest
from unittest.mock import MagicMock

def test_delete_account_reassign_success():
    mock_client = MagicMock()
    mock_client.rpc.return_value.execute.return_value = MockResponse(
        data=[{
            'recurring_templates_reassigned': 3,
            'transactions_reassigned': 15,
            'account_soft_deleted': True,
            'deleted_at': '2025-11-15T10:30:00Z'
        }]
    )
    
    result = call_rpc(mock_client, 'delete_account_reassign', {...})
    
    assert result['transactions_reassigned'] == 15
    assert result['account_soft_deleted'] is True
```

---

## Migration File Reference

All RPCs are defined in versioned SQL migration files under `supabase/migrations/`:

| RPC Function | Migration File | Date Created |
|:-------------|:---------------|:-------------|
| `delete_account_reassign` | `20251115000001_delete_account_reassign.sql` | Nov 15, 2025 |
| `delete_account_cascade` | `20251115000002_delete_account_cascade.sql` | Nov 15, 2025 |
| `delete_account_soft_delete` | `20251115000003_delete_account_soft_delete_rpc.sql` | Nov 15, 2025 (DEPRECATED) |
| `delete_transaction` | `20251115000004_delete_transaction_rpc.sql` | Nov 15, 2025 |
| `delete_recurring_transaction` | `20251115000005_delete_recurring_transaction_rpc.sql` | Nov 15, 2025 |
| `sync_recurring_transactions` | `20251106000001_sync_recurring_transactions_function.sql` | Nov 6, 2025 |
| `delete_category_reassign` | `20251107000010_delete_category_reassign_flow_aware.sql` | Nov 7, 2025 |
| `delete_recurring_and_pair` | `20251107000002_delete_recurring_transaction_and_pair.sql` | Nov 7, 2025 |
| `create_transfer` | `20251107000004_create_transfer_rpc.sql` | Nov 7, 2025 |
| `create_recurring_transfer` | `20251107000005_create_recurring_transfer_rpc.sql` | Nov 7, 2025 |
| `delete_transfer` | `20251107000008_delete_transfer_rpc.sql` | Nov 7, 2025 |
| `create_wishlist_with_items` | `20251107000009_create_wishlist_with_items_rpc.sql` | Nov 7, 2025 |

---

## Summary

**Total Active RPCs: 12**
- Account management: 2
- Transaction management: 1
- Category management: 1
- Transfer management: 2
- Recurring transactions: 4
- Wishlist: 1
- Soft-delete (standalone): 1 (DEPRECATED)

**Deprecated RPCs: 1**
- `soft_delete_account` (use `delete_account_reassign` or `delete_account_cascade` instead)

**Planned RPCs: 2**
- `recompute_account_balance` (cache management)
- `recompute_budget_consumption` (cache management)

---

**Last Updated:** November 15, 2025  
**Maintainer:** Backend Team  
**Related Docs:** 
- `DB-DDL.txt` (schema definitions)
- `API-endpoints.md` (HTTP API that calls these RPCs)