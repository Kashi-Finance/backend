"""
Account service.

Handles CRUD operations for user accounts with proper delete rule enforcement.
Accounts are financial containers (cash, bank, credit card, etc.) that track
balances via transaction history.
"""

import logging
from typing import Dict, Any, Optional, List, cast

from supabase import Client

logger = logging.getLogger(__name__)


async def get_user_accounts(
    supabase_client: Client,
    user_id: str,
    limit: int = 50,
    offset: int = 0
) -> List[Dict[str, Any]]:
    """
    Fetch all accounts belonging to the user with pagination support.
    
    Args:
        supabase_client: Authenticated Supabase client
        user_id: The authenticated user's ID
        limit: Maximum number of accounts to return (default 50)
        offset: Number of accounts to skip for pagination (default 0)
    
    Returns:
        List of account dicts
    
    Security:
        - RLS enforces user_id = auth.uid()
        - User can only access their own accounts
    """
    logger.debug(f"Fetching accounts for user {user_id} (limit={limit}, offset={offset})")
    
    result = (
        supabase_client.table("account")
        .select("*")
        .eq("user_id", user_id)
        .order("created_at", desc=True)
        .range(offset, offset + limit - 1)
        .execute()
    )
    
    accounts: List[Dict[str, Any]] = cast(List[Dict[str, Any]], result.data or [])
    logger.info(f"Found {len(accounts)} accounts for user {user_id}")
    
    return accounts


async def get_account_by_id(
    supabase_client: Client,
    user_id: str,
    account_id: str
) -> Optional[Dict[str, Any]]:
    """
    Fetch a single account by ID.
    
    Args:
        supabase_client: Authenticated Supabase client
        user_id: The authenticated user's ID
        account_id: The account UUID
    
    Returns:
        Account dict, or None if not found
    
    Security:
        - RLS enforces user_id = auth.uid()
        - User can only access their own accounts
    """
    logger.debug(f"Fetching account {account_id} for user {user_id}")
    
    result = (
        supabase_client.table("account")
        .select("*")
        .eq("id", account_id)
        .eq("user_id", user_id)
        .execute()
    )
    
    if not result.data or len(result.data) == 0:
        logger.warning(f"Account {account_id} not found for user {user_id}")
        return None
    
    account: Dict[str, Any] = cast(Dict[str, Any], result.data[0])
    logger.info(f"Account {account_id} found for user {user_id}")
    
    return account


async def create_account(
    supabase_client: Client,
    user_id: str,
    name: str,
    account_type: str,
    currency: str,
    icon: str,
    color: str,
    is_favorite: bool = False,
    is_pinned: bool = False,
    description: Optional[str] = None
) -> Dict[str, Any]:
    """
    Create a new account.
    
    Args:
        supabase_client: Authenticated Supabase client
        user_id: The authenticated user's ID
        name: Human-readable account name
        account_type: Account type (cash, bank, credit_card, etc.)
        currency: ISO currency code (must match profile.currency_preference)
        icon: Icon identifier for UI display
        color: Hex color code for UI display (e.g., '#FF5733')
        is_favorite: If true, set as user's favorite account (clears previous favorite)
        is_pinned: If true, pin account to top of list
        description: Optional description for the account
    
    Returns:
        The created account dict
    
    Raises:
        ValueError: If currency doesn't match user's profile.currency_preference
    
    Security:
        - RLS enforces user_id = auth.uid()
        - User can only create accounts for themselves
        - Single-currency-per-user policy enforced
    """
    # Validate currency matches user's profile (single-currency-per-user policy)
    try:
        supabase_client.rpc(
            'validate_user_currency',
            {'p_user_id': user_id, 'p_currency': currency}
        ).execute()
    except Exception as e:
        error_msg = str(e)
        if "Currency mismatch" in error_msg:
            raise ValueError(
                f"Currency '{currency}' does not match your profile currency. "
                "All accounts must use the same currency as your profile."
            )
        raise
    
    account_data = {
        "user_id": user_id,
        "name": name,
        "type": account_type,
        "currency": currency,
        "icon": icon,
        "color": color.upper(),  # Normalize to uppercase hex
        "is_favorite": False,  # Will be set via RPC if requested
        "is_pinned": is_pinned,
        "description": description
    }
    
    logger.info(
        f"Creating account for user {user_id}: "
        f"name='{name}', type={account_type}, currency={currency}, "
        f"icon={icon}, color={color}, is_pinned={is_pinned}"
    )
    
    result = supabase_client.table("account").insert(account_data).execute()
    
    if not result.data or len(result.data) == 0:
        raise Exception("Failed to create account: no data returned")
    
    created_account: Dict[str, Any] = cast(Dict[str, Any], result.data[0])
    logger.info(f"Account created successfully: {created_account['id']}")
    
    # If is_favorite requested, use RPC to safely set it (clears previous favorite)
    if is_favorite:
        try:
            await set_favorite_account(supabase_client, user_id, created_account['id'])
            # Refresh account data to get updated is_favorite status
            created_account['is_favorite'] = True
        except Exception as e:
            logger.warning(f"Failed to set account {created_account['id']} as favorite: {e}")
            # Account was created, just couldn't set favorite - not critical
    
    return created_account


async def update_account(
    supabase_client: Client,
    user_id: str,
    account_id: str,
    **updates: Any
) -> Optional[Dict[str, Any]]:
    """
    Update account fields.
    
    Args:
        supabase_client: Authenticated Supabase client
        user_id: The authenticated user's ID
        account_id: The account UUID to update
        **updates: Fields to update (name, type, icon, color, is_pinned, description)
                   - currency cannot be changed (single-currency-per-user policy)
                   - is_favorite should be managed via set_favorite_account RPC
    
    Returns:
        The updated account dict, or None if not found
    
    Raises:
        ValueError: If attempting to change currency (not allowed under single-currency policy)
    
    Security:
        - RLS enforces user_id = auth.uid()
        - User can only update their own accounts
        - Currency changes are blocked (single-currency-per-user policy)
    """
    # Block currency changes - single-currency-per-user policy
    if 'currency' in updates:
        raise ValueError(
            "Currency cannot be changed after account creation. "
            "All accounts must use the same currency as your profile."
        )
    
    # Block direct is_favorite changes - must use RPC for data integrity
    if 'is_favorite' in updates:
        raise ValueError(
            "is_favorite cannot be changed directly. "
            "Use the set_favorite_account or clear_favorite_account endpoints."
        )
    
    # Normalize color to uppercase if provided
    if 'color' in updates and updates['color']:
        updates['color'] = updates['color'].upper()
    
    logger.info(f"Updating account {account_id} for user {user_id}: {list(updates.keys())}")
    
    result = (
        supabase_client.table("account")
        .update(updates)
        .eq("id", account_id)
        .eq("user_id", user_id)
        .execute()
    )
    
    if not result.data or len(result.data) == 0:
        logger.warning(f"Account {account_id} not found for user {user_id}")
        return None
    
    updated_account: Dict[str, Any] = cast(Dict[str, Any], result.data[0])
    logger.info(f"Account {account_id} updated successfully")
    
    return updated_account


async def delete_account_with_reassignment(
    supabase_client: Client,
    user_id: str,
    account_id: str,
    target_account_id: str
) -> int:
    """
    Soft-delete account by reassigning all transactions to another account.
    
    Uses RPC function `delete_account_reassign` for atomic operation.
    This implements DB delete rule Option 1 with soft-delete strategy:
    1. Reassign all recurring templates to target_account_id
    2. Reassign all transactions to target_account_id
    3. Soft-delete the source account (set deleted_at)
    
    Args:
        supabase_client: Authenticated Supabase client
        user_id: The authenticated user's ID
        account_id: The account UUID to soft-delete
        target_account_id: The account UUID to receive transactions
    
    Returns:
        Number of transactions reassigned
    
    Raises:
        ValueError: If accounts are invalid or validation fails
        Exception: If RPC call fails
    
    Security:
        - RPC validates both accounts belong to user_id
        - All operations happen atomically in DB
        - Source account is soft-deleted (deleted_at set), not physically removed
    """
    logger.info(
        f"Soft-deleting account {account_id} with reassignment to {target_account_id} "
        f"for user {user_id}"
    )
    
    # Call RPC function for atomic soft-delete with reassignment
    result = supabase_client.rpc(
        'delete_account_reassign',
        {
            'p_account_id': account_id,
            'p_user_id': user_id,
            'p_target_account_id': target_account_id
        }
    ).execute()
    
    if not result.data or not isinstance(result.data, list) or len(result.data) == 0:
        raise Exception("RPC delete_account_reassign failed: no data returned")
    
    rpc_result = cast(Dict[str, Any], result.data[0])
    transaction_count = int(rpc_result.get('transactions_reassigned', 0))
    account_soft_deleted = bool(rpc_result.get('account_soft_deleted', False))
    
    if not account_soft_deleted:
        raise Exception(f"Account {account_id} was not soft-deleted")
    
    logger.info(
        f"Account {account_id} soft-deleted via RPC after reassigning "
        f"{transaction_count} transactions"
    )
    
    return transaction_count


async def delete_account_with_transactions(
    supabase_client: Client,
    user_id: str,
    account_id: str
) -> tuple[int, int]:
    """
    Soft-delete account along with all its transactions.
    
    Uses RPC function `delete_account_cascade` for atomic operation.
    This implements DB delete rule Option 2 with soft-delete strategy:
    1. Soft-delete all recurring transaction templates
    2. Soft-delete all transactions for this account
    3. Soft-delete the account
    
    Args:
        supabase_client: Authenticated Supabase client
        user_id: The authenticated user's ID
        account_id: The account UUID to soft-delete
    
    Returns:
        Tuple of (recurring_templates_soft_deleted, transactions_soft_deleted)
    
    Raises:
        Exception: If RPC call fails
    
    Security:
        - RPC validates account belongs to user_id
        - All operations happen atomically in DB
        - All records are soft-deleted (deleted_at set), not physically removed
    """
    logger.info(
        f"Soft-deleting account {account_id} with all transactions for user {user_id}"
    )
    
    # Call RPC function for atomic soft-delete cascade
    result = supabase_client.rpc(
        'delete_account_cascade',
        {
            'p_account_id': account_id,
            'p_user_id': user_id
        }
    ).execute()
    
    if not result.data or not isinstance(result.data, list) or len(result.data) == 0:
        raise Exception("RPC delete_account_cascade failed: no data returned")
    
    rpc_result = cast(Dict[str, Any], result.data[0])
    recurring_count = int(rpc_result.get('recurring_templates_soft_deleted', 0))
    transaction_count = int(rpc_result.get('transactions_soft_deleted', 0))
    account_soft_deleted = bool(rpc_result.get('account_soft_deleted', False))
    
    if not account_soft_deleted:
        raise Exception(f"Account {account_id} was not soft-deleted")
    
    logger.info(
        f"Account {account_id} soft-deleted via RPC along with "
        f"{recurring_count} recurring templates and {transaction_count} transactions"
    )
    
    return (recurring_count, transaction_count)


async def recompute_account_balance(
    supabase_client: Client,
    user_id: str,
    account_id: str
) -> float:
    """
    Recompute account cached_balance from transaction history.
    
    This function calls the `recompute_account_balance` RPC which:
    1. Validates account belongs to user
    2. Sums all non-deleted transactions (income positive, outcome negative)
    3. Updates account.cached_balance
    4. Returns the new balance
    
    Call this after:
    - Creating transactions
    - Updating transactions (amount/account/flow_type changed)
    - Deleting transactions
    - Restoring soft-deleted transactions
    
    Args:
        supabase_client: Authenticated Supabase client
        user_id: The authenticated user's ID
        account_id: The account UUID to recompute
    
    Returns:
        The new computed balance
    
    Raises:
        Exception: If RPC call fails or account not found
    
    Security:
        - RPC validates account belongs to user_id
        - RLS is bypassed by SECURITY DEFINER but ownership is verified
    """
    logger.debug(f"Recomputing balance for account {account_id}, user {user_id}")
    
    try:
        result = supabase_client.rpc(
            'recompute_account_balance',
            {
                'p_account_id': account_id,
                'p_user_id': user_id
            }
        ).execute()
        
        if result.data is None:
            raise Exception("RPC recompute_account_balance returned None")
        
        # RPC returns a single numeric value
        # Cast to appropriate type - it could be int or float
        balance_value = result.data
        if isinstance(balance_value, (int, float)):
            new_balance = float(balance_value)
        elif isinstance(balance_value, str):
            new_balance = float(balance_value)
        else:
            raise Exception(f"Unexpected balance type: {type(balance_value)}")
        
        logger.info(f"Account {account_id} balance recomputed: {new_balance}")
        
        return new_balance
        
    except Exception as e:
        logger.error(f"Failed to recompute balance for account {account_id}: {e}")
        raise


# --- Favorite Account Management ---

async def set_favorite_account(
    supabase_client: Client,
    user_id: str,
    account_id: str
) -> Dict[str, Any]:
    """
    Set an account as the user's favorite.
    
    Uses RPC to safely toggle favorite status, ensuring only one account
    per user can be marked as favorite at a time.
    
    Args:
        supabase_client: Authenticated Supabase client
        user_id: The authenticated user's ID
        account_id: The account UUID to set as favorite
    
    Returns:
        Dict with previous_favorite_id, new_favorite_id, and success
    
    Raises:
        Exception: If RPC call fails or account doesn't exist/belong to user
    
    Security:
        - RPC validates account belongs to user_id
        - Atomic operation prevents race conditions
    """
    logger.info(f"Setting account {account_id} as favorite for user {user_id}")
    
    result = supabase_client.rpc(
        'set_favorite_account',
        {
            'p_account_id': account_id,
            'p_user_id': user_id
        }
    ).execute()
    
    if not result.data or not isinstance(result.data, list) or len(result.data) == 0:
        raise Exception("RPC set_favorite_account failed: no data returned")
    
    rpc_result = cast(Dict[str, Any], result.data[0])
    
    previous_id = rpc_result.get('previous_favorite_id')
    if previous_id:
        logger.info(f"Cleared previous favorite account {previous_id}")
    
    logger.info(f"Account {account_id} is now favorite for user {user_id}")
    
    return rpc_result


async def clear_favorite_account(
    supabase_client: Client,
    user_id: str,
    account_id: str
) -> bool:
    """
    Clear the favorite status from an account.
    
    Args:
        supabase_client: Authenticated Supabase client
        user_id: The authenticated user's ID
        account_id: The account UUID to clear favorite status from
    
    Returns:
        True if the account was favorite and is now cleared, False if it wasn't favorite
    
    Raises:
        Exception: If RPC call fails or account doesn't exist/belong to user
    """
    logger.info(f"Clearing favorite status from account {account_id} for user {user_id}")
    
    result = supabase_client.rpc(
        'clear_favorite_account',
        {
            'p_account_id': account_id,
            'p_user_id': user_id
        }
    ).execute()
    
    if not result.data or not isinstance(result.data, list) or len(result.data) == 0:
        raise Exception("RPC clear_favorite_account failed: no data returned")
    
    rpc_result = cast(Dict[str, Any], result.data[0])
    was_cleared = bool(rpc_result.get('cleared', False))
    
    if was_cleared:
        logger.info(f"Favorite status cleared from account {account_id}")
    else:
        logger.info(f"Account {account_id} was not favorite, no change needed")
    
    return was_cleared


async def get_favorite_account(
    supabase_client: Client,
    user_id: str
) -> Optional[str]:
    """
    Get the UUID of the user's favorite account.
    
    Args:
        supabase_client: Authenticated Supabase client
        user_id: The authenticated user's ID
    
    Returns:
        UUID of the favorite account, or None if no favorite is set
    """
    logger.debug(f"Getting favorite account for user {user_id}")
    
    result = supabase_client.rpc(
        'get_favorite_account',
        {'p_user_id': user_id}
    ).execute()
    
    # RPC returns UUID as string or None
    favorite_id: Optional[str] = None
    if result.data and isinstance(result.data, str):
        favorite_id = result.data
    
    if favorite_id:
        logger.debug(f"User {user_id} has favorite account {favorite_id}")
    else:
        logger.debug(f"User {user_id} has no favorite account set")
    
    return favorite_id
