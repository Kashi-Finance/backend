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

SUBCATEGORY RULES:
1. Categories can have subcategories (max depth: 1 - parent -> child only)
2. parent_category_id links a subcategory to its parent
3. Parent and child MUST have same flow_type and user_id
4. System categories CANNOT be parents or children
5. Subcategories can be created inline with parent category
6. When deleting a parent, subcategories become top-level (parent_category_id = NULL)
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
    include_subcategories: bool = False,
    parent_only: bool = False,
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
        include_subcategories: If True, nest subcategories under their parents
        parent_only: If True, only return top-level categories (parent_category_id IS NULL)
    
    Returns:
        List of category records (system + user categories)
        When include_subcategories=True, each parent has a 'subcategories' field
    
    Security:
        - System categories are visible to all users (read-only)
        - User categories filtered by RLS to owner only
    """
    logger.debug(f"Fetching categories for user {user_id} (limit={limit}, offset={offset}, include_subcategories={include_subcategories})")
    
    # Build query
    query = supabase_client.table("category").select("*")
    
    # Filter by system OR user's categories
    query = query.or_(f"user_id.is.null,user_id.eq.{user_id}")
    
    # If parent_only, filter to top-level categories
    if parent_only:
        query = query.is_("parent_category_id", "null")
    
    # Order and paginate
    query = query.order("name").range(offset, offset + limit - 1)
    
    result = query.execute()
    
    categories = cast(List[Dict[str, Any]], result.data)
    
    if include_subcategories:
        # Build a mapping of parent_id -> list of children
        parent_map: Dict[str, List[Dict[str, Any]]] = {}
        top_level: List[Dict[str, Any]] = []
        
        for cat in categories:
            parent_id = cat.get("parent_category_id")
            if parent_id is None:
                # Top-level category
                cat["subcategories"] = []
                top_level.append(cat)
            else:
                # Subcategory - add to parent's list
                if parent_id not in parent_map:
                    parent_map[parent_id] = []
                parent_map[parent_id].append(cat)
        
        # Attach subcategories to their parents
        for cat in top_level:
            cat_id = cat.get("id")
            if cat_id in parent_map:
                cat["subcategories"] = parent_map[cat_id]
        
        categories = top_level
    
    logger.info(f"Fetched {len(categories)} categories for user {user_id}")
    
    return categories


async def get_subcategories(
    supabase_client: Client,
    user_id: str,
    parent_category_id: str,
) -> List[Dict[str, Any]]:
    """
    Fetch all subcategories for a given parent category.
    
    Args:
        supabase_client: Authenticated Supabase client
        user_id: The authenticated user's ID
        parent_category_id: UUID of the parent category
    
    Returns:
        List of subcategory records
    """
    logger.debug(f"Fetching subcategories for parent {parent_category_id}")
    
    result = (
        supabase_client.table("category")
        .select("*")
        .eq("parent_category_id", parent_category_id)
        .order("name")
        .execute()
    )
    
    subcategories = cast(List[Dict[str, Any]], result.data)
    
    logger.info(f"Fetched {len(subcategories)} subcategories for parent {parent_category_id}")
    
    return subcategories


async def create_category(
    supabase_client: Client,
    user_id: str,
    name: str,
    flow_type: str,
    icon: str,
    color: str,
    parent_category_id: Optional[str] = None,
    subcategories: Optional[List[Dict[str, str]]] = None,
) -> tuple[Dict[str, Any], int]:
    """
    Create a new user category with optional inline subcategories.
    
    Args:
        supabase_client: Authenticated Supabase client
        user_id: The authenticated user's ID
        name: Category display name
        flow_type: "income" or "outcome"
        icon: Icon identifier for UI display
        color: Hex color code for UI display (e.g., '#4CAF50')
        parent_category_id: If provided, creates this as a subcategory
        subcategories: List of inline subcategory definitions (name, icon, color)
    
    Returns:
        Tuple of (created_category, subcategories_created_count)
        The created_category includes 'subcategories' field if any were created
    
    Raises:
        Exception: If the database operation fails
        ValueError: If parent category validation fails
    
    Security:
        - RLS enforces that user_id = auth.uid()
        - User can only create categories for themselves
        - System categories (user_id=NULL) cannot be created via this function
    """
    # Validate parent_category_id if provided
    if parent_category_id:
        parent = await get_category_by_id(supabase_client, user_id, parent_category_id)
        if not parent:
            raise ValueError(f"Parent category {parent_category_id} not found or not accessible")
        
        # Ensure parent is a user category (not system)
        if parent.get("user_id") is None:
            raise ValueError("Cannot create subcategory under a system category")
        
        # Ensure same user owns the parent
        if parent.get("user_id") != user_id:
            raise ValueError("Parent category belongs to a different user")
        
        # Ensure flow_type matches parent
        if parent.get("flow_type") != flow_type:
            raise ValueError(f"Subcategory flow_type ({flow_type}) must match parent flow_type ({parent.get('flow_type')})")
        
        # Ensure parent is not already a subcategory (max depth = 1)
        if parent.get("parent_category_id") is not None:
            raise ValueError("Cannot create subcategory under another subcategory. Maximum depth is 1.")
    
    category_data = {
        "user_id": user_id,
        "name": name,
        "flow_type": flow_type,
        "icon": icon,
        "color": color.upper(),  # Normalize to uppercase hex
        "parent_category_id": parent_category_id,
        # key is NULL for user categories (only system categories have keys)
    }
    
    logger.info(f"Creating category for user {user_id}: name={name}, flow_type={flow_type}, icon={icon}, color={color}, parent={parent_category_id}")
    
    result = supabase_client.table("category").insert(category_data).execute()
    
    if not result.data or len(result.data) == 0:
        raise Exception("Failed to create category: no data returned")
    
    created_category = cast(Dict[str, Any], result.data[0])
    created_category["subcategories"] = []
    subcategories_created = 0
    
    # Create inline subcategories if provided
    if subcategories and len(subcategories) > 0:
        # Cannot create subcategories if this category is already a subcategory
        if parent_category_id:
            raise ValueError("Cannot create subcategories for a category that is itself a subcategory. Maximum depth is 1.")
        
        parent_id = created_category["id"]
        for sub in subcategories:
            sub_data = {
                "user_id": user_id,
                "name": sub["name"],
                "flow_type": flow_type,  # Inherit from parent
                "icon": sub["icon"],
                "color": sub["color"].upper(),
                "parent_category_id": parent_id,
            }
            sub_result = supabase_client.table("category").insert(sub_data).execute()
            if sub_result.data and len(sub_result.data) > 0:
                created_category["subcategories"].append(sub_result.data[0])
                subcategories_created += 1
        
        logger.info(f"Created {subcategories_created} subcategories for category {parent_id}")
    
    logger.info(f"Category created successfully: id={created_category.get('id')}, user_id={user_id}")
    
    return (created_category, subcategories_created)


async def get_category_by_id(
    supabase_client: Client,
    user_id: str,
    category_id: str,
    include_subcategories: bool = False,
) -> Optional[Dict[str, Any]]:
    """
    Fetch a single category by its ID.
    
    Args:
        supabase_client: Authenticated Supabase client
        user_id: The authenticated user's ID
        category_id: UUID of the category to fetch
        include_subcategories: If True, include subcategories in response
    
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
    
    # Include subcategories if requested
    if include_subcategories:
        subcategories = await get_subcategories(supabase_client, user_id, category_id)
        category["subcategories"] = subcategories
    
    logger.info(f"Fetched category {category_id} for user {user_id}")
    
    return category


async def update_category(
    supabase_client: Client,
    user_id: str,
    category_id: str,
    name: Optional[str] = None,
    icon: Optional[str] = None,
    color: Optional[str] = None,
) -> Optional[Dict[str, Any]]:
    """
    Update a user category.
    
    Args:
        supabase_client: Authenticated Supabase client
        user_id: The authenticated user's ID
        category_id: UUID of the category to update
        name: New category name (optional)
        icon: New icon identifier (optional)
        color: New hex color code (optional)
    
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
    if icon is not None:
        update_data["icon"] = icon
    if color is not None:
        update_data["color"] = color.upper()  # Normalize to uppercase hex
    
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
) -> tuple[bool, int, int, int, int]:
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
    
    Subcategory Handling:
    - When deleting a parent category, subcategories become top-level (parent_category_id = NULL)
    - The database ON DELETE CASCADE handles this automatically
    
    Flow-Type Matching:
    - If deleted category is flow_type='outcome', reassigns to 'general' outcome category
    - If deleted category is flow_type='income', reassigns to 'general' income category
    
    Args:
        supabase_client: Authenticated Supabase client
        user_id: The authenticated user's ID
        category_id: UUID of the category to delete
        cascade: If True, delete transactions instead of reassigning (default: False)
    
    Returns:
        Tuple of (success, transactions_reassigned, budget_links_removed, transactions_deleted, subcategories_orphaned)
        - transactions_reassigned: count when cascade=False
        - transactions_deleted: count when cascade=True
        - subcategories_orphaned: count of subcategories that became top-level
    
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
        return (False, 0, 0, 0, 0)
    
    # Prevent deleting system categories
    if existing.get("user_id") is None:
        raise Exception("Cannot delete system category")
    
    # Count subcategories that will be orphaned (become top-level)
    subcategories = await get_subcategories(supabase_client, user_id, category_id)
    subcategories_orphaned = len(subcategories)
    
    mode = "CASCADE" if cascade else "REASSIGN"
    logger.info(f"Preparing to delete category {category_id} for user {user_id} (mode={mode}, orphaned_subcategories={subcategories_orphaned})")

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
            return (False, 0, 0, 0, 0)

        row = cast(Dict[str, Any], data[0])
        transactions_reassigned = int(row.get("transactions_reassigned") or 0)
        budget_links_removed = int(row.get("budget_links_removed") or 0)
        transactions_deleted = int(row.get("transactions_deleted") or 0)
        
        logger.info(
            f"Category {category_id} deleted via RPC (mode={mode}): "
            f"reassigned={transactions_reassigned}, deleted={transactions_deleted}, links_removed={budget_links_removed}, orphaned={subcategories_orphaned}"
        )
        return (True, transactions_reassigned, budget_links_removed, transactions_deleted, subcategories_orphaned)
    except Exception as e:
        logger.error(f"Failed to delete category via RPC for {category_id}: {e}", exc_info=True)
        raise
