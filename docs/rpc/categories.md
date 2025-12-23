# Category Management RPCs

## Overview

Category RPCs handle deletion of user categories with flow-type-aware reassignment.

---

## `delete_category_reassign`

**Purpose:** Delete a user category after reassigning all transactions to a flow-type-matched fallback category.

**Signature:**
```sql
CREATE OR REPLACE FUNCTION delete_category_reassign(
  p_category_id uuid,
  p_user_id uuid,
  p_fallback_category_id uuid
)
RETURNS TABLE(
  transactions_reassigned INT,
  budget_links_removed INT,
  transactions_deleted INT,
  subcategories_orphaned INT,
  category_deleted BOOLEAN
)
```

**Security:** `SECURITY DEFINER` (validates ownership)

**Behavior:**
1. Validates `p_category_id` is a user category (not system category)
2. Validates `p_category_id` belongs to `p_user_id`
3. Reassigns all transactions from `p_category_id` to `p_fallback_category_id`
4. Removes all `budget_category` links
5. Handles subcategories:
   - Sets `parent_category_id = NULL` on subcategories (orphans them)
   - Returns count of orphaned subcategories
6. Physically deletes the category (hard-delete)
7. Returns counts and delete status

**Usage:**
```python
result = supabase_client.rpc(
    'delete_category_reassign',
    {
        'p_category_id': category_uuid,
        'p_user_id': user_uuid,
        'p_fallback_category_id': fallback_uuid  # Flow-type-matched "general" category
    }
).execute()

row = result.data[0]
# row['transactions_reassigned'] - count of transactions moved to fallback
# row['budget_links_removed'] - count of budget_category links removed
# row['subcategories_orphaned'] - count of subcategories now parentless
# row['category_deleted'] - should be True on success
```

**Flow-Type Awareness:**
- If deleted category is `flow_type='outcome'`, reassign to `general` outcome category
- If deleted category is `flow_type='income'`, reassign to `general` income category
- The API layer is responsible for fetching the correct flow-type-matched fallback

**Notes:**
- Categories use **hard-delete** (not soft-delete) for simplicity
- System categories (with `key` field) cannot be deleted
- Subcategories become top-level categories when parent is deleted

**Related:**
- See `docs/api/categories.md` for the DELETE endpoint that calls this RPC
