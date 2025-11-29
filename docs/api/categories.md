# Categories Endpoints

> **Transaction categorization (system + user categories)**

## Table of Contents

1. [Endpoint Reference](#endpoint-reference)
2. [Category Types](#category-types)
3. [System Categories](#system-categories)
4. [GET /categories](#get-categories)
5. [POST /categories](#post-categories)
6. [GET /categories/{id}](#get-categoriesid)
7. [PATCH /categories/{id}](#patch-categoriesid)
8. [DELETE /categories/{id}](#delete-categoriesid)
9. [Integration Notes](#integration-notes)

---

## Endpoint Reference

| Method | Path | Description |
|--------|------|-------------|
| GET | `/categories` | List system + user categories |
| POST | `/categories` | Create user category |
| GET | `/categories/{id}` | Get category details |
| PATCH | `/categories/{id}` | Update user category name |
| DELETE | `/categories/{id}` | Delete user category with reassignment |

---

## Category Types

### Flow Types

```typescript
type FlowType = "income" | "outcome"
```

### Category Structure

```json
{
  "id": "category-uuid",
  "user_id": "user-uuid" | null,  // null = system category
  "key": "general" | null,        // non-null = system category
  "name": "Groceries",
  "flow_type": "outcome",
  "created_at": "2025-10-01T00:00:00Z",
  "updated_at": "2025-10-01T00:00:00Z"
}
```

---

## System Categories

System categories are predefined, read-only, and have `user_id=NULL` with a `key` field.

| Key | Flow Type | Purpose | Auto-assigned |
|-----|-----------|---------|---------------|
| `initial_balance` | income | Opening balance (assets) | ✓ account creation |
| `initial_balance` | outcome | Opening balance (liabilities) | ✓ account creation |
| `balance_update` | income | Manual positive adjustment | ✗ |
| `balance_update` | outcome | Manual negative adjustment | ✗ |
| `transfer` | income | Receiving side of transfer | ✓ transfers |
| `transfer` | outcome | Sending side of transfer | ✓ transfers |
| `general` | income | Uncategorized income | Fallback |
| `general` | outcome | Uncategorized expense | Fallback |

**Rules:**
- ❌ Cannot create system categories via API
- ❌ Cannot update system categories
- ❌ Cannot delete system categories

---

## GET /categories

**Purpose:** List all categories available to the authenticated user.

**Query Parameters:**
| Param | Type | Default | Description |
|-------|------|---------|-------------|
| `limit` | int | 100 | Max categories |
| `offset` | int | 0 | Pagination offset |

**Response:**
```json
{
  "categories": [
    {
      "id": "category-uuid-123",
      "user_id": null,
      "key": "general",
      "name": "General",
      "flow_type": "outcome",
      "created_at": "2025-10-01T00:00:00Z",
      "updated_at": "2025-10-01T00:00:00Z"
    },
    {
      "id": "category-uuid-456",
      "user_id": "user-uuid-789",
      "key": null,
      "name": "Groceries",
      "flow_type": "outcome",
      "created_at": "2025-11-01T10:00:00Z",
      "updated_at": "2025-11-01T10:00:00Z"
    }
  ],
  "count": 2,
  "limit": 100,
  "offset": 0
}
```

**Status Codes:** 200, 401, 500

---

## POST /categories

**Purpose:** Create a new personal category.

**Request Body:**
```json
{
  "name": "Groceries",
  "flow_type": "outcome"
}
```

**Required Fields:**
- `name` (string, 1-100 chars)
- `flow_type` (Literal["income", "outcome"])

**Response (201):**
```json
{
  "status": "CREATED",
  "category": {
    "id": "category-uuid-456",
    "user_id": "user-uuid-789",
    "key": null,
    "name": "Groceries",
    "flow_type": "outcome",
    "created_at": "2025-11-05T10:00:00Z",
    "updated_at": "2025-11-05T10:00:00Z"
  },
  "message": "Category created successfully"
}
```

**Typical Trigger:** User accepts InvoiceAgent suggestion with `match_type = "NEW_PROPOSED"`

**Status Codes:** 201, 400, 401, 422, 500

---

## GET /categories/{id}

**Purpose:** Retrieve details of a specific category.

**Behavior:**
- User can access system categories (read-only)
- User can access their own personal categories
- Returns 404 for other users' categories

**Status Codes:** 200, 401, 404, 500

---

## PATCH /categories/{id}

**Purpose:** Update an existing user category (name only).

**Request Body:**
```json
{
  "name": "Supermarket"
}
```

**Editable Fields:**
- `name` (string, 1-100 chars)

**Immutable Fields:**
- `flow_type` - Changing would affect all transactions, impacting balances

**Rejected:**
- System categories (returns 400)

**Response:**
```json
{
  "status": "UPDATED",
  "category": { ... },
  "message": "Category updated successfully"
}
```

**Status Codes:** 200, 400, 401, 404, 422, 500

---

## DELETE /categories/{id}

**Purpose:** Delete a user category with flow-type aware transaction reassignment.

**Query Parameters:**
| Param | Type | Default | Description |
|-------|------|---------|-------------|
| `cascade` | boolean | false | Deletion mode |

### Deletion Modes

#### Mode 1: Reassign (default, `cascade=false`) - RECOMMENDED

1. Determine `flow_type` of category being deleted
2. Find matching system `general` category:
   - `outcome` category → reassign to `general` (outcome)
   - `income` category → reassign to `general` (income)
3. Reassign all transactions
4. Remove `budget_category` links
5. Delete the category

#### Mode 2: Cascade Delete (`cascade=true`) - DESTRUCTIVE

1. **Permanently deletes all transactions**
2. Removes `budget_category` links
3. Deletes the category
4. ⚠️ Cannot be undone

**Protected Categories:**
- System categories CANNOT be deleted (returns 400)

**Response (Reassign):**
```json
{
  "status": "DELETED",
  "category_id": "category-uuid-456",
  "transactions_reassigned": 15,
  "budget_links_removed": 2,
  "transactions_deleted": 0,
  "message": "Category deleted successfully (REASSIGN). 15 transaction(s) reassigned..."
}
```

**Response (Cascade):**
```json
{
  "status": "DELETED",
  "category_id": "category-uuid-456",
  "transactions_reassigned": 0,
  "budget_links_removed": 2,
  "transactions_deleted": 15,
  "message": "Category deleted successfully (CASCADE). 15 transaction(s) permanently deleted..."
}
```

**Status Codes:** 200, 400, 401, 404, 500

---

## Integration Notes

### Dependencies

- **Transactions** require a `category_id`
- **Budgets** link to categories via `budget_category`
- **InvoiceAgent** suggests categories for invoices
- **Recurring transactions** require a `category_id`

### Flow-Type Matching on Delete

Ensures data integrity:
- Deleting "Groceries" (outcome) → transactions go to "General" (outcome)
- Deleting "Freelance" (income) → transactions go to "General" (income)
- Income and outcome transactions never mixed

### InvoiceAgent Category Suggestion

```json
{
  "category_suggestion": {
    "match_type": "EXISTING" | "NEW_PROPOSED",
    "category_id": "uuid" | null,
    "category_name": "Groceries" | null,
    "proposed_name": null | "Mascotas"
  }
}
```

- `EXISTING`: Use existing category (preselect in UI)
- `NEW_PROPOSED`: Create new category (prompt user)
