"""
Service layer for Kashi Finances Backend.

Contains business logic orchestration that:
- Adapts endpoint requests to adk agent calls
- Enforces domain filtering and scope checking before calling agents
- Maps agent outputs into Pydantic ResponseModels
- Handles persistence coordination (calling DB layer under RLS)

Services act as the glue between routes (HTTP layer) and agents/database.
"""

from .account_service import (
    get_user_accounts,
    get_account_by_id,
    create_account,
    update_account,
    delete_account_with_reassignment,
    delete_account_with_transactions,
    recompute_account_balance,
)
from .budget_service import (
    get_all_budgets,
    get_budget_by_id,
    create_budget,
    update_budget,
    delete_budget,
)
from .category_service import (
    get_all_categories,
    get_category_by_id,
    create_category,
    update_category,
    delete_category,
)
from .invoice_service import create_invoice, get_user_invoices, get_invoice_by_id, format_extracted_text, delete_invoice
from .profile_service import (
    get_user_profile,
    create_user_profile,
    update_user_profile,
    delete_user_profile
)
from .storage import upload_invoice_image, get_invoice_image_url, delete_invoice_image
from .transaction_service import (
    create_transaction,
    get_user_transactions,
    get_transaction_by_id,
    update_transaction,
    delete_transaction,
)
from .recurring_transaction_service import (
    get_all_recurring_transactions,
    get_recurring_transaction_by_id,
    create_recurring_transaction,
    update_recurring_transaction,
    delete_recurring_transaction,
    sync_recurring_transactions,
)

__all__ = [
    "get_user_accounts",
    "get_account_by_id",
    "create_account",
    "update_account",
    "delete_account_with_reassignment",
    "delete_account_with_transactions",
    "recompute_account_balance",
    "get_all_budgets",
    "get_budget_by_id",
    "create_budget",
    "update_budget",
    "delete_budget",
    "get_all_categories",
    "get_category_by_id",
    "create_category",
    "update_category",
    "delete_category",
    "create_invoice",
    "get_user_invoices",
    "get_invoice_by_id",
    "format_extracted_text",
    "delete_invoice",
    "get_user_profile",
    "create_user_profile",
    "update_user_profile",
    "delete_user_profile",
    "upload_invoice_image",
    "get_invoice_image_url",
    "delete_invoice_image",
    "create_transaction",
    "get_user_transactions",
    "get_transaction_by_id",
    "update_transaction",
    "delete_transaction",
    "get_all_recurring_transactions",
    "get_recurring_transaction_by_id",
    "create_recurring_transaction",
    "update_recurring_transaction",
    "delete_recurring_transaction",
    "sync_recurring_transactions",
]
