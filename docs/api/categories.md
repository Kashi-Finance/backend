# Categories Endpoints

> **Transaction categorization (system + user categories with subcategory support)**

## Table of Contents

1. [Endpoint Reference](#endpoint-reference)
2. [Category Types](#category-types)
3. [Subcategory Support](#subcategory-support)
4. [System Categories](#system-categories)
5. [GET /categories](#get-categories)
6. [POST /categories](#post-categories)
7. [GET /categories/{id}](#get-categoriesid)
8. [GET /categories/{id}/subcategories](#get-categoriesidsubcategories)
9. [PATCH /categories/{id}](#patch-categoriesid)
10. [DELETE /categories/{id}](#delete-categoriesid)
11. [Integration Notes](#integration-notes)

---

## Endpoint Reference

| Method | Path | Description |
|--------|------|-------------|
| GET | `/categories` | List system + user categories (with tree option) |
| POST | `/categories` | Create user category (with inline subcategories) |
| GET | `/categories/{id}` | Get category details |
| GET | `/categories/{id}/subcategories` | List subcategories of a parent |
| PATCH | `/categories/{id}` | Update user category (name, icon, color) |
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
  "user_id": "user-uuid" | null,
  "key": "general" | null,
  "name": "Groceries",
  "flow_type": "outcome",
  "icon": "shopping",
  "color": "#4CAF50",
  "parent_category_id": null | "parent-uuid",
  "subcategories": [],
  "created_at": "2025-10-01T00:00:00Z",
  "updated_at": "2025-10-01T00:00:00Z"
}
```

**Field Descriptions:**
| Field | Type | Description |
|-------|------|-------------|
| `id` | UUID | Category identifier |
| `user_id` | UUID? | Owner (null for system categories) |
| `key` | string? | System key (null for user categories) |
| `name` | string | Display name |
| `flow_type` | FlowType | "income" or "outcome" |
| `icon` | string | Icon identifier for UI (e.g., 'shopping', 'food') |
| `color` | string | Hex color code (e.g., '#4CAF50') |
| `parent_category_id` | UUID? | Parent category (null = top-level) |
| `subcategories` | array | Child categories (when include_tree=true) |
| `created_at` | timestamp | Creation timestamp |
| `updated_at` | timestamp | Last update timestamp |

---

## Subcategory Support

### Hierarchy Rules

- **Max depth:** 1 level (parent → children, no grandchildren)
- **Inheritance:** Subcategories inherit `flow_type` from parent
- **Constraint:** A category with `parent_category_id` cannot have children

### Creating Subcategories

Two approaches:

**1. Inline creation (recommended for UI):**
```json
POST /categories
{
  "name": "Food & Drink",
  "flow_type": "outcome",
  "icon": "food",
  "color": "#4CAF50",
  "subcategories": [
    {"name": "Groceries", "icon": "cart", "color": "#81C784"},
    {"name": "Restaurants", "icon": "restaurant", "color": "#66BB6A"},
    {"name": "Coffee", "icon": "coffee", "color": "#A5D6A7"}
  ]
}
```

**2. Separate creation:**
```json
POST /categories
{
  "name": "Groceries",
  "flow_type": "outcome",
  "icon": "cart",
  "color": "#81C784",
  "parent_category_id": "parent-uuid"
}
```

### Tree View

```json
GET /categories?include_tree=true

{
  "categories": [
    {
      "id": "parent-uuid",
      "name": "Food & Drink",
      "flow_type": "outcome",
      "parent_category_id": null,
      "subcategories": [
        {"id": "child-1", "name": "Groceries", "parent_category_id": "parent-uuid", "subcategories": []},
        {"id": "child-2", "name": "Restaurants", "parent_category_id": "parent-uuid", "subcategories": []}
      ]
    }
  ]
}
```

### Deletion Behavior

When deleting a parent category:
- Subcategories are **orphaned** (set `parent_category_id = NULL`)
- Orphaned subcategories become top-level categories
- Response includes `subcategories_orphaned` count

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
| `include_tree` | boolean | false | Include subcategories nested in parent |

**Response (flat, default):**
```json
{
  "categories": [
    {
      "id": "category-uuid-123",
      "user_id": null,
      "key": "general",
      "name": "General",
      "flow_type": "outcome",
      "icon": "tag",
      "color": "#9E9E9E",
      "parent_category_id": null,
      "subcategories": [],
      "created_at": "2025-10-01T00:00:00Z",
      "updated_at": "2025-10-01T00:00:00Z"
    },
    {
      "id": "category-uuid-456",
      "user_id": "user-uuid-789",
      "key": null,
      "name": "Groceries",
      "flow_type": "outcome",
      "icon": "shopping",
      "color": "#4CAF50",
      "parent_category_id": null,
      "subcategories": [],
      "created_at": "2025-11-01T10:00:00Z",
      "updated_at": "2025-11-01T10:00:00Z"
    }
  ],
  "count": 2,
  "limit": 100,
  "offset": 0
}
```

**Response (tree view, `include_tree=true`):**
```json
{
  "categories": [
    {
      "id": "parent-uuid",
      "name": "Food & Drink",
      "flow_type": "outcome",
      "parent_category_id": null,
      "subcategories": [
        {
          "id": "child-1",
          "name": "Groceries",
          "parent_category_id": "parent-uuid",
          "subcategories": []
        },
        {
          "id": "child-2",
          "name": "Restaurants",
          "parent_category_id": "parent-uuid",
          "subcategories": []
        }
      ]
    }
  ],
  "count": 1,
  "limit": 100,
  "offset": 0
}
```

**Notes:**
- Tree view only returns top-level categories with children nested
- Flat view returns all categories (parents and children) as siblings

**Status Codes:** 200, 401, 500

---

## POST /categories

**Purpose:** Create a new personal category, optionally with inline subcategories.

**Request Body (simple category):**
```json
{
  "name": "Groceries",
  "flow_type": "outcome",
  "icon": "shopping",
  "color": "#4CAF50"
}
```

**Request Body (with subcategories):**
```json
{
  "name": "Food & Drink",
  "flow_type": "outcome",
  "icon": "food",
  "color": "#4CAF50",
  "subcategories": [
    {"name": "Groceries", "icon": "cart", "color": "#81C784"},
    {"name": "Restaurants", "icon": "restaurant", "color": "#66BB6A"},
    {"name": "Coffee", "icon": "coffee", "color": "#A5D6A7"}
  ]
}
```

**Request Body (as subcategory):**
```json
{
  "name": "Coffee Shops",
  "flow_type": "outcome",
  "icon": "coffee",
  "color": "#A5D6A7",
  "parent_category_id": "parent-uuid"
}
```

**Required Fields:**
| Field | Type | Description |
|-------|------|-------------|
| `name` | string | Category name (1-100 chars) |
| `flow_type` | FlowType | "income" or "outcome" |
| `icon` | string | Icon identifier (1-50 chars) |
| `color` | string | Hex color code (#RRGGBB) |

**Optional Fields:**
| Field | Type | Description |
|-------|------|-------------|
| `parent_category_id` | UUID? | Parent category (for creating subcategory) |
| `subcategories` | array | Inline subcategories to create with parent |

**Subcategory Object:**
| Field | Type | Description |
|-------|------|-------------|
| `name` | string | Subcategory name |
| `icon` | string | Icon identifier |
| `color` | string | Hex color code |

**Response (201, simple):**
```json
{
  "status": "CREATED",
  "category": {
    "id": "category-uuid-456",
    "user_id": "user-uuid-789",
    "key": null,
    "name": "Groceries",
    "flow_type": "outcome",
    "icon": "shopping",
    "color": "#4CAF50",
    "parent_category_id": null,
    "subcategories": [],
    "created_at": "2025-11-05T10:00:00Z",
    "updated_at": "2025-11-05T10:00:00Z"
  },
  "subcategories_created": 0,
  "message": "Category created successfully"
}
```

**Response (201, with subcategories):**
```json
{
  "status": "CREATED",
  "category": {
    "id": "parent-uuid",
    "name": "Food & Drink",
    "flow_type": "outcome",
    "parent_category_id": null,
    "subcategories": [
      {"id": "sub-1", "name": "Groceries", "parent_category_id": "parent-uuid"},
      {"id": "sub-2", "name": "Restaurants", "parent_category_id": "parent-uuid"},
      {"id": "sub-3", "name": "Coffee", "parent_category_id": "parent-uuid"}
    ]
  },
  "subcategories_created": 3,
  "message": "Category created successfully with 3 subcategory(ies)"
}
```

**Validation Errors:**
- Cannot create subcategory of a subcategory (max depth 1)
- `parent_category_id` must exist and belong to user
- Cannot use both `parent_category_id` and `subcategories[]`

**Status Codes:** 201, 400, 401, 422, 500

---

## GET /categories/{id}

**Purpose:** Retrieve details of a specific category.

**Query Parameters:**
| Param | Type | Default | Description |
|-------|------|---------|-------------|
| `include_subcategories` | boolean | false | Include subcategories in response |

**Behavior:**
- User can access system categories (read-only)
- User can access their own personal categories
- Returns 404 for other users' categories

**Response:**
```json
{
  "id": "category-uuid",
  "user_id": "user-uuid",
  "name": "Food & Drink",
  "flow_type": "outcome",
  "icon": "food",
  "color": "#4CAF50",
  "parent_category_id": null,
  "subcategories": [],
  "created_at": "2025-11-01T10:00:00Z",
  "updated_at": "2025-11-01T10:00:00Z"
}
```

**Status Codes:** 200, 401, 404, 500

---

## GET /categories/{id}/subcategories

**Purpose:** List all subcategories of a parent category.

**Response:**
```json
[
  {
    "id": "sub-1",
    "user_id": "user-uuid",
    "name": "Groceries",
    "flow_type": "outcome",
    "icon": "cart",
    "color": "#81C784",
    "parent_category_id": "parent-uuid",
    "subcategories": [],
    "created_at": "2025-11-01T10:00:00Z",
    "updated_at": "2025-11-01T10:00:00Z"
  },
  {
    "id": "sub-2",
    "user_id": "user-uuid",
    "name": "Restaurants",
    "flow_type": "outcome",
    "icon": "restaurant",
    "color": "#66BB6A",
    "parent_category_id": "parent-uuid",
    "subcategories": [],
    "created_at": "2025-11-01T10:00:00Z",
    "updated_at": "2025-11-01T10:00:00Z"
  }
]
```

**Status Codes:** 200, 401, 404, 500

---

## PATCH /categories/{id}

**Purpose:** Update an existing user category.

**Request Body (all optional, at least one required):**
```json
{
  "name": "Supermarket",
  "icon": "cart",
  "color": "#2196F3"
}
```

**Editable Fields:**
| Field | Type | Description |
|-------|------|-------------|
| `name` | string | Category name (1-100 chars) |
| `icon` | string | Icon identifier (1-50 chars) |
| `color` | string | Hex color code (#RRGGBB) |

**Immutable Fields:**
- `flow_type` - Changing would affect all transactions, impacting balances

**Rejected:**
- System categories (returns 400)

**Response:**
```json
{
  "status": "UPDATED",
  "category": { ...full category object... },
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
  "subcategories_orphaned": 3,
  "message": "Category deleted successfully (REASSIGN). 15 transaction(s) reassigned, 3 subcategory(ies) orphaned..."
}
```

**Response (Cascade):**
```json
{
  "status": "DELETED",
  "category_id": "category-uuid-456",
  "transactions_reassigned": 0,
  "budget_links_removed": 2,
  "subcategories_orphaned": 3,
  "message": "Category deleted successfully (CASCADE). 15 transaction(s) permanently deleted, 3 subcategory(ies) orphaned..."
}
```

**Subcategory Behavior:**
- When deleting a parent category, its subcategories are **orphaned**
- Orphaned subcategories have `parent_category_id` set to `NULL`
- They become top-level categories
- Response includes `subcategories_orphaned` count

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
