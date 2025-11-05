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
{purchased_items}
Receipt Image ID: {storage_path}"""


def format_extracted_text(
    store_name: str,
    transaction_time: str,
    total_amount: str,
    currency: str,
    purchased_items: str,
    storage_path: str,
) -> str:
    """
    Format invoice data into the canonical EXTRACTED_INVOICE_TEXT_FORMAT.

    This is the ONLY format allowed for invoice.extracted_text.

    Args:
        store_name: Merchant/store name (cleaned)
        transaction_time: ISO-8601 datetime string
        total_amount: Total as string (e.g. "123.45")
        currency: Currency code (e.g. "GTQ")
        purchased_items: Multi-line list of items with quantities and prices
        storage_path: Internal receipt image identifier or storage path (e.g. Supabase Storage path)

    Returns:
        Formatted text matching EXTRACTED_INVOICE_TEXT_FORMAT exactly.
    """
    return EXTRACTED_INVOICE_TEXT_FORMAT.format(
        store_name=store_name,
        transaction_time=transaction_time,
        total_amount=total_amount,
        currency=currency,
        purchased_items=purchased_items,
        storage_path=storage_path,
    )


async def create_invoice(
    supabase_client: Client,
    user_id: str,
    storage_path: str,
    store_name: str,
    transaction_time: str,
    total_amount: str,
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
        total_amount: Total amount as string
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
    # Format data into canonical template
    extracted_text = format_extracted_text(
        store_name=store_name,
        transaction_time=transaction_time,
        total_amount=total_amount,
        currency=currency,
        purchased_items=purchased_items,
        storage_path=storage_path,
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


async def update_invoice(
    supabase_client: Client,
    user_id: str,
    invoice_id: str,
    store_name: Optional[str] = None,
    transaction_time: Optional[str] = None,
    total_amount: Optional[str] = None,
    currency: Optional[str] = None,
    purchased_items: Optional[str] = None,
    storage_path: Optional[str] = None,
) -> Optional[Dict[str, Any]]:
    """
    Update an existing invoice record.

    This function:
    1. Fetches the current invoice to ensure it exists and belongs to the user
    2. Rebuilds the extracted_text in the canonical format with updated fields
    3. Updates the invoice record in Supabase
    4. RLS automatically enforces user_id = auth.uid()

    Args:
        supabase_client: Authenticated Supabase client (with user token)
        user_id: The authenticated user's ID (from JWT token)
        invoice_id: UUID of the invoice to update
        store_name: Updated store name (if provided)
        transaction_time: Updated transaction datetime (if provided)
        total_amount: Updated total amount (if provided)
        currency: Updated currency code (if provided)
        purchased_items: Updated purchased items list (if provided)
        storage_path: Updated storage path (if provided)

    Returns:
        The updated invoice record from Supabase (includes id, created_at, updated_at), or None if not found

    Raises:
        Exception: If the database operation fails

    Security:
        - RLS policies enforce that user_id = auth.uid()
        - User can only update their own invoices
        - Attempting to update another user's invoice will fail silently (return None)
    """
    # First, fetch the existing invoice to get current values
    existing = await get_invoice_by_id(supabase_client, user_id, invoice_id)
    if not existing:
        logger.warning(f"Cannot update invoice {invoice_id}: not found or not accessible by user {user_id}")
        return None

    # Parse the current extracted_text to get existing values
    extracted_text = existing.get("extracted_text", "")
    current_storage_path = existing.get("storage_path", "")

    # Extract current values from extracted_text using simple parsing
    # Format: Store Name: ..., Transaction Time: ..., etc.
    current_values = _parse_extracted_text(extracted_text)

    # Use provided values or fall back to current values
    updated_store_name = store_name or current_values.get("store_name", "")
    updated_transaction_time = transaction_time or current_values.get("transaction_time", "")
    updated_total_amount = total_amount or current_values.get("total_amount", "")
    updated_currency = currency or current_values.get("currency", "")
    updated_purchased_items = purchased_items or current_values.get("purchased_items", "")
    updated_storage_path = storage_path or current_storage_path

    # Rebuild extracted_text in canonical format
    new_extracted_text = format_extracted_text(
        store_name=updated_store_name,
        transaction_time=updated_transaction_time,
        total_amount=updated_total_amount,
        currency=updated_currency,
        purchased_items=updated_purchased_items,
        storage_path=updated_storage_path,
    )

    logger.info(
        f"Updating invoice {invoice_id} for user {user_id}: "
        f"store={updated_store_name}, amount={updated_total_amount} {updated_currency}"
    )

    # Update in Supabase (RLS enforced automatically)
    result = (
        supabase_client.table("invoice")
        .update({"extracted_text": new_extracted_text, "storage_path": updated_storage_path})
        .eq("id", invoice_id)
        .execute()
    )

    if not result.data or len(result.data) == 0:
        logger.warning(f"Failed to update invoice {invoice_id}: no data returned")
        return None

    updated_invoice = cast(Dict[str, Any], result.data[0])

    logger.info(f"Invoice {invoice_id} updated successfully for user {user_id}")

    return updated_invoice


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

    logger.info(f"Deleting invoice {invoice_id} for user {user_id}")

    # Extract storage_path before deletion for cleanup
    storage_path = existing.get("storage_path")
    
    # Delete from Supabase (RLS enforced automatically)
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

    # Delete the associated receipt image from storage
    # This is a non-critical operation - invoice is already deleted from DB
    if storage_path:
        try:
            from backend.services.storage import delete_invoice_image
            deletion_success = await delete_invoice_image(supabase_client, storage_path)
            if deletion_success:
                logger.info(f"Successfully deleted receipt image for invoice {invoice_id}: {storage_path}")
            else:
                logger.warning(f"Failed to delete receipt image for invoice {invoice_id}: {storage_path}")
        except Exception as e:
            logger.warning(f"Exception during receipt image deletion for invoice {invoice_id}: {e}")
    
    return True


def _parse_extracted_text(extracted_text: str) -> Dict[str, str]:
    """
    Parse the canonical extracted_text format into individual fields.

    Parses the EXTRACTED_INVOICE_TEXT_FORMAT template back into structured data.

    Args:
        extracted_text: The canonical formatted invoice text

    Returns:
        Dictionary with keys: store_name, transaction_time, total_amount,
        currency, purchased_items, storage_path

    Note:
        This is a best-effort parser. Missing fields will have empty string values.
    """
    result = {
        "store_name": "",
        "transaction_time": "",
        "total_amount": "",
        "currency": "",
        "purchased_items": "",
        "storage_path": "",
    }

    lines = extracted_text.split("\n")
    current_section = None

    for line in lines:
        line = line.rstrip()

        if line.startswith("Store Name:"):
            result["store_name"] = line.replace("Store Name:", "").strip()
        elif line.startswith("Transaction Time:"):
            result["transaction_time"] = line.replace("Transaction Time:", "").strip()
        elif line.startswith("Total Amount:"):
            result["total_amount"] = line.replace("Total Amount:", "").strip()
        elif line.startswith("Currency:"):
            result["currency"] = line.replace("Currency:", "").strip()
        elif line.startswith("Purchased Items:"):
            current_section = "purchased_items"
        elif line.startswith("Receipt Image ID:"):
            result["storage_path"] = line.replace("Receipt Image ID:", "").strip()
            current_section = None
        elif current_section == "purchased_items" and line.strip():
            # Accumulate purchased items lines
            if result["purchased_items"]:
                result["purchased_items"] += "\n" + line
            else:
                result["purchased_items"] = line

    return result
