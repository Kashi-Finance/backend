# Wishlist RPCs

## Overview

Wishlist RPCs handle atomic creation of wishlists with their items.

---

## `create_wishlist_with_items`

**Purpose:** Atomically create a wishlist and add initial items.

**Signature:**
```sql
CREATE OR REPLACE FUNCTION create_wishlist_with_items(
  p_user_id uuid,
  p_name text,
  p_items jsonb
)
RETURNS TABLE(
  wishlist_id uuid,
  items_created INT
)
```

**Security:** `SECURITY DEFINER` (validates ownership)

**Behavior:**
1. Inserts wishlist row for `p_user_id` with `p_name`
2. Parses `p_items` JSONB array and inserts each item
3. Returns wishlist UUID and count of items created

**Input Format (p_items):**
```json
[
  {
    "description": "Gaming laptop",
    "estimated_price": 1200.00,
    "priority": "high",
    "url": "https://example.com/laptop"
  },
  {
    "description": "Wireless headphones",
    "estimated_price": 150.00,
    "priority": "medium"
  }
]
```

**Usage:**
```python
result = supabase_client.rpc(
    'create_wishlist_with_items',
    {
        'p_user_id': user_uuid,
        'p_name': 'Tech purchases 2025',
        'p_items': [
            {
                'description': 'Gaming laptop',
                'estimated_price': 1200.00,
                'priority': 'high',
                'url': 'https://example.com/laptop'
            }
        ]
    }
).execute()

row = result.data[0]
# row['wishlist_id'] - UUID of created wishlist
# row['items_created'] - count of items inserted
```

**Notes:**
- All items inserted atomically with wishlist creation
- `wishlist_item` has FK cascade on wishlist deletion
- Priority enum: 'low', 'medium', 'high'
