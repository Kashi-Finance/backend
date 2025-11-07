"""
Service layer for transfer operations (normal and recurring).

Handles business logic for creating paired transactions (transfers) and
paired recurring_transaction rules (recurring transfers).
"""

import logging
from typing import Dict, Any, Optional, List, Tuple

logger = logging.getLogger(__name__)


# --- Normal Transfer Service Functions ---

async def create_transfer(
    supabase_client: Any,
    user_id: str,
    from_account_id: str,
    to_account_id: str,
    amount: float,
    date: str,
    description: Optional[str] = None,
    transfer_category_id: Optional[str] = None
) -> Tuple[Dict[str, Any], Dict[str, Any]]:
    """
    Create a one-time internal transfer between two accounts.
    
    Uses RPC function `create_transfer` for atomic paired transaction creation.
    
    Args:
        supabase_client: Authenticated Supabase client
        user_id: User UUID from auth token
        from_account_id: Source account UUID
        to_account_id: Destination account UUID
        amount: Amount to transfer (must be > 0)
        date: Transfer date (ISO-8601 format)
        description: Optional description for both transactions
        transfer_category_id: UUID of 'transfer' system category (fetched if not provided)
        
    Returns:
        Tuple of (outgoing_transaction, incoming_transaction) dicts
        
    Raises:
        ValueError: If accounts don't belong to user or validation fails
        Exception: If RPC call fails
        
    Security:
        - RPC validates both accounts belong to user_id
        - All operations happen atomically in DB
    """
    logger.info(
        f"Creating transfer for user {user_id}: "
        f"{amount} from {from_account_id} to {to_account_id}"
    )
    
    # Fetch 'transfer' system category if not provided
    if transfer_category_id is None:
        category_result = (
            supabase_client.table("category")
            .select("id")
            .eq("key", "transfer")
            .execute()
        )
        
        if not category_result.data or len(category_result.data) == 0:
            raise ValueError("System category 'transfer' not found")
        
        transfer_category_id = category_result.data[0]["id"]
    
    # Call RPC function for atomic transfer creation
    result = supabase_client.rpc(
        'create_transfer',
        {
            'p_user_id': user_id,
            'p_from_account_id': from_account_id,
            'p_to_account_id': to_account_id,
            'p_amount': amount,
            'p_date': date,
            'p_description': description,
            'p_transfer_category_id': transfer_category_id
        }
    ).execute()
    
    if not result.data or len(result.data) == 0:
        raise Exception("RPC create_transfer failed: no data returned")
    
    rpc_result = result.data[0]
    outgoing_id = rpc_result['outgoing_transaction_id']
    incoming_id = rpc_result['incoming_transaction_id']
    
    # Fetch both transactions for return value consistency
    outgoing_result = (
        supabase_client.table("transaction")
        .select("*")
        .eq("id", outgoing_id)
        .execute()
    )
    
    incoming_result = (
        supabase_client.table("transaction")
        .select("*")
        .eq("id", incoming_id)
        .execute()
    )
    
    if not outgoing_result.data or not incoming_result.data:
        raise Exception("Failed to fetch created transactions")
    
    outgoing_transaction = outgoing_result.data[0]
    incoming_transaction = incoming_result.data[0]
    
    logger.info(
        f"Transfer created via RPC: {outgoing_id} (out) <-> {incoming_id} (in)"
    )
    
    return (outgoing_transaction, incoming_transaction)


async def delete_transfer(
    supabase_client: Any,
    user_id: str,
    transaction_id: str
) -> Tuple[str, str]:
    """
    Delete a transfer by deleting both paired transactions.
    
    Uses RPC function `delete_transfer` for atomic deletion.
    
    Args:
        supabase_client: Authenticated Supabase client
        user_id: User UUID from auth token
        transaction_id: UUID of either transaction in the pair
        
    Returns:
        Tuple of (deleted_transaction_id, paired_transaction_id)
        
    Raises:
        ValueError: If transaction not found or not a transfer
        Exception: If RPC call fails
        
    Security:
        RPC validates ownership and atomicity
    """
    logger.info(f"Deleting transfer for user {user_id}: transaction {transaction_id}")
    
    # Call RPC function for atomic transfer deletion
    result = supabase_client.rpc(
        'delete_transfer',
        {
            'p_transaction_id': transaction_id,
            'p_user_id': user_id
        }
    ).execute()
    
    if not result.data or len(result.data) == 0:
        raise Exception("RPC delete_transfer failed: no data returned")
    
    rpc_result = result.data[0]
    deleted_id = rpc_result['deleted_transaction_id']
    paired_id = rpc_result['paired_transaction_id']
    
    logger.info(f"Transfer deleted via RPC: {deleted_id} and {paired_id}")
    
    return (deleted_id, paired_id)


# --- Recurring Transfer Service Functions ---

async def create_recurring_transfer(
    supabase_client: Any,
    user_id: str,
    from_account_id: str,
    to_account_id: str,
    amount: float,
    description_outgoing: Optional[str],
    description_incoming: Optional[str],
    frequency: str,
    interval: int,
    start_date: str,
    by_weekday: Optional[List[str]] = None,
    by_monthday: Optional[List[int]] = None,
    end_date: Optional[str] = None,
    is_active: bool = True,
    transfer_category_id: Optional[str] = None
) -> Tuple[Dict[str, Any], Dict[str, Any]]:
    """
    Create a recurring internal transfer.
    
    Uses RPC function `create_recurring_transfer` for atomic paired rule creation.
    
    Args:
        supabase_client: Authenticated Supabase client
        user_id: User UUID from auth token
        from_account_id: Source account UUID
        to_account_id: Destination account UUID
        amount: Amount per occurrence
        description_outgoing: Description for outgoing side (optional)
        description_incoming: Description for incoming side (optional)
        frequency: 'daily', 'weekly', 'monthly', or 'yearly'
        interval: Repeat every N units
        start_date: Start date (YYYY-MM-DD)
        by_weekday: Weekdays for weekly frequency (optional)
        by_monthday: Month days for monthly frequency (optional)
        end_date: End date or NULL (optional)
        is_active: Whether rules are active (default True)
        transfer_category_id: UUID of 'from_recurrent_transaction' system category
        
    Returns:
        Tuple of (outgoing_rule, incoming_rule) dicts
        
    Raises:
        ValueError: If accounts don't belong to user or validation fails
        Exception: If RPC call fails
        
    Security:
        - RPC validates both accounts belong to user_id
        - All operations happen atomically in DB
    """
    logger.info(
        f"Creating recurring transfer for user {user_id}: "
        f"{amount} from {from_account_id} to {to_account_id}, {frequency}"
    )
    
    # Fetch 'from_recurrent_transaction' system category
    if transfer_category_id is None:
        category_result = (
            supabase_client.table("category")
            .select("id")
            .eq("key", "from_recurrent_transaction")
            .execute()
        )
        
        if not category_result.data or len(category_result.data) == 0:
            raise ValueError("System category 'from_recurrent_transaction' not found")
        
        transfer_category_id = category_result.data[0]["id"]
    
    # Call RPC function for atomic recurring transfer creation
    result = supabase_client.rpc(
        'create_recurring_transfer',
        {
            'p_user_id': user_id,
            'p_from_account_id': from_account_id,
            'p_to_account_id': to_account_id,
            'p_amount': amount,
            'p_description_outgoing': description_outgoing,
            'p_description_incoming': description_incoming,
            'p_frequency': frequency,
            'p_interval': interval,
            'p_start_date': start_date,
            'p_by_weekday': by_weekday,
            'p_by_monthday': by_monthday,
            'p_end_date': end_date,
            'p_is_active': is_active,
            'p_transfer_category_id': transfer_category_id
        }
    ).execute()
    
    if not result.data or len(result.data) == 0:
        raise Exception("RPC create_recurring_transfer failed: no data returned")
    
    rpc_result = result.data[0]
    outgoing_id = rpc_result['outgoing_rule_id']
    incoming_id = rpc_result['incoming_rule_id']
    
    # Fetch both rules for return value consistency
    outgoing_result = (
        supabase_client.table("recurring_transaction")
        .select("*")
        .eq("id", outgoing_id)
        .execute()
    )
    
    incoming_result = (
        supabase_client.table("recurring_transaction")
        .select("*")
        .eq("id", incoming_id)
        .execute()
    )
    
    if not outgoing_result.data or not incoming_result.data:
        raise Exception("Failed to fetch created recurring rules")
    
    outgoing_rule = outgoing_result.data[0]
    incoming_rule = incoming_result.data[0]
    
    logger.info(
        f"Recurring transfer created via RPC: {outgoing_id} (out) <-> {incoming_id} (in)"
    )
    
    return (outgoing_rule, incoming_rule)


async def delete_recurring_transfer(
    supabase_client: Any,
    user_id: str,
    recurring_transaction_id: str
) -> Tuple[str, str]:
    """
    Delete a recurring transfer by deleting both paired rules.
    
    Args:
        supabase_client: Authenticated Supabase client
        user_id: User UUID from auth token
        recurring_transaction_id: UUID of either rule in the pair
        
    Returns:
        Tuple of (deleted_rule_id, paired_rule_id)
        
    Raises:
        ValueError: If rule not found or not a recurring transfer
        Exception: If deletion fails
        
    Security:
        RLS enforces user_id = auth.uid() on deletes
    """
    logger.info(
        f"Deleting recurring transfer for user {user_id}: "
        f"rule {recurring_transaction_id}"
    )
    
    # Fetch the rule
    rule_result = (
        supabase_client.table("recurring_transaction")
        .select("id, paired_recurring_transaction_id, user_id")
        .eq("id", recurring_transaction_id)
        .eq("user_id", user_id)
        .execute()
    )
    
    if not rule_result.data or len(rule_result.data) == 0:
        raise ValueError(
            f"Recurring transaction {recurring_transaction_id} not found or not accessible"
        )
    
    rule = rule_result.data[0]
    paired_id = rule.get("paired_recurring_transaction_id")
    
    if not paired_id:
        raise ValueError(
            f"Recurring transaction {recurring_transaction_id} is not part of a transfer"
        )
    
    # Delete both rules
    # The DB ON DELETE SET NULL will handle clearing the references
    delete_main = (
        supabase_client.table("recurring_transaction")
        .delete()
        .eq("id", recurring_transaction_id)
        .execute()
    )
    
    delete_paired = (
        supabase_client.table("recurring_transaction")
        .delete()
        .eq("id", paired_id)
        .execute()
    )
    
    logger.info(f"Recurring transfer deleted: {recurring_transaction_id} and {paired_id}")
    
    return (recurring_transaction_id, paired_id)
