# Account Management RPCs

## Overview

Account RPCs handle soft-deletion of accounts with two strategies:
- **Reassign**: Move transactions to another account before deletion
- **Cascade**: Soft-delete all associated transactions

---

## `delete_account_reassign`

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

## `delete_account_cascade`

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

## `recompute_account_balance`

**Purpose:** Recalculate `account.cached_balance` from transaction history.

**Signature:**
```sql
CREATE OR REPLACE FUNCTION recompute_account_balance(
  p_account_id uuid,
  p_user_id uuid
)
RETURNS numeric(12,2)
```

**Security:** `SECURITY DEFINER` (validates ownership via `user_id`)

**Behavior:**
1. Validates `p_account_id` belongs to `p_user_id`
2. Sums all non-deleted transactions for the account:
   - `income` transactions: positive contribution (+amount)
   - `outcome` transactions: negative contribution (-amount)
3. Updates `account.cached_balance` with the computed sum
4. Returns the new balance

**When to Call:**
- After bulk transaction reassignment (`delete_account_reassign`)
- After soft-deleting transactions
- After restoring soft-deleted transactions
- Periodic cache verification (recommended: daily background job)

**Notes:**
- Only counts transactions where `deleted_at IS NULL`
- Updates `account.updated_at` timestamp
- Atomic operation (transaction-safe)
