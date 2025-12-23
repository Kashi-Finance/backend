# Engagement API

> **Domain:** Streak tracking and gamification features
> 
> **Index:** [API-endpoints.md](../../API-endpoints.md#11-engagement)

---

## Overview

The Engagement API provides streak tracking to encourage daily financial logging. Streaks are automatically updated when users log transactions or commit invoices.

**Key Concepts:**
- **Streak**: Consecutive days with at least one financial activity
- **Streak Freeze**: One free "miss day" protection per week
- **Activity**: Creating a transaction or committing an invoice

---

## Endpoints

### GET /engagement/streak

Get full streak status with risk assessment.

**Authentication:** Required (Bearer token)

**Response:** `StreakStatusResponse`

```json
{
  "current_streak": 7,
  "longest_streak": 14,
  "last_activity_date": "2025-12-01",
  "streak_freeze_available": true,
  "streak_at_risk": false,
  "days_until_streak_break": 2
}
```

**Response Fields:**

| Field | Type | Description |
|-------|------|-------------|
| `current_streak` | integer | Current consecutive days with activity |
| `longest_streak` | integer | All-time personal best |
| `last_activity_date` | date \| null | Last date of financial activity (UTC) |
| `streak_freeze_available` | boolean | Whether freeze protection is available |
| `streak_at_risk` | boolean | True if no activity logged today |
| `days_until_streak_break` | integer \| null | Days before streak breaks (0 = end of today) |

**Use Cases:**
- Display streak widget on home screen
- Show "at risk" warning to encourage logging
- Check freeze availability before showing reminder

---

### GET /engagement/summary

Get condensed engagement stats for dashboard display.

**Authentication:** Required (Bearer token)

**Response:** `EngagementSummary`

```json
{
  "current_streak": 7,
  "longest_streak": 14,
  "streak_at_risk": false,
  "streak_freeze_available": true,
  "has_logged_today": true
}
```

**Response Fields:**

| Field | Type | Description |
|-------|------|-------------|
| `current_streak` | integer | Current consecutive days |
| `longest_streak` | integer | All-time record |
| `streak_at_risk` | boolean | Needs attention today |
| `streak_freeze_available` | boolean | Freeze protection status |
| `has_logged_today` | boolean | True if user logged activity today |

**Use Cases:**
- Quick dashboard card
- Check if user needs reminder notification
- Show completion status for the day

---

### GET /engagement/budget-score

Get budget health score based on active budget adherence.

**Authentication:** Required (Bearer token)

**Response:** `BudgetScoreResponse`

```json
{
  "score": 85,
  "trend": "up",
  "budgets_on_track": 3,
  "budgets_warning": 1,
  "budgets_over": 0,
  "total_budgets": 4,
  "breakdown": [
    {
      "budget_id": "b1234567-89ab-cdef-0123-456789abcdef",
      "budget_name": "Groceries Monthly",
      "category_name": "Food & Groceries",
      "limit_amount": 2000.00,
      "consumed_amount": 1450.00,
      "utilization": 0.725,
      "score": 100,
      "status": "on_track"
    }
  ],
  "perfect_week": false,
  "message": "Great job! 3 of 4 budgets are on track."
}
```

**Response Fields:**

| Field | Type | Description |
|-------|------|-------------|
| `score` | integer (0-100) | Overall budget health score |
| `trend` | string | Score trend vs last week: `up`, `down`, `stable` |
| `budgets_on_track` | integer | Budgets under 75% of limit |
| `budgets_warning` | integer | Budgets at 75-100% of limit |
| `budgets_over` | integer | Budgets over limit |
| `total_budgets` | integer | Total active budgets |
| `breakdown` | array | Per-budget score details |
| `perfect_week` | boolean | True if score=100 for 7 consecutive days |
| `message` | string | Human-readable summary |

**Breakdown Item Fields:**

| Field | Type | Description |
|-------|------|-------------|
| `budget_id` | string (UUID) | Budget identifier |
| `budget_name` | string | Budget display name |
| `category_name` | string \| null | Associated category name |
| `limit_amount` | number | Budget limit amount |
| `consumed_amount` | number | Current period consumption |
| `utilization` | number | Consumption ratio (0.0 to 1.0+) |
| `score` | integer (0-100) | Individual budget score |
| `status` | string | `on_track`, `warning`, or `over` |

**Scoring Logic:**

| Utilization | Score | Status |
|-------------|-------|--------|
| 0-75% | 100 | `on_track` |
| 75-100% | 100 → 75 (linear) | `warning` |
| 100%+ | 75 → 0 (penalty) | `over` |

**Edge Cases:**

- No budgets: Returns score=100, empty breakdown
- All budgets on track: score=100, `perfect_week` may be true
- Budget with limit_amount=0: Treated as 0% utilization

**Use Cases:**
- Budget health dashboard widget
- Color coding (green 80+, yellow 50-79, red <50)
- Weekly trend visualization
- Spending alerts and notifications

---

## Automatic Streak Updates

Streaks are updated automatically by the backend when:

1. **Creating a transaction:** `POST /transactions`
2. **Committing an invoice:** `POST /invoices/commit`

The update happens after successful persistence and:
- Is non-blocking (won't fail the main operation)
- Updates `current_streak`, `longest_streak`, `last_activity_date`
- May use streak freeze if applicable

**Update Response (internal):**

```json
{
  "current_streak": 8,
  "longest_streak": 14,
  "streak_continued": true,
  "streak_frozen": false,
  "new_personal_best": false
}
```

---

## Profile Integration

Streak fields are included in the profile response (`GET /profile`):

```json
{
  "user_id": "...",
  "first_name": "...",
  "current_streak": 7,
  "longest_streak": 14,
  "last_activity_date": "2025-12-01",
  "streak_freeze_available": true,
  "streak_freeze_used_this_week": false,
  "created_at": "...",
  "updated_at": "..."
}
```

This allows the UI to display streak data without an extra API call.

---

## Streak Mechanics

### Streak Calculation

| Scenario | Effect |
|----------|--------|
| First activity ever | Streak starts at 1 |
| Logged today already | No change (idempotent) |
| Logged yesterday | Streak increments |
| Missed 1 day + freeze available | Freeze used, streak continues |
| Missed 1+ day + no freeze | Streak resets to 1 |

### Streak Freeze

- One free freeze per week
- Automatically used if needed (no manual action)
- Resets every Monday (UTC)
- Tracked via `streak_freeze_used_this_week` flag

### RPC Functions

The backend uses PostgreSQL RPC functions for atomic operations:

| Function | Purpose |
|----------|---------|
| `update_user_streak(user_id)` | Update streak after activity |
| `get_user_streak(user_id)` | Get streak with risk assessment |
| `reset_weekly_streak_freezes()` | Cron job to reset freezes |

---

## Error Handling

| Status | Error | Description |
|--------|-------|-------------|
| 401 | `unauthorized` | Missing or invalid token |
| 500 | `streak_fetch_failed` | Database error |
| 500 | `engagement_fetch_failed` | Profile fetch error |

---

## Handling "No Expense" Days

**Question:** What happens when a user genuinely has no purchases or expenses on a given day?

**Current Behavior:** Streak breaks unless the user has a streak freeze available.

### Solutions in Current Implementation

1. **Streak Freeze (Available Now)**
   - Users get 1 free freeze per week
   - Automatically used when streak would break
   - Covers up to 1 "off day" per week

2. **Log Income Instead**
   - Any transaction (income or expense) counts as activity
   - Users can log expected income for the day

### Future Enhancement: "No Expenses Check-in" (Proposed)

For users who are genuinely frugal or have days without any financial activity:

```
POST /engagement/check-in
{
  "type": "no_expenses",
  "note": "Optional user note about the day"
}
```

**Proposed Rules:**
- Available once per day
- Only visible after 6 PM local time
- Counts as financial activity for streak
- Tracked separately for analytics

**UI Mockup:**
```
┌────────────────────────────────┐
│  💰 No expenses today?         │
│                                │
│  Great job being mindful!      │
│  Check in to keep your streak. │
│                                │
│  [✓ I had no expenses today]   │
└────────────────────────────────┘
```

> **Implementation Status:** Not yet implemented. Current MVP relies on streak freeze.

---

## UI Integration Guidelines

### Home Screen

1. Call `GET /engagement/summary` on app launch
2. Show streak count with fire emoji 🔥
3. If `streak_at_risk`, show warning indicator
4. If `has_logged_today`, show checkmark ✅

### Streak Widget

```
┌────────────────────────┐
│  🔥 7 day streak       │
│  Personal best: 14     │
│  ✅ Logged today       │
└────────────────────────┘
```

### Risk Warning

When `streak_at_risk` is true:
```
┌────────────────────────┐
│  ⚠️ Log today to       │
│  keep your streak!     │
│  [Log expense]         │
└────────────────────────┘
```

### Freeze Indicator

When `streak_freeze_available` is false:
```
┌────────────────────────┐
│  🧊 Freeze used        │
│  Resets Monday         │
└────────────────────────┘
```

---

## Related Documentation

- [Profile API](./auth-profile.md) - Profile includes streak fields
- [Transactions API](./transactions.md) - Creating transactions updates streak
- [Invoices API](./invoices.md) - Committing invoices updates streak
