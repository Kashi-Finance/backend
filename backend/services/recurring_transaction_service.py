"""
Service layer for recurring_transaction CRUD and sync operations.

Handles business logic for managing recurring transaction rules and
synchronizing them to generate actual transactions.
"""

import logging
from datetime import date
from typing import Any, Dict, List, Optional, Tuple, cast

logger = logging.getLogger(__name__)


async def get_all_recurring_transactions(
    supabase_client: Any,
    user_id: str,
    limit: int = 50,
    offset: int = 0
) -> List[Dict[str, Any]]:
    """
    Retrieve all recurring transaction rules for a user.

    Args:
        supabase_client: Authenticated Supabase client
        user_id: User UUID from auth token
        limit: Maximum number of rules to return (default 50)
        offset: Number of rules to skip for pagination (default 0)

    Returns:
        List of recurring transaction dicts (ordered by created_at desc)

    Security:
        RLS enforces user_id = auth.uid() automatically
    """
    logger.info(f"Fetching recurring transactions for user {user_id} (limit={limit}, offset={offset})")

    result = supabase_client.table("recurring_transaction") \
        .select("*") \
        .eq("user_id", user_id) \
        .order("created_at", desc=True) \
        .range(offset, offset + limit - 1) \
        .execute()

    return result.data if result.data else []


async def get_recurring_transaction_by_id(
    supabase_client: Any,
    user_id: str,
    recurring_transaction_id: str
) -> Optional[Dict[str, Any]]:
    """
    Retrieve a single recurring transaction rule by ID.

    Args:
        supabase_client: Authenticated Supabase client
        user_id: User UUID from auth token
        recurring_transaction_id: Recurring transaction UUID

    Returns:
        Recurring transaction dict or None if not found

    Security:
        RLS enforces user_id = auth.uid() automatically
    """
    logger.info(f"Fetching recurring transaction {recurring_transaction_id} for user {user_id}")

    result = supabase_client.table("recurring_transaction") \
        .select("*") \
        .eq("id", recurring_transaction_id) \
        .eq("user_id", user_id) \
        .execute()

    if result.data and len(result.data) > 0:
        data: dict[str, Any] = result.data[0]
        return data

    return None


async def create_recurring_transaction(
    supabase_client: Any,
    user_id: str,
    account_id: str,
    category_id: str,
    flow_type: str,
    amount: float,
    description: str,
    frequency: str,
    interval: int,
    start_date: str,
    paired_recurring_transaction_id: Optional[str] = None,
    by_weekday: Optional[List[str]] = None,
    by_monthday: Optional[List[int]] = None,
    end_date: Optional[str] = None,
    is_active: bool = True
) -> Dict[str, Any]:
    """
    Create a new recurring transaction rule.

    Args:
        supabase_client: Authenticated Supabase client
        user_id: User UUID from auth token
        account_id: Account UUID
        category_id: Category UUID
        flow_type: 'income' or 'outcome'
        amount: Amount per occurrence (must be > 0)
        description: Transaction description
        frequency: 'daily', 'weekly', 'monthly', or 'yearly'
        interval: How often it repeats (must be >= 1)
        start_date: Start date (YYYY-MM-DD)
        paired_recurring_transaction_id: Optional paired rule UUID for transfers
        by_weekday: Optional list of weekday names for weekly frequency
        by_monthday: Optional list of day numbers for monthly frequency
        end_date: Optional end date (YYYY-MM-DD)
        is_active: Whether rule is active (default True)

    Returns:
        Created recurring transaction dict

    Raises:
        Exception if creation fails or validation errors occur

    Security:
        RLS enforces user_id = auth.uid() on insert
    """
    logger.info(f"Creating recurring transaction for user {user_id}: {description}")

    # Build insert payload
    insert_data = {
        "user_id": user_id,
        "account_id": account_id,
        "category_id": category_id,
        "flow_type": flow_type,
        "amount": amount,
        "description": description,
        "frequency": frequency,
        "interval": interval,
        "start_date": start_date,
        "next_run_date": start_date,  # Initially set to start_date
        "is_active": is_active
    }

    # Add optional fields
    if paired_recurring_transaction_id is not None:
        insert_data["paired_recurring_transaction_id"] = paired_recurring_transaction_id

    if by_weekday is not None:
        insert_data["by_weekday"] = by_weekday

    if by_monthday is not None:
        insert_data["by_monthday"] = by_monthday

    if end_date is not None:
        insert_data["end_date"] = end_date

    # Insert into database
    result = supabase_client.table("recurring_transaction") \
        .insert(insert_data) \
        .execute()

    if not result.data or len(result.data) == 0:
        raise Exception("Failed to create recurring transaction")

    created: dict[str, Any] = result.data[0]
    logger.info(f"Recurring transaction created: {created.get('id')}")
    return created


async def update_recurring_transaction(
    supabase_client: Any,
    user_id: str,
    recurring_transaction_id: str,
    apply_retroactive_change: bool = False,
    **updates
) -> Tuple[Optional[Dict[str, Any]], int]:
    """
    Update a recurring transaction rule.

    Special handling:
    - If start_date changes and apply_retroactive_change=True, deletes past
      generated transactions
    - If is_active changes from False → True, recalculates next_run_date
      to next future occurrence (does not backfill missed occurrences)

    Args:
        supabase_client: Authenticated Supabase client
        user_id: User UUID from auth token
        recurring_transaction_id: Recurring transaction UUID
        apply_retroactive_change: If True and start_date changed, delete past transactions
        **updates: Fields to update (only non-None values)

    Returns:
        Tuple of (updated recurring transaction dict, retroactive_deletes_count)

    Security:
        RLS enforces user_id = auth.uid() on update and delete
    """
    logger.info(f"Updating recurring transaction {recurring_transaction_id} for user {user_id}")

    retroactive_deletes = 0

    # Check if start_date is being changed
    if "start_date" in updates and apply_retroactive_change:
        # TODO(db-team): Implement retroactive deletion logic
        # This requires:
        # 1. Fetch old start_date
        # 2. Delete transactions WHERE recurring_transaction_id = this rule
        #    AND date BETWEEN old_start_date AND today
        # 3. Count deleted rows
        logger.warning(
            f"Retroactive change requested for recurring transaction {recurring_transaction_id}, "
            "but deletion logic not yet implemented (TODO)"
        )

    # Check if is_active is being changed from False → True
    if "is_active" in updates and updates["is_active"] is True:
        # TODO: Recalculate next_run_date to next future occurrence
        # For now, we'll let the update proceed with provided next_run_date or current value
        logger.info(
            f"Activating recurring transaction {recurring_transaction_id}. "
            "next_run_date should be recalculated to next future occurrence."
        )

    # Perform update
    result = supabase_client.table("recurring_transaction") \
        .update(updates) \
        .eq("id", recurring_transaction_id) \
        .eq("user_id", user_id) \
        .execute()

    if not result.data or len(result.data) == 0:
        return None, retroactive_deletes

    logger.info(f"Recurring transaction {recurring_transaction_id} updated successfully")
    return result.data[0], retroactive_deletes


async def delete_recurring_transaction(
    supabase_client: Any,
    user_id: str,
    recurring_transaction_id: str
) -> Tuple[bool, bool]:
    """
    Delete a recurring transaction rule following DB deletion rules.

    DB Rules:
    1. The record can be deleted safely without touching past generated transactions
    2. If it has a paired rule (paired_recurring_transaction_id), that reference
       must be deleted together
    3. Deleting the rule stops future auto-generation but preserves existing records

    Args:
        supabase_client: Authenticated Supabase client
        user_id: User UUID from auth token
        recurring_transaction_id: Recurring transaction UUID to delete

    Returns:
        Tuple of (success: bool, paired_rule_deleted: bool)

    Security:
        RLS enforces user_id = auth.uid() on delete
    """
    logger.info(f"Deleting recurring transaction {recurring_transaction_id} for user {user_id}")

    # Use DB RPC to atomically delete the rule and its paired rule (if owned by same user)
    try:
        rpc_res = supabase_client.rpc(
            "delete_recurring_and_pair",
            {
                "p_recurring_id": recurring_transaction_id,
                "p_user_id": user_id,
            },
        ).execute()

        data = getattr(rpc_res, "data", None)
        if not isinstance(data, list) or len(data) == 0:
            logger.warning(f"RPC delete_recurring_and_pair returned no rows for {recurring_transaction_id}")
            return False, False

        row = cast(Dict[str, Any], data[0])
        success = bool(row.get("success") or False)
        paired_deleted = bool(row.get("paired_deleted") or False)

        logger.info(
            f"Recurring transaction {recurring_transaction_id} deletion via RPC: success={success}, paired_deleted={paired_deleted}"
        )

        return success, paired_deleted
    except Exception as e:
        logger.error(f"Failed to delete recurring transaction via RPC for {recurring_transaction_id}: {e}", exc_info=True)
        raise


async def sync_recurring_transactions(
    supabase_client: Any,
    user_id: str,
    today: Optional[date] = None
) -> Tuple[int, int, int, int]:
    """
    Synchronize recurring transactions by calling the PostgreSQL function.

    This generates all pending transactions up to today by invoking the
    database function. The function handles:
    - Paired recurring transfers (linked via paired_transaction_id)
    - Account balance updates (batch, once per affected account)
    - Budget consumption updates (outcome transactions only, batch)

    Args:
        supabase_client: Authenticated Supabase client
        user_id: User UUID from auth token
        today: Target date (defaults to current date)

    Returns:
        Tuple of (transactions_generated, rules_processed, accounts_updated, budgets_updated)

    Raises:
        Exception if RPC call fails

    Security:
        Function uses SECURITY DEFINER but enforces user_id parameter
        RLS is applied within the function
    """
    if today is None:
        today = date.today()

    logger.info(f"Syncing recurring transactions for user {user_id} up to {today}")

    try:
        # Call PostgreSQL function via Supabase RPC
        result = supabase_client.rpc(
            'sync_recurring_transactions',
            {
                'p_user_id': user_id,
                'p_today': str(today)
            }
        ).execute()

        if not result.data or len(result.data) == 0:
            logger.warning("Sync function returned no data")
            return 0, 0, 0, 0

        # Extract results from function return
        sync_result = result.data[0]
        transactions_generated = sync_result.get('transactions_generated', 0)
        rules_processed = sync_result.get('rules_processed', 0)
        accounts_updated = sync_result.get('accounts_updated', 0)
        budgets_updated = sync_result.get('budgets_updated', 0)

        logger.info(
            f"Sync complete: {transactions_generated} transactions generated "
            f"from {rules_processed} rules, {accounts_updated} accounts updated, "
            f"{budgets_updated} budgets updated"
        )

        return transactions_generated, rules_processed, accounts_updated, budgets_updated

    except Exception as e:
        logger.error(f"Failed to sync recurring transactions: {e}", exc_info=True)
        raise
