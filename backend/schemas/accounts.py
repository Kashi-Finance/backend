"""
Pydantic schemas for account CRUD endpoints.

These models define the strict request/response contracts for account management.
Accounts are financial containers (cash, bank, credit card, etc.) that track balances
via transaction history.
"""

from typing import Optional, Literal
from pydantic import BaseModel, Field


# Account type enum (matches DB CHECK constraint)
AccountType = Literal[
    "cash",
    "bank", 
    "credit_card",
    "loan",
    "remittance",
    "crypto",
    "investment"
]


# --- Account response models ---

class AccountResponse(BaseModel):
    """
    Response for account details.
    
    Contains all account fields. Balance is computed from transactions,
    not stored directly.
    """
    id: str = Field(..., description="Account UUID")
    user_id: str = Field(..., description="Owner user UUID (from auth.users)")
    name: str = Field(..., description="Human-readable account name")
    type: AccountType = Field(..., description="Kind of financial container")
    currency: str = Field(..., description="ISO currency code (e.g. 'GTQ')")
    created_at: str = Field(..., description="ISO-8601 timestamp when created")
    updated_at: str = Field(..., description="ISO-8601 timestamp of last update")


# --- Account create models ---

class AccountCreateRequest(BaseModel):
    """
    Request to create a new account.
    
    All fields are required except those with defaults.
    """
    name: str = Field(
        ...,
        description="Human-readable account name",
        min_length=1,
        max_length=200,
        examples=["Banco Industrial Checking Account", "Wallet Cash"]
    )
    type: AccountType = Field(
        ...,
        description="Account type",
        examples=["bank", "cash", "credit_card"]
    )
    currency: str = Field(
        ...,
        description="ISO currency code",
        min_length=3,
        max_length=3,
        examples=["GTQ", "USD", "EUR"]
    )
    initial_balance: Optional[float] = Field(
        None,
        description="Optional initial balance for the account. "
                    "If provided, creates an income transaction with system_generated_key='initial_balance'",
        ge=0,
        examples=[1000.00, 500.50, 0.00]
    )
    initial_balance_category_id: Optional[str] = Field(
        None,
        description="Category UUID for initial balance transaction. "
                    "Required if initial_balance is provided",
        examples=["uuid-of-category"]
    )


class AccountCreateResponse(BaseModel):
    """
    Response after successfully creating an account.
    """
    status: str = Field("CREATED", description="Indicates successful creation")
    account: AccountResponse = Field(..., description="The created account")
    message: str = Field(
        ...,
        description="Success message",
        examples=["Account created successfully"]
    )


# --- Account update models ---

class AccountUpdateRequest(BaseModel):
    """
    Request to update an account.
    
    All fields are optional - only provided fields will be updated.
    At least one field must be provided.
    """
    name: Optional[str] = Field(
        None,
        description="Updated account name",
        min_length=1,
        max_length=200
    )
    type: Optional[AccountType] = Field(
        None,
        description="Updated account type"
    )
    currency: Optional[str] = Field(
        None,
        description="Updated currency code",
        min_length=3,
        max_length=3
    )


class AccountUpdateResponse(BaseModel):
    """
    Response after successfully updating an account.
    """
    status: str = Field("UPDATED", description="Indicates successful update")
    account: AccountResponse = Field(..., description="The updated account")
    message: str = Field(
        ...,
        description="Success message",
        examples=["Account updated successfully"]
    )


# --- Account delete models ---

class AccountDeleteRequest(BaseModel):
    """
    Request to delete an account.
    
    Must specify deletion strategy per DB delete rule.
    """
    strategy: Literal["reassign", "delete_transactions"] = Field(
        ...,
        description=(
            "Deletion strategy:\n"
            "- 'reassign': Move all transactions to target_account_id, then delete\n"
            "- 'delete_transactions': Delete all transactions, then delete account"
        )
    )
    # Present in the request body for all strategies. When strategy='delete_transactions'
    # this field must be explicitly null. When strategy='reassign' this must be
    # a non-null UUID belonging to the same user.
    target_account_id: Optional[str] = Field(
        ...,
        description=(
            "UUID of the account to receive reassigned transactions when strategy='reassign'.\n"
            "For strategy='delete_transactions' this field must be explicitly null.\n"
            "Must belong to the same user when non-null."
        )
    )


class AccountDeleteResponse(BaseModel):
    """
    Response after successfully deleting an account.
    """
    status: str = Field("DELETED", description="Indicates successful deletion")
    message: str = Field(
        ...,
        description="Success message with deletion details",
        examples=[
            "Account deleted successfully. 15 transactions reassigned.",
            "Account deleted successfully. 8 transactions deleted."
        ]
    )
    transactions_affected: int = Field(
        ...,
        description="Number of transactions reassigned or deleted"
    )


# --- Account list response ---

class AccountListResponse(BaseModel):
    """
    Response for listing user accounts.
    """
    accounts: list[AccountResponse] = Field(
        ...,
        description="List of user's accounts"
    )
    count: int = Field(..., description="Total number of accounts returned")
    limit: int = Field(..., description="Maximum number of accounts requested")
    offset: int = Field(..., description="Number of accounts skipped (pagination offset)")
