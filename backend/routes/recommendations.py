"""
FastAPI routes for recommendation system endpoints.

This module exposes HTTP endpoints for the recommendation flow powered by
the Prompt Chaining architecture using DeepSeek V3.2. All endpoints require
authentication via Supabase Auth.

Endpoints:
- POST /recommendations/query: Initial recommendation query
- POST /recommendations/retry: Retry with updated criteria
"""

import logging
from fastapi import APIRouter, Depends
from typing import Union

from backend.auth.dependencies import get_authenticated_user, AuthenticatedUser
from backend.db.client import get_supabase_client
from backend.schemas.recommendations import (
    RecommendationQueryRequest,
    RecommendationRetryRequest,
    RecommendationQueryResponseNeedsClarification,
    RecommendationQueryResponseOK,
    RecommendationQueryResponseNoValidOption
)
from backend.services.recommendation_service import (
    query_recommendations,
    retry_recommendations
)

logger = logging.getLogger(__name__)

# Create router
router = APIRouter(
    prefix="/recommendations",
    tags=["recommendations"]
)


# Union type for response models (FastAPI will select correct one based on status)
RecommendationResponse = Union[
    RecommendationQueryResponseNeedsClarification,
    RecommendationQueryResponseOK,
    RecommendationQueryResponseNoValidOption
]


# ============================================================================
# ENDPOINTS
# ============================================================================

@router.post(
    "/query",
    response_model=RecommendationResponse,
    status_code=200,
    summary="Query product recommendations",
    description="""
    Queries the recommendation system for product suggestions based on user's goal.
    
    **Authentication:** Required (Bearer token)
    
    **Frontend Flow:**
    1. User fills wizard with goal description and preferences
    2. User clicks "Get recommendations"
    3. POST /recommendations/query with query_raw and optional budget_hint
    4. Receive one of two responses:
       - OK: Successful recommendations (display results, allow selection)
       - NO_VALID_OPTION: No suitable products (offer retry or manual save)
    
    **Architecture:**
    Uses Prompt Chaining with DeepSeek V3.2 for single-shot recommendations.
    - Validates intent (rejects prohibited content)
    - Searches for products based on user criteria
    - Returns structured JSON output
    
    **Next Steps After OK:**
    - User selects 0-3 recommendations
    - POST /wishlists with selected_items to persist goal + selections
    """
)
async def query_recommendations_endpoint(
    request: RecommendationQueryRequest,
    auth_user: AuthenticatedUser = Depends(get_authenticated_user)
) -> RecommendationResponse:
    """
    Initial recommendation query endpoint.
    
    - Auth: Handled by get_authenticated_user dependency
    - Parse/Validate: Handled by Pydantic RecommendationQueryRequest
    - Domain filter: Built into system prompt (guardrails)
    - Call LLM: Single call to DeepSeek V3.2 via service layer
    - Map output: Service layer maps LLM output to response models
    - Return response: FastAPI validates and returns response_model
    """
    logger.info(
        f"POST /recommendations/query called by user_id={auth_user.user_id}, "
        f"query_raw='{request.query_raw[:50]}...'"
    )
    
    # Create authenticated Supabase client (respects RLS)
    supabase_client = get_supabase_client(auth_user.access_token)
    
    # Call service layer (handles all orchestration and error handling)
    response = await query_recommendations(
        supabase_client=supabase_client,
        user_id=auth_user.user_id,
        query_raw=request.query_raw,
        budget_hint=request.budget_hint,
        preferred_store=request.preferred_store,
        user_note=request.user_note,
        extra_details=request.extra_details
    )
    
    logger.info(f"Returning response with status={response.status}")
    return response


@router.post(
    "/retry",
    response_model=RecommendationResponse,
    status_code=200,
    summary="Retry recommendations with updated criteria",
    description="""
    Retries recommendations with adjusted parameters.
    
    **Authentication:** Required (Bearer token)
    
    **Use Cases:**
    1. User received NO_VALID_OPTION and wants to try different criteria
       - Example: Increase budget, change store preference, broaden query
    2. User received OK but wants to see different options
    
    **Frontend Flow:**
    1. User adjusts criteria (budget, query, store, notes)
    2. User clicks "Try again" or "Search again"
    3. POST /recommendations/retry with updated request
    4. Receive same response types as /query
    
    **Technical Behavior:**
    - Identical to /query endpoint (calls same service)
    - Separate endpoint for semantic clarity and future extensibility
    """
)
async def retry_recommendations_endpoint(
    request: RecommendationRetryRequest,
    auth_user: AuthenticatedUser = Depends(get_authenticated_user)
) -> RecommendationResponse:
    """
    Retry recommendation query endpoint.
    
    Same flow as query endpoint but semantically represents a retry.
    """
    logger.info(
        f"POST /recommendations/retry called by user_id={auth_user.user_id}, "
        f"query_raw='{request.query_raw[:50]}...'"
    )
    
    # Create authenticated Supabase client (respects RLS)
    supabase_client = get_supabase_client(auth_user.access_token)
    
    # Call service layer (retry_recommendations internally calls query_recommendations)
    response = await retry_recommendations(
        supabase_client=supabase_client,
        user_id=auth_user.user_id,
        query_raw=request.query_raw,
        budget_hint=request.budget_hint,
        preferred_store=request.preferred_store,
        user_note=request.user_note,
        extra_details=request.extra_details
    )
    
    logger.info(f"Returning response with status={response.status}")
    return response
