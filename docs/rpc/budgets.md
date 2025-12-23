# Budget RPCs

## Overview

Budget RPCs handle soft-deletion and cache recomputation for budgets.

---

## `delete_budget`

**Purpose:** Soft-delete a budget (set `deleted_at` timestamp).

**Signature:**
```sql
CREATE OR REPLACE FUNCTION delete_budget(
  p_budget_id uuid,
  p_user_id uuid
)
RETURNS TABLE(
  budget_soft_deleted BOOLEAN,
  deleted_at TIMESTAMPTZ
)
```

**Security:** `SECURITY DEFINER` (validates ownership via `user_id`)

**Behavior:**
1. Validates `p_budget_id` belongs to `p_user_id`
2. Sets `deleted_at = now()` on the budget
3. Returns soft-delete status and timestamp

**Usage:**
```python
result = supabase_client.rpc(
    'delete_budget',
    {
        'p_budget_id': budget_uuid,
        'p_user_id': user_uuid
    }
).execute()

row = result.data[0]
# row['budget_soft_deleted'] - should be True on success
# row['deleted_at'] - timestamp of soft-delete
```

**Notes:**
- Budget becomes invisible to user queries (RLS filters `deleted_at IS NULL`)
- `budget_category` junction rows remain for historical analysis
- Transactions remain unaffected (budget deletion doesn't affect historical spending data)

---

## `recompute_budget_consumption`

**Purpose:** Recalculate `budget.cached_consumption` for a given budget period.

**Signature:**
```sql
CREATE OR REPLACE FUNCTION recompute_budget_consumption(
  p_budget_id uuid,
  p_user_id uuid,
  p_period_start date,
  p_period_end date
)
RETURNS numeric(12,2)
```

**Security:** `SECURITY DEFINER` (validates ownership via `user_id`)

**Behavior:**
1. Validates `p_budget_id` belongs to `p_user_id`
2. Validates date range (`p_period_start` <= `p_period_end`)
3. Fetches all categories linked to budget via `budget_category` junction
4. Sums all non-deleted **OUTCOME** transactions in those categories within date range
5. Updates `budget.cached_consumption` with the computed sum
6. Returns the new consumption amount

**Usage:**
```python
result = supabase_client.rpc(
    'recompute_budget_consumption',
    {
        'p_budget_id': budget_uuid,
        'p_user_id': user_uuid,
        'p_period_start': '2025-11-01',
        'p_period_end': '2025-11-30'
    }
).execute()

new_consumption = result.data  # Returns numeric value
```

**When to Call:**
- After soft-deleting transactions that affect budget categories
- When budget period rolls over (start of new month/week/year)
- After changing budget category associations via `budget_category` updates
- Periodic cache verification (recommended: daily background job)

**Notes:**
- Only counts transactions where `flow_type = 'outcome'` (expenses only)
- Only counts transactions where `deleted_at IS NULL`
- Date range is inclusive: `[p_period_start, p_period_end]`
- Updates `budget.updated_at` timestamp
- Atomic operation (transaction-safe)
