"""
Pydantic schemas for recurring_transaction CRUD endpoints.

Defines request/response models for managing recurring transaction rules
that automatically generate transactions based on schedules.
"""

from typing import List, Literal, Optional

from pydantic import BaseModel, Field, field_validator

# Type aliases matching DB enums
RecurringFrequency = Literal["daily", "weekly", "monthly", "yearly"]
FlowType = Literal["income", "outcome"]


class RecurringTransactionResponse(BaseModel):
    """
    Complete recurring transaction rule representation.

    Returned by GET endpoints and after create/update operations.
    """
    id: str = Field(..., description="Recurring transaction UUID")
    user_id: str = Field(..., description="Owner user UUID")
    account_id: str = Field(..., description="Account UUID that will receive/pay")
    category_id: str = Field(..., description="Category UUID for generated transactions")
    flow_type: FlowType = Field(..., description="Direction: income or outcome")
    amount: float = Field(..., description="Amount to insert each occurrence", gt=0)
    description: str = Field(..., description="Text for transaction description")
    paired_recurring_transaction_id: Optional[str] = Field(
        None,
        description="UUID of paired recurring rule for internal transfers"
    )
    frequency: RecurringFrequency = Field(..., description="Base recurrence cadence")
    interval: int = Field(..., description="How often it repeats (must be >= 1)", ge=1)
    by_weekday: Optional[List[str]] = Field(
        None,
        description="Specific weekdays (e.g. ['monday', 'friday']) for weekly frequency"
    )
    by_monthday: Optional[List[int]] = Field(
        None,
        description="Specific month days (1-31) for monthly frequency"
    )
    start_date: str = Field(..., description="When this rule becomes valid (DATE format)")
    next_run_date: str = Field(..., description="Next date to materialize a transaction (DATE format)")
    end_date: Optional[str] = Field(None, description="Stop date (DATE format), NULL = indefinite")
    is_active: bool = Field(..., description="Whether the rule generates transactions")
    created_at: str = Field(..., description="Creation timestamp (ISO-8601)")
    updated_at: str = Field(..., description="Last update timestamp (ISO-8601)")


class RecurringTransactionListResponse(BaseModel):
    """Paginated list of recurring transaction rules."""
    recurring_transactions: List[RecurringTransactionResponse]
    count: int = Field(..., description="Total number of rules returned")


class RecurringTransactionCreateRequest(BaseModel):
    """
    Request body for creating a new recurring transaction rule.

    All fields are required except paired_recurring_transaction_id, by_weekday,
    by_monthday, and end_date.
    """
    account_id: str = Field(..., description="Account UUID")
    category_id: str = Field(..., description="Category UUID")
    flow_type: FlowType = Field(..., description="income or outcome")
    amount: float = Field(..., description="Amount per occurrence", gt=0)
    description: str = Field(..., description="Transaction description", min_length=1)
    paired_recurring_transaction_id: Optional[str] = Field(
        None,
        description="UUID of paired rule for transfers (optional)"
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
    end_date: Optional[str] = Field(None, description="End date (YYYY-MM-DD) or NULL")
    is_active: bool = Field(True, description="Active by default")

    @field_validator("by_weekday")
    @classmethod
    def validate_weekdays(cls, v: Optional[List[str]], info) -> Optional[List[str]]:
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


class RecurringTransactionCreateResponse(BaseModel):
    """Response after creating a recurring transaction rule."""
    status: Literal["CREATED"] = "CREATED"
    recurring_transaction: RecurringTransactionResponse
    message: str = Field(..., description="Success message")


class RecurringTransactionUpdateRequest(BaseModel):
    """
    Request body for partially updating a recurring transaction rule.

    All fields are optional. Only provided fields will be updated.
    Special semantics apply to start_date and is_active changes (see domain rules).
    """
    account_id: Optional[str] = Field(None, description="Account UUID")
    category_id: Optional[str] = Field(None, description="Category UUID")
    flow_type: Optional[FlowType] = Field(None, description="income or outcome")
    amount: Optional[float] = Field(None, description="Amount per occurrence", gt=0)
    description: Optional[str] = Field(None, description="Transaction description", min_length=1)
    paired_recurring_transaction_id: Optional[str] = Field(
        None,
        description="UUID of paired rule (can be set to NULL)"
    )
    frequency: Optional[RecurringFrequency] = Field(None, description="daily/weekly/monthly/yearly")
    interval: Optional[int] = Field(None, description="Repeat every N units", ge=1)
    by_weekday: Optional[List[str]] = Field(None, description="Weekday names for weekly")
    by_monthday: Optional[List[int]] = Field(None, description="Day numbers for monthly")
    start_date: Optional[str] = Field(None, description="Start date (YYYY-MM-DD)")
    next_run_date: Optional[str] = Field(None, description="Next run date (YYYY-MM-DD)")
    end_date: Optional[str] = Field(None, description="End date or NULL")
    is_active: Optional[bool] = Field(None, description="Enable/disable rule")
    apply_retroactive_change: bool = Field(
        False,
        description="If true and start_date changed, delete past generated transactions"
    )

    @field_validator("by_weekday")
    @classmethod
    def validate_weekdays(cls, v: Optional[List[str]]) -> Optional[List[str]]:
        """Validate weekday names."""
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
        """Validate month day numbers."""
        if v is None:
            return v

        for day in v:
            if day < 1 or day > 31:
                raise ValueError(f"Invalid monthday: {day}. Must be between 1 and 31")

        return v


class RecurringTransactionUpdateResponse(BaseModel):
    """Response after updating a recurring transaction rule."""
    status: Literal["UPDATED"] = "UPDATED"
    recurring_transaction: RecurringTransactionResponse
    retroactive_deletes: int = Field(
        0,
        description="Number of past transactions deleted (if apply_retroactive_change=true)"
    )
    message: str = Field(..., description="Success message")


class RecurringTransactionDeleteResponse(BaseModel):
    """Response after deleting a recurring transaction rule."""
    status: Literal["DELETED"] = "DELETED"
    recurring_transaction_id: str = Field(..., description="UUID of deleted rule")
    paired_rule_deleted: bool = Field(
        False,
        description="Whether a paired rule was also deleted"
    )
    message: str = Field(..., description="Success message")


class SyncRecurringTransactionsRequest(BaseModel):
    """
    Optional request body for sync endpoint.

    Currently no fields required, but allows for future expansion
    (e.g., preview mode, max occurrences limit).
    """
    preview_mode: bool = Field(
        False,
        description="If true, return count without actually creating transactions (future)"
    )
    max_occurrences: Optional[int] = Field(
        None,
        description="Maximum transactions to generate per sync (future safeguard)",
        ge=1
    )


class SyncRecurringTransactionsResponse(BaseModel):
    """
    Response from sync endpoint.

    Returns summary of transactions generated and caches updated.
    The sync operation is atomic and handles:
    - Paired recurring transfers (linked via paired_transaction_id)
    - Account balance updates
    - Budget consumption updates (outcome transactions only)
    """
    status: Literal["SYNCED"] = "SYNCED"
    transactions_generated: int = Field(..., description="Total transactions created")
    rules_processed: int = Field(..., description="Number of recurring rules processed")
    accounts_updated: int = Field(
        default=0,
        description="Number of accounts whose cached_balance was recomputed"
    )
    budgets_updated: int = Field(
        default=0,
        description="Number of budgets whose cached_consumption was recomputed (outcome only)"
    )
    message: str = Field(..., description="Success message")

