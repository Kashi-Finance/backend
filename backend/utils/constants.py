"""
System-generated key constants for transaction.system_generated_key field.

These keys mark transactions that were created automatically by the system
(not manually entered by the user). Used for UI decoration and filtering.

See: DB-documentation.md section "System-Generated Key List"
"""

SYSTEM_GENERATED_KEYS = {
    # Recurring transactions materialized from templates
    'RECURRING_SYNC': 'recurring_sync',

    # Transactions created from invoice OCR extraction
    'INVOICE_OCR': 'invoice_ocr',

    # Initial balance transaction when creating an account
    'INITIAL_BALANCE': 'initial_balance',

    # Future: Bulk import tools (not yet implemented)
    'BULK_IMPORT': 'bulk_import',
}
