# Accounts Endpoints

> **Financial account management (bank, cash, credit, etc.)**

## Table of Contents

1. [Endpoint Reference](#endpoint-reference)
2. [Account Types](#account-types)
3. [Account Model](#account-model)
4. [GET /accounts](#get-accounts)
5. [POST /accounts](#post-accounts)
6. [GET /accounts/{id}](#get-accountsid)
7. [PATCH /accounts/{id}](#patch-accountsid)
8. [DELETE /accounts/{id}](#delete-accountsid)
9. [Favorite Account Endpoints](#favorite-account-endpoints)
10. [Integration Notes](#integration-notes)

---

## Endpoint Reference

| Method | Path | Description |
|--------|------|-------------|
| GET | `/accounts` | List all user accounts |
| POST | `/accounts` | Create new account |
| GET | `/accounts/{id}` | Get account details |
| PATCH | `/accounts/{id}` | Update account |
| DELETE | `/accounts/{id}` | Delete account with strategy |
| GET | `/accounts/favorite` | Get user's favorite account |
| POST | `/accounts/favorite` | Set favorite account |
| DELETE | `/accounts/favorite/{id}` | Clear favorite status |

---

## Account Types

```typescript
type AccountType = 
  | "cash"        // Physical cash
  | "bank"        // Bank account (checking/savings)
  | "credit_card" // Credit card
  | "loan"        // Loan account
  | "remittance"  // Remittance/transfer account
  | "crypto"      // Cryptocurrency wallet
  | "investment"  // Investment account
```

---

## Account Model

**Full Account Response:**
```json
{
  "id": "account-uuid-123",
  "user_id": "user-uuid-456",
  "name": "Main Checking",
  "type": "bank",
  "currency": "GTQ",
  "icon": "bank",
  "color": "#4CAF50",
  "is_favorite": true,
  "is_pinned": false,
  "description": "My main checking account",
  "cached_balance": 2500.50,
  "created_at": "2025-10-31T10:00:00Z",
  "updated_at": "2025-10-31T10:00:00Z"
}
```

**Field Descriptions:**
| Field | Type | Description |
|-------|------|-------------|
| `id` | UUID | Account identifier |
| `user_id` | UUID | Owner user ID |
| `name` | string | User-friendly account name |
| `type` | AccountType | Type of financial container |
| `currency` | string | ISO currency code (e.g., 'GTQ') |
| `icon` | string | Icon identifier for UI (e.g., 'wallet', 'bank') |
| `color` | string | Hex color code (e.g., '#FF5733') |
| `is_favorite` | boolean | Auto-selected for manual transactions (max 1 per user) |
| `is_pinned` | boolean | Pinned to top of account list |
| `description` | string? | Optional user description |
| `cached_balance` | number | Cached balance (recomputable) |
| `created_at` | timestamp | Creation timestamp |
| `updated_at` | timestamp | Last update timestamp |

---

## GET /accounts

**Purpose:** List all financial accounts for the authenticated user.

**Query Parameters:**
| Param | Type | Default | Description |
|-------|------|---------|-------------|
| `limit` | int | 50 | Max accounts to return |
| `offset` | int | 0 | Pagination offset |

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
      "icon": "bank",
      "color": "#4CAF50",
      "is_favorite": true,
      "is_pinned": false,
      "description": null,
      "cached_balance": 2500.50,
      "created_at": "2025-10-31T10:00:00Z",
      "updated_at": "2025-10-31T10:00:00Z"
    }
  ],
  "count": 1,
  "limit": 50,
  "offset": 0
}
```

**Status Codes:** 200, 401, 500

---

## POST /accounts

**Purpose:** Create a new financial account.

**Request Body:**
```json
{
  "name": "Main Checking",
  "type": "bank",
  "currency": "GTQ",
  "icon": "bank",
  "color": "#4CAF50",
  "is_favorite": false,
  "is_pinned": false,
  "description": "My main checking account",
  "initial_balance": 1500.00
}
```

**Required Fields:**
| Field | Type | Description |
|-------|------|-------------|
| `name` | string | Account name (1-200 chars) |
| `type` | AccountType | Account type enum |
| `currency` | string | ISO currency code (3 chars) |
| `icon` | string | Icon identifier (1-50 chars) |
| `color` | string | Hex color code (#RRGGBB) |

**Optional Fields:**
| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `is_favorite` | boolean | false | Set as favorite account (auto-clears previous) |
| `is_pinned` | boolean | false | Pin to top of account list |
| `description` | string | null | User description (max 500 chars) |
| `initial_balance` | number | null | Initial balance (creates income transaction) |

**Response (201):**
```json
{
  "status": "CREATED",
  "account": { ...full account object... },
  "message": "Account created successfully"
}
```

**Status Codes:** 201, 400 (currency mismatch), 401, 422, 500

---

## GET /accounts/{id}

**Purpose:** Retrieve details of a specific account.

**Path Parameters:**
- `account_id` (UUID)

**Response:** Full account object (see Account Model above)

**Status Codes:** 200, 401, 404, 500

---

## PATCH /accounts/{id}

**Purpose:** Update an existing account.

**Request Body (all optional, at least one required):**
```json
{
  "name": "Updated Account Name",
  "type": "cash",
  "icon": "wallet",
  "color": "#FF5733",
  "is_pinned": true,
  "description": "Updated description"
}
```

**Updatable Fields:**
| Field | Type | Notes |
|-------|------|-------|
| `name` | string | 1-200 chars |
| `type` | AccountType | Account type |
| `icon` | string | Icon identifier |
| `color` | string | Hex color code |
| `is_pinned` | boolean | Pin status |
| `description` | string | User description |

**NOT Updatable:**
- `currency` - Single-currency-per-user policy (400 error)
- `is_favorite` - Use `/accounts/favorite` endpoint (400 error)

**Response:**
```json
{
  "status": "UPDATED",
  "account": { ...full account object... },
  "message": "Account updated successfully"
}
```

**Status Codes:** 200, 400, 401, 404, 500

---

## Favorite Account Endpoints

The favorite account feature allows users to designate one account as their default for manual transaction creation. Only one account per user can be marked as favorite at a time.

### GET /accounts/favorite

**Purpose:** Get the user's favorite account ID.

**Response:**
```json
{
  "favorite_account_id": "account-uuid-123"
}
```

Or if no favorite is set:
```json
{
  "favorite_account_id": null
}
```

**Status Codes:** 200, 401, 500

---

### POST /accounts/favorite

**Purpose:** Set an account as the user's favorite. Automatically clears the previous favorite.

**Request Body:**
```json
{
  "account_id": "account-uuid-123"
}
```

**Response:**
```json
{
  "status": "OK",
  "previous_favorite_id": "old-account-uuid",
  "new_favorite_id": "account-uuid-123",
  "message": "Account set as favorite"
}
```

**Notes:**
- If the account is already favorite, returns success with no changes
- `previous_favorite_id` is null if no previous favorite existed

**Status Codes:** 200, 401, 403 (not owner), 404 (not found), 500

---

### DELETE /accounts/favorite/{account_id}

**Purpose:** Clear the favorite status from an account.

**Path Parameters:**
- `account_id` (UUID): Account to clear favorite status from

**Response:**
```json
{
  "status": "OK",
  "cleared": true,
  "message": "Favorite status cleared"
}
```

Or if the account was not favorite:
```json
{
  "status": "OK",
  "cleared": false,
  "message": "Account was not favorite"
}
```

**Status Codes:** 200, 401, 404, 500

---

## DELETE /accounts/{id}

**Purpose:** Delete an account and handle associated transactions.

**Request Body:**
```json
{
  "strategy": "reassign",
  "target_account_id": "target-account-uuid"
}
```

OR

```json
{
  "strategy": "delete_transactions",
  "target_account_id": null
}
```

### Deletion Strategies

| Strategy | Behavior |
|----------|----------|
| `reassign` | Move all transactions to `target_account_id` (RECOMMENDED) |
| `delete_transactions` | **DESTRUCTIVE**: Permanently delete all transactions |

### Strategy: reassign

1. Validates `target_account_id` exists and belongs to user
2. Updates all transactions: `account_id → target_account_id`
3. Deletes the account
4. Preserves transaction history

### Strategy: delete_transactions

1. Clears `paired_transaction_id` references
2. Deletes all transactions for account
3. Deletes the account
4. **Cannot be undone**

**Response (reassign):**
```json
{
  "status": "DELETED",
  "account_id": "account-uuid-123",
  "transactions_affected": 5,
  "message": "Account deleted successfully. 5 transactions reassigned to target account."
}
```

**Response (delete_transactions):**
```json
{
  "status": "DELETED",
  "account_id": "account-uuid-123",
  "transactions_affected": 3,
  "message": "Account deleted successfully. 3 transactions deleted."
}
```

**Status Codes:** 200, 400, 401, 404, 500

---

## Integration Notes

### Dependencies

- **Transactions** require an `account_id`
- **Transfers** require two accounts (source + destination)
- **Recurring transactions** require an `account_id`

### Cached Balance

- `cached_balance` is performance-optimized
- Recomputable via `recompute_account_balance` RPC
- Updated automatically on transaction changes

### RLS Enforcement

- Users can only access their own accounts
- Both accounts in a transfer must belong to same user
- Target account for reassignment must belong to same user
