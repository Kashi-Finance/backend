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
    user_id: str
) -> List[Dict[str, Any]]:
    """
    Fetch all accounts belonging to the user.
    
    Args:
        supabase_client: Authenticated Supabase client
        user_id: The authenticated user's ID
    
    Returns:
        List of account dicts
    
    Security:
        - RLS enforces user_id = auth.uid()
        - User can only access their own accounts
    """
    logger.debug(f"Fetching accounts for user {user_id}")
    
    result = (
        supabase_client.table("account")
        .select("*")
        .eq("user_id", user_id)
        .order("created_at", desc=True)
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
        ValueError: If target account doesn't exist or doesn't belong to user
        Exception: If reassignment or deletion fails
    
    Security:
        - RLS enforces user_id = auth.uid()
        - Validates target account belongs to same user
    """
    logger.info(
        f"Deleting account {account_id} with reassignment to {target_account_id} "
        f"for user {user_id}"
    )
    
    # Verify target account exists and belongs to user
    target_account = await get_account_by_id(supabase_client, user_id, target_account_id)
    if not target_account:
        raise ValueError(
            f"Target account {target_account_id} not found or doesn't belong to user"
        )
    
    # Get count of transactions to reassign
    count_result = (
        supabase_client.table("transaction")
        .select("id", count=cast(Any, "exact"))
        .eq("account_id", account_id)
        .eq("user_id", user_id)
        .execute()
    )

    transaction_count = getattr(count_result, "count", 0) or 0
    logger.info(f"Found {transaction_count} transactions to reassign")
    
    # Reassign all transactions
    if transaction_count > 0:
        reassign_result = (
            supabase_client.table("transaction")
            .update({"account_id": target_account_id})
            .eq("account_id", account_id)
            .eq("user_id", user_id)
            .execute()
        )
        
        if not reassign_result.data:
            raise Exception("Failed to reassign transactions")
        
        logger.info(f"Reassigned {transaction_count} transactions")
    
    # Delete the account
    delete_result = (
        supabase_client.table("account")
        .delete()
        .eq("id", account_id)
        .eq("user_id", user_id)
        .execute()
    )
    
    if not delete_result.data or len(delete_result.data) == 0:
        raise Exception("Failed to delete account")
    
    logger.info(f"Account {account_id} deleted successfully after reassigning {transaction_count} transactions")
    
    return transaction_count


async def delete_account_with_transactions(
    supabase_client: Client,
    user_id: str,
    account_id: str
) -> int:
    """
    Delete account by deleting all related transactions.
    
    This implements DB delete rule Option 2:
    1. Delete all transactions for this account
    2. Handle paired transfers (clear paired_transaction_id)
    3. Delete the account
    
    Note: Invoice cleanup is deferred - invoices linked only to deleted
    transactions may become orphaned and should be handled separately.
    
    Args:
        supabase_client: Authenticated Supabase client
        user_id: The authenticated user's ID
        account_id: The account UUID to delete
    
    Returns:
        Number of transactions deleted
    
    Raises:
        Exception: If transaction deletion or account deletion fails
    
    Security:
        - RLS enforces user_id = auth.uid()
        - Only deletes user's own transactions and account
    """
    logger.info(
        f"Deleting account {account_id} with all transactions for user {user_id}"
    )
    
    # Get all transactions for this account
    transactions_result = (
        supabase_client.table("transaction")
        .select("id, paired_transaction_id")
        .eq("account_id", account_id)
        .eq("user_id", user_id)
        .execute()
    )
    
    transactions = cast(List[Dict[str, Any]], transactions_result.data) if transactions_result.data else []
    transaction_count = len(transactions)
    logger.info(f"Found {transaction_count} transactions to delete")
    
    # Handle paired transfers - clear references
    paired_ids = [
        t.get("paired_transaction_id")
        for t in transactions
        if t.get("paired_transaction_id")
    ]
    
    if paired_ids:
        logger.info(f"Clearing {len(paired_ids)} paired transaction references")
        # Clear paired_transaction_id for transactions that reference our transactions
        supabase_client.table("transaction").update(
            {"paired_transaction_id": None}
        ).in_("paired_transaction_id", [t.get("id") for t in transactions]).execute()
    
    # Delete all transactions
    if transaction_count > 0:
        delete_txn_result = (
            supabase_client.table("transaction")
            .delete()
            .eq("account_id", account_id)
            .eq("user_id", user_id)
            .execute()
        )
        
        if not delete_txn_result.data:
            raise Exception("Failed to delete transactions")
        
        logger.info(f"Deleted {transaction_count} transactions")
    
    # Delete the account
    delete_result = (
        supabase_client.table("account")
        .delete()
        .eq("id", account_id)
        .eq("user_id", user_id)
        .execute()
    )
    
    if not delete_result.data or len(delete_result.data) == 0:
        raise Exception("Failed to delete account")
    
    logger.info(f"Account {account_id} deleted successfully after removing {transaction_count} transactions")
    
    return transaction_count
