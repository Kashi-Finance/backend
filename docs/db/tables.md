# Table Definitions

> Full schema documentation for all Kashi Finances database tables.

---

## Table of Contents

- [auth.users](#authusers)
- [profile](#profile)
- [account](#account)
- [category](#category)
- [invoice](#invoice)
- [recurring_transaction](#recurring_transaction)
- [transaction](#transaction)
- [budget](#budget)
- [budget_category](#budget_category)
- [wishlist](#wishlist)
- [wishlist_item](#wishlist_item)

---

## auth.users

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

## profile

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
| `current_streak` | INTEGER | `NOT NULL DEFAULT 0` | Current consecutive days with activity | `7` |
| `longest_streak` | INTEGER | `NOT NULL DEFAULT 0` | All-time longest streak | `14` |
| `last_activity_date` | DATE | `NULLABLE` | Last date of financial activity | `2025-12-01` |
| `streak_freeze_available` | BOOLEAN | `NOT NULL DEFAULT true` | Whether freeze is available this week | `true` |
| `streak_freeze_used_this_week` | BOOLEAN | `NOT NULL DEFAULT false` | Whether freeze was used this week | `false` |
| `created_at` | TIMESTAMPTZ | `DEFAULT now()` | Row creation timestamp | `2025-10-31T12:00:00-06:00` |
| `updated_at` | TIMESTAMPTZ | `DEFAULT now()` | Last update timestamp | `2025-10-31T12:00:00-06:00` |

**Engagement/Streak Fields:**
- `current_streak`: Increments when user logs activity on consecutive days
- `longest_streak`: Personal best, updated when current_streak exceeds it
- `last_activity_date`: Used to calculate streak continuity (UTC date)
- `streak_freeze_available`: One free freeze per week, protects streak if user misses a day
- `streak_freeze_used_this_week`: Reset by cron job every Monday

**Indexes:** None (small table, single-row lookups by PK)

**Delete Behavior:**
- Profiles are **not physically deleted** while the user exists in `auth.users`
- "Delete profile" requests trigger an **anonymization update**:
  - `first_name` → set to `"Deleted User"`
  - `last_name` → set to `NULL`
  - `avatar_url` → set to `NULL`
- `country` and `currency_preference` are **kept** for system consistency
- Streak fields are preserved (they're not personal data)
- The row must remain because it provides localization data to agents

---

## account

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
| `created_at` | TIMESTAMPTZ | `DEFAULT now()` | Row creation timestamp | `2025-10-29T08:15:00-06:00` |
| `updated_at` | TIMESTAMPTZ | `DEFAULT now()` | Last update timestamp | `2025-10-31T08:15:00-06:00` |

**Account Types:** See [enums.md](./enums.md#account_type_enum)

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

## category

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

**Flow Types:** See [enums.md](./enums.md#flow_type_enum)

**Constraints:**
- `UNIQUE (key, flow_type)` — Each system category key can exist once per flow type
- `CHECK` constraint ensures:
  - System categories: `user_id IS NULL AND key IS NOT NULL`
  - User categories: `user_id IS NOT NULL AND key IS NULL`

**Indexes:**
- `category_user_id_idx` on `(user_id) WHERE user_id IS NOT NULL` — For listing user's categories

**System Categories:** See [system-data.md](./system-data.md#system-category-list)

**Delete Behavior:**

When a user deletes a **user category**:
1. Update all `transaction` rows using that `category_id` to point to the system `general` category (matching flow_type)
2. Delete all `budget_category` rows referencing this category
3. After no transactions or budgets reference it, delete the category

**System categories can never be deleted.**

---

## invoice

User-uploaded invoices/receipts with OCR-extracted text.

| Field | Type | Constraints | Description | Example |
|:------|:-----|:------------|:------------|:--------|
| `id` | UUID (PK) | `PRIMARY KEY DEFAULT gen_random_uuid()` | Invoice identifier | `inv-b3d9b1f6-aa11-422c-a65a-21b1abacfe43` |
| `user_id` | UUID (FK) | `NOT NULL`<br/>`REFERENCES auth.users(id) ON DELETE CASCADE` | Invoice owner | `38f7d540-23fa-497a-8df2-3ab9cbe13da5` |
| `storage_path` | TEXT | `NOT NULL` | Path in Supabase Storage | `invoices/user123/inv-abc.jpg` |
| `extracted_text` | TEXT | `NOT NULL` | OCR text (see format below) | See below |
| `deleted_at` | TIMESTAMPTZ | `NULLABLE` | Soft-delete timestamp | `2025-11-01T10:00:00-06:00` |
| `created_at` | TIMESTAMPTZ | `DEFAULT now()` | Row creation timestamp | `2025-10-30T14:30:00-06:00` |
| `updated_at` | TIMESTAMPTZ | `DEFAULT now()` | Last update timestamp | `2025-10-30T14:30:00-06:00` |

**Indexes:**
- `invoice_user_id_idx` on `(user_id)` — For listing user's invoices
- `invoice_deleted_at_idx` on `(deleted_at) WHERE deleted_at IS NOT NULL` — For filtering soft-deleted invoices

**Extracted Text Format:**

The `extracted_text` field stores OCR text in a **canonical format** defined by the API architecture:

```json
{
  "raw_text": "...",
  "confidence": 0.95,
  "vendor": "Google Cloud Vision",
  "extracted_at": "2025-10-30T14:30:00Z"
}
```

**Delete Behavior:**

When deleting an invoice:
1. Set `deleted_at` (soft-delete)
2. **Archive the storage file** (move to archive path, do not immediately delete)
3. Schedule background purge based on retention policy (e.g., 90 days)
4. If the invoice is referenced by transactions, those transactions keep the reference (invoice_id) but see NULL due to RLS filtering

---

## recurring_transaction

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
| `created_at` | TIMESTAMPTZ | `DEFAULT now()` | Row creation timestamp | `2025-10-30T10:00:00-06:00` |
| `updated_at` | TIMESTAMPTZ | `DEFAULT now()` | Last update timestamp | `2025-10-30T10:00:00-06:00` |

**Frequency Types:** See [enums.md](./enums.md#recurring_frequency_enum)

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
1. Set `deleted_at` (soft-delete)
2. Stop future materialization (backend checks `deleted_at` before creating transactions)
3. **Already-created transactions are NOT affected** (they keep `recurring_transaction_id` reference)
4. If part of a recurring transfer pair, consider soft-deleting both templates together

---

## transaction

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
   - `embedding` field stores a 1536-dimension vector
   - See [semantic-search.md](./semantic-search.md) for details

**Delete Behavior:**

When deleting a transaction:
1. Set `deleted_at` (soft-delete)
2. Decrement `account.cached_balance` atomically using triggers/RPCs
3. If the transaction is part of a budget period, decrement `budget.cached_consumption`
4. If part of a transfer pair (has `paired_transaction_id`), consider deleting both sides together
5. Hard-delete is only performed by admin RPCs for GDPR compliance (after retention period)

**Foreign Key Constraint Note:**

`category_id` uses `ON DELETE RESTRICT` (not CASCADE) because deleting a category requires reassigning all transactions to the `general` category first.

---

## budget

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
| `created_at` | TIMESTAMPTZ | `DEFAULT now()` | Row creation timestamp | `2025-10-30T10:00:00-06:00` |
| `updated_at` | TIMESTAMPTZ | `DEFAULT now()` | Last update timestamp | `2025-11-15T14:00:00-06:00` |

**Frequency Types:** See [enums.md](./enums.md#budget_frequency_enum)

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
1. Set `deleted_at` (soft-delete)
2. Delete all `budget_category` rows linking this budget to categories (CASCADE)
3. Budget stops applying but historical data is retained for reports

---

## budget_category

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

## wishlist

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

**Status Types:** See [enums.md](./enums.md#wishlist_status_enum)

**Indexes:**
- `wishlist_user_id_idx` on `(user_id)` — For listing user's wishlists
- `wishlist_user_status_idx` on `(user_id, status)` — For filtering by status
- `wishlist_created_at_idx` on `(created_at DESC)` — For sorting by creation date

**Delete Behavior:**

When deleting a wishlist:
- All `wishlist_item` rows are automatically deleted (CASCADE)

---

## wishlist_item

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
