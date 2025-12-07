"""
Category CRUD API endpoints.

Provides endpoints for managing income/outcome categories with subcategory support.

Endpoints:
- GET /categories - List all categories (system + user's personal)
- POST /categories - Create a new user category (with optional inline subcategories)
- GET /categories/{category_id} - Get single category
- GET /categories/{category_id}/subcategories - List subcategories of a category
- PATCH /categories/{category_id} - Update user category
- DELETE /categories/{category_id} - Delete user category (with DB rule enforcement)

Subcategory Support:
- Categories can have subcategories (max depth: 1)
- Use parent_category_id to create a subcategory
- Use subcategories array to create parent with inline subcategories
"""

import logging
from typing import Annotated, List
from fastapi import APIRouter, Depends, HTTPException, status, Query

from backend.auth.dependencies import get_authenticated_user, AuthenticatedUser
from backend.db.client import get_supabase_client
from backend.services.category_service import (
    get_all_categories,
    get_subcategories,
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


def _build_category_response(cat: dict) -> CategoryResponse:
    """Helper to build CategoryResponse from a category dict."""
    subcategories = None
    if cat.get("subcategories") is not None:
        subcategories = [_build_category_response(sub) for sub in cat.get("subcategories", [])]
    
    return CategoryResponse(
        id=str(cat.get("id")),
        user_id=str(cat.get("user_id")) if cat.get("user_id") else None,
        parent_category_id=str(cat.get("parent_category_id")) if cat.get("parent_category_id") else None,
        key=cat.get("key"),
        name=cat.get("name", ""),
        flow_type=cat.get("flow_type", "outcome"),
        icon=cat.get("icon", ""),
        color=cat.get("color", ""),
        created_at=cat.get("created_at", ""),
        updated_at=cat.get("updated_at"),
        subcategories=subcategories
    )


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
    
    Query parameters:
    - include_subcategories: If true, nest subcategories under their parents
    - parent_only: If true, only return top-level categories (no subcategories in list)
    
    Security:
    - Requires valid authentication token
    - System categories are visible to all users (read-only)
    - User categories filtered by RLS
    """
)
async def list_categories(
    auth_user: Annotated[AuthenticatedUser, Depends(get_authenticated_user)],
    limit: int = 100,
    offset: int = 0,
    include_subcategories: bool = Query(False, description="Nest subcategories under their parents"),
    parent_only: bool = Query(False, description="Only return top-level categories")
) -> CategoryListResponse:
    """List all categories available to the user."""
    logger.info(f"Listing categories for user {auth_user.user_id} (limit={limit}, offset={offset}, include_subcategories={include_subcategories})")
    
    supabase_client = get_supabase_client(auth_user.access_token)
    
    try:
        categories = await get_all_categories(
            supabase_client=supabase_client,
            user_id=auth_user.user_id,
            limit=limit,
            offset=offset,
            include_subcategories=include_subcategories,
            parent_only=parent_only
        )
        
        category_responses = [_build_category_response(cat) for cat in categories]
        
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
    
    Subcategory Support:
    - To create a subcategory, provide parent_category_id
    - To create a parent with inline subcategories, provide subcategories array
    - Cannot do both (max depth is 1)
    
    Security:
    - Requires valid authentication token
    - RLS enforces user can only create categories for themselves
    """
)
async def create_user_category(
    request: CategoryCreateRequest,
    auth_user: Annotated[AuthenticatedUser, Depends(get_authenticated_user)]
) -> CategoryCreateResponse:
    """Create a new user category with optional subcategories."""
    logger.info(
        f"Creating category for user {auth_user.user_id}: "
        f"name={request.name}, flow_type={request.flow_type}, parent={request.parent_category_id}"
    )
    
    supabase_client = get_supabase_client(auth_user.access_token)
    
    try:
        # Convert inline subcategories to dicts
        subcategories_data = None
        if request.subcategories:
            subcategories_data = [
                {"name": sub.name, "icon": sub.icon, "color": sub.color}
                for sub in request.subcategories
            ]
        
        created_category, subcategories_created = await create_category(
            supabase_client=supabase_client,
            user_id=auth_user.user_id,
            name=request.name,
            flow_type=request.flow_type,
            icon=request.icon,
            color=request.color,
            parent_category_id=request.parent_category_id,
            subcategories=subcategories_data
        )
        
        logger.info(f"Category created successfully: id={created_category.get('id')}, subcategories={subcategories_created}")
        
        return CategoryCreateResponse(
            status="CREATED",
            category=_build_category_response(created_category),
            subcategories_created=subcategories_created,
            message=f"Category created successfully" + (f" with {subcategories_created} subcategories" if subcategories_created > 0 else "")
        )
        
    except ValueError as e:
        # Validation errors from service layer
        logger.warning(f"Validation error creating category: {e}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={
                "error": "validation_error",
                "details": str(e)
            }
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
    
    Query parameters:
    - include_subcategories: If true, include subcategories in response
    
    Security:
    - Requires valid authentication token
    - User can view system categories (read-only)
    - User can view their own categories
    """
)
async def get_category(
    category_id: str,
    auth_user: Annotated[AuthenticatedUser, Depends(get_authenticated_user)],
    include_subcategories: bool = Query(False, description="Include subcategories in response")
) -> CategoryResponse:
    """Get details of a single category."""
    logger.info(f"Fetching category {category_id} for user {auth_user.user_id}")
    
    supabase_client = get_supabase_client(auth_user.access_token)
    
    try:
        category = await get_category_by_id(
            supabase_client=supabase_client,
            user_id=auth_user.user_id,
            category_id=category_id,
            include_subcategories=include_subcategories
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
        
        return _build_category_response(category)
        
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


@router.get(
    "/{category_id}/subcategories",
    response_model=List[CategoryResponse],
    status_code=status.HTTP_200_OK,
    summary="List subcategories",
    description="""
    List all subcategories of a given parent category.
    
    Security:
    - Requires valid authentication token
    - User can only view subcategories of their own categories or system categories
    """
)
async def list_subcategories(
    category_id: str,
    auth_user: Annotated[AuthenticatedUser, Depends(get_authenticated_user)]
) -> List[CategoryResponse]:
    """List subcategories of a parent category."""
    logger.info(f"Fetching subcategories of {category_id} for user {auth_user.user_id}")
    
    supabase_client = get_supabase_client(auth_user.access_token)
    
    try:
        # First verify the parent category exists and is accessible
        parent = await get_category_by_id(
            supabase_client=supabase_client,
            user_id=auth_user.user_id,
            category_id=category_id
        )
        
        if not parent:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail={
                    "error": "not_found",
                    "details": f"Category {category_id} not found or not accessible"
                }
            )
        
        subcategories = await get_subcategories(
            supabase_client=supabase_client,
            user_id=auth_user.user_id,
            parent_category_id=category_id
        )
        
        return [_build_category_response(sub) for sub in subcategories]
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to fetch subcategories: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={
                "error": "fetch_error",
                "details": "Failed to retrieve subcategories"
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
    if request.name is None and request.icon is None and request.color is None:
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
            name=request.name,
            icon=request.icon,
            color=request.color
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
            category=_build_category_response(updated_category),
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
    Delete a user category following DB deletion rules (FLOW-TYPE AWARE).
    
    This endpoint supports two deletion modes:
    
    **Default mode (cascade=false, recommended):**
    - Reassigns all transactions to the flow-type-matched 'general' system category
      * If deleted category is 'outcome', reassigns to 'general' outcome category
      * If deleted category is 'income', reassigns to 'general' income category
    - Removes all budget_category links
    - Deletes the category
    
    **Cascade mode (cascade=true):**
    - Deletes all transactions referencing this category
    - Removes all budget_category links
    - Deletes the category
    
    Security:
    - Requires valid authentication token
    - Only the category owner can delete
    - System categories are protected from deletion
    
    DB Rules:
    1. Determine flow_type of deleted category
    2. Find matching 'general' system category (key='general', same flow_type)
    3. Reassign transactions to flow-type-matched general (or cascade delete if requested)
    4. Remove all budget_category links
    5. Delete the category
    """
)
async def delete_user_category(
    category_id: str,
    auth_user: Annotated[AuthenticatedUser, Depends(get_authenticated_user)],
    cascade: bool = False,
) -> CategoryDeleteResponse:
    """
    Delete a user category (with flow-type aware DB rule enforcement).
    
    Args:
        category_id: UUID of the category to delete
        auth_user: Authenticated user from token
        cascade: If True, delete transactions instead of reassigning (default: False)
    
    Returns:
        CategoryDeleteResponse with deletion details
    
    Raises:
        HTTPException 400: If trying to delete system category
        HTTPException 404: If category not found or not accessible
    """
    mode = "CASCADE" if cascade else "REASSIGN"
    logger.info(f"Deleting category {category_id} for user {auth_user.user_id} (mode={mode})")
    
    supabase_client = get_supabase_client(auth_user.access_token)
    
    try:
        success, transactions_reassigned, budget_links_removed, transactions_deleted, subcategories_orphaned = await delete_category(
            supabase_client=supabase_client,
            user_id=auth_user.user_id,
            category_id=category_id,
            cascade=cascade
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
        
        if cascade:
            logger.info(
                f"Category {category_id} deleted successfully (CASCADE): "
                f"{transactions_deleted} transactions deleted, "
                f"{budget_links_removed} budget links removed, "
                f"{subcategories_orphaned} subcategories orphaned"
            )
            message = (
                f"Category deleted successfully. "
                f"{transactions_deleted} transaction(s) deleted, "
                f"{budget_links_removed} budget link(s) removed, "
                f"{subcategories_orphaned} subcategory(ies) orphaned."
            )
        else:
            logger.info(
                f"Category {category_id} deleted successfully (REASSIGN): "
                f"{transactions_reassigned} transactions reassigned to flow-type-matched 'general', "
                f"{budget_links_removed} budget links removed, "
                f"{subcategories_orphaned} subcategories orphaned"
            )
            message = (
                f"Category deleted successfully. "
                f"{transactions_reassigned} transaction(s) reassigned to flow-type-matched 'general', "
                f"{budget_links_removed} budget link(s) removed, "
                f"{subcategories_orphaned} subcategory(ies) orphaned."
            )
        
        return CategoryDeleteResponse(
            status="DELETED",
            category_id=str(category_id),
            transactions_reassigned=transactions_reassigned,
            budget_links_removed=budget_links_removed,
            subcategories_orphaned=subcategories_orphaned,
            message=message
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
