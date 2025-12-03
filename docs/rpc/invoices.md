# Invoice RPCs

## Overview

Invoice RPCs handle soft-deletion of invoices.

---

## `delete_invoice`

**Purpose:** Soft-delete an invoice (set `deleted_at` timestamp).

**Signature:**
```sql
CREATE OR REPLACE FUNCTION delete_invoice(
  p_invoice_id uuid,
  p_user_id uuid
)
RETURNS TABLE(
  invoice_soft_deleted BOOLEAN,
  deleted_at TIMESTAMPTZ
)
```

**Security:** `SECURITY DEFINER` (validates ownership via `user_id`)

**Behavior:**
1. Validates `p_invoice_id` belongs to `p_user_id`
2. Sets `deleted_at = now()` on the invoice
3. Returns soft-delete status and timestamp

**Usage:**
```python
result = supabase_client.rpc(
    'delete_invoice',
    {
        'p_invoice_id': invoice_uuid,
        'p_user_id': user_uuid
    }
).execute()

row = result.data[0]
# row['invoice_soft_deleted'] - should be True on success
# row['deleted_at'] - timestamp of soft-delete
```

**Notes:**
- Invoice becomes invisible to user queries (RLS filters `deleted_at IS NULL`)
- Storage cleanup (invoice image/PDF) should be handled by backend service layer after successful soft-delete
- Related transactions remain intact (invoice_id FK is SET NULL on soft-delete)
