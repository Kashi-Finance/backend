"""
Category persistence service.

CRITICAL RULES (from DB-documentation.md):
1. System categories (user_id IS NULL, key present) are read-only and CANNOT be deleted
2. System categories use UNIQUE constraint on (key, flow_type)
3. When deleting a user category (FLOW-TYPE AWARE):
   - Default mode (cascade=False):
     * Determine the flow_type of the deleted category
     * Find matching 'general' system category (key='general', same flow_type)
     * Reassign all transactions to flow-type-matched general category
     * Remove all budget_category links
     * Delete the category
   - Cascade mode (cascade=True):
     * Delete all transactions referencing the category
     * Remove all budget_category links
     * Delete the category
4. RLS is enforced automatically via the authenticated Supabase client
"""

import logging
from typing import Dict, Any, Optional, List, cast

from supabase import Client

logger = logging.getLogger(__name__)


async def get_all_categories(
    supabase_client: Client,
    user_id: str,
    limit: int = 100,
    offset: int = 0,
) -> List[Dict[str, Any]]:
    """
    Fetch all categories available to the user.
    
    Returns:
    - System categories (user_id IS NULL)
    - User's personal categories (user_id = authenticated user)
    
    Args:
        supabase_client: Authenticated Supabase client
        user_id: The authenticated user's ID
        limit: Maximum number of categories to return
        offset: Number of categories to skip (for pagination)
    
    Returns:
        List of category records (system + user categories)
    
    Security:
        - System categories are visible to all users (read-only)
        - User categories filtered by RLS to owner only
    """
    logger.debug(f"Fetching categories for user {user_id} (limit={limit}, offset={offset})")
    
    # Query both system categories (user_id IS NULL) and user's personal categories
    result = (
        supabase_client.table("category")
        .select("*")
        .or_(f"user_id.is.null,user_id.eq.{user_id}")
        .order("name")
        .range(offset, offset + limit - 1)
        .execute()
    )
    
    categories = cast(List[Dict[str, Any]], result.data)
    
    logger.info(f"Fetched {len(categories)} categories for user {user_id}")
    
    return categories


async def create_category(
    supabase_client: Client,
    user_id: str,
    name: str,
    flow_type: str,
) -> Dict[str, Any]:
    """
    Create a new user category.
    
    Args:
        supabase_client: Authenticated Supabase client
        user_id: The authenticated user's ID
        name: Category display name
        flow_type: "income" or "outcome"
    
    Returns:
        The created category record
    
    Raises:
        Exception: If the database operation fails
    
    Security:
        - RLS enforces that user_id = auth.uid()
        - User can only create categories for themselves
        - System categories (user_id=NULL) cannot be created via this function
    """
    category_data = {
        "user_id": user_id,
        "name": name,
        "flow_type": flow_type,
        # key is NULL for user categories (only system categories have keys)
    }
    
    logger.info(f"Creating category for user {user_id}: name={name}, flow_type={flow_type}")
    
    result = supabase_client.table("category").insert(category_data).execute()
    
    if not result.data or len(result.data) == 0:
        raise Exception("Failed to create category: no data returned")
    
    created_category = cast(Dict[str, Any], result.data[0])
    
    logger.info(f"Category created successfully: id={created_category.get('id')}, user_id={user_id}")
    
    return created_category


async def get_category_by_id(
    supabase_client: Client,
    user_id: str,
    category_id: str,
) -> Optional[Dict[str, Any]]:
    """
    Fetch a single category by its ID.
    
    Args:
        supabase_client: Authenticated Supabase client
        user_id: The authenticated user's ID
        category_id: UUID of the category to fetch
    
    Returns:
        Category record if found and accessible, None otherwise
    
    Security:
        - User can access system categories (user_id IS NULL)
        - User can access their own categories (user_id = auth.uid())
        - User cannot access other users' categories
    """
    logger.debug(f"Fetching category {category_id} for user {user_id}")
    
    result = (
        supabase_client.table("category")
        .select("*")
        .eq("id", category_id)
        .execute()
    )
    
    if not result.data or len(result.data) == 0:
        logger.warning(f"Category {category_id} not found or not accessible by user {user_id}")
        return None
    
    category = cast(Dict[str, Any], result.data[0])
    
    # Verify access: must be system category OR user's own category
    if category.get("user_id") is not None and category.get("user_id") != user_id:
        logger.warning(f"Category {category_id} belongs to another user")
        return None
    
    logger.info(f"Fetched category {category_id} for user {user_id}")
    
    return category


async def update_category(
    supabase_client: Client,
    user_id: str,
    category_id: str,
    name: Optional[str] = None,
) -> Optional[Dict[str, Any]]:
    """
    Update a user category.
    
    Args:
        supabase_client: Authenticated Supabase client
        user_id: The authenticated user's ID
        category_id: UUID of the category to update
        name: New category name (optional)
    
    Returns:
        Updated category record if successful, None if not found or not accessible
    
    Raises:
        Exception: If trying to update a system category
    
    Security:
        - User can only update their own categories
        - System categories (user_id IS NULL) cannot be updated
    
    NOTE: flow_type is NOT editable. Changing flow_type would affect all transactions
    in that category, impacting balances and dependent data structures.
    """
    # First verify the category exists and is owned by user
    existing = await get_category_by_id(supabase_client, user_id, category_id)
    if not existing:
        return None
    
    # Prevent updating system categories
    if existing.get("user_id") is None:
        raise Exception("Cannot update system category")
    
    # Build update payload with only provided fields
    update_data: Dict[str, Any] = {}
    if name is not None:
        update_data["name"] = name
    
    if not update_data:
        # No fields to update
        return existing
    
    logger.info(f"Updating category {category_id} for user {user_id}: {update_data}")
    
    result = (
        supabase_client.table("category")
        .update(update_data)
        .eq("id", category_id)
        .execute()
    )
    
    if not result.data or len(result.data) == 0:
        logger.warning(f"Update of category {category_id} returned no rows")
        return None
    
    updated_category = cast(Dict[str, Any], result.data[0])
    
    logger.info(f"Category {category_id} updated successfully")
    
    return updated_category


async def delete_category(
    supabase_client: Client,
    user_id: str,
    category_id: str,
    cascade: bool = False,
) -> tuple[bool, int, int, int]:
    """
    Delete a user category following DB deletion rules.
    
    DB Rule (FLOW-TYPE AWARE):
    - Default (cascade=False):
      1. Determine the flow_type of the category being deleted
      2. Find the matching 'general' system category (key='general', same flow_type)
      3. Reassign all transactions to the flow-type-matched general category
      4. Remove all budget_category links
      5. Delete the category
    
    - Cascade Mode (cascade=True):
      1. Delete all transactions referencing this category (ON DELETE CASCADE behavior)
      2. Remove all budget_category links
      3. Delete the category
    
    - System categories CANNOT be deleted
    
    Flow-Type Matching:
    - If deleted category is flow_type='outcome', reassigns to 'general' outcome category
    - If deleted category is flow_type='income', reassigns to 'general' income category
    
    Args:
        supabase_client: Authenticated Supabase client
        user_id: The authenticated user's ID
        category_id: UUID of the category to delete
        cascade: If True, delete transactions instead of reassigning (default: False)
    
    Returns:
        Tuple of (success, transactions_reassigned, budget_links_removed, transactions_deleted)
        - transactions_reassigned: count when cascade=False
        - transactions_deleted: count when cascade=True
    
    Raises:
        Exception: If trying to delete a system category or if DB operation fails
    
    Security:
        - User can only delete their own categories
        - System categories are protected from deletion
    """
    # First verify the category exists and is owned by user
    existing = await get_category_by_id(supabase_client, user_id, category_id)
    if not existing:
        logger.warning(f"Cannot delete category {category_id}: not found or not accessible by user {user_id}")
        return (False, 0, 0, 0)
    
    # Prevent deleting system categories
    if existing.get("user_id") is None:
        raise Exception("Cannot delete system category")
    
    mode = "CASCADE" if cascade else "REASSIGN"
    logger.info(f"Preparing to delete category {category_id} for user {user_id} (mode={mode})")

    # Delegate reassign + delete to DB RPC for atomicity (avoids race conditions)
    try:
        rpc_res = supabase_client.rpc(
            "delete_category_reassign",
            {
                "p_category_id": category_id,
                "p_user_id": user_id,
                "p_cascade": cascade,
            },
        ).execute()

        data = getattr(rpc_res, "data", None)
        if not isinstance(data, list) or len(data) == 0:
            logger.warning(f"RPC delete_category_reassign returned no rows for category {category_id}")
            return (False, 0, 0, 0)

        row = cast(Dict[str, Any], data[0])
        transactions_reassigned = int(row.get("transactions_reassigned") or 0)
        budget_links_removed = int(row.get("budget_links_removed") or 0)
        transactions_deleted = int(row.get("transactions_deleted") or 0)
        
        logger.info(
            f"Category {category_id} deleted via RPC (mode={mode}): "
            f"reassigned={transactions_reassigned}, deleted={transactions_deleted}, links_removed={budget_links_removed}"
        )
        return (True, transactions_reassigned, budget_links_removed, transactions_deleted)
    except Exception as e:
        logger.error(f"Failed to delete category via RPC for {category_id}: {e}", exc_info=True)
        raise
