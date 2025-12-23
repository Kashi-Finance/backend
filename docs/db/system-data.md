# System Data

> System categories and system-generated transaction keys.

---

## System Categories

System categories are **global, immutable categories** where:
- `user_id IS NULL` (not owned by any user)
- `key IS NOT NULL` (has a stable identifier)

They are created and managed only by the system via database migrations.

**CRITICAL:** The `(key, flow_type)` combination is UNIQUE. Each system category key exists exactly once per `flow_type`.

### System Category List

| Key | Flow Type | Name | Purpose |
|:----|:----------|:-----|:--------|
| `initial_balance` | `income` | Initial Balance (Income) | Opening balance for income-type accounts |
| `initial_balance` | `outcome` | Initial Balance (Outcome) | Opening balance for outcome-type accounts |
| `balance_update` | `income` | Manual Balance Adjustment (Income) | Manual positive balance corrections |
| `balance_update` | `outcome` | Manual Balance Adjustment (Outcome) | Manual negative balance corrections |
| `transfer` | `income` | Transfer (Income) | Destination side of internal transfers |
| `transfer` | `outcome` | Transfer (Outcome) | Source side of internal transfers |
| `general` | `income` | General Income | Default category for uncategorized income |
| `general` | `outcome` | General Outcome | Default category for uncategorized expenses |

### Important Notes

- System categories are **never** used to indicate "this transaction was auto-generated"
- Auto-generated transactions use `transaction.system_generated_key` for metadata
- Categories must always represent **user-intended categorization**
- When creating an account with `initial_balance`, the API automatically selects the system category with `key='initial_balance'` and `flow_type='income'` (or `outcome` for liability accounts)
- Users do not need to know the category ID — the system handles category selection for special operations

---

## System-Generated Transaction Keys

When transactions are created automatically by the system, they are marked using `transaction.system_generated_key`.

This is a **human-readable metadata field** used for:
- UI decoration (icons, labels)
- Filtering (show only manual transactions)
- Audit trail

### System-Generated Key List

| Key | Description | Used By |
|:----|:------------|:--------|
| `recurring_sync` | Transaction materialized from a recurring transaction template | Recurring transaction sync process |
| `invoice_ocr` | Transaction created from invoice OCR extraction | Invoice commit endpoint |
| `initial_balance` | Transaction created as initial balance when account is created | Account creation endpoint |
| `bulk_import` | Transaction imported via bulk data import | Bulk import tools (not yet implemented) |

### Important Notes

- `system_generated_key` is **nullable** and **optional**
- It is used for **UI decoration only**, not for business logic
- The authoritative link between a transaction and its recurring template is `transaction.recurring_transaction_id`
- User-created manual transactions have `system_generated_key = NULL`

---

## Usage Examples

### Finding System Category for Transfers

```sql
-- Get the transfer category for outcome (source side)
SELECT id FROM category 
WHERE key = 'transfer' AND flow_type = 'outcome';

-- Get the transfer category for income (destination side)
SELECT id FROM category 
WHERE key = 'transfer' AND flow_type = 'income';
```

### Creating Initial Balance Transaction

```sql
-- Get the initial_balance category for income
SELECT id FROM category 
WHERE key = 'initial_balance' AND flow_type = 'income';

-- Create the initial balance transaction
INSERT INTO transaction (
  user_id, account_id, category_id, 
  flow_type, amount, date, 
  description, system_generated_key
) VALUES (
  $user_id, $account_id, $category_id,
  'income', $initial_amount, now(),
  'Initial Balance', 'initial_balance'
);
```

### Filtering Out System Transactions in UI

```sql
-- Show only user-created transactions
SELECT * FROM transaction
WHERE user_id = auth.uid()
  AND system_generated_key IS NULL
  AND deleted_at IS NULL
ORDER BY date DESC;
```

---

## Category Selection Logic

### For Regular Transactions

1. User selects category from their categories + system categories
2. Category must match transaction's `flow_type`
3. Store `category_id` on transaction

### For Transfers

1. API automatically uses `transfer` category
2. Outcome side: `key='transfer' AND flow_type='outcome'`
3. Income side: `key='transfer' AND flow_type='income'`
4. User does NOT select category for transfers

### For Initial Balance

1. API automatically uses `initial_balance` category
2. For asset accounts: `key='initial_balance' AND flow_type='income'`
3. For liability accounts: `key='initial_balance' AND flow_type='outcome'`
4. User does NOT select category for initial balance

### For Category Deletion

1. Find all transactions using the deleted category
2. Reassign to: `key='general' AND flow_type=transaction.flow_type`
3. Then delete the category
