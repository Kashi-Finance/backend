# Wishlist Endpoints

> **Purchase goals and saved product options**

## Table of Contents

1. [Endpoint Reference](#endpoint-reference)
2. [Conceptual Model](#conceptual-model)
3. [Status Values](#status-values)
4. [GET /wishlists](#get-wishlists)
5. [POST /wishlists](#post-wishlists)
6. [GET /wishlists/{id}](#get-wishlistsid)
7. [GET /wishlists/{id}/items](#get-wishlistsiditems)
8. [PATCH /wishlists/{id}](#patch-wishlistsid)
9. [DELETE /wishlists/{id}](#delete-wishlistsid)
10. [DELETE /wishlists/{id}/items/{item_id}](#delete-wishlistsiditemsitem_id)
11. [Integration Notes](#integration-notes)

---

## Endpoint Reference

| Method | Path | Description |
|--------|------|-------------|
| GET | `/wishlists` | List all wishlists |
| POST | `/wishlists` | Create wishlist with optional items |
| GET | `/wishlists/{id}` | Get wishlist with items |
| GET | `/wishlists/{id}/items` | Get items only |
| PATCH | `/wishlists/{id}` | Update wishlist |
| DELETE | `/wishlists/{id}` | Delete wishlist (cascades items) |
| DELETE | `/wishlists/{id}/items/{item_id}` | Delete single item |

---

## Conceptual Model

### Wishlist (Goal)

The "meta" or goal the user wants to achieve:

```json
{
  "id": "wlst-uuid",
  "user_id": "user-uuid",
  "goal_title": "Laptop para diseño gráfico",
  "budget_hint": "7000.00",
  "currency_code": "GTQ",
  "target_date": "2025-12-20",
  "preferred_store": "Prefer Intelaf Zone 9",
  "user_note": "No RGB lights, minimalist design",
  "status": "active",
  "created_at": "...",
  "updated_at": "..."
}
```

### Wishlist Item (Saved Option)

A concrete store option saved by the user:

```json
{
  "id": "wi-uuid",
  "wishlist_id": "wlst-uuid",
  "product_title": "HP Envy Ryzen 7 16GB RAM 512GB SSD",
  "price_total": "6200.00",
  "seller_name": "ElectroCentro Guatemala",
  "url": "https://electrocentro.gt/hp-envy-ryzen7",
  "pickup_available": true,
  "warranty_info": "HP 12-month warranty",
  "copy_for_user": "Recommended for graphic design. Meets specs.",
  "badges": ["Cheapest", "12m Warranty", "Pickup Today"],
  "created_at": "...",
  "updated_at": "..."
}
```

**Key Points:**
- Wishlist CAN exist with zero items
- Items ONLY created when user explicitly selects options
- Never created automatically

---

## Status Values

| Status | Description |
|--------|-------------|
| `active` | Goal is still being pursued |
| `purchased` | Goal has been achieved |
| `abandoned` | User no longer interested |

---

## GET /wishlists

**Purpose:** List all wishlists for the authenticated user.

**Query Parameters:**
| Param | Type | Default | Description |
|-------|------|---------|-------------|
| `limit` | int | 50 | Max 100 |
| `offset` | int | 0 | Pagination offset |

**Response:**
```json
{
  "wishlists": [
    {
      "id": "wlst-uuid",
      "user_id": "user-uuid",
      "goal_title": "Laptop para diseño gráfico",
      "budget_hint": "7000.00",
      "currency_code": "GTQ",
      "target_date": "2025-12-20",
      "preferred_store": "Prefer Intelaf Zone 9",
      "user_note": "No RGB lights",
      "status": "active",
      "created_at": "...",
      "updated_at": "..."
    }
  ],
  "count": 1,
  "limit": 50,
  "offset": 0
}
```

**Status Codes:** 200, 401, 500

---

## POST /wishlists

**Purpose:** Create wishlist with optional selected items.

### Three Frontend Scenarios

**CASE A - Manual save (no recommendations):**
- User fills wizard, clicks "Save my goal"
- `selected_items` omitted or empty
- Only wishlist created (no items)

**CASE B - Recommendations but none selected:**
- User requests recommendations, reviews options, doesn't select any
- `selected_items` omitted or empty
- Only wishlist created (no items)

**CASE C - Recommendations with 1-3 selected:**
- User requests recommendations, selects 1-3 offers
- `selected_items` contains selected offers
- Wishlist AND items created

**Request Body:**
```json
{
  "goal_title": "Laptop Ryzen 7, 16GB RAM, SSD 512GB",
  "budget_hint": 7000.00,
  "currency_code": "GTQ",
  "target_date": "2025-12-20",
  "preferred_store": "Prefer Intelaf Zone 9",
  "user_note": "No RGB lights, minimalist design",
  "selected_items": [
    {
      "product_title": "HP Envy Ryzen 7 16GB RAM 512GB SSD",
      "price_total": 6200.00,
      "seller_name": "ElectroCentro Guatemala",
      "url": "https://electrocentro.gt/hp-envy-ryzen7",
      "pickup_available": true,
      "warranty_info": "HP 12-month warranty",
      "copy_for_user": "Recommended for graphic design.",
      "badges": ["Cheapest", "12m Warranty"]
    }
  ]
}
```

**Required Fields:**
- `goal_title` (1-500 chars)
- `budget_hint` (> 0)
- `currency_code` (3 chars, ISO)

**Optional Fields:**
- `target_date`
- `preferred_store` (max 200 chars)
- `user_note` (max 1000 chars)
- `selected_items` (max 3 items, each with max 3 badges)

**Response (201):**
```json
{
  "status": "CREATED",
  "wishlist": { ... },
  "items_created": 1,
  "message": "Wishlist created successfully with 1 saved offer"
}
```

**Status Codes:** 201, 400, 401, 500

---

## GET /wishlists/{id}

**Purpose:** Get wishlist with all saved items.

**Response:**
```json
{
  "wishlist": {
    "id": "wlst-uuid",
    "goal_title": "Laptop Ryzen 7",
    "budget_hint": "7000.00",
    ...
  },
  "items": [
    {
      "id": "wi-uuid",
      "wishlist_id": "wlst-uuid",
      "product_title": "HP Envy Ryzen 7",
      ...
    }
  ]
}
```

**Status Codes:** 200, 401, 404, 500

---

## GET /wishlists/{id}/items

**Purpose:** Get just the saved items (without wishlist details).

**Query Parameters:**
| Param | Type | Default | Description |
|-------|------|---------|-------------|
| `limit` | int | 50 | Max 100 |
| `offset` | int | 0 | Pagination offset |

**Response:** Array of item objects (no wishlist wrapper)

**Use Cases:**
- Fetch items independently
- Carousel/gallery view
- Pagination for many items

**Status Codes:** 200, 401, 404, 500

---

## PATCH /wishlists/{id}

**Purpose:** Update wishlist details.

**Request Body (all optional):**
```json
{
  "goal_title": "Updated goal",
  "budget_hint": 8000.00,
  "currency_code": "USD",
  "target_date": "2026-01-15",
  "preferred_store": "Any online",
  "user_note": "Updated preferences",
  "status": "purchased"
}
```

**Note:** Cannot add/remove items via this endpoint.

**Response:**
```json
{
  "status": "UPDATED",
  "wishlist": { ... },
  "message": "Wishlist updated successfully"
}
```

**Status Codes:** 200, 400, 401, 404, 500

---

## DELETE /wishlists/{id}

**Purpose:** Delete wishlist and all items (CASCADE).

**Response:**
```json
{
  "status": "DELETED",
  "message": "Wishlist deleted successfully. 2 items removed.",
  "items_deleted": 2
}
```

**Status Codes:** 200, 401, 500

---

## DELETE /wishlists/{id}/items/{item_id}

**Purpose:** Delete a single item.

**Behavior:**
- Parent wishlist remains
- Wishlist can have zero items after deletion

**Response:**
```json
{
  "status": "DELETED",
  "message": "Wishlist item deleted successfully"
}
```

**Status Codes:** 200, 401, 404, 500

---

## Integration Notes

### Recommendations Integration

See [recommendations.md](./recommendations.md) for full flow.

```
User fills wizard
       │
       ├─► "Save my goal" → POST /wishlists (no items)
       │
       └─► "Get recommendations"
                │
                ▼
           POST /recommendations/query
                │
                ▼
           User selects 0-3 options
                │
                ▼
           POST /wishlists (with selected_items)
```

### Field Mapping

FormatterAgent output → `selected_items` → `wishlist_item`:

| Field | Description |
|-------|-------------|
| `product_title` | Commercial product name |
| `price_total` | Total price |
| `seller_name` | Store/seller |
| `url` | Real product URL |
| `pickup_available` | Boolean |
| `warranty_info` | Warranty details |
| `copy_for_user` | AI-generated description |
| `badges` | UI badge labels (max 3) |

### Business Rules

- **Creation:** Can create without items (manual save)
- **Adding items:** Only via creation `selected_items`
- **Deletion:** Wishlist cascade → deletes all items
- **Item deletion:** Doesn't affect parent wishlist
- **Items cannot be added after creation** (user must create new wishlist or use recommendations again)

### RLS

- All wishlists protected by `user_id = auth.uid()`
- Users can only see/modify their own goals and items
