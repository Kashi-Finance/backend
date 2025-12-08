"""
Pydantic schemas for account CRUD endpoints.

These models define the strict request/response contracts for account management.
Accounts are financial containers (cash, bank, credit card, etc.) that track balances
via transaction history.
"""

import re
from typing import Literal, Optional

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


def validate_hex_color(color: str) -> str:
    """Validate hex color format (#RRGGBB)."""
    if not re.match(r'^#[0-9A-Fa-f]{6}$', color):
        raise ValueError("Color must be a valid hex code (e.g., '#FF5733')")
    return color.upper()


# --- Account response models ---

class AccountResponse(BaseModel):
    """
    Response for account details.

    Contains all account fields including cached balance and display customization.
    """
    id: str = Field(..., description="Account UUID")
    user_id: str = Field(..., description="Owner user UUID (from auth.users)")
    name: str = Field(..., description="Human-readable account name")
    type: AccountType = Field(..., description="Kind of financial container")
    currency: str = Field(..., description="ISO currency code (e.g. 'GTQ')")
    icon: str = Field(..., description="Icon identifier for UI display (e.g., 'wallet', 'bank')")
    color: str = Field(..., description="Hex color code for UI display (e.g., '#FF5733')")
    is_favorite: bool = Field(..., description="If true, auto-selected for manual transaction creation")
    is_pinned: bool = Field(..., description="If true, appears at top of account list")
    description: Optional[str] = Field(None, description="Optional user description")
    cached_balance: float = Field(
        ...,
        description="Cached account balance (performance cache, recomputable via recompute_account_balance RPC)"
    )
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
    icon: str = Field(
        ...,
        description="Icon identifier for UI display",
        min_length=1,
        max_length=50,
        examples=["wallet", "bank", "credit_card", "piggy_bank"]
    )
    color: str = Field(
        ...,
        description="Hex color code for UI display (e.g., '#FF5733')",
        pattern=r'^#[0-9A-Fa-f]{6}$',
        examples=["#FF5733", "#4CAF50", "#2196F3"]
    )
    is_favorite: bool = Field(
        False,
        description="If true, this account will be auto-selected for manual transactions. "
                    "Only one account per user can be favorite (previous favorite is auto-cleared)."
    )
    is_pinned: bool = Field(
        False,
        description="If true, this account appears at the top of account lists"
    )
    description: Optional[str] = Field(
        None,
        description="Optional user description for the account",
        max_length=500,
        examples=["Main checking account for daily expenses", "Emergency savings"]
    )
    initial_balance: Optional[float] = Field(
        None,
        description="Optional initial balance for the account. "
                    "If provided, creates an income transaction with system_generated_key='initial_balance' "
                    "using the system category with key='initial_balance' and flow_type='income'",
        ge=0,
        examples=[1000.00, 500.50, 0.00]
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

    NOTE: Currency cannot be changed after creation (single-currency-per-user policy).
    NOTE: To set is_favorite=true, use the dedicated set_favorite_account RPC.
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
    icon: Optional[str] = Field(
        None,
        description="Updated icon identifier",
        min_length=1,
        max_length=50
    )
    color: Optional[str] = Field(
        None,
        description="Updated hex color code (e.g., '#FF5733')",
        pattern=r'^#[0-9A-Fa-f]{6}$'
    )
    is_pinned: Optional[bool] = Field(
        None,
        description="Updated pinned status (pinned accounts appear at top)"
    )
    description: Optional[str] = Field(
        None,
        description="Updated description (pass empty string to clear)",
        max_length=500
    )
    # Currency is intentionally NOT updatable - single-currency-per-user policy
    # is_favorite is managed via set_favorite_account RPC for data integrity


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


# --- Favorite account models ---

class SetFavoriteAccountRequest(BaseModel):
    """
    Request to set an account as the user's favorite.

    Setting a new favorite automatically clears the previous favorite (if any).
    """
    account_id: str = Field(
        ...,
        description="UUID of the account to set as favorite"
    )


class SetFavoriteAccountResponse(BaseModel):
    """
    Response after setting a favorite account.
    """
    status: str = Field("OK", description="Success indicator")
    previous_favorite_id: Optional[str] = Field(
        None,
        description="UUID of the previously favorite account (null if none)"
    )
    new_favorite_id: str = Field(
        ...,
        description="UUID of the newly favorited account"
    )
    message: str = Field(
        ...,
        description="Success message",
        examples=["Account set as favorite", "Account was already favorite"]
    )


class ClearFavoriteAccountResponse(BaseModel):
    """
    Response after clearing favorite status from an account.
    """
    status: str = Field("OK", description="Success indicator")
    cleared: bool = Field(
        ...,
        description="True if the account was favorite and is now cleared. False if it wasn't favorite."
    )
    message: str = Field(
        ...,
        description="Success message",
        examples=["Favorite status cleared", "Account was not favorite"]
    )


class GetFavoriteAccountResponse(BaseModel):
    """
    Response with the user's favorite account info.
    """
    status: str = Field(
        default="OK",
        description="Status of the response"
    )
    favorite_account_id: Optional[str] = Field(
        None,
        description="UUID of the favorite account, or null if no favorite is set"
    )
