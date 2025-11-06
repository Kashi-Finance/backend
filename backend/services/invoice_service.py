"""
Invoice persistence service.

CRITICAL RULES:
1. invoice.extracted_text MUST follow EXTRACTED_INVOICE_TEXT_FORMAT exactly
2. Do NOT store invoice fields in separate columns (store_name, total_amount, etc.)
3. All data goes into the canonical extracted_text template
4. RLS is enforced automatically via the authenticated Supabase client
"""

import logging
from typing import Dict, Any, Optional, cast, List

from supabase import Client

logger = logging.getLogger(__name__)

# Canonical format (must match backend/db.instructions.md and API expectations)
# We use 'storage_path' here because that's the column name in the DB and the
# identifier we store in Supabase Storage.
EXTRACTED_INVOICE_TEXT_FORMAT = """Store Name: {store_name}
Transaction Time: {transaction_time}
Total Amount: {total_amount}
Currency: {currency}
Purchased Items:
{purchased_items}"""


def format_extracted_text(
    store_name: str,
    transaction_time: str,
    total_amount: str | float,
    currency: str,
    purchased_items: str,
) -> str:
    """
    Format invoice data into the canonical EXTRACTED_INVOICE_TEXT_FORMAT.

    This is the ONLY format allowed for invoice.extracted_text.

    Args:
        store_name: Merchant/store name (cleaned)
        transaction_time: ISO-8601 datetime string
        total_amount: Total as string or float (will be converted to string)
        currency: Currency code (e.g. "GTQ")
        purchased_items: Multi-line list of items with quantities and prices

    Returns:
        Formatted text matching EXTRACTED_INVOICE_TEXT_FORMAT exactly.
    """
    # Convert total_amount to string if it's a float
    total_amount_str = str(total_amount) if isinstance(total_amount, (int, float)) else total_amount
    
    return EXTRACTED_INVOICE_TEXT_FORMAT.format(
        store_name=store_name,
        transaction_time=transaction_time,
        total_amount=total_amount_str,
        currency=currency,
        purchased_items=purchased_items,
    )


async def create_invoice(
    supabase_client: Client,
    user_id: str,
    storage_path: str,
    store_name: str,
    transaction_time: str,
    total_amount: str | float,
    currency: str,
    purchased_items: str,
) -> Dict[str, Any]:
    """
    Create an invoice record in Supabase.

    This function:
    1. Formats invoice data into the canonical extracted_text template
    2. Inserts the record into the invoice table
    3. RLS automatically enforces user_id = auth.uid()

    Args:
        supabase_client: Authenticated Supabase client (with user token)
        user_id: The authenticated user's ID (from JWT token)
        storage_path: Path to the receipt image in Supabase Storage
        store_name: Merchant/store name
        transaction_time: ISO-8601 datetime string
        total_amount: Total amount as string or float
        currency: Currency code
        purchased_items: Formatted list of purchased items

    Returns:
        The created invoice record from Supabase (includes id, created_at, etc.)

    Raises:
        Exception: If the database operation fails

    Security:
        - RLS policies enforce that user_id = auth.uid()
        - The user can only create invoices for themselves
        - No other user can see this invoice
    """
    # Convert total_amount to string if it's a float
    total_amount_str = str(total_amount) if isinstance(total_amount, (int, float)) else total_amount
    
    # Format data into canonical template
    extracted_text = format_extracted_text(
        store_name=store_name,
        transaction_time=transaction_time,
        total_amount=total_amount_str,
        currency=currency,
        purchased_items=purchased_items,
    )

    # Prepare invoice record
    invoice_data = {
        "user_id": user_id,
        "storage_path": storage_path,
        "extracted_text": extracted_text,
    }

    logger.info(
        f"Creating invoice for user {user_id}: "
        f"store={store_name}, amount={total_amount} {currency}"
    )

    # Insert into Supabase (RLS enforced automatically)
    result = supabase_client.table("invoice").insert(invoice_data).execute()

    if not result.data or len(result.data) == 0:
        raise Exception("Failed to create invoice: no data returned")

    # result.data is a JSON-like structure returned by supabase client.
    # Statically cast it to the expected dict type for the type checker.
    created_invoice = cast(Dict[str, Any], result.data[0])

    logger.info(
        f"Invoice created successfully: id={created_invoice.get('id')}, "
        f"user_id={user_id}"
    )

    return created_invoice


async def get_user_invoices(
    supabase_client: Client,
    user_id: str,
    limit: int = 50,
    offset: int = 0,
) -> list[Dict[str, Any]]:
    """
    Fetch invoices for the authenticated user.

    Args:
        supabase_client: Authenticated Supabase client
        user_id: The authenticated user's ID
        limit: Maximum number of invoices to return
        offset: Number of invoices to skip (for pagination)

    Returns:
        List of invoice records (RLS ensures only user's own invoices)

    Security:
        - RLS automatically filters to user_id = auth.uid()
        - User can only see their own invoices
    """
    logger.debug(f"Fetching invoices for user {user_id} (limit={limit}, offset={offset})")

    result = (
        supabase_client.table("invoice")
        .select("*")
        .order("created_at", desc=True)
        .range(offset, offset + limit - 1)
        .execute()
    )

    # Cast the returned JSON list to the expected list-of-dicts type
    invoices = cast(List[Dict[str, Any]], result.data)

    logger.info(f"Fetched {len(invoices)} invoices for user {user_id}")

    return invoices


async def get_invoice_by_id(
    supabase_client: Client,
    user_id: str,
    invoice_id: str,
) -> Optional[Dict[str, Any]]:
    """
    Fetch a single invoice by its ID.

    Args:
        supabase_client: Authenticated Supabase client
        user_id: The authenticated user's ID
        invoice_id: UUID of the invoice to fetch

    Returns:
        Invoice record if found and belongs to user, None otherwise

    Security:
        - RLS automatically enforces user_id = auth.uid()
        - User can only see their own invoices
        - Returns None if invoice doesn't exist or belongs to another user
    """
    logger.debug(f"Fetching invoice {invoice_id} for user {user_id}")

    result = (
        supabase_client.table("invoice")
        .select("*")
        .eq("id", invoice_id)
        .execute()
    )

    if not result.data or len(result.data) == 0:
        logger.warning(f"Invoice {invoice_id} not found or not accessible by user {user_id}")
        return None

    logger.info(f"Fetched invoice {invoice_id} for user {user_id}")

    return cast(Dict[str, Any], result.data[0])


async def delete_invoice(
    supabase_client: Client,
    user_id: str,
    invoice_id: str,
) -> bool:
    """
    Delete an invoice record and its associated storage file.

    This function:
    1. Checks that the invoice exists and belongs to the user
    2. Retrieves the storage_path from the invoice
    3. Deletes the receipt image from Supabase Storage
    4. Deletes the invoice record from the database
    5. RLS automatically enforces user_id = auth.uid()

    Args:
        supabase_client: Authenticated Supabase client (with user token)
        user_id: The authenticated user's ID (from JWT token)
        invoice_id: UUID of the invoice to delete

    Returns:
        True if deletion was successful, False if invoice not found or not accessible

    Raises:
        Exception: If the database operation fails

    Security:
        - RLS policies enforce that user_id = auth.uid()
        - User can only delete their own invoices
        - Attempting to delete another user's invoice will fail silently (return False)

    Note:
        - Deletes BOTH the database record AND the associated receipt image
        - Image deletion is non-critical; DB deletion takes precedence
        - If image deletion fails, invoice is still deleted from DB and a warning is logged
    """
    # First, verify the invoice exists and belongs to the user
    existing = await get_invoice_by_id(supabase_client, user_id, invoice_id)
    if not existing:
        logger.warning(f"Cannot delete invoice {invoice_id}: not found or not accessible by user {user_id}")
        return False

    logger.info(f"Preparing to delete invoice {invoice_id} for user {user_id}")

    # Extract storage_path for storage cleanup
    storage_path = existing.get("storage_path")

    # 1) Handle transactions that reference this invoice
    # Per DB rules: transactions referencing this invoice must be handled before deleting the invoice.
    # The safe and conservative approach: clear invoice_id on all transactions that reference it.
    try:
        update_res = (
            supabase_client.table("transaction")
            .update({"invoice_id": None})
            .eq("invoice_id", invoice_id)
            .execute()
        )
        # update_res.data may be None or empty if no rows matched; that's fine
        transactions_updated = len(update_res.data) if update_res.data else 0
        logger.info(f"Cleared invoice_id on {transactions_updated} transaction(s) referencing invoice {invoice_id}")
    except Exception as e:
        logger.error(f"Failed to clear invoice_id on transactions for invoice {invoice_id}: {e}", exc_info=True)
        raise

    # 2) Delete the associated receipt image from storage BEFORE removing DB row
    if storage_path:
        try:
            from backend.services.storage import delete_invoice_image
            deletion_success = await delete_invoice_image(supabase_client, storage_path)
            if not deletion_success:
                # According to DB rules we must remove the file; treat failure as an error
                logger.error(f"Failed to delete receipt image for invoice {invoice_id}: {storage_path}")
                raise Exception("Failed to delete receipt image from storage")
            logger.info(f"Successfully deleted receipt image for invoice {invoice_id}: {storage_path}")
        except Exception as e:
            logger.error(f"Exception during receipt image deletion for invoice {invoice_id}: {e}", exc_info=True)
            # Bubble up to prevent deleting the DB row if storage cleanup couldn't be completed
            raise

    # 3) Delete invoice DB row (after transactions handled and storage cleaned)
    result = (
        supabase_client.table("invoice")
        .delete()
        .eq("id", invoice_id)
        .execute()
    )

    # Verify deletion actually removed a row
    if not result.data or len(result.data) == 0:
        logger.warning(f"Deletion of invoice {invoice_id} returned no rows for user {user_id}")
        return False

    logger.info(f"Invoice {invoice_id} deleted successfully for user {user_id}")

    return True

