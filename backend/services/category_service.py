"""
Category persistence service.

CRITICAL RULES (from DB documentation.md):
1. System categories (user_id IS NULL, key present) are read-only and CANNOT be deleted
2. When deleting a user category:
   - Update all transactions using that category_id to the 'general' system category
   - Remove all budget_category links
   - Then delete the category
3. RLS is enforced automatically via the authenticated Supabase client
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
) -> tuple[bool, int, int]:
    """
    Delete a user category following DB deletion rules.
    
    DB Documentation Rule:
    1. Update all transactions using this category_id to the 'general' system category
    2. Remove all budget_category links
    3. Delete the category
    4. System categories CANNOT be deleted
    
    Args:
        supabase_client: Authenticated Supabase client
        user_id: The authenticated user's ID
        category_id: UUID of the category to delete
    
    Returns:
        Tuple of (success, transactions_reassigned_count, budget_links_removed_count)
    
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
        return (False, 0, 0)
    
    # Prevent deleting system categories
    if existing.get("user_id") is None:
        raise Exception("Cannot delete system category")
    
    logger.info(f"Preparing to delete category {category_id} for user {user_id}")
    
    # Step 1: Find the 'general' system category (the reassignment target)
    general_result = (
        supabase_client.table("category")
        .select("id")
        .eq("key", "general")
        .is_("user_id", "null")
        .execute()
    )
    
    # Normalize and validate returned data
    general_data = cast(List[Dict[str, Any]], general_result.data) if general_result.data else []
    if not general_data or len(general_data) == 0:
        raise Exception("System 'general' category not found - database integrity issue")

    general_category_id = str(general_data[0].get("id"))
    logger.info(f"Found 'general' category: {general_category_id}")
    
    # Step 2: Reassign all transactions from deleted category to 'general'
    try:
        update_res = (
            supabase_client.table("transaction")
            .update({"category_id": general_category_id})
            .eq("category_id", category_id)
            .execute()
        )
        update_data = cast(List[Dict[str, Any]], update_res.data) if update_res.data else []
        transactions_reassigned = len(update_data)
        logger.info(f"Reassigned {transactions_reassigned} transaction(s) to 'general' category")
    except Exception as e:
        logger.error(f"Failed to reassign transactions for category {category_id}: {e}", exc_info=True)
        raise
    
    # Step 3: Remove all budget_category links
    try:
        delete_budget_links_res = (
            supabase_client.table("budget_category")
            .delete()
            .eq("category_id", category_id)
            .execute()
        )
        delete_budget_links_data = cast(List[Dict[str, Any]], delete_budget_links_res.data) if delete_budget_links_res.data else []
        budget_links_removed = len(delete_budget_links_data)
        logger.info(f"Removed {budget_links_removed} budget_category link(s)")
    except Exception as e:
        logger.error(f"Failed to remove budget_category links for category {category_id}: {e}", exc_info=True)
        raise
    
    # Step 4: Delete the category
    result = (
        supabase_client.table("category")
        .delete()
        .eq("id", category_id)
        .execute()
    )
    
    result_data = cast(List[Dict[str, Any]], result.data) if result.data else []
    if not result_data or len(result_data) == 0:
        logger.warning(f"Deletion of category {category_id} returned no rows")
        return (False, transactions_reassigned, budget_links_removed)
    
    logger.info(f"Category {category_id} deleted successfully for user {user_id}")
    
    return (True, transactions_reassigned, budget_links_removed)
