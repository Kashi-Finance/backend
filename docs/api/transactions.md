# Transactions Endpoints

> **Money movements (income/outcome), filtering, and CRUD operations**

## Table of Contents

1. [Endpoint Reference](#endpoint-reference)
2. [Transaction Schema](#transaction-schema)
3. [POST /transactions](#post-transactions)
4. [GET /transactions](#get-transactions)
5. [GET /transactions/{id}](#get-transactionsid)
6. [PATCH /transactions/{id}](#patch-transactionsid)
7. [DELETE /transactions/{id}](#delete-transactionsid)
8. [POST /transactions/sync-recurring](#post-transactionssync-recurring)
9. [Integration Notes](#integration-notes)

---

## Endpoint Reference

| Method | Path | Description |
|--------|------|-------------|
| POST | `/transactions` | Create manual transaction |
| GET | `/transactions` | List with filters/pagination |
| GET | `/transactions/{id}` | Get single transaction |
| PATCH | `/transactions/{id}` | Update transaction |
| DELETE | `/transactions/{id}` | Delete (+ paired if transfer) |
| POST | `/transactions/sync-recurring` | Generate pending recurring transactions |

---

## Transaction Schema

```json
{
  "id": "uuid",
  "user_id": "uuid",
  "account_id": "uuid",
  "category_id": "uuid",
  "invoice_id": "uuid" | null,
  "flow_type": "income" | "outcome",
  "amount": 128.50,
  "date": "2025-10-30T14:32:00-06:00",
  "description": "Super Despensa Familiar",
  "paired_transaction_id": "uuid" | null,
  "embedding": [...] | null,
  "created_at": "2025-11-03T10:15:00Z",
  "updated_at": "2025-11-03T10:15:00Z"
}
```

**Field Notes:**
- `invoice_id` - Set when created from invoice commit
- `paired_transaction_id` - Set for internal transfers (don't count as spending/income)
- `embedding` - Semantic vector for AI search

---

## POST /transactions

**Purpose:** Insert a transaction manually (not from OCR or automation).

**Request Body:**
```json
{
  "account_id": "uuid",
  "category_id": "uuid",
  "flow_type": "income" | "outcome",
  "amount": 128.50,
  "date": "2025-10-30T14:32:00-06:00",
  "description": "Super Despensa Familiar"
}
```

**Required Fields:**
- `account_id` (UUID)
- `category_id` (UUID) - Use "General" if user doesn't pick one
- `flow_type` ("income" | "outcome")
- `amount` (numeric, > 0)
- `date` (ISO-8601)

**Optional Fields:**
- `description` (string)

**Response (201):**
```json
{
  "id": "uuid",
  "user_id": "uuid",
  "account_id": "uuid",
  "category_id": "uuid",
  "invoice_id": null,
  "flow_type": "outcome",
  "amount": 128.50,
  "date": "2025-10-30T14:32:00-06:00",
  "description": "Super Despensa Familiar",
  "paired_transaction_id": null,
  "embedding": null,
  "created_at": "2025-11-03T10:15:00Z",
  "updated_at": "2025-11-03T10:15:00Z"
}
```

**Status Codes:** 201, 400, 401, 500

---

## GET /transactions

**Purpose:** Fetch user's transactions with optional filters, sorting, and pagination.

**Query Parameters:**
| Param | Type | Default | Description |
|-------|------|---------|-------------|
| `limit` | int | 50 | Max 100 |
| `offset` | int | 0 | Pagination offset |
| `account_id` | UUID | - | Filter by account |
| `category_id` | UUID | - | Filter by category |
| `flow_type` | string | - | "income" or "outcome" |
| `from_date` | ISO-8601 | - | Start date |
| `to_date` | ISO-8601 | - | End date |
| `sort_by` | string | "date" | "date" or "amount" |
| `sort_order` | string | "desc" | "asc" or "desc" |

**Response:**
```json
{
  "transactions": [...],
  "count": 15,
  "limit": 50,
  "offset": 0
}
```

**Status Codes:** 200, 401, 500

---

## GET /transactions/{id}

**Purpose:** Retrieve a single transaction's details.

**Path Parameters:**
- `transaction_id` (UUID)

**Status Codes:** 200, 401, 404, 500

---

## PATCH /transactions/{id}

**Purpose:** Edit a transaction (amount, description, category, account, etc.).

**Request Body (all optional, at least one required):**
```json
{
  "account_id": "uuid",
  "category_id": "uuid",
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
  "transaction_id": "uuid",
  "transaction": { ... },
  "message": "Transaction updated successfully"
}
```

**⚠️ Transfer Restriction:**
If transaction has `paired_transaction_id` AND category is `transfer`:
```json
{
  "error": "cannot_edit_transfer",
  "details": "This transaction is part of an internal transfer. Use PATCH /transfers/{id} to edit it."
}
```

**Status Codes:** 200, 400, 401, 404, 500

---

## DELETE /transactions/{id}

**Purpose:** Delete a transaction. If part of a transfer, deletes both sides.

**Behavior:**
1. Fetch transaction by ID
2. Check if `paired_transaction_id` is set
3. If paired (transfer): Delete BOTH transactions
4. If not paired: Delete single transaction

**Response (Transfer):**
```json
{
  "status": "DELETED",
  "transaction_id": "txn-uuid-1",
  "paired_transaction_deleted": "txn-uuid-2",
  "message": "Transfer deleted (both sides removed)"
}
```

**Response (Normal):**
```json
{
  "status": "DELETED",
  "transaction_id": "txn-uuid",
  "message": "Transaction deleted successfully"
}
```

**Notes:**
- Invoice-linked transactions: Invoice is NOT deleted
- Deletion is permanent (no soft delete)
- Paired deletion is atomic (both or neither)

**Status Codes:** 200, 401, 404, 500

---

## POST /transactions/sync-recurring

**Purpose:** Generate all pending transactions from recurring rules.

**Request Body:** Empty `{}`

**Behavior:**
1. Calls PostgreSQL `sync_recurring_transactions(user_id, today)`
2. For each active rule where `next_run_date <= today`:
   - Creates transaction(s) with `date = scheduled_occurrence`
   - Updates `next_run_date` to next future occurrence
   - Stops if `end_date` exceeded
3. If paired rule → creates paired transactions

**Response:**
```json
{
  "status": "SYNCED",
  "transactions_generated": 3,
  "rules_processed": 2,
  "message": "Generated 3 transactions from 2 recurring rules"
}
```

**Use Cases:**
- App calls on boot to catch up
- Background job calls daily
- User manually triggers after editing rules

**Status Codes:** 200, 401, 500

---

## Integration Notes

### Transaction Sources

| Source | `invoice_id` | `paired_transaction_id` |
|--------|--------------|------------------------|
| Manual | null | null |
| Invoice | set | null |
| Transfer | null | set |
| Recurring | null | set (if paired) |

### Transfer vs Regular Transaction

```
Regular Transaction:
  paired_transaction_id = null
  → Counts in spending/income insights

Transfer:
  paired_transaction_id = <partner_txn_id>
  category.key = "transfer"
  → Do NOT count as spending/income
```

### Activity Feed

- `/transactions` powers the activity feed
- Filter by `account_id` for per-account view
- Use `paired_transaction_id` to identify transfers

### Related Endpoints

- **Invoices**: `POST /invoices/commit` creates transactions
- **Transfers**: `POST /transfers` creates paired transactions
- **Recurring**: `POST /transactions/sync-recurring` generates transactions
