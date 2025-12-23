# Favorite Account RPCs

## Overview

Favorite account RPCs manage the user's preferred default account for transaction creation. Only one account per user can be marked as favorite.

---

## `set_favorite_account`

**Purpose:** Sets an account as the user's favorite, automatically unsetting any previous favorite.

**Signature:**
```sql
CREATE OR REPLACE FUNCTION set_favorite_account(
  p_account_id uuid,
  p_user_id uuid
)
RETURNS TABLE(
  previous_favorite_id uuid,
  new_favorite_id uuid,
  success boolean
)
```

**Security:** `SECURITY DEFINER`

**Behavior:**
1. Validates account exists and belongs to user
2. Finds current favorite (if any)
3. If requested account is already favorite, returns success with no changes
4. Unsets previous favorite's `is_favorite` flag
5. Sets new account's `is_favorite` to true
6. Returns previous and new favorite IDs

**Usage:**
```python
result = supabase_client.rpc(
    'set_favorite_account',
    {
        'p_account_id': account_uuid,
        'p_user_id': user_uuid
    }
).execute()

row = result.data[0]
# row['previous_favorite_id'] - UUID of previously favorite account (or None)
# row['new_favorite_id'] - UUID of newly favorited account
# row['success'] - always True if no exception
```

**Notes:**
- Only one account per user can be marked as favorite
- Safe for concurrent calls (atomic operation)
- Returns previous_favorite_id as None if no previous favorite

---

## `clear_favorite_account`

**Purpose:** Clears the favorite status from a specific account.

**Signature:**
```sql
CREATE OR REPLACE FUNCTION clear_favorite_account(
  p_account_id uuid,
  p_user_id uuid
)
RETURNS TABLE(
  cleared boolean
)
```

**Security:** `SECURITY DEFINER`

**Behavior:**
1. Validates account exists and belongs to user
2. If account is not favorite, returns `cleared = false`
3. Sets `is_favorite = false` on account
4. Returns `cleared = true`

**Usage:**
```python
result = supabase_client.rpc(
    'clear_favorite_account',
    {
        'p_account_id': account_uuid,
        'p_user_id': user_uuid
    }
).execute()

was_cleared = result.data[0]['cleared']  # True if status was changed
```

---

## `get_favorite_account`

**Purpose:** Returns the UUID of the user's favorite account, or NULL if none set.

**Signature:**
```sql
CREATE OR REPLACE FUNCTION get_favorite_account(
  p_user_id uuid
)
RETURNS uuid
```

**Security:** `SECURITY DEFINER`

**Behavior:**
1. Finds account with `is_favorite = true` for user
2. Returns account UUID or NULL

**Usage:**
```python
result = supabase_client.rpc(
    'get_favorite_account',
    {'p_user_id': user_uuid}
).execute()

favorite_account_id = result.data  # UUID or None
```
