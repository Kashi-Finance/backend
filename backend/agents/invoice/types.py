"""
InvoiceAgent Type Definitions

Strictly typed input/output contracts for InvoiceAgent.
All types are JSON-serializable and compatible with Pydantic.
"""

from typing import TypedDict, Literal, Optional


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
