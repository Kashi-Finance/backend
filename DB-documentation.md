# Kashi Finances — Database Documentation Index

> **Quick reference for database schema with pointers to detailed documentation.**
>
> This file follows Anthropic's progressive disclosure pattern: concise index here, full details in [docs/db/](./docs/db/).

**Last Updated:** November 30, 2025  
**Architecture:** Supabase (Auth + Postgres + Storage + RLS + pgvector) + Cloud Run (FastAPI + Python)

---

## Navigation

| Topic | Quick Ref | Full Docs |
|-------|-----------|-----------|
| Table Schemas | [Section 2](#2-tables-overview) | [docs/db/tables.md](./docs/db/tables.md) |
| Row-Level Security | [Section 3](#3-row-level-security) | [docs/db/rls.md](./docs/db/rls.md) |
| Enums | [Section 4](#4-enums) | [docs/db/enums.md](./docs/db/enums.md) |
| Indexes | [Section 5](#5-indexes) | [docs/db/indexes.md](./docs/db/indexes.md) |
| Soft-Delete | [Section 6](#6-soft-delete-strategy) | [docs/db/soft-delete.md](./docs/db/soft-delete.md) |
| Cached Values | [Section 7](#7-cached-values) | [docs/db/cached-values.md](./docs/db/cached-values.md) |
| Semantic Search | [Section 8](#8-semantic-search) | [docs/db/semantic-search.md](./docs/db/semantic-search.md) |
| System Data | [Section 9](#9-system-categories--keys) | [docs/db/system-data.md](./docs/db/system-data.md) |
| Currency Policy | [Section 10](#10-single-currency-per-user) | N/A |

---

## 1. Overview

**Key Design Principles:**

1. **Row-Level Security (RLS)** — Isolates user data automatically at the database level
2. **Soft-delete strategy** — Preserves audit trail and enables recovery
3. **Cached balances** — Performance optimization (recomputable from transactions)
4. **Semantic search** — pgvector embeddings on transactions
5. **Strong typing** — CHECK constraints and PostgreSQL enums
6. **Single-currency-per-user** — All financial data uses `profile.currency_preference`

📖 **Architecture details:** [docs/db/README.md](./docs/db/README.md)

---

## 2. Tables Overview

| Table | Purpose | Owner | Soft-Delete |
|-------|---------|-------|-------------|
| `auth.users` | Supabase Auth users | Supabase | N/A |
| `profile` | User preferences (1:1 with auth.users) | User | Anonymize |
| `account` | Financial accounts | User | ✅ |
| `category` | Transaction categories | System/User | Hard delete |
| `transaction` | Income/outcome records | User | ✅ |
| `invoice` | Receipts with OCR text | User | ✅ |
| `budget` | Spending limits | User | ✅ |
| `budget_category` | Budget ↔ Category links | User | Cascade |
| `recurring_transaction` | Recurring templates | User | ✅ |
| `wishlist` | Purchase goals | User | Hard delete |
| `wishlist_item` | Product recommendations | User | Cascade |

📖 **Full schemas:** [docs/db/tables.md](./docs/db/tables.md)

---

## 3. Row-Level Security

**All user-owned tables enforce RLS:**

```sql
-- Standard pattern for user-owned data
user_id = auth.uid() AND deleted_at IS NULL
```

**Special cases:**
- `category` — Users see own + system categories (`user_id IS NULL`)
- `wishlist_item` — Indirect ownership via `wishlist`

📖 **Full RLS policies:** [docs/db/rls.md](./docs/db/rls.md)

---

## 4. Enums

| Enum | Values | Used By |
|------|--------|---------|
| `account_type_enum` | cash, bank, credit_card, loan, remittance, crypto, investment | `account.type` |
| `flow_type_enum` | income, outcome | transactions, categories |
| `budget_frequency_enum` | once, daily, weekly, monthly, yearly | `budget.frequency` |
| `recurring_frequency_enum` | daily, weekly, monthly, yearly | `recurring_transaction.frequency` |
| `wishlist_status_enum` | active, purchased, abandoned | `wishlist.status` |

📖 **Full enum docs:** [docs/db/enums.md](./docs/db/enums.md)

---

## 5. Indexes

**Most important indexes:**

| Index | Purpose |
|-------|---------|
| `transaction_user_date_idx` | User transaction history |
| `transaction_account_idx` | Account transaction history |
| `transaction_embedding_idx` | Semantic search (IVFFlat) |
| `recurring_tx_user_active_idx` | Templates to materialize |
| `budget_user_active_idx` | Active budgets |

📖 **Full index list:** [docs/db/indexes.md](./docs/db/indexes.md)

---

## 6. Soft-Delete Strategy

**Tables using soft-delete:** `account`, `transaction`, `invoice`, `budget`, `recurring_transaction`

**Process:**
1. Set `deleted_at` timestamp (not physical delete)
2. RLS automatically filters `deleted_at IS NULL`
3. Cached balances updated atomically
4. Hard-delete only via GDPR compliance RPC (after 90 days)

📖 **Full soft-delete docs:** [docs/db/soft-delete.md](./docs/db/soft-delete.md)

---

## 7. Cached Values

| Field | Table | Computation |
|-------|-------|-------------|
| `cached_balance` | `account` | SUM(income) - SUM(outcome) |
| `cached_consumption` | `budget` | SUM(outcome in tracked categories) |

**Reconciliation RPCs:**
- `recompute_account_balance(account_id)`
- `recompute_budget_consumption(budget_id, period_start, period_end)`

📖 **Full caching docs:** [docs/db/cached-values.md](./docs/db/cached-values.md)

---

## 8. Semantic Search

**Implementation:**
- Model: `text-embedding-3-small` (1536 dimensions)
- Storage: `transaction.embedding` (VECTOR(1536))
- Index: IVFFlat with cosine similarity

**Query example:**
```sql
SELECT * FROM transaction
WHERE user_id = auth.uid() AND deleted_at IS NULL
ORDER BY embedding <=> $query_embedding
LIMIT 10;
```

📖 **Full semantic search docs:** [docs/db/semantic-search.md](./docs/db/semantic-search.md)

---

## 9. System Categories & Keys

### System Categories

| Key | Flow Types | Purpose |
|-----|------------|---------|
| `initial_balance` | income, outcome | Account opening balance |
| `balance_update` | income, outcome | Manual corrections |
| `transfer` | income, outcome | Internal transfers |
| `general` | income, outcome | Default uncategorized |

### System-Generated Keys

| Key | Description |
|-----|-------------|
| `recurring_sync` | From recurring template |
| `invoice_ocr` | From invoice OCR |
| `initial_balance` | Account creation |
| `bulk_import` | Bulk data import |

📖 **Full system data docs:** [docs/db/system-data.md](./docs/db/system-data.md)

---

## 10. Single-Currency-Per-User

**Policy (Nov 30, 2025):** Each user operates in a single currency.

### Source of Truth

`profile.currency_preference` is the authoritative currency for all user financial data.

### Currency Fields

| Table | Field | Enforcement |
|-------|-------|-------------|
| `profile` | `currency_preference` | Source of truth |
| `account` | `currency` | Must match profile (validated on create) |
| `wishlist` | `currency_code` | Must match profile (validated on create) |
| `budget` | `currency` | Auto-populated from profile |
| `transaction` | — | Inherits from account |
| `recurring_transaction` | — | Inherits from account |

### Validation RPCs

| RPC | Purpose |
|-----|---------|
| `validate_user_currency(user_id, currency)` | Raises exception if currency != profile |
| `get_user_currency(user_id)` | Returns user's currency_preference |
| `can_change_user_currency(user_id)` | Returns false if has accounts/wishlists/budgets |

### Changing Currency

Users can only change `currency_preference` if they have:
- **No accounts** (including soft-deleted)
- **No wishlists**
- **No budgets** (including soft-deleted)

📖 **Related migration:** `20251130000001_single_currency_per_user.sql`

---

## 11. Entity Relationships

```
auth.users (1) ──→ (1) profile
           (1) ──→ (N) account ──→ (N) transaction
           (1) ──→ (N) category ──→ (N) transaction
           (1) ──→ (N) invoice ──→ (N) transaction
           (1) ──→ (N) budget ──→ (N) budget_category ──→ category
           (1) ──→ (N) recurring_transaction
           (1) ──→ (N) wishlist ──→ (N) wishlist_item

transaction (1) ↔ (1) transaction (paired_transaction_id)
recurring_transaction (1) ↔ (1) recurring_transaction (paired)
```

---

## 12. Data Integrity

### CHECK Constraints

- `amount >= 0` — Amounts always positive; flow_type determines direction
- `limit_amount > 0` — Budgets must have positive limits
- `interval >= 1` — Frequency intervals must be at least 1

### Foreign Key Behaviors

| FK Pattern | Behavior |
|------------|----------|
| `user_id → auth.users` | CASCADE (user deletion deletes all data) |
| `category_id → category` | RESTRICT (must reassign first) |
| `invoice_id → invoice` | SET NULL (transaction keeps working) |
| `paired_transaction_id` | SET NULL (clears pair reference) |
| Junction tables | CASCADE (deleted with parent) |

📖 **Full table definitions:** [docs/db/tables.md](./docs/db/tables.md)

---

## 13. Best Practices

1. **Always use RLS** — Never bypass in application code
2. **Soft-delete by default** — Use soft-delete RPCs for user operations
3. **Recompute regularly** — Run reconciliation jobs for cached values
4. **Test concurrency** — Use row-level locking in critical RPCs
5. **Monitor performance** — Watch slow query logs and adjust indexes
6. **Respect single-currency** — Validate currency on entity creation

---

**End of Database Documentation Index**
