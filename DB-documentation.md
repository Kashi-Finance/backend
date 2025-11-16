# Kashi Finances — Database Documentation

**Last Updated:** November 15, 2025  
**Architecture:** Supabase (Auth + Postgres + Storage + RLS + pgvector) + Cloud Run (FastAPI + Python + Google ADK)

---

## Overview

Kashi Finances uses PostgreSQL (via Supabase) to store personal finance data, including:

- User profiles and preferences
- Financial accounts (bank, cash, credit cards, loans, etc.)
- Transactions (income and outcome)
- Invoices and receipts (with OCR text)
- Categories (system-defined and user-defined)
- Budgets and spending limits
- Recurring transaction templates
- Wishlist goals and product recommendations

**Key Design Principles:**

1. **Row-Level Security (RLS)** isolates user data automatically at the database level
2. **Soft-delete strategy** for user-initiated deletions (preserves audit trail and enables recovery)
3. **Cached balances** for performance (recomputable from transaction history)
4. **Semantic search** using pgvector embeddings on transactions
5. **Strong typing** with CHECK constraints and PostgreSQL enums

---

## System Categories

System categories are **global, immutable categories** (where `user_id IS NULL` and `key IS NOT NULL`) that cannot be deleted or modified by users. They are created and managed only by the system via database migrations.

**CRITICAL:** The `(key, flow_type)` combination is UNIQUE. Each system category key exists exactly once per `flow_type`.

### System Category List

| Key | Flow Type | Name | Purpose |
|:----|:----------|:-----|:--------|
| `initial_balance` | `income` | Initial Balance (Income) | Opening balance for income-type accounts |
| `initial_balance` | `outcome` | Initial Balance (Outcome) | Opening balance for outcome-type accounts |
| `balance_update_income` | `income` | Manual Balance Adjustment (Income) | Manual positive balance corrections |
| `balance_update_outcome` | `outcome` | Manual Balance Adjustment (Outcome) | Manual negative balance corrections |
| `transfer` | `income` | Transfer (Income) | Destination side of internal transfers |
| `transfer` | `outcome` | Transfer (Outcome) | Source side of internal transfers |
| `general` | `income` | General Income | Default category for uncategorized income |
| `general` | `outcome` | General Outcome | Default category for uncategorized expenses |

**Important Notes:**

- System categories are **never** used to indicate "this transaction was auto-generated"
- Auto-generated transactions (from recurring rules, invoice OCR, etc.) use the `transaction.system_generated_key` field for metadata
- Categories must always represent **user-intended categorization**

---

## System-Generated Transaction Keys

When transactions are created automatically by the system, they are marked using the `transaction.system_generated_key` field. This is a **human-readable metadata field** used for UI decoration and filtering.

### System-Generated Key List

| Key | Description | Used By |
|:----|:------------|:--------|
| `recurring_rule_auto` | Transaction materialized from a recurring transaction template | Recurring transaction sync process |
| `invoice_ocr` | Transaction created from invoice OCR extraction | Invoice commit endpoint |
| `bulk_import` | Transaction imported via bulk data import | Bulk import tools |

**Important Notes:**

- `system_generated_key` is **nullable** and **optional**
- It is used for **UI decoration only**, not for business logic
- The authoritative link between a transaction and its recurring template is `transaction.recurring_transaction_id`
- User-created manual transactions have `system_generated_key = NULL`

---

## Table Definitions

### Table: `auth.users`

Managed by Supabase Auth. Contains user authentication data.

| Field | Type | Constraints | Description | Example |
|:------|:-----|:------------|:------------|:--------|
| `id` | UUID (PK) | `PRIMARY KEY` | Unique user identifier | `38f7d540-23fa-497a-8df2-3ab9cbe13da5` |
| `email` | TEXT | Unique at auth layer | User email for login | `samuel@example.com` |
| `created_at` | TIMESTAMPTZ | `DEFAULT now()` | Account creation timestamp | `2025-10-30T18:00:00-06:00` |

**Relationships:**
- 1:1 with `profile`
- 1:N with `account`, `transaction`, `invoice`, `budget`, `recurring_transaction`, `category` (user categories only), `wishlist`

**Delete Behavior:**
- Users cannot be directly deleted by the application
- Disable or anonymize through Supabase Auth instead
- If full deletion is required (GDPR), it must be a controlled backend operation that:
  1. Anonymizes or deletes all user-owned data
  2. Archives necessary audit records
  3. Finally removes the user record

---

### Table: `profile`

User profile and preferences. 1:1 relationship with `auth.users`.

| Field | Type | Constraints | Description | Example |
|:------|:-----|:------------|:------------|:--------|
| `user_id` | UUID (PK, FK) | `PRIMARY KEY`<br/>`REFERENCES auth.users(id) ON DELETE CASCADE` | Links to auth user | `38f7d540-23fa-497a-8df2-3ab9cbe13da5` |
| `first_name` | TEXT | `NOT NULL` | User first name | `Samuel` |
| `last_name` | TEXT | `NULLABLE` | User last name | `Marroquín` |
| `avatar_url` | TEXT | `NULLABLE` | Public avatar URL | `https://storage.kashi.app/avatars/u1.png` |
| `currency_preference` | TEXT | `NOT NULL` | ISO currency code for UI | `GTQ` |
| `locale` | TEXT | `NOT NULL DEFAULT 'system'` | Localization hint | `system` |
| `country` | TEXT | `NOT NULL` | ISO-2 country code | `GT` |
| `created_at` | TIMESTAMPTZ | `DEFAULT now()` | Row creation timestamp | `2025-10-31T12:00:00-06:00` |
| `updated_at` | TIMESTAMPTZ | `DEFAULT now()` | Last update timestamp | `2025-10-31T12:00:00-06:00` |

**Indexes:** None (small table, single-row lookups by PK)

**Delete Behavior:**
- Profiles are **not physically deleted** while the user exists in `auth.users`
- "Delete profile" requests trigger an **anonymization update**:
  - `first_name` → set to `"Deleted User"`
  - `last_name` → set to `NULL`
  - `avatar_url` → set to `NULL`
- `country` and `currency_preference` are **kept** for system consistency
- The row must remain because it provides localization data to agents

---

### Table: `account`

Financial accounts owned by users (bank accounts, cash, credit cards, loans, etc.).

| Field | Type | Constraints | Description | Example |
|:------|:-----|:------------|:------------|:--------|
| `id` | UUID (PK) | `PRIMARY KEY DEFAULT gen_random_uuid()` | Account identifier | `a214db42-32b1-4fb2-bbde-37dbce2c0cc4` |
| `user_id` | UUID (FK) | `NOT NULL`<br/>`REFERENCES auth.users(id) ON DELETE CASCADE` | Account owner | `38f7d540-23fa-497a-8df2-3ab9cbe13da5` |
| `name` | TEXT | `NOT NULL` | User-friendly name | `Banco Industrial Checking Account` |
| `type` | account_type_enum | `NOT NULL` | Account type | `bank` |
| `currency` | TEXT | `NOT NULL` | ISO currency code | `GTQ` |
| `cached_balance` | NUMERIC(12,2) | `NOT NULL DEFAULT 0` | Cached balance (performance optimization) | `1500.00` |
| `deleted_at` | TIMESTAMPTZ | `NULLABLE` | Soft-delete timestamp | `2025-11-01T10:00:00-06:00` |
| `deleted_by` | UUID | `NULLABLE` | User who deleted (or NULL if system) | `38f7d540-23fa-497a-8df2-3ab9cbe13da5` |
| `created_at` | TIMESTAMPTZ | `DEFAULT now()` | Row creation timestamp | `2025-10-29T08:15:00-06:00` |
| `updated_at` | TIMESTAMPTZ | `DEFAULT now()` | Last update timestamp | `2025-10-31T08:15:00-06:00` |

**Account Types (account_type_enum):**
- `cash` — Physical cash or wallet
- `bank` — Checking or savings account
- `credit_card` — Credit card account
- `loan` — Loan account
- `remittance` — Remittance/transfer account
- `crypto` — Cryptocurrency wallet
- `investment` — Investment/brokerage account

**Indexes:**
- `account_user_id_idx` on `(user_id)` — For listing user's accounts
- `account_deleted_at_idx` on `(deleted_at) WHERE deleted_at IS NOT NULL` — For filtering soft-deleted accounts

**Important Business Rules:**
- Account balance is **never stored directly**
- `cached_balance` is a **performance cache** recomputable from `transaction` rows
- Balance = SUM(income amounts) - SUM(outcome amounts) for all transactions in the account
- Use `recompute_account_balance(account_id)` RPC to verify/correct the cache

**Delete Behavior:**

Users must choose one of two strategies when deleting an account:

**Option 1: Reassign Transactions**
1. Update all transactions with `account_id = deleted_account_id` to point to a different account (chosen by user)
2. After all transactions are reassigned, delete the account
3. If any transaction cannot be reassigned (e.g., target account doesn't belong to user), the operation fails

**Option 2: Delete All Related Transactions**
1. Delete all transactions with `account_id = deleted_account_id`
2. If any transaction is linked to an invoice that has no other transactions, optionally delete the invoice (following invoice delete rule)
3. After all transactions are deleted, delete the account
4. If any transactions are locked/protected (future audit requirement), the operation fails

Both strategies enforce that the account belongs to the authenticated user.

---

### Table: `category`

Transaction categories. Can be **system categories** (global and immutable) or **user categories** (personal and editable).

| Field | Type | Constraints | Description | Example |
|:------|:-----|:------------|:------------|:--------|
| `id` | UUID (PK) | `PRIMARY KEY DEFAULT gen_random_uuid()` | Category identifier | `c21af3b8-9813-46bb-bce7-347f0f310e00` |
| `user_id` | UUID (FK) | `NULLABLE`<br/>`REFERENCES auth.users(id) ON DELETE CASCADE` | NULL for system categories | `NULL` (system) or UUID (user) |
| `key` | TEXT | `NULLABLE`<br/>`UNIQUE (key, flow_type)` | Stable system key (only for system categories) | `general`, `transfer` |
| `name` | TEXT | `NOT NULL` | User-facing label | `Supermarket` |
| `flow_type` | flow_type_enum | `NOT NULL` | Income or outcome | `outcome` |
| `created_at` | TIMESTAMPTZ | `DEFAULT now()` | Row creation timestamp | `2025-10-30T10:00:00-06:00` |
| `updated_at` | TIMESTAMPTZ | `DEFAULT now()` | Last update timestamp | `2025-10-31T13:20:00-06:00` |

**Flow Types (flow_type_enum):**
- `income` — For income transactions
- `outcome` — For expense transactions

**Constraints:**
- `UNIQUE (key, flow_type)` — Each system category key can exist once per flow type
- `CHECK` constraint ensures:
  - System categories: `user_id IS NULL AND key IS NOT NULL`
  - User categories: `user_id IS NOT NULL AND key IS NULL`

**Indexes:**
- `category_user_id_idx` on `(user_id) WHERE user_id IS NOT NULL` — For listing user's categories

**Delete Behavior:**

When a user deletes a **user category**:
1. Update all `transaction` rows using that `category_id` to point to the system `general` category (matching flow_type)
2. Delete all `budget_category` rows referencing this category
3. After no transactions or budgets reference it, delete the category

**System categories can never be deleted.**

---

### Table: `invoice`

User-uploaded invoices/receipts with OCR-extracted text.

| Field | Type | Constraints | Description | Example |
|:------|:-----|:------------|:------------|:--------|
| `id` | UUID (PK) | `PRIMARY KEY DEFAULT gen_random_uuid()` | Invoice identifier | `inv-b3d9b1f6-aa11-422c-a65a-21b1abacfe43` |
| `user_id` | UUID (FK) | `NOT NULL`<br/>`REFERENCES auth.users(id) ON DELETE CASCADE` | Invoice owner | `38f7d540-23fa-497a-8df2-3ab9cbe13da5` |
| `storage_path` | TEXT | `NOT NULL` | Path in Supabase Storage | `invoices/user123/inv-abc.jpg` |
| `extracted_text` | TEXT | `NOT NULL` | OCR text (see format below) | See below |
| `deleted_at` | TIMESTAMPTZ | `NULLABLE` | Soft-delete timestamp | `2025-11-01T10:00:00-06:00` |
| `deleted_by` | UUID | `NULLABLE` | User who deleted | `38f7d540-23fa-497a-8df2-3ab9cbe13da5` |
| `created_at` | TIMESTAMPTZ | `DEFAULT now()` | Row creation timestamp | `2025-10-30T14:30:00-06:00` |
| `updated_at` | TIMESTAMPTZ | `DEFAULT now()` | Last update timestamp | `2025-10-30T14:30:00-06:00` |

**Indexes:**
- `invoice_user_id_idx` on `(user_id)` — For listing user's invoices
- `invoice_deleted_at_idx` on `(deleted_at) WHERE deleted_at IS NOT NULL` — For filtering soft-deleted invoices

**Extracted Text Format:**

The `extracted_text` field stores OCR text in a **canonical format** defined by the API architecture. This format is:

```
{
  "raw_text": "...",
  "confidence": 0.95,
  "vendor": "Google Cloud Vision",
  "extracted_at": "2025-10-30T14:30:00Z"
}
```

**Delete Behavior:**

When deleting an invoice:
1. Set `deleted_at` and `deleted_by` (soft-delete)
2. **Archive the storage file** (move to archive path, do not immediately delete)
3. Schedule background purge based on retention policy (e.g., 90 days)
4. If the invoice is referenced by transactions, those transactions keep the reference (invoice_id) but see NULL due to RLS filtering

---

### Table: `recurring_transaction`

Templates for generating recurring transactions automatically.

| Field | Type | Constraints | Description | Example |
|:------|:-----|:------------|:------------|:--------|
| `id` | UUID (PK) | `PRIMARY KEY DEFAULT gen_random_uuid()` | Template identifier | `rt-7a8b9c0d-1e2f-3a4b-5c6d-7e8f9a0b1c2d` |
| `user_id` | UUID (FK) | `NOT NULL`<br/>`REFERENCES auth.users(id) ON DELETE CASCADE` | Template owner | `38f7d540-23fa-497a-8df2-3ab9cbe13da5` |
| `account_id` | UUID (FK) | `NOT NULL`<br/>`REFERENCES account(id) ON DELETE CASCADE` | Target account | `a214db42-32b1-4fb2-bbde-37dbce2c0cc4` |
| `category_id` | UUID (FK) | `NULLABLE`<br/>`REFERENCES category(id) ON DELETE SET NULL` | Category for materialized transactions | `c21af3b8-9813-46bb-bce7-347f0f310e00` |
| `flow_type` | flow_type_enum | `NOT NULL` | Income or outcome | `outcome` |
| `amount` | NUMERIC(12,2) | `NOT NULL CHECK (amount >= 0)` | Transaction amount | `150.00` |
| `description` | TEXT | `NOT NULL` | Transaction description | `Monthly gym membership` |
| `paired_recurring_transaction_id` | UUID (FK) | `NULLABLE`<br/>`REFERENCES recurring_transaction(id) ON DELETE SET NULL` | Links two templates for recurring transfers | `rt-9d8e7f6g-5h4i-3j2k-1l0m-n9o8p7q6r5s4` |
| `frequency` | recurring_frequency_enum | `NOT NULL` | Recurrence frequency | `monthly` |
| `interval` | INTEGER | `NOT NULL DEFAULT 1 CHECK (interval >= 1)` | Repetition interval | `1` (every period) |
| `by_weekday` | TEXT[] | `NULLABLE` | For weekly: days of week | `["monday", "friday"]` |
| `by_monthday` | INTEGER[] | `NULLABLE` | For monthly: days of month | `[1, 15]` |
| `start_date` | DATE | `NOT NULL` | Start date for recurrence | `2025-01-01` |
| `next_run_date` | DATE | `NOT NULL` | Next materialization date | `2025-12-01` |
| `end_date` | DATE | `NULLABLE` | Optional end date | `2026-12-31` |
| `is_active` | BOOLEAN | `NOT NULL DEFAULT true` | Active/inactive status | `true` |
| `deleted_at` | TIMESTAMPTZ | `NULLABLE` | Soft-delete timestamp | `NULL` |
| `deleted_by` | UUID | `NULLABLE` | User who deleted | `NULL` |
| `created_at` | TIMESTAMPTZ | `DEFAULT now()` | Row creation timestamp | `2025-10-30T10:00:00-06:00` |
| `updated_at` | TIMESTAMPTZ | `DEFAULT now()` | Last update timestamp | `2025-10-30T10:00:00-06:00` |

**Frequency Types (recurring_frequency_enum):**
- `daily` — Repeats daily
- `weekly` — Repeats weekly
- `monthly` — Repeats monthly
- `yearly` — Repeats yearly

**Indexes:**
- `recurring_tx_user_active_idx` on `(user_id, is_active, next_run_date)` — For finding active templates to materialize
- `recurring_tx_paired_idx` on `(paired_recurring_transaction_id) WHERE paired_recurring_transaction_id IS NOT NULL` — For transfer lookups
- `recurring_tx_deleted_at_idx` on `(deleted_at) WHERE deleted_at IS NOT NULL` — For filtering soft-deleted templates

**Recurring Transfers:**

Transfers between accounts are modeled as **two linked transactions** (one outcome, one income). For **recurring transfers**, we need **two linked templates**:

1. Create two `recurring_transaction` rows (one outcome, one income)
2. Set `paired_recurring_transaction_id` on each to reference the other
3. Ensure both templates have matching amounts, frequencies, and dates
4. When materialized, create two transactions linked via `paired_transaction_id`

**Delete Behavior:**

When deleting a recurring transaction template:
1. Set `deleted_at` and `deleted_by` (soft-delete)
2. Stop future materialization (backend checks `deleted_at` before creating transactions)
3. **Already-created transactions are NOT affected** (they keep `recurring_transaction_id` reference)
4. If part of a recurring transfer pair, consider soft-deleting both templates together

---

### Table: `transaction`

Individual financial transactions (income or outcome). Account balance is derived by summing transaction amounts.

| Field | Type | Constraints | Description | Example |
|:------|:-----|:------------|:------------|:--------|
| `id` | UUID (PK) | `PRIMARY KEY DEFAULT gen_random_uuid()` | Transaction identifier | `tx-1a2b3c4d-5e6f-7a8b-9c0d-1e2f3a4b5c6d` |
| `user_id` | UUID (FK) | `NOT NULL`<br/>`REFERENCES auth.users(id) ON DELETE CASCADE` | Transaction owner | `38f7d540-23fa-497a-8df2-3ab9cbe13da5` |
| `account_id` | UUID (FK) | `NOT NULL`<br/>`REFERENCES account(id) ON DELETE CASCADE` | Associated account | `a214db42-32b1-4fb2-bbde-37dbce2c0cc4` |
| `category_id` | UUID (FK) | `NOT NULL`<br/>`REFERENCES category(id) ON DELETE RESTRICT` | Transaction category | `c21af3b8-9813-46bb-bce7-347f0f310e00` |
| `invoice_id` | UUID (FK) | `NULLABLE`<br/>`REFERENCES invoice(id) ON DELETE SET NULL` | Linked invoice (if any) | `inv-b3d9b1f6-aa11-422c-a65a-21b1abacfe43` |
| `flow_type` | flow_type_enum | `NOT NULL` | Income or outcome | `outcome` |
| `amount` | NUMERIC(12,2) | `NOT NULL CHECK (amount >= 0)` | Transaction amount (always positive) | `150.00` |
| `date` | TIMESTAMPTZ | `NOT NULL` | Effective date of transaction | `2025-10-30T14:30:00-06:00` |
| `description` | TEXT | `NULLABLE` | User-provided description | `Gym membership payment` |
| `embedding` | VECTOR(1536) | `NULLABLE` | Semantic embedding for search | `[0.1, -0.3, ...]` |
| `paired_transaction_id` | UUID (FK) | `NULLABLE`<br/>`REFERENCES transaction(id) ON DELETE SET NULL` | Links two transactions for transfers | `tx-9d8e7f6g-5h4i-3j2k-1l0m` |
| `recurring_transaction_id` | UUID (FK) | `NULLABLE`<br/>`REFERENCES recurring_transaction(id) ON DELETE SET NULL` | Template that generated this transaction | `rt-7a8b9c0d-1e2f-3a4b-5c6d` |
| `system_generated_key` | TEXT | `NULLABLE` | Human-readable system marker | `recurring_rule_auto` |
| `deleted_at` | TIMESTAMPTZ | `NULLABLE` | Soft-delete timestamp | `NULL` |
| `deleted_by` | UUID | `NULLABLE` | User who deleted | `NULL` |
| `created_at` | TIMESTAMPTZ | `DEFAULT now()` | Row creation timestamp | `2025-10-30T14:30:00-06:00` |
| `updated_at` | TIMESTAMPTZ | `DEFAULT now()` | Last update timestamp | `2025-10-30T14:30:00-06:00` |

**Indexes:**
- `transaction_user_date_idx` on `(user_id, date DESC)` — For user transaction history
- `transaction_account_idx` on `(account_id, date DESC)` — For account transaction history
- `transaction_category_idx` on `(category_id)` — For category-based queries
- `transaction_recurring_idx` on `(recurring_transaction_id) WHERE recurring_transaction_id IS NOT NULL` — For finding transactions from a template
- `transaction_paired_idx` on `(paired_transaction_id) WHERE paired_transaction_id IS NOT NULL` — For transfer lookups
- `transaction_invoice_idx` on `(invoice_id) WHERE invoice_id IS NOT NULL` — For invoice-linked transactions
- `transaction_deleted_at_idx` on `(deleted_at) WHERE deleted_at IS NOT NULL` — For filtering soft-deleted transactions
- `transaction_embedding_idx` using `ivfflat (embedding vector_cosine_ops)` — For semantic search

**Important Business Rules:**

1. **Balance Calculation:**
   - Account balance = SUM(income amounts) - SUM(outcome amounts)
   - Balance is **never stored directly** in the account table
   - `account.cached_balance` is a performance cache that is recomputable

2. **Transfers:**
   - Modeled as **two linked transactions** (one outcome, one income)
   - Both transactions reference each other via `paired_transaction_id`
   - Both use the system category `transfer` (matching their flow_type)
   - Deleting one side should delete both (or fail if not allowed)

3. **Recurring Transactions:**
   - When a recurring template materializes, it creates a transaction with:
     - `recurring_transaction_id` = template ID
     - `system_generated_key` = `"recurring_rule_auto"` (optional)
   - The link is preserved even if the template is later deleted (soft-delete)

4. **Semantic Search:**
   - `embedding` field stores a 1536-dimension vector (e.g., from `text-embedding-3-large`)
   - Enables natural language search like "supermarket expenses last month"
   - Generated by backend when transaction is created/updated

**Delete Behavior:**

When deleting a transaction:
1. Set `deleted_at` and `deleted_by` (soft-delete)
2. Decrement `account.cached_balance` atomically using triggers/RPCs
3. If the transaction is part of a budget period, decrement `budget.cached_consumption`
4. If part of a transfer pair (has `paired_transaction_id`), consider deleting both sides together
5. Hard-delete is only performed by admin RPCs for GDPR compliance (after retention period)

**Foreign Key Constraint Note:**

`category_id` uses `ON DELETE RESTRICT` (not CASCADE) because deleting a category requires reassigning all transactions to the `general` category first.

---

### Table: `budget`

Spending limits that can be one-time or recurring.

| Field | Type | Constraints | Description | Example |
|:------|:-----|:------------|:------------|:--------|
| `id` | UUID (PK) | `PRIMARY KEY DEFAULT gen_random_uuid()` | Budget identifier | `b-1a2b3c4d-5e6f-7a8b-9c0d-1e2f3a4b5c6d` |
| `name` | TEXT | `NOT NULL` | Budget name | `Monthly Groceries` |
| `user_id` | UUID (FK) | `NOT NULL`<br/>`REFERENCES auth.users(id) ON DELETE CASCADE` | Budget owner | `38f7d540-23fa-497a-8df2-3ab9cbe13da5` |
| `limit_amount` | NUMERIC(12,2) | `NOT NULL CHECK (limit_amount > 0)` | Budget limit | `500.00` |
| `frequency` | budget_frequency_enum | `NOT NULL` | Recurrence frequency | `monthly` |
| `interval` | INTEGER | `NOT NULL DEFAULT 1 CHECK (interval >= 1)` | Repetition interval | `1` |
| `start_date` | DATE | `NOT NULL` | Budget start date | `2025-11-01` |
| `end_date` | DATE | `NULLABLE` | Optional end date (for project budgets) | `2025-12-31` |
| `is_active` | BOOLEAN | `NOT NULL DEFAULT true` | Active/inactive status | `true` |
| `cached_consumption` | NUMERIC(12,2) | `NOT NULL DEFAULT 0` | Current period consumption (cache) | `320.50` |
| `deleted_at` | TIMESTAMPTZ | `NULLABLE` | Soft-delete timestamp | `NULL` |
| `deleted_by` | UUID | `NULLABLE` | User who deleted | `NULL` |
| `created_at` | TIMESTAMPTZ | `DEFAULT now()` | Row creation timestamp | `2025-10-30T10:00:00-06:00` |
| `updated_at` | TIMESTAMPTZ | `DEFAULT now()` | Last update timestamp | `2025-11-15T14:00:00-06:00` |

**Frequency Types (budget_frequency_enum):**
- `once` — One-time budget
- `daily` — Repeats daily
- `weekly` — Repeats weekly
- `monthly` — Repeats monthly
- `yearly` — Repeats yearly

**Indexes:**
- `budget_user_active_idx` on `(user_id, is_active)` — For finding active budgets
- `budget_deleted_at_idx` on `(deleted_at) WHERE deleted_at IS NOT NULL` — For filtering soft-deleted budgets

**Budget Consumption:**

- A budget tracks spending across one or more categories (linked via `budget_category` table)
- `cached_consumption` stores the **current period's spending** (performance cache)
- Consumption = SUM of all `outcome` transactions in linked categories within the current budget period
- Use `recompute_budget_consumption(budget_id, period_start, period_end)` RPC to verify/correct the cache

**Delete Behavior:**

When deleting a budget:
1. Set `deleted_at` and `deleted_by` (soft-delete)
2. Delete all `budget_category` rows linking this budget to categories (CASCADE)
3. Budget stops applying but historical data is retained for reports

---

### Table: `budget_category`

N:M relationship between budgets and categories. Links budgets to the categories they track.

| Field | Type | Constraints | Description | Example |
|:------|:-----|:------------|:------------|:--------|
| `budget_id` | UUID (PK, FK) | `PRIMARY KEY`<br/>`REFERENCES budget(id) ON DELETE CASCADE` | Budget ID | `b-1a2b3c4d-5e6f-7a8b-9c0d` |
| `category_id` | UUID (PK, FK) | `PRIMARY KEY`<br/>`REFERENCES category(id) ON DELETE CASCADE` | Category ID | `c21af3b8-9813-46bb-bce7` |
| `user_id` | UUID (FK) | `NOT NULL`<br/>`REFERENCES auth.users(id) ON DELETE CASCADE` | Owner (for RLS) | `38f7d540-23fa-497a-8df2-3ab9cbe13da5` |
| `created_at` | TIMESTAMPTZ | `DEFAULT now()` | Row creation timestamp | `2025-10-30T10:00:00-06:00` |
| `updated_at` | TIMESTAMPTZ | `DEFAULT now()` | Last update timestamp | `2025-10-30T10:00:00-06:00` |

**Composite Primary Key:** `(budget_id, category_id)` prevents duplicates

**Indexes:**
- `budget_category_user_idx` on `(user_id)` — For user-scoped queries
- `budget_category_category_idx` on `(category_id)` — For finding budgets that track a category

**Delete Behavior:**

- When a budget is deleted, all `budget_category` rows are automatically deleted (CASCADE)
- When a category is deleted, all `budget_category` rows are automatically deleted (CASCADE)

---

### Table: `wishlist`

User purchase goals with budget and timeline.

| Field | Type | Constraints | Description | Example |
|:------|:-----|:------------|:------------|:--------|
| `id` | UUID (PK) | `PRIMARY KEY DEFAULT gen_random_uuid()` | Wishlist identifier | `w-1a2b3c4d-5e6f-7a8b-9c0d` |
| `user_id` | UUID (FK) | `NOT NULL`<br/>`REFERENCES auth.users(id) ON DELETE CASCADE` | Wishlist owner | `38f7d540-23fa-497a-8df2-3ab9cbe13da5` |
| `goal_title` | TEXT | `NOT NULL` | Goal description | `New laptop for work` |
| `budget_hint` | NUMERIC(12,2) | `NOT NULL` | Budget estimate | `1500.00` |
| `currency_code` | TEXT | `NOT NULL` | Currency for budget | `USD` |
| `target_date` | DATE | `NULLABLE` | Optional target date | `2025-12-31` |
| `preferred_store` | TEXT | `NULLABLE` | Preferred seller/store | `Best Buy` |
| `user_note` | TEXT | `NULLABLE` | User notes | `Needs to run Linux` |
| `status` | wishlist_status_enum | `NOT NULL` | Goal status | `active` |
| `created_at` | TIMESTAMPTZ | `DEFAULT now()` | Row creation timestamp | `2025-10-30T10:00:00-06:00` |
| `updated_at` | TIMESTAMPTZ | `DEFAULT now()` | Last update timestamp | `2025-11-15T14:00:00-06:00` |

**Status Types (wishlist_status_enum):**
- `active` — Goal is active
- `purchased` — Goal has been achieved/purchased
- `abandoned` — Goal has been abandoned

**Indexes:**
- `wishlist_user_id_idx` on `(user_id)` — For listing user's wishlists
- `wishlist_user_status_idx` on `(user_id, status)` — For filtering by status
- `wishlist_created_at_idx` on `(created_at DESC)` — For sorting by creation date

**Delete Behavior:**

When deleting a wishlist:
- All `wishlist_item` rows are automatically deleted (CASCADE)

---

### Table: `wishlist_item`

Product recommendations saved by user within a wishlist goal.

| Field | Type | Constraints | Description | Example |
|:------|:-----|:------------|:------------|:--------|
| `id` | UUID (PK) | `PRIMARY KEY DEFAULT gen_random_uuid()` | Item identifier | `wi-1a2b3c4d-5e6f-7a8b-9c0d` |
| `wishlist_id` | UUID (FK) | `NOT NULL`<br/>`REFERENCES wishlist(id) ON DELETE CASCADE` | Parent wishlist | `w-1a2b3c4d-5e6f-7a8b-9c0d` |
| `product_title` | TEXT | `NOT NULL` | Product name | `Dell XPS 13 Laptop` |
| `price_total` | NUMERIC(12,2) | `NOT NULL` | Total price | `1299.99` |
| `seller_name` | TEXT | `NOT NULL` | Seller/store name | `Best Buy` |
| `url` | TEXT | `NOT NULL` | Product URL | `https://bestbuy.com/...` |
| `pickup_available` | BOOLEAN | `NOT NULL DEFAULT false` | In-store pickup option | `true` |
| `warranty_info` | TEXT | `NOT NULL` | Warranty details | `1-year manufacturer warranty` |
| `copy_for_user` | TEXT | `NOT NULL` | AI-generated description | `Great for productivity...` |
| `badges` | JSONB | `NOT NULL DEFAULT '[]'` | Feature badges | `["free_shipping", "bestseller"]` |
| `created_at` | TIMESTAMPTZ | `DEFAULT now()` | Row creation timestamp | `2025-10-30T10:00:00-06:00` |
| `updated_at` | TIMESTAMPTZ | `DEFAULT now()` | Last update timestamp | `2025-10-30T10:00:00-06:00` |

**Indexes:**
- `wishlist_item_wishlist_id_idx` on `(wishlist_id)` — For listing items in a wishlist
- `wishlist_item_join_idx` on `(wishlist_id, created_at DESC)` — For sorted listing with join pattern

**Delete Behavior:**

- When a wishlist is deleted, all items are automatically deleted (CASCADE)

---

## Row-Level Security (RLS)

All user-owned tables enforce **Row-Level Security (RLS)** to automatically isolate user data at the database level.

### RLS Pattern

**For user-owned tables (account, transaction, invoice, budget, recurring_transaction):**

```sql
-- SELECT: Users see only non-deleted rows they own
user_id = auth.uid() AND deleted_at IS NULL

-- INSERT: Users can only insert for themselves
user_id = auth.uid()

-- UPDATE: Users can only update non-deleted rows they own
USING: user_id = auth.uid() AND deleted_at IS NULL
WITH CHECK: user_id = auth.uid()

-- DELETE: Users can only delete rows they own
user_id = auth.uid()
```

**For category table (special case):**

```sql
-- SELECT: Users see their own categories AND global system categories
user_id = auth.uid() OR user_id IS NULL

-- INSERT: Users can only create personal categories (key must be NULL)
user_id = auth.uid() AND key IS NULL

-- UPDATE: Users can only update their own categories (not system categories)
user_id = auth.uid() AND key IS NULL

-- DELETE: Users can only delete their own categories (not system categories)
user_id = auth.uid() AND key IS NULL
```

**For wishlist_item table (indirect ownership):**

```sql
-- Access control via JOIN to wishlist table
EXISTS (
  SELECT 1 FROM public.wishlist w
  WHERE w.id = wishlist_item.wishlist_id
    AND w.user_id = auth.uid()
)
```

---

## Soft-Delete Strategy

Most user-initiated deletions are **soft-deletes**, not physical deletions.

### Why Soft-Delete?

1. **Recoverability** — Users can restore accidentally deleted data
2. **Audit Trail** — Support teams can debug issues with historical data
3. **Referential Safety** — Avoid cascade deletion of related objects (invoices, paired transactions, etc.)
4. **Better UX** — Enables undo functionality

### Implementation

**Soft-delete columns (added to tables):**
- `deleted_at` (TIMESTAMPTZ NULL) — Timestamp when deleted
- `deleted_by` (UUID NULL) — User who performed the delete (or NULL if system)

**RLS enforcement:**
- User queries automatically filter `deleted_at IS NULL`
- Backend services can query soft-deleted rows when needed for recovery/audit operations

**Service layer behavior:**
- DELETE endpoints call soft-delete RPCs instead of physical deletes
- RPCs return summary of what was soft-deleted
- Cached balances are adjusted atomically

### Hard-Delete Path (GDPR Compliance)

For GDPR "right to be forgotten" requests:

1. Use dedicated GDPR compliance RPCs (not exposed to regular API)
2. Requires approval and logging
3. Must wait for retention window to expire (e.g., 90 days after soft-delete)
4. Physically removes data from database
4. Permanently removes rows and anonymizes related data
5. Archives invoice storage files before deletion

---

## Cached Balances and Consumption

For performance, we cache computed values that can be derived from transaction history.

### Cached Fields

1. **`account.cached_balance`** (NUMERIC(12,2))
   - Performance cache of account balance
   - Recomputable: SUM(income amounts) - SUM(outcome amounts)
   - Updated atomically via triggers/RPCs
   - Use `recompute_account_balance(account_id)` to verify

2. **`budget.cached_consumption`** (NUMERIC(12,2))
   - Performance cache of current period spending
   - Recomputable: SUM(outcome transactions in linked categories within period)
   - Updated atomically via triggers/RPCs
   - Use `recompute_budget_consumption(budget_id, period_start, period_end)` to verify

### Reconciliation

- Scheduled background jobs verify cached values against transaction history
- If drift exceeds threshold, alerts are raised
- Auto-correction or manual review depending on policy

---

## Indexes and Performance

### Index Strategy

1. **User-scoped queries** — Most queries filter by `user_id`, so indexes on `(user_id, ...)` are common
2. **Soft-delete filtering** — Partial indexes on `deleted_at WHERE deleted_at IS NOT NULL` optimize filtering
3. **Foreign key lookups** — Indexes on FK columns for joins and cascades
4. **Temporal queries** — Indexes on `(user_id, date DESC)` for transaction history
5. **Semantic search** — IVFFlat index on embedding vectors

### Most Important Indexes

- `transaction_user_date_idx` — User transaction history
- `transaction_account_idx` — Account transaction history
- `transaction_embedding_idx` — Semantic search
- `recurring_tx_user_active_idx` — Finding templates to materialize
- `budget_user_active_idx` — Finding active budgets

---

## Data Integrity Constraints

### CHECK Constraints

- `amount >= 0` — Transaction amounts are always positive; flow_type determines direction
- `limit_amount > 0` — Budgets must have positive limits
- `interval >= 1` — Frequency intervals must be at least 1
- Category scope constraint — System categories have `key`, user categories don't

### UNIQUE Constraints

- `category(key, flow_type)` — Each system category key exists once per flow type
- `budget_category(budget_id, category_id)` — Prevents duplicate category links

### Foreign Key Constraints

**Soft-Delete Compatible Constraints:**

For tables using soft-delete strategy (`deleted_at` column), foreign keys use `ON DELETE RESTRICT` to prevent cascade deletion:
- `transaction.account_id → account(id) ON DELETE RESTRICT` — Transactions remain when account is soft-deleted (RLS hides deleted accounts)
- `recurring_transaction.account_id → account(id) ON DELETE RESTRICT` — Templates remain when account is soft-deleted

**Category Constraints:**
- `transaction.category_id → category(id) ON DELETE RESTRICT` — Requires reassignment to `general` category before deletion

**Optional Reference Constraints:**
- `transaction.invoice_id → invoice(id) ON DELETE SET NULL` — Transaction remains if invoice is deleted
- `transaction.paired_transaction_id → transaction(id) ON DELETE SET NULL` — Clears pair reference if partner is deleted
- `transaction.recurring_transaction_id → recurring_transaction(id) ON DELETE SET NULL` — Transaction remains if template is deleted
- `recurring_transaction.paired_recurring_transaction_id → recurring_transaction(id) ON DELETE SET NULL` — Clears pair reference if partner template is deleted
- `recurring_transaction.category_id → category(id) ON DELETE SET NULL` — Template remains if category is deleted

**Cascade Constraints (Parent-Child Relationships):**
- Most `user_id` FKs use `ON DELETE CASCADE` — Deleting user deletes all owned data
- `budget_category` junction table uses `ON DELETE CASCADE` for both sides

**Important:** Soft-delete operations use RPCs that set `deleted_at` without triggering FK actions. Hard-delete (GDPR compliance) uses admin RPCs that explicitly handle all references before physical deletion.

---

## Semantic Search

Transactions support natural language search via pgvector embeddings.

### Implementation

1. **Embedding generation** — Backend generates 1536-dimension vectors using embedding model (e.g., `text-embedding-3-large`)
2. **Storage** — Stored in `transaction.embedding` (VECTOR(1536))
3. **Index** — IVFFlat index for cosine similarity search
4. **Query** — Users can search "supermarket last month" and get relevant transactions even if description varies

### Example Query

```sql
SELECT * FROM transaction
WHERE user_id = auth.uid() AND deleted_at IS NULL
ORDER BY embedding <=> '[embedding_vector]'
LIMIT 10;
```

---

## Enums Reference

### account_type_enum

| Value | Description |
|:------|:------------|
| `cash` | Physical cash or wallet |
| `bank` | Checking or savings account |
| `credit_card` | Credit card account |
| `loan` | Loan account |
| `remittance` | Remittance/transfer account |
| `crypto` | Cryptocurrency wallet |
| `investment` | Investment/brokerage account |

### flow_type_enum

| Value | Description |
|:------|:------------|
| `income` | Money coming in (positive) |
| `outcome` | Money going out (negative) |

### budget_frequency_enum

| Value | Description |
|:------|:------------|
| `once` | One-time budget |
| `daily` | Repeats daily |
| `weekly` | Repeats weekly |
| `monthly` | Repeats monthly |
| `yearly` | Repeats yearly |

### recurring_frequency_enum

| Value | Description |
|:------|:------------|
| `daily` | Repeats daily |
| `weekly` | Repeats weekly |
| `monthly` | Repeats monthly |
| `yearly` | Repeats yearly |

### wishlist_status_enum

| Value | Description |
|:------|:------------|
| `active` | Goal is active |
| `purchased` | Goal has been achieved/purchased |
| `abandoned` | Goal has been abandoned |

---

## Entity Relationship Summary

```
auth.users (1) → (1) profile
auth.users (1) → (N) account
auth.users (1) → (N) category (user categories only)
auth.users (1) → (N) invoice
auth.users (1) → (N) transaction
auth.users (1) → (N) budget
auth.users (1) → (N) recurring_transaction
auth.users (1) → (N) wishlist

account (1) → (N) transaction
account (1) → (N) recurring_transaction

category (1) → (N) transaction
category (1) → (N) recurring_transaction
category (1) → (N) budget_category

invoice (1) → (N) transaction

transaction (1) ↔ (1) transaction (paired_transaction_id for transfers)
recurring_transaction (1) → (N) transaction
recurring_transaction (1) ↔ (1) recurring_transaction (paired for recurring transfers)

budget (1) → (N) budget_category
budget (M) ↔ (N) category (via budget_category)

wishlist (1) → (N) wishlist_item
```

---

## Best Practices

1. **Always use RLS** — Never bypass RLS in application code
2. **Soft-delete by default** — Use soft-delete RPCs for user operations
3. **Recompute regularly** — Run reconciliation jobs to verify cached balances
4. **Test concurrency** — Use row-level locking (`SELECT ... FOR UPDATE`) in RPCs for critical operations
5. **Monitor performance** — Watch slow query logs and adjust indexes as needed
6. **Document schema changes** — Keep this document updated when schema evolves

---

**End of Database Documentation**
