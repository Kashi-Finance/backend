"""
Pydantic schemas for wishlist CRUD endpoints.

These models define the strict request/response contracts for wishlist management.
Wishlists represent user purchase goals (what they want to buy), and wishlist_items
represent specific store options saved from the recommendation flow.
"""

from datetime import date
from decimal import Decimal
from typing import List, Literal, Optional

from pydantic import BaseModel, Field, HttpUrl, field_validator

# Wishlist status enum (matches DB CHECK constraint)
WishlistStatus = Literal["active", "purchased", "abandoned"]


# --- Wishlist item models (used for saving recommendations) ---

class WishlistItemFromRecommendation(BaseModel):
    """
    A specific store option selected from the recommendation flow.

    These come from the recommendation service output and are saved when the user
    explicitly selects them at the end of the recommendation wizard.
    """
    product_title: str = Field(
        ...,
        description="Commercial product name from the recommendation",
        min_length=1,
        max_length=500,
        examples=["HP Envy Ryzen 7 16GB RAM 512GB SSD 15.6\""]
    )
    price_total: Decimal = Field(
        ...,
        description="Total price for the product (NUMERIC(12,2), must be >= 0)",
        ge=0,
        decimal_places=2,
        examples=[6200.00]
    )
    seller_name: str = Field(
        ...,
        description="Store or seller name",
        min_length=1,
        max_length=200,
        examples=["ElectroCentro Guatemala"]
    )
    url: HttpUrl = Field(
        ...,
        description="Valid URL where user can view/purchase the product",
        examples=["https://electrocentro.gt/hp-envy-ryzen7"]
    )
    pickup_available: bool = Field(
        ...,
        description="Whether in-store pickup is available",
        examples=[True]
    )
    warranty_info: str = Field(
        ...,
        description="Warranty details",
        min_length=1,
        max_length=500,
        examples=["HP 12-month warranty"]
    )
    copy_for_user: str = Field(
        ...,
        description="Descriptive copy for UI display",
        min_length=1,
        max_length=1000,
        examples=[
            "Recommended for graphic design. Meets Ryzen 7 & 16GB RAM specs. "
            "~Q100 cheaper than others."
        ]
    )
    badges: List[str] = Field(
        ...,
        description="UI badge labels (max 3)",
        max_length=3,
        examples=[["Cheapest", "12m Warranty", "Pickup Today"]]
    )

    @field_validator("badges")
    @classmethod
    def validate_badges_length(cls, v: List[str]) -> List[str]:
        """Ensure badges list has at most 3 items."""
        if len(v) > 3:
            raise ValueError("badges list must contain at most 3 items")
        return v


class WishlistItemResponse(BaseModel):
    """
    Response model for a saved wishlist item.
    """
    id: str = Field(..., description="Wishlist item UUID")
    wishlist_id: str = Field(..., description="Parent wishlist UUID")
    product_title: str = Field(..., description="Product name")
    price_total: str = Field(..., description="Total price (as string)")
    seller_name: str = Field(..., description="Store/seller name")
    url: str = Field(..., description="Product URL")
    pickup_available: bool = Field(..., description="In-store pickup available")
    warranty_info: str = Field(..., description="Warranty details")
    copy_for_user: str = Field(..., description="UI descriptive copy")
    badges: List[str] = Field(..., description="UI badge labels")
    created_at: str = Field(..., description="ISO-8601 creation timestamp")
    updated_at: str = Field(..., description="ISO-8601 update timestamp")


# --- Wishlist create models ---

class WishlistCreateRequest(BaseModel):
    """
    Request to create a new wishlist (goal).

    Supports three frontend scenarios:
    - CASE A: Manual save (no recommendations) - selected_items omitted/empty
    - CASE B: Recommendations requested but none selected - selected_items omitted/empty
    - CASE C: Recommendations requested and 1-3 selected - selected_items has items
    """
    goal_title: str = Field(
        ...,
        description="User's goal description (natural or technical language)",
        min_length=1,
        max_length=500,
        examples=[
            "Laptop para diseño gráfico que no sobrecaliente",
            "Laptop Ryzen 7, 16GB RAM, SSD 512GB, 15 pulgadas, sin RGB"
        ]
    )
    budget_hint: Decimal = Field(
        ...,
        description="Maximum budget the user is willing to spend (NUMERIC(12,2), must be > 0)",
        gt=0,
        decimal_places=2,
        examples=[7000.00]
    )
    currency_code: str = Field(
        ...,
        description="ISO currency code (3 chars, should match user profile currency)",
        min_length=3,
        max_length=3,
        pattern="^[A-Z]{3}$",
        examples=["GTQ", "USD"]
    )
    target_date: Optional[date] = Field(
        None,
        description="Optional target date for achieving the goal",
        examples=["2025-12-20"]
    )
    preferred_store: Optional[str] = Field(
        None,
        description="User's declared store preference",
        max_length=200,
        examples=["Prefer Intelaf Zone 9", "Physical store preferred"]
    )
    user_note: Optional[str] = Field(
        None,
        description="User's personal note with restrictions or style preferences",
        max_length=1000,
        examples=["No RGB lights, minimalist design for university use"]
    )
    selected_items: Optional[List[WishlistItemFromRecommendation]] = Field(
        None,
        description=(
            "Store options selected from recommendation flow. "
            "Omit or pass empty list if no items selected. "
            "Must have 1-3 items if provided."
        ),
        max_length=3
    )

    @field_validator("selected_items")
    @classmethod
    def validate_selected_items(cls, v: Optional[List[WishlistItemFromRecommendation]]) -> Optional[List[WishlistItemFromRecommendation]]:
        """Ensure selected_items has at most 3 items if provided."""
        if v is not None and len(v) > 3:
            raise ValueError("selected_items must contain at most 3 items")
        return v


class WishlistResponse(BaseModel):
    """
    Response model for wishlist details.
    """
    id: str = Field(..., description="Wishlist UUID")
    user_id: str = Field(..., description="Owner user UUID")
    goal_title: str = Field(..., description="User's goal description")
    budget_hint: str = Field(..., description="Maximum budget (as string)")
    currency_code: str = Field(..., description="ISO currency code")
    target_date: Optional[str] = Field(None, description="Target date (YYYY-MM-DD or null)")
    preferred_store: Optional[str] = Field(None, description="Store preference")
    user_note: Optional[str] = Field(None, description="User's personal note")
    status: WishlistStatus = Field(..., description="Goal status")
    created_at: str = Field(..., description="ISO-8601 creation timestamp")
    updated_at: str = Field(..., description="ISO-8601 update timestamp")


class WishlistCreateResponse(BaseModel):
    """
    Response after successfully creating a wishlist.
    """
    status: str = Field("CREATED", description="Indicates successful creation")
    wishlist: WishlistResponse = Field(..., description="The created wishlist")
    items_created: int = Field(
        ...,
        description="Number of wishlist_item rows created (0-3)"
    )
    message: str = Field(
        ...,
        description="Success message",
        examples=[
            "Wishlist created successfully",
            "Wishlist created successfully (no offers selected)",
            "Wishlist created successfully with 2 saved offers"
        ]
    )


# --- Wishlist update models ---

class WishlistUpdateRequest(BaseModel):
    """
    Request to update a wishlist.

    All fields are optional - only provided fields will be updated.
    At least one field must be provided.
    """
    goal_title: Optional[str] = Field(
        None,
        description="Updated goal description",
        min_length=1,
        max_length=500
    )
    budget_hint: Optional[Decimal] = Field(
        None,
        description="Updated budget (NUMERIC(12,2), must be > 0)",
        gt=0,
        decimal_places=2
    )
    currency_code: Optional[str] = Field(
        None,
        description="Updated currency code",
        min_length=3,
        max_length=3,
        pattern="^[A-Z]{3}$"
    )
    target_date: Optional[date] = Field(
        None,
        description="Updated target date"
    )
    preferred_store: Optional[str] = Field(
        None,
        description="Updated store preference",
        max_length=200
    )
    user_note: Optional[str] = Field(
        None,
        description="Updated user note",
        max_length=1000
    )
    status: Optional[WishlistStatus] = Field(
        None,
        description="Updated status"
    )


class WishlistUpdateResponse(BaseModel):
    """
    Response after successfully updating a wishlist.
    """
    status: str = Field("UPDATED", description="Indicates successful update")
    wishlist: WishlistResponse = Field(..., description="The updated wishlist")
    message: str = Field(
        ...,
        description="Success message",
        examples=["Wishlist updated successfully"]
    )


# --- Wishlist delete models ---

class WishlistDeleteResponse(BaseModel):
    """
    Response after successfully deleting a wishlist.
    """
    status: str = Field("DELETED", description="Indicates successful deletion")
    message: str = Field(
        ...,
        description="Success message",
        examples=["Wishlist deleted successfully. 2 items removed."]
    )
    items_deleted: int = Field(
        ...,
        description="Number of wishlist_item rows deleted (cascaded)"
    )


# --- Wishlist list response ---

class WishlistListResponse(BaseModel):
    """
    Response for listing user wishlists.
    """
    wishlists: List[WishlistResponse] = Field(
        ...,
        description="List of user's wishlists"
    )
    count: int = Field(..., description="Total number of wishlists returned")
    limit: int = Field(..., description="Maximum number of wishlists requested")
    offset: int = Field(..., description="Number of wishlists skipped (pagination)")


# --- Wishlist with items response (detailed view) ---

class WishlistWithItemsResponse(BaseModel):
    """
    Response for wishlist with its saved items.

    Used for GET /wishlists/{wishlist_id} to return complete goal details.
    """
    wishlist: WishlistResponse = Field(..., description="The wishlist goal")
    items: List[WishlistItemResponse] = Field(
        ...,
        description="Saved store options for this goal (0-N items)"
    )


# --- Wishlist item delete models ---

class WishlistItemDeleteResponse(BaseModel):
    """
    Response after successfully deleting a wishlist item.
    """
    status: str = Field("DELETED", description="Indicates successful deletion")
    message: str = Field(
        ...,
        description="Success message",
        examples=["Wishlist item deleted successfully"]
    )
