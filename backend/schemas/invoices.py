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
    
    The frontend sends the edited/confirmed data from the DRAFT response,
    along with the account and category selected by the user.
    
    When committed, this will:
    - Create an invoice record
    - Create a linked transaction record with the invoice_id reference
    """
    store_name: str = Field(..., description="Merchant/store name")
    transaction_time: str = Field(..., description="ISO-8601 datetime of purchase")
    total_amount: str = Field(..., description="Total amount as string (e.g., '128.50')")
    currency: str = Field(..., description="Currency code (e.g., 'GTQ')")
    purchased_items: str = Field(
        ...,
        description="Formatted multi-line list of purchased items"
    )
    storage_path: str = Field(
        ...,
        description="Path to receipt image in Supabase Storage"
    )
    account_id: str = Field(
        ...,
        description="UUID of the account this transaction belongs to (user-selected)"
    )
    category_id: str = Field(
        ...,
        description="UUID of the expense category (user-selected or from suggestion)"
    )


class InvoiceCommitResponse(BaseModel):
    """
    Response after successfully persisting an invoice and creating linked transaction.
    
    Returns both the invoice ID and the automatically created transaction ID.
    """
    status: Literal["COMMITTED"] = Field(
        "COMMITTED",
        description="Indicates the invoice was successfully saved"
    )
    invoice_id: str = Field(..., description="UUID of created invoice record")
    transaction_id: str = Field(..., description="UUID of linked transaction record")
    message: str = Field(
        ...,
        description="Success message",
        examples=["Invoice and transaction saved successfully"]
    )


# --- Retrieval endpoint models ---

class InvoiceDetailResponse(BaseModel):
    """
    Response for GET /invoices/{invoice_id} - Single invoice details.
    """
    id: str = Field(..., description="Invoice UUID")
    user_id: str = Field(..., description="Owner user UUID")
    storage_path: str = Field(..., description="Path to receipt image in Supabase Storage")
    extracted_text: str = Field(..., description="Canonical formatted invoice data")
    created_at: str = Field(..., description="ISO-8601 timestamp when invoice was created")
    updated_at: Optional[str] = Field(None, description="ISO-8601 timestamp of last update")


class InvoiceListResponse(BaseModel):
    """
    Response for GET /invoices - List of user's invoices.
    """
    invoices: List[InvoiceDetailResponse] = Field(..., description="List of invoice records")
    count: int = Field(..., description="Total number of invoices returned")
    limit: int = Field(..., description="Limit used for pagination")
    offset: int = Field(..., description="Offset used for pagination")


# --- Update endpoint models ---

class InvoiceUpdateRequest(BaseModel):
    """
    Request to update an existing invoice.
    
    All fields are optional - only provided fields will be updated.
    The extracted_text will be automatically rebuilt in the canonical format.
    """
    store_name: Optional[str] = Field(
        None,
        description="Updated merchant/store name"
    )
    transaction_time: Optional[str] = Field(
        None,
        description="Updated ISO-8601 datetime of purchase"
    )
    total_amount: Optional[str] = Field(
        None,
        description="Updated total amount as string (e.g., '128.50')"
    )
    currency: Optional[str] = Field(
        None,
        description="Updated currency code (e.g., 'GTQ')"
    )
    purchased_items: Optional[str] = Field(
        None,
        description="Updated formatted multi-line list of purchased items"
    )
    storage_path: Optional[str] = Field(
        None,
        description="Updated path to receipt image in Supabase Storage"
    )


class InvoiceUpdateResponse(BaseModel):
    """
    Response after successfully updating an invoice.
    """
    status: Literal["UPDATED"] = Field(
        "UPDATED",
        description="Indicates the invoice was successfully updated"
    )
    invoice_id: str = Field(..., description="UUID of updated invoice record")
    invoice: InvoiceDetailResponse = Field(
        ...,
        description="Complete updated invoice details"
    )
    message: str = Field(
        ...,
        description="Success message",
        examples=["Invoice updated successfully"]
    )


# --- Delete endpoint models ---

class InvoiceDeleteResponse(BaseModel):
    """
    Response after successfully deleting an invoice.
    """
    status: Literal["DELETED"] = Field(
        "DELETED",
        description="Indicates the invoice was successfully deleted"
    )
    invoice_id: str = Field(..., description="UUID of deleted invoice record")
    message: str = Field(
        ...,
        description="Success message",
        examples=["Invoice deleted successfully"]
    )
