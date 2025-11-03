"""
InvoiceAgent - Receipt/Invoice Processing Agent

This adk agent extracts structured financial data from invoice/receipt images.

Responsibilities:
- Parse invoice images to extract store_name, transaction_time, total_amount, currency, items
- Suggest appropriate expense category (match existing or propose new)
- Return structured data suitable for persistence under RLS
- Generate canonical extracted_text snapshot for DB storage

Out-of-scope:
- General finance advice
- Non-invoice questions
- Database writes (handled by API layer)

Security:
- Does NOT log full invoice images or complete transaction histories
- Does NOT write to database directly
- Assumes backend has validated Supabase token and resolved user_id
"""

import logging
from typing import TypedDict, Literal, Optional
from dataclasses import dataclass
from google import genai
from google.genai import types

logger = logging.getLogger(__name__)


# ============================================================================
# Type Definitions (Input/Output Contracts)
# ============================================================================

class PurchasedItem(TypedDict):
    """Single line item from an invoice."""
    description: str
    quantity: float
    unit_price: Optional[float]
    line_total: float


class CategorySuggestion(TypedDict):
    """Category assignment suggestion for the invoice."""
    match_type: Literal["EXISTING", "NEW_PROPOSED"]
    category_id: Optional[str]  # UUID if EXISTING
    category_name: Optional[str]  # name if EXISTING or NEW_PROPOSED
    proposed_name: Optional[str]  # only if NEW_PROPOSED


class InvoiceAgentInput(TypedDict):
    """Input schema for InvoiceAgent."""
    user_id: str  # Authenticated user (from Supabase Auth, never from client)
    receipt_image_id: str  # Reference to uploaded image in storage
    receipt_image_base64: Optional[str]  # Base64-encoded image data (if available)
    ocr_text: Optional[str]  # Pre-extracted OCR text (optional)
    country: str  # User's country (from getUserCountry or getUserProfile)
    currency_preference: str  # User's preferred currency (from getUserProfile)


class InvoiceAgentOutput(TypedDict):
    """Output schema for InvoiceAgent."""
    status: Literal["DRAFT", "INVALID_IMAGE", "OUT_OF_SCOPE"]
    
    # Present when status == "DRAFT"
    store_name: Optional[str]
    transaction_time: Optional[str]  # ISO-8601 datetime string
    total_amount: Optional[float]
    currency: Optional[str]
    purchased_items: Optional[list[PurchasedItem]]
    category_suggestion: Optional[CategorySuggestion]
    extracted_text: Optional[str]  # Canonical multi-line snapshot
    
    # Present when status != "DRAFT"
    reason: Optional[str]  # Short factual explanation


# ============================================================================
# Tool Definitions (Available to the Agent)
# ============================================================================

# The agent has access to these tools. They MUST be documented here so the
# agent runtime knows when and how to call them.

TOOLS_DOCUMENTATION = """
Available Tools for InvoiceAgent:

1. fetch()
   Purpose: Retrieve the most recent ADK runtime / tool invocation spec / policy docs.
   Use when: At the start of execution to ensure updated contract.
   Input: {} (no parameters)
   Output: Opaque doc string / JSON with current ADK rules.
   Security: Read-only.
   Notes: MUST be called first to self-sync with current ADK guidelines.

2. getUserProfile(user_id: str) -> dict
   Purpose: Return basic profile context (country, currency_preference, locale).
   Input: {"user_id": "uuid"}
   Output: {"country": "GT", "currency_preference": "GTQ", "locale": "es-GT"}
   Use cases: 
     - Get currency_preference fallback if receipt currency is missing
     - Localization context
   Security: Backend injects user_id. Agent MUST NOT trust arbitrary client user_id.

3. getUserCategories(user_id: str) -> list[dict]
   Purpose: Return the list of categories the user can assign to expenses.
   Input: {"user_id": "uuid"}
   Output: [
     {"category_id": "uuid-1", "name": "Supermercado", "flow_type": "outcome"},
     {"category_id": "uuid-2", "name": "General", "flow_type": "outcome", "is_default": true}
   ]
   Use cases:
     - Build category_suggestion:
       * match_type: "EXISTING" -> map to existing category_id
       * match_type: "NEW_PROPOSED" -> suggest new name but DO NOT create it
   Security: Read-only. MUST NOT write or create categories.

IMPORTANT: The agent MUST respond ONLY with valid JSON matching the output schema.
No prose, no markdown, no trailing comments in the runtime response.
"""


# ============================================================================
# Agent System Prompt
# ============================================================================

INVOICE_AGENT_SYSTEM_PROMPT = f"""
You are InvoiceAgent, a specialized receipt/invoice processing agent for Kashi Finances.

YOUR ROLE:
- Extract structured financial data from invoice/receipt images
- Suggest appropriate expense categories
- Return clean, validated JSON output

AVAILABLE TOOLS:
{TOOLS_DOCUMENTATION}

WORKFLOW:
1. FIRST: Call fetch() to get the latest ADK spec (you MUST do this before any other action)
2. Validate the request is in-scope (invoice/receipt processing ONLY)
3. If out-of-scope (e.g., general questions, advice, non-invoice content):
   Return: {{"status": "OUT_OF_SCOPE", "reason": "InvoiceAgent only processes receipts."}}
4. If the image is not usable (corrupted, not an invoice, unreadable):
   Return: {{"status": "INVALID_IMAGE", "reason": "factual explanation"}}
5. If the image is valid:
   a. Call getUserProfile(user_id) to get currency_preference fallback
   b. Call getUserCategories(user_id) to get available categories
   c. Extract: store_name, transaction_time (ISO-8601), total_amount, currency, purchased_items[]
   d. Build category_suggestion:
      - If store/items match an existing category -> match_type: "EXISTING", category_id: "..."
      - If no match -> match_type: "NEW_PROPOSED", proposed_name: "suggested name"
   e. Generate extracted_text using EXACT template:
      
      Store Name: {{store_name}}
      Transaction Time: {{transaction_time}}
      Total Amount: {{total_amount}}
      Currency: {{currency}}
      Purchased Items:
      {{purchased_items}}
      Receipt Image ID: {{receipt_id}}
      
   f. Return: {{"status": "DRAFT", "store_name": "...", ...}}

GUARDRAILS:
- REFUSE sexual content, weapons, illegal goods, scams
- REFUSE general finance advice or chat
- ONLY answer invoice/receipt processing requests
- NEVER log full invoice images or sensitive financial data
- NEVER write to database (persistence is handled by API layer)
- NEVER trust user_id from client (backend provides the real one)

OUTPUT FORMAT:
- ALWAYS return valid JSON matching InvoiceAgentOutput schema
- NO markdown, NO prose, NO comments
- If out-of-scope or invalid, still return valid JSON with appropriate status

SECURITY:
- Backend has already validated Supabase token and resolved user_id
- Do NOT override or invent user_id values
- Do NOT expose sensitive data beyond what's needed for the invoice draft
"""


# ============================================================================
# Mock Tool Implementations (Placeholders for Backend Integration)
# ============================================================================

def fetch_adk_spec() -> dict:
    """
    Fetches the latest ADK runtime spec.
    
    In production, this would call an actual endpoint or cache.
    For now, returns a placeholder.
    """
    return {
        "version": "2025-11-01",
        "spec": "Google ADK with Gemini function calling",
        "notes": "Use OpenAPI-compatible schema for function declarations"
    }


def get_user_profile(user_id: str) -> dict:
    """
    Get user profile (country, currency_preference, locale).
    
    TODO(db-team): Implement actual DB query following backend/db.instructions.md
    
    Args:
        user_id: Authenticated user UUID from Supabase Auth
        
    Returns:
        Profile dict with country, currency_preference, locale
    """
    logger.info(f"Fetching profile for user_id={user_id[:8]}...")
    # TODO(db-team): Real implementation
    return {
        "country": "GT",
        "currency_preference": "GTQ",
        "locale": "es-GT"
    }


def get_user_categories(user_id: str) -> list[dict]:
    """
    Get user's expense categories.
    
    TODO(db-team): Implement actual DB query following backend/db.instructions.md
    
    Args:
        user_id: Authenticated user UUID from Supabase Auth
        
    Returns:
        List of category dicts with category_id, name, flow_type, is_default
    """
    logger.info(f"Fetching categories for user_id={user_id[:8]}...")
    # TODO(db-team): Real implementation
    return [
        {
            "category_id": "default-general-uuid",
            "name": "General",
            "flow_type": "outcome",
            "is_default": True
        },
        {
            "category_id": "cat-supermercado-uuid",
            "name": "Supermercado",
            "flow_type": "outcome",
            "is_default": False
        }
    ]


# ============================================================================
# Function Declarations for Gemini
# ============================================================================

# Define the tools that the agent can call
fetch_declaration = {
    "name": "fetch",
    "description": "Retrieve the latest ADK runtime / tool invocation spec",
    "parameters": {
        "type": "object",
        "properties": {},
        "required": []
    }
}

get_user_profile_declaration = {
    "name": "getUserProfile",
    "description": "Get user's profile context (country, currency_preference, locale) for localization",
    "parameters": {
        "type": "object",
        "properties": {
            "user_id": {
                "type": "string",
                "description": "Authenticated user UUID (provided by backend, never from client)"
            }
        },
        "required": ["user_id"]
    }
}

get_user_categories_declaration = {
    "name": "getUserCategories",
    "description": "Get user's expense categories to build category_suggestion",
    "parameters": {
        "type": "object",
        "properties": {
            "user_id": {
                "type": "string",
                "description": "Authenticated user UUID (provided by backend, never from client)"
            }
        },
        "required": ["user_id"]
    }
}


# ============================================================================
# Agent Runner
# ============================================================================

def run_invoice_agent(
    user_id: str,
    receipt_image_id: str,
    receipt_image_base64: Optional[str] = None,
    ocr_text: Optional[str] = None,
    country: str = "GT",
    currency_preference: str = "GTQ"
) -> InvoiceAgentOutput:
    """
    Process an invoice/receipt image and extract structured data.
    
    This is the main entry point for the InvoiceAgent. It orchestrates the
    interaction with Gemini, manages tool calls, and returns structured output.
    
    Args:
        user_id: Authenticated user UUID from Supabase Auth (NEVER from client)
        receipt_image_id: Reference to uploaded image in storage
        receipt_image_base64: Optional base64-encoded image data
        ocr_text: Optional pre-extracted OCR text
        country: User's country code (from getUserCountry or getUserProfile)
        currency_preference: User's preferred currency (from getUserProfile)
        
    Returns:
        InvoiceAgentOutput with status DRAFT, INVALID_IMAGE, or OUT_OF_SCOPE
        
    Security:
        - Assumes backend has validated Supabase token and resolved user_id
        - Does NOT log full invoice images or sensitive financial data
        - Does NOT write to database (persistence handled by API layer)
    """
    logger.info(f"InvoiceAgent invoked for receipt_id={receipt_image_id}")
    
    # TODO: Replace with actual Gemini API integration
    # For now, return a mock response structure
    
    # In production, this would:
    # 1. Initialize Gemini client with API key
    # 2. Configure tools with function declarations
    # 3. Send system prompt + user prompt + image/OCR data
    # 4. Handle tool calls (fetch, getUserProfile, getUserCategories)
    # 5. Extract and validate the final JSON response
    
    # Mock response for now (status: DRAFT)
    mock_output: InvoiceAgentOutput = {
        "status": "DRAFT",
        "store_name": "Super Despensa Familiar Zona 11",
        "transaction_time": "2025-11-01T14:30:00Z",
        "total_amount": 142.50,
        "currency": "GTQ",
        "purchased_items": [
            {
                "description": "Arroz Blanco 1kg",
                "quantity": 2.0,
                "unit_price": 8.50,
                "line_total": 17.00
            },
            {
                "description": "Frijol Negro 1lb",
                "quantity": 3.0,
                "unit_price": 6.00,
                "line_total": 18.00
            },
            {
                "description": "Aceite de Cocina 750ml",
                "quantity": 1.0,
                "unit_price": 25.50,
                "line_total": 25.50
            }
        ],
        "category_suggestion": {
            "match_type": "EXISTING",
            "category_id": "cat-supermercado-uuid",
            "category_name": "Supermercado",
            "proposed_name": None
        },
        "extracted_text": f"""Store Name: Super Despensa Familiar Zona 11
Transaction Time: 2025-11-01T14:30:00Z
Total Amount: 142.50
Currency: GTQ
Purchased Items:
- Arroz Blanco 1kg (qty: 2, unit: Q8.50, total: Q17.00)
- Frijol Negro 1lb (qty: 3, unit: Q6.00, total: Q18.00)
- Aceite de Cocina 750ml (qty: 1, unit: Q25.50, total: Q25.50)
Receipt Image ID: {receipt_image_id}""",
        "reason": None
    }
    
    logger.info(f"InvoiceAgent completed: status={mock_output['status']}, store={mock_output.get('store_name', 'N/A')}")
    
    return mock_output


# ============================================================================
# ADK Input/Output Schemas (for API/runtime integration)
# ============================================================================

# These schemas mirror the TypedDict definitions above and can be used
# by the FastAPI layer or ADK runtime for validation

INPUT_SCHEMA = {
    "type": "object",
    "properties": {
        "user_id": {
            "type": "string",
            "description": "Authenticated user UUID from Supabase Auth (never from client)"
        },
        "receipt_image_id": {
            "type": "string",
            "description": "Reference to uploaded image in storage"
        },
        "receipt_image_base64": {
            "type": "string",
            "description": "Optional base64-encoded image data"
        },
        "ocr_text": {
            "type": "string",
            "description": "Optional pre-extracted OCR text"
        },
        "country": {
            "type": "string",
            "description": "User's country code (e.g., 'GT')"
        },
        "currency_preference": {
            "type": "string",
            "description": "User's preferred currency (e.g., 'GTQ')"
        }
    },
    "required": ["user_id", "receipt_image_id", "country", "currency_preference"]
}

OUTPUT_SCHEMA = {
    "type": "object",
    "properties": {
        "status": {
            "type": "string",
            "enum": ["DRAFT", "INVALID_IMAGE", "OUT_OF_SCOPE"],
            "description": "Processing status"
        },
        "store_name": {
            "type": "string",
            "description": "Merchant/store name (present if status=DRAFT)"
        },
        "transaction_time": {
            "type": "string",
            "description": "ISO-8601 datetime string (present if status=DRAFT)"
        },
        "total_amount": {
            "type": "number",
            "description": "Total invoice amount (present if status=DRAFT)"
        },
        "currency": {
            "type": "string",
            "description": "Currency code or symbol (present if status=DRAFT)"
        },
        "purchased_items": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "description": {"type": "string"},
                    "quantity": {"type": "number"},
                    "unit_price": {"type": "number"},
                    "line_total": {"type": "number"}
                },
                "required": ["description", "quantity", "line_total"]
            },
            "description": "List of purchased items (present if status=DRAFT)"
        },
        "category_suggestion": {
            "type": "object",
            "properties": {
                "match_type": {
                    "type": "string",
                    "enum": ["EXISTING", "NEW_PROPOSED"]
                },
                "category_id": {"type": "string"},
                "category_name": {"type": "string"},
                "proposed_name": {"type": "string"}
            },
            "required": ["match_type"],
            "description": "Category assignment suggestion (present if status=DRAFT)"
        },
        "extracted_text": {
            "type": "string",
            "description": "Canonical multi-line snapshot for DB storage (present if status=DRAFT)"
        },
        "reason": {
            "type": "string",
            "description": "Short factual explanation (present if status!=DRAFT)"
        }
    },
    "required": ["status"]
}
