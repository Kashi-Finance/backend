"""
Pydantic schemas for transaction CRUD endpoints.

These models define the strict request/response contracts for transaction management.
Transactions represent individual money movements (income or outcome) tied to accounts and categories.
"""

from typing import List, Literal, Optional

from pydantic import BaseModel, Field

# --- Transaction creation models ---

class TransactionCreateRequest(BaseModel):
    """
    Request to create a new transaction manually.

    Used when user manually records a transaction (not from invoice OCR).
    All required fields must be provided by the user.
    """
    account_id: str = Field(..., description="UUID of the account affected by this transaction")
    category_id: str = Field(..., description="UUID of the spending/earning category")
    flow_type: Literal["income", "outcome"] = Field(
        ...,
        description="Money direction: 'income' (money in) or 'outcome' (money out)"
    )
    amount: float = Field(
        ...,
        description="Transaction amount (must be >= 0)",
        ge=0.0,
        examples=[128.50, 1500.00]
    )
    date: str = Field(
        ...,
        description="ISO-8601 datetime when the transaction occurred",
        examples=["2025-10-30T14:32:00-06:00"]
    )
    description: Optional[str] = Field(
        None,
        description="Human-readable description/note for this transaction",
        examples=["Grocery shopping at Super Despensa"]
    )


# --- Transaction update models ---

class TransactionUpdateRequest(BaseModel):
    """
    Request to update an existing transaction.

    All fields are optional - only provided fields will be updated.
    """
    account_id: Optional[str] = Field(
        None,
        description="Updated account UUID"
    )
    category_id: Optional[str] = Field(
        None,
        description="Updated category UUID"
    )
    flow_type: Optional[Literal["income", "outcome"]] = Field(
        None,
        description="Updated money direction"
    )
    amount: Optional[float] = Field(
        None,
        description="Updated transaction amount (must be >= 0)",
        ge=0.0
    )
    date: Optional[str] = Field(
        None,
        description="Updated ISO-8601 datetime"
    )
    description: Optional[str] = Field(
        None,
        description="Updated description/note"
    )


# --- Transaction response models ---

class TransactionDetailResponse(BaseModel):
    """
    Response for GET /transactions/{transaction_id} - Single transaction details.

    Includes all transaction fields plus convenience fields for display.
    """
    id: str = Field(..., description="Transaction UUID")
    user_id: str = Field(..., description="Owner user UUID")
    account_id: str = Field(..., description="Account UUID")
    category_id: str = Field(..., description="Category UUID")
    invoice_id: Optional[str] = Field(None, description="Linked invoice UUID (if created from OCR)")
    flow_type: Literal["income", "outcome"] = Field(..., description="Money direction")
    amount: float = Field(..., description="Transaction amount")
    date: str = Field(..., description="ISO-8601 datetime when transaction occurred")
    description: Optional[str] = Field(None, description="Transaction description/note")
    embedding: Optional[list] = Field(None, description="Semantic vector (pgvector) for AI similarity search")
    paired_transaction_id: Optional[str] = Field(
        None,
        description="UUID of paired transaction if this is part of an internal transfer"
    )
    created_at: str = Field(..., description="ISO-8601 timestamp when record was created")
    updated_at: Optional[str] = Field(None, description="ISO-8601 timestamp of last update")


class TransactionListResponse(BaseModel):
    """
    Response for GET /transactions - List of user's transactions.

    Supports pagination and filtering.
    """
    transactions: List[TransactionDetailResponse] = Field(..., description="List of transaction records")
    count: int = Field(..., description="Total number of transactions returned")
    limit: int = Field(..., description="Limit used for pagination")
    offset: int = Field(..., description="Offset used for pagination")


# --- Transaction creation response ---

class TransactionCreateResponse(BaseModel):
    """
    Response after successfully creating a transaction.
    """
    status: Literal["CREATED"] = Field(
        "CREATED",
        description="Indicates the transaction was successfully created"
    )
    transaction_id: str = Field(..., description="UUID of created transaction record")
    transaction: TransactionDetailResponse = Field(
        ...,
        description="Complete transaction details"
    )
    message: str = Field(
        ...,
        description="Success message",
        examples=["Transaction created successfully"]
    )


# --- Transaction update response ---

class TransactionUpdateResponse(BaseModel):
    """
    Response after successfully updating a transaction.
    """
    status: Literal["UPDATED"] = Field(
        "UPDATED",
        description="Indicates the transaction was successfully updated"
    )
    transaction_id: str = Field(..., description="UUID of updated transaction record")
    transaction: TransactionDetailResponse = Field(
        ...,
        description="Complete updated transaction details"
    )
    message: str = Field(
        ...,
        description="Success message",
        examples=["Transaction updated successfully"]
    )


# --- Transaction delete response ---

class TransactionDeleteResponse(BaseModel):
    """
    Response after successfully deleting a transaction.
    """
    status: Literal["DELETED"] = Field(
        "DELETED",
        description="Indicates the transaction was successfully deleted"
    )
    transaction_id: str = Field(..., description="UUID of deleted transaction record")
    message: str = Field(
        ...,
        description="Success message",
        examples=["Transaction deleted successfully"]
    )
