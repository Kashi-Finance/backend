# Budget Endpoints

> **Spending limits with category linking and consumption tracking**

## Table of Contents

1. [Endpoint Reference](#endpoint-reference)
2. [Budget Schema](#budget-schema)
3. [Frequency Options](#frequency-options)
4. [GET /budgets](#get-budgets)
5. [POST /budgets](#post-budgets)
6. [GET /budgets/{id}](#get-budgetsid)
7. [PATCH /budgets/{id}](#patch-budgetsid)
8. [DELETE /budgets/{id}](#delete-budgetsid)
9. [Integration Notes](#integration-notes)

---

## Endpoint Reference

| Method | Path | Description |
|--------|------|-------------|
| GET | `/budgets` | List all budgets with categories |
| POST | `/budgets` | Create budget with category links |
| GET | `/budgets/{id}` | Get single budget with categories |
| PATCH | `/budgets/{id}` | Update budget (not categories) |
| DELETE | `/budgets/{id}` | Soft-delete budget |

---

## Budget Schema

```json
{
  "id": "budget-uuid",
  "user_id": "user-uuid",
  "limit_amount": 500.00,
  "frequency": "monthly",
  "interval": 1,
  "start_date": "2025-11-01",
  "end_date": null,
  "is_active": true,
  "cached_consumption": 320.75,
  "categories": [
    {
      "id": "category-uuid",
      "user_id": "user-uuid",
      "key": null,
      "name": "Groceries",
      "flow_type": "outcome",
      "created_at": "...",
      "updated_at": "..."
    }
  ],
  "created_at": "...",
  "updated_at": "..."
}
```

---

## Frequency Options

| Value | Description |
|-------|-------------|
| `once` | One-time budget |
| `daily` | Repeats daily |
| `weekly` | Repeats weekly |
| `monthly` | Repeats monthly |
| `yearly` | Repeats yearly |

**Interval:** Multiplier (e.g., `frequency="weekly"`, `interval=2` = every 2 weeks)

---

## GET /budgets

**Purpose:** List all budgets with their linked categories.

**Query Parameters:**
| Param | Type | Description |
|-------|------|-------------|
| `frequency` | string | Filter by frequency |
| `is_active` | boolean | Filter by active status |

**Response:**
```json
{
  "budgets": [
    {
      "id": "budget-uuid",
      "user_id": "user-uuid",
      "limit_amount": 500.00,
      "frequency": "monthly",
      "interval": 1,
      "start_date": "2025-11-01",
      "end_date": null,
      "is_active": true,
      "cached_consumption": 320.75,
      "categories": [
        {
          "id": "category-uuid-1",
          "user_id": "user-uuid",
          "key": null,
          "name": "Groceries",
          "flow_type": "outcome",
          "created_at": "...",
          "updated_at": "..."
        }
      ],
      "created_at": "...",
      "updated_at": "..."
    }
  ],
  "count": 1
}
```

**Category Fields:**
All category fields are returned:
- `id`, `user_id`, `key`, `name`, `flow_type`, `created_at`, `updated_at`

**Status Codes:** 200, 401, 500

---

## POST /budgets

**Purpose:** Create a new budget with optional category linking.

**Request Body:**
```json
{
  "limit_amount": 500.00,
  "frequency": "monthly",
  "interval": 1,
  "start_date": "2025-11-01",
  "end_date": null,
  "is_active": true,
  "category_ids": ["category-uuid-1", "category-uuid-2"]
}
```

**Field Constraints:**
| Field | Rule |
|-------|------|
| `limit_amount` | Must be > 0 |
| `frequency` | Valid enum value |
| `interval` | Must be >= 1 |
| `start_date` | Required, DATE format |
| `end_date` | Optional, must be >= start_date |
| `is_active` | Default true |
| `category_ids` | Optional, list of UUIDs |

**Response (201):**
```json
{
  "status": "CREATED",
  "budget": { ... },
  "categories_linked": 2,
  "message": "Budget created successfully with 2 categories"
}
```

**Status Codes:** 201, 400, 401, 500

---

## GET /budgets/{id}

**Purpose:** Retrieve single budget with all linked categories.

**Response:** Same schema as list item.

**Status Codes:** 200, 401, 404, 500

---

## PATCH /budgets/{id}

**Purpose:** Update budget details (partial update).

**Request Body (all optional):**
```json
{
  "limit_amount": 600.00,
  "is_active": false,
  "end_date": "2026-12-31"
}
```

**Updatable Fields:**
- `limit_amount` (> 0)
- `frequency` (valid enum)
- `interval` (>= 1)
- `start_date`
- `end_date`
- `is_active`

**NOT Updatable via this endpoint:**
- Category links (future: separate endpoint)

**Response:**
```json
{
  "status": "UPDATED",
  "budget": { ... },
  "message": "Budget updated successfully"
}
```

**Status Codes:** 200, 400, 401, 404, 500

---

## DELETE /budgets/{id}

**Purpose:** Soft-delete a budget.

**Behavior:**
- Calls `delete_budget(p_budget_id, p_user_id)` RPC
- Sets `deleted_at` timestamp
- `budget_category` junction rows preserved for historical analysis
- Soft-deleted budgets hidden via RLS

**Response:**
```json
{
  "status": "DELETED",
  "budget_id": "budget-uuid",
  "deleted_at": "2025-11-16T10:30:00-06:00",
  "message": "Budget soft-deleted successfully"
}
```

**Status Codes:** 200, 401, 404, 500

---

## Integration Notes

### Category Linking

- Budgets link to categories via `budget_category` junction table
- Each budget can track spending across multiple categories
- System categories (with `key`) are linkable
- User categories (key=null) are linkable

### Cached Consumption

- `cached_consumption` tracks spending against budget
- Recomputable via `recompute_budget_consumption` RPC
- Updated automatically on transaction changes

### Budget vs Recurring Transaction

| Feature | Budget | Recurring Transaction |
|---------|--------|----------------------|
| Purpose | Spending limit | Auto-generate transactions |
| `once` frequency | ✓ Allowed | ✗ Not allowed |
| Creates transactions | No | Yes (on sync) |
| Tracks spending | Yes | No |

### Category Deletion Impact

When a category linked to a budget is deleted:
- `budget_category` link is removed
- Budget remains (may have other categories)
- Transactions reassigned to `general`

### RLS Enforcement

- Users only see their own budgets
- Category access checked during linking
- System categories accessible to all for linking
