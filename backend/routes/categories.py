"""
Category CRUD API endpoints.

Provides endpoints for managing income/outcome categories.

Endpoints:
- GET /categories - List all categories (system + user's personal)
- POST /categories - Create a new user category
- GET /categories/{category_id} - Get single category
- PATCH /categories/{category_id} - Update user category
- DELETE /categories/{category_id} - Delete user category (with DB rule enforcement)
"""

import logging
from typing import Annotated
from fastapi import APIRouter, Depends, HTTPException, status

from backend.auth.dependencies import get_authenticated_user, AuthenticatedUser
from backend.db.client import get_supabase_client
from backend.services.category_service import (
    get_all_categories,
    create_category,
    get_category_by_id,
    update_category,
    delete_category,
)
from backend.schemas.categories import (
    CategoryResponse,
    CategoryListResponse,
    CategoryCreateRequest,
    CategoryCreateResponse,
    CategoryUpdateRequest,
    CategoryUpdateResponse,
    CategoryDeleteResponse,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/categories", tags=["categories"])


@router.get(
    "",
    response_model=CategoryListResponse,
    status_code=status.HTTP_200_OK,
    summary="List all categories",
    description="""
    Retrieve all categories available to the authenticated user.
    
    This endpoint:
    - Returns system categories (user_id=NULL, read-only)
    - Returns user's personal categories (user_id=authenticated user)
    - Orders by name alphabetically
    - Supports pagination via limit/offset
    
    Security:
    - Requires valid authentication token
    - System categories are visible to all users (read-only)
    - User categories filtered by RLS
    """
)
async def list_categories(
    auth_user: Annotated[AuthenticatedUser, Depends(get_authenticated_user)],
    limit: int = 100,
    offset: int = 0
) -> CategoryListResponse:
    """
    List all categories available to the user.
    
    **6-STEP ENDPOINT FLOW:**
    
    Step 1: Auth
    - Handled by get_authenticated_user dependency
    
    Step 2: Parse/Validate Request
    - Query parameters validated by FastAPI
    
    Step 3: Domain & Intent Filter
    - No domain filtering needed (valid category list request)
    
    Step 4: Call Service
    - Call get_all_categories() service function
    
    Step 5: Map Output -> ResponseModel
    - Return CategoryListResponse
    
    Step 6: Persistence
    - Read-only operation (no persistence)
    """
    logger.info(f"Listing categories for user {auth_user.user_id} (limit={limit}, offset={offset})")
    
    supabase_client = get_supabase_client(auth_user.access_token)
    
    try:
        categories = await get_all_categories(
            supabase_client=supabase_client,
            user_id=auth_user.user_id,
            limit=limit,
            offset=offset
        )
        
        category_responses = [
            CategoryResponse(
                id=str(cat.get("id")),
                user_id=str(cat.get("user_id")) if cat.get("user_id") else None,
                key=cat.get("key"),
                name=cat.get("name", ""),
                flow_type=cat.get("flow_type", "outcome"),
                created_at=cat.get("created_at", ""),
                updated_at=cat.get("updated_at")
            )
            for cat in categories
        ]
        
        logger.info(f"Returning {len(category_responses)} categories for user {auth_user.user_id}")
        
        return CategoryListResponse(
            categories=category_responses,
            count=len(category_responses),
            limit=limit,
            offset=offset
        )
        
    except Exception as e:
        logger.error(f"Failed to fetch categories: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={
                "error": "fetch_error",
                "details": "Failed to retrieve categories from database"
            }
        )


@router.post(
    "",
    response_model=CategoryCreateResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create a new user category",
    description="""
    Create a new personal category for the authenticated user.
    
    This endpoint:
    - Creates a user category (user_id = authenticated user)
    - Cannot create system categories (those are pre-defined)
    - Validates name and flow_type
    
    Security:
    - Requires valid authentication token
    - RLS enforces user can only create categories for themselves
    """
)
async def create_user_category(
    request: CategoryCreateRequest,
    auth_user: Annotated[AuthenticatedUser, Depends(get_authenticated_user)]
) -> CategoryCreateResponse:
    """
    Create a new user category.
    
    Auth
    - Handled by get_authenticated_user dependency
    
    Parse/Validate Request
    - FastAPI validates CategoryCreateRequest

    Domain & Intent Filter
    - Validate name is not empty (Pydantic already enforces this)

    Call Service
    - Call create_category() service function
    
    Map Output -> ResponseModel
    - Return CategoryCreateResponse
    
    Persistence
    - Service layer handles DB insert with RLS
    """
    logger.info(
        f"Creating category for user {auth_user.user_id}: "
        f"name={request.name}, flow_type={request.flow_type}"
    )
    
    supabase_client = get_supabase_client(auth_user.access_token)
    
    try:
        created_category = await create_category(
            supabase_client=supabase_client,
            user_id=auth_user.user_id,
            name=request.name,
            flow_type=request.flow_type
        )
        
        logger.info(f"Category created successfully: id={created_category.get('id')}")
        
        return CategoryCreateResponse(
            status="CREATED",
            category=CategoryResponse(
                id=str(created_category.get("id")),
                user_id=str(created_category.get("user_id")),
                key=created_category.get("key"),
                name=created_category.get("name", ""),
                flow_type=created_category.get("flow_type", "outcome"),
                created_at=created_category.get("created_at", ""),
                updated_at=created_category.get("updated_at")
            ),
            message="Category created successfully"
        )
        
    except Exception as e:
        logger.error(f"Failed to create category: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={
                "error": "create_error",
                "details": "Failed to create category"
            }
        )


@router.get(
    "/{category_id}",
    response_model=CategoryResponse,
    status_code=status.HTTP_200_OK,
    summary="Get category details",
    description="""
    Retrieve a single category by its ID.
    
    This endpoint:
    - Returns category details if accessible
    - User can access system categories and their own categories
    - Returns 404 if category doesn't exist or not accessible
    
    Security:
    - Requires valid authentication token
    - User can view system categories (read-only)
    - User can view their own categories
    """
)
async def get_category(
    category_id: str,
    auth_user: Annotated[AuthenticatedUser, Depends(get_authenticated_user)]
) -> CategoryResponse:
    """
    Get details of a single category.
    
    Args:
        category_id: UUID of the category to retrieve
        auth_user: Authenticated user from token
    
    Returns:
        CategoryResponse with category details
    
    Raises:
        HTTPException 404: If category not found or not accessible
    """
    logger.info(f"Fetching category {category_id} for user {auth_user.user_id}")
    
    supabase_client = get_supabase_client(auth_user.access_token)
    
    try:
        category = await get_category_by_id(
            supabase_client=supabase_client,
            user_id=auth_user.user_id,
            category_id=category_id
        )
        
        if not category:
            logger.warning(f"Category {category_id} not found or not accessible by user {auth_user.user_id}")
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail={
                    "error": "not_found",
                    "details": f"Category {category_id} not found or not accessible"
                }
            )
        
        logger.info(f"Returning category {category_id} for user {auth_user.user_id}")
        
        return CategoryResponse(
            id=str(category.get("id")),
            user_id=str(category.get("user_id")) if category.get("user_id") else None,
            key=category.get("key"),
            name=category.get("name", ""),
            flow_type=category.get("flow_type", "outcome"),
            created_at=category.get("created_at", ""),
            updated_at=category.get("updated_at")
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to fetch category {category_id}: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={
                "error": "fetch_error",
                "details": "Failed to retrieve category from database"
            }
        )


@router.patch(
    "/{category_id}",
    response_model=CategoryUpdateResponse,
    status_code=status.HTTP_200_OK,
    summary="Update a user category",
    description="""
    Update an existing user category.
    
    This endpoint:
    - Updates only the fields provided in the request
    - Requires at least one field to be provided
    - Cannot update system categories
    - Only the category owner can update
    
    Security:
    - Requires valid authentication token
    - RLS ensures user can only update their own categories
    - System categories are protected from modification
    """
)
async def update_user_category(
    category_id: str,
    request: CategoryUpdateRequest,
    auth_user: Annotated[AuthenticatedUser, Depends(get_authenticated_user)]
) -> CategoryUpdateResponse:
    """
    Update a user category (partial update).
    
    Args:
        category_id: UUID of the category to update
        request: Fields to update
        auth_user: Authenticated user from token
    
    Returns:
        CategoryUpdateResponse with updated category
    
    Raises:
        HTTPException 400: If no fields provided or trying to update system category
        HTTPException 404: If category not found or not accessible
    """
    # Validate at least one field is provided
    if request.name is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={
                "error": "invalid_request",
                "details": "At least one field must be provided for update"
            }
        )
    
    logger.info(f"Updating category {category_id} for user {auth_user.user_id}")
    
    supabase_client = get_supabase_client(auth_user.access_token)
    
    try:
        updated_category = await update_category(
            supabase_client=supabase_client,
            user_id=auth_user.user_id,
            category_id=category_id,
            name=request.name
        )
        
        if not updated_category:
            logger.warning(f"Category {category_id} not found or not accessible by user {auth_user.user_id}")
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail={
                    "error": "not_found",
                    "details": f"Category {category_id} not found or not accessible"
                }
            )
        
        logger.info(f"Category {category_id} updated successfully")
        
        return CategoryUpdateResponse(
            status="UPDATED",
            category=CategoryResponse(
                id=str(updated_category.get("id")),
                user_id=str(updated_category.get("user_id")) if updated_category.get("user_id") else None,
                key=updated_category.get("key"),
                name=updated_category.get("name", ""),
                flow_type=updated_category.get("flow_type", "outcome"),
                created_at=updated_category.get("created_at", ""),
                updated_at=updated_category.get("updated_at")
            ),
            message="Category updated successfully"
        )
        
    except HTTPException:
        raise
    except Exception as e:
        # Check if it's the system category protection error
        if "Cannot update system category" in str(e):
            logger.warning(f"Attempt to update system category {category_id}")
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail={
                    "error": "system_category",
                    "details": "Cannot update system category"
                }
            )
        
        logger.error(f"Failed to update category {category_id}: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={
                "error": "update_error",
                "details": "Failed to update category"
            }
        )


@router.delete(
    "/{category_id}",
    response_model=CategoryDeleteResponse,
    status_code=status.HTTP_200_OK,
    summary="Delete a user category",
    description="""
    Delete a user category following DB deletion rules.
    
    This endpoint:
    - Reassigns all transactions using this category to the 'general' system category
    - Removes all budget_category links
    - Deletes the category
    - Cannot delete system categories
    
    Security:
    - Requires valid authentication token
    - Only the category owner can delete
    - System categories are protected from deletion
    
    DB Rules:
    1. Update all transactions using category_id to 'general' system category
    2. Remove all budget_category links
    3. Delete the category
    4. System categories CANNOT be deleted
    """
)
async def delete_user_category(
    category_id: str,
    auth_user: Annotated[AuthenticatedUser, Depends(get_authenticated_user)]
) -> CategoryDeleteResponse:
    """
    Delete a user category (with DB rule enforcement).
    
    Args:
        category_id: UUID of the category to delete
        auth_user: Authenticated user from token
    
    Returns:
        CategoryDeleteResponse with deletion details
    
    Raises:
        HTTPException 400: If trying to delete system category
        HTTPException 404: If category not found or not accessible
    """
    logger.info(f"Deleting category {category_id} for user {auth_user.user_id}")
    
    supabase_client = get_supabase_client(auth_user.access_token)
    
    try:
        success, transactions_reassigned, budget_links_removed = await delete_category(
            supabase_client=supabase_client,
            user_id=auth_user.user_id,
            category_id=category_id
        )
        
        if not success:
            logger.warning(f"Category {category_id} not found or not accessible by user {auth_user.user_id}")
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail={
                    "error": "not_found",
                    "details": f"Category {category_id} not found or not accessible"
                }
            )
        
        logger.info(
            f"Category {category_id} deleted successfully: "
            f"{transactions_reassigned} transactions reassigned, "
            f"{budget_links_removed} budget links removed"
        )
        
        return CategoryDeleteResponse(
            status="DELETED",
            category_id=str(category_id),
            transactions_reassigned=transactions_reassigned,
            budget_links_removed=budget_links_removed,
            message=(
                f"Category deleted successfully. "
                f"{transactions_reassigned} transaction(s) reassigned to 'general', "
                f"{budget_links_removed} budget link(s) removed."
            )
        )
        
    except HTTPException:
        raise
    except Exception as e:
        # Check if it's the system category protection error
        if "Cannot delete system category" in str(e):
            logger.warning(f"Attempt to delete system category {category_id}")
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail={
                    "error": "system_category",
                    "details": "Cannot delete system category"
                }
            )
        
        logger.error(f"Failed to delete category {category_id}: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={
                "error": "delete_error",
                "details": "Failed to delete category"
            }
        )
