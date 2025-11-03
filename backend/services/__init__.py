"""
Service layer for Kashi Finances Backend.

Contains business logic orchestration that:
- Adapts endpoint requests to adk agent calls
- Enforces domain filtering and scope checking before calling agents
- Maps agent outputs into Pydantic ResponseModels
- Handles persistence coordination (calling DB layer under RLS)

Services act as the glue between routes (HTTP layer) and agents/database.
"""

from .invoice_service import create_invoice, get_user_invoices, format_extracted_text
from .profile_service import (
    get_user_profile,
    create_user_profile,
    update_user_profile
)

__all__ = [
    "create_invoice",
    "get_user_invoices",
    "format_extracted_text",
    "get_user_profile",
    "create_user_profile",
    "update_user_profile",
]
