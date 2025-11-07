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
    currency: str
) -> Dict[str, Any]:
    """
    Create a new account.
    
    Args:
        supabase_client: Authenticated Supabase client
        user_id: The authenticated user's ID
        name: Human-readable account name
        account_type: Account type (cash, bank, credit_card, etc.)
        currency: ISO currency code
    
    Returns:
        The created account dict
    
    Security:
        - RLS enforces user_id = auth.uid()
        - User can only create accounts for themselves
    """
    account_data = {
        "user_id": user_id,
        "name": name,
        "type": account_type,
        "currency": currency
    }
    
    logger.info(
        f"Creating account for user {user_id}: "
        f"name='{name}', type={account_type}, currency={currency}"
    )
    
    result = supabase_client.table("account").insert(account_data).execute()
    
    if not result.data or len(result.data) == 0:
        raise Exception("Failed to create account: no data returned")
    
    created_account: Dict[str, Any] = cast(Dict[str, Any], result.data[0])
    logger.info(f"Account created successfully: {created_account['id']}")
    
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
        **updates: Fields to update (name, type, currency)
    
    Returns:
        The updated account dict, or None if not found
    
    Security:
        - RLS enforces user_id = auth.uid()
        - User can only update their own accounts
    """
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
    Delete account by reassigning all transactions to another account.
    
    Uses RPC function `delete_account_reassign` for atomic operation.
    This implements DB delete rule Option 1:
    1. Reassign all transactions to target_account_id
    2. Delete the account
    
    Args:
        supabase_client: Authenticated Supabase client
        user_id: The authenticated user's ID
        account_id: The account UUID to delete
        target_account_id: The account UUID to receive transactions
    
    Returns:
        Number of transactions reassigned
    
    Raises:
        ValueError: If accounts are invalid or validation fails
        Exception: If RPC call fails
    
    Security:
        - RPC validates both accounts belong to user_id
        - All operations happen atomically in DB
    """
    logger.info(
        f"Deleting account {account_id} with reassignment to {target_account_id} "
        f"for user {user_id}"
    )
    
    # Call RPC function for atomic delete with reassignment
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
    account_deleted = bool(rpc_result.get('account_deleted', False))
    
    if not account_deleted:
        raise Exception(f"Account {account_id} was not deleted")
    
    logger.info(
        f"Account {account_id} deleted via RPC after reassigning "
        f"{transaction_count} transactions"
    )
    
    return transaction_count


async def delete_account_with_transactions(
    supabase_client: Client,
    user_id: str,
    account_id: str
) -> int:
    """
    Delete account by deleting all related transactions.
    
    Uses RPC function `delete_account_cascade` for atomic operation.
    This implements DB delete rule Option 2:
    1. Delete all transactions for this account
    2. Handle paired transfers (clear paired_transaction_id)
    3. Delete the account
    
    Args:
        supabase_client: Authenticated Supabase client
        user_id: The authenticated user's ID
        account_id: The account UUID to delete
    
    Returns:
        Number of transactions deleted
    
    Raises:
        Exception: If RPC call fails
    
    Security:
        - RPC validates account belongs to user_id
        - All operations happen atomically in DB
    """
    logger.info(
        f"Deleting account {account_id} with all transactions for user {user_id}"
    )
    
    # Call RPC function for atomic delete with cascade
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
    transaction_count = int(rpc_result.get('transactions_deleted', 0))
    paired_refs_cleared = int(rpc_result.get('paired_references_cleared', 0))
    account_deleted = bool(rpc_result.get('account_deleted', False))
    
    if not account_deleted:
        raise Exception(f"Account {account_id} was not deleted")
    
    logger.info(
        f"Account {account_id} deleted via RPC after removing {transaction_count} "
        f"transactions (cleared {paired_refs_cleared} paired references)"
    )
    
    return transaction_count
