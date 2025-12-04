# Frontend Guide: Recurring Transactions Sync

> **Optimal strategy for syncing recurring transactions on app launch**

## Table of Contents

1. [Overview](#overview)
2. [The Sync Endpoint](#the-sync-endpoint)
3. [Optimal Sync Strategy](#optimal-sync-strategy)
4. [Handling Multiple Pending Transactions](#handling-multiple-pending-transactions)
5. [User Notification Patterns](#user-notification-patterns)
6. [Example Flows](#example-flows)
7. [Integration Checklist](#integration-checklist)

---

## Overview

Recurring transactions are **templates** that define when transactions should be automatically generated. The sync endpoint generates all pending transactions **atomically** in a single API call.

### Key Concepts

| Term | Description |
|------|-------------|
| **Recurring Rule** | Template defining frequency, amount, account, etc. |
| **`next_run_date`** | The next date when a transaction should be generated |
| **Sync** | Single atomic operation that generates transactions AND updates caches |
| **Paired Transfers** | Recurring transfers create linked transactions automatically |

### Why This Architecture?

- **Single API call** handles everything (no separate balance/budget refresh needed)
- **Atomic operation** - all changes happen in one database transaction
- **Efficient batching** - account/budget updates happen once per affected entity
- **Mobile-optimized** - minimize network calls on app launch

---

## The Sync Endpoint

### `POST /transactions/sync-recurring`

**Purpose:** Generate all pending transactions AND update all affected caches in ONE call.

**Request:**
```json
{
  "sync_date": "2025-12-04"
}
```

**Response:**
```json
{
  "status": "SYNCED",
  "transactions_generated": 5,
  "rules_processed": 2,
  "accounts_updated": 3,
  "budgets_updated": 1,
  "message": "Generated 5 transactions from 2 recurring rules. Updated 3 accounts and 1 budgets."
}
```

### What Happens During Sync (All Atomic)

```
┌────────────────────────────────────────────────────────────────────┐
│  sync_recurring_transactions(user_id, today)                       │
│                                                                     │
│  PHASE 1: Generate Transactions                                    │
│  ├─► For each active rule where next_run_date <= today:            │
│  │   ├─► If PAIRED (transfer): Generate linked transactions        │
│  │   │   └─► Both txns linked via paired_transaction_id            │
│  │   └─► If STANDALONE: Generate single transaction                │
│  ├─► Track affected accounts and categories                        │
│  └─► Update next_run_date on each rule                             │
│                                                                     │
│  PHASE 2: Update Account Balances (batch)                          │
│  └─► Recompute cached_balance ONCE per affected account            │
│                                                                     │
│  PHASE 3: Update Budget Consumption (batch)                        │
│  ├─► Only for OUTCOME transactions (income doesn't consume budget) │
│  ├─► Transfers do NOT affect budgets (correct behavior)            │
│  └─► Recompute cached_consumption ONCE per affected budget         │
│                                                                     │
│  RETURN: { transactions, rules, accounts, budgets }                 │
└────────────────────────────────────────────────────────────────────┘
```

### Key Behaviors

| Scenario | Behavior |
|----------|----------|
| **Recurring Transfer** | Creates TWO linked transactions (via `paired_transaction_id`) |
| **Outcome Transaction** | Updates account balance AND budget consumption |
| **Income Transaction** | Updates account balance ONLY (no budget impact) |
| **Transfer** | Updates BOTH account balances, NO budget impact |
| **3-month gap** | Generates ALL missed transactions (uses WHILE loop) |

---

## Optimal Sync Strategy

### ✅ RECOMMENDED: Single Sync on Splash Screen

The most efficient approach is to call sync **once** from the splash screen:

```dart
class SplashScreen extends StatefulWidget {
  @override
  _SplashScreenState createState() => _SplashScreenState();
}

class _SplashScreenState extends State<SplashScreen> {
  @override
  void initState() {
    super.initState();
    _initializeApp();
  }
  
  Future<void> _initializeApp() async {
    // 1. Check authentication
    final isAuthenticated = await authService.checkAuth();
    if (!isAuthenticated) {
      Navigator.pushReplacementNamed(context, '/login');
      return;
    }
    
    // 2. Sync recurring transactions (handles everything!)
    final syncResult = await recurringService.sync();
    
    // 3. Show notification if transactions were generated
    if (syncResult.transactionsGenerated > 0) {
      _showSyncNotification(syncResult);
    }
    
    // 4. Navigate to dashboard (all data is now fresh)
    Navigator.pushReplacementNamed(context, '/dashboard');
  }
}
```

### Why Splash Screen?

| Benefit | Explanation |
|---------|-------------|
| **One API call** | Sync does everything: transactions + balances + budgets |
| **User expects loading** | Splash screen is natural place for initialization |
| **No redundant fetches** | Dashboard shows fresh data immediately |
| **Simpler frontend** | No need to coordinate multiple refresh calls |

### Throttling (Still Recommended)

Even with splash-screen sync, implement throttling for edge cases:

```dart
class RecurringSyncManager {
  static const _minSyncInterval = Duration(minutes: 5);
  DateTime? _lastSyncTime;
  
  Future<SyncResult?> syncIfNeeded() async {
    final now = DateTime.now();
    
    // Skip if synced recently (handles quick app restarts)
    if (_lastSyncTime != null && 
        now.difference(_lastSyncTime!) < _minSyncInterval) {
      return null; // Cached data is still fresh
    }
    
    final result = await _performSync();
    _lastSyncTime = now;
    return result;
  }
  
  // Force sync ignores throttle (used for pull-to-refresh)
  Future<SyncResult> forceSync() async {
    final result = await _performSync();
    _lastSyncTime = DateTime.now();
    return result;
  }
}
```

### When to Force Sync

| Trigger | Action |
|---------|--------|
| App launch (splash) | `syncIfNeeded()` |
| Pull-to-refresh on dashboard | `forceSync()` |
| Navigate to recurring rules screen | `forceSync()` |
| After creating/editing recurring rule | `forceSync()` |
| App was backgrounded > 24 hours | `forceSync()` |

---

## Handling Multiple Pending Transactions

### Scenario: User Returns After 3 Months

User has monthly salary + weekly savings transfer. Opens app after 3 months:

```
Before Sync:
├── Salary rule: next_run_date = 2025-09-01
├── Savings transfer: next_run_date = 2025-09-01 (paired)
├── Today: 2025-12-04
└── Pending: 3 salary + 12 weeks of transfers

After Sync (single API call):
├── Transactions created: 3 salary + 24 transfer txns = 27 total
│   ├── 2025-09-01: Salary +Q5,000
│   ├── 2025-09-01: Transfer -Q500 (checking) ←→ Transfer +Q500 (savings)
│   ├── 2025-10-01: Salary +Q5,000
│   ├── 2025-10-01: Transfer -Q500 ←→ Transfer +Q500
│   ├── ... (all weekly transfers)
│   └── 2025-12-01: Salary +Q5,000
├── Accounts updated: 2 (checking, savings)
├── Budgets updated: 0 (transfers don't affect budgets)
└── next_run_dates: All advanced to next future date
```

### Response:

```json
{
  "status": "SYNCED",
  "transactions_generated": 27,
  "rules_processed": 2,
  "accounts_updated": 2,
  "budgets_updated": 0,
  "message": "Generated 27 transactions from 2 recurring rules. Updated 2 accounts and 0 budgets."
}
```

---

## User Notification Patterns

### After Sync (Splash → Dashboard)

```dart
void _showSyncNotification(SyncResult result) {
  if (result.transactionsGenerated == 0) {
    // No notification needed
    return;
  }
  
  if (result.transactionsGenerated <= 5) {
    // Brief toast
    showToast('${result.transactionsGenerated} recurring transactions synced');
  } else {
    // Dialog for many transactions
    showDialog(
      title: 'Recurring Transactions Synced',
      message: '''
        Generated ${result.transactionsGenerated} transactions 
        from ${result.rulesProcessed} recurring rules.
        
        ${result.accountsUpdated} accounts updated.
        ${result.budgetsUpdated} budgets updated.
      ''',
      actions: [
        DialogAction('View Transactions', () => navigateTo('/transactions?filter=recurring_sync')),
        DialogAction('Dismiss', () => {}),
      ],
    );
  }
}
```

### Transaction List Indicators

Mark auto-generated transactions in UI:
- Badge/icon showing "recurring" source
- Filter option: `system_generated_key = 'recurring_sync'`
- Group by source recurring rule when filtering

---

## Example Flows

### Flow 1: Normal Daily Open

```
User opens app (synced 2 hours ago)
    │
    ▼
Splash: syncIfNeeded() → Skip (throttled, < 5 min)
    │
    ▼
Dashboard shows cached data (still fresh from last sync)
```

### Flow 2: First Open After Weekend

```
User opens app Monday (last sync: Friday 6pm)
    │
    ▼
Splash: syncIfNeeded() → Proceed (gap > 5 min)
    │
    ├─► POST /transactions/sync-recurring
    │
    ├─► Response: { transactions_generated: 0 }
    │   (No rules scheduled for weekend)
    │
    ▼
Dashboard shows fresh data (no notification needed)
```

### Flow 3: Open After 3 Weeks Vacation

```
User opens app (last sync: 3 weeks ago)
    │
    ▼
Splash: syncIfNeeded() → Proceed
    │
    ├─► POST /transactions/sync-recurring
    │
    ├─► Response: {
    │     transactions_generated: 15,
    │     rules_processed: 4,
    │     accounts_updated: 3,
    │     budgets_updated: 2
    │   }
    │
    ├─► All account balances now correct
    ├─► All budget consumptions now correct
    │
    ▼
Show dialog: "15 transactions synced from 4 rules"
    │
    ├─► [View] → Navigate to transaction list
    └─► [OK] → Continue to dashboard (data is fresh)
```

### Flow 4: Pull-to-Refresh on Dashboard

```
User pulls to refresh on dashboard
    │
    ▼
forceSync() → Always proceeds
    │
    ├─► POST /transactions/sync-recurring
    │
    ├─► Response: { transactions_generated: 0 }
    │
    ▼
Refresh dashboard data (account list, budgets, etc.)
    │
    ▼
Brief toast: "Everything up to date"
```

---

## Integration Checklist

### Splash Screen Setup
- [ ] Call `syncIfNeeded()` on splash screen after auth check
- [ ] Show loading indicator during sync
- [ ] Handle sync errors gracefully (offline mode)
- [ ] Show notification if `transactions_generated > 0`

### Sync Manager
- [ ] Implement 5-minute throttle for `syncIfNeeded()`
- [ ] Implement `forceSync()` for manual refresh
- [ ] Track `_lastSyncTime` in memory (resets on app restart)
- [ ] Consider persistent storage for `_lastSyncTime` (optional)

### Dashboard Integration
- [ ] Pull-to-refresh calls `forceSync()`
- [ ] No need to manually refresh accounts/budgets after sync
- [ ] Display sync timestamp if desired ("Last synced: 2 min ago")

### Transaction List
- [ ] Support filter by `system_generated_key = 'recurring_sync'`
- [ ] Show recurring icon/badge on synced transactions
- [ ] Paired transfers display correctly (linked via `paired_transaction_id`)

### Testing Scenarios
- [ ] Normal daily usage (throttle works)
- [ ] Week gap (few transactions)
- [ ] Month gap (many transactions)
- [ ] Recurring transfer sync (paired correctly)
- [ ] Budget consumption updates (outcome only)
- [ ] Error handling (network failure during sync)
