# Transfer RPCs

## Overview

Transfer RPCs handle creation and deletion of transfers, which are paired transactions (one outcome from source account, one income to destination account).

---

## `create_transfer`

**Purpose:** Atomically create a transfer (two paired transactions).

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

row = result.data[0]
# row['from_transaction_id'] - UUID of outcome transaction
# row['to_transaction_id'] - UUID of income transaction
```

**Notes:**
- Both transactions created atomically (single DB transaction)
- Paired transactions linked via `paired_transaction_id`
- Always uses system "transfer" category

---

## `delete_transfer`

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

## `update_transfer`

**Purpose:** Update a transfer's amount, description, or date. Updates both paired transactions atomically.

**Signature:**
```sql
CREATE OR REPLACE FUNCTION update_transfer(
  p_transaction_id uuid,
  p_user_id uuid,
  p_amount numeric(12,2),
  p_description text,
  p_date timestamptz
)
RETURNS TABLE(
  from_transaction_id uuid,
  to_transaction_id uuid,
  updated_count INT
)
```

**Security:** `SECURITY DEFINER` (validates ownership)

**Behavior:**
1. Validates `p_transaction_id` belongs to `p_user_id`
2. Finds the paired transaction via `paired_transaction_id`
3. Updates both transactions with new values
4. Returns both UUIDs and update count

**Usage:**
```python
result = supabase_client.rpc(
    'update_transfer',
    {
        'p_transaction_id': either_transaction_uuid,
        'p_user_id': user_uuid,
        'p_amount': 200.00,
        'p_description': 'Updated transfer description',
        'p_date': '2025-11-20T10:00:00Z'
    }
).execute()
```

**Notes:**
- Both transactions updated atomically
- Amount is absolute value (stored as-is on both transactions)
