"""
Budget CRUD API endpoints.

Provides endpoints for managing user spending budgets.

Endpoints:
- GET /budgets - List all budgets
- POST /budgets - Create a new budget
- GET /budgets/{budget_id} - Get single budget
- PATCH /budgets/{budget_id} - Update budget
- DELETE /budgets/{budget_id} - Delete budget (with DB rule enforcement)
"""

import logging
from typing import Annotated, Any, Optional
from fastapi import APIRouter, Depends, HTTPException, Query, status, Path

from backend.auth.dependencies import get_authenticated_user, AuthenticatedUser
from backend.db.client import get_supabase_client
from backend.services.budget_service import (
    get_all_budgets,
    get_budget_by_id,
    create_budget,
    update_budget,
    delete_budget,
)
from backend.schemas.budgets import (
    BudgetResponse,
    BudgetListResponse,
    BudgetCreateRequest,
    BudgetCreateResponse,
    BudgetUpdateRequest,
    BudgetUpdateResponse,
    BudgetDeleteResponse,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/budgets", tags=["budgets"])


@router.get(
    "",
    response_model=BudgetListResponse,
    status_code=status.HTTP_200_OK,
    summary="List all budgets",
    description="""
    Retrieve all budgets belonging to the authenticated user.
    
    This endpoint:
    - Returns all user's budgets
    - Supports filtering by frequency and active status
    - Ordered by creation date (newest first)
    - Only accessible to the budget owner (RLS enforced)
    
    Security:
    - Requires valid Authorization Bearer token
    - RLS ensures users only see their own budgets
    """
)
async def list_budgets(
    auth_user: Annotated[AuthenticatedUser, Depends(get_authenticated_user)],
    frequency: Optional[str] = Query(None, description="Filter by frequency (daily|weekly|monthly|yearly|once)"),
    is_active: Optional[bool] = Query(None, description="Filter by active status"),
) -> BudgetListResponse:
    """
    List all budgets for the authenticated user.
    
    **6-STEP ENDPOINT FLOW:**
    
    Step 1: Auth
    - Handled by get_authenticated_user dependency
    
    Step 2: Parse/Validate Request
    - No request body (GET endpoint)
    - Query parameters: frequency, is_active
    
    Step 3: Domain & Intent Filter
    - Simple list request with optional filters
    
    Step 4: Call Service
    - Call get_all_budgets() service function with filters
    
    Step 5: Map Output -> ResponseModel
    - Convert budgets list to BudgetListResponse
    
    Step 6: Persistence
    - Read-only operation (no persistence needed)
    """
    logger.info(
        f"Listing budgets for user {auth_user.user_id} "
        f"(filters: frequency={frequency}, is_active={is_active})"
    )
    
    supabase_client = get_supabase_client(auth_user.access_token)
    
    try:
        budgets = await get_all_budgets(
            supabase_client=supabase_client,
            user_id=auth_user.user_id,
            frequency=frequency,
            is_active=is_active,
        )
        
        # Helper to coerce DB values to strings
        def _as_str(v: Any) -> str:
            return str(v) if v is not None else ""
        
        def _as_float(v: Any) -> float:
            try:
                return float(v) if v is not None else 0.0
            except (ValueError, TypeError):
                return 0.0
        
        def _as_int(v: Any) -> int:
            try:
                return int(v) if v is not None else 1
            except (ValueError, TypeError):
                return 1
        
        def _as_bool(v: Any) -> bool:
            return bool(v) if v is not None else True
        
        budget_responses = [
            BudgetResponse(
                id=_as_str(b.get("id")),
                user_id=_as_str(b.get("user_id")),
                name=_as_str(b.get("name")) if b.get("name") else "Presupuesto",  # Optional field
                limit_amount=_as_float(b.get("limit_amount")),
                frequency=b.get("frequency", "monthly"),  # type: ignore
                interval=_as_int(b.get("interval")),
                start_date=_as_str(b.get("start_date")),
                end_date=_as_str(b.get("end_date")) if b.get("end_date") else None,
                is_active=_as_bool(b.get("is_active")),
                categories=b.get("categories", []),  # Categories already transformed in service layer
                created_at=_as_str(b.get("created_at")),
                updated_at=_as_str(b.get("updated_at"))
            )
            for b in budgets
        ]
        
        logger.info(f"Returning {len(budget_responses)} budgets for user {auth_user.user_id}")
        
        return BudgetListResponse(
            budgets=budget_responses,
            count=len(budget_responses)
        )
        
    except Exception as e:
        logger.error(f"Failed to fetch budgets: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={
                "error": "fetch_error",
                "details": "Failed to retrieve budgets from database"
            }
        )


@router.post(
    "",
    response_model=BudgetCreateResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create a new budget",
    description="""
    Create a new spending budget with optional category links.
    
    This endpoint:
    - Creates a new budget with spending limits and time periods
    - Optionally links categories via budget_category table
    - Validates frequency and interval constraints
    
    Security:
    - Requires valid Authorization Bearer token
    - RLS enforces budget is owned by authenticated user
    """
)
async def create_new_budget(
    request: BudgetCreateRequest,
    auth_user: Annotated[AuthenticatedUser, Depends(get_authenticated_user)]
) -> BudgetCreateResponse:
    """
    Create a new budget.
    
    **6-STEP ENDPOINT FLOW:**
    
    Step 1: Auth
    - Handled by get_authenticated_user dependency
    
    Step 2: Parse/Validate Request
    - FastAPI validates BudgetCreateRequest automatically
    
    Step 3: Domain & Intent Filter
    - Validate frequency is in allowed enum
    - Validate limit_amount > 0
    
    Step 4: Call Service
    - Call create_budget() service function
    
    Step 5: Map Output -> ResponseModel
    - Convert created budget to BudgetCreateResponse
    
    Step 6: Persistence
    - Service layer handles database insert and category linking
    """
    logger.info(f"Creating budget for user {auth_user.user_id}: limit={request.limit_amount}")
    
    supabase_client = get_supabase_client(auth_user.access_token)
    
    try:
        created_budget, categories_linked = await create_budget(
            supabase_client=supabase_client,
            user_id=auth_user.user_id,
            name=request.name or "Presupuesto",
            limit_amount=request.limit_amount,
            frequency=request.frequency,
            interval=request.interval,
            start_date=request.start_date,
            end_date=request.end_date,
            is_active=request.is_active,
            category_ids=request.category_ids
        )
        
        # Helper to coerce DB values to strings
        def _as_str(v: Any) -> str:
            return str(v) if v is not None else ""
        
        def _as_float(v: Any) -> float:
            try:
                return float(v) if v is not None else 0.0
            except (ValueError, TypeError):
                return 0.0
        
        def _as_int(v: Any) -> int:
            try:
                return int(v) if v is not None else 1
            except (ValueError, TypeError):
                return 1
        
        def _as_bool(v: Any) -> bool:
            return bool(v) if v is not None else True
        
        budget_response = BudgetResponse(
            id=_as_str(created_budget.get("id")),
            user_id=_as_str(created_budget.get("user_id")),
            name=created_budget.get("name") or "Presupuesto",
            limit_amount=_as_float(created_budget.get("limit_amount")),
            frequency=created_budget.get("frequency", "monthly"),  # type: ignore
            interval=_as_int(created_budget.get("interval")),
            start_date=_as_str(created_budget.get("start_date")),
            end_date=_as_str(created_budget.get("end_date")) if created_budget.get("end_date") else None,
            is_active=_as_bool(created_budget.get("is_active")),
            categories=created_budget.get("categories", []),  # Categories from service layer
            created_at=_as_str(created_budget.get("created_at")),
            updated_at=_as_str(created_budget.get("updated_at"))
        )
        
        logger.info(f"Budget created successfully: {budget_response.id} with {categories_linked} categories")
        
        return BudgetCreateResponse(
            status="CREATED",
            budget=budget_response,
            categories_linked=categories_linked,
            message=f"Budget created successfully with {categories_linked} categories"
        )
        
    except Exception as e:
        logger.error(f"Failed to create budget for user {auth_user.user_id}: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={
                "error": "create_error",
                "details": "Failed to create budget"
            }
        )


@router.get(
    "/{budget_id}",
    response_model=BudgetResponse,
    status_code=status.HTTP_200_OK,
    summary="Get budget details",
    description="""
    Retrieve details of a single budget by ID.
    
    This endpoint:
    - Returns budget details for the specified ID
    - Only accessible to the budget owner (RLS enforced)
    
    Security:
    - Requires valid Authorization Bearer token
    - Returns 404 if budget doesn't exist or belongs to another user
    """
)
async def get_budget(
    budget_id: Annotated[str, Path(description="Budget UUID")],
    auth_user: Annotated[AuthenticatedUser, Depends(get_authenticated_user)]
) -> BudgetResponse:
    """Get budget by ID."""
    logger.info(f"Fetching budget {budget_id} for user {auth_user.user_id}")
    
    supabase_client = get_supabase_client(auth_user.access_token)
    
    try:
        budget = await get_budget_by_id(
            supabase_client=supabase_client,
            user_id=auth_user.user_id,
            budget_id=budget_id
        )
        
        if not budget:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail={
                    "error": "not_found",
                    "details": "Budget not found"
                }
            )
        
        # Helper to coerce DB values to strings
        def _as_str(v: Any) -> str:
            return str(v) if v is not None else ""
        
        def _as_float(v: Any) -> float:
            try:
                return float(v) if v is not None else 0.0
            except (ValueError, TypeError):
                return 0.0
        
        def _as_int(v: Any) -> int:
            try:
                return int(v) if v is not None else 1
            except (ValueError, TypeError):
                return 1
        
        def _as_bool(v: Any) -> bool:
            return bool(v) if v is not None else True
        
        return BudgetResponse(
            id=_as_str(budget.get("id")),
            user_id=_as_str(budget.get("user_id")),
            name=budget.get("name"),  # Optional field
            limit_amount=_as_float(budget.get("limit_amount")),
            frequency=budget.get("frequency", "monthly"),  # type: ignore
            interval=_as_int(budget.get("interval")),
            start_date=_as_str(budget.get("start_date")),
            end_date=_as_str(budget.get("end_date")) if budget.get("end_date") else None,
            is_active=_as_bool(budget.get("is_active")),
            categories=budget.get("categories", []),  # Categories from service layer
            created_at=_as_str(budget.get("created_at")),
            updated_at=_as_str(budget.get("updated_at"))
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to fetch budget {budget_id}: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={
                "error": "fetch_error",
                "details": "Failed to retrieve budget"
            }
        )


@router.patch(
    "/{budget_id}",
    response_model=BudgetUpdateResponse,
    status_code=status.HTTP_200_OK,
    summary="Update budget",
    description="""
    Update budget details.
    
    This endpoint:
    - Accepts partial updates (only provided fields are updated)
    - Returns the complete updated budget
    - Does NOT update category links (use separate endpoints for that)
    
    Security:
    - Only the budget owner can update their budget
    - RLS enforces user_id = auth.uid()
    """
)
async def update_existing_budget(
    budget_id: Annotated[str, Path(description="Budget UUID")],
    request: BudgetUpdateRequest,
    auth_user: Annotated[AuthenticatedUser, Depends(get_authenticated_user)]
) -> BudgetUpdateResponse:
    """Update budget details."""
    logger.info(f"Updating budget {budget_id} for user {auth_user.user_id}")
    
    # Extract non-None updates
    updates = request.model_dump(exclude_none=True)
    
    if not updates:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={
                "error": "invalid_request",
                "details": "At least one field must be provided for update"
            }
        )
    
    supabase_client = get_supabase_client(auth_user.access_token)
    
    try:
        updated_budget = await update_budget(
            supabase_client=supabase_client,
            user_id=auth_user.user_id,
            budget_id=budget_id,
            **updates
        )
        
        if not updated_budget:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail={
                    "error": "not_found",
                    "details": "Budget not found"
                }
            )
        
        # Helper to coerce DB values to strings
        def _as_str(v: Any) -> str:
            return str(v) if v is not None else ""
        
        def _as_float(v: Any) -> float:
            try:
                return float(v) if v is not None else 0.0
            except (ValueError, TypeError):
                return 0.0
        
        def _as_int(v: Any) -> int:
            try:
                return int(v) if v is not None else 1
            except (ValueError, TypeError):
                return 1
        
        def _as_bool(v: Any) -> bool:
            return bool(v) if v is not None else True
        
        budget_response = BudgetResponse(
            id=_as_str(updated_budget.get("id")),
            user_id=_as_str(updated_budget.get("user_id")),
            name=updated_budget.get("name"),  # Optional field
            limit_amount=_as_float(updated_budget.get("limit_amount")),
            frequency=updated_budget.get("frequency", "monthly"),  # type: ignore
            interval=_as_int(updated_budget.get("interval")),
            start_date=_as_str(updated_budget.get("start_date")),
            end_date=_as_str(updated_budget.get("end_date")) if updated_budget.get("end_date") else None,
            is_active=_as_bool(updated_budget.get("is_active")),
            categories=updated_budget.get("categories", []),  # Categories from service layer
            created_at=_as_str(updated_budget.get("created_at")),
            updated_at=_as_str(updated_budget.get("updated_at"))
        )
        
        logger.info(f"Budget {budget_id} updated successfully")
        
        return BudgetUpdateResponse(
            status="UPDATED",
            budget=budget_response,
            message="Budget updated successfully"
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to update budget {budget_id}: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={
                "error": "update_error",
                "details": "Failed to update budget"
            }
        )


@router.delete(
    "/{budget_id}",
    response_model=BudgetDeleteResponse,
    status_code=status.HTTP_200_OK,
    summary="Delete budget",
    description="""
    Delete a budget following DB deletion rules.
    
    This endpoint:
    - Deletes all budget_category links first
    - Then deletes the budget
    - Never deletes transactions (they remain as history)
    
    Security:
    - Requires valid Authorization Bearer token
    - Only the budget owner can delete their budget
    
    DB Rules (from DB-documentation.md):
    1. Delete all budget_category links
    2. Delete the budget
    3. Transactions remain untouched
    """
)
async def delete_existing_budget(
    budget_id: Annotated[str, Path(description="Budget UUID to delete")],
    auth_user: Annotated[AuthenticatedUser, Depends(get_authenticated_user)]
) -> BudgetDeleteResponse:
    """Delete budget following DB delete rules."""
    logger.info(f"Deleting budget {budget_id} for user {auth_user.user_id}")
    
    supabase_client = get_supabase_client(auth_user.access_token)
    
    try:
        success, deleted_at = await delete_budget(
            supabase_client=supabase_client,
            user_id=auth_user.user_id,
            budget_id=budget_id
        )
        
        if not success:
            logger.warning(f"Budget {budget_id} not found or not accessible by user {auth_user.user_id}")
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail={
                    "error": "not_found",
                    "details": f"Budget {budget_id} not found or not accessible"
                }
            )
        
        logger.info(f"Budget {budget_id} soft-deleted successfully at {deleted_at}")
        
        return BudgetDeleteResponse(
            status="DELETED",
            budget_id=str(budget_id),
            deleted_at=str(deleted_at),
            message="Budget soft-deleted successfully"
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to delete budget {budget_id}: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={
                "error": "delete_error",
                "details": "Failed to delete budget"
            }
        )
