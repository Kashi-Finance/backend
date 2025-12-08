"""
Transaction persistence service.

CRITICAL RULES:
1. All operations MUST respect RLS (user_id = auth.uid())
2. Never trust client-provided user_id - always use authenticated user_id from JWT
3. Handle paired transactions (transfers) according to DB delete rules
4. Invoice-linked transactions should clear invoice_id when invoice is deleted
5. After transaction CRUD, recompute both account balance AND budget consumption
"""

import logging
from typing import Any, Dict, List, Optional, cast

from supabase import Client

logger = logging.getLogger(__name__)


async def _recompute_budgets_for_category(
    supabase_client: Client,
    user_id: str,
    category_id: str
) -> None:
    """
    Recompute cached_consumption for all budgets tracking the given category.

    This should be called after creating, updating, or deleting a transaction
    to keep budget data in sync. The RPC finds all active budgets that track
    this category and recalculates their consumption atomically.

    Args:
        supabase_client: Authenticated Supabase client
        user_id: The authenticated user's ID
        category_id: The category affected by the transaction

    Note:
        This is a non-blocking operation - failures are logged but don't
        raise exceptions to avoid failing the main transaction operation.
    """
    try:
        result = supabase_client.rpc(
            'recompute_budgets_for_category',
            {
                'p_user_id': user_id,
                'p_category_id': category_id
            }
        ).execute()

        # Log which budgets were updated (RPC returns table, data is a list)
        if result.data and isinstance(result.data, list):
            for budget_update in result.data:
                if isinstance(budget_update, dict):
                    budget_name = budget_update.get('budget_name', 'Unknown')
                    old_val = budget_update.get('old_consumption', 0)
                    new_val = budget_update.get('new_consumption', 0)
                    if old_val != new_val:
                        logger.debug(
                            f"Budget '{budget_name}' consumption updated: "
                            f"{old_val} -> {new_val}"
                        )
    except Exception as e:
        logger.warning(f"Failed to recompute budgets for category {category_id}: {e}")
        # Don't raise - budget recompute is non-critical


async def create_transaction(
    supabase_client: Client,
    user_id: str,
    account_id: str,
    category_id: str,
    flow_type: str,
    amount: float,
    date: str,
    description: Optional[str] = None,
    invoice_id: Optional[str] = None,
    system_generated_key: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Create a transaction record in Supabase.

    This function:
    1. Validates that flow_type is 'income' or 'outcome'
    2. Inserts the record into the transaction table
    3. RLS automatically enforces user_id = auth.uid()

    Args:
        supabase_client: Authenticated Supabase client (with user token)
        user_id: The authenticated user's ID (from JWT token)
        account_id: UUID of the account affected by this transaction
        category_id: UUID of the spending/earning category
        flow_type: Money direction ('income' or 'outcome')
        amount: Transaction amount (must be >= 0)
        date: ISO-8601 datetime when transaction occurred
        description: Optional human-readable description
        invoice_id: Optional UUID of linked invoice (if created from OCR)
        system_generated_key: Optional short string to tag system-created transactions
            (e.g. 'recurring_sync', 'invoice_ocr', 'initial_balance'). Database
            column is nullable; pass None when not applicable.

    Returns:
        The created transaction record from Supabase (includes id, created_at, etc.)

    Raises:
        ValueError: If flow_type is invalid
        Exception: If the database operation fails

    Security:
        - RLS policies enforce that user_id = auth.uid()
        - The user can only create transactions for themselves
        - No other user can see this transaction
    """
    # Validate flow_type
    if flow_type not in ("income", "outcome"):
        raise ValueError(f"Invalid flow_type: {flow_type}. Must be 'income' or 'outcome'")

    # Prepare transaction record
    transaction_data = {
        "user_id": user_id,
        "account_id": account_id,
        "category_id": category_id,
        "flow_type": flow_type,
        "amount": amount,
        "date": date,
        "description": description,
        "invoice_id": invoice_id,
        "system_generated_key": system_generated_key,
    }

    logger.info(
        f"Creating transaction for user {user_id}: "
        f"account={account_id}, amount={amount}, flow_type={flow_type}"
    )

    # Insert into Supabase (RLS enforced automatically)
    result = supabase_client.table("transaction").insert(transaction_data).execute()

    if not result.data or len(result.data) == 0:
        raise Exception("Failed to create transaction: no data returned")

    created_transaction = cast(Dict[str, Any], result.data[0])

    logger.info(
        f"Transaction created successfully: id={created_transaction.get('id')}, "
        f"user_id={user_id}"
    )

    # Recompute account balance after creating transaction
    try:
        from backend.services.account_service import recompute_account_balance
        await recompute_account_balance(supabase_client, user_id, account_id)
        logger.debug(f"Account balance recomputed for account {account_id} after transaction creation")
    except Exception as e:
        logger.warning(f"Failed to recompute account balance after transaction creation: {e}")
        # Don't fail the transaction creation, just log the warning
        # The balance can be recomputed later if needed

    # Recompute budget consumption for all budgets tracking this category
    # Only applies to outcome transactions (expenses affect budget consumption)
    if flow_type == "outcome":
        await _recompute_budgets_for_category(supabase_client, user_id, category_id)

    # TODO(db-team): generate and save embedding for transaction.embedding field using text-embedding-3-small
    # The embedding should be generated from:
    # 1. If invoice_id is not NULL: fetch invoice.extracted_text and combine with transaction data
    # 2. If invoice_id is NULL: use transaction data only (description, amount, category_name, date)
    # This enables semantic search over transactions (e.g., "show all grocery-like expenses")
    # See backend/db.instructions.md section 3 for detailed embedding generation strategy

    return created_transaction


async def get_user_transactions(
    supabase_client: Client,
    user_id: str,
    limit: int = 50,
    offset: int = 0,
    account_id: Optional[str] = None,
    category_id: Optional[str] = None,
    flow_type: Optional[str] = None,
    from_date: Optional[str] = None,
    to_date: Optional[str] = None,
    sort_by: str = "date",
    sort_order: str = "desc",
) -> List[Dict[str, Any]]:
    """
    Fetch transactions for the authenticated user with optional filters and sorting.

    Args:
        supabase_client: Authenticated Supabase client
        user_id: The authenticated user's ID
        limit: Maximum number of transactions to return
        offset: Number of transactions to skip (for pagination)
        account_id: Optional filter by account
        category_id: Optional filter by category
        flow_type: Optional filter by flow type ('income' or 'outcome')
        from_date: Optional filter by start date (ISO-8601)
        to_date: Optional filter by end date (ISO-8601)
        sort_by: Field to sort by ('date' or 'amount', default 'date')
        sort_order: Sort order ('asc' or 'desc', default 'desc')

    Returns:
        List of transaction records (RLS ensures only user's own transactions)

    Security:
        - RLS automatically filters to user_id = auth.uid()
        - User can only see their own transactions
    """
    logger.debug(
        f"Fetching transactions for user {user_id} "
        f"(limit={limit}, offset={offset}, sort_by={sort_by}, sort_order={sort_order}, "
        f"filters: account={account_id}, category={category_id}, flow_type={flow_type})"
    )

    # Build query with filters
    query = supabase_client.table("transaction").select("*")

    if account_id:
        query = query.eq("account_id", account_id)
    if category_id:
        query = query.eq("category_id", category_id)
    if flow_type:
        query = query.eq("flow_type", flow_type)
    if from_date:
        query = query.gte("date", from_date)
    if to_date:
        query = query.lte("date", to_date)

    # Validate sort_by field
    allowed_sort_fields = ["date", "amount"]
    if sort_by not in allowed_sort_fields:
        logger.warning(f"Invalid sort_by '{sort_by}', defaulting to 'date'")
        sort_by = "date"

    # Validate sort_order
    if sort_order not in ["asc", "desc"]:
        logger.warning(f"Invalid sort_order '{sort_order}', defaulting to 'desc'")
        sort_order = "desc"

    # Apply ordering and pagination
    is_desc = sort_order == "desc"
    result = query.order(sort_by, desc=is_desc).range(offset, offset + limit - 1).execute()

    transactions = cast(List[Dict[str, Any]], result.data)

    logger.info(f"Fetched {len(transactions)} transactions for user {user_id}")

    return transactions


async def get_transaction_by_id(
    supabase_client: Client,
    user_id: str,
    transaction_id: str,
) -> Optional[Dict[str, Any]]:
    """
    Fetch a single transaction by its ID.

    Args:
        supabase_client: Authenticated Supabase client
        user_id: The authenticated user's ID
        transaction_id: UUID of the transaction to fetch

    Returns:
        Transaction record if found and belongs to user, None otherwise

    Security:
        - RLS automatically enforces user_id = auth.uid()
        - User can only see their own transactions
        - Returns None if transaction doesn't exist or belongs to another user
    """
    logger.debug(f"Fetching transaction {transaction_id} for user {user_id}")

    result = (
        supabase_client.table("transaction")
        .select("*")
        .eq("id", transaction_id)
        .execute()
    )

    if not result.data or len(result.data) == 0:
        logger.warning(
            f"Transaction {transaction_id} not found or not accessible by user {user_id}"
        )
        return None

    logger.info(f"Fetched transaction {transaction_id} for user {user_id}")

    return cast(Dict[str, Any], result.data[0])


async def update_transaction(
    supabase_client: Client,
    user_id: str,
    transaction_id: str,
    account_id: Optional[str] = None,
    category_id: Optional[str] = None,
    flow_type: Optional[str] = None,
    amount: Optional[float] = None,
    date: Optional[str] = None,
    description: Optional[str] = None,
) -> Optional[Dict[str, Any]]:
    """
    Update an existing transaction record.

    This function:
    1. Fetches the current transaction to ensure it exists and belongs to the user
    2. Updates only the provided fields
    3. RLS automatically enforces user_id = auth.uid()

    Args:
        supabase_client: Authenticated Supabase client (with user token)
        user_id: The authenticated user's ID (from JWT token)
        transaction_id: UUID of the transaction to update
        account_id: Updated account UUID (if provided)
        category_id: Updated category UUID (if provided)
        flow_type: Updated money direction (if provided)
        amount: Updated transaction amount (if provided)
        date: Updated datetime (if provided)
        description: Updated description (if provided)

    Returns:
        The updated transaction record from Supabase, or None if not found

    Raises:
        ValueError: If flow_type is invalid
        Exception: If the database operation fails

    Security:
        - RLS policies enforce that user_id = auth.uid()
        - User can only update their own transactions
        - Attempting to update another user's transaction will fail silently (return None)
    """
    # First, verify the transaction exists and belongs to the user
    existing = await get_transaction_by_id(supabase_client, user_id, transaction_id)
    if not existing:
        logger.warning(
            f"Cannot update transaction {transaction_id}: "
            f"not found or not accessible by user {user_id}"
        )
        return None

    # Validate flow_type if provided
    if flow_type and flow_type not in ("income", "outcome"):
        raise ValueError(f"Invalid flow_type: {flow_type}. Must be 'income' or 'outcome'")

    # Build update payload with only provided fields
    update_data: Dict[str, Any] = {}
    if account_id is not None:
        update_data["account_id"] = account_id
    if category_id is not None:
        update_data["category_id"] = category_id
    if flow_type is not None:
        update_data["flow_type"] = flow_type
    if amount is not None:
        update_data["amount"] = amount
    if date is not None:
        update_data["date"] = date
    if description is not None:
        update_data["description"] = description

    if not update_data:
        logger.warning(f"No fields to update for transaction {transaction_id}")
        return existing

    logger.info(
        f"Updating transaction {transaction_id} for user {user_id}: "
        f"fields={list(update_data.keys())}"
    )

    # Update in Supabase (RLS enforced automatically)
    result = (
        supabase_client.table("transaction")
        .update(update_data)
        .eq("id", transaction_id)
        .execute()
    )

    if not result.data or len(result.data) == 0:
        logger.warning(f"Failed to update transaction {transaction_id}: no data returned")
        return None

    updated_transaction = cast(Dict[str, Any], result.data[0])

    logger.info(f"Transaction {transaction_id} updated successfully for user {user_id}")

    # Recompute account balance if amount, account, or flow_type changed
    should_recompute = (
        amount is not None or
        account_id is not None or
        flow_type is not None
    )

    if should_recompute:
        try:
            from backend.services.account_service import recompute_account_balance

            # Recompute balance for current account
            current_account = updated_transaction.get("account_id")
            if current_account:
                await recompute_account_balance(supabase_client, user_id, current_account)
                logger.debug(f"Account balance recomputed for account {current_account} after update")

            # If account changed, also recompute old account balance
            if account_id is not None and existing.get("account_id") != account_id:
                old_account = existing.get("account_id")
                if old_account:
                    await recompute_account_balance(supabase_client, user_id, old_account)
                    logger.debug(f"Account balance recomputed for old account {old_account} after transfer")

        except Exception as e:
            logger.warning(f"Failed to recompute account balance after transaction update: {e}")
            # Don't fail the update, just log the warning

    # TODO(db-team): regenerate and save embedding for transaction.embedding field using text-embedding-3-small
    # The embedding should be regenerated if description, amount, category, or date changed
    # Generation strategy:
    # 1. If invoice_id is not NULL: fetch invoice.extracted_text and combine with updated transaction data
    # 2. If invoice_id is NULL: use updated transaction data only (description, amount, category_name, date)
    # This maintains accurate semantic search after updates
    # See backend/db.instructions.md section 3 for detailed embedding generation strategy

    # Recompute budget consumption if amount, category, flow_type, or date changed
    should_recompute_budget = (
        amount is not None or
        category_id is not None or
        flow_type is not None or
        date is not None
    )

    if should_recompute_budget:
        # Get the current category to recompute its budgets
        current_category = updated_transaction.get("category_id")
        if current_category:
            await _recompute_budgets_for_category(supabase_client, user_id, current_category)

        # If category changed, also recompute the old category's budgets
        if category_id is not None and existing.get("category_id") != category_id:
            old_category = existing.get("category_id")
            if old_category:
                await _recompute_budgets_for_category(supabase_client, user_id, old_category)

    return updated_transaction


async def delete_transaction(
    supabase_client: Client,
    user_id: str,
    transaction_id: str,
) -> bool:
    """
    Delete a transaction record.

    This function:
    1. Checks that the transaction exists and belongs to the user
    2. If paired (transfer), clears the pair reference or removes both
    3. If linked to invoice, does NOT delete the invoice
    4. Deletes the transaction from the database
    5. RLS automatically enforces user_id = auth.uid()

    Args:
        supabase_client: Authenticated Supabase client (with user token)
        user_id: The authenticated user's ID (from JWT token)
        transaction_id: UUID of the transaction to delete

    Returns:
        True if deletion was successful, False if transaction not found or not accessible

    Raises:
        Exception: If the database operation fails

    Security:
        - RLS policies enforce that user_id = auth.uid()
        - User can only delete their own transactions
        - Attempting to delete another user's transaction will fail silently (return False)

    Note:
        - This does NOT delete linked invoices (invoice persistence is separate)
        - If part of a transfer (paired_transaction_id), the pair reference is cleared
        - Storage cleanup for invoice images should be handled separately if needed
    """
    # First, verify the transaction exists and belongs to the user
    existing = await get_transaction_by_id(supabase_client, user_id, transaction_id)
    if not existing:
        logger.warning(
            f"Cannot delete transaction {transaction_id}: "
            f"not found or not accessible by user {user_id}"
        )
        return False

    # Check if this is part of a paired transfer
    paired_id = existing.get("paired_transaction_id")
    if paired_id:
        logger.info(
            f"Transaction {transaction_id} is paired with {paired_id}. "
            f"Deleting both transactions (transfer)."
        )
        # Use transfer service to delete both sides
        from backend.services.transfer_service import delete_transfer
        try:
            await delete_transfer(supabase_client, user_id, transaction_id)
            return True
        except Exception as e:
            logger.error(f"Failed to delete paired transfer: {e}")
            raise

    logger.info(f"Deleting transaction {transaction_id} for user {user_id}")

    # Delete from Supabase (RLS enforced automatically)
    result = (
        supabase_client.table("transaction")
        .delete()
        .eq("id", transaction_id)
        .execute()
    )

    # Verify deletion actually removed a row
    if not result.data or len(result.data) == 0:
        logger.warning(
            f"Deletion of transaction {transaction_id} returned no rows for user {user_id}"
        )
        return False

    logger.info(f"Transaction {transaction_id} deleted successfully for user {user_id}")

    # Recompute account balance after deletion
    try:
        from backend.services.account_service import recompute_account_balance
        account_id_for_recompute = existing.get("account_id")
        if account_id_for_recompute:
            await recompute_account_balance(supabase_client, user_id, account_id_for_recompute)
            logger.debug(f"Account balance recomputed for account {account_id_for_recompute} after deletion")
    except Exception as e:
        logger.warning(f"Failed to recompute account balance after transaction deletion: {e}")
        # Don't fail the deletion, just log the warning

    # Recompute budget consumption for affected category
    category_id = existing.get("category_id")
    if category_id:
        await _recompute_budgets_for_category(supabase_client, user_id, category_id)

    return True
