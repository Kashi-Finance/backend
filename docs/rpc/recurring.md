# Recurring Transaction RPCs

## Overview

Recurring transaction RPCs handle synchronization of recurring templates to generate actual transactions, and management of recurring transfer templates.

---

## `sync_recurring_transactions`

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
result = supabase_client.rpc(
    'sync_recurring_transactions',
    {
        'p_user_id': user_uuid,
        'p_today': '2025-11-15'  # ISO date string
    }
).execute()

row = result.data[0]
# row['transactions_generated'] - total transactions created
# row['rules_processed'] - number of templates checked
```

**Notes:**
- Should be called daily by backend scheduler
- Idempotent: safe to call multiple times for same date
- Handles daily, weekly, monthly, yearly frequencies
- Generated transactions marked with `system_generated_key = 'recurring_sync'`

---

## `create_recurring_transfer`

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

## `delete_recurring_transaction`

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

**Notes:**
- Template becomes inactive (no future transactions generated)
- Already-generated transactions remain untouched
- Does NOT soft-delete paired template (use `delete_recurring_and_pair` for transfers)

---

## `delete_recurring_and_pair`

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
