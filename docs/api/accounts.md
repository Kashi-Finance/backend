# Accounts Endpoints

> **Financial account management (bank, cash, credit, etc.)**

## Table of Contents

1. [Endpoint Reference](#endpoint-reference)
2. [Account Types](#account-types)
3. [GET /accounts](#get-accounts)
4. [POST /accounts](#post-accounts)
5. [GET /accounts/{id}](#get-accountsid)
6. [PATCH /accounts/{id}](#patch-accountsid)
7. [DELETE /accounts/{id}](#delete-accountsid)
8. [Integration Notes](#integration-notes)

---

## Endpoint Reference

| Method | Path | Description |
|--------|------|-------------|
| GET | `/accounts` | List all user accounts |
| POST | `/accounts` | Create new account |
| GET | `/accounts/{id}` | Get account details |
| PATCH | `/accounts/{id}` | Update account |
| DELETE | `/accounts/{id}` | Delete account with strategy |

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
  "initial_balance": 1500.00
}
```

**Required Fields:**
- `name` (string, min_length=1)
- `type` (AccountType enum)
- `currency` (string, 3 chars, ISO code)

**Optional Fields:**
- `initial_balance` (float, >=0): Creates income transaction with system category `key='initial_balance'`

**Response (201):**
```json
{
  "status": "CREATED",
  "account": {
    "id": "account-uuid-123",
    "user_id": "user-uuid-456",
    "name": "Main Checking",
    "type": "bank",
    "currency": "GTQ",
    "cached_balance": 1500.00,
    "created_at": "2025-11-05T10:00:00Z",
    "updated_at": "2025-11-05T10:00:00Z"
  },
  "message": "Account created successfully"
}
```

**Status Codes:** 201, 400, 401, 422, 500

---

## GET /accounts/{id}

**Purpose:** Retrieve details of a specific account.

**Path Parameters:**
- `account_id` (UUID)

**Response:**
```json
{
  "id": "account-uuid-123",
  "user_id": "user-uuid-456",
  "name": "Main Checking",
  "type": "bank",
  "currency": "GTQ",
  "cached_balance": 2500.50,
  "created_at": "2025-10-31T10:00:00Z",
  "updated_at": "2025-10-31T10:00:00Z"
}
```

**Status Codes:** 200, 401, 404, 500

---

## PATCH /accounts/{id}

**Purpose:** Update an existing account.

**Request Body (all optional, at least one required):**
```json
{
  "name": "Updated Account Name",
  "type": "cash",
  "currency": "USD"
}
```

**Response:**
```json
{
  "status": "UPDATED",
  "account": { ... },
  "message": "Account updated successfully"
}
```

**Status Codes:** 200, 400, 401, 404, 422, 500

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
