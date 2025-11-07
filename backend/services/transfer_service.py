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
    
    Creates two paired transactions:
    1. Outcome transaction from source account
    2. Income transaction to destination account
    
    Both transactions are linked via paired_transaction_id and use the
    'transfer' system category.
    
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
        Exception: If transaction creation fails
        
    Security:
        - Validates both accounts belong to user_id
        - RLS enforces user_id = auth.uid() on inserts
    """
    logger.info(
        f"Creating transfer for user {user_id}: "
        f"{amount} from {from_account_id} to {to_account_id}"
    )
    
    # Validate both accounts belong to the user
    from_account_result = (
        supabase_client.table("account")
        .select("id")
        .eq("id", from_account_id)
        .eq("user_id", user_id)
        .execute()
    )
    
    if not from_account_result.data or len(from_account_result.data) == 0:
        raise ValueError(f"Source account {from_account_id} not found or not accessible")
    
    to_account_result = (
        supabase_client.table("account")
        .select("id")
        .eq("id", to_account_id)
        .eq("user_id", user_id)
        .execute()
    )
    
    if not to_account_result.data or len(to_account_result.data) == 0:
        raise ValueError(f"Destination account {to_account_id} not found or not accessible")
    
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

    
    # Step 1: Create outgoing transaction (outcome from source)
    outgoing_data = {
        "user_id": user_id,
        "account_id": from_account_id,
        "category_id": transfer_category_id,
        "flow_type": "outcome",
        "amount": amount,
        "date": date,
        "description": description
    }
    
    outgoing_result = (
        supabase_client.table("transaction")
        .insert(outgoing_data)
        .execute()
    )
    
    if not outgoing_result.data or len(outgoing_result.data) == 0:
        raise Exception("Failed to create outgoing transaction")
    
    outgoing_transaction = outgoing_result.data[0]
    outgoing_id = outgoing_transaction["id"]
    
    # Step 2: Create incoming transaction (income to destination)
    incoming_data = {
        "user_id": user_id,
        "account_id": to_account_id,
        "category_id": transfer_category_id,
        "flow_type": "income",
        "amount": amount,
        "date": date,
        "description": description,
        "paired_transaction_id": outgoing_id
    }
    
    incoming_result = (
        supabase_client.table("transaction")
        .insert(incoming_data)
        .execute()
    )
    
    if not incoming_result.data or len(incoming_result.data) == 0:
        # Rollback: delete outgoing transaction
        (
            supabase_client.table("transaction")
            .delete()
            .eq("id", outgoing_id)
            .execute()
        )
        raise Exception("Failed to create incoming transaction")
    
    incoming_transaction = incoming_result.data[0]
    incoming_id = incoming_transaction["id"]
    
    # Step 3: Update outgoing transaction to link back to incoming
    update_result = (
        supabase_client.table("transaction")
        .update({"paired_transaction_id": incoming_id})
        .eq("id", outgoing_id)
        .execute()
    )
    
    if not update_result.data or len(update_result.data) == 0:
        # Rollback: delete both transactions
        (
            supabase_client.table("transaction")
            .delete()
            .eq("id", outgoing_id)
            .execute()
        )
        (
            supabase_client.table("transaction")
            .delete()
            .eq("id", incoming_id)
            .execute()
        )
        raise Exception("Failed to link paired transactions")
    
    outgoing_transaction = update_result.data[0]
    
    logger.info(
        f"Transfer created: {outgoing_id} (out) <-> {incoming_id} (in)"
    )
    
    return (outgoing_transaction, incoming_transaction)


async def delete_transfer(
    supabase_client: Any,
    user_id: str,
    transaction_id: str
) -> Tuple[str, str]:
    """
    Delete a transfer by deleting both paired transactions.
    
    Args:
        supabase_client: Authenticated Supabase client
        user_id: User UUID from auth token
        transaction_id: UUID of either transaction in the pair
        
    Returns:
        Tuple of (deleted_transaction_id, paired_transaction_id)
        
    Raises:
        ValueError: If transaction not found or not a transfer
        Exception: If deletion fails
        
    Security:
        RLS enforces user_id = auth.uid() on deletes
    """
    logger.info(f"Deleting transfer for user {user_id}: transaction {transaction_id}")
    
    # Fetch the transaction
    transaction_result = (
        supabase_client.table("transaction")
        .select("id, paired_transaction_id, user_id")
        .eq("id", transaction_id)
        .eq("user_id", user_id)
        .execute()
    )
    
    if not transaction_result.data or len(transaction_result.data) == 0:
        raise ValueError(f"Transaction {transaction_id} not found or not accessible")
    
    transaction = transaction_result.data[0]
    paired_id = transaction.get("paired_transaction_id")
    
    if not paired_id:
        raise ValueError(f"Transaction {transaction_id} is not part of a transfer")
    
    # Delete both transactions
    # The DB ON DELETE SET NULL will handle clearing the references
    delete_main = (
        supabase_client.table("transaction")
        .delete()
        .eq("id", transaction_id)
        .execute()
    )
    
    delete_paired = (
        supabase_client.table("transaction")
        .delete()
        .eq("id", paired_id)
        .execute()
    )
    
    logger.info(f"Transfer deleted: {transaction_id} and {paired_id}")
    
    return (transaction_id, paired_id)


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
    
    Creates two paired recurring_transaction rules:
    1. Outcome template for source account
    2. Income template for destination account
    
    Both rules are linked via paired_recurring_transaction_id.
    
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
        transfer_category_id: UUID of 'transfer' system category
        
    Returns:
        Tuple of (outgoing_rule, incoming_rule) dicts
        
    Raises:
        ValueError: If accounts don't belong to user or validation fails
        Exception: If rule creation fails
        
    Security:
        - Validates both accounts belong to user_id
        - RLS enforces user_id = auth.uid() on inserts
    """
    logger.info(
        f"Creating recurring transfer for user {user_id}: "
        f"{amount} from {from_account_id} to {to_account_id}, {frequency}"
    )
    
    # Validate both accounts belong to the user
    from_account_result = (
        supabase_client.table("account")
        .select("id")
        .eq("id", from_account_id)
        .eq("user_id", user_id)
        .execute()
    )
    
    if not from_account_result.data or len(from_account_result.data) == 0:
        raise ValueError(f"Source account {from_account_id} not found or not accessible")
    
    to_account_result = (
        supabase_client.table("account")
        .select("id")
        .eq("id", to_account_id)
        .eq("user_id", user_id)
        .execute()
    )
    
    if not to_account_result.data or len(to_account_result.data) == 0:
        raise ValueError(f"Destination account {to_account_id} not found or not accessible")
    
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
    
    # Step 1: Create outgoing recurring rule
    outgoing_data = {
        "user_id": user_id,
        "account_id": from_account_id,
        "category_id": transfer_category_id,
        "flow_type": "outcome",
        "amount": amount,
        "description": description_outgoing,
        "frequency": frequency,
        "interval": interval,
        "start_date": start_date,
        "next_run_date": start_date,
        "is_active": is_active
    }
    
    if by_weekday is not None:
        outgoing_data["by_weekday"] = by_weekday
    if by_monthday is not None:
        outgoing_data["by_monthday"] = by_monthday
    if end_date is not None:
        outgoing_data["end_date"] = end_date
    
    outgoing_result = (
        supabase_client.table("recurring_transaction")
        .insert(outgoing_data)
        .execute()
    )
    
    if not outgoing_result.data or len(outgoing_result.data) == 0:
        raise Exception("Failed to create outgoing recurring rule")
    
    outgoing_rule = outgoing_result.data[0]
    outgoing_id = outgoing_rule["id"]
    
    # Step 2: Create incoming recurring rule
    incoming_data = {
        "user_id": user_id,
        "account_id": to_account_id,
        "category_id": transfer_category_id,
        "flow_type": "income",
        "amount": amount,
        "description": description_incoming,
        "frequency": frequency,
        "interval": interval,
        "start_date": start_date,
        "next_run_date": start_date,
        "is_active": is_active,
        "paired_recurring_transaction_id": outgoing_id
    }
    
    if by_weekday is not None:
        incoming_data["by_weekday"] = by_weekday
    if by_monthday is not None:
        incoming_data["by_monthday"] = by_monthday
    if end_date is not None:
        incoming_data["end_date"] = end_date
    
    incoming_result = (
        supabase_client.table("recurring_transaction")
        .insert(incoming_data)
        .execute()
    )
    
    if not incoming_result.data or len(incoming_result.data) == 0:
        # Rollback: delete outgoing rule
        (
            supabase_client.table("recurring_transaction")
            .delete()
            .eq("id", outgoing_id)
            .execute()
        )
        raise Exception("Failed to create incoming recurring rule")
    
    incoming_rule = incoming_result.data[0]
    incoming_id = incoming_rule["id"]
    
    # Step 3: Update outgoing rule to link back to incoming
    update_result = (
        supabase_client.table("recurring_transaction")
        .update({"paired_recurring_transaction_id": incoming_id})
        .eq("id", outgoing_id)
        .execute()
    )
    
    if not update_result.data or len(update_result.data) == 0:
        # Rollback: delete both rules
        (
            supabase_client.table("recurring_transaction")
            .delete()
            .eq("id", outgoing_id)
            .execute()
        )
        (
            supabase_client.table("recurring_transaction")
            .delete()
            .eq("id", incoming_id)
            .execute()
        )
        raise Exception("Failed to link paired recurring rules")
    
    outgoing_rule = update_result.data[0]
    
    logger.info(
        f"Recurring transfer created: {outgoing_id} (out) <-> {incoming_id} (in)"
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
