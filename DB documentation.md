# Kashi Finances — Database Documentation (Visual Layout)

**Architecture:** Supabase (Auth + Postgres + Storage + RLS + pgvector) + Cloud Run (FastAPI + Python + Google ADK)


---

## 🧠 Overview

Kashi Finances stores personal finance data, invoices, recurring payments, budgets, wishlist goals, and AI-search metadata.

Postgres enforces:

- Strong typing (UUID, NUMERIC, TIMESTAMPTZ)
- Business logic using `CHECK` constraints
- Semantic search with `pgvector`
- Access isolation with RLS

This document includes:

- Every table
- Field types and meaning
- Allowed values / enum-style constraints
- Integrity / CHECK rules
- Cross-table behavior (appendices)

---

## 👤 Table: `auth_users`

|Field|Type|Constraints / Checks|Description|Example|
|:--|:--|:--|:--|:--|
|`id`|UUID (PK)|`PRIMARY KEY`|Unique user id (Supabase Auth).|`38f7d540-23fa-497a-8df2-3ab9cbe13da5`|
|`email`|TEXT|Should be unique at auth layer|Login email.|`samuel@example.com`|
|`created_at`|TIMESTAMPTZ|`DEFAULT now()` (Supabase)|When the account was created.|`2025-10-30T18:00:00-06:00`|

**Relationship summary:**

- `auth_users` → (1) `profile`
- `auth_users` → (N) `account`, `transaction`, `budget`, `wishlist_item`, `recurring_transaction`, `invoice`, custom `category`

**Delete rule:**

Users cannot be deleted directly. Instead, accounts should be disabled or anonymized through Supabase Auth.  
Since all financial data (`transaction`, `invoice`, `budget`, etc.) depend on `auth_users.id`, deleting a user would cascade across the system.  
If full deletion is ever required (for example, GDPR compliance), it must be handled as a controlled backend operation that first anonymizes or deletes all user-owned rows in related tables, before finally removing the user record.

---

## 🧾 Table: `profile`

| Field                 | Type                          | Constraints / Checks                                             | Description                         | Example                                    |
| :-------------------- | :---------------------------- | :--------------------------------------------------------------- | :---------------------------------- | :----------------------------------------- |
| `user_id`             | UUID (PK, FK → auth_users.id) | `PRIMARY KEY`, `REFERENCES auth_users(id)`                       | Links to the auth user.             | `38f7d540-23fa-497a-8df2-3ab9cbe13da5`     |
| `first_name`          | TEXT                          | `NOT NULL`                                                       | User first name.                    | `Samuel`                                   |
| `last_name`           | TEXT                          | `NULLABLE`                                                       | User last name.                     | `Marroquín`                                |
| `avatar_url`          | TEXT                          | `NULLABLE`                                                       | Public avatar URL.                  | `https://storage.kashi.app/avatars/u1.png` |
| `currency_preference` | TEXT                          | `NOT NULL`, suggested ISO code like `GTQ`, not enforced by CHECK | Preferred currency for UI.          | `GTQ`                                      |
| `locale`              | TEXT                          | `DEFAULT 'system'`                                               | Language / localization hint.       | `system`                                   |
| `country`             | TEXT                          | `NOT NULL`, expected ISO-2 country code                          | Used for geo-aware recommendations. | `GT`                                       |
| `created_at`          | TIMESTAMPTZ                   | `DEFAULT now()`                                                  | Row creation timestamp.             | `2025-10-31T12:00:00-06:00`                |
| `updated_at`          | TIMESTAMPTZ                   | `DEFAULT now()`                                                  | Last update timestamp.              | `2025-10-31T12:00:00-06:00`                |

**Notes:**

- `country` is consumed by RecommendationCoordinatorAgent via an internal tool `getUserCountry(user_id)` to localize sellers / prices.

**Delete rule:**

Profiles are not physically deleted while the user exists in `auth_users`.  
If a user requests “delete profile,” the backend must perform an update instead — clearing or anonymizing personal fields (`first_name`, `last_name`, `avatar_url`, etc.) while keeping the row for internal consistency (country, currency preferences, etc.).  
The record must remain because it provides localization data to other agents.

---

## 💳 Table: `account`

| Field        | Type        | Constraints / Checks                                                                                  | Description                                       | Example                                |
| :----------- | :---------- | :---------------------------------------------------------------------------------------------------- | :------------------------------------------------ | :------------------------------------- |
| `id`         | UUID (PK)   | `PRIMARY KEY`                                                                                         | Account identifier.                               | `a214db42-32b1-4fb2-bbde-37dbce2c0cc4` |
| `user_id`    | UUID        | `NOT NULL`, `REFERENCES auth_users(id)`                                                               | Owner of the account.                             | `38f7d540-23fa-497a-8df2-3ab9cbe13da5` |
| `name`       | TEXT        | `NOT NULL`                                                                                            | Human-readable name.                              | `Banco Industrial Checking Account`    |
| `type`       | TEXT        | `CHECK (type IN ('cash','bank','credit_card','loan','remittance','crypto','investment'))`, `NOT NULL` | Kind of financial container.                      | `bank`                                 |
| `currency`   | TEXT        | `NOT NULL`                                                                                            | ISO-like currency code the balance is tracked in. | `GTQ`                                  |
| `created_at` | TIMESTAMPTZ | `DEFAULT now()`                                                                                       | When this account row was created.                | `2025-10-29T08:15:00-06:00`            |
| `updated_at` | TIMESTAMPTZ | `DEFAULT now()`                                                                                       | Last time the row was updated.                    | `2025-10-31T08:15:00-06:00`            |

**Enum-style values:** `type`

- `cash` — literal wallet / cash-in-hand tracking
- `bank` — checking / savings
- `credit_card` — credit line you owe
- `loan` — you owe money (personal loan, etc.)
- `remittance` — money transfer channel (incoming remittances)
- `crypto` — crypto wallet
- `investment` — brokerage / stocks / funds

**Important business rule:**

- We **never** store a `balance` column. The effective balance is computed from `transaction` rows (sum of income minus sum of outcome) for that account.


**Delete rule:**  

An account cannot just “disappear”. The backend must handle all `transaction` rows that reference that account **before** deleting it.  
There are two allowed flows. The app will explicitly ask the user which one they want:

**Option 1 — Reassign transactions, then delete the account**

1. The backend must update every `transaction` where `transaction.account_id` equals the account being deleted.
2. All those transactions must be reassigned to another existing account that belongs to the same user (the replacement account is chosen by the user in the UI).
3. After every transaction has been successfully reassigned, the original account can be safely deleted.
4. If any transaction cannot be reassigned (for example, the target account doesn’t belong to the same user), the delete must fail.

**Option 2 — Delete all related transactions, then delete the account**

1. The backend must delete every `transaction` where `transaction.account_id` equals the account being deleted.
    
    - If any of those transactions are part of an internal transfer pair (`paired_transaction_id`), both sides of the transfer must be cleaned up. That means: clear the link so no transaction points to a deleted one.
    - If any of those transactions are linked to an invoice (`invoice_id`), and that invoice is only referenced by this transaction, the backend may also delete that invoice following the invoice delete rule (including deleting the stored file).
2. After all related transactions are deleted (and any dependent cleanup is done), the account itself can be deleted.
3. If for policy/audit reasons the system is not allowed to delete certain transactions (for example, locked records in the future), the delete must fail.

In both options, the backend must enforce that the account being deleted belongs to the authenticated user.

---

## 🗂 Table: `category`

| Field        | Type        | Constraints / Checks                                    | Description                           | Example                                |
| :----------- | :---------- | :------------------------------------------------------ | :------------------------------------ | :------------------------------------- |
| `id`         | UUID (PK)   | `PRIMARY KEY`                                           | Category identifier.                  | `c21af3b8-9813-46bb-bce7-347f0f310e00` |
| `user_id`    | UUID        | `REFERENCES auth_users(id)`, `NULLABLE`                 | NULL → global/system category.        | `NULL`                                 |
| `key`        | TEXT        | `UNIQUE`, only set for system categories                | Stable system key.                    | `initial_balance`                      |
| `name`       | TEXT        | `NOT NULL`                                              | User-facing label.                    | `Supermarket`                          |
| `flow_type`  | TEXT        | `CHECK (flow_type IN ('income','outcome'))`, `NOT NULL` | Direction of money for this category. | `outcome`                              |
| `created_at` | TIMESTAMPTZ | `DEFAULT now()`                                         | Row creation timestamp.               | `2025-10-30T10:00:00-06:00`            |
| `updated_at` | TIMESTAMPTZ | `DEFAULT now()`                                         | Last update timestamp.                | `2025-10-31T13:20:00-06:00`            |

**System categories** (global, `user_id IS NULL`, `key` present):

- `initial_balance` — opening balance seeding an account
- `balance_update_income` — manual positive adjustment
- `balance_update_outcome` — manual negative adjustment
- `from_recurrent_transaction` — money auto-logged from a recurring schedule
- `transfer` — assigned when a transaction is used as transfer part
- `general` — for no-assigned category transactions

**User categories** (personal, `user_id NOT NULL`, `key IS NULL`):

- Can be edited/renamed by the user
- Can be attached to `budget` via `budget_category`

**Enum-style values:** `flow_type`

- `outcome` — for `outcome` transactions
- `income` — for `income` transactions

**Delete rule:**  

When a user requests to delete a category:

1. The backend must update all `transaction` rows using that `category_id` to the system-wide default category identified by the key `general`.
2. After no transactions reference the deleted category, it can safely be removed.
3. Any `budget_category` rows referencing this category must also be removed.  
    System categories (`user_id IS NULL`, `key` present) can never be deleted.

---

## 📑 Table: `invoice`

|Field|Type|Constraints / Checks|Description|Example|
|:--|:--|:--|:--|:--|
|`id`|UUID (PK)|`PRIMARY KEY`|Invoice record id.|`inv-b3d9b1f6-aa11-422c-a65a-21b1abacfe43`|
|`user_id`|UUID|`NOT NULL`, `REFERENCES auth_users(id)`|Owner of this invoice.|`38f7d540-23fa-497a-8df2-3ab9cbe13da5`|
|`storage_path`|TEXT|`NOT NULL`|Final Supabase Storage path after user confirms.|`invoices/2025/10/31/receipt_002.jpg`|
|`extracted_text`|TEXT|`NOT NULL`|OCR raw text we keep for audit / traceability.|`"Super Despensa Familiar – Q128.50 – 30 Oct"`|
|`created_at`|TIMESTAMPTZ|`DEFAULT now()`|Created timestamp.|`2025-10-30T14:35:00-06:00`|
|`updated_at`|TIMESTAMPTZ|`DEFAULT now()`|Last update.|`2025-10-31T09:40:00-06:00`|

**Business rules:**

- We only INSERT here after the human confirms the OCR preview.
- If the OCR result is unusable (`status = "INVALID_IMAGE"`), nothing is saved: no row in `invoice`, no row in `transaction`, no upload.

**Relationship:**

- 1 ↔ 1 with `transaction` (a transaction created from OCR will reference its invoice via `transaction.invoice_id`).

**Delete rule:**  

When deleting an invoice:

1. All transactions referencing it (`transaction.invoice_id`) must be handled first.
    - If the transaction exists solely because of that invoice (OCR-generated), it must update its `invoice_id` field to null.
2. Only after transactions are handled can the invoice be deleted.
3. The backend must also remove the associated file from Supabase Storage using `storage_path` before deleting the database row.  
    No record or file should remain orphaned.

---

## 💰 Table: `transaction`

| Field                   | Type          | Constraints / Checks                                    | Description                                           | Example                                    |
| :---------------------- | :------------ | :------------------------------------------------------ | :---------------------------------------------------- | :----------------------------------------- |
| `id`                    | UUID (PK)     | `PRIMARY KEY`                                           | Transaction id.                                       | `t-a1e7dd02-98c4-41fa-bdf8-0d7fa1c390ab`   |
| `user_id`               | UUID          | `NOT NULL`, `REFERENCES auth_users(id)`                 | Owner user.                                           | `38f7d540-23fa-497a-8df2-3ab9cbe13da5`     |
| `account_id`            | UUID          | `NOT NULL`, `REFERENCES account(id)`                    | Which account this affects.                           | `a214db42-32b1-4fb2-bbde-37dbce2c0cc4`     |
| `category_id`           | UUID          | `REFERENCES category(id)`, `NOT NULL`                   | Spending/earning category.                            | `c21af3b8-9813-46bb-bce7-347f0f310e00`     |
| `invoice_id`            | UUID          | `REFERENCES invoice(id)`, `NULLABLE`                    | Link to scanned invoice, if any.                      | `inv-b3d9b1f6-aa11-422c-a65a-21b1abacfe43` |
| `flow_type`             | TEXT          | `CHECK (flow_type IN ('income','outcome'))`, `NOT NULL` | Money direction.                                      | `outcome`                                  |
| `amount`                | NUMERIC(12,2) | `NOT NULL`, should be >= 0                              | Monetary amount for this record.                      | `128.50`                                   |
| `date`                  | TIMESTAMPTZ   | `NOT NULL`                                              | Effective financial date (when it "really" happened). | `2025-10-30T14:32:00-06:00`                |
| `description`           | TEXT          | `NULLABLE`                                              | Human-readable label.                                 | `Super Despensa Familiar Zona 11`          |
| `embedding`             | VECTOR        | `NULLABLE`                                              | Semantic vector (pgvector) for AI similarity search.  | `—`                                        |
| `paired_transaction_id` | UUID          | `REFERENCES transaction(id)`, `NULLABLE`                | Used to pair two sides of an internal transfer.       | `t-b3f5da10-3a22-476b-a4b4-e2b75e1d91c8`   |
| `created_at`            | TIMESTAMPTZ   | `DEFAULT now()`                                         | Insert timestamp.                                     | `2025-10-30T14:40:00-06:00`                |
| `updated_at`            | TIMESTAMPTZ   | `DEFAULT now()`                                         | Update timestamp.                                     | `2025-10-31T09:00:00-06:00`                |

**Enum-style values:** `flow_type`

- `income` → money enters the account
- `outcome` → money leaves the account

**Important transfer rule:**

- An internal transfer between two accounts of the same user is modeled as **two** rows:
    - Row A: `flow_type='outcome'` from Account A
    - Row B: `flow_type='income'` into Account B
- Each of the rows must have the global system category identified with the key `transfer` (there's only one in the entire table).

**Semantic search / `embedding`:**

- We store a dense vector of the transaction meaning
- Querying with another vector lets us retrieve “similar” expenses even if the text is different (example: "supermarket" matches "Super Despensa Familiar", "La Torre", etc.)

**Delete rule:**  

When a transaction is deleted:

1. The backend must ensure the record belongs to the authenticated user.
2. If it is part of a paired transfer (`paired_transaction_id`), the paired transaction must have its reference cleared or also be removed.
3. If linked to an invoice, the invoice is **not** automatically deleted; however, if no other transactions reference it, the system may remove the invoice following the `invoice` delete rule.  
    All deletions should maintain accounting integrity and prevent broken links.

---

## 📆 Table: `budget`

| Field          | Type          | Constraints / Checks                                                            | Description                                           | Example                                  |
| :------------- | :------------ | :------------------------------------------------------------------------------ | :---------------------------------------------------- | :--------------------------------------- |
| `id`           | UUID (PK)     | `PRIMARY KEY`                                                                   | Budget id.                                            | `b-9903acde-aa01-4aa2-b0c5-a6bceef80100` |
| `user_id`      | UUID          | `NOT NULL`, `REFERENCES auth_users(id)`                                         | Owner user.                                           | `38f7d540-23fa-497a-8df2-3ab9cbe13da5`   |
| `limit_amount` | NUMERIC(12,2) | `NOT NULL`, amount > 0                                                          | Maximum allowed spend for this budget period.         | `1200.00`                                |
| `frequency`    | TEXT          | `CHECK (frequency IN ('once','daily','weekly','monthly','yearly'))`, `NOT NULL` | Budget repetition cadence.                            | `monthly`                                |
| `interval`     | INTEGER       | `DEFAULT 1`, must be >=1                                                        | How often the budget repeats in units of `frequency`. | `1`                                      |
| `start_date`   | DATE          | `NOT NULL`                                                                      | When this budget starts counting.                     | `2025-10-01`                             |
| `end_date`     | DATE          | `NULLABLE`                                                                      | Hard stop date (for one-time / project budgets).      | `2026-01-01`                             |
| `is_active`    | BOOLEAN       | `DEFAULT true`                                                                  | Whether the budget is currently in effect.            | `true`                                   |
| `created_at`   | TIMESTAMPTZ   | `DEFAULT now()`                                                                 | Created at.                                           | `2025-10-29T10:00:00-06:00`              |
| `updated_at`   | TIMESTAMPTZ   | `DEFAULT now()`                                                                 | Updated at.                                           | `2025-10-31T10:00:00-06:00`              |

**Enum-style values:** `frequency`

- `once` → single-use / project-style budget (e.g. "University Project Materials")
- `daily` → resets every `interval` days
- `weekly` → resets every `interval` weeks
- `monthly` → resets every `interval` months
- `yearly` → resets every `interval` years

**How consumption is calculated:**

- A budget links to categories (via `budget_category`).
- Consumption = sum of all `transaction.amount` where:
    - `transaction.flow_type = 'outcome'`
    - `transaction.category_id` is one of the budget categories
    - `transaction.date` falls in the active window for that budget cycle

**Delete rule:**  

Before deleting a budget:

1. The backend must delete all `budget_category` links tied to it.
2. After those relations are cleared, the budget can be deleted.  
    Deleting a budget never removes any historical transactions; those remain as financial history.

---

## 🪙 Table: `budget_category`

|Field|Type|Constraints / Checks|Description|Example|
|:--|:--|:--|:--|:--|
|`budget_id`|UUID|`NOT NULL`, `REFERENCES budget(id)`|Budget that owns this link.|`b-9903acde-aa01-4aa2-b0c5-a6bceef80100`|
|`category_id`|UUID|`NOT NULL`, `REFERENCES category(id)`|Category included in that budget.|`c21af3b8-9813-46bb-bce7-347f0f310e00`|
|`user_id`|UUID|`NOT NULL`, `REFERENCES auth_users(id)`|Owner user (must match budget.user_id).|`38f7d540-23fa-497a-8df2-3ab9cbe13da5`|
|`created_at`|TIMESTAMPTZ|`DEFAULT now()`|Linked at timestamp.|`2025-10-29T09:00:00-06:00`|
|`updated_at`|TIMESTAMPTZ|`DEFAULT now()`|Updated at.|`2025-10-31T09:00:00-06:00`|

**Integrity note:**

- (`budget_id`, `category_id`) should behave like a composite key to avoid duplicates. The app should prevent inserting the same category twice into the same budget.

**Delete rule:**  

Deleting a `budget_category` record only removes the link between a budget and a category.  
It does not delete the `budget`, the `category`, or any transactions.  
However, if the related `category` or `budget` is deleted, the backend must automatically delete this linking row to maintain referential integrity.

---

## 🔁 Table: `recurring_transaction`

| Field                             | Type          | Constraints / Checks                                                     | Description                                                       | Example                                  |
| :-------------------------------- | :------------ | :----------------------------------------------------------------------- | :---------------------------------------------------------------- | :--------------------------------------- |
| `id`                              | UUID (PK)     | `PRIMARY KEY`                                                            | Recurring rule id.                                                | `r-af204a6a-f79e-42e5-8c87-b84e7b66b3cf` |
| `user_id`                         | UUID          | `NOT NULL`, `REFERENCES auth_users(id)`                                  | Owner user.                                                       | `38f7d540-23fa-497a-8df2-3ab9cbe13da5`   |
| `account_id`                      | UUID          | `NOT NULL`, `REFERENCES account(id)`                                     | Account that will receive or pay.                                 | `a214db42-32b1-4fb2-bbde-37dbce2c0cc4`   |
| `category_id`                     | UUID          | `REFERENCES category(id)`, `NOT NULL`                                    | Optional category to assign to each generated transaction.        | `c21af3b8-9813-46bb-bce7-347f0f310e00`   |
| `flow_type`                       | TEXT          | `CHECK (flow_type IN ('income','outcome'))`, `NOT NULL`                  | Direction of money for each occurrence.                           | `outcome`                                |
| `amount`                          | NUMERIC(12,2) | `NOT NULL`, amount >= 0                                                  | Amount to insert each time this recurs.                           | `450.00`                                 |
| `description`                     | TEXT          | `NOT NULL`                                                               | Text that will become the transaction description.                | `Gym membership subscription`            |
| `paired_recurring_transaction_id` | UUID          | `REFERENCES recurring_transaction(id)`, `NULLABLE`                       | Used to pair two sides of an internal recurring transfer.         | `t-b3f5da10-3a22-476b-a4b4-e2b75e1d91c8` |
| `frequency`                       | TEXT          | `CHECK (frequency IN ('daily','weekly','monthly','yearly'))`, `NOT NULL` | Base recurrence cadence.                                          | `monthly`                                |
| `interval`                        | INTEGER       | `DEFAULT 1`, must be >=1                                                 | How often it repeats in units of `frequency`.                     | `1`                                      |
| `by_weekday`                      | TEXT[]        | `NULLABLE`, only meaningful if `frequency='weekly'`                      | Specific weekdays (e.g. `monday`, `friday`).                      | `{"monday","friday"}`                    |
| `by_monthday`                     | INT[]         | `NULLABLE`, only meaningful if `frequency='monthly'`                     | Specific month days (1–31).                                       | `{1,15}`                                 |
| `start_date`                      | DATE          | `NOT NULL`                                                               | When this rule becomes valid.                                     | `2025-11-01`                             |
| `next_run_date`                   | DATE          | `NOT NULL`                                                               | The next date the system should materialize a real `transaction`. | `2025-12-01`                             |
| `end_date`                        | DATE          | `NULLABLE`                                                               | Stop date. After this, no new transactions are generated.         | `NULL`                                   |
| `is_active`                       | BOOLEAN       | `DEFAULT true`                                                           | Whether the rule is still generating transactions.                | `true`                                   |
| `created_at`                      | TIMESTAMPTZ   | `DEFAULT now()`                                                          | Created at.                                                       | `2025-10-28T10:00:00-06:00`              |
| `updated_at`                      | TIMESTAMPTZ   | `DEFAULT now()`                                                          | Updated at.                                                       | `2025-10-31T10:00:00-06:00`              |

**Enum-style values:** `frequency`

- `daily` → every N days
- `weekly` → every N weeks (and possibly only certain weekdays)
- `monthly` → every N months (and possibly only certain calendar days)
- `yearly` → every N years

**Execution logic:**

- On or after `next_run_date`, backend creates a new row in `transaction` with:
    - same `flow_type`
    - same `amount`
    - same `account_id`
    - (optional) `category_id`
    - `description`
- Then backend advances `next_run_date` according to `frequency` + `interval` (+ weekday/monthday rules when relevant).

**Delete rule:**  

When deleting a recurring rule:

1. The record can be deleted safely without touching past generated transactions.
2. If it has a paired rule (`paired_recurring_transaction_id`), that reference must be deleted together.
3. Deleting the rule stops any future auto-generation of transactions but preserves existing financial records.

---


## 🎯 Table: wishlist

**Purpose:**

`wishlist` represents the user's main purchase goal — what they want to buy or achieve (e.g., “a laptop for Photoshop,” “a good ergonomic chair,” etc.).

**Conceptual keys:**

- Captures the INTENTION and CONTEXT declared by the user.
- This goal can exist without any specific options yet.
- Created in two scenarios:  
    a) The user saves their goal WITHOUT requesting intelligent recommendations.  
    b) The user DID request recommendations, reviewed options suggested by the agent, reached the final screen, and decided to save the goal (whether or not specific offers were selected).
- It can exist with zero associated `wishlist_item` records.

| Field           | Type          | Constraints / Checks                                               | Description                                                                                                                                                | Example                                                       |
| --------------- | ------------- | ------------------------------------------------------------------ | ---------------------------------------------------------------------------------------------------------------------------------------------------------- | ------------------------------------------------------------- |
| id              | UUID (PK)     | `PRIMARY KEY`                                                      | Unique identifier for the goal.                                                                                                                            | wlst-3c12f4f0-9a02-4f8a-9a8d-12ab34cd56ef                     |
| user_id         | UUID          | `NOT NULL`, `REFERENCES auth_users(id)`                            | The user who owns this goal.                                                                                                                               | 38f7d540-23fa-497a-8df2-3ab9cbe13da5                          |
| goal_title      | TEXT          | `NOT NULL`                                                         | The text entered by the user describing what they want. May be natural language (“Laptop that doesn’t overheat and runs Photoshop smoothly”) or technical. | "Laptop Ryzen 7, 16GB RAM, SSD 512GB, 15-inch, no RGB lights" |
| budget_hint     | NUMERIC(12,2) | `NOT NULL`                                                         | Approximate maximum budget the user is willing to spend. Always collected during goal creation flow.                                                       | 7000.00                                                       |
| currency_code   | TEXT          | `NOT NULL`                                                         | ISO currency code used for this goal. Should match the user’s profile currency (e.g., "GTQ").                                                              | GTQ                                                           |
| target_date     | DATE          | `NULLABLE`                                                         | Optional target date for achieving the goal. NULL if not specified. Later used for reminders (“for December 2025”).                                        | 2025-12-20                                                    |
| preferred_store | TEXT          | `NULLABLE`                                                         | User’s declared store preference, e.g., “If possible, from Intelaf,” “Prefer physical store.”                                                              | “Prefer Intelaf Zone 9”                                       |
| user_note       | TEXT          | `NULLABLE`                                                         | User’s personal note with restrictions or desired style, also used by the recommendation agent. E.g., “No gamer RGB lights.”                               | “No RGB lights, minimalist design for university use.”        |
| status          | TEXT          | `CHECK (status IN ('active','purchased','abandoned'))`, `NOT NULL` | Status of the goal: 'active' = still interested, 'purchased' = already achieved, 'abandoned' = no longer interested. Default 'active'.                     | active                                                        |
| created_at      | TIMESTAMPTZ   | `DEFAULT now()`                                                    | Timestamp when the goal was created.                                                                                                                       | 2025-10-31T14:00:00-06:00                                     |
| updated_at      | TIMESTAMPTZ   | `DEFAULT now()`                                                    | Timestamp of the last update.                                                                                                                              | 2025-10-31T14:00:00-06:00                                     |

**Important notes on `wishlist`:**

- Captures what the user WANTS and under what conditions.
- Can exist without any `wishlist_item` (no offers saved yet).
- Does not store store-specific or URL details — those belong to `wishlist_item`.

**Persistence rules / flow:**

**CASE A (user saves their goal without recommendations):**

→ INSERT into wishlist with user_id, goal_title, budget_hint, currency_code, target_date, preferred_store, user_note, status='active'.  
→ No `wishlist_item` rows created.

**CASE B (user requested recommendations but selected none):**

→ Same as CASE A.

**CASE C (user requested recommendations and selected one or more offers):**

→ Create a wishlist row as in CASE A.  
→ Then create one `wishlist_item` row per selected offer.

**CASE D (user cancels before confirmation):**

→ Nothing is inserted into either table (prevents orphan goals).

**Delete rule:**

Deleting a `wishlist` also requires deleting its dependent `wishlist_item` rows first (or rely on ON DELETE CASCADE). After cleanup, the `wishlist` can be safely removed.

---

## 🛍 Table: wishlist_item

**Purpose:**

`wishlist_item` represents a SPECIFIC OPTION found by the Recommendation Agent that the user explicitly decided to save as a candidate for their goal.

**Conceptual keys:**

- Each wishlist can have 0, 1, or many wishlist_items.
- If no offers were selected, the wishlist has 0 items.
- Each wishlist_item exists ONLY when the user explicitly clicked “Save this option.”
- Items are never created automatically.

| Field            | Type          | Constraints / Checks                                    | Description                                                                                                                                | Example                                                                                       |
| ---------------- | ------------- | ------------------------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------ | --------------------------------------------------------------------------------------------- |
| id               | UUID (PK)     | `PRIMARY KEY`                                           | Unique identifier for the saved offer.                                                                                                     | wi-772a8b7d-1292-4ab3-bca1-8e40b7cbebcb                                                       |
| wishlist_id      | UUID          | `NOT NULL`, `REFERENCES wishlist(id) ON DELETE CASCADE` | Parent-child relationship. This item belongs to a specific wishlist.                                                                       | wlst-3c12f4f0-9a02-4f8a-9a8d-12ab34cd56ef                                                     |
| product_title    | TEXT          | `NOT NULL`                                              | Commercial product name (e.g., “HP Envy Ryzen 7 16GB RAM 512GB SSD 15.6”).                                                                 | “HP Envy Ryzen 7 16GB RAM 512GB SSD 15.6”                                                     |
| price_total      | NUMERIC(12,2) | `NOT NULL`                                              | Total store-reported price for the offer. Must match the wishlist.currency_code.                                                           | 6200.00                                                                                       |
| seller_name      | TEXT          | `NOT NULL`                                              | Store or seller name.                                                                                                                      | “ElectroCentro Guatemala”                                                                     |
| url              | TEXT          | `NOT NULL`                                              | Verified URL where the user can view/purchase the offer. The agent must NEVER invent URLs.                                                 | “[https://electrocentro.gt/hp-envy-ryzen7”](https://electrocentro.gt/hp-envy-ryzen7%E2%80%9D) |
| pickup_available | BOOLEAN       | `NOT NULL DEFAULT false`                                | Indicates whether in-store pickup is available (“pickup today”).                                                                           | true                                                                                          |
| warranty_info    | TEXT          | `NOT NULL`                                              | Warranty details (e.g., “HP 12-month warranty”).                                                                                           | “HP 12-month warranty.”                                                                       |
| copy_for_user    | TEXT          | `NOT NULL`                                              | Short descriptive copy for the app UI. Generated by FormatterAgent. Max ~3 sentences, informative tone, no emojis, no subjective promises. | “Recommended for graphic design. Meets Ryzen 7 & 16GB RAM specs. ~Q100 cheaper than others.”  |
| badges           | JSONB         | `NOT NULL DEFAULT '[]'::jsonb`                          | Short badge list (max 3), displayed as UI chips (e.g., [“Cheapest”, “12m Warranty”, “Pickup Today”]).                                      | [“Cheapest”, “12m Warranty”, “Pickup Today”]                                                  |
| created_at       | TIMESTAMPTZ   | `DEFAULT now()`                                         | Timestamp when the item was saved.                                                                                                         | 2025-10-31T14:05:00-06:00                                                                     |
| updated_at       | TIMESTAMPTZ   | `DEFAULT now()`                                         | Last updated timestamp.                                                                                                                    | 2025-10-31T14:05:00-06:00                                                                     |

**Important notes on `wishlist_item`:**

- Does NOT repeat fields like budget_hint, preferred_store, or user_note — those belong to `wishlist`.
- Conceptually: wishlist_item = “a store selling something that meets (roughly) what the user wanted.”

**Relationship `wishlist` ↔ `wishlist_item`:**

- `wishlist` = the user's declared goal.
- `wishlist_item` = the specific saved offers.
- One wishlist → many wishlist_items.
- Valid for a wishlist to exist with no items.
- Valid for a wishlist to have multiple items (e.g., 2–3 store options for comparison).

**Delete rule:**

When a `wishlist_item` is requested to be deleted, the backend service must follow these steps:

1. Ensure that the `wishlist_item` belongs to a `wishlist` owned by the authenticated user.  
   This prevents users from deleting saved offers that belong to other users.
2. Deleting a `wishlist_item` simply removes that specific offer from the user’s goal list.
   It does **not** affect the parent `wishlist` record or any other `wishlist_item` under the same goal.
3. The parent `wishlist` remains active and unaffected, even if all its items are deleted.  
   A `wishlist` with zero `wishlist_item` rows is still valid and may later receive new items.
4.  If the parent `wishlist` is deleted, all its associated `wishlist_item` rows are automatically removed due to the **`ON DELETE CASCADE`** foreign key constraint on `wishlist_item.wishlist_id`.
5. The Recommendation Agent must never trigger automatic deletions of `wishlist_item` entries unless explicitly requested by the user (e.g., “Remove this saved offer”).

---

# 📘 Appendices

## A. Global Relationships & Derived Logic

- `auth_users` 1–1 `profile`
- `auth_users` 1–N `account`, `transaction`, `budget`, `wishlist_item`, `recurring_transaction`, `invoice`, personal `category`
- `account` 1–N `transaction`, `recurring_transaction`
- `budget` N–M `category` through `budget_category`
- `invoice` 1–1 `transaction`
- `transaction` self-joins via `paired_transaction_id` to model internal transfers (outcome in one account ↔ income in another)
- `recurring_transaction` self-joins via `paired_recurring_transaction_id` to model internal recurring transfers (outcome in one account ↔ income in another)

**Derived balance rule:**

- We never store running balance per account
- Balance is derived from `transaction.amount` grouped by `account_id` and `flow_type`

---

## B. OCR Flow ("confirm-then-persist")

1. User snaps or uploads an image of a receipt.
2. Backend (InvoiceAgent) runs OCR and returns a draft JSON (`status = "DRAFT"`) with:
    - `store_name`, `purchase_datetime`, `total_amount`, `currency`, `items[]`, and a `category_suggestion`.
3. User edits/approves in the frontend.
4. Frontend sends `/invoices/commit` with final corrected data.
5. Backend:
    - uploads the image into storage
    - inserts `invoice`
    - inserts `transaction` linked to that invoice
6. If the OCR result is unusable, InvoiceAgent returns `status = "INVALID_IMAGE"` and NO rows are persisted.

**Why:**

- Protects user trust ("we won't save anything without you")
- Keeps the database clean (no garbage invoices / blurry receipts)

---

## C. Recurring Transactions & Budgets

**Recurring generation:**

- Each row in `recurring_transaction` is an automation contract
- When `next_run_date <= today` AND `is_active = true` AND (no `end_date` reached):
    - Create a `transaction`
    - Set its `flow_type`, `amount`, `account_id`, `category_id`, `description`, `date = now()`
    - Advance `next_run_date`

**Budgets:**

- A `budget` represents a spending cap over time for one or more categories
- Categories are attached via `budget_category`
- Usage is calculated from `transaction` rows:
    - Only `flow_type = 'outcome'`
    - Category belongs to this budget
    - Transaction date falls into the active repetition window (`start_date`, `frequency`, `interval`, current cycle)

**`frequency` semantics recap:**

- For `budget.frequency`: `'once','daily','weekly','monthly','yearly'`
- For `recurring_transaction.frequency`: `'daily','weekly','monthly','yearly'`

---

## D. Semantic Search with `embedding`

**Field:** `transaction.embedding` (VECTOR, nullable)

**Purpose:**

- Store an AI-generated vector representing the meaning of the purchase.
- Allow semantic queries like: "show all grocery-like expenses" even if the text doesn't literally say "grocery".

**Example query scenario:**

- User searches "supermarket"
- We embed that query
- We run cosine / inner product similarity in Postgres against `transaction.embedding`
- We retrieve rows with descriptions like:
    - `Super Despensa Familiar Zona 11`
    - `Walmart Guatemala`
    - `La Torre` (local grocery)  

**Why this matters:**

- Better personal spend insights for the user
- Better category suggestions and analytics for budgeting

---

## E. RLS (Row-Level Security)

**Core guarantees:**

- Every table that has a `user_id` enforces `user_id = auth.uid()` on `SELECT`, `INSERT`, `UPDATE`, `DELETE`.
- A user cannot read or mutate another user's financial data.
- System rows (like global categories with `user_id IS NULL`) are readable by all users, but are not writable by normal users.
- For `transaction`, RLS should also validate that:
    - The `account_id` belongs to the same `auth.uid()`
    - The `category_id` (if provided) also belongs to that same user OR is a global category (`user_id IS NULL`)

**Practical effect:**

- Agents and frontend can safely request "all my transactions" without worrying about leakage across users.
- The Recommendation agent can read global categories (system defaults), but not another person's private categories.