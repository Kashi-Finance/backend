"""
Service layer for transfer operations (normal and recurring).

Handles business logic for creating paired transactions (transfers) and
paired recurring_transaction rules (recurring transfers).
"""

import logging
from typing import Any, Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)


# --- Normal Transfer Service Functions ---

async def create_transfer(
    supabase_client: Any,
    user_id: str,
    from_account_id: str,
    to_account_id: str,
    amount: float,
    date: str,
    description: Optional[str] = None
) -> Tuple[Dict[str, Any], Dict[str, Any]]:
    """
    Create a one-time internal transfer between two accounts.

    Uses RPC function `create_transfer` for atomic paired transaction creation.
    The RPC automatically assigns the correct 'transfer' category based on flow_type:
    - Outgoing transaction (outcome): Uses 'transfer' + 'outcome' category
    - Incoming transaction (income): Uses 'transfer' + 'income' category

    Args:
        supabase_client: Authenticated Supabase client
        user_id: User UUID from auth token
        from_account_id: Source account UUID
        to_account_id: Destination account UUID
        amount: Amount to transfer (must be > 0)
        date: Transfer date (ISO-8601 format)
        description: Optional description for both transactions

    Returns:
        Tuple of (outgoing_transaction, incoming_transaction) dicts

    Raises:
        ValueError: If accounts don't belong to user or validation fails
        Exception: If RPC call fails

    Security:
        - RPC validates both accounts belong to user_id
        - All operations happen atomically in DB
        - Categories are flow-aware: same key='transfer', different flow_type
    """
    logger.info(
        f"Creating transfer for user {user_id}: "
        f"{amount} from {from_account_id} to {to_account_id}"
    )

    # Call RPC function for atomic transfer creation
    # RPC handles category selection internally (flow-aware)
    result = supabase_client.rpc(
        'create_transfer',
        {
            'p_user_id': user_id,
            'p_from_account_id': from_account_id,
            'p_to_account_id': to_account_id,
            'p_amount': amount,
            'p_date': date,
            'p_description': description
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

    # Recompute balances for both accounts after transfer
    try:
        from backend.services.account_service import recompute_account_balance
        await recompute_account_balance(supabase_client, user_id, from_account_id)
        await recompute_account_balance(supabase_client, user_id, to_account_id)
        logger.debug("Account balances recomputed for both accounts after transfer creation")
    except Exception as e:
        logger.warning(f"Failed to recompute account balances after transfer creation: {e}")
        # Don't fail the transfer creation, just log the warning

    return (outgoing_transaction, incoming_transaction)


async def update_transfer(
    supabase_client: Any,
    user_id: str,
    transaction_id: str,
    amount: Optional[float] = None,
    date: Optional[str] = None,
    description: Optional[str] = None
) -> Tuple[Dict[str, Any], Dict[str, Any]]:
    """
    Update a transfer by updating both paired transactions atomically.

    Uses RPC function `update_transfer` for atomic update.

    Args:
        supabase_client: Authenticated Supabase client
        user_id: User UUID from auth token
        transaction_id: UUID of either transaction in the pair
        amount: New amount (optional, must be > 0 if provided)
        date: New date in ISO-8601 format (optional)
        description: New description (optional)

    Returns:
        Tuple of (updated_transaction, updated_paired_transaction) dicts

    Raises:
        ValueError: If transaction not found, not a transfer, or validation fails
        Exception: If RPC call fails

    Security:
        - RPC validates ownership and atomicity
        - Only amount, date, and description can be updated
        - Both transactions receive identical updates

    Notes:
        - category_id, flow_type, paired_transaction_id, and account_id are immutable
        - If any field is not provided (None), it remains unchanged
    """
    logger.info(f"Updating transfer for user {user_id}: transaction {transaction_id}")

    # Validate amount if provided
    if amount is not None and amount <= 0:
        raise ValueError("Amount must be greater than 0")

    # Call RPC function for atomic transfer update
    result = supabase_client.rpc(
        'update_transfer',
        {
            'p_transaction_id': transaction_id,
            'p_user_id': user_id,
            'p_amount': amount,
            'p_date': date,
            'p_description': description
        }
    ).execute()

    if not result.data or len(result.data) == 0:
        raise Exception("RPC update_transfer failed: no data returned")

    rpc_result = result.data[0]
    updated_id = rpc_result['updated_transaction_id']
    paired_id = rpc_result['updated_paired_transaction_id']

    # Fetch both updated transactions for return value
    updated_result = (
        supabase_client.table("transaction")
        .select("*")
        .eq("id", updated_id)
        .execute()
    )

    paired_result = (
        supabase_client.table("transaction")
        .select("*")
        .eq("id", paired_id)
        .execute()
    )

    if not updated_result.data or not paired_result.data:
        raise Exception("Failed to fetch updated transactions")

    updated_transaction = updated_result.data[0]
    paired_transaction = paired_result.data[0]

    logger.info(
        f"Transfer updated via RPC: {updated_id} <-> {paired_id}"
    )

    # Recompute balances for both accounts after transfer update
    try:
        from backend.services.account_service import recompute_account_balance
        from_account = updated_transaction.get("account_id")
        to_account = paired_transaction.get("account_id")

        if from_account:
            await recompute_account_balance(supabase_client, user_id, from_account)
        if to_account:
            await recompute_account_balance(supabase_client, user_id, to_account)

        logger.debug("Account balances recomputed for both accounts after transfer update")
    except Exception as e:
        logger.warning(f"Failed to recompute account balances after transfer update: {e}")
        # Don't fail the transfer update, just log the warning

    return (updated_transaction, paired_transaction)


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

    # Fetch the transaction and its pair BEFORE deletion to get account IDs
    transaction_result = (
        supabase_client.table("transaction")
        .select("account_id, paired_transaction_id")
        .eq("id", transaction_id)
        .execute()
    )

    if not transaction_result.data or len(transaction_result.data) == 0:
        raise ValueError(f"Transaction {transaction_id} not found")

    transaction = transaction_result.data[0]
    account_1 = transaction.get("account_id")
    paired_id_for_lookup = transaction.get("paired_transaction_id")

    account_2 = None
    if paired_id_for_lookup:
        paired_result = (
            supabase_client.table("transaction")
            .select("account_id")
            .eq("id", paired_id_for_lookup)
            .execute()
        )
        if paired_result.data and len(paired_result.data) > 0:
            account_2 = paired_result.data[0].get("account_id")

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

    # Recompute balances for both accounts after transfer deletion
    try:
        from backend.services.account_service import recompute_account_balance
        if account_1:
            await recompute_account_balance(supabase_client, user_id, account_1)
        if account_2:
            await recompute_account_balance(supabase_client, user_id, account_2)
        logger.debug("Account balances recomputed for both accounts after transfer deletion")
    except Exception as e:
        logger.warning(f"Failed to recompute account balances after transfer deletion: {e}")
        # Don't fail the deletion, just log the warning

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
    is_active: bool = True
) -> Tuple[Dict[str, Any], Dict[str, Any]]:
    """
    Create a recurring internal transfer.

    Uses RPC function `create_recurring_transfer` for atomic paired rule creation.
    The RPC automatically assigns the correct 'transfer' category based on flow_type:
    - Outgoing rule (outcome): Uses 'transfer' + 'outcome' category
    - Incoming rule (income): Uses 'transfer' + 'income' category

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

    Returns:
        Tuple of (outgoing_rule, incoming_rule) dicts

    Raises:
        ValueError: If accounts don't belong to user or validation fails
        Exception: If RPC call fails

    Security:
        - RPC validates both accounts belong to user_id
        - All operations happen atomically in DB
        - Categories are flow-aware: same key='transfer', different flow_type
    """
    logger.info(
        f"Creating recurring transfer for user {user_id}: "
        f"{amount} from {from_account_id} to {to_account_id}, {frequency}"
    )

    # Call RPC function for atomic recurring transfer creation
    # RPC handles category selection internally (flow-aware)
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
            'p_is_active': is_active
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
