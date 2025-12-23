"""
Pydantic schemas for invoice OCR endpoints.

These models define the strict request/response contracts for invoice processing.
"""

from typing import List, Literal, Optional

from pydantic import BaseModel, Field, model_validator

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

    INVARIANT: One of the following MUST be true:
    - match_type="EXISTING" AND category_id is not None AND category_name is not None AND proposed_name is None
    - match_type="NEW_PROPOSED" AND category_id is None AND category_name is None AND proposed_name is not None

    All four fields are ALWAYS present (never omitted).
    Fields that don't apply are explicitly set to null.

    This design:
    - Makes Flutter/frontend type-safe (no missing key checks)
    - Enables backend validation of invariants
    - Simplifies conditional rendering (check field nullability, not key existence)
    """
    match_type: Literal["EXISTING", "NEW_PROPOSED"] = Field(
        ...,
        description="Discriminator: whether matched to existing category or proposing new one"
    )
    category_id: Optional[str] = Field(
        None,
        description="UUID of matched category (non-null IF match_type=EXISTING)"
    )
    category_name: Optional[str] = Field(
        None,
        description="Name of matched category (non-null IF match_type=EXISTING)"
    )
    proposed_name: Optional[str] = Field(
        None,
        description="Suggested name for new category (non-null IF match_type=NEW_PROPOSED)"
    )

    @model_validator(mode="after")
    def validate_category_invariant(self):
        """
        Validate that category_suggestion invariant is maintained.

        INVARIANT:
        - If match_type="EXISTING": category_id and category_name must be non-None, proposed_name must be None
        - If match_type="NEW_PROPOSED": proposed_name must be non-None, category_id and category_name must be None
        """
        match_type = self.match_type
        category_id = self.category_id
        category_name = self.category_name
        proposed_name = self.proposed_name

        if match_type == "EXISTING":
            if category_id is None or category_name is None:
                raise ValueError(
                    "category_suggestion invariant violated: "
                    "match_type=EXISTING requires category_id and category_name to be non-null"
                )
            if proposed_name is not None:
                raise ValueError(
                    "category_suggestion invariant violated: "
                    "match_type=EXISTING requires proposed_name to be null"
                )
        elif match_type == "NEW_PROPOSED":
            if proposed_name is None:
                raise ValueError(
                    "category_suggestion invariant violated: "
                    "match_type=NEW_PROPOSED requires proposed_name to be non-null"
                )
            if category_id is not None or category_name is not None:
                raise ValueError(
                    "category_suggestion invariant violated: "
                    "match_type=NEW_PROPOSED requires category_id and category_name to be null"
                )

        return self


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
    transaction_time: str = Field(
        ...,
        description="ISO-8601 datetime of transaction",
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

    IMPORTANT: The image is sent as base64 because it was NOT uploaded during the
    OCR draft phase. The backend will upload it now during commit.

    When committed, this will:
    - Upload receipt image to Supabase Storage
    - Create an invoice record with the uploaded image reference
    - Create a linked transaction record with the invoice_id reference
    """
    store_name: str = Field(..., min_length=1, description="Merchant/store name")
    transaction_time: str = Field(..., min_length=1, description="ISO-8601 datetime of purchase")
    total_amount: float = Field(..., gt=0, description="Total amount as number (e.g., 128.50)")
    currency: str = Field(..., min_length=1, description="Currency code (e.g., 'GTQ')")
    purchased_items: str | List[str] = Field(
        ...,
        description="Formatted multi-line list of purchased items (string) OR array of item strings (will be joined)"
    )
    image_base64: str = Field(
        ...,
        min_length=10,
        description="Receipt image as base64 string (will be uploaded to storage)"
    )
    image_filename: str = Field(
        default="receipt.jpg",
        description="Original image filename for storage reference"
    )
    account_id: str = Field(
        ...,
        min_length=1,
        description="UUID of the account this transaction belongs to (user-selected)"
    )
    category_id: str = Field(
        ...,
        min_length=1,
        description="UUID of the expense category (user-selected or from suggestion)"
    )

    @model_validator(mode="after")
    def normalize_purchased_items(self):
        """
        Normalize purchased_items to always be a string.

        If frontend sends an array, join it with newlines.
        This provides backward compatibility while frontend migrates to string format.
        """
        if isinstance(self.purchased_items, list):
            self.purchased_items = "\n".join(self.purchased_items)
        return self

    # Pydantic v2 config: enable type coercion, strip whitespace, forbid extra fields
    model_config = {
        "str_strip_whitespace": True,
        "extra": "forbid"  # Reject requests with unexpected fields
    }


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




# --- Delete endpoint models ---

class InvoiceDeleteResponse(BaseModel):
    """
    Response after successfully soft-deleting an invoice.
    """
    status: Literal["DELETED"] = Field(
        "DELETED",
        description="Indicates the invoice was successfully soft-deleted"
    )
    invoice_id: str = Field(..., description="UUID of soft-deleted invoice record")
    deleted_at: str = Field(..., description="ISO-8601 timestamp when invoice was soft-deleted")
    message: str = Field(
        ...,
        description="Success message",
        examples=["Invoice soft-deleted successfully"]
    )
