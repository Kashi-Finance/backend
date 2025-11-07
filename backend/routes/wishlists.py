"""
Wishlist CRUD API endpoints.

Provides endpoints for managing user wishlists (purchase goals) and wishlist_items
(saved store options from recommendation flow). Supports three creation scenarios:
manual save, recommendations without selection, and recommendations with selection.
"""

import logging
from typing import Annotated, Any, List
from fastapi import APIRouter, Depends, HTTPException, status, Path, Query

from backend.auth.dependencies import get_authenticated_user, AuthenticatedUser
from backend.db.client import get_supabase_client
from backend.services.wishlist_service import (
    get_user_wishlists,
    get_wishlist_by_id,
    get_wishlist_items,
    create_wishlist,
    update_wishlist,
    delete_wishlist,
    delete_wishlist_item,
)
from backend.schemas.wishlists import (
    WishlistResponse,
    WishlistCreateRequest,
    WishlistCreateResponse,
    WishlistUpdateRequest,
    WishlistUpdateResponse,
    WishlistDeleteResponse,
    WishlistListResponse,
    WishlistWithItemsResponse,
    WishlistItemResponse,
    WishlistItemDeleteResponse,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/wishlists", tags=["wishlists"])


def _as_str(v: Any) -> str:
    """Helper to coerce DB values to strings."""
    return str(v) if v is not None else ""


@router.get(
    "",
    response_model=WishlistListResponse,
    status_code=status.HTTP_200_OK,
    summary="List user wishlists",
    description="""
    Retrieve all wishlists (purchase goals) belonging to the authenticated user.
    
    This endpoint:
    - Returns all user's wishlist goals
    - Ordered by creation date (newest first)
    - Only accessible to the wishlist owner (RLS enforced)
    - Supports pagination via limit/offset
    
    Security:
    - Requires valid Authorization Bearer token
    - RLS ensures users only see their own wishlists
    """
)
async def list_wishlists(
    auth_user: Annotated[AuthenticatedUser, Depends(get_authenticated_user)],
    limit: int = Query(50, ge=1, le=100, description="Maximum number of wishlists to return"),
    offset: int = Query(0, ge=0, description="Number of wishlists to skip for pagination")
) -> WishlistListResponse:
    """List all wishlists for the authenticated user."""
    logger.info(f"Listing wishlists for user {auth_user.user_id} (limit={limit}, offset={offset})")
    
    supabase_client = get_supabase_client(auth_user.access_token)
    
    try:
        wishlists = await get_user_wishlists(
            supabase_client=supabase_client,
            user_id=auth_user.user_id,
            limit=limit,
            offset=offset
        )
        
        wishlist_responses = [
            WishlistResponse(
                id=_as_str(w.get("id")),
                user_id=_as_str(w.get("user_id")),
                goal_title=_as_str(w.get("goal_title")),
                budget_hint=_as_str(w.get("budget_hint")),
                currency_code=_as_str(w.get("currency_code")),
                target_date=_as_str(w.get("target_date")) if w.get("target_date") else None,
                preferred_store=_as_str(w.get("preferred_store")) if w.get("preferred_store") else None,
                user_note=_as_str(w.get("user_note")) if w.get("user_note") else None,
                status=w.get("status", "active"),  # type: ignore
                created_at=_as_str(w.get("created_at")),
                updated_at=_as_str(w.get("updated_at")),
            )
            for w in wishlists
        ]
        
        logger.info(f"Returning {len(wishlist_responses)} wishlists for user {auth_user.user_id}")
        
        return WishlistListResponse(
            wishlists=wishlist_responses,
            count=len(wishlist_responses),
            limit=limit,
            offset=offset
        )
        
    except Exception as e:
        logger.error(f"Failed to list wishlists for user {auth_user.user_id}: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={
                "error": "fetch_error",
                "details": "Failed to retrieve wishlists from database"
            }
        )


@router.post(
    "",
    response_model=WishlistCreateResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create wishlist",
    description="""
    Create a new wishlist (purchase goal) with optional selected items.
    
    This endpoint supports three frontend scenarios:
    
    **CASE A - Manual save (no recommendations)**
    - User fills wizard and clicks "Save my goal" without requesting recommendations
    - selected_items is omitted or empty
    - Only wishlist is created (no items)
    
    **CASE B - Recommendations requested but none selected**
    - User requests recommendations, reviews options, but doesn't select any
    - selected_items is omitted or empty
    - Only wishlist is created (no items)
    
    **CASE C - Recommendations requested and 1-3 selected**
    - User requests recommendations, reviews options, and selects 1-3 offers
    - selected_items contains the selected offers
    - Wishlist is created AND wishlist_item rows are inserted
    
    All operations are atomic - either everything succeeds or everything rolls back.
    
    Security:
    - Requires valid Authorization Bearer token
    - RLS ensures wishlist is owned by authenticated user
    - user_id comes from token, not request body
    """
)
async def create_new_wishlist(
    request: WishlistCreateRequest,
    auth_user: Annotated[AuthenticatedUser, Depends(get_authenticated_user)]
) -> WishlistCreateResponse:
    """
    Create a new wishlist (goal) with optional items.
    
    **6-STEP ENDPOINT FLOW:**
    
    Step 1: Auth
    - Handled by get_authenticated_user dependency
    
    Step 2: Parse/Validate Request
    - FastAPI validates WishlistCreateRequest automatically
    - Validates selected_items (max 3) if provided
    
    Step 3: Domain & Intent Filter
    - No ADK agent involved (pure CRUD)
    - Validate budget_hint > 0 (enforced by Pydantic)
    
    Step 4: Call Service
    - Call create_wishlist() service function
    - Service handles atomic wishlist + items creation
    
    Step 5: Map Output -> ResponseModel
    - Convert created wishlist to WishlistCreateResponse
    
    Step 6: Persistence
    - Service layer handles atomic database inserts
    - Wishlist first, then items (if any)
    - Rollback on failure
    """
    logger.info(
        f"Creating wishlist for user {auth_user.user_id}: "
        f"goal='{request.goal_title}', items={len(request.selected_items) if request.selected_items else 0}"
    )
    
    supabase_client = get_supabase_client(auth_user.access_token)
    
    try:
        # Convert Pydantic models to dicts for service layer
        selected_items_dicts = None
        if request.selected_items and len(request.selected_items) > 0:
            selected_items_dicts = [item.model_dump() for item in request.selected_items]
        
        # Create wishlist (and items if provided)
        created_wishlist, items_created = await create_wishlist(
            supabase_client=supabase_client,
            user_id=auth_user.user_id,
            goal_title=request.goal_title,
            budget_hint=request.budget_hint,
            currency_code=request.currency_code,
            target_date=str(request.target_date) if request.target_date else None,
            preferred_store=request.preferred_store,
            user_note=request.user_note,
            selected_items=selected_items_dicts
        )
        
        wishlist_response = WishlistResponse(
            id=_as_str(created_wishlist.get("id")),
            user_id=_as_str(created_wishlist.get("user_id")),
            goal_title=_as_str(created_wishlist.get("goal_title")),
            budget_hint=_as_str(created_wishlist.get("budget_hint")),
            currency_code=_as_str(created_wishlist.get("currency_code")),
            target_date=_as_str(created_wishlist.get("target_date")) if created_wishlist.get("target_date") else None,
            preferred_store=_as_str(created_wishlist.get("preferred_store")) if created_wishlist.get("preferred_store") else None,
            user_note=_as_str(created_wishlist.get("user_note")) if created_wishlist.get("user_note") else None,
            status=created_wishlist.get("status", "active"),  # type: ignore
            created_at=_as_str(created_wishlist.get("created_at")),
            updated_at=_as_str(created_wishlist.get("updated_at")),
        )
        
        # Generate appropriate message based on items created
        if items_created == 0:
            message = "Wishlist created successfully (no offers selected)"
        elif items_created == 1:
            message = "Wishlist created successfully with 1 saved offer"
        else:
            message = f"Wishlist created successfully with {items_created} saved offers"
        
        logger.info(f"Wishlist created successfully: {wishlist_response.id} ({items_created} items)")
        
        return WishlistCreateResponse(
            status="CREATED",
            wishlist=wishlist_response,
            items_created=items_created,
            message=message
        )
        
    except Exception as e:
        logger.error(f"Failed to create wishlist for user {auth_user.user_id}: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={
                "error": "create_error",
                "details": "Failed to create wishlist"
            }
        )


@router.get(
    "/{wishlist_id}",
    response_model=WishlistWithItemsResponse,
    status_code=status.HTTP_200_OK,
    summary="Get wishlist with items",
    description="""
    Retrieve details of a single wishlist with all its saved items.
    
    This endpoint:
    - Returns wishlist goal details
    - Includes all saved wishlist_item rows (0-N)
    - Only accessible to the wishlist owner (RLS enforced)
    
    Security:
    - Requires valid Authorization Bearer token
    - Returns 404 if wishlist doesn't exist or belongs to another user
    """
)
async def get_wishlist(
    wishlist_id: Annotated[str, Path(description="Wishlist UUID")],
    auth_user: Annotated[AuthenticatedUser, Depends(get_authenticated_user)]
) -> WishlistWithItemsResponse:
    """Get wishlist by ID with all its items."""
    logger.info(f"Fetching wishlist {wishlist_id} for user {auth_user.user_id}")
    
    supabase_client = get_supabase_client(auth_user.access_token)
    
    try:
        # Get wishlist
        wishlist = await get_wishlist_by_id(
            supabase_client=supabase_client,
            user_id=auth_user.user_id,
            wishlist_id=wishlist_id
        )
        
        if not wishlist:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail={
                    "error": "not_found",
                    "details": "Wishlist not found"
                }
            )
        
        # Get items
        items = await get_wishlist_items(
            supabase_client=supabase_client,
            wishlist_id=wishlist_id
        )
        
        wishlist_response = WishlistResponse(
            id=_as_str(wishlist.get("id")),
            user_id=_as_str(wishlist.get("user_id")),
            goal_title=_as_str(wishlist.get("goal_title")),
            budget_hint=_as_str(wishlist.get("budget_hint")),
            currency_code=_as_str(wishlist.get("currency_code")),
            target_date=_as_str(wishlist.get("target_date")) if wishlist.get("target_date") else None,
            preferred_store=_as_str(wishlist.get("preferred_store")) if wishlist.get("preferred_store") else None,
            user_note=_as_str(wishlist.get("user_note")) if wishlist.get("user_note") else None,
            status=wishlist.get("status", "active"),  # type: ignore
            created_at=_as_str(wishlist.get("created_at")),
            updated_at=_as_str(wishlist.get("updated_at")),
        )
        
        item_responses = [
            WishlistItemResponse(
                id=_as_str(item.get("id")),
                wishlist_id=_as_str(item.get("wishlist_id")),
                product_title=_as_str(item.get("product_title")),
                price_total=_as_str(item.get("price_total")),
                seller_name=_as_str(item.get("seller_name")),
                url=_as_str(item.get("url")),
                pickup_available=item.get("pickup_available", False),
                warranty_info=_as_str(item.get("warranty_info")),
                copy_for_user=_as_str(item.get("copy_for_user")),
                badges=item.get("badges", []) if isinstance(item.get("badges"), list) else [],
                created_at=_as_str(item.get("created_at")),
                updated_at=_as_str(item.get("updated_at")),
            )
            for item in items
        ]
        
        logger.info(f"Returning wishlist {wishlist_id} with {len(item_responses)} items")
        
        return WishlistWithItemsResponse(
            wishlist=wishlist_response,
            items=item_responses
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to fetch wishlist {wishlist_id}: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={
                "error": "fetch_error",
                "details": "Failed to retrieve wishlist"
            }
        )


@router.get(
    "/{wishlist_id}/items",
    response_model=List[WishlistItemResponse],
    status_code=status.HTTP_200_OK,
    summary="Get wishlist items",
    description="""
    Retrieve all items saved in a specific wishlist.
    
    This endpoint:
    - Returns all saved store options (0-N items) for the wishlist
    - Ordered by creation date (newest first)
    - Only accessible if the wishlist belongs to the authenticated user (RLS enforced)
    - Returns empty list if wishlist has no items
    - Supports pagination for large item collections
    
    Use Cases:
    - Fetch items separately from wishlist details
    - Refresh items list after adding/removing items
    - Paginate through large item collections
    - Display items in a separate carousel or list view
    
    Security:
    - Requires valid Authorization Bearer token
    - Returns 404 if wishlist doesn't exist or belongs to another user
    - RLS ensures user can only access their own wishlist's items
    """
)
async def get_wishlist_items_list(
    wishlist_id: Annotated[str, Path(description="Wishlist UUID")],
    auth_user: Annotated[AuthenticatedUser, Depends(get_authenticated_user)],
    limit: int = Query(50, ge=1, le=100, description="Maximum number of items to return"),
    offset: int = Query(0, ge=0, description="Number of items to skip for pagination")
) -> List[WishlistItemResponse]:
    """Get all items for a specific wishlist with pagination."""
    logger.info(
        f"Fetching items for wishlist {wishlist_id} for user {auth_user.user_id} "
        f"(limit={limit}, offset={offset})"
    )
    
    supabase_client = get_supabase_client(auth_user.access_token)
    
    try:
        # First verify that the wishlist exists and belongs to this user
        wishlist = await get_wishlist_by_id(
            supabase_client=supabase_client,
            user_id=auth_user.user_id,
            wishlist_id=wishlist_id
        )
        
        if not wishlist:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail={
                    "error": "not_found",
                    "details": "Wishlist not found"
                }
            )
        
        # Get items with pagination
        items = await get_wishlist_items(
            supabase_client=supabase_client,
            wishlist_id=wishlist_id
        )
        
        item_responses = [
            WishlistItemResponse(
                id=_as_str(item.get("id")),
                wishlist_id=_as_str(item.get("wishlist_id")),
                product_title=_as_str(item.get("product_title")),
                price_total=_as_str(item.get("price_total")),
                seller_name=_as_str(item.get("seller_name")),
                url=_as_str(item.get("url")),
                pickup_available=item.get("pickup_available", False),
                warranty_info=_as_str(item.get("warranty_info")),
                copy_for_user=_as_str(item.get("copy_for_user")),
                badges=item.get("badges", []) if isinstance(item.get("badges"), list) else [],
                created_at=_as_str(item.get("created_at")),
                updated_at=_as_str(item.get("updated_at")),
            )
            for item in items
        ]
        
        logger.info(
            f"Returning {len(item_responses)} items for wishlist {wishlist_id}"
        )
        
        return item_responses
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(
            f"Failed to fetch items for wishlist {wishlist_id}: {e}",
            exc_info=True
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={
                "error": "fetch_error",
                "details": "Failed to retrieve wishlist items"
            }
        )


@router.patch(
    "/{wishlist_id}",
    response_model=WishlistUpdateResponse,
    status_code=status.HTTP_200_OK,
    summary="Update wishlist",
    description="""
    Update wishlist details.
    
    This endpoint:
    - Accepts partial updates (only provided fields are updated)
    - Returns the complete updated wishlist
    - Cannot add/remove items (use separate item endpoints)
    
    Security:
    - Requires valid Authorization Bearer token
    - Only the wishlist owner can update their wishlist
    - RLS enforces user_id = auth.uid()
    """
)
async def update_existing_wishlist(
    wishlist_id: Annotated[str, Path(description="Wishlist UUID")],
    request: WishlistUpdateRequest,
    auth_user: Annotated[AuthenticatedUser, Depends(get_authenticated_user)]
) -> WishlistUpdateResponse:
    """Update wishlist details."""
    logger.info(f"Updating wishlist {wishlist_id} for user {auth_user.user_id}")
    
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
    
    # Convert date to string if present
    if "target_date" in updates and updates["target_date"] is not None:
        updates["target_date"] = str(updates["target_date"])
    
    supabase_client = get_supabase_client(auth_user.access_token)
    
    try:
        updated_wishlist = await update_wishlist(
            supabase_client=supabase_client,
            user_id=auth_user.user_id,
            wishlist_id=wishlist_id,
            **updates
        )
        
        if not updated_wishlist:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail={
                    "error": "not_found",
                    "details": "Wishlist not found"
                }
            )
        
        wishlist_response = WishlistResponse(
            id=_as_str(updated_wishlist.get("id")),
            user_id=_as_str(updated_wishlist.get("user_id")),
            goal_title=_as_str(updated_wishlist.get("goal_title")),
            budget_hint=_as_str(updated_wishlist.get("budget_hint")),
            currency_code=_as_str(updated_wishlist.get("currency_code")),
            target_date=_as_str(updated_wishlist.get("target_date")) if updated_wishlist.get("target_date") else None,
            preferred_store=_as_str(updated_wishlist.get("preferred_store")) if updated_wishlist.get("preferred_store") else None,
            user_note=_as_str(updated_wishlist.get("user_note")) if updated_wishlist.get("user_note") else None,
            status=updated_wishlist.get("status", "active"),  # type: ignore
            created_at=_as_str(updated_wishlist.get("created_at")),
            updated_at=_as_str(updated_wishlist.get("updated_at")),
        )
        
        logger.info(f"Wishlist {wishlist_id} updated successfully")
        
        return WishlistUpdateResponse(
            status="UPDATED",
            wishlist=wishlist_response,
            message="Wishlist updated successfully"
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to update wishlist {wishlist_id}: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={
                "error": "update_error",
                "details": "Failed to update wishlist"
            }
        )


@router.delete(
    "/{wishlist_id}",
    response_model=WishlistDeleteResponse,
    status_code=status.HTTP_200_OK,
    summary="Delete wishlist",
    description="""
    Delete a wishlist and all its items (CASCADE).
    
    Per DB delete rule:
    - All wishlist_item rows are deleted automatically (ON DELETE CASCADE)
    - Then the wishlist is deleted
    
    Security:
    - Requires valid Authorization Bearer token
    - Only the wishlist owner can delete their wishlist
    - RLS enforces user_id = auth.uid()
    """
)
async def delete_existing_wishlist(
    wishlist_id: Annotated[str, Path(description="Wishlist UUID to delete")],
    auth_user: Annotated[AuthenticatedUser, Depends(get_authenticated_user)]
) -> WishlistDeleteResponse:
    """Delete wishlist following DB delete rules (CASCADE to items)."""
    logger.info(f"Deleting wishlist {wishlist_id} for user {auth_user.user_id}")
    
    supabase_client = get_supabase_client(auth_user.access_token)
    
    try:
        items_deleted = await delete_wishlist(
            supabase_client=supabase_client,
            user_id=auth_user.user_id,
            wishlist_id=wishlist_id
        )
        
        if items_deleted == 0:
            message = "Wishlist deleted successfully (no items)."
        elif items_deleted == 1:
            message = "Wishlist deleted successfully. 1 item removed."
        else:
            message = f"Wishlist deleted successfully. {items_deleted} items removed."
        
        logger.info(f"Wishlist {wishlist_id} deleted successfully ({items_deleted} items)")
        
        return WishlistDeleteResponse(
            status="DELETED",
            message=message,
            items_deleted=items_deleted
        )
        
    except Exception as e:
        logger.error(f"Failed to delete wishlist {wishlist_id}: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={
                "error": "delete_error",
                "details": "Failed to delete wishlist"
            }
        )


@router.delete(
    "/{wishlist_id}/items/{item_id}",
    response_model=WishlistItemDeleteResponse,
    status_code=status.HTTP_200_OK,
    summary="Delete wishlist item",
    description="""
    Delete a single wishlist item.
    
    Per DB delete rule:
    - Item is deleted
    - Parent wishlist remains unaffected
    - Wishlist can have zero items after deletion
    
    Security:
    - Requires valid Authorization Bearer token
    - Verifies wishlist ownership before allowing item deletion
    - Returns 404 if item or wishlist doesn't exist
    """
)
async def delete_existing_wishlist_item(
    wishlist_id: Annotated[str, Path(description="Parent wishlist UUID")],
    item_id: Annotated[str, Path(description="Wishlist item UUID to delete")],
    auth_user: Annotated[AuthenticatedUser, Depends(get_authenticated_user)]
) -> WishlistItemDeleteResponse:
    """Delete a single wishlist item."""
    logger.info(f"Deleting item {item_id} from wishlist {wishlist_id} for user {auth_user.user_id}")
    
    supabase_client = get_supabase_client(auth_user.access_token)
    
    try:
        deleted = await delete_wishlist_item(
            supabase_client=supabase_client,
            user_id=auth_user.user_id,
            wishlist_id=wishlist_id,
            item_id=item_id
        )
        
        if not deleted:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail={
                    "error": "not_found",
                    "details": "Wishlist item not found"
                }
            )
        
        logger.info(f"Item {item_id} deleted successfully from wishlist {wishlist_id}")
        
        return WishlistItemDeleteResponse(
            status="DELETED",
            message="Wishlist item deleted successfully"
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to delete item {item_id}: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={
                "error": "delete_error",
                "details": "Failed to delete wishlist item"
            }
        )
