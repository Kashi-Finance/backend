"""
Pydantic schemas for invoice OCR endpoints.

These models define the strict request/response contracts for invoice processing.
"""

from typing import List, Literal, Optional
from pydantic import BaseModel, Field


# --- Item models ---

class PurchasedItemResponse(BaseModel):
    """
    A single item from a parsed receipt.
    
    Maps to InvoiceAgent's PurchasedItem output.
    """
    description: str = Field(..., description="Item description (e.g., 'Leche deslactosada 1L')")
    quantity: float = Field(..., description="Quantity purchased")
    unit_price: Optional[float] = Field(None, description="Price per unit (optional)")
    total_price: float = Field(..., description="Total line price for this item")


# --- Category suggestion models ---

class CategorySuggestionResponse(BaseModel):
    """
    Category assignment suggestion from InvoiceAgent.
    
    Either matches an existing category or proposes a new one.
    """
    match_type: Literal["EXISTING", "NEW_PROPOSED"] = Field(
        ...,
        description="Whether agent matched to an existing user category or proposes a new name"
    )
    category_id: Optional[str] = Field(
        None,
        description="UUID of matched category (only if match_type=EXISTING)"
    )
    category_name: str = Field(
        ...,
        description="Name of category (existing or proposed)"
    )


# --- Response models ---

class InvoiceOCRResponseInvalid(BaseModel):
    """
    Response when uploaded image cannot be processed.
    
    This is returned when:
    - Image is not a receipt
    - Image is unreadable (too blurry, damaged, etc.)
    - Required fields (store name, total) cannot be extracted
    """
    status: Literal["INVALID_IMAGE"] = Field(
        "INVALID_IMAGE",
        description="Indicates the image could not be processed"
    )
    reason: str = Field(
        ...,
        description="Human-readable explanation for why the image is invalid",
        examples=[
            "No pude leer datos suficientes para construir la transacción. Intenta otra foto donde se vea el total y el nombre del comercio."
        ]
    )


class InvoiceOCRResponseDraft(BaseModel):
    """
    Response when OCR successfully extracted invoice data.
    
    This is a PREVIEW ONLY - nothing is persisted to DB yet.
    Frontend should show this to user for editing/confirmation.
    User calls /invoices/commit to actually save the transaction.
    """
    status: Literal["DRAFT"] = Field(
        "DRAFT",
        description="Indicates successful extraction (not yet committed)"
    )
    store_name: str = Field(
        ...,
        description="Extracted merchant/store name",
        examples=["Super Despensa Familiar Zona 11"]
    )
    purchase_datetime: str = Field(
        ...,
        description="ISO-8601 datetime of purchase",
        examples=["2025-10-30T14:32:00-06:00"]
    )
    total_amount: float = Field(
        ...,
        description="Total amount from receipt",
        examples=[128.50]
    )
    currency: str = Field(
        ...,
        description="Currency code",
        examples=["GTQ", "USD"]
    )
    items: List[PurchasedItemResponse] = Field(
        ...,
        description="Individual line items parsed from receipt"
    )
    category_suggestion: CategorySuggestionResponse = Field(
        ...,
        description="Agent's suggestion for which category this purchase belongs to"
    )


# --- Union type for response ---

InvoiceOCRResponse = InvoiceOCRResponseDraft | InvoiceOCRResponseInvalid


# --- Commit endpoint models ---

class InvoiceCommitRequest(BaseModel):
    """
    Request to commit (persist) an invoice after OCR and user confirmation.
    
    The frontend sends the edited/confirmed data from the DRAFT response.
    """
    store_name: str = Field(..., description="Merchant/store name")
    transaction_time: str = Field(..., description="ISO-8601 datetime of purchase")
    total_amount: str = Field(..., description="Total amount as string (e.g., '128.50')")
    currency: str = Field(..., description="Currency code (e.g., 'GTQ')")
    purchased_items: str = Field(
        ...,
        description="Formatted multi-line list of purchased items"
    )
    nit: str = Field(..., description="NIT or taxpayer identification number")
    storage_path: str = Field(
        ...,
        description="Path to receipt image in Supabase Storage"
    )


class InvoiceCommitResponse(BaseModel):
    """
    Response after successfully persisting an invoice.
    """
    status: Literal["COMMITTED"] = Field(
        "COMMITTED",
        description="Indicates the invoice was successfully saved"
    )
    invoice_id: str = Field(..., description="UUID of created invoice record")
    message: str = Field(
        ...,
        description="Success message",
        examples=["Invoice saved successfully"]
    )
