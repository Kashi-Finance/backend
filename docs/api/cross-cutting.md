# Cross-Cutting Concerns & Dependencies

> **Security patterns, shared conventions, and feature dependencies**

## Table of Contents

1. [Authentication Flow](#1-authentication-flow)
2. [Standard Response Formats](#2-standard-response-formats)
3. [Row-Level Security (RLS)](#3-row-level-security-rls)
4. [Feature Dependencies](#4-feature-dependencies)
5. [System Categories](#5-system-categories)
6. [Cached Fields & Performance](#6-cached-fields--performance)

---

## 1. Authentication Flow

All endpoints require an authenticated user unless explicitly marked as `public`.

### Token Flow

```http
Authorization: Bearer <access_token>
```

### Backend Verification Steps

1. Validate token signature (Supabase Auth)
2. Extract authenticated `user_id` from token (`auth.uid()`)
3. Use that `user_id` to:
   - Fetch user's profile from `profile` table
   - Enforce RLS so caller only sees/updates their rows

### Key Rules

- Client does **NOT** need to send `user_id` in requests
- If client sends `user_id`, backend **overrides/ignores** it
- Invalid/expired token → `401 Unauthorized`
- `GET /auth/me` requires no body

---

## 2. Standard Response Formats

### List Responses (200 OK)

```json
{
  "<resource_type>": [...],
  "count": 42,
  "limit": 50,
  "offset": 0
}
```

### Creation Responses (201 CREATED)

```json
{
  "status": "CREATED",
  "<resource_type>_id": "uuid-here",
  "<resource_type>": { ...full_object },
  "message": "Success message"
}
```

### Update Responses (200 OK)

```json
{
  "status": "UPDATED",
  "<resource_type>_id": "uuid-here",
  "<resource_type>": { ...full_updated_object },
  "message": "Success message"
}
```

### Deletion Responses

**Soft-delete** (invoices, budgets, profiles):
```json
{
  "status": "DELETED",
  "<resource_type>_id": "uuid-here",
  "deleted_at": "2025-11-16T10:30:00Z",
  "message": "Success message"
}
```

**Hard-delete** (transactions, recurring, categories):
```json
{
  "status": "DELETED",
  "<resource_type>_id": "uuid-here",
  "message": "Success message"
}
```

### Error Responses (4xx, 5xx)

```json
{
  "error": "error_code",
  "details": "Human-readable description"
}
```

**Common error codes:**
| Code | HTTP | Description |
|------|------|-------------|
| `unauthorized` | 401 | Missing/invalid token |
| `forbidden` | 403 | Not allowed to access |
| `not_found` | 404 | Resource doesn't exist |
| `validation_error` | 400 | Invalid request data |
| `out_of_scope` | 400 | Intent not supported |
| `conflict` | 409 | State conflict |
| `internal_error` | 500 | Server error |

---

## 3. Row-Level Security (RLS)

Every user-owned table enforces `user_id = auth.uid()`:

| Table | RLS Scope |
|-------|-----------|
| `profile` | User can only access own profile |
| `account` | User can only access own accounts |
| `category` | User sees system + own categories |
| `transaction` | User can only access own transactions |
| `invoice` | User can only access own invoices |
| `budget` | User can only access own budgets |
| `budget_category` | User can only access own links |
| `recurring_transaction` | User can only access own rules |
| `wishlist` | User can only access own wishlists |
| `wishlist_item` | User can only access own items |

**System categories** (`user_id=NULL`) are readable by all, editable by none.

---

## 4. Feature Dependencies

### Dependency Matrix

```
account ──────────► transaction
                         │
category ───────────────►│
                         │
invoice ────────────────►│
                         │
recurring_transaction ──►│
                         │
budget ◄─────────────────┘
   │
   └──► budget_category ◄─── category

wishlist ──────────────► wishlist_item

profile ──────────────► (all endpoints for context)
```

### Critical Dependencies

#### Transactions require:
- `account_id` - Money must live somewhere
- `category_id` - Every transaction is categorized
- Optional: `invoice_id` - If created from OCR
- Optional: `paired_transaction_id` - If part of transfer

#### Budgets require:
- One or more `category_id` via `budget_category` junction
- Categories cannot be deleted if linked to budget (reassigned instead)

#### Invoices create:
- Automatically create linked `transaction` on commit
- Transaction links back via `invoice_id`

#### Transfers create:
- Two paired `transaction` records (outcome + income)
- Both linked via `paired_transaction_id`
- Both use system category `key='transfer'`

#### Recurring transactions create:
- Transactions on sync via `sync_recurring_transactions`
- If paired recurring → creates paired transactions

#### Wishlists:
- Independent from transactions/accounts
- `wishlist_item` records cascade on wishlist delete

### Deletion Cascade Rules

| Resource | On Delete |
|----------|-----------|
| Account | Reassign or cascade-delete transactions |
| Category (user) | Reassign to flow-type-matched `general` |
| Category (system) | CANNOT delete |
| Transaction | Hard delete (+ paired if transfer) |
| Invoice | Soft delete (transaction preserved) |
| Budget | Soft delete (junction preserved) |
| Recurring | Hard delete (+ paired if transfer) |
| Wishlist | Hard delete + cascade items |
| Wishlist Item | Hard delete |

---

## 5. System Categories

System categories have `user_id=NULL` and a non-null `key` field.

| Key | Flow Type | Purpose | Auto-assigned |
|-----|-----------|---------|---------------|
| `initial_balance` | income | Opening balance (assets) | Yes - on account creation |
| `initial_balance` | outcome | Opening balance (liabilities) | Yes - on account creation |
| `balance_update` | income | Manual positive adjustment | No |
| `balance_update` | outcome | Manual negative adjustment | No |
| `transfer` | income | Receiving side of transfer | Yes - on transfer |
| `transfer` | outcome | Sending side of transfer | Yes - on transfer |
| `general` | income | Uncategorized income | Fallback |
| `general` | outcome | Uncategorized expense | Fallback |

### Category Rules

1. System categories are **read-only** (no create/update/delete)
2. User categories have `key=NULL`
3. Deleting user category → reassign to matching `general`
4. `flow_type` is **immutable** after creation

---

## 6. Cached Fields & Performance

### Cached Balance Fields

| Table | Field | Recomputation |
|-------|-------|---------------|
| `account` | `cached_balance` | `recompute_account_balance` RPC |
| `budget` | `cached_consumption` | `recompute_budget_consumption` RPC |

### Usage Patterns

- Frontend reads cached values for fast display
- Backend triggers recomputation on relevant changes
- Manual recomputation available via RPC if needed

### Semantic Search

- `transaction.embedding` stores vector for AI search
- Can be `null` if not yet generated
- Used by RecommendationCoordinatorAgent's SearchAgent

---

## Quick Reference: Cross-Feature Interactions

### Invoice → Transaction

```
POST /invoices/commit
  ├─► Creates invoice record
  └─► Creates transaction with:
      ├─ flow_type: "outcome"
      ├─ invoice_id: <new_invoice_id>
      ├─ category_id: <from_request>
      └─ account_id: <from_request>
```

### Transfer → Transactions

```
POST /transfers
  └─► Creates 2 transactions:
      ├─ Transaction 1 (outcome from source)
      │   └─ paired_transaction_id: <txn2_id>
      └─ Transaction 2 (income to destination)
          └─ paired_transaction_id: <txn1_id>
```

### Recurring → Transactions

```
POST /transactions/sync-recurring
  └─► For each active rule where next_run_date <= today:
      ├─ Creates transaction(s)
      ├─ Updates next_run_date
      └─ If paired → creates paired transactions
```

### Category Deletion → Transactions

```
DELETE /categories/{id}?cascade=false
  └─► Reassigns transactions to flow-type-matched "general"
      ├─ outcome category → general (outcome)
      └─ income category → general (income)
```
