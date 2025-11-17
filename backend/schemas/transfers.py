"""
Pydantic schemas for transfer endpoints (normal and recurring).

Transfers are special transactions that move money between two accounts
owned by the same user. They are represented as paired transaction records.
"""

from typing import List, Literal, Optional
from pydantic import BaseModel, Field, field_validator

# Import TransactionDetailResponse for reuse
from backend.schemas.transactions import TransactionDetailResponse
# Import RecurringTransactionResponse for reuse
from backend.schemas.recurring_transactions import RecurringTransactionResponse


# --- Normal Transfer Schemas ---

class TransferCreateRequest(BaseModel):
    """
    Request for creating a one-time internal transfer between accounts.
    
    Creates two paired transactions:
    - One outcome from source account
    - One income to destination account
    """
    from_account_id: str = Field(..., description="Source account UUID (money leaves)")
    to_account_id: str = Field(..., description="Destination account UUID (money enters)")
    amount: float = Field(..., description="Amount to transfer", gt=0)
    date: str = Field(..., description="Transfer date (ISO-8601 format)")
    description: Optional[str] = Field(
        None,
        description="Optional description for both transactions"
    )
    
    @field_validator("description")
    @classmethod
    def validate_description_not_empty_if_provided(cls, v: Optional[str]) -> Optional[str]:
        """Ensure description is not just whitespace if provided."""
        if v is not None and v.strip() == "":
            return None
        return v


class TransferCreateResponse(BaseModel):
    """
    Response after creating a transfer.
    
    Returns the two paired transaction records created (outcome and income).
    Frontend can treat these as regular transactions in their displays.
    """
    status: Literal["CREATED"] = "CREATED"
    transactions: List[TransactionDetailResponse] = Field(
        ...,
        description="Array of two transactions: [0] = outcome from source, [1] = income to destination"
    )
    message: str = Field(..., description="Success message")


class TransferUpdateRequest(BaseModel):
    """
    Request for updating a transfer.
    
    Updates both paired transactions atomically with the same values.
    Only amount, date, and description can be updated.
    All other fields (category, flow_type, accounts) are immutable.
    """
    amount: Optional[float] = Field(None, description="New amount (must be > 0)", gt=0)
    date: Optional[str] = Field(None, description="New date (ISO-8601 format)")
    description: Optional[str] = Field(None, description="New description for both transactions")
    
    @field_validator("description")
    @classmethod
    def validate_description_not_empty_if_provided(cls, v: Optional[str]) -> Optional[str]:
        """Ensure description is not just whitespace if provided."""
        if v is not None and v.strip() == "":
            return None
        return v


class TransferUpdateResponse(BaseModel):
    """
    Response after updating a transfer.
    
    Returns both updated transaction records to maintain consistency.
    """
    status: Literal["UPDATED"] = "UPDATED"
    transactions: List[TransactionDetailResponse] = Field(
        ...,
        description="Array of two updated transactions: [0] = outcome, [1] = income"
    )
    message: str = Field(..., description="Success message")


class TransferDeleteResponse(BaseModel):
    """Response after deleting a transfer."""
    status: Literal["DELETED"] = "DELETED"
    transaction_id: str = Field(..., description="UUID of the deleted transaction")
    paired_transaction_id: str = Field(..., description="UUID of the paired deleted transaction")
    message: str = Field(..., description="Success message")




# --- Recurring Transfer Schemas ---

RecurringFrequency = Literal["daily", "weekly", "monthly", "yearly"]


class RecurringTransferCreateRequest(BaseModel):
    """
    Request for creating a recurring internal transfer.
    
    Creates two paired recurring_transaction rules:
    - One outcome template for source account
    - One income template for destination account
    """
    from_account_id: str = Field(..., description="Source account UUID")
    to_account_id: str = Field(..., description="Destination account UUID")
    amount: float = Field(..., description="Amount to transfer each occurrence", gt=0)
    description_outgoing: Optional[str] = Field(
        None,
        description="Description for outgoing side (if NULL, uses generic 'Transfer out')"
    )
    description_incoming: Optional[str] = Field(
        None,
        description="Description for incoming side (if NULL, uses generic 'Transfer in')"
    )
    frequency: RecurringFrequency = Field(..., description="daily/weekly/monthly/yearly")
    interval: int = Field(1, description="Repeat every N units of frequency", ge=1)
    by_weekday: Optional[List[str]] = Field(
        None,
        description="Required for weekly: weekday names (lowercase)"
    )
    by_monthday: Optional[List[int]] = Field(
        None,
        description="Required for monthly: day numbers (1-31)"
    )
    start_date: str = Field(..., description="Start date (YYYY-MM-DD)")
    end_date: Optional[str] = Field(None, description="End date (YYYY-MM-DD) or NULL for indefinite")
    is_active: bool = Field(True, description="Active by default")
    
    @field_validator("by_weekday")
    @classmethod
    def validate_weekdays(cls, v: Optional[List[str]]) -> Optional[List[str]]:
        """Validate weekday names for weekly frequency."""
        if v is None:
            return v
        
        valid_weekdays = {"monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday"}
        for day in v:
            if day.lower() not in valid_weekdays:
                raise ValueError(f"Invalid weekday: {day}. Must be one of {valid_weekdays}")
        
        return [d.lower() for d in v]
    
    @field_validator("by_monthday")
    @classmethod
    def validate_monthdays(cls, v: Optional[List[int]]) -> Optional[List[int]]:
        """Validate month day numbers for monthly frequency."""
        if v is None:
            return v
        
        for day in v:
            if day < 1 or day > 31:
                raise ValueError(f"Invalid monthday: {day}. Must be between 1 and 31")
        
        return v


class RecurringTransferCreateResponse(BaseModel):
    """
    Response after creating a recurring transfer.
    
    Returns the two paired recurring_transaction records created 
    (outcome and income rules). Frontend can use the same schema as regular recurring transactions.
    """
    status: Literal["CREATED"] = "CREATED"
    recurring_transactions: List[RecurringTransactionResponse] = Field(
        ...,
        description="Array of two recurring transaction rules: [0] = outcome from source, [1] = income to destination"
    )
    message: str = Field(..., description="Success message")


class RecurringTransferDeleteResponse(BaseModel):
    """Response after deleting a recurring transfer."""
    status: Literal["DELETED"] = "DELETED"
    outgoing_rule_id: str = Field(..., description="UUID of deleted outgoing rule")
    incoming_rule_id: str = Field(..., description="UUID of deleted incoming rule")
    message: str = Field(..., description="Success message")
