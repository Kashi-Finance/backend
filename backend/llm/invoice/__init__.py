"""
Invoice OCR workflow package (legacy name: InvoiceAgent).

Single-shot invoice OCR and extraction pipeline using Google Gemini
(via the google-genai SDK, no agent framework). The workflow:
- Extracts store name, transaction time, total amount, currency
- Parses individual line items with quantities and prices
- Suggests category assignments based on user's existing categories
- Handles invalid images and out-of-scope requests gracefully

Main Components:
- types: TypedDict definitions for structured data
- tools: Backend helper functions (profile, categories) - called by endpoint
- schemas: JSON schemas for validation
- prompts: System prompts for the LLM
- agent: Main runner function that performs the single Gemini call

Usage:
    from backend.llm.invoice import run_invoice_agent

    result = run_invoice_agent(
        user_id="user-uuid-from-auth",
        receipt_image_id="img-123",
        user_categories=categories_list,
        receipt_image_base64=encoded_image,
        country="GT",
        currency_preference="GTQ"
    )
"""

from backend.llm.invoice.agent import run_invoice_agent
from backend.llm.invoice.prompts import (
    INVOICE_AGENT_SYSTEM_PROMPT,
)
from backend.llm.invoice.schemas import (
    INPUT_SCHEMA,
    OUTPUT_SCHEMA,
)
from backend.llm.invoice.tools import (
    get_user_categories,
    get_user_profile,
)
from backend.llm.invoice.types import (
    CategorySuggestion,
    InvoiceAgentInput,
    InvoiceAgentOutput,
    PurchasedItem,
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
