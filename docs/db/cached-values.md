# Cached Balances and Consumption

> For performance, we cache computed values that can be derived from transaction history.

---

## Cached Fields

### account.cached_balance

| Field | Type | Default |
|:------|:-----|:--------|
| `cached_balance` | NUMERIC(12,2) | 0 |

**Purpose:** Performance cache of account balance

**Computation:**
```sql
SUM(amount) WHERE flow_type = 'income'
- SUM(amount) WHERE flow_type = 'outcome'
```

**Updated by:**
- Transaction creation (increment/decrement)
- Transaction deletion (reverse the amount)
- Transaction update (if amount or flow_type changes)
- Balance reconciliation RPC

**Verification:**
```sql
SELECT recompute_account_balance(account_id);
```

---

### budget.cached_consumption

| Field | Type | Default |
|:------|:-----|:--------|
| `cached_consumption` | NUMERIC(12,2) | 0 |

**Purpose:** Performance cache of current period spending

**Computation:**
```sql
SUM(t.amount)
FROM transaction t
JOIN budget_category bc ON t.category_id = bc.category_id
WHERE bc.budget_id = budget.id
  AND t.flow_type = 'outcome'
  AND t.date BETWEEN period_start AND period_end
  AND t.deleted_at IS NULL
```

**Updated by:**
- Transaction creation (if category is tracked by budget)
- Transaction deletion (reverse)
- Transaction update (if amount, category, or date changes)
- Period rollover (reset to 0 at start of new period)
- Consumption reconciliation RPC

**Verification:**
```sql
SELECT recompute_budget_consumption(budget_id, period_start, period_end);
```

---

## Why Cache?

1. **Performance** — Avoid expensive SUM queries on every page load
2. **Responsiveness** — Instant balance display in mobile app
3. **Scalability** — O(1) reads instead of O(n) transaction scans

---

## Cache Update Triggers

### On Transaction INSERT

```sql
-- Update account balance
IF flow_type = 'income' THEN
  UPDATE account SET cached_balance = cached_balance + amount
ELSE
  UPDATE account SET cached_balance = cached_balance - amount
END IF;

-- Update budget consumption (if applicable)
FOR each budget tracking this category in current period:
  UPDATE budget SET cached_consumption = cached_consumption + amount
```

### On Transaction DELETE (soft-delete)

```sql
-- Reverse the balance change
IF flow_type = 'income' THEN
  UPDATE account SET cached_balance = cached_balance - amount
ELSE
  UPDATE account SET cached_balance = cached_balance + amount
END IF;

-- Reverse budget consumption (if applicable)
FOR each budget tracking this category in current period:
  UPDATE budget SET cached_consumption = cached_consumption - amount
```

### On Transaction UPDATE

If `amount`, `flow_type`, `category_id`, or `date` changes:
1. Reverse old values
2. Apply new values

---

## Reconciliation

### Scheduled Jobs

Background jobs verify cached values against transaction history:

1. Run periodically (e.g., daily at low-traffic hours)
2. Compare cached values to computed values
3. If drift exceeds threshold, raise alert
4. Auto-correct or manual review depending on policy

### On-Demand Reconciliation

```sql
-- Recompute and update account balance
SELECT recompute_account_balance('account-uuid');

-- Recompute budget consumption for current period
SELECT recompute_budget_consumption('budget-uuid', '2025-11-01', '2025-11-30');
```

---

## Concurrency Handling

To prevent race conditions:

1. **Use row-level locks** in RPCs:
   ```sql
   SELECT * FROM account WHERE id = $1 FOR UPDATE;
   ```

2. **Atomic updates** with single statements:
   ```sql
   UPDATE account 
   SET cached_balance = cached_balance + $amount
   WHERE id = $account_id;
   ```

3. **Transaction isolation** for multi-step operations

---

## Edge Cases

### Transfers

A transfer creates two transactions:
- Outcome from source account (decrements source balance)
- Income to destination account (increments destination balance)

Both cached balances update atomically within the same transaction.

### Category Reassignment

When a category is deleted and transactions are reassigned to "general":
- Budget consumption for the OLD budget is decremented
- Budget consumption for any budget tracking "general" is incremented

### Account Reassignment

When an account is deleted and transactions are reassigned:
- Source account balance becomes 0 (all transactions moved)
- Target account balance is recalculated with new transactions
