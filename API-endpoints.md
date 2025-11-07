# Kashi Finances — API Endpoints
  
> This canvas lists every public REST endpoint the mobile app (Flutter frontend) will call. It also describes purpose, request, response shape at a high level, and important rules. Internal agent-to-agent calls are **not** exposed directly to the app.
> Base URL to define
> All endpoints require an authenticated user unless explicitly marked as `public`.

---

## 0. Authentication Flow (VERY IMPORTANT)

All endpoints in this document assume the mobile app includes a valid access token on every request:

```http

Authorization: Bearer <access_token>

```

How the backend knows "who is calling":

1. The backend verifies the token signature (Supabase Auth).
2. The backend extracts the authenticated `user_id` from that token (this is equivalent to `auth.uid()` under RLS).
3. The backend uses that `user_id` to:

* Fetch the user's profile from the `profile` table.
* Enforce Row-Level Security so the caller only sees/updates rows where `user_id` = them.
  
This means:

* The client does **not** need to send `user_id` in most requests. If it sends one anyway, the backend will still override/validate it against the token.
* If the token is missing/invalid/expired, the backend answers `401 Unauthorized`.
* `GET /auth/me` does **not** need a body.

---

## 1. Auth & Profile

These endpoints cover login context for the app and the basic user profile data needed by agents.

### `GET /auth/me`

Purpose: return the authenticated user's core identity for the session.

* Input: header `Authorization: Bearer <access_token>`. No body.
* Backend flow:
	1. Validate token.
	2. Extract `user_id`.
	3. Query `profile` table by that `user_id`.
* Returns:
	* `user_id`
	* `email`
	* `profile` (first_name, last_name, avatar_url, country, currency_preference, locale)


Use in frontend:
* On app boot, call this once to hydrate global session state.
* Also confirms token is still valid.

---

### `GET /profile`

**Purpose:** Retrieve the authenticated user's profile.

**Request:** No body. Authorization required (Bearer token).

**Behavior:**
- Returns the user's profile data including personal info and preferences
- Only accessible to the profile owner (RLS enforced)
- Returns 404 if profile doesn't exist

**Response:**
```json
{
  "user_id": "38f7d540-23fa-497a-8df2-3ab9cbe13da5",
  "first_name": "Samuel",
  "last_name": "Marroquín",
  "avatar_url": "https://storage.kashi.app/avatars/u1.png",
  "currency_preference": "GTQ",
  "locale": "es",
  "country": "GT",
  "created_at": "2025-10-31T12:00:00-06:00",
  "updated_at": "2025-10-31T12:00:00-06:00"
}
```

**Status Codes:**
* `200 OK` - Profile retrieved successfully
* `401 UNAUTHORIZED` - Missing or invalid authentication token
* `404 NOT FOUND` - Profile not found for this user
* `500 INTERNAL SERVER ERROR` - Database query error

**Security:**
* RLS ensures users only see their own profile
* Profile contains localization data used by RecommendationCoordinatorAgent

---

### `PATCH /profile`

**Purpose:** Update the authenticated user's profile.

**Request:** JSON body validated by `ProfileUpdateRequest`. Authorization required (Bearer token).

**Request Body (all fields optional, at least one required):**
```json
{
  "first_name": "Samuel",
  "last_name": "Marroquín",
  "avatar_url": "https://storage.kashi.app/avatars/new-avatar.png",
  "currency_preference": "USD",
  "locale": "es",
  "country": "GT"
}
```

**Behavior:**
- Accepts partial updates (only provided fields are updated)
- Returns the complete updated profile
- Validates field constraints (e.g., country must be 2-char ISO code)

**Response:**
```json
{
  "status": "UPDATED",
  "profile": {
    "user_id": "38f7d540-23fa-497a-8df2-3ab9cbe13da5",
    "first_name": "Samuel",
    "last_name": "Marroquín",
    "avatar_url": "https://storage.kashi.app/avatars/new-avatar.png",
    "currency_preference": "USD",
    "locale": "es-GT",
    "country": "GT",
    "created_at": "2025-10-31T12:00:00-06:00",
    "updated_at": "2025-11-05T10:30:00-06:00"
  },
  "message": "Profile updated successfully"
}
```

**Status Codes:**
* `200 OK` - Profile updated successfully
* `400 BAD REQUEST` - Invalid request data or no fields provided
* `401 UNAUTHORIZED` - Missing or invalid authentication token
* `404 NOT FOUND` - Profile not found for this user
* `500 INTERNAL SERVER ERROR` - Database update error

**Security:**
* Only the profile owner can update their profile
* RLS enforces user_id = auth.uid()

**Notes:**
* `country` is used by agents for localized recommendations
* `currency_preference` sets default currency for the user's financial data
* At least one field must be provided for a valid update

---

### `DELETE /profile`

**Purpose:** Delete (anonymize) the authenticated user's profile.

**Request:** No body. Authorization required (Bearer token).

**Behavior:**
- **IMPORTANT:** Profile is NOT physically deleted (follows DB documentation delete rule)
- Instead, personal fields are cleared/anonymized:
  - `first_name` → set to "Deleted User"
  - `last_name` → set to null
  - `avatar_url` → set to null
- `country` and `currency_preference` are **kept** for system consistency
- The profile row remains to support localization for agents (e.g., `getUserCountry`)

**Response:**
```json
{
  "status": "DELETED",
  "message": "Profile deleted successfully"
}
```

**Status Codes:**
* `200 OK` - Profile anonymized successfully
* `401 UNAUTHORIZED` - Missing or invalid authentication token
* `404 NOT FOUND` - Profile not found for this user
* `500 INTERNAL SERVER ERROR` - Database update error

**Security:**
* Only the profile owner can delete their profile
* RLS enforces user_id = auth.uid()

**Important Delete Rule:**
* Profiles are not physically deleted while the user exists in `auth_users`
* The backend performs an UPDATE instead, clearing/anonymizing personal fields
* The record must remain because it provides localization data to other agents
* This is an anonymization operation, not a true deletion

---

## 2. Accounts & Categories

Money lives in accounts. Spending is labeled with categories.

### `GET /accounts`

**Purpose:** List all financial accounts for the authenticated user.

**Request:** No body. Authorization required (Bearer token).

**Query Parameters:**
- `limit` (optional, integer, default=50): Maximum number of accounts to return
- `offset` (optional, integer, default=0): Number of accounts to skip for pagination

**Behavior:**
- Returns all accounts owned by the authenticated user
- Each account includes computed balance (derived from transactions)
- Balance is never stored in DB; always calculated on read
- Results are ordered by creation date (newest first)
- RLS automatically filters to user's accounts only

**Response:**
```json
{
  "accounts": [
    {
      "id": "account-uuid-123",
      "user_id": "user-uuid-456",
      "name": "Main Checking",
      "type": "bank",
      "currency": "GTQ",
      "created_at": "2025-10-31T10:00:00Z",
      "updated_at": "2025-10-31T10:00:00Z"
    }
  ],
  "count": 1,
  "limit": 50,
  "offset": 0
}
```

**Account Types (Literal enum):**
- `cash` - Physical cash
- `bank` - Bank account (checking/savings)
- `credit_card` - Credit card account
- `loan` - Loan account
- `remittance` - Remittance/transfer account
- `crypto` - Cryptocurrency wallet
- `investment` - Investment account

**Status Codes:**
- `200 OK` - Accounts retrieved successfully
- `401 UNAUTHORIZED` - Missing or invalid authentication token
- `500 INTERNAL SERVER ERROR` - Database query error

**Security:**
- RLS enforces `user_id = auth.uid()` automatically
- User can only see their own accounts

---

### `POST /accounts`

**Purpose:** Create a new financial account.

**Request:** JSON body with account details. Authorization required (Bearer token).

**Request Body:**
```json
{
  "name": "Main Checking",
  "type": "bank",
  "currency": "GTQ"
}
```

**Required Fields:**
- `name` (string, min_length=1): Account name
- `type` (AccountType enum): One of the account types listed above
- `currency` (string, min_length=3, max_length=3): ISO currency code (e.g., "GTQ", "USD")

**Behavior:**
- Creates a new account owned by the authenticated user
- `user_id` is set from auth token (client cannot override)
- Account starts with zero balance (balance derived from transactions)
- All fields are validated by Pydantic before persistence

**Response:**
```json
{
  "status": "CREATED",
  "account": {
    "id": "account-uuid-123",
    "user_id": "user-uuid-456",
    "name": "Main Checking",
    "type": "bank",
    "currency": "GTQ",
    "created_at": "2025-11-05T10:00:00Z",
    "updated_at": "2025-11-05T10:00:00Z"
  },
  "message": "Account created successfully"
}
```

**Status Codes:**
- `201 CREATED` - Account created successfully
- `400 BAD REQUEST` - Invalid request data
- `401 UNAUTHORIZED` - Missing or invalid authentication token
- `422 UNPROCESSABLE ENTITY` - Validation error (invalid type, currency, etc.)
- `500 INTERNAL SERVER ERROR` - Database error

**Security:**
- RLS automatically sets `user_id = auth.uid()` on insert
- User cannot create accounts for other users

---

### `GET /accounts/{account_id}`

**Purpose:** Retrieve details of a specific account.

**Request:** No body. Authorization required (Bearer token).

**Path Parameters:**
- `account_id` (string, UUID): The account ID to retrieve

**Behavior:**
- Returns the account if it exists and belongs to the authenticated user
- Returns 404 if account doesn't exist or doesn't belong to user (RLS enforcement)
- Account balance is computed from transactions (not stored)

**Response:**
```json
{
  "id": "account-uuid-123",
  "user_id": "user-uuid-456",
  "name": "Main Checking",
  "type": "bank",
  "currency": "GTQ",
  "created_at": "2025-10-31T10:00:00Z",
  "updated_at": "2025-10-31T10:00:00Z"
}
```

**Status Codes:**
- `200 OK` - Account retrieved successfully
- `401 UNAUTHORIZED` - Missing or invalid authentication token
- `404 NOT FOUND` - Account not found or not accessible by user
- `500 INTERNAL SERVER ERROR` - Database query error

**Security:**
- RLS ensures user can only access their own accounts

---

### `PATCH /accounts/{account_id}`

**Purpose:** Update an existing account (rename, change type, change currency).

**Request:** JSON body with fields to update. Authorization required (Bearer token).

**Path Parameters:**
- `account_id` (string, UUID): The account ID to update

**Request Body (all fields optional, but at least one required):**
```json
{
  "name": "Updated Account Name",
  "type": "cash",
  "currency": "USD"
}
```

**Optional Fields:**
- `name` (string, min_length=1): New account name
- `type` (AccountType enum): New account type
- `currency` (string, min_length=3, max_length=3): New currency code

**Behavior:**
- Updates only the fields provided in the request
- At least one field must be provided (returns 400 if body is empty)
- Only the account owner can update (RLS enforced)
- Returns 404 if account doesn't exist or doesn't belong to user

**Response:**
```json
{
  "status": "UPDATED",
  "account": {
    "id": "account-uuid-123",
    "user_id": "user-uuid-456",
    "name": "Updated Account Name",
    "type": "cash",
    "currency": "USD",
    "created_at": "2025-10-31T10:00:00Z",
    "updated_at": "2025-11-05T14:30:00Z"
  },
  "message": "Account updated successfully"
}
```

**Status Codes:**
- `200 OK` - Account updated successfully
- `400 BAD REQUEST` - No fields provided for update
- `401 UNAUTHORIZED` - Missing or invalid authentication token
- `404 NOT FOUND` - Account not found or not accessible by user
- `422 UNPROCESSABLE ENTITY` - Validation error
- `500 INTERNAL SERVER ERROR` - Database error

**Security:**
- RLS ensures user can only update their own accounts

---

### `DELETE /accounts/{account_id}`

**Purpose:** Delete an account and handle associated transactions.

**Request:** JSON body with deletion strategy. Authorization required (Bearer token).

**Path Parameters:**
- `account_id` (string, UUID): The account ID to delete

**Request Body:**

Note: The request envelope is consistent for all strategies — `target_account_id` must be present in the JSON body.

Examples:
```json
{
  "strategy": "reassign",
  "target_account_id": "target-account-uuid"
}
```
```json
{
  "strategy": "delete_transactions",
  "target_account_id": null
}
```

**Required Fields:**
- `strategy` (Literal["reassign", "delete_transactions"]): Deletion strategy to use

**target_account_id behavior:**
- Present in the request body for all strategies.
- If `strategy == "reassign"`: `target_account_id` MUST be a non-null UUID that belongs to the same user.
- If `strategy == "delete_transactions"`: `target_account_id` MUST be explicitly `null` to signal intentional absence.

**Deletion Strategies:**

1. **`strategy = "reassign"`** (RECOMMENDED):
   - Reassigns all transactions from the deleted account to `target_account_id`
   - Validates that `target_account_id` exists and belongs to same user
   - Updates all transactions: `UPDATE transaction SET account_id = target_account_id WHERE account_id = account_id_to_delete`
   - Then deletes the account
   - Preserves transaction history
   - Returns count of transactions reassigned

2. **`strategy = "delete_transactions"`**:
   - **WARNING:** This permanently deletes all transactions associated with the account
   - First clears `paired_transaction_id` references (to avoid FK violations)
   - Then deletes all transactions: `DELETE FROM transaction WHERE account_id = account_id_to_delete`
   - Then deletes the account
   - Returns count of transactions deleted
   - Cannot be undone

**Behavior:**
- Only the account owner can delete (RLS enforced)
- Returns 404 if account doesn't exist or doesn't belong to user
- Returns 400 if `target_account_id` is missing for "reassign" strategy
- Returns 400 if `target_account_id` doesn't exist or doesn't belong to user

**Response (reassign strategy):**
```json
{
  "status": "DELETED",
  "account_id": "account-uuid-123",
  "transactions_affected": 5,
  "message": "Account deleted successfully. 5 transactions reassigned to target account."
}
```

**Response (delete_transactions strategy):**
```json
{
  "status": "DELETED",
  "account_id": "account-uuid-123",
  "transactions_affected": 3,
  "message": "Account deleted successfully. 3 transactions deleted."
}
```

**Status Codes:**
- `200 OK` - Account deleted successfully
- `400 BAD REQUEST` - Invalid strategy or missing target_account_id for reassign
- `401 UNAUTHORIZED` - Missing or invalid authentication token
- `404 NOT FOUND` - Account or target account not found
- `500 INTERNAL SERVER ERROR` - Database error

**Security:**
- RLS ensures user can only delete their own accounts
- Target account (for reassign) must also belong to same user
- All DB operations happen within a transaction (atomic)

**Important Notes:**
- Frontend should warn user about data loss when using `delete_transactions` strategy
- `reassign` strategy is recommended to preserve financial history
- Balance of target account (for reassign) will be updated automatically based on reassigned transactions

---

### `GET /categories`

**Purpose:** List all categories available to the authenticated user.

**Request:** No body. Authorization required (Bearer token).

**Query Parameters:**
- `limit` (optional, integer, default=100): Maximum number of categories to return
- `offset` (optional, integer, default=0): Number of categories to skip for pagination

**Behavior:**
- Returns system categories (user_id=NULL, read-only, with `key` field)
- Returns user's personal categories (user_id=authenticated user, `key` is NULL)
- System categories are visible to all users but cannot be modified or deleted
- User categories are only visible to the owner
- Results are ordered by name alphabetically
- Used by: invoice flow (category dropdown), manual transaction entry, budgets

**System Categories (read-only, user_id=NULL):**
- `initial_balance` — Opening balance seeding an account
- `balance_update_income` — Manual positive adjustment
- `balance_update_outcome` — Manual negative adjustment
- `from_recurrent_transaction` — Money auto-logged from recurring schedule
- `transfer` — Assigned when transaction is used as transfer part
- `general` — For no-assigned category transactions (default fallback)

**Response:**
```json
{
  "categories": [
    {
      "id": "category-uuid-123",
      "user_id": null,
      "key": "general",
      "name": "General",
      "flow_type": "outcome",
      "created_at": "2025-10-01T00:00:00Z",
      "updated_at": "2025-10-01T00:00:00Z"
    },
    {
      "id": "category-uuid-456",
      "user_id": "user-uuid-789",
      "key": null,
      "name": "Groceries",
      "flow_type": "outcome",
      "created_at": "2025-11-01T10:00:00Z",
      "updated_at": "2025-11-01T10:00:00Z"
    }
  ],
  "count": 2,
  "limit": 100,
  "offset": 0
}
```

**Flow Types:**
- `income` — For income categories
- `outcome` — For expense categories

**Status Codes:**
- `200 OK` - Categories retrieved successfully
- `401 UNAUTHORIZED` - Missing or invalid authentication token
- `500 INTERNAL SERVER ERROR` - Database query error

**Security:**
- System categories are read-only for all users
- User categories filtered by RLS to owner only
- User cannot see other users' personal categories

---

### `POST /categories`

**Purpose:** Create a new personal category for the authenticated user.

**Request:** JSON body with category details. Authorization required (Bearer token).

**Request Body:**
```json
{
  "name": "Groceries",
  "flow_type": "outcome"
}
```

**Required Fields:**
- `name` (string, min_length=1, max_length=100): Category display name
- `flow_type` (Literal["income", "outcome"]): Money direction

**Behavior:**
- Creates a user category (user_id = authenticated user, key = NULL)
- System categories cannot be created via API (those are pre-defined)
- All fields are validated by Pydantic before persistence
- Typical trigger: user accepts an InvoiceAgent suggestion `match_type = "NEW_PROPOSED"`

**Response:**
```json
{
  "status": "CREATED",
  "category": {
    "id": "category-uuid-456",
    "user_id": "user-uuid-789",
    "key": null,
    "name": "Groceries",
    "flow_type": "outcome",
    "created_at": "2025-11-05T10:00:00Z",
    "updated_at": "2025-11-05T10:00:00Z"
  },
  "message": "Category created successfully"
}
```

**Status Codes:**
- `201 CREATED` - Category created successfully
- `400 BAD REQUEST` - Invalid request data
- `401 UNAUTHORIZED` - Missing or invalid authentication token
- `422 UNPROCESSABLE ENTITY` - Validation error (invalid flow_type, empty name, etc.)
- `500 INTERNAL SERVER ERROR` - Database error

**Security:**
- RLS automatically sets `user_id = auth.uid()` on insert
- User cannot create categories for other users
- System categories (key NOT NULL) cannot be created

---

### `GET /categories/{category_id}`

**Purpose:** Retrieve details of a specific category.

**Request:** No body. Authorization required (Bearer token).

**Path Parameters:**
- `category_id` (string, UUID): The category ID to retrieve

**Behavior:**
- Returns the category if it exists and is accessible
- User can access system categories (read-only)
- User can access their own personal categories
- Returns 404 if category doesn't exist or doesn't belong to user

**Response:**
```json
{
  "id": "category-uuid-123",
  "user_id": null,
  "key": "general",
  "name": "General",
  "flow_type": "outcome",
  "created_at": "2025-10-01T00:00:00Z",
  "updated_at": "2025-10-01T00:00:00Z"
}
```

**Status Codes:**
- `200 OK` - Category retrieved successfully
- `401 UNAUTHORIZED` - Missing or invalid authentication token
- `404 NOT FOUND` - Category not found or not accessible by user
- `500 INTERNAL SERVER ERROR` - Database query error

**Security:**
- User can view system categories (read-only)
- User can view their own categories
- User cannot view other users' categories

---

### `PATCH /categories/{category_id}`

**Purpose:** Update an existing user category (name only).

**Request:** JSON body with fields to update. Authorization required (Bearer token).

**Path Parameters:**
- `category_id` (string, UUID): The category ID to update

**Request Body:**
```json
{
  "name": "Supermarket"
}
```

**Optional Fields:**
- `name` (string, min_length=1, max_length=100): New category name

**Immutable Fields:**
- `flow_type` — NOT editable. Changing flow_type would affect all transactions in that category, impacting balances and dependent data structures. Users must create a new category with the correct flow_type instead.

**Behavior:**
- Updates only the fields provided in the request
- At least one field must be provided (returns 400 if name is not provided)
- Only the category owner can update (RLS enforced)
- System categories CANNOT be updated (returns 400)
- Returns 404 if category doesn't exist or doesn't belong to user

**Response:**
```json
{
  "status": "UPDATED",
  "category": {
    "id": "category-uuid-456",
    "user_id": "user-uuid-789",
    "key": null,
    "name": "Supermarket",
    "flow_type": "income",
    "created_at": "2025-11-01T10:00:00Z",
    "updated_at": "2025-11-05T14:30:00Z"
  },
  "message": "Category updated successfully"
}
```

**Status Codes:**
- `200 OK` - Category updated successfully
- `400 BAD REQUEST` - No fields provided OR trying to update system category
- `401 UNAUTHORIZED` - Missing or invalid authentication token
- `404 NOT FOUND` - Category not found or not accessible by user
- `422 UNPROCESSABLE ENTITY` - Validation error
- `500 INTERNAL SERVER ERROR` - Database error

**Security:**
- RLS ensures user can only update their own categories
- System categories are protected from modification

---

### `DELETE /categories/{category_id}`

**Purpose:** Delete a user category following DB deletion rules.

**Request:** No body. Authorization required (Bearer token).

**Path Parameters:**
- `category_id` (string, UUID): The category ID to delete

**Deletion Rules:**
1. **Reassign all transactions** using this category to the system `general` category
2. **Remove all budget_category links** referencing this category
3. **Delete the category** from the database
4. **System categories CANNOT be deleted** (returns 400)

**Behavior:**
- Only the category owner can delete (RLS enforced)
- System categories are protected from deletion
- Returns count of transactions reassigned and budget links removed
- All DB operations happen within a transaction (atomic)
- Returns 404 if category doesn't exist or doesn't belong to user

**Response:**
```json
{
  "status": "DELETED",
  "category_id": "category-uuid-456",
  "transactions_reassigned": 15,
  "budget_links_removed": 2,
  "message": "Category deleted successfully. 15 transaction(s) reassigned to 'general', 2 budget link(s) removed."
}
```

**Status Codes:**
- `200 OK` - Category deleted successfully
- `400 BAD REQUEST` - Trying to delete system category
- `401 UNAUTHORIZED` - Missing or invalid authentication token
- `404 NOT FOUND` - Category not found or not accessible by user
- `500 INTERNAL SERVER ERROR` - Database error

**Security:**
- RLS ensures user can only delete their own categories
- System categories are completely protected
- All DB operations are transactional (if any step fails, nothing is deleted)

**Important Notes:**
- Frontend should warn user that transactions will be reassigned to "General" category
- Budget links are removed automatically (budgets themselves are NOT deleted)
- Deletion is permanent and cannot be undone
- The `general` system category is used as the reassignment target
  
---

## 3. Transactions (manual + automatically generated from invoices)

A `transaction` is one money movement (income or outcome). It may optionally be linked to an `invoice` when created from the invoice OCR workflow.

### Shape of a transaction object

```json
{
	"id": "...",
	"user_id": "...",
	"account_id": "...",
	"category_id": "...",
	"invoice_id": "..." | null,
	"flow_type": "income" | "outcome",
	"amount": 128.50,
	"date": "2025-10-30T14:32:00-06:00",
	"description": "Super Despensa Familiar Zona 11",
	"paired_transaction_id": "..." | null,
	"created_at": "2025-11-03T10:15:00Z",
	"updated_at": "2025-11-03T10:15:00Z"
}
```

**Notes:**
* `invoice_id` is set when the transaction was automatically created from an invoice commit.
* `paired_transaction_id` is set if this transaction is part of an internal transfer between two of the user's own accounts. The frontend should NOT count internal transfers as "spending" or "income" in insights.

### `POST /transactions`

**Purpose:** Insert a transaction manually (not from OCR, not from an automation rule).

**Request Body:**
```json
{
	"account_id": "...",
	"category_id": "...",
	"flow_type": "income" | "outcome",
	"amount": 128.50,
	"date": "2025-10-30T14:32:00-06:00",
	"description": "Super Despensa Familiar"
}
```

**Notes:**
* `category_id` is required. If the user doesn't pick one in UI, the app should send the default "General" category ID.
* Authorization required (Bearer token).

**Response:** Created transaction object with full details including `transaction_id`, `created_at`, etc.

**Status Code:** `201 CREATED`

---

### `GET /transactions`

**Purpose:** Fetch user's transactions with optional filters and pagination.

**Query Params (all optional):**
* `limit` (int, default 50, max 100) - Maximum number of transactions to return
* `offset` (int, default 0) - Number of transactions to skip for pagination
* `account_id` (UUID) - Filter by specific account
* `category_id` (UUID) - Filter by specific category
* `flow_type` (string: "income" or "outcome") - Filter by transaction type
* `from_date` (ISO-8601 string) - Filter by start date
* `to_date` (ISO-8601 string) - Filter by end date

**Response:**
```json
{
	"transactions": [
		{
			"id": "...",
			"user_id": "...",
			"account_id": "...",
			"category_id": "...",
			"invoice_id": "..." | null,
			"flow_type": "outcome",
			"amount": 128.50,
			"date": "2025-10-30T14:32:00-06:00",
			"description": "Super Despensa Familiar",
			"paired_transaction_id": null,
			"created_at": "2025-11-03T10:15:00Z",
			"updated_at": "2025-11-03T10:15:00Z"
		}
	],
	"count": 1,
	"limit": 50,
	"offset": 0
}
```

**Security:**
* Authorization required.
* RLS ensures users only see their own transactions.
* Results ordered by date descending (newest first).

**Status Code:** `200 OK`

---

### `GET /transactions/{transaction_id}`

**Purpose:** Retrieve a single transaction's details.

**Path Params:**
* `transaction_id` (UUID) - Transaction identifier

**Response:** Single transaction object (same shape as above)

**Status Codes:**
* `200 OK` - Transaction found and returned
* `404 NOT FOUND` - Transaction doesn't exist or not accessible by user

**Security:**
* Authorization required.
* RLS ensures users can only access their own transactions.

---

### `PATCH /transactions/{transaction_id}`

**Purpose:** Edit a transaction (amount, description, category, account reassignment, etc.).

**Path Params:**
* `transaction_id` (UUID) - Transaction identifier

**Request Body (all fields optional, at least one required):**
```json
{
	"account_id": "...",
	"category_id": "...",
	"flow_type": "income" | "outcome",
	"amount": 150.00,
	"date": "2025-10-31T10:00:00-06:00",
	"description": "Updated description"
}
```

**Response:**
```json
{
	"status": "UPDATED",
	"transaction_id": "...",
	"transaction": {
		/* full updated transaction object */
	},
	"message": "Transaction updated successfully"
}
```

**Status Codes:**
* `200 OK` - Transaction updated successfully
* `404 NOT FOUND` - Transaction doesn't exist or not accessible by user
* `400 BAD REQUEST` - Invalid data (e.g., invalid flow_type, negative amount)

**Security:**
* Authorization required.
* Only the transaction owner can update their transactions.

---

### `DELETE /transactions/{transaction_id}` (Updated for Transfers)

**Purpose:** Delete a transaction. If part of a transfer, deletes both sides automatically.

**Request:** Authorization required (Bearer token).

**Behavior:**
1. Fetches transaction by ID
2. Checks if `paired_transaction_id` is not NULL
3. If paired (transfer):
   - Deletes BOTH transactions (symmetric deletion)
   - Returns success with paired info
4. If not paired:
   - Deletes single transaction normally

**Response (Transfer):**
```json
{
  "status": "DELETED",
  "transaction_id": "txn-uuid-1",
  "paired_transaction_deleted": "txn-uuid-2",
  "message": "Transfer deleted (both sides removed)"
}
```

**Response (Normal Transaction):**
```json
{
  "status": "DELETED",
  "transaction_id": "txn-uuid",
  "message": "Transaction deleted successfully"
}
```

**Status Codes:**
* `200 OK` - Transaction(s) deleted successfully
* `401 UNAUTHORIZED` - Missing or invalid authentication token
* `404 NOT FOUND` - Transaction not found or not accessible
* `500 INTERNAL SERVER ERROR` - Database error

**Security:**
* RLS enforces user can only delete own transactions
* Paired deletion happens atomically (both or neither)

**Important Notes:**
- Deleting one side of a transfer automatically deletes the other
- Invoice-linked transactions: Invoice is NOT deleted (invoice persistence separate)
- Past history: Deletion removes records permanently (no soft delete)

---

## 4. Invoice Flow (OCR → preview → commit → CRUD)

The invoice endpoints provide an OCR preview workflow plus limited CRUD over persisted invoice rows.

**IMPORTANT IMMUTABILITY RULE:**
* Invoices **cannot be updated** after being committed.
* Only two operations are permitted on committed invoices: **view** and **delete**.
* If a user needs to correct invoice data, they must delete the incorrect invoice and create a new one.
* This enforces data integrity and audit trail consistency.

**Implementation notes:**
- The canonical invoice storage format is a single `extracted_text` text column that must follow a strict template (handled by the service layer).
- Receipt images are uploaded to Supabase Storage. The service stores a `storage_path` (the storage object identifier) in the invoice row.
- Row-Level Security (RLS) is enforced by using an authenticated Supabase client for all DB operations. All invoice endpoints require a valid bearer token.
- `/invoices/ocr` processes the image and returns a DRAFT preview only — it does NOT upload to storage or persist an `invoice` record.
- `/invoices/commit` uploads the image to storage, persists an invoice row **and automatically creates a linked transaction** in the `transaction` table.

### `POST /invoices/ocr`

**Purpose:** Accept a receipt image and return a preview/draft extraction produced by the InvoiceAgent.

**Request:** multipart form-data with `image` (binary). Authorization required.

**Behavior:**
- Validates that the uploaded file is an image and within size limits (max 5MB).
- Calls the `InvoiceAgent` (single-shot multimodal vision workflow using Gemini) with the image and user profile context to obtain a structured extraction.
- **NOTE: The image is NOT uploaded to Supabase Storage during this phase** — it's only processed in memory for the draft.
- Returns either:
	- `status = "INVALID_IMAGE"` with a human-friendly `reason` when the agent cannot extract a receipt, or
	- `status = "DRAFT"` with structured fields (store_name, transaction_time, total_amount, currency, items[], and category suggestion).

**Security / UX rules:**
* This endpoint never inserts rows into `invoice` or `transaction` tables. It is preview-only.
* The image is NOT persisted to storage during this step.
* The image ID/receipt reference is NOT returned in the draft (storage happens only at commit time).
* The frontend must save the image in memory and send it again when calling `/invoices/commit`.
* The frontend must call `/invoices/commit` to actually persist the invoice and upload the image.

**Example 1: Successful draft response with EXISTING category match:**

```json
{
	"status": "DRAFT",
	"store_name": "Super Despensa Familiar Zona 11",
	"transaction_time": "2025-10-30T14:32:00-06:00",
	"total_amount": 128.50,
	"currency": "GTQ",
	"items": [
		{"description": "Leche 1L", "quantity": 2, "total_price": 35.00},
		{"description": "Pan molde", "quantity": 1, "total_price": 22.50}
	],
	"category_suggestion": {
		"match_type": "EXISTING",
		"category_id": "uuid-de-supermercado",
		"category_name": "Supermercado",
		"proposed_name": null
	}
}
```

**Example 2: Successful draft with NEW_PROPOSED category:**

```json
{
	"status": "DRAFT",
	"store_name": "Pet Zone",
	"transaction_time": "2025-10-29T18:11:00-06:00",
	"total_amount": 312.00,
	"currency": "GTQ",
	"items": [
		{"description": "Concentrado premium perro 15kg", "quantity": 1, "total_price": 312.00}
	],
	"category_suggestion": {
		"match_type": "NEW_PROPOSED",
		"category_id": null,
		"category_name": null,
		"proposed_name": "Mascotas"
	}
}
```

**Example 3: Invalid image (cannot extract receipt):**

```json
{
	"status": "INVALID_IMAGE",
	"reason": "No pude leer datos suficientes para construir la transacción. Intenta tomar otra foto donde se vea el total y el nombre del comercio."
}
```

**Important: category_suggestion Structure**

The `category_suggestion` object **always includes all 4 fields** in both cases:
- `match_type`: discriminator ("EXISTING" or "NEW_PROPOSED")
- `category_id`: string or null
- `category_name`: string or null  
- `proposed_name`: string or null

**Invariant Rules (enforced by backend validator):**

1. **EXISTING case**: 
   - `category_id` ≠ null (UUID from user's categories)
   - `category_name` ≠ null (exact name)
   - `proposed_name` = null
   - Frontend should preselect this category in the dropdown.

2. **NEW_PROPOSED case**:
   - `category_id` = null
   - `category_name` = null
   - `proposed_name` ≠ null (suggested new category name)
   - Frontend should select "General" by default and optionally show UI to create the new category.

3. When `status = "INVALID_IMAGE"`, no category_suggestion is provided.

**Why all 4 fields always?** Type safety and clarity. The frontend never has to check "is this field present?" — all 4 fields exist, some are just null. The backend validates this invariant, so invalid responses are caught before reaching the frontend.

**Status Codes:**
* `200 OK` - Draft extraction successful
* `400 BAD REQUEST` - Invalid file type, file too large, or out-of-scope request
* `401 UNAUTHORIZED` - Missing or invalid authentication token
* `500 INTERNAL SERVER ERROR` - Agent error or server failure

---

### `POST /invoices/commit`

**Purpose:** Persist a confirmed invoice to the database **and create a linked transaction**. Also uploads the receipt image to Supabase Storage.

**Request:** JSON body validated by `InvoiceCommitRequest`. Authorization required.

**Request Body:**
```json
{
	"store_name": "Super Despensa Familiar",
	"transaction_time": "2025-10-30T14:32:00-06:00",
	"total_amount": 128.50,
	"currency": "GTQ",
	"purchased_items": "- Leche 1L (2x) @ Q12.50 = Q25.00
- Pan molde @ Q15.00 = Q15.00",
	"image_base64": "/9j/4AAQSkZJRgABAQEAYABgAAD...",
	"image_filename": "receipt_20251030.jpg",
	"account_id": "...",
	"category_id": "..."
}
```

**Note:** 
- The frontend must provide `account_id` and `category_id` (user-selected from dropdowns).
- The image is sent as **base64** because it was NOT uploaded during the OCR draft phase.
- The `image_filename` is used to preserve the original filename in storage.

**Behavior:**
1. Validates required fields (store_name, total_amount, currency, image_base64, account_id, category_id).
2. **Uploads the receipt image to Supabase Storage** (this is the first time image is persisted).
3. Formats the canonical `extracted_text` using the project's template and inserts a new row in the `invoice` table with the uploaded image's storage path. RLS ensures the row is created for the authenticated user only.
4. **Automatically creates a linked transaction** with:
	- `flow_type = "outcome"` (invoices are always expenses)
	- `amount` = invoice total_amount
	- `date` = invoice transaction_time
	- `description` = invoice store_name
	- `invoice_id` = created invoice ID
	- `account_id` and `category_id` from request
5. Returns both the created invoice ID and transaction ID.

**Response (simplified):**

```json
{
	"status": "COMMITTED",
	"invoice_id": "...",
	"transaction_id": "...",
	"message": "Invoice and transaction saved successfully"
}
```

**Status Codes:**
* `201 CREATED` - Invoice and transaction created successfully
* `400 BAD REQUEST` - Invalid request data or missing required fields
* `401 UNAUTHORIZED` - Missing or invalid authentication token
* `500 INTERNAL SERVER ERROR` - Database persistence error or storage upload failure

**Important notes:**
* This endpoint creates BOTH an `invoice` row AND a `transaction` row atomically.
* The transaction is always an expense (`flow_type = "outcome"`).
* **The receipt image is uploaded to Supabase Storage only at this stage** (commit phase).
* If the user cancels before calling this endpoint, the image is never persisted to storage.
* Once committed, the invoice **cannot be updated** (immutability rule).

---

### `GET /invoices`

**Purpose:** Return the authenticated user's invoices (paginated).

**Query params:**
* `limit` (int, default 50, max 100) - Maximum number of invoices to return
* `offset` (int, default 0) - Number of invoices to skip for pagination

**Authorization:** Required (Bearer token).

**Behavior:**
- Returns a page of invoice rows belonging to the authenticated user (RLS enforced by DB).
- Each item includes: `id`, `user_id`, `storage_path`, `extracted_text`, `created_at`, `updated_at`.

**Response:**
```json
{
	"invoices": [
		{
			"id": "...",
			"user_id": "...",
			"storage_path": "invoices/<user_id>/<uuid>.jpg",
			"extracted_text": "Store Name: ...
Transaction Time: ...
...",
			"created_at": "2025-11-03T10:15:00Z",
			"updated_at": "2025-11-03T10:15:00Z"
		}
	],
	"count": 1,
	"limit": 50,
	"offset": 0
}
```

**Status Codes:**
* `200 OK` - Invoices retrieved successfully
* `401 UNAUTHORIZED` - Missing or invalid authentication token
* `500 INTERNAL SERVER ERROR` - Database query error

**Security:**
* RLS ensures users only see their own invoices.
* Results ordered by `created_at` descending (newest first).

---

### `GET /invoices/{invoice_id}`

**Purpose:** Retrieve a single invoice's details.

**Path param:** `invoice_id` (UUID). Authorization required.

**Behavior:**
- Returns the invoice record if it exists and belongs to the authenticated user.
- Returns `404 Not Found` if the invoice does not exist or is not accessible by the caller.

**Response:**
```json
{
	"id": "...",
	"user_id": "...",
	"storage_path": "invoices/<user_id>/<uuid>.jpg",
	"extracted_text": "Store Name: Super Despensa
Transaction Time: 2025-10-30T14:32:00-06:00
Total Amount: 128.50
Currency: GTQ
Purchased Items:
- Leche 1L (2x) @ Q12.50 = Q25.00
Receipt Image ID: invoices/<user_id>/<uuid>.jpg",
	"created_at": "2025-11-03T10:15:00Z",
	"updated_at": "2025-11-03T10:15:00Z"
}
```

The detail response includes the canonical `extracted_text` (the formatted template), `storage_path`, and timestamps.

**Status Codes:**
* `200 OK` - Invoice found and returned
* `404 NOT FOUND` - Invoice doesn't exist or not accessible by user
* `401 UNAUTHORIZED` - Missing or invalid authentication token
* `500 INTERNAL SERVER ERROR` - Database query error

---

### `DELETE /invoices/{invoice_id}`

**Purpose:** Permanently delete an invoice row.

**Path param:** `invoice_id` (UUID). Authorization required.

**Behavior:**
- Verifies the invoice exists and belongs to the authenticated user.
- Deletes the invoice row and returns a success payload.
- **Does NOT delete** the associated receipt image from Supabase Storage (storage cleanup is a separate concern).
- **Does NOT delete** the linked transaction (transactions remain intact even if their source invoice is deleted).
- Returns `404 Not Found` if the invoice does not exist or is not accessible by the caller.

**Response:**
```json
{
	"status": "DELETED",
	"invoice_id": "...",
	"message": "Invoice deleted successfully"
}
```

**Status Codes:**
* `200 OK` - Invoice deleted successfully
* `404 NOT FOUND` - Invoice doesn't exist or not accessible by user
* `401 UNAUTHORIZED` - Missing or invalid authentication token
* `500 INTERNAL SERVER ERROR` - Database deletion error

**Notes:**
* Deleting an invoice does NOT delete the linked transaction.
* Users can separately delete the transaction via `DELETE /transactions/{transaction_id}` if needed.

---

**User workflow for corrections:**
1. Delete the incorrect invoice: `DELETE /invoices/{invoice_id}`
2. Create a new invoice with correct data: `POST /invoices/ocr` → `POST /invoices/commit`

---

## 5. Budgets

A Budget = spending limit window that can repeat (`monthly`, etc.) or be one-off (`once`).
These map to the `budget` table and its join table to categories (`budget_category`).

### Frequency enum

`frequency` accepts:
* `once` - One-time budget
* `daily` - Repeats daily
* `weekly` - Repeats weekly
* `monthly` - Repeats monthly
* `yearly` - Repeats yearly

`interval` works with it (e.g. `frequency = "weekly"`, `interval = 2` = every 2 weeks).

---

### `GET /budgets`

**Purpose:** List all budgets for the authenticated user with their linked categories.

**Request:** No body. Authorization required (Bearer token).

**Query Parameters:**
* None (returns all budgets ordered by creation date)

**Behavior:**
- Returns all user's budgets with their linked categories
- Uses JOIN on `budget_category` → `category` to fetch category details
- Ordered by `created_at` descending (newest first)
- Only accessible to the budget owner (RLS enforced)
- Each budget includes list of categories linked via `budget_category` junction table

**Response:**
```json
{
  "budgets": [
    {
      "id": "budget-uuid",
      "user_id": "user-uuid",
      "limit_amount": 500.00,
      "frequency": "monthly",
      "interval": 1,
      "start_date": "2025-11-01",
      "end_date": null,
      "is_active": true,
      "categories": [
        {
          "id": "category-uuid-1",
          "name": "Groceries",
          "flow_type": "outcome",
          "key": null
        },
        {
          "id": "category-uuid-2",
          "name": "Restaurants",
          "flow_type": "outcome",
          "key": null
        }
      ],
      "created_at": "2025-11-03T10:15:00Z",
      "updated_at": "2025-11-03T10:15:00Z"
    }
  ],
  "count": 1
}
```

**Response Fields:**
- `categories`: Array of categories linked to this budget via `budget_category` table
  - Each category includes: `id`, `name`, `flow_type`, `key` (null for user categories)
  - Empty array if no categories linked
  - Categories can be system categories (with `key` field) or user-created (key is null)

**Status Codes:**
* `200 OK` - Budgets retrieved successfully
* `401 UNAUTHORIZED` - Missing or invalid authentication token
* `500 INTERNAL SERVER ERROR` - Database query error

**Security:**
* RLS ensures users only see their own budgets
* Categories are filtered by user access (system categories visible to all, user categories only to owner)

---

### `POST /budgets`

**Purpose:** Create a new budget with optional category linking.

**Request:**
```json
{
  "limit_amount": 500.00,
  "frequency": "monthly",
  "interval": 1,
  "start_date": "2025-11-01",
  "end_date": null,
  "is_active": true,
  "category_ids": ["category-uuid-1", "category-uuid-2"]
}
```

**Field Constraints:**
* `limit_amount` - Must be > 0
* `frequency` - Must be one of: once, daily, weekly, monthly, yearly
* `interval` - Must be >= 1
* `start_date` - Required, DATE format
* `end_date` - Optional, must be >= start_date if provided
* `is_active` - Defaults to true
* `category_ids` - Optional list of category UUIDs to link

**Behavior:**
- Creates a new budget row
- Links categories via `budget_category` junction table
- All category links use the authenticated user's `user_id` (RLS enforced)
- Returns the created budget + count of linked categories

**Response:**
```json
{
  "status": "CREATED",
  "budget": {
    "id": "budget-uuid",
    "user_id": "user-uuid",
    "limit_amount": 500.00,
    "frequency": "monthly",
    "interval": 1,
    "start_date": "2025-11-01",
    "end_date": null,
    "is_active": true,
    "categories": [
      {
        "id": "category-uuid-1",
        "name": "Groceries",
        "flow_type": "outcome",
        "key": null
      },
      {
        "id": "category-uuid-2",
        "name": "Restaurants",
        "flow_type": "outcome",
        "key": null
      }
    ],
    "created_at": "2025-11-03T10:15:00Z",
    "updated_at": "2025-11-03T10:15:00Z"
  },
  "categories_linked": 2,
  "message": "Budget created successfully with 2 categories"
}
```

**Status Codes:**
* `201 CREATED` - Budget created successfully
* `400 BAD REQUEST` - Invalid request data (validation error)
* `401 UNAUTHORIZED` - Missing or invalid authentication token
* `500 INTERNAL SERVER ERROR` - Database persistence error

**Security:**
* Only authenticated users can create budgets
* Budget is automatically assigned to the authenticated user's `user_id`

---

### `GET /budgets/{budget_id}`

**Purpose:** Retrieve details of a single budget by ID with its linked categories.

**Request:** No body. Authorization required (Bearer token).

**Path Parameters:**
* `budget_id` - UUID of the budget to retrieve

**Behavior:**
- Returns budget details for the specified ID with linked categories
- Uses JOIN on `budget_category` → `category` to fetch category details
- Only accessible to the budget owner (RLS enforced)
- Returns 404 if budget doesn't exist or belongs to another user

**Response:**
```json
{
  "id": "budget-uuid",
  "user_id": "user-uuid",
  "limit_amount": 500.00,
  "frequency": "monthly",
  "interval": 1,
  "start_date": "2025-11-01",
  "end_date": null,
  "is_active": true,
  "categories": [
    {
      "id": "category-uuid-1",
      "name": "Groceries",
      "flow_type": "outcome",
      "key": null
    },
    {
      "id": "category-uuid-2",
      "name": "Restaurants",
      "flow_type": "outcome",
      "key": null
    }
  ],
  "created_at": "2025-11-03T10:15:00Z",
  "updated_at": "2025-11-03T10:15:00Z"
}
```

**Response Fields:**
- `categories`: Array of categories linked to this budget via `budget_category` table
  - Each category includes: `id`, `name`, `flow_type`, `key` (null for user categories)
  - Empty array if no categories linked
  - Categories can be system categories or user-created categories

**Status Codes:**
* `200 OK` - Budget retrieved successfully
* `401 UNAUTHORIZED` - Missing or invalid authentication token
* `404 NOT FOUND` - Budget not found or not accessible by user
* `500 INTERNAL SERVER ERROR` - Database query error

---

### `PATCH /budgets/{budget_id}`

**Purpose:** Update budget details (partial update).

**Request:**
```json
{
  "limit_amount": 600.00,
  "is_active": false
}
```

**Updatable Fields (all optional):**
* `limit_amount` - Must be > 0 if provided
* `frequency` - Must be valid enum value
* `interval` - Must be >= 1 if provided
* `start_date` - DATE format
* `end_date` - Must be >= start_date if provided
* `is_active` - Boolean

**Behavior:**
- Accepts partial updates (only provided fields are updated)
- Returns the complete updated budget
- Does NOT update category links (use separate endpoints for that)
- Only the budget owner can update their budget

**Response:**
```json
{
  "status": "UPDATED",
  "budget": {
    "id": "budget-uuid",
    "user_id": "user-uuid",
    "limit_amount": 600.00,
    "frequency": "monthly",
    "interval": 1,
    "start_date": "2025-11-01",
    "end_date": null,
    "is_active": false,
    "categories": [
      {
        "id": "category-uuid-1",
        "name": "Groceries",
        "flow_type": "outcome",
        "key": null
      }
    ],
    "created_at": "2025-11-03T10:15:00Z",
    "updated_at": "2025-11-03T10:20:00Z"
  },
  "message": "Budget updated successfully"
}
```

**Status Codes:**
* `200 OK` - Budget updated successfully
* `400 BAD REQUEST` - Invalid request data or no fields provided
* `401 UNAUTHORIZED` - Missing or invalid authentication token
* `404 NOT FOUND` - Budget not found or not accessible by user
* `500 INTERNAL SERVER ERROR` - Database update error

---

### `DELETE /budgets/{budget_id}`

**Purpose:** Delete a budget following DB deletion rules.

**Request:** No body. Authorization required (Bearer token).

**Path Parameters:**
* `budget_id` - UUID of the budget to delete

**Behavior:**
- Follows exact DB deletion rule from `DB documentation.md`:
  1. Delete all `budget_category` links tied to the budget
  2. Delete the budget
  3. Never delete transactions (they remain as financial history)
- Only the budget owner can delete their budget
- Returns count of unlinked categories for transparency

**Response:**
```json
{
  "status": "DELETED",
  "budget_id": "budget-uuid",
  "categories_unlinked": 2,
  "message": "Budget deleted successfully. 2 category link(s) removed."
}
```

**Status Codes:**
* `200 OK` - Budget deleted successfully
* `401 UNAUTHORIZED` - Missing or invalid authentication token
* `404 NOT FOUND` - Budget not found or not accessible by user
* `500 INTERNAL SERVER ERROR` - Database deletion error

**DB Rule Enforcement:**
This endpoint follows the deletion rule:
1. Delete all `budget_category` links where `budget_id` matches AND `user_id` matches
2. Delete the budget row
3. Transactions are NEVER deleted (remain as history)

**Security:**
* RLS enforces user can only delete their own budgets
* Cascade deletion is handled explicitly in service layer

---

## 7. Wishlist / Goals / Recommendations integration

### Hierarchy

- `wishlist` **(Parent)** — represents the user goal or intention (e.g., _"I want a laptop for Photoshop, not gamer"_).
    
- `wishlist_item` **(Child)** — represents specific recommended options that the user decided to save from the Recommendation Agent results.

### `GET /wishlists`

**Description:** Returns all saved wishlists (goals) for the authenticated user.

**Response Example:**

```json
[
  {
    "id": "f3d3b64c-79e4-4e29-bb2c-41b09e7ac8c1",
    "goal_title": "Laptop for Photoshop (non-gamer)",
    "budget_hint": 7000,
    "currency_code": "GTQ",
    "target_date": "2025-12-01",
    "preferred_store": "Intelaf",
    "user_note": "No RGB lights, quiet keyboard",
    "status": "active",
    "created_at": "2025-10-30T10:25:43.225Z",
    "updated_at": "2025-10-30T10:25:43.225Z"
  }
]
```

---

### `POST /wishlists`

**Description:** Creates a new wishlist goal for the user.

**Request Body:**

```json
{
  "goal_title": "Laptop for Photoshop",
  "budget_hint": 7000,
  "currency_code": "GTQ",
  "target_date": "2025-12-01",
  "preferred_store": "Intelaf",
  "user_note": "Not gamer style",
  "status": "active"
}
```

**Response:**

```json
{
  "id": "f3d3b64c-79e4-4e29-bb2c-41b09e7ac8c1",
  "goal_title": "Laptop for Photoshop",
  "budget_hint": 7000,
  "currency_code": "GTQ",
  "target_date": "2025-12-01",
  "preferred_store": "Intelaf",
  "user_note": "Not gamer style",
  "status": "active",
  "created_at": "2025-10-30T10:25:43.225Z"
}
```

---

### `PATCH /wishlists/{wishlist_id}`

**Description:** Updates an existing wishlist goal (e.g., marking it as completed or changing the target date).

**Request Example:**

```json
{
  "status": "purchased",
  "target_date": "2025-12-31"
}
```

**Response:**

```json
{
  "id": "f3d3b64c-79e4-4e29-bb2c-41b09e7ac8c1",
  "status": "purchased",
  "target_date": "2025-12-31",
  "updated_at": "2025-10-31T14:05:11.893Z"
}
```

---

### `DELETE /wishlists/{wishlist_id}`

**Description:** Deletes a wishlist and all its related items.

**Delete Rule:** When a wishlist is deleted, **all related wishlist\_item rows must be deleted automatically** (`ON DELETE CASCADE`).

**Response:**

```json
{ "message": "Wishlist and related items deleted successfully." }
```

---

## 8. `wishlist_item` Endpoints (Saved Recommendations)

### `GET /wishlists/{wishlist_id}/items`

**Description:** Returns all saved items within a specific wishlist.

**Response Example:**

```json
[
  {
    "id": "24b2e91b-ec1a-4c94-9d1f-ded17b861c74",
    "wishlist_id": "f3d3b64c-79e4-4e29-bb2c-41b09e7ac8c1",
    "product_title": "ASUS VivoBook Ryzen 7",
    "price_total": 6750,
    "seller_name": "TecnoMundo",
    "url": "https://tecnomundo.gt/asus-vivobook",
    "pickup_available": true,
    "warranty_info": "12 months",
    "copy_for_user": "Great performance for Photoshop, below budget.",
    "badges": ["Best Price", "Warranty 12m"],
    "created_at": "2025-10-30T11:03:21.446Z"
  }
]
```

---

### `POST /wishlists/{wishlist_id}/items`

**Description:** Adds a new recommended item to an existing wishlist.

**Request Example:**

```json
{
  "product_title": "ASUS VivoBook Ryzen 7",
  "price_total": 6750,
  "seller_name": "TecnoMundo",
  "url": "https://tecnomundo.gt/asus-vivobook",
  "pickup_available": true,
  "warranty_info": "12 months",
  "copy_for_user": "Recommended by AI agent.",
  "badges": ["Best Value", "Trusted Store"]
}
```

**Response:**

```json
{
  "id": "...",
  "wishlist_id": "...",
  "product_title": "ASUS VivoBook Ryzen 7",
  "price_total": 6750,
  "seller_name": "TecnoMundo",
  "url": "https://tecnomundo.gt/asus-vivobook",
  "pickup_available": true,
  "warranty_info": "12 months",
  "copy_for_user": "Recommended by AI agent.",
  "badges": ["Best Value", "Trusted Store"],
  "created_at": "2025-10-30T11:03:21.446Z"
}
```

---

### `DELETE /wishlists/{wishlist_id}/items/{item_id}`

**Description:** Deletes a specific saved recommendation from the user wishlist.

**Delete Rule:** When a wishlist\_item is deleted, **only that item is removed**. The parent wishlist remains intact.

**Response:**

```json
{ "message": "Wishlist item deleted successfully." }
```




---

## 9. Recommendation Agent Entry Point

Single public entry for all product suggestions / purchase guidance. The frontend NEVER calls subagents directly.

### `POST /recommendations/query`

Purpose: ask for product suggestions or continue an ongoing clarification loop.
* Body must include:

```json

{

	"query_raw": "texto libre que el usuario escribió",
	
	"budget_hint": 7000,
	
	"extra_details": {
	
	// merged answers the user already gave in previous steps
	
	}

}

```

`extra_details` starts as `{}` and grows as the agent asks follow-ups.

Backend flow:
1. FastAPI calls `RecommendationCoordinatorAgent`.
2. That agent validates intent:
	* rejects sexual / crimen / cosas prohibidas → `NO_VALID_OPTION`.
	* also rejects cosas incoherentes ("quiero un misil").
3. If info is incomplete:
	* returns `NEEDS_CLARIFICATION` with questions.
4. If info is good:
	* calls SearchAgent → FormatterAgent
	* returns up to 3 ranked options.

Possible responses:

**A. status = "NEEDS_CLARIFICATION"**


```json

{

	"status": "NEEDS_CLARIFICATION",
	
	"missing_fields": [
	
	{ "field": "use_case", "question": "¿Para qué la vas a usar? (oficina, diseño...)" }
	
	]

}

```

Frontend: show these exact `question`s, collect answers, merge them into `extra_details` and re-call this same endpoint.


**B. status = "OK"**

```json

{

	"status": "OK",
	
	"results_for_user": [
	
	{
	
		"product_title": "HP Envy Ryzen 7 16GB RAM 512GB SSD 15.6\"",
		
		"price_total": 6200.00,
		
		"seller_name": "ElectroCentro Guatemala",
		
		"url": "https://electrocentro.gt/hp-envy-ryzen7",
		
		"pickup_available": true,
		
		"warranty_info": "Garantía HP 12 meses",
		
		"copy_for_user": "Opción recomendada para diseño gráfico. Buen rendimiento con Ryzen 7 y 16GB RAM. Está alrededor de Q100 más barata que otras opciones similares.",
		
		"badges": ["Más barata", "Pantalla antirreflejo", "Garantía 12 meses"]
	
	}
	
	]

}

```

Rules for frontend:
* Render cards exactly in this order. Do not reorder. Do not rewrite `copy_for_user`.
* Si el usuario no tiene aún una wishlist para esta meta, crearla con `POST /wishlists` y luego guardar la opción con `POST /wishlists/{wishlist_id}/items`. Si ya existe, saltar directo al POST de `items`
* If the user doesn't have a wishlist for this goal yet, create it using `POST /wishlists` then store the option using `POST /wishlists/{wishlist_id}/items`. If already exists, do the POST `items`
  

**C. status = "NO_VALID_OPTION"**

```json

{

"status": "NO_VALID_OPTION"

}

```


Meaning:
* Agent searched but filtered everything (estafa, precios falsos, incoherente, producto bloqueado).
* Frontend shows "No encontramos una oferta confiable con esos criterios." + CTA para ajustar presupuesto / marca.

---

## 10. Recurring Transactions

Recurring transaction endpoints manage rules that automatically generate transactions at scheduled intervals. These are used for:
- Recurring bills (rent, utilities, subscriptions)
- Regular income (salary, freelance retainers)
- Automatic savings transfers

**Important distinctions:**
- `budget`: spending/income caps with `once` frequency allowed
- `recurring_transaction`: rules that automatically generate transactions (frequency CANNOT be `once`)
- Supports `end_date` for temporary recurring rules
- Uses `next_run_date` to track when next transaction should be generated
- Supports paired rules (e.g., transfer from savings to checking)

---

### `GET /recurring-transactions`

**Purpose:** List all recurring transaction rules for the authenticated user.

**Request:** No body. Authorization required (Bearer token).

**Query Parameters:**
- None (returns all rules, ordered by creation date newest first)

**Behavior:**
- Returns all active and inactive recurring rules
- Ordered by `created_at` descending (newest first)
- RLS enforces only owner can see their rules

**Response:**
```json
{
  "recurring_transactions": [
    {
      "id": "uuid-here",
      "user_id": "user-uuid",
      "account_id": "account-uuid",
      "category_id": "category-uuid",
      "flow_type": "outcome",
      "amount": 1200.00,
      "description": "Monthly rent payment",
      "paired_recurring_transaction_id": null,
      "frequency": "monthly",
      "interval": 1,
      "by_weekday": null,
      "by_monthday": [1],
      "start_date": "2025-01-01",
      "next_run_date": "2025-12-01",
      "end_date": null,
      "is_active": true,
      "created_at": "2025-11-01T10:00:00Z",
      "updated_at": "2025-11-01T10:00:00Z"
    }
  ],
  "count": 1
}
```

**Field Semantics:**
- `frequency`: One of `"daily"`, `"weekly"`, `"monthly"`, `"yearly"` (NO `"once"`)
- `interval`: Multiplier (e.g., `interval=2` with `frequency="weekly"` = every 2 weeks)
- `by_weekday`: Required for `frequency="weekly"` (e.g., `["monday", "friday"]`)
- `by_monthday`: Required for `frequency="monthly"` (e.g., `[1, 15]` for 1st and 15th)
- `next_run_date`: When the next transaction will be generated (updated after sync)
- `end_date`: Optional date when rule should stop generating transactions
- `is_active`: If false, rule is paused and won't generate transactions

**Status Codes:**
* `200 OK` - Rules retrieved successfully
* `401 UNAUTHORIZED` - Missing or invalid authentication token
* `500 INTERNAL SERVER ERROR` - Database query error

---

### `POST /recurring-transactions`

**Purpose:** Create a new recurring transaction rule.

**Request:** Authorization required (Bearer token).

```json
{
  "account_id": "account-uuid",
  "category_id": "category-uuid",
  "flow_type": "outcome",
  "amount": 1200.00,
  "description": "Monthly rent payment",
  "frequency": "monthly",
  "interval": 1,
  "by_monthday": [1],
  "start_date": "2025-12-01",
  "is_active": true
}
```

**Required Fields:**
- `account_id`: Account where transactions will be created
- `category_id`: Category for generated transactions
- `flow_type`: `"income"` or `"outcome"`
- `amount`: Must be > 0
- `description`: Human-readable description
- `frequency`: One of `"daily"`, `"weekly"`, `"monthly"`, `"yearly"`
- `start_date`: First date to generate transaction (ISO-8601 date)

**Optional Fields:**
- `paired_recurring_transaction_id`: UUID of paired rule (for transfers)
- `interval`: Default 1 (every occurrence)
- `by_weekday`: Required for `frequency="weekly"` (array of weekday names)
- `by_monthday`: Required for `frequency="monthly"` (array of day numbers 1-31)
- `end_date`: Date when rule should stop (ISO-8601 date, nullable)
- `is_active`: Default `true`

**Validation Rules:**
1. If `frequency="weekly"`, `by_weekday` MUST be provided and non-empty
2. If `frequency="monthly"`, `by_monthday` MUST be provided and non-empty
3. `by_weekday` values must be valid weekday names (lowercase)
4. `by_monthday` values must be between 1 and 31
5. `interval` must be >= 1
6. `amount` must be > 0

**Behavior:**
- Creates a new recurring rule
- Sets `next_run_date = start_date` initially
- RLS enforces rule is owned by authenticated user
- If `paired_recurring_transaction_id` provided, both rules generate transactions together

**Response:**
```json
{
  "status": "CREATED",
  "recurring_transaction": {
    "id": "new-uuid",
    "user_id": "user-uuid",
    "account_id": "account-uuid",
    "category_id": "category-uuid",
    "flow_type": "outcome",
    "amount": 1200.00,
    "description": "Monthly rent payment",
    "paired_recurring_transaction_id": null,
    "frequency": "monthly",
    "interval": 1,
    "by_weekday": null,
    "by_monthday": [1],
    "start_date": "2025-12-01",
    "next_run_date": "2025-12-01",
    "end_date": null,
    "is_active": true,
    "created_at": "2025-11-06T10:00:00Z",
    "updated_at": "2025-11-06T10:00:00Z"
  },
  "message": "Recurring transaction rule created successfully"
}
```

**Status Codes:**
* `201 CREATED` - Rule created successfully
* `400 BAD REQUEST` - Validation error (missing required fields, invalid frequency-specific constraints)
* `401 UNAUTHORIZED` - Missing or invalid authentication token
* `500 INTERNAL SERVER ERROR` - Database insertion error

---

### `GET /recurring-transactions/{id}`

**Purpose:** Retrieve details of a single recurring transaction rule.

**Request:** No body. Authorization required (Bearer token).

**Path Parameters:**
- `id`: UUID of the recurring transaction rule

**Behavior:**
- Returns rule details for the specified ID
- RLS enforces only owner can access their rule
- Returns 404 if rule doesn't exist or belongs to another user

**Response:**
```json
{
  "id": "uuid-here",
  "user_id": "user-uuid",
  "account_id": "account-uuid",
  "category_id": "category-uuid",
  "flow_type": "income",
  "amount": 5000.00,
  "description": "Monthly salary",
  "paired_recurring_transaction_id": null,
  "frequency": "monthly",
  "interval": 1,
  "by_weekday": null,
  "by_monthday": [15],
  "start_date": "2025-01-15",
  "next_run_date": "2025-12-15",
  "end_date": null,
  "is_active": true,
  "created_at": "2025-01-10T10:00:00Z",
  "updated_at": "2025-11-15T14:30:00Z"
}
```

**Status Codes:**
* `200 OK` - Rule retrieved successfully
* `401 UNAUTHORIZED` - Missing or invalid authentication token
* `404 NOT FOUND` - Rule not found or not accessible
* `500 INTERNAL SERVER ERROR` - Database query error

---

### `PATCH /recurring-transactions/{id}`

**Purpose:** Update a recurring transaction rule (partial update).

**Request:** Authorization required (Bearer token).

**Path Parameters:**
- `id`: UUID of the recurring transaction rule to update

**Request Body (all fields optional):**
```json
{
  "description": "Updated description",
  "amount": 1500.00,
  "is_active": false,
  "end_date": "2026-12-31",
  "apply_retroactive_change": false
}
```

**Optional Fields (partial update):**
- `account_id`: Change target account
- `category_id`: Change category
- `flow_type`: Change between income/outcome
- `amount`: Update amount
- `description`: Update description
- `frequency`: Change recurrence pattern
- `interval`: Change interval multiplier
- `by_weekday`: Update weekday schedule (for weekly)
- `by_monthday`: Update monthday schedule (for monthly)
- `start_date`: Change start date (see special behavior below)
- `end_date`: Set or change end date
- `is_active`: Activate or pause rule (see special behavior below)
- `apply_retroactive_change`: Flag for `start_date` change behavior (default `false`)

**Special Behaviors:**

1. **Changing `start_date` with `apply_retroactive_change=true`:**
   - Deletes all past transactions that were generated by this rule
   - Use case: User realized they entered wrong start date
   - Returns count of deleted transactions in `retroactive_deletes` field
   - WARNING: This is destructive and cannot be undone

2. **Changing `is_active` from `false` → `true` (reactivation):**
   - Recalculates `next_run_date` to next future occurrence based on current date
   - Does NOT backfill missed occurrences during inactive period
   - Use case: User paused subscription, now resuming from today forward

**Behavior:**
- Only provided fields are updated (partial update)
- At least one field must be provided
- RLS enforces only owner can update their rule
- Returns updated rule plus metadata about retroactive changes

**Response:**
```json
{
  "status": "UPDATED",
  "recurring_transaction": {
    "id": "uuid-here",
    "user_id": "user-uuid",
    "account_id": "account-uuid",
    "category_id": "category-uuid",
    "flow_type": "outcome",
    "amount": 1500.00,
    "description": "Updated description",
    "paired_recurring_transaction_id": null,
    "frequency": "monthly",
    "interval": 1,
    "by_weekday": null,
    "by_monthday": [1],
    "start_date": "2025-01-01",
    "next_run_date": "2025-12-01",
    "end_date": "2026-12-31",
    "is_active": false,
    "created_at": "2025-11-01T10:00:00Z",
    "updated_at": "2025-11-06T15:30:00Z"
  },
  "retroactive_deletes": 0,
  "message": "Recurring transaction rule updated successfully"
}
```

**Response Fields:**
- `retroactive_deletes`: Number of past transactions deleted (if `apply_retroactive_change=true`)

**Status Codes:**
* `200 OK` - Rule updated successfully
* `400 BAD REQUEST` - No fields provided, or validation error
* `401 UNAUTHORIZED` - Missing or invalid authentication token
* `404 NOT FOUND` - Rule not found or not accessible
* `500 INTERNAL SERVER ERROR` - Database update error

**Notes:**
- TODO in service layer: Actual retroactive deletion logic not yet implemented
- TODO in service layer: `next_run_date` recalculation on activation not yet implemented
- These are marked as TODOs in `backend/services/recurring_transaction_service.py`

---

### `DELETE /recurring-transactions/{id}` (Updated for Recurring Transfers)

**Purpose:** Delete a recurring rule. If part of a recurring transfer, deletes both rules automatically.

**Request:** Authorization required (Bearer token).

**Behavior:**
1. Fetches recurring rule by ID
2. Checks if `paired_recurring_transaction_id` is not NULL
3. If paired (recurring transfer):
   - Deletes BOTH rules (symmetric deletion)
   - Returns success with paired info
4. If not paired:
   - Deletes single rule normally
5. Does NOT delete past generated transactions (they remain as history)

**Response (Recurring Transfer):**
```json
{
  "status": "DELETED",
  "recurring_transaction_id": "rule-uuid-1",
  "paired_rule_deleted": true,
  "message": "Recurring transaction rule deleted successfully. Paired rule was also deleted."
}
```

**Response (Normal Recurring Rule):**
```json
{
  "status": "DELETED",
  "recurring_transaction_id": "rule-uuid",
  "paired_rule_deleted": false,
  "message": "Recurring transaction rule deleted successfully."
}
```

**Status Codes:**
* `200 OK` - Rule(s) deleted successfully
* `401 UNAUTHORIZED` - Missing or invalid authentication token
* `404 NOT FOUND` - Rule not found or not accessible
* `500 INTERNAL SERVER ERROR` - Database error

**Security:**
* RLS enforces user can only delete own rules
* Paired deletion happens atomically (both rules or neither)

**Important Notes:**
- Deleting one rule of a recurring transfer automatically deletes the paired rule
- Past generated transactions preserved (history maintained)
- Future sync will no longer generate transactions for deleted rules

---

### `POST /transactions/sync-recurring`

**Purpose:** Synchronize recurring transactions and generate pending transactions.

**Request:** Authorization required (Bearer token).

```json
{}
```

**Request Body:**
- Empty body (future: may accept `preview_mode` and `max_occurrences` flags)

**Behavior:**
- Calls PostgreSQL function `sync_recurring_transactions(user_id, today)`
- Generates ALL pending transactions for all active rules up to today
- Atomic operation (all-or-nothing, no partial updates)
- Idempotent (safe to call multiple times)
- For each active rule:
  - Checks if `next_run_date <= today`
  - Generates transaction(s) with `date = scheduled_occurrence` (not today's date)
  - Updates `next_run_date` to next future occurrence
  - Stops if `end_date` exceeded
- Supports daily, weekly, monthly, yearly frequencies
- TODO: Proper `by_weekday` and `by_monthday` matching (currently simplified)

**Response:**
```json
{
  "status": "SYNCED",
  "transactions_generated": 3,
  "rules_processed": 2,
  "message": "Generated 3 transactions from 2 recurring rules"
}
```

**Response Fields:**
- `transactions_generated`: Total number of new transactions created
- `rules_processed`: Number of recurring rules that had pending occurrences
- `message`: Human-readable summary

**Status Codes:**
* `200 OK` - Sync completed successfully
* `401 UNAUTHORIZED` - Missing or invalid authentication token
* `500 INTERNAL SERVER ERROR` - PostgreSQL function error

**Implementation Notes:**
- Logic lives in PostgreSQL function `sync_recurring_transactions`
- Backend NEVER reimplements sync logic (calls DB function via Supabase RPC)
- Provides atomicity, consistency, idempotency

**Edge Cases:**
- Long user absence: Generates ALL pending occurrences (TODO: add `max_occurrences` limit)
- Paired rules: Generates transactions for both rules in same sync
- Inactive rules: Skipped during sync
- Rules with `end_date` in past: Skipped during sync

**Use Cases:**
- App calls on boot to catch up on missed recurring transactions
- Background job calls daily to generate today's transactions
- User manually triggers sync after editing rules

**Future Enhancements:**
- `preview_mode`: Return what would be generated without actually creating
- `max_occurrences`: Limit number of transactions generated per sync
- Advanced recurrence patterns: Last day of month, business days only, etc.
- Conflict detection: Warn if manual transaction already exists for scheduled date

---

## 11. Transfers (Internal Money Movements)

Transfers represent internal money movements between the user's own accounts. Each transfer consists of **two paired transactions** (one outcome, one income) that are created, updated, and deleted together atomically.

---

### Transfer Concepts

**Normal Transfers (One-time):**
- Created via `POST /transfers`
- Generates 2 paired `transaction` records:
  - One **outcome** transaction from source account
  - One **income** transaction to destination account
- Both transactions use the system category with key `transfer`
- Both reference each other via `paired_transaction_id` field

**Recurring Transfers:**
- Created via `POST /transfers/recurring`
- Generates 2 paired `recurring_transaction` rules:
  - One **outcome** template for source account
  - One **income** template for destination account
- Both rules use the system category with key `from_recurrent_transaction`
- Both reference each other via `paired_recurring_transaction_id` field
- Sync generates paired transactions automatically on schedule

**Key Rules:**
1. **Atomicity:** Both sides created together or neither
2. **Symmetric Deletion:** Deleting one side deletes both automatically
3. **Same User:** Both accounts must belong to the authenticated user
4. **Paired IDs:** All responses include both transaction/rule IDs for transparency
5. **System Categories:** Transfers use dedicated system categories, not user categories

---

### `POST /transfers`

**Purpose:** Create a one-time transfer between two accounts.

**Request:** Authorization required (Bearer token).

```json
{
  "from_account_id": "acct-uuid-source",
  "to_account_id": "acct-uuid-destination",
  "amount": 500.00,
  "date": "2025-11-03",
  "description": "Monthly savings transfer"
}
```

**Request Fields:**
- `from_account_id` (required): UUID of source account (money goes out)
- `to_account_id` (required): UUID of destination account (money goes in)
- `amount` (required): Amount to transfer (must be > 0)
- `date` (required): Transfer date in YYYY-MM-DD format
- `description` (optional): Description for both transactions

**Behavior:**
1. Validates both accounts belong to authenticated user
2. Fetches system category with `key='transfer'`
3. Creates outcome transaction from source account
4. Creates income transaction to destination account
5. Links both via `paired_transaction_id` (symmetric)
6. Returns both transaction IDs

**Response:**
```json
{
  "status": "CREATED",
  "transfer": {
    "from_transaction_id": "txn-uuid-out",
    "to_transaction_id": "txn-uuid-in",
    "from_account_id": "acct-uuid-source",
    "to_account_id": "acct-uuid-destination",
    "amount": 500.00,
    "date": "2025-11-03",
    "description": "Monthly savings transfer"
  },
  "message": "Transfer created successfully"
}
```

**Status Codes:**
* `201 CREATED` - Transfer created successfully
* `400 BAD REQUEST` - Invalid accounts (don't belong to user) or validation error
* `401 UNAUTHORIZED` - Missing or invalid authentication token
* `500 INTERNAL SERVER ERROR` - Database error or atomicity failure

**Security:**
* RLS enforces both accounts belong to `auth.uid()`
* Cannot create transfers between different users' accounts
* Paired transactions visible only to owner

**Edge Cases:**
- Transfer from account to itself: Allowed (but creates neutral effect)
- Negative amount: Rejected at validation layer (amount must be > 0)
- Partial failure: Atomicity ensures both transactions created or neither

---

### `POST /transfers/recurring`

**Purpose:** Create a recurring transfer template between two accounts.

**Request:** Authorization required (Bearer token).

```json
{
  "from_account_id": "acct-uuid-source",
  "to_account_id": "acct-uuid-destination",
  "amount": 500.00,
  "description_outgoing": "Monthly savings withdrawal",
  "description_incoming": "Monthly savings deposit",
  "frequency": "monthly",
  "interval": 1,
  "by_monthday": [5],
  "start_date": "2025-11-05",
  "end_date": null,
  "is_active": true
}
```

**Request Fields:**
- `from_account_id` (required): UUID of source account
- `to_account_id` (required): UUID of destination account
- `amount` (required): Amount per occurrence (must be > 0)
- `description_outgoing` (optional): Description for outcome side
- `description_incoming` (optional): Description for income side
- `frequency` (required): 'daily', 'weekly', 'monthly', or 'yearly'
- `interval` (required): Repeat every N units (must be >= 1)
- `by_weekday` (conditional): Required for weekly (e.g., ["monday", "friday"])
- `by_monthday` (conditional): Required for monthly (e.g., [1, 15, 30])
- `start_date` (required): Start date (YYYY-MM-DD)
- `end_date` (optional): End date or null for indefinite
- `is_active` (optional): Whether rules are active (default: true)

**Behavior:**
1. Validates both accounts belong to authenticated user
2. Validates frequency-specific fields (weekdays for weekly, monthdays for monthly)
3. Fetches system category with `key='from_recurrent_transaction'`
4. Creates outcome recurring rule for source account
5. Creates income recurring rule for destination account
6. Links both via `paired_recurring_transaction_id` (symmetric)
7. Sets `next_run_date = start_date` for both rules
8. Returns both rule IDs

**Response:**
```json
{
  "status": "CREATED",
  "recurring_transfer": {
    "outgoing_rule_id": "rule-uuid-out",
    "incoming_rule_id": "rule-uuid-in",
    "from_account_id": "acct-uuid-source",
    "to_account_id": "acct-uuid-destination",
    "amount": 500.00,
    "description_outgoing": "Monthly savings withdrawal",
    "description_incoming": "Monthly savings deposit",
    "frequency": "monthly",
    "interval": 1,
    "by_monthday": [5],
    "start_date": "2025-11-05",
    "next_run_date": "2025-11-05",
    "end_date": null,
    "is_active": true,
    "created_at": "2025-11-03T10:00:00Z"
  },
  "message": "Recurring transfer created successfully"
}
```

**Status Codes:**
* `201 CREATED` - Recurring transfer created successfully
* `400 BAD REQUEST` - Invalid accounts, missing frequency fields, or validation error
* `401 UNAUTHORIZED` - Missing or invalid authentication token
* `500 INTERNAL SERVER ERROR` - Database error or atomicity failure

**Validation Rules:**
- Weekly frequency REQUIRES `by_weekday` (at least one day)
- Monthly frequency REQUIRES `by_monthday` (at least one day, 1-31)
- Weekday names must be lowercase English (e.g., "monday", "wednesday")
- Interval must be positive integer
- Start date must be valid ISO-8601 date
- End date (if provided) must be after start date

**Security:**
* RLS enforces both accounts belong to `auth.uid()`
* Cannot create recurring transfers between different users' accounts
* Paired rules visible only to owner

**Sync Behavior:**
- `POST /transactions/sync-recurring` generates paired transactions for both rules
- Each occurrence creates two transactions (out + in) with matching dates
- Both generated transactions also have `paired_transaction_id` linking them

---

## 12. Security / RLS expectations

* Every request runs as the currently authenticated user (token in `Authorization` header).
* Row-Level Security in Supabase enforces `user_id = auth.uid()` for all user-owned rows (`account`, `transaction`, `invoice`, `budget`, `recurring_transaction`, `wishlist_item`, etc.).
* Global rows (example: global categories) are readable but not editable by normal users.

The backend is responsible for:
1. Making sure the token is valid (reject unauthenticated calls).
2. Making sure cross-user access is impossible (ignore/override any spoofed `user_id` in the body).
3. Refusing creation of illegal/blocked content in `/recommendations/query`.

---

## 13. Summary checklist for frontend devs

Boot / session:
* Read saved token from secure storage.
* Call `GET /auth/me` → hydrate session (`user_id`, `country`, `currency_preference`, etc.).
* If 401, force login again.

Invoice flow:
* Send photo → `POST /invoices/ocr`.
* If `DRAFT`, show preview. Let user pick `account_id`, `category_id` from `/accounts` + `/categories`.
* On confirm → `POST /invoices/commit`.

Wishlist / metas / compras:
* User writes goal or taps "dame opciones" → `POST /recommendations/query`.
* Show `NEEDS_CLARIFICATION` Q&A loop OR show ranked `OK` cards.
* Allow "Guardar en mi wishlist" could be `POST /wishlists` + `POST /wishlists/{wishlist_id}/items` or a direct `POST /wishlists/{wishlist_id}/items` if the goal already exists.

Budgets & suscripciones:
* `/budgets` for spending caps (frequency can be `once`).
* `/recurring-transactions` for repeating charges/income (frequency cannot be `once`; supports `end_date`, `next_run_date`).

Activity / historia financiera:
* `/transactions` powers the activity feed and balance per account. Treat transactions with `paired_transaction_id` as transfers, not spending.