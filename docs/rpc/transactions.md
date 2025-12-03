# Transaction Management RPCs

## Overview

Transaction RPCs handle soft-deletion of individual transactions.

---

## `delete_transaction`

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

**Related:**
- For transfers, use `delete_transfer` to delete both paired transactions
- For recurring transactions, use `delete_recurring_transaction`
