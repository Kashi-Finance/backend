# PostgreSQL Enums

> Type-safe enum definitions used across the database.

---

## account_type_enum

Account types for financial accounts.

| Value | Description |
|:------|:------------|
| `cash` | Physical cash or wallet |
| `bank` | Checking or savings account |
| `credit_card` | Credit card account |
| `loan` | Loan account |
| `remittance` | Remittance/transfer account |
| `crypto` | Cryptocurrency wallet |
| `investment` | Investment/brokerage account |

**Used by:** `account.type`

---

## flow_type_enum

Direction of money flow.

| Value | Description |
|:------|:------------|
| `income` | Money coming in (positive) |
| `outcome` | Money going out (negative) |

**Used by:** `transaction.flow_type`, `category.flow_type`, `recurring_transaction.flow_type`

---

## budget_frequency_enum

Budget recurrence frequency.

| Value | Description |
|:------|:------------|
| `once` | One-time budget |
| `daily` | Repeats daily |
| `weekly` | Repeats weekly |
| `monthly` | Repeats monthly |
| `yearly` | Repeats yearly |

**Used by:** `budget.frequency`

---

## recurring_frequency_enum

Recurring transaction frequency.

| Value | Description |
|:------|:------------|
| `daily` | Repeats daily |
| `weekly` | Repeats weekly |
| `monthly` | Repeats monthly |
| `yearly` | Repeats yearly |

**Used by:** `recurring_transaction.frequency`

**Note:** Unlike `budget_frequency_enum`, this does not include `once` because a one-time transaction is just a regular transaction.

---

## wishlist_status_enum

Wishlist goal status.

| Value | Description |
|:------|:------------|
| `active` | Goal is active |
| `purchased` | Goal has been achieved/purchased |
| `abandoned` | Goal has been abandoned |

**Used by:** `wishlist.status`

---

## Enum Modification Rules

1. **Add values via migration** — Always use `ALTER TYPE ... ADD VALUE`
2. **Never remove values** — PostgreSQL doesn't support removing enum values easily
3. **Order matters for some operations** — New values are added at the end by default
4. **Test thoroughly** — Enum changes can break application code

**Example migration to add a value:**

```sql
ALTER TYPE account_type_enum ADD VALUE 'savings' AFTER 'bank';
```
