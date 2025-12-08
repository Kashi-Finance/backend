"""
Pydantic schemas for recommendation query endpoints.

These models define the strict request/response contracts for the
recommendation system powered by Gemini with Google Search grounding.
"""

from decimal import Decimal
from typing import Any, Dict, List, Literal, Optional

from pydantic import BaseModel, Field

# ============================================================================
# REQUEST MODELS
# ============================================================================

class RecommendationQueryRequest(BaseModel):
    """
    Request to query recommendations for a purchase goal.

    This is the initial request that triggers the recommendation service.
    The service will validate the request, call Gemini with Google Search,
    and return structured product recommendations from real web data.

    Frontend scenarios:
    - First query: User fills basic info and clicks "Get recommendations"
    - Retry/refine: User adjusts parameters and tries again
    """
    query_raw: str = Field(
        ...,
        description=(
            "User's natural language query describing what they want to buy. "
            "Can be natural ('laptop para diseño') or technical "
            "('Laptop Ryzen 7, 16GB RAM, SSD 512GB')."
        ),
        min_length=3,
        max_length=1000,
        examples=[
            "laptop para diseño gráfico",
            "Laptop Ryzen 7, 16GB RAM, SSD 512GB, 15 pulgadas"
        ]
    )
    budget_hint: Optional[Decimal] = Field(
        None,
        description=(
            "Maximum budget user is willing to spend in local currency. "
            "Usually REQUIRED by agent for product recommendations. "
            "If omitted, agent may return NEEDS_CLARIFICATION."
        ),
        gt=0,
        decimal_places=2,
        examples=[7000.00, 5500.50]
    )
    preferred_store: Optional[str] = Field(
        None,
        description="User's preferred store name or location",
        max_length=200,
        examples=["Intelaf Zone 9", "ElectroCentro", "Physical stores only"]
    )
    user_note: Optional[str] = Field(
        None,
        description=(
            "User's additional preferences, restrictions, or style notes. "
            "Agent uses this to filter/adapt results."
        ),
        max_length=1000,
        examples=[
            "No RGB lights, minimalist design",
            "Must have warranty and pickup available",
            "nada gamer"
        ]
    )
    extra_details: Optional[Dict[str, Any]] = Field(
        default_factory=dict,
        description=(
            "Progressive Q&A answers for clarification flow. "
            "Populated when user responds to NEEDS_CLARIFICATION."
        ),
        examples=[
            {"clarified_budget": 6500.00},
            {"ram_preference": "16GB minimum"}
        ]
    )


class RecommendationRetryRequest(BaseModel):
    """
    Request to retry recommendations with updated criteria.

    Used when:
    - User received NO_VALID_OPTION and wants to adjust criteria
    - User wants to broaden search (higher budget, different store, etc.)
    - User wants different options (agent may return different results)

    Same structure as RecommendationQueryRequest but semantically different
    (this is a retry/refinement, not a fresh query).
    """
    query_raw: str = Field(
        ...,
        description="Updated or refined query",
        min_length=3,
        max_length=1000
    )
    budget_hint: Optional[Decimal] = Field(
        None,
        description="Updated budget (can be higher/lower than original)",
        gt=0,
        decimal_places=2
    )
    preferred_store: Optional[str] = Field(
        None,
        description="Updated store preference",
        max_length=200
    )
    user_note: Optional[str] = Field(
        None,
        description="Updated user notes/preferences",
        max_length=1000
    )
    extra_details: Optional[Dict[str, Any]] = Field(
        default_factory=dict,
        description="Additional clarification answers"
    )


# ============================================================================
# RESPONSE MODELS
# ============================================================================

class MissingFieldResponse(BaseModel):
    """
    Schema for a missing field that needs user clarification.

    Returned when agent determines required information is missing.
    """
    field: str = Field(
        ...,
        description="Machine-readable field name (e.g., 'budget_hint', 'query_raw')",
        examples=["budget_hint", "preferred_store", "query_raw"]
    )
    question: str = Field(
        ...,
        description="Spanish prompt for user to answer",
        examples=[
            "¿Cuál es tu presupuesto aproximado para esta compra?",
            "¿Qué tipo de producto estás buscando específicamente?"
        ]
    )


class ProductRecommendation(BaseModel):
    """
    Schema for a single formatted product recommendation.

    This is the final output from the recommendation service, ready for UI display.
    Matches WishlistItemFromRecommendation schema for seamless persistence.
    """
    product_title: str = Field(
        ...,
        description="Commercial product name",
        examples=["HP Envy Ryzen 7 16GB RAM 512GB SSD 15.6\""]
    )
    price_total: float = Field(
        ...,
        description="Total price in local currency",
        gt=0,
        examples=[6200.00]
    )
    seller_name: str = Field(
        ...,
        description="Store or seller name",
        examples=["ElectroCentro Guatemala"]
    )
    url: str = Field(
        ...,
        description="Valid URL where user can view/purchase the product",
        examples=["https://electrocentro.gt/hp-envy-ryzen7"]
    )
    pickup_available: bool = Field(
        ...,
        description="Whether in-store pickup is available",
        examples=[True, False]
    )
    warranty_info: str = Field(
        ...,
        description="Warranty details",
        examples=["HP 12-month warranty", "Garantía 12 meses tienda"]
    )
    copy_for_user: str = Field(
        ...,
        description=(
            "Descriptive copy for UI display. "
            "Max 3 sentences, factual, no emojis, no hype. "
            "Frontend renders as-is."
        ),
        examples=[
            "Ideal para Photoshop y diseño gráfico. Cumple con GPU dedicada y diseño sobrio sin luces gamer.",
            "Recommended for graphic design. Meets Ryzen 7 & 16GB RAM specs. ~Q100 cheaper than others."
        ]
    )
    badges: List[str] = Field(
        ...,
        description="UI badge labels (max 3), factual and concise",
        max_length=3,
        examples=[
            ["Cheapest", "12m Warranty", "Pickup Today"],
            ["Buen precio", "GPU dedicada", "Diseño sobrio"]
        ]
    )


class RecommendationQueryResponseNeedsClarification(BaseModel):
    """
    Response when agent needs more information to proceed.

    Frontend should:
    1. Display missing_fields questions to user
    2. Collect answers
    3. Submit new request with updated extra_details
    """
    status: Literal["NEEDS_CLARIFICATION"] = Field(
        "NEEDS_CLARIFICATION",
        description="Indicates missing required information"
    )
    missing_fields: List[MissingFieldResponse] = Field(
        ...,
        description="List of fields that need clarification (typically 1-2)",
        min_length=1
    )


class RecommendationQueryResponseOK(BaseModel):
    """
    Response when agent successfully found recommendations.

    Frontend should:
    1. Display results_for_user to user
    2. Allow user to select 0-3 options
    3. Submit POST /wishlists with selected_items when ready
    """
    status: Literal["OK"] = Field(
        "OK",
        description="Indicates successful recommendations"
    )
    results_for_user: List[ProductRecommendation] = Field(
        ...,
        description="List of formatted product recommendations (max 3)",
        min_length=1,
        max_length=3
    )


class RecommendationQueryResponseNoValidOption(BaseModel):
    """
    Response when agent cannot find suitable recommendations.

    Reasons:
    - Out-of-scope request (prohibited content, illegal items)
    - No products match criteria within budget
    - All candidates failed validation
    - Agent error or search failure

    Frontend should:
    1. Display reason to user
    2. Offer retry with adjusted criteria (higher budget, different query, etc.)
    """
    status: Literal["NO_VALID_OPTION"] = Field(
        "NO_VALID_OPTION",
        description="Indicates no suitable recommendations found"
    )
    reason: Optional[str] = Field(
        None,
        description="Optional explanation for why no options were found",
        examples=[
            "No se encontraron productos que cumplan los criterios dentro del presupuesto.",
            "Request contains prohibited content.",
            "An error occurred while processing your request."
        ]
    )


# Union type for response (FastAPI will use correct model based on status)
RecommendationQueryResponse = (
    RecommendationQueryResponseNeedsClarification |
    RecommendationQueryResponseOK |
    RecommendationQueryResponseNoValidOption
)
