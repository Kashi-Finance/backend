# Currency Validation RPCs

## Overview

Currency RPCs enforce the single-currency-per-user policy. The user's `profile.currency_preference` is the source of truth for all financial entities.

---

## `validate_user_currency`

**Purpose:** Validates that a currency code matches the user's profile.currency_preference.

**Signature:**
```sql
CREATE OR REPLACE FUNCTION validate_user_currency(
  p_user_id uuid,
  p_currency text
)
RETURNS boolean
```

**Security:** `SECURITY DEFINER`

**Behavior:**
1. Fetches user's `currency_preference` from profile
2. Raises exception if profile not found
3. Raises exception if `p_currency != currency_preference`
4. Returns `true` if validation passes

**Usage:**
```python
try:
    supabase_client.rpc(
        'validate_user_currency',
        {'p_user_id': user_id, 'p_currency': 'USD'}
    ).execute()
except Exception as e:
    if "Currency mismatch" in str(e):
        raise ValueError("Currency doesn't match profile")
```

---

## `get_user_currency`

**Purpose:** Returns the user's currency_preference from their profile.

**Signature:**
```sql
CREATE OR REPLACE FUNCTION get_user_currency(
  p_user_id uuid
)
RETURNS text
```

**Security:** `SECURITY DEFINER`

**Behavior:**
1. Fetches user's `currency_preference` from profile
2. Raises exception if profile not found
3. Returns the currency code (e.g., "GTQ", "USD")

**Usage:**
```python
result = supabase_client.rpc(
    'get_user_currency',
    {'p_user_id': user_id}
).execute()
currency = result.data  # e.g., "GTQ"
```

---

## `can_change_user_currency`

**Purpose:** Checks if a user can safely change their currency_preference. Returns `false` if user has any accounts, wishlists, or budgets.

**Signature:**
```sql
CREATE OR REPLACE FUNCTION can_change_user_currency(
  p_user_id uuid
)
RETURNS boolean
```

**Security:** `SECURITY DEFINER`

**Behavior:**
1. Checks for non-deleted accounts
2. Checks for wishlists (no soft-delete)
3. Checks for non-deleted budgets
4. Returns `false` if any exist, `true` otherwise

**Usage:**
```python
result = supabase_client.rpc(
    'can_change_user_currency',
    {'p_user_id': user_id}
).execute()

if not result.data:
    raise ValueError("Cannot change currency with existing financial data")
```

**Notes:**
- This enforces the rule that currency can only be changed before creating any financial data
- After creating accounts, wishlists, or budgets, user must delete all to change currency
