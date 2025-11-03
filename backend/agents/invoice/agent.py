"""
InvoiceAgent Runner

Main agent execution logic. Orchestrates interaction with Gemini,
manages tool calls, and returns structured output.
"""

import logging
from typing import Optional

from backend.agents.invoice.types import InvoiceAgentOutput

logger = logging.getLogger(__name__)


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
        "transaction_time": "2025-11-02T14:30:00Z",
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
Transaction Time: 2025-11-02T14:30:00Z
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
