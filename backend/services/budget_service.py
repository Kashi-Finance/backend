"""
Budget persistence service.

CRITICAL RULES:
1. Budgets track spending limits over time for one or more categories
2. Categories are linked via budget_category junction table
3. When deleting a budget:
   - First delete all budget_category links
   - Then delete the budget
   - Never delete transactions (they remain as history)
4. RLS is enforced automatically via the authenticated Supabase client
"""

import logging
from typing import Any, Dict, List, Optional, cast

from supabase import Client

logger = logging.getLogger(__name__)


async def get_all_budgets(
    supabase_client: Client,
    user_id: str,
    limit: int = 50,
    offset: int = 0,
    frequency: Optional[str] = None,
    is_active: Optional[bool] = None,
) -> List[Dict[str, Any]]:
    """
    Fetch all budgets for the user with their linked categories.

    Uses Supabase JOIN to fetch budget_category relationships and category details.

    Args:
        supabase_client: Authenticated Supabase client
        user_id: The authenticated user's ID
        limit: Maximum number of budgets to return (default 50)
        offset: Number of budgets to skip for pagination (default 0)
        frequency: Optional filter by budget frequency (daily/weekly/monthly/yearly/once)
        is_active: Optional filter by active status

    Returns:
        List of budget records with embedded categories

    Security:
        - RLS enforces user_id = auth.uid()
        - User can only access their own budgets
    """
    logger.debug(
        f"Fetching budgets with categories for user {user_id} "
        f"(limit={limit}, offset={offset}, filters: frequency={frequency}, is_active={is_active})"
    )

    # Use Supabase foreign key syntax to join budget_category and category
    # Select full category records so the API can return every category field
    query = (
        supabase_client.table("budget")
        .select("""
            *,
            budget_category(
                category:category_id(*)
            )
        """)
        .eq("user_id", user_id)
    )

    # Apply filters
    if frequency:
        query = query.eq("frequency", frequency)
    if is_active is not None:
        query = query.eq("is_active", is_active)

    # Apply pagination
    result = query.order("created_at", desc=True).range(offset, offset + limit - 1).execute()

    budgets_raw = cast(List[Dict[str, Any]], result.data or [])

    # Transform nested structure to flat categories list
    budgets = []
    for budget_raw in budgets_raw:
        budget = {k: v for k, v in budget_raw.items() if k != "budget_category"}

        # Extract categories from budget_category junction
        categories = []
        if "budget_category" in budget_raw and budget_raw["budget_category"]:
            for link in budget_raw["budget_category"]:
                if link and "category" in link and link["category"]:
                    cat = link["category"]
                    # Include every field from the category record so the
                    # frontend can reuse DTOs without losing timestamps/user_id.
                    # Convert id to string for consistency.
                    full_cat = {k: v for k, v in cat.items()} if isinstance(cat, dict) else {}
                    if "id" in full_cat:
                        full_cat["id"] = str(full_cat["id"])
                    categories.append(full_cat)

        budget["categories"] = categories
        budgets.append(budget)

    logger.info(f"Fetched {len(budgets)} budgets with categories for user {user_id}")

    return budgets


async def get_budget_by_id(
    supabase_client: Client,
    user_id: str,
    budget_id: str
) -> Optional[Dict[str, Any]]:
    """
    Fetch a single budget by its ID with linked categories.

    Uses Supabase JOIN to fetch budget_category relationships and category details.

    Args:
        supabase_client: Authenticated Supabase client
        user_id: The authenticated user's ID
        budget_id: UUID of the budget to fetch

    Returns:
        Budget record with embedded categories if found and accessible, None otherwise

    Security:
        - User can only access their own budgets
        - RLS enforces user_id = auth.uid()
    """
    logger.debug(f"Fetching budget {budget_id} with categories for user {user_id}")

    # Select full category records so the API can return every category field
    result = (
        supabase_client.table("budget")
        .select("""
            *,
            budget_category(
                category:category_id(*)
            )
        """)
        .eq("id", budget_id)
        .eq("user_id", user_id)
        .execute()
    )

    if not result.data or len(result.data) == 0:
        logger.warning(f"Budget {budget_id} not found or not accessible by user {user_id}")
        return None

    budget_raw = cast(Dict[str, Any], result.data[0])

    # Transform nested structure to flat categories list
    budget = {k: v for k, v in budget_raw.items() if k != "budget_category"}

    # Extract categories from budget_category junction
    categories = []
    if "budget_category" in budget_raw and budget_raw["budget_category"]:
        for link in budget_raw["budget_category"]:
            if link and "category" in link and link["category"]:
                cat = link["category"]
                # Include every field from the category record so the
                # frontend can reuse DTOs without losing timestamps/user_id.
                full_cat = {k: v for k, v in cat.items()} if isinstance(cat, dict) else {}
                if "id" in full_cat:
                    full_cat["id"] = str(full_cat["id"])
                categories.append(full_cat)

    budget["categories"] = categories

    logger.info(f"Fetched budget {budget_id} with {len(categories)} categories for user {user_id}")

    return budget


async def create_budget(
    supabase_client: Client,
    user_id: str,
    name: Optional[str],
    limit_amount: float,
    frequency: str,
    interval: int,
    start_date: str,
    end_date: Optional[str],
    is_active: bool,
    category_ids: List[str]
) -> tuple[Dict[str, Any], int]:
    """
    Create a new budget and link categories.

    The budget currency is automatically set to the user's profile.currency_preference.

    Args:
        supabase_client: Authenticated Supabase client
        user_id: The authenticated user's ID
        name: Optional user-friendly name for the budget
        limit_amount: Maximum spend for budget period
        frequency: Budget repetition cadence
        interval: How often budget repeats
        start_date: When budget starts (ISO-8601 date)
        end_date: When budget ends (optional)
        is_active: Whether budget is active
        category_ids: List of category UUIDs to link

    Returns:
        Tuple of (created budget, number of categories linked)

    Raises:
        Exception: If the database operation fails or user profile not found

    Security:
        - RLS enforces that user_id = auth.uid()
        - User can only create budgets for themselves
        - Currency is auto-populated from profile (single-currency-per-user policy)
    """
    # Get user's currency from profile (single-currency-per-user policy)
    currency_result = supabase_client.rpc(
        'get_user_currency',
        {'p_user_id': user_id}
    ).execute()

    if not currency_result.data:
        raise Exception("Failed to get user currency: profile not found")

    user_currency = currency_result.data

    budget_data = {
        "user_id": user_id,
        "name": name,
        "limit_amount": limit_amount,
        "currency": user_currency,  # Auto-populated from profile
        "frequency": frequency,
        "interval": interval,
        "start_date": start_date,
        "end_date": end_date,
        "is_active": is_active
    }

    logger.info(f"Creating budget for user {user_id}: limit={limit_amount} {user_currency}, frequency={frequency}")

    result = supabase_client.table("budget").insert(budget_data).execute()

    if not result.data or len(result.data) == 0:
        raise Exception("Failed to create budget: no data returned")

    created_budget = cast(Dict[str, Any], result.data[0])
    budget_id = str(created_budget.get("id"))

    logger.info(f"Budget created successfully: {budget_id}")

    # Link categories via budget_category
    categories_linked = 0
    if category_ids:
        budget_category_links = [
            {
                "budget_id": budget_id,
                "category_id": cat_id,
                "user_id": user_id
            }
            for cat_id in category_ids
        ]

        link_result = (
            supabase_client.table("budget_category")
            .insert(budget_category_links)
            .execute()
        )

        if link_result.data:
            categories_linked = len(link_result.data)
            logger.info(f"Linked {categories_linked} categories to budget {budget_id}")

    # Re-fetch budget with categories to include in response
    budget_with_categories = await get_budget_by_id(supabase_client, user_id, budget_id)
    if not budget_with_categories:
        # Fallback to created_budget without categories if fetch fails
        logger.warning(f"Could not re-fetch budget {budget_id} with categories")
        created_budget["categories"] = []
        return created_budget, categories_linked

    return budget_with_categories, categories_linked


async def update_budget(
    supabase_client: Client,
    user_id: str,
    budget_id: str,
    **updates: Any
) -> Optional[Dict[str, Any]]:
    """
    Update a budget.

    Args:
        supabase_client: Authenticated Supabase client
        user_id: The authenticated user's ID
        budget_id: UUID of the budget to update
        **updates: Fields to update

    Returns:
        Updated budget record if successful, None if not found or not accessible

    Raises:
        Exception: If trying to update a budget that doesn't belong to user

    Security:
        - User can only update their own budgets
        - RLS enforces user_id = auth.uid()

    NOTE: This does not update budget_category links. Use separate endpoints
    for adding/removing category links.
    """
    # First verify the budget exists and is owned by user
    existing = await get_budget_by_id(supabase_client, user_id, budget_id)
    if not existing:
        return None

    logger.info(f"Updating budget {budget_id} for user {user_id}: {list(updates.keys())}")

    result = (
        supabase_client.table("budget")
        .update(updates)
        .eq("id", budget_id)
        .eq("user_id", user_id)
        .execute()
    )

    if not result.data or len(result.data) == 0:
        logger.warning(f"Budget {budget_id} not found for user {user_id}")
        return None

    logger.info(f"Budget {budget_id} updated successfully")

    # Re-fetch budget with categories to include in response
    updated_budget_with_categories = await get_budget_by_id(supabase_client, user_id, budget_id)

    return updated_budget_with_categories


async def delete_budget(
    supabase_client: Client,
    user_id: str,
    budget_id: str
) -> tuple[bool, str | None]:
    """
    Soft-delete a user budget using the delete_budget RPC.

    This function:
    1. Calls the delete_budget RPC for atomic soft-delete operation
    2. RPC validates ownership and sets deleted_at timestamp
    3. budget_category junction rows remain (for historical analysis)

    Args:
        supabase_client: Authenticated Supabase client
        user_id: The authenticated user's ID
        budget_id: UUID of the budget to soft-delete

    Returns:
        Tuple of (success, deleted_at timestamp or None)

    Raises:
        Exception: If RPC call fails

    Security:
        - RPC validates user_id ownership before soft-deleting
        - User can only delete their own budgets
    """
    logger.info(f"Preparing to soft-delete budget {budget_id} for user {user_id}")

    try:
        # Call the delete_budget RPC for atomic soft-delete
        rpc_res = supabase_client.rpc(
            "delete_budget",
            {
                "p_budget_id": budget_id,
                "p_user_id": user_id,
            },
        ).execute()

        data = getattr(rpc_res, "data", None)
        if not isinstance(data, list) or len(data) == 0:
            logger.warning(f"RPC delete_budget returned no rows for budget {budget_id}")
            return (False, None)

        row = cast(Dict[str, Any], data[0])
        budget_soft_deleted = bool(row.get("budget_soft_deleted", False))
        deleted_at = row.get("deleted_at")

        if budget_soft_deleted:
            logger.info(f"Budget {budget_id} soft-deleted successfully via RPC at {deleted_at}")
            return (True, deleted_at)
        else:
            logger.warning(f"Budget {budget_id} soft-delete failed via RPC")
            return (False, None)

    except Exception as e:
        logger.error(f"Failed to soft-delete budget via RPC for {budget_id}: {e}", exc_info=True)
        raise
