# Soft-Delete Strategy

> Most user-initiated deletions are soft-deletes, not physical deletions.

---

## Why Soft-Delete?

1. **Recoverability** — Users can restore accidentally deleted data
2. **Audit Trail** — Support teams can debug issues with historical data
3. **Referential Safety** — Avoid cascade deletion of related objects (invoices, paired transactions, etc.)
4. **Better UX** — Enables undo functionality

---

## Implementation

### Soft-Delete Column

All soft-deletable tables include:

```sql
deleted_at TIMESTAMPTZ NULL
```

- `NULL` = active record
- Timestamp = when the record was soft-deleted

### Tables Using Soft-Delete

| Table | Has `deleted_at` |
|:------|:-----------------|
| `account` | ✅ |
| `transaction` | ✅ |
| `invoice` | ✅ |
| `budget` | ✅ |
| `recurring_transaction` | ✅ |
| `profile` | ❌ (uses anonymization instead) |
| `category` | ❌ (reassign to general, then hard delete) |
| `wishlist` | ❌ (hard delete with cascade) |
| `wishlist_item` | ❌ (cascade from wishlist) |
| `budget_category` | ❌ (junction table, cascade) |

---

## RLS Enforcement

User queries automatically filter soft-deleted records:

```sql
-- RLS policy includes:
user_id = auth.uid() AND deleted_at IS NULL
```

Backend services can query soft-deleted rows when needed for:
- Recovery operations
- Audit/debugging
- GDPR compliance workflows

---

## Service Layer Behavior

1. **DELETE endpoints** call soft-delete RPCs instead of physical deletes
2. **RPCs return summary** of what was soft-deleted
3. **Cached balances** are adjusted atomically during soft-delete
4. **Related records** may be updated (e.g., clear `paired_transaction_id`)

---

## Delete Behavior by Table

### account

1. Set `deleted_at` timestamp
2. User chooses: reassign transactions OR delete transactions
3. If transactions deleted, update `cached_balance` on remaining accounts
4. Recurring templates for this account are also soft-deleted

### transaction

1. Set `deleted_at` timestamp
2. Decrement `account.cached_balance` atomically
3. If part of budget period, decrement `budget.cached_consumption`
4. If part of transfer pair, soft-delete both sides together

### invoice

1. Set `deleted_at` timestamp
2. Archive storage file (move to archive path)
3. Schedule background purge based on retention policy
4. Linked transactions keep `invoice_id` but see NULL via RLS

### budget

1. Set `deleted_at` timestamp
2. `budget_category` rows are deleted (CASCADE)
3. Historical data retained for reports

### recurring_transaction

1. Set `deleted_at` timestamp
2. Stop future materialization (backend checks `deleted_at`)
3. Already-created transactions are NOT affected
4. If transfer pair, soft-delete both templates together

### profile

**Special case: Anonymization instead of soft-delete**

1. Set `first_name` to `"Deleted User"`
2. Set `last_name` to `NULL`
3. Set `avatar_url` to `NULL`
4. Keep `country` and `currency_preference` for system consistency

---

## Hard-Delete Path (GDPR Compliance)

For GDPR "right to be forgotten" requests:

1. **Use dedicated GDPR compliance RPCs** (not exposed to regular API)
2. **Requires approval and logging**
3. **Wait for retention window** to expire (e.g., 90 days after soft-delete)
4. **Permanently remove rows** and anonymize related data
5. **Archive invoice storage files** before deletion

### Hard-Delete Process

```
User requests deletion
        ↓
Soft-delete all user data
        ↓
Wait 90 days (retention period)
        ↓
Admin triggers GDPR hard-delete RPC
        ↓
Physically remove data
        ↓
Archive/delete storage files
        ↓
Log completion for compliance
```

---

## Recovery Operations

To restore a soft-deleted record:

1. Query with explicit `deleted_at IS NOT NULL` filter
2. Set `deleted_at = NULL`
3. Recalculate any cached values affected
4. Update related records if needed

**Note:** Recovery should be time-limited (e.g., within 30 days of deletion).
