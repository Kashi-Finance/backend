"""
InvoiceAgent Package

Modular InvoiceAgent implementation for extracting structured data from receipts.

This package provides a complete invoice OCR and extraction pipeline using
Google Gemini with a single-shot LLM call. The agent can:
- Extract store name, transaction time, total amount, currency
- Parse individual line items with quantities and prices
- Suggest category assignments based on user's existing categories
- Handle invalid images and out-of-scope requests gracefully

Main Components:
- types: TypedDict definitions for structured data
- tools: Backend helper functions (profile, categories) - called by endpoint
- schemas: JSON schemas for validation
- prompts: System prompts for the LLM
- agent: Main runner function that orchestrates Gemini interaction

Usage:
    from backend.agents.invoice import run_invoice_agent
    
    result = run_invoice_agent(
        user_id="user-uuid-from-auth",
        receipt_image_id="img-123",
        user_categories=categories_list,
        receipt_image_base64=encoded_image,
        country="GT",
        currency_preference="GTQ"
    )
"""

from backend.agents.invoice.agent import run_invoice_agent
from backend.agents.invoice.types import (
    PurchasedItem,
    CategorySuggestion,
    InvoiceAgentInput,
    InvoiceAgentOutput,
)
from backend.agents.invoice.tools import (
    get_user_profile,
    get_user_categories,
)
from backend.agents.invoice.schemas import (
    INPUT_SCHEMA,
    OUTPUT_SCHEMA,
)
from backend.agents.invoice.prompts import (
    INVOICE_AGENT_SYSTEM_PROMPT,
)

__all__ = [
    # Main runner
    "run_invoice_agent",
    # Types
    "PurchasedItem",
    "CategorySuggestion",
    "InvoiceAgentInput",
    "InvoiceAgentOutput",
    # Tools
    "get_user_profile",
    "get_user_categories",
    # Schemas
    "INPUT_SCHEMA",
    "OUTPUT_SCHEMA",
    # Prompts
    "INVOICE_AGENT_SYSTEM_PROMPT",
]
