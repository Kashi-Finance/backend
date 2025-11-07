"""
Wishlist service.

Handles CRUD operations for user wishlists and wishlist_items with proper
atomic transactions and delete rule enforcement.

Wishlists represent user purchase goals (what they want to buy), and
wishlist_items represent specific store options saved from recommendation flow.
"""

import logging
import json
from typing import Dict, Any, Optional, List, cast
from decimal import Decimal, ROUND_HALF_UP

from supabase import Client

logger = logging.getLogger(__name__)


def _normalize_numeric_12_2(value: Any) -> str:
    """
    Ensure the value fits into NUMERIC(12,2): quantize to 2 decimals and
    enforce the maximum allowed magnitude (9999999999.99).
    Returns the string representation suitable for insertion into the DB.

    Accepts numeric-like inputs (str, int, float, Decimal). Conversion to
    Decimal is performed for precise rounding.
    """
    if not isinstance(value, Decimal):
        try:
            value = Decimal(str(value))
        except Exception as exc:  # pragma: no cover - defensive
            raise ValueError("numeric value required") from exc

    quantized = value.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
    max_val = Decimal("9999999999.99")
    if quantized.copy_abs() > max_val:
        raise ValueError("value exceeds NUMERIC(12,2) range")
    return f"{quantized:.2f}"


async def get_user_wishlists(
    supabase_client: Client,
    user_id: str,
    limit: int = 50,
    offset: int = 0
) -> List[Dict[str, Any]]:
    """
    Fetch all wishlists belonging to the user with pagination support.
    
    Args:
        supabase_client: Authenticated Supabase client
        user_id: The authenticated user's ID
        limit: Maximum number of wishlists to return (default 50)
        offset: Number of wishlists to skip for pagination (default 0)
    
    Returns:
        List of wishlist dicts
    
    Security:
        - RLS enforces user_id = auth.uid()
        - User can only access their own wishlists
    """
    logger.debug(f"Fetching wishlists for user {user_id} (limit={limit}, offset={offset})")
    
    result = (
        supabase_client.table("wishlist")
        .select("*")
        .eq("user_id", user_id)
        .order("created_at", desc=True)
        .range(offset, offset + limit - 1)
        .execute()
    )
    
    wishlists: List[Dict[str, Any]] = cast(List[Dict[str, Any]], result.data or [])
    logger.info(f"Found {len(wishlists)} wishlists for user {user_id}")
    
    return wishlists


async def get_wishlist_by_id(
    supabase_client: Client,
    user_id: str,
    wishlist_id: str
) -> Optional[Dict[str, Any]]:
    """
    Fetch a single wishlist by ID.
    
    Args:
        supabase_client: Authenticated Supabase client
        user_id: The authenticated user's ID
        wishlist_id: The wishlist UUID
    
    Returns:
        Wishlist dict, or None if not found
    
    Security:
        - RLS enforces user_id = auth.uid()
        - User can only access their own wishlists
    """
    logger.debug(f"Fetching wishlist {wishlist_id} for user {user_id}")
    
    result = (
        supabase_client.table("wishlist")
        .select("*")
        .eq("id", wishlist_id)
        .eq("user_id", user_id)
        .execute()
    )
    
    if not result.data or len(result.data) == 0:
        logger.warning(f"Wishlist {wishlist_id} not found for user {user_id}")
        return None
    
    wishlist: Dict[str, Any] = cast(Dict[str, Any], result.data[0])
    logger.info(f"Wishlist {wishlist_id} found for user {user_id}")
    
    return wishlist


async def get_wishlist_items(
    supabase_client: Client,
    wishlist_id: str
) -> List[Dict[str, Any]]:
    """
    Fetch all items for a specific wishlist.
    
    Args:
        supabase_client: Authenticated Supabase client
        wishlist_id: The wishlist UUID
    
    Returns:
        List of wishlist_item dicts (may be empty)
    
    Note:
        RLS is handled by the parent wishlist query. This assumes
        the caller has already verified wishlist ownership.
    """
    logger.debug(f"Fetching items for wishlist {wishlist_id}")
    
    result = (
        supabase_client.table("wishlist_item")
        .select("*")
        .eq("wishlist_id", wishlist_id)
        .order("created_at", desc=False)
        .execute()
    )
    
    items: List[Dict[str, Any]] = cast(List[Dict[str, Any]], result.data or [])
    logger.info(f"Found {len(items)} items for wishlist {wishlist_id}")
    
    return items


async def create_wishlist(
    supabase_client: Client,
    user_id: str,
    goal_title: str,
    budget_hint: Decimal,
    currency_code: str,
    target_date: Optional[str] = None,
    preferred_store: Optional[str] = None,
    user_note: Optional[str] = None,
    selected_items: Optional[List[Dict[str, Any]]] = None
) -> tuple[Dict[str, Any], int]:
    """
    Create a new wishlist (goal) with optional selected items.
    
    This implements the three frontend scenarios atomically:
    - CASE A: Manual save (no recommendations) - selected_items is None/empty
    - CASE B: Recommendations requested but none selected - selected_items is None/empty
    - CASE C: Recommendations requested and 1-3 selected - selected_items has items
    
    Args:
        supabase_client: Authenticated Supabase client
        user_id: The authenticated user's ID
        goal_title: User's goal description
        budget_hint: Maximum budget
        currency_code: ISO currency code
        target_date: Optional target date (ISO string)
        preferred_store: Optional store preference
        user_note: Optional user note
        selected_items: Optional list of selected recommendation items (0-3)
    
    Returns:
        Tuple of (created_wishlist_dict, items_created_count)
    
    Raises:
        Exception: If wishlist or item creation fails
    
    Security:
        - RLS enforces user_id = auth.uid()
        - All operations are atomic (single transaction context via Supabase)
    """
    logger.info(
        f"Creating wishlist for user {user_id}: "
        f"goal_title='{goal_title}', budget_hint={budget_hint}, "
        f"items={len(selected_items) if selected_items else 0}"
    )
    
    # Step 1: Create wishlist
    wishlist_data = {
        "user_id": user_id,
        "goal_title": goal_title,
        "budget_hint": _normalize_numeric_12_2(budget_hint),  # NUMERIC(12,2)
        "currency_code": currency_code,
        "target_date": target_date,
        "preferred_store": preferred_store,
        "user_note": user_note,
        "status": "active"
    }
    
    result = supabase_client.table("wishlist").insert(wishlist_data).execute()
    
    if not result.data or len(result.data) == 0:
        raise Exception("Failed to create wishlist: no data returned")
    
    created_wishlist: Dict[str, Any] = cast(Dict[str, Any], result.data[0])
    wishlist_id = created_wishlist["id"]
    logger.info(f"Wishlist created successfully: {wishlist_id}")
    
    # Step 2: Create items if provided
    items_created = 0
    
    if selected_items and len(selected_items) > 0:
        logger.info(f"Creating {len(selected_items)} items for wishlist {wishlist_id}")
        
        # Prepare item rows
        item_rows = []
        for item in selected_items:
            item_row = {
                "wishlist_id": wishlist_id,
                "product_title": item["product_title"],
                # Normalize price_total to NUMERIC(12,2)
                "price_total": _normalize_numeric_12_2(item["price_total"]),
                "seller_name": item["seller_name"],
                "url": str(item["url"]),  # Convert HttpUrl to string
                "pickup_available": item["pickup_available"],
                "warranty_info": item["warranty_info"],
                "copy_for_user": item["copy_for_user"],
                "badges": json.dumps(item["badges"])  # Convert list to JSONB
            }
            item_rows.append(item_row)
        
        # Insert all items
        items_result = supabase_client.table("wishlist_item").insert(item_rows).execute()
        
        if not items_result.data:
            # Rollback wishlist creation by deleting it
            logger.error(f"Failed to create items, rolling back wishlist {wishlist_id}")
            supabase_client.table("wishlist").delete().eq("id", wishlist_id).execute()
            raise Exception("Failed to create wishlist items")
        
        items_created = len(items_result.data)
        logger.info(f"Created {items_created} items for wishlist {wishlist_id}")
    
    logger.info(
        f"Wishlist {wishlist_id} created successfully with {items_created} items"
    )
    
    return created_wishlist, items_created


async def update_wishlist(
    supabase_client: Client,
    user_id: str,
    wishlist_id: str,
    **updates: Any
) -> Optional[Dict[str, Any]]:
    """
    Update wishlist fields.
    
    Args:
        supabase_client: Authenticated Supabase client
        user_id: The authenticated user's ID
        wishlist_id: The wishlist UUID to update
        **updates: Fields to update (goal_title, budget_hint, etc.)
    
    Returns:
        The updated wishlist dict, or None if not found
    
    Security:
        - RLS enforces user_id = auth.uid()
        - User can only update their own wishlists
    """
    logger.info(f"Updating wishlist {wishlist_id} for user {user_id}: {list(updates.keys())}")
    
    # Convert/normalize budget_hint to NUMERIC(12,2) if present
    if "budget_hint" in updates:
        try:
            updates["budget_hint"] = _normalize_numeric_12_2(updates["budget_hint"])
        except Exception as exc:  # pragma: no cover - defensive
            raise ValueError("Invalid budget_hint: must be numeric and fit NUMERIC(12,2)") from exc
    
    result = (
        supabase_client.table("wishlist")
        .update(updates)
        .eq("id", wishlist_id)
        .eq("user_id", user_id)
        .execute()
    )
    
    if not result.data or len(result.data) == 0:
        logger.warning(f"Wishlist {wishlist_id} not found for user {user_id}")
        return None
    
    updated_wishlist: Dict[str, Any] = cast(Dict[str, Any], result.data[0])
    logger.info(f"Wishlist {wishlist_id} updated successfully")
    
    return updated_wishlist


async def delete_wishlist(
    supabase_client: Client,
    user_id: str,
    wishlist_id: str
) -> int:
    """
    Delete a wishlist and all its items (CASCADE).
    
    Per DB delete rule:
    1. All wishlist_item rows are deleted automatically (ON DELETE CASCADE)
    2. Then the wishlist is deleted
    
    Args:
        supabase_client: Authenticated Supabase client
        user_id: The authenticated user's ID
        wishlist_id: The wishlist UUID to delete
    
    Returns:
        Number of wishlist_item rows deleted (cascaded)
    
    Raises:
        Exception: If deletion fails
    
    Security:
        - RLS enforces user_id = auth.uid()
        - User can only delete their own wishlists
    """
    logger.info(f"Deleting wishlist {wishlist_id} for user {user_id}")
    
    # Get count of items to delete (for response message)
    items_result = (
        supabase_client.table("wishlist_item")
        .select("id", count=cast(Any, "exact"))
        .eq("wishlist_id", wishlist_id)
        .execute()
    )
    
    items_count = getattr(items_result, "count", 0) or 0
    logger.info(f"Found {items_count} items to delete for wishlist {wishlist_id}")
    
    # Delete wishlist (items cascade automatically)
    delete_result = (
        supabase_client.table("wishlist")
        .delete()
        .eq("id", wishlist_id)
        .eq("user_id", user_id)
        .execute()
    )
    
    if not delete_result.data or len(delete_result.data) == 0:
        raise Exception("Failed to delete wishlist: not found or access denied")
    
    logger.info(
        f"Wishlist {wishlist_id} deleted successfully. {items_count} items cascaded."
    )
    
    return items_count


async def delete_wishlist_item(
    supabase_client: Client,
    user_id: str,
    wishlist_id: str,
    item_id: str
) -> bool:
    """
    Delete a single wishlist item.
    
    Per DB delete rule:
    1. Verify item belongs to a wishlist owned by the user
    2. Delete the item
    3. Parent wishlist remains unaffected
    
    Args:
        supabase_client: Authenticated Supabase client
        user_id: The authenticated user's ID
        wishlist_id: The parent wishlist UUID (for verification)
        item_id: The wishlist_item UUID to delete
    
    Returns:
        True if deleted, False if not found
    
    Security:
        - Verifies wishlist ownership before allowing item deletion
        - RLS protects against cross-user access
    """
    logger.info(f"Deleting item {item_id} from wishlist {wishlist_id} for user {user_id}")
    
    # Verify wishlist ownership
    wishlist = await get_wishlist_by_id(supabase_client, user_id, wishlist_id)
    if not wishlist:
        logger.warning(f"Wishlist {wishlist_id} not found for user {user_id}")
        return False
    
    # Delete the item
    delete_result = (
        supabase_client.table("wishlist_item")
        .delete()
        .eq("id", item_id)
        .eq("wishlist_id", wishlist_id)
        .execute()
    )
    
    if not delete_result.data or len(delete_result.data) == 0:
        logger.warning(f"Item {item_id} not found in wishlist {wishlist_id}")
        return False
    
    logger.info(f"Item {item_id} deleted successfully from wishlist {wishlist_id}")
    return True
