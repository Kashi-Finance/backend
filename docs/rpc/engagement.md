# Engagement & Streak RPCs

> Full detailed documentation for the Engagement feature's RPC functions.
>
> Quick reference: [RPC-documentation.md (Section 13)](../../RPC-documentation.md#13-engagement--streak)

---

## Overview

The Engagement RPCs implement a **daily activity streak system with freeze protection**. These functions are automatically called after successful transactions and invoices to maintain user engagement metrics.

**Total RPCs:** 3

| Function | Purpose | Scope |
|----------|---------|-------|
| `update_user_streak` | Update user's streak after activity | Per-transaction |
| `get_user_streak` | Retrieve current streak status | Query-only |
| `reset_weekly_streak_freezes` | Reset all user freezes (scheduled) | Admin/Cron |

---

## `update_user_streak`

**Purpose:** Updates a user's streak after logging a financial transaction or invoice. Called automatically by the API layer after successful activity logging.

**Signature:**
```sql
CREATE OR REPLACE FUNCTION update_user_streak(
  p_user_id uuid
)
RETURNS TABLE(
  current_streak INT,
  longest_streak INT,
  streak_continued BOOLEAN,
  streak_frozen BOOLEAN,
  new_personal_best BOOLEAN
)
```

**Security:** `SECURITY DEFINER` (validates ownership via `user_id`)

**Parameters:**
- `p_user_id` (uuid, required) — User to update (from Supabase Auth)

**Return Fields:**
- `current_streak` (int) — User's current streak count (after update)
- `longest_streak` (int) — User's all-time record streak
- `streak_continued` (boolean) — Was the streak extended? (true if new activity logged)
- `streak_frozen` (boolean) — Was freeze used in this update? (true if freeze applied)
- `new_personal_best` (boolean) — Is current_streak a new personal record?

**Behavior:**

1. **Fetch current streak state** from `profile` table:
   - `current_streak`, `longest_streak`, `last_activity_date`
   - `streak_freeze_available`, `streak_freeze_used_this_week`

2. **Calculate days since last activity:**
   ```
   days_since_activity = TODAY - last_activity_date
   ```

3. **Apply streak logic based on days_since_activity:**

   | Condition | Action | Result |
   |-----------|--------|--------|
   | `last_activity_date IS NULL` | Set streak = 1 | New user, first activity |
   | `days_since_activity = 0` | No change | Already logged today |
   | `days_since_activity = 1` | Increment streak | Continuous streak continues |
   | `days_since_activity = 2 AND freeze_available` | Use freeze, increment | Preserve streak via freeze (freeze now used) |
   | `days_since_activity >= 2` (no freeze) or `days_since_activity >= 3` | Reset to 1 | Streak broken |

4. **Update longest_streak** if `current_streak > longest_streak`

5. **Update profile** with new streak state:
   - Set `current_streak` to calculated value
   - Set `longest_streak` to max(current_streak, longest_streak)
   - Set `last_activity_date = TODAY`
   - Mark streak fields updated (set `updated_at = now()`)

6. **Return updated streak data** to caller

**Usage:**

```python
# Python - Supabase client
result = supabase.rpc('update_user_streak', {
    'p_user_id': user_uuid
}).execute()

if result.data:
    streak_update = result.data[0]
    print(f"Current streak: {streak_update['current_streak']}")
    print(f"Personal best: {streak_update['longest_streak']}")
    print(f"Freeze used: {streak_update['streak_frozen']}")
    
    if streak_update['new_personal_best']:
        print("🏆 New personal best!")
else:
    print("No data returned (should not happen)")
```

**Example Scenarios:**

```
Scenario 1: User logs first transaction ever
- last_activity_date: NULL → current_streak = 1
- Returns: (1, 1, True, False, True)

Scenario 2: User logs on consecutive days
- last_activity_date: 2025-12-01, today: 2025-12-02
- days_since = 1 → current_streak = 8 + 1 = 9
- Returns: (9, 14, True, False, False)

Scenario 3: User missed 1 day but has freeze available
- last_activity_date: 2025-12-01, today: 2025-12-03
- days_since = 2, freeze_available = true
- Use freeze → current_streak = 8 + 1 = 9
- Returns: (9, 14, True, True, False)
- Note: streak_freeze_used_this_week = true, streak_freeze_available = false

Scenario 4: User missed 1+ days without freeze (or missed 2+ days)
- last_activity_date: 2025-12-01, today: 2025-12-04 (3 days)
- days_since = 3, freeze_available = true (not used yet)
- Streak broken → current_streak = 1
- Returns: (1, 20, False, False, False)
- Note: Freeze remains available because we didn't get a chance to use it

Scenario 5: User missed 1 day, already used freeze this week
- last_activity_date: 2025-12-06, today: 2025-12-08 (2 days)
- days_since = 2, freeze_available = false (already used Monday)
- Streak broken → current_streak = 1
- Returns: (1, 20, False, False, False)
```

**Error Handling:**

- **User not found** → Raises `NO_DATA_FOUND` exception
- **Profile not found** → Raises `PROFILE_NOT_FOUND` exception
- Invalid `user_id` format → Database validation error

**Non-Blocking Usage:**

The API layer calls this function **non-blocking** after transaction/invoice creation:

```python
# Inside transactions.py or invoices.py
try:
    await update_streak_after_activity(user_uuid)
except Exception as e:
    logger.warning(f"Streak update failed for user {user_uuid}: {e}")
    # Transaction still succeeds - streak is optional

return TransactionResponse(...)  # Successful response regardless
```

---

## `get_user_streak`

**Purpose:** Retrieves current streak status including risk assessment for UI display.

**Signature:**
```sql
CREATE OR REPLACE FUNCTION get_user_streak(
  p_user_id uuid
)
RETURNS TABLE(
  current_streak INT,
  longest_streak INT,
  last_activity_date DATE,
  streak_freeze_available BOOLEAN,
  streak_at_risk BOOLEAN,
  days_until_streak_break INT
)
```

**Security:** `SECURITY DEFINER` (validates ownership via `user_id`)

**Parameters:**
- `p_user_id` (uuid, required) — User to query (from Supabase Auth)

**Return Fields:**
- `current_streak` (int) — User's current active streak
- `longest_streak` (int) — User's all-time record
- `last_activity_date` (date) — Last day user logged activity
- `streak_freeze_available` (boolean) — Does user have a freeze available?
- `streak_at_risk` (boolean) — Is streak at risk of breaking?
- `days_until_streak_break` (int) — Days remaining before streak resets (0 if at risk)

**Behavior:**

1. **Fetch streak data** from `profile`:
   - `current_streak`, `longest_streak`, `last_activity_date`
   - `streak_freeze_available`

2. **Calculate risk indicators:**
   ```
   days_since = TODAY - last_activity_date
   
   streak_at_risk = (days_since == 1)  # Will break tomorrow
   days_until_break = MAX(0, 2 - days_since)  # 1 day left before reset
   ```

3. **Return complete status** with all fields

**Usage:**

```python
# Python - Supabase client
result = supabase.rpc('get_user_streak', {
    'p_user_id': user_uuid
}).execute()

if result.data:
    status = result.data[0]
    
    # Display in UI
    print(f"🔥 Streak: {status['current_streak']} days")
    print(f"🏆 Best: {status['longest_streak']} days")
    print(f"Last activity: {status['last_activity_date']}")
    
    # Show risk indicators
    if status['streak_at_risk']:
        print("⚠️ Streak at risk! Log an activity today to continue")
        print(f"⏰ {status['days_until_streak_break']} day left")
    
    # Show freeze status
    if status['streak_freeze_available']:
        print("❄️ You have 1 freeze available")
    else:
        print("❄️ Freeze already used this week")
```

**Example Scenarios:**

```
Scenario 1: User is up-to-date
- last_activity_date: 2025-12-02, today: 2025-12-02
- days_since = 0
- Returns: (7, 14, 2025-12-02, True, False, 1)

Scenario 2: User is at risk (last activity yesterday)
- last_activity_date: 2025-12-01, today: 2025-12-02
- days_since = 1
- Returns: (7, 14, 2025-12-01, True, True, 0)

Scenario 3: User's streak is broken
- last_activity_date: 2025-11-30, today: 2025-12-02
- days_since = 2
- Returns: (1, 14, 2025-11-30, True, False, 0)

Scenario 4: User has no freeze available
- Used freeze this week
- Returns: (..., False, ...)
```

**UI Integration:**

This RPC is called:
- When opening the app (check current streak)
- When displaying dashboard/engagement card
- On engagement detail screen
- To determine whether to show risk warnings

---

## `reset_weekly_streak_freezes`

**Purpose:** Resets freeze availability for all users at the start of each week. Called by pg_cron scheduler, **not accessible from authenticated client**.

**Signature:**
```sql
CREATE OR REPLACE FUNCTION reset_weekly_streak_freezes()
RETURNS INT
```

**Security:** `SECURITY DEFINER` (admin function only)

**No parameters** — system-wide operation

**Return Value:**
- INT — Count of users whose freeze availability was reset

**Behavior:**

1. **Find all users who used their freeze this week:**
   ```sql
   WHERE streak_freeze_used_this_week = TRUE
   ```

2. **Reset for each user:**
   - Set `streak_freeze_available = TRUE`
   - Set `streak_freeze_used_this_week = FALSE`

3. **Return count** of updated rows

**Scheduling (pg_cron):**

```sql
-- Call every Monday at 00:00 UTC
SELECT cron.schedule(
  'reset-streak-freezes-weekly',
  '0 0 * * MON',  -- Monday 00:00 UTC
  'SELECT reset_weekly_streak_freezes()'
);
```

**Usage:**

```python
# This function is NOT called from authenticated client
# It's called by pg_cron scheduler on the backend

# If you need to manually reset (admin only):
result = supabase.rpc('reset_weekly_streak_freezes').execute()
count_reset = result.data  # e.g., 1250 users
print(f"Reset freeze for {count_reset} users")
```

**Error Handling:**

- **Permission denied** — Only callable by scheduler/admin, not authenticated users
- Returns 0 if no users need reset

**Monitoring:**

```sql
-- Check recent freeze resets
SELECT 
  COUNT(*) as users_reset,
  MAX(updated_at) as last_reset
FROM profile
WHERE streak_freeze_used_this_week = FALSE 
  AND streak_freeze_available = TRUE;
```

---

## Integration with Transaction/Invoice Routes

**Automatic Streak Updates:**

The backend automatically calls `update_user_streak` after successful transaction or invoice logging. This is handled by the `engagement_service.py`:

```python
# In transactions.py or invoices.py
from backend.services.engagement_service import update_streak_after_activity

# After successful transaction creation:
await update_streak_after_activity(user_id)  # Non-blocking

# Endpoint returns success regardless of streak update result
```

**Error Handling:**

```python
try:
    result = await update_streak_after_activity(user_id)
    logger.info(f"Streak updated for user: {result}")
except Exception as e:
    logger.warning(f"Streak update failed (non-blocking): {e}")
    # Transaction already succeeded, just log the warning
```

---

## Profile Fields

These RPC functions read and modify these fields on the `profile` table:

| Field | Type | Default | Purpose |
|-------|------|---------|---------|
| `current_streak` | INT | 0 | Current active streak count |
| `longest_streak` | INT | 0 | All-time personal best |
| `last_activity_date` | DATE | NULL | Last day with logged activity |
| `streak_freeze_available` | BOOLEAN | TRUE | Does user have weekly freeze? |
| `streak_freeze_used_this_week` | BOOLEAN | FALSE | Has freeze been used this week? |

---

## Examples

### Example 1: Daily Engagement Flow

```
Monday 2025-12-02, 10:00 AM
User logs a transaction for Q500

1. POST /transactions succeeds
2. Calls update_user_streak(user_id)
3. RPC: last_activity = NULL → current_streak = 1
4. Returns: (current_streak=1, longest_streak=1, streak_continued=True, streak_frozen=False, new_personal_best=True)
5. Frontend shows: "🔥 1-day streak! 🏆 New personal best!"

Tuesday 2025-12-03, 9:00 PM
User logs an invoice

1. POST /invoices succeeds  
2. Calls update_user_streak(user_id)
3. RPC: days_since = 1 (yesterday logged) → current_streak = 1 + 1 = 2
4. Returns: (current_streak=2, longest_streak=2, streak_continued=True, streak_frozen=False, new_personal_best=True)
5. Frontend shows: "🔥 2-day streak! Keep it going 💪"

Wednesday 2025-12-04, no activity

1. User opens app at 11:00 PM
2. GET /engagement/streak calls get_user_streak(user_id)
3. RPC: days_since = 2 (last activity was Tuesday, no activity today), last_activity = 2025-12-03
4. Returns: (current_streak=2, longest_streak=2, streak_at_risk=True, days_until_streak_break=0, streak_freeze_available=True)
5. Frontend shows warning: "⚠️ Your streak is at risk! Log an activity before midnight to continue"

Thursday 2025-12-05, 2:00 AM - MISSED CUTOFF
1. User did not log activity by end of Wednesday
2. Streak was broken on new day (Thursday)

Friday 2025-12-06, 10:00 AM
User logs a transaction
1. POST /transactions succeeds  
2. Calls update_user_streak(user_id)
3. RPC: days_since >= 3 (last was Tuesday) → current_streak = 1 (reset)
4. Returns: (current_streak=1, longest_streak=2, streak_continued=False, streak_frozen=False, new_personal_best=False)
5. Frontend shows: "⚠️ Streak broken. Starting fresh: 🔥 1 day"
```

### Example 2: Using Freeze Protection

```
Friday 2025-12-06, 10:00 AM - User logs transaction
- Current: current_streak=12, longest_streak=14, freeze_available=True
- RPC: days_since = 1 (yesterday logged) → current_streak = 12 + 1 = 13
- Result: Streak continues without using freeze

Saturday 2025-12-07 - NO ACTIVITY
- freeze_available = True (not used yet)
- streak_at_risk will be True if user opens app

Sunday 2025-12-08 - NO ACTIVITY

Monday 2025-12-09, 10:00 AM - User logs a transaction
- RPC: last_activity = 2025-12-06, today = 2025-12-09
- days_since = 3 (Friday → Monday is 3 days)
- PROBLEM: streak would break since days_since >= 3
- SOLUTION: Freeze is available and used
- Wait, actually: days_since = 3 means we already passed the freeze window
  (freeze only works for days_since = 2)
- Result: current_streak resets to 1 (freeze doesn't help)
- freeze_available = True (unused)

---

ALTERNATIVE: Correct scenario with freeze usage

Friday 2025-12-06, 10:00 AM - User logs transaction
- Current: current_streak=12, longest_streak=14, freeze_available=True

Saturday 2025-12-07 - NO ACTIVITY (still good, only 1 day since activity)

Sunday 2025-12-08 - NO ACTIVITY (now 2 days since last activity Friday)

Monday 2025-12-09, 10:00 AM - User logs transaction
- RPC: last_activity = 2025-12-06, today = 2025-12-09
- days_since = 3 (but we need to count from Friday: Fri→Sat=1, Sat→Sun=2, Sun→Mon=3)
- Actually: When we say "last_activity = Friday 2025-12-06"
  - Saturday 2025-12-07: days_since = 1 day
  - Sunday 2025-12-08: days_since = 2 days
  - Monday 2025-12-09: days_since = 3 days
- So at Monday, days_since = 3, which is beyond freeze window
- Result: streak breaks (can't use freeze for 3+ day gaps)

CORRECT SCENARIO:

Friday 2025-12-06, 10:00 AM
- User logs a transaction
- current_streak = 12, freeze_available = True

Saturday 2025-12-07 - NO ACTIVITY (but streak not broken yet)

Sunday 2025-12-08, 10:00 AM - User logs transaction
- RPC: last_activity = 2025-12-06, today = 2025-12-08
- days_since = 2 (Fri→Sat=1, Sat→Sun=2)
- freeze_available = True
- Result: Use freeze, current_streak = 12 + 1 = 13
- Returns: (current_streak=13, streak_frozen=True, new_personal_best=False)
- freeze_available becomes False, streak_freeze_used_this_week = True

Monday 2025-12-16, 00:00 UTC (one week later)
1. pg_cron runs reset_weekly_streak_freezes()
2. All users with used freezes get reset:
   - streak_freeze_available = TRUE
   - streak_freeze_used_this_week = FALSE
3. User can use freeze again next week
```

---

## Testing

**Test Cases:**

1. **First ever activity** — streak should be 1
2. **Consecutive days** — streak should increment
3. **One day missed + freeze available** — streak should continue via freeze
4. **Multiple days missed + no freeze** — streak should reset to 1
5. **Multiple days missed + already used freeze** — streak should reset to 1
6. **Freeze reset at week boundary** — available flag should reset

**Mock Usage:**

```python
def test_update_user_streak_first_activity():
    result = supabase.rpc('update_user_streak', {
        'p_user_id': user_uuid
    }).execute()
    
    assert result.data[0]['current_streak'] == 1
    assert result.data[0]['longest_streak'] == 1
    assert result.data[0]['streak_continued'] == True

def test_get_user_streak_at_risk():
    result = supabase.rpc('get_user_streak', {
        'p_user_id': user_uuid
    }).execute()
    
    assert result.data[0]['streak_at_risk'] == True
    assert result.data[0]['days_until_streak_break'] == 0
```

---

**Last Updated:** December 1, 2025  
**Related:** [RPC-documentation.md](../../RPC-documentation.md), [engagement_service.py](../../backend/services/engagement_service.py)
