# RPC Usage Guidelines

## General Principles

### 1. Always Pass `user_id`
- All RPCs validate ownership via `user_id` parameter
- Extract `user_id` from Supabase Auth token (`auth.uid()`)
- Never allow client to set `user_id` arbitrarily

### 2. Use SECURITY DEFINER Carefully
- All RPCs run with creator privileges (`SECURITY DEFINER`)
- They bypass RLS internally but validate `user_id` explicitly
- Never expose raw table access to users

### 3. Atomicity
- All RPCs wrap operations in single DB transaction
- Either all changes succeed or all fail (rollback)
- No partial state possible

### 4. Error Handling
- RPCs raise `EXCEPTION` on validation failure
- Backend should catch and convert to HTTP 400/403/404
- Log errors but don't expose internal details to client

---

## Soft-Delete vs Hard-Delete

### Soft-Delete (Current Strategy)
- **Used for:** accounts, transactions, invoices, budgets, recurring templates
- **Mechanism:** Set `deleted_at = now()`
- **Visibility:** RLS filters `WHERE deleted_at IS NULL`
- **Recovery:** Set `deleted_at = NULL` to restore
- **Audit:** All historical data preserved

### Hard-Delete
- **Used for:** categories (user categories only), wishlists, wishlist items
- **Mechanism:** Physical `DELETE FROM ...`
- **Rationale:** Simpler data with no audit requirements
- **No recovery possible**

---

## Cache Management

### Current Cached Fields
| Field | Table | Purpose |
|-------|-------|---------|
| `cached_balance` | account | Sum of all transactions |
| `cached_consumption` | budget | Sum of category transactions in period |

### When to Recompute
- After bulk reassignment operations
- After soft-deleting transactions
- After restoring soft-deleted data
- Periodic verification (recommended: daily)

### Future Considerations
- **Option 1:** DB triggers on transaction INSERT/UPDATE/DELETE
- **Option 2:** Explicit RPC calls after operations
- **Current:** Manual explicit calls (Option 2)

---

## Testing RPCs

### Required Test Coverage
- **Happy path:** Valid inputs, successful operation
- **Ownership validation:** Reject wrong `user_id`
- **Edge cases:** Empty results, zero amounts, null fields
- **Atomic rollback:** Verify transaction consistency
- **RLS enforcement:** Verify soft-deleted rows invisible

### Example Test Pattern
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

## Security Best Practices

### Search Path Security
All RPCs use:
```sql
SET search_path = ''
```
And reference tables with fully qualified names:
```sql
public.transaction
public.account
public.category
```

This prevents search_path injection attacks.

### Input Validation
- All UUIDs validated as belonging to `p_user_id`
- Foreign key references validated before modification
- Amount fields checked for valid ranges
- Date ranges validated (`start <= end`)

---

## Summary Statistics

| Domain | RPC Count |
|--------|-----------|
| Account management | 3 |
| Transaction management | 1 |
| Category management | 1 |
| Transfer management | 3 |
| Recurring transactions | 4 |
| Wishlist | 1 |
| Invoice | 1 |
| Budget | 2 |
| Currency validation | 3 |
| Favorite account | 3 |
| **Total** | **22** |
