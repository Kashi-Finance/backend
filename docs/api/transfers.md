# Transfer Endpoints

> **Internal money movements between user's own accounts**

## Table of Contents

1. [Endpoint Reference](#endpoint-reference)
2. [Transfer Concepts](#transfer-concepts)
3. [Transfer Edit Rules](#transfer-edit-rules)
4. [POST /transfers](#post-transfers)
5. [PATCH /transfers/{id}](#patch-transfersid)
6. [POST /transfers/recurring](#post-transfersrecurring)
7. [Deletion Behavior](#deletion-behavior)
8. [Integration Notes](#integration-notes)

---

## Endpoint Reference

| Method | Path | Description |
|--------|------|-------------|
| POST | `/transfers` | Create one-time transfer |
| PATCH | `/transfers/{id}` | Update transfer (both sides) |
| POST | `/transfers/recurring` | Create recurring transfer template |

**Related:**
- `DELETE /transactions/{id}` - Deletes both sides of transfer
- `DELETE /recurring-transactions/{id}` - Deletes both recurring rules

---

## Transfer Concepts

### One-Time Transfers

- Created via `POST /transfers`
- Returns 2 transaction records
- Array[0]: **outcome** from source account
- Array[1]: **income** to destination account
- Both use system category `key='transfer'`
- Both linked via `paired_transaction_id`

### Recurring Transfers

- Created via `POST /transfers/recurring`
- Returns 2 recurring_transaction records
- Array[0]: **outcome** template for source account
- Array[1]: **income** template for destination account
- Both use system category `key='from_recurrent_transaction'`
- Both linked via `paired_recurring_transaction_id`
- Sync generates paired transactions automatically

### Key Benefits

| Benefit | Description |
|---------|-------------|
| Same Schema | Uses standard transaction/recurring schemas |
| Atomicity | Both sides created together or neither |
| Symmetric Deletion | Deleting one side deletes both |
| Same User | Both accounts must belong to authenticated user |
| System Categories | Uses dedicated categories, not user-selected |

---

## Transfer Edit Rules

**⚠️ CRITICAL: Transfers are atomic two-leg structures**

### Editing Transfers

✅ **Use `PATCH /transfers/{id}`:**
- Accepts ID of either transaction in the pair
- Updates BOTH transactions atomically
- Allowed fields: `amount`, `date`, `description`

❌ **`PATCH /transactions/{id}` rejects transfers:**
```json
{
  "error": "cannot_edit_transfer",
  "details": "This transaction is part of an internal transfer. Use PATCH /transfers/{id} to edit it."
}
```

### Immutable Fields

Cannot be changed after creation:
- `category_id` (must be system 'transfer')
- `flow_type` (outcome/income fixed)
- `paired_transaction_id`
- `account_id` (source/destination fixed)

---

## POST /transfers

**Purpose:** Create a one-time transfer between two accounts.

**Request Body:**
```json
{
  "from_account_id": "acct-uuid-source",
  "to_account_id": "acct-uuid-destination",
  "amount": 500.00,
  "date": "2025-11-03",
  "description": "Monthly savings transfer"
}
```

**Required Fields:**
- `from_account_id` (UUID, source)
- `to_account_id` (UUID, destination)
- `amount` (> 0)
- `date` (YYYY-MM-DD)

**Optional:**
- `description`

**Behavior:**
1. Validate both accounts belong to user
2. Fetch system category `key='transfer'`
3. Create outcome transaction from source
4. Create income transaction to destination
5. Link via `paired_transaction_id`

**Response (201):**
```json
{
  "status": "CREATED",
  "transactions": [
    {
      "id": "txn-uuid-out",
      "account_id": "acct-uuid-source",
      "category_id": "cat-uuid-transfer",
      "flow_type": "outcome",
      "amount": 500.00,
      "paired_transaction_id": "txn-uuid-in",
      ...
    },
    {
      "id": "txn-uuid-in",
      "account_id": "acct-uuid-destination",
      "category_id": "cat-uuid-transfer",
      "flow_type": "income",
      "amount": 500.00,
      "paired_transaction_id": "txn-uuid-out",
      ...
    }
  ],
  "message": "Transfer created successfully"
}
```

**Status Codes:** 201, 400, 401, 500

---

## PATCH /transfers/{id}

**Purpose:** Update transfer by updating both paired transactions.

**URL Parameter:**
- `id` - UUID of either transaction in the pair

**Request Body (all optional, at least one required):**
```json
{
  "amount": 600.00,
  "date": "2025-11-04",
  "description": "Updated transfer description"
}
```

**Behavior:**
1. Validate transaction exists and is a transfer
2. Validate belongs to authenticated user
3. Update BOTH paired transactions with same values
4. Return both updated transactions

**Response (200):**
```json
{
  "status": "UPDATED",
  "transactions": [
    { ... outcome transaction ... },
    { ... income transaction ... }
  ],
  "message": "Transfer updated successfully"
}
```

**Status Codes:** 200, 400, 401, 404, 500

---

## POST /transfers/recurring

**Purpose:** Create a recurring transfer template.

**Request Body:**
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

**Required Fields:**
- `from_account_id`, `to_account_id`
- `amount` (> 0)
- `frequency` (daily/weekly/monthly/yearly)
- `interval` (>= 1)
- `start_date`

**Conditional:**
- `by_weekday` - Required for weekly
- `by_monthday` - Required for monthly

**Optional:**
- `description_outgoing`, `description_incoming`
- `end_date`
- `is_active` (default true)

**Behavior:**
1. Validate both accounts belong to user
2. Validate frequency-specific fields
3. Fetch system category `key='from_recurrent_transaction'`
4. Create outcome recurring rule for source
5. Create income recurring rule for destination
6. Link via `paired_recurring_transaction_id`
7. Set `next_run_date = start_date`

**Response (201):**
```json
{
  "status": "CREATED",
  "recurring_transactions": [
    {
      "id": "rule-uuid-out",
      "account_id": "acct-uuid-source",
      "flow_type": "outcome",
      "paired_recurring_transaction_id": "rule-uuid-in",
      ...
    },
    {
      "id": "rule-uuid-in",
      "account_id": "acct-uuid-destination",
      "flow_type": "income",
      "paired_recurring_transaction_id": "rule-uuid-out",
      ...
    }
  ],
  "message": "Recurring transfer created successfully"
}
```

**Status Codes:** 201, 400, 401, 500

---

## Deletion Behavior

### Deleting One-Time Transfer

Via `DELETE /transactions/{id}`:
- Detects `paired_transaction_id`
- Deletes BOTH transactions
- Atomic (both or neither)

```json
{
  "status": "DELETED",
  "transaction_id": "txn-uuid-1",
  "paired_transaction_deleted": "txn-uuid-2",
  "message": "Transfer deleted (both sides removed)"
}
```

### Deleting Recurring Transfer

Via `DELETE /recurring-transactions/{id}`:
- Detects `paired_recurring_transaction_id`
- Deletes BOTH rules
- Past generated transactions NOT deleted

```json
{
  "status": "DELETED",
  "recurring_transaction_id": "rule-uuid-1",
  "paired_rule_deleted": true,
  "message": "Recurring transaction rule deleted successfully. Paired rule was also deleted."
}
```

---

## Integration Notes

### Transfer Recognition

A transaction is a transfer if:
- `paired_transaction_id` is NOT NULL
- `category.key` is `'transfer'` or `'from_recurrent_transaction'`

### Insights/Reporting

**⚠️ Do NOT count transfers as spending or income**

Transfers are internal movements:
- Filter out `paired_transaction_id IS NOT NULL`
- Or exclude category keys `transfer`, `from_recurrent_transaction`

### Sync Behavior

Recurring transfers generate paired transactions:
```
sync_recurring_transactions()
       │
       ├─► Rule 1 (outcome) → Transaction A
       └─► Rule 2 (income)  → Transaction B
                                 │
                        Both linked via
                    paired_transaction_id
```

### Account Balance Impact

| Transaction | Source Account | Destination Account |
|-------------|----------------|---------------------|
| Outcome | -amount | - |
| Income | - | +amount |

Net effect: Money moved, total unchanged.
