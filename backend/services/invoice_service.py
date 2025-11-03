"""
Invoice persistence service.

This module handles saving invoice data to Supabase following the rules
defined in .github/instructions/db.instructions.md.

CRITICAL RULES:
1. invoice.extracted_text MUST follow EXTRACTED_INVOICE_TEXT_FORMAT exactly
2. Do NOT store invoice fields in separate columns (store_name, total_amount, etc.)
3. All data goes into the canonical extracted_text template
4. RLS is enforced automatically via the authenticated Supabase client
"""

import logging
from datetime import datetime
from typing import Dict, Any, Optional
from uuid import UUID

from supabase import Client

logger = logging.getLogger(__name__)

# Canonical format from db.instructions.md
EXTRACTED_INVOICE_TEXT_FORMAT = """Store Name: {store_name}
Transaction Time: {transaction_time}
Total Amount: {total_amount}
Currency: {currency}
Purchased Items:
{purchased_items}
NIT: {nit}"""


def format_extracted_text(
    store_name: str,
    transaction_time: str,
    total_amount: str,
    currency: str,
    purchased_items: str,
    nit: str
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
        nit: Taxpayer identification number (NIT) or receipt identifier
    
    Returns:
        Formatted text matching EXTRACTED_INVOICE_TEXT_FORMAT exactly.
    """
    return EXTRACTED_INVOICE_TEXT_FORMAT.format(
        store_name=store_name,
        transaction_time=transaction_time,
        total_amount=total_amount,
        currency=currency,
        purchased_items=purchased_items,
        nit=nit
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
    nit: str
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
        nit: NIT or receipt identifier
    
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
        nit=nit
    )
    
    # Prepare invoice record
    invoice_data = {
        "user_id": user_id,
        "storage_path": storage_path,
        "extracted_text": extracted_text
    }
    
    logger.info(
        f"Creating invoice for user {user_id}: "
        f"store={store_name}, amount={total_amount} {currency}"
    )
    
    # Insert into Supabase (RLS enforced automatically)
    result = supabase_client.table("invoice").insert(invoice_data).execute()
    
    if not result.data or len(result.data) == 0:
        raise Exception("Failed to create invoice: no data returned")
    
    created_invoice = result.data[0]
    
    logger.info(
        f"Invoice created successfully: id={created_invoice.get('id')}, "
        f"user_id={user_id}"
    )
    
    return created_invoice


async def get_user_invoices(
    supabase_client: Client,
    user_id: str,
    limit: int = 50,
    offset: int = 0
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
    
    logger.info(f"Fetched {len(result.data)} invoices for user {user_id}")
    
    return result.data
