# Kashi Finances — API Endpoints Index

> **Quick reference for API endpoints with pointers to detailed documentation.**
> 
> This file follows Anthropic's progressive disclosure pattern: concise index here, full details in [docs/api/](./docs/api/).

---

## Navigation

| Domain | Quick Ref | Full Docs |
|--------|-----------|-----------|
| Auth & Profile | [Section 1](#1-auth--profile) | [docs/api/auth-profile.md](./docs/api/auth-profile.md) |
| Accounts | [Section 2](#2-accounts) | [docs/api/accounts.md](./docs/api/accounts.md) |
| Categories | [Section 3](#3-categories) | [docs/api/categories.md](./docs/api/categories.md) |
| Transactions | [Section 4](#4-transactions) | [docs/api/transactions.md](./docs/api/transactions.md) |
| Invoices | [Section 5](#5-invoices) | [docs/api/invoices.md](./docs/api/invoices.md) |
| Budgets | [Section 6](#6-budgets) | [docs/api/budgets.md](./docs/api/budgets.md) |
| Recurring | [Section 7](#7-recurring-transactions) | [docs/api/recurring.md](./docs/api/recurring.md) |
| Transfers | [Section 8](#8-transfers) | [docs/api/transfers.md](./docs/api/transfers.md) |
| Wishlists | [Section 9](#9-wishlists) | [docs/api/wishlists.md](./docs/api/wishlists.md) |
| Recommendations | [Section 10](#10-recommendations) | [docs/api/recommendations.md](./docs/api/recommendations.md) |
| Engagement | [Section 11](#11-engagement) | [docs/api/engagement.md](./docs/api/engagement.md) |
| Cross-Cutting | [Section 0](#0-authentication--security) | [docs/api/cross-cutting.md](./docs/api/cross-cutting.md) |

---

## 0. Authentication & Security

**All endpoints require \`Authorization: Bearer <token>\` unless marked public.**

\`\`\`http
Authorization: Bearer <access_token>
\`\`\`

**Token flow:**
1. Backend validates token signature (Supabase Auth)
2. Extracts \`user_id\` from token (\`auth.uid()\`)
3. RLS enforces \`user_id = auth.uid()\` on all user-owned rows

**Key rules:**
- Client does NOT send \`user_id\` — extracted from token
- Invalid/expired token → \`401 Unauthorized\`

📖 **Full details:** [docs/api/cross-cutting.md](./docs/api/cross-cutting.md)

---

## 1. Auth & Profile

| Method | Path | Purpose |
|--------|------|---------|
| GET | \`/auth/me\` | Get authenticated user identity |
| GET | \`/profile\` | Get user profile |
| POST | \`/profile\` | Create user profile |
| PATCH | \`/profile\` | Update profile |
| DELETE | \`/profile\` | Anonymize profile (soft-delete) |

**Notes:**
- Profile provides localization context for agents (\`country\`, \`currency_preference\`)
- DELETE anonymizes personal fields but keeps \`country\`/\`currency\` for system consistency

📖 **Full details:** [docs/api/auth-profile.md](./docs/api/auth-profile.md)

---

## 2. Accounts

| Method | Path | Purpose |
|--------|------|---------|
| GET | \`/accounts\` | List user accounts |
| POST | \`/accounts\` | Create account (with optional initial balance) |
| GET | \`/accounts/{id}\` | Get account details |
| PATCH | \`/accounts/{id}\` | Update account |
| DELETE | \`/accounts/{id}\` | Delete with strategy (reassign or cascade) |
| GET | \`/accounts/favorite\` | Get user's favorite account |
| POST | \`/accounts/favorite\` | Set favorite account |
| DELETE | \`/accounts/favorite/{id}\` | Clear favorite status |

**Account Types:** \`cash\`, \`bank\`, \`credit_card\`, \`loan\`, \`remittance\`, \`crypto\`, \`investment\`

**Account Display Fields:**
- \`icon\` (required): Icon identifier for UI (e.g., 'wallet', 'bank')
- \`color\` (required): Hex color code (e.g., '#FF5733')
- \`is_favorite\`: Auto-select for manual transactions (max 1 per user)
- \`is_pinned\`: Pin to top of account list
- \`description\` (optional): User description

**Delete strategies:**
- \`reassign\` (recommended): Move transactions to target account
- \`delete_transactions\`: Permanently delete all transactions ⚠️

📖 **Full details:** [docs/api/accounts.md](./docs/api/accounts.md)

---

## 3. Categories

| Method | Path | Purpose |
|--------|------|---------|
| GET | \`/categories\` | List system + user categories (with optional tree view) |
| POST | \`/categories\` | Create user category (with optional inline subcategories) |
| GET | \`/categories/{id}\` | Get category details |
| GET | \`/categories/{id}/subcategories\` | List subcategories of a parent |
| PATCH | \`/categories/{id}\` | Update user category (name, icon, color) |
| DELETE | \`/categories/{id}\` | Delete with reassignment |

**Flow types:** \`income\`, \`outcome\`

**Category Display Fields:**
- \`icon\` (required): Icon identifier for UI (e.g., 'shopping', 'food')
- \`color\` (required): Hex color code (e.g., '#4CAF50')
- \`parent_category_id\` (optional): Parent category UUID for subcategories

**Subcategory Support:**
- Max depth: 1 (subcategories cannot have children)
- Inline creation: POST can create parent + subcategories atomically
- DELETE orphans subcategories (sets \`parent_category_id = NULL\`)
- Tree view: \`GET /categories?include_tree=true\` returns nested structure

**System categories** (read-only, \`key\` field set):
- \`initial_balance\`, \`balance_update\`, \`transfer\`, \`general\`

**Delete behavior:**
- \`cascade=false\` (default): Reassign to flow-type-matched \`general\`
- \`cascade=true\`: Delete all transactions ⚠️
- Subcategories become top-level (orphaned)

📖 **Full details:** [docs/api/categories.md](./docs/api/categories.md)

---

## 4. Transactions

| Method | Path | Purpose |
|--------|------|---------|
| POST | \`/transactions\` | Create manual transaction |
| GET | \`/transactions\` | List with filters/pagination |
| GET | \`/transactions/{id}\` | Get transaction details |
| PATCH | \`/transactions/{id}\` | Update transaction |
| DELETE | \`/transactions/{id}\` | Delete (+ paired if transfer) |
| POST | \`/transactions/sync-recurring\` | Generate pending recurring transactions |

**Key fields:**
- \`paired_transaction_id\`: Set for transfers (don't count in insights)
- \`invoice_id\`: Set when created from invoice commit

**Transfer restriction:** Use \`PATCH /transfers/{id}\` to edit transfers (this endpoint rejects them)

📖 **Full details:** [docs/api/transactions.md](./docs/api/transactions.md)

---

## 5. Invoices

| Method | Path | Purpose |
|--------|------|---------|
| POST | \`/invoices/ocr\` | Preview extraction from receipt image |
| POST | \`/invoices/commit\` | Persist invoice + create transaction |
| GET | \`/invoices\` | List invoices |
| GET | \`/invoices/{id}\` | Get invoice details |
| DELETE | \`/invoices/{id}\` | Soft-delete invoice |

**Workflow:**
\`\`\`
Photo → POST /invoices/ocr → DRAFT preview
     → User selects account/category
     → POST /invoices/commit → Invoice + Transaction created
\`\`\`

**⚠️ Immutability rule:** Invoices cannot be updated after commit. To correct: delete + create new.

📖 **Full details:** [docs/api/invoices.md](./docs/api/invoices.md)

---

## 6. Budgets

| Method | Path | Purpose |
|--------|------|---------|
| GET | \`/budgets\` | List budgets with categories |
| POST | \`/budgets\` | Create budget with category links |
| GET | \`/budgets/{id}\` | Get budget with categories |
| PATCH | \`/budgets/{id}\` | Update budget details |
| DELETE | \`/budgets/{id}\` | Soft-delete budget |

**Frequencies:** \`once\`, \`daily\`, \`weekly\`, \`monthly\`, \`yearly\`

**Key features:**
- Links to multiple categories via \`budget_category\` junction
- \`cached_consumption\` tracks spending (recomputable via RPC)
- Full category objects returned in responses

📖 **Full details:** [docs/api/budgets.md](./docs/api/budgets.md)

---

## 7. Recurring Transactions

| Method | Path | Purpose |
|--------|------|---------|
| GET | \`/recurring-transactions\` | List rules |
| POST | \`/recurring-transactions\` | Create rule |
| GET | \`/recurring-transactions/{id}\` | Get rule details |
| PATCH | \`/recurring-transactions/{id}\` | Update rule |
| DELETE | \`/recurring-transactions/{id}\` | Delete (+ paired if recurring transfer) |

**Frequencies:** \`daily\`, \`weekly\`, \`monthly\`, \`yearly\` (❌ NOT \`once\`)

**Conditional fields:**
- Weekly requires \`by_weekday\` (e.g., \`["monday", "friday"]\`)
- Monthly requires \`by_monthday\` (e.g., \`[1, 15]\`)

**Sync:** \`POST /transactions/sync-recurring\` generates pending transactions

📖 **Full details:** [docs/api/recurring.md](./docs/api/recurring.md)

---

## 8. Transfers

| Method | Path | Purpose |
|--------|------|---------|
| POST | \`/transfers\` | Create one-time transfer |
| PATCH | \`/transfers/{id}\` | Update both sides atomically |
| POST | \`/transfers/recurring\` | Create recurring transfer |

**Transfer = 2 paired transactions:**
- Array[0]: outcome from source account
- Array[1]: income to destination account
- Both use system category \`key='transfer'\`
- Both linked via \`paired_transaction_id\`

**Edit rules:**
- ✅ Use \`PATCH /transfers/{id}\` for transfers
- ❌ \`PATCH /transactions/{id}\` rejects transfers

**Deletion:** \`DELETE /transactions/{id}\` deletes both sides atomically

📖 **Full details:** [docs/api/transfers.md](./docs/api/transfers.md)

---

## 9. Wishlists

| Method | Path | Purpose |
|--------|------|---------|
| GET | \`/wishlists\` | List wishlists |
| POST | \`/wishlists\` | Create with optional items |
| GET | \`/wishlists/{id}\` | Get wishlist + items |
| GET | \`/wishlists/{id}/items\` | Get items only |
| PATCH | \`/wishlists/{id}\` | Update wishlist |
| DELETE | \`/wishlists/{id}\` | Delete (cascades items) |
| DELETE | \`/wishlists/{id}/items/{item_id}\` | Delete single item |

**Conceptual model:**
- \`wishlist\`: The goal (what user wants to buy)
- \`wishlist_item\`: Saved store options (from recommendations)

**Statuses:** \`active\`, \`purchased\`, \`abandoned\`

📖 **Full details:** [docs/api/wishlists.md](./docs/api/wishlists.md)

---

## 10. Recommendations

| Method | Path | Purpose |
|--------|------|---------|
| POST | \`/recommendations/query\` | Get AI-powered product suggestions |
| POST | \`/recommendations/retry\` | Retry with updated criteria |

**Response types:**
- \`NEEDS_CLARIFICATION\`: Missing required info (e.g., budget)
- \`OK\`: 1-3 product recommendations
- \`NO_VALID_OPTION\`: No suitable products found

**Safety guardrails:**
- Rejects prohibited content (weapons, adult, scams)
- Validates budget constraints
- Respects user preferences from \`user_note\`
- All URLs are real (no hallucinations)

📖 **Full details:** [docs/api/recommendations.md](./docs/api/recommendations.md)

---

## 11. Engagement

| Method | Path | Purpose |
|--------|------|---------|
| GET | \`/engagement/streak\` | Get full streak status with risk assessment |
| GET | \`/engagement/summary\` | Get condensed engagement stats for dashboard |
| GET | \`/engagement/budget-score\` | Get budget health score (0-100) with breakdown |

**Streak System:**
- \`current_streak\`: Consecutive days with financial activity
- \`longest_streak\`: All-time personal best
- \`streak_freeze_available\`: One free freeze per week (resets Mondays)
- \`streak_at_risk\`: True if no activity logged today

**Budget Health Score:**
- Score from 0-100 based on budget adherence
- Per-budget breakdown with utilization and status
- Color coding: green (80+), yellow (50-79), red (<50)
- Status: `on_track` (<75%), `warning` (75-100%), `over` (>100%)

**Auto-updates:**
- Streak is updated automatically when:
  - Creating a transaction (\`POST /transactions\`)
  - Committing an invoice (\`POST /invoices/commit\`)

**Profile Fields:**
Streak data is also included in \`GET /profile\` response:
- \`current_streak\`, \`longest_streak\`, \`last_activity_date\`
- \`streak_freeze_available\`, \`streak_freeze_used_this_week\`

📖 **Full details:** [docs/api/engagement.md](./docs/api/engagement.md)

---

## Response Formats

### List Responses (200)
\`\`\`json
{ "<resource>": [...], "count": 42, "limit": 50, "offset": 0 }
\`\`\`

### Creation Responses (201)
\`\`\`json
{ "status": "CREATED", "<resource>_id": "uuid", "<resource>": {...}, "message": "..." }
\`\`\`

### Update Responses (200)
\`\`\`json
{ "status": "UPDATED", "<resource>_id": "uuid", "<resource>": {...}, "message": "..." }
\`\`\`

### Delete Responses (200)
\`\`\`json
{ "status": "DELETED", "<resource>_id": "uuid", "message": "..." }
\`\`\`

### Error Responses (4xx/5xx)
\`\`\`json
{ "error": "error_code", "details": "Human-readable description" }
\`\`\`

**Common error codes:** \`unauthorized\`, \`forbidden\`, \`not_found\`, \`validation_error\`, \`out_of_scope\`, \`conflict\`, \`internal_error\`

📖 **Full details:** [docs/api/cross-cutting.md](./docs/api/cross-cutting.md)

---

## Feature Dependencies

\`\`\`
account ──────────► transaction ◄─── invoice
                        │
category ──────────────►│
                        │
recurring_transaction ──►│
                        │
budget ◄───────────────┘
   │
   └──► budget_category ◄─── category

wishlist ──────────────► wishlist_item
profile ──────────────► (context for all endpoints)
\`\`\`

**Key dependencies:**
- Transactions require \`account_id\` and \`category_id\`
- Invoices auto-create linked transactions
- Transfers create 2 paired transactions
- Budgets link to categories via junction table

📖 **Full details:** [docs/api/cross-cutting.md](./docs/api/cross-cutting.md)

---

## Frontend Checklist

### Boot/Session
1. Read saved token from secure storage
2. Call \`GET /auth/me\` → hydrate session
3. If 401 → force login

### Invoice Flow
1. Photo → \`POST /invoices/ocr\`
2. If \`DRAFT\` → show preview, let user pick account/category
3. Confirm → \`POST /invoices/commit\`

### Wishlist/Recommendations
1. User writes goal → \`POST /recommendations/query\`
2. Handle \`NEEDS_CLARIFICATION\` loop or show \`OK\` cards
3. User selects options → \`POST /wishlists\` with \`selected_items\`

### Budgets vs Recurring
- \`/budgets\`: Spending caps (can be \`once\`)
- \`/recurring-transactions\`: Auto-generate transactions (NOT \`once\`)

### Activity Feed
- \`/transactions\` powers activity
- Treat \`paired_transaction_id\` as transfers (don't count as spending)

---

## Documentation Structure

\`\`\`
/backend/
├── API-endpoints.md          # This index file (<500 lines)
└── docs/api/
    ├── README.md             # Navigation guide
    ├── auth-profile.md       # Auth & Profile details
    ├── accounts.md           # Accounts details
    ├── categories.md         # Categories details
    ├── transactions.md       # Transactions details
    ├── invoices.md           # Invoices details
    ├── budgets.md            # Budgets details
    ├── recurring.md          # Recurring transactions details
    ├── transfers.md          # Transfers details
    ├── wishlists.md          # Wishlists details
    ├── recommendations.md    # Recommendations details
    ├── engagement.md         # Engagement/streak details
    └── cross-cutting.md      # Security, dependencies, patterns
\`\`\`

This structure follows Anthropic's progressive disclosure pattern for optimal context consumption (load only the domain doc you need).
