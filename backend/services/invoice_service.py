"""
Invoice persistence service.

CRITICAL RULES:
1. invoice.extracted_text MUST follow EXTRACTED_INVOICE_TEXT_FORMAT exactly
2. Do NOT store invoice fields in separate columns (store_name, total_amount, etc.)
3. All data goes into the canonical extracted_text template
4. RLS is enforced automatically via the authenticated Supabase client
"""

import logging
from typing import Any, Dict, List, Optional, cast

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
) -> tuple[bool, str | None]:
    """
    Soft-delete an invoice record using the delete_invoice RPC.

    This function:
    1. Calls the delete_invoice RPC for atomic soft-delete operation
    2. RPC validates ownership and sets deleted_at timestamp
    3. Optionally handles storage cleanup after successful soft-delete

    Args:
        supabase_client: Authenticated Supabase client (with user token)
        user_id: The authenticated user's ID (from JWT token)
        invoice_id: UUID of the invoice to soft-delete

    Returns:
        Tuple of (success, deleted_at timestamp or None)

    Raises:
        Exception: If the RPC call fails

    Security:
        - RPC validates user_id ownership before soft-deleting
        - User can only delete their own invoices
        - Attempting to delete another user's invoice will raise an exception

    Note:
        - Uses soft-delete (sets deleted_at) via RPC
        - Storage cleanup should be handled asynchronously/separately if needed
        - Transactions referencing this invoice are NOT modified (invoice remains in history)
    """
    logger.info(f"Preparing to soft-delete invoice {invoice_id} for user {user_id}")

    try:
        # Call the delete_invoice RPC for atomic soft-delete
        rpc_res = supabase_client.rpc(
            "delete_invoice",
            {
                "p_invoice_id": invoice_id,
                "p_user_id": user_id,
            },
        ).execute()

        data = getattr(rpc_res, "data", None)
        if not isinstance(data, list) or len(data) == 0:
            logger.warning(f"RPC delete_invoice returned no rows for invoice {invoice_id}")
            return (False, None)

        row = cast(Dict[str, Any], data[0])
        invoice_soft_deleted = bool(row.get("invoice_soft_deleted", False))
        deleted_at = row.get("deleted_at")

        if invoice_soft_deleted:
            logger.info(f"Invoice {invoice_id} soft-deleted successfully via RPC at {deleted_at}")
            return (True, deleted_at)
        else:
            logger.warning(f"Invoice {invoice_id} soft-delete failed via RPC")
            return (False, None)

    except Exception as e:
        logger.error(f"Failed to soft-delete invoice via RPC for {invoice_id}: {e}", exc_info=True)
        raise

