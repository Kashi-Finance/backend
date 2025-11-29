# Indexes and Performance

> Index strategy and performance optimization for Kashi Finances database.

---

## Index Strategy

1. **User-scoped queries** — Most queries filter by `user_id`, so indexes on `(user_id, ...)` are common
2. **Soft-delete filtering** — Partial indexes on `deleted_at WHERE deleted_at IS NOT NULL` optimize filtering
3. **Foreign key lookups** — Indexes on FK columns for joins and cascades
4. **Temporal queries** — Indexes on `(user_id, date DESC)` for transaction history
5. **Semantic search** — IVFFlat index on embedding vectors

---

## Index Reference

### account

| Index | Columns | Purpose |
|:------|:--------|:--------|
| `account_user_id_idx` | `(user_id)` | List user's accounts |
| `account_deleted_at_idx` | `(deleted_at) WHERE deleted_at IS NOT NULL` | Filter soft-deleted |

### transaction

| Index | Columns | Purpose |
|:------|:--------|:--------|
| `transaction_user_date_idx` | `(user_id, date DESC)` | User transaction history |
| `transaction_account_idx` | `(account_id, date DESC)` | Account transaction history |
| `transaction_category_idx` | `(category_id)` | Category-based queries |
| `transaction_recurring_idx` | `(recurring_transaction_id) WHERE NOT NULL` | Find transactions from template |
| `transaction_paired_idx` | `(paired_transaction_id) WHERE NOT NULL` | Transfer lookups |
| `transaction_invoice_idx` | `(invoice_id) WHERE NOT NULL` | Invoice-linked transactions |
| `transaction_deleted_at_idx` | `(deleted_at) WHERE deleted_at IS NOT NULL` | Filter soft-deleted |
| `transaction_embedding_idx` | `(embedding vector_cosine_ops)` IVFFlat | Semantic search |

### recurring_transaction

| Index | Columns | Purpose |
|:------|:--------|:--------|
| `recurring_tx_user_active_idx` | `(user_id, is_active, next_run_date)` | Find templates to materialize |
| `recurring_tx_paired_idx` | `(paired_recurring_transaction_id) WHERE NOT NULL` | Transfer template lookups |
| `recurring_tx_deleted_at_idx` | `(deleted_at) WHERE deleted_at IS NOT NULL` | Filter soft-deleted |

### budget

| Index | Columns | Purpose |
|:------|:--------|:--------|
| `budget_user_active_idx` | `(user_id, is_active)` | Find active budgets |
| `budget_deleted_at_idx` | `(deleted_at) WHERE deleted_at IS NOT NULL` | Filter soft-deleted |

### budget_category

| Index | Columns | Purpose |
|:------|:--------|:--------|
| `budget_category_user_idx` | `(user_id)` | User-scoped queries |
| `budget_category_category_idx` | `(category_id)` | Find budgets tracking a category |

### invoice

| Index | Columns | Purpose |
|:------|:--------|:--------|
| `invoice_user_id_idx` | `(user_id)` | List user's invoices |
| `invoice_deleted_at_idx` | `(deleted_at) WHERE deleted_at IS NOT NULL` | Filter soft-deleted |

### category

| Index | Columns | Purpose |
|:------|:--------|:--------|
| `category_user_id_idx` | `(user_id) WHERE user_id IS NOT NULL` | List user's categories |

### wishlist

| Index | Columns | Purpose |
|:------|:--------|:--------|
| `wishlist_user_id_idx` | `(user_id)` | List user's wishlists |
| `wishlist_user_status_idx` | `(user_id, status)` | Filter by status |
| `wishlist_created_at_idx` | `(created_at DESC)` | Sort by creation date |

### wishlist_item

| Index | Columns | Purpose |
|:------|:--------|:--------|
| `wishlist_item_wishlist_id_idx` | `(wishlist_id)` | List items in a wishlist |
| `wishlist_item_join_idx` | `(wishlist_id, created_at DESC)` | Sorted listing with join |

---

## Most Important Indexes

For query optimization, prioritize these indexes:

1. `transaction_user_date_idx` — User transaction history (most common query)
2. `transaction_account_idx` — Account transaction history
3. `transaction_embedding_idx` — Semantic search
4. `recurring_tx_user_active_idx` — Finding templates to materialize
5. `budget_user_active_idx` — Finding active budgets

---

## Performance Monitoring

1. **Monitor slow query logs** — Identify queries without index usage
2. **Use EXPLAIN ANALYZE** — Verify index usage in query plans
3. **Check index bloat** — Run REINDEX periodically if needed
4. **Consider partial indexes** — For frequently filtered columns

**Example:**

```sql
EXPLAIN ANALYZE
SELECT * FROM transaction
WHERE user_id = 'uuid' AND deleted_at IS NULL
ORDER BY date DESC
LIMIT 50;
```
