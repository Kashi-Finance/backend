"""
Profile CRUD API endpoints.

Provides endpoints for managing user profile information and preferences.

Profiles contain user settings like country, currency preference, and personal info.
Each profile is 1:1 with an auth.users record.
"""

import logging
from typing import Annotated, Any
from fastapi import APIRouter, Depends, HTTPException, status
from postgrest.exceptions import APIError

from backend.auth.dependencies import get_authenticated_user, AuthenticatedUser
from backend.db.client import get_supabase_client
from backend.services import (
    get_user_profile,
    update_user_profile,
    delete_user_profile,
    create_user_profile,
)
from backend.schemas.profile import (
    ProfileResponse,
    ProfileUpdateRequest,
    ProfileUpdateResponse,
    ProfileDeleteResponse,
    ProfileCreateRequest,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/profile", tags=["profile"])


@router.get(
    "",
    response_model=ProfileResponse,
    status_code=status.HTTP_200_OK,
    summary="Get user profile",
    description="""
    Retrieve the authenticated user's profile.
    
    This endpoint:
    - Returns user's personal information and preferences
    - Only accessible to the profile owner (RLS enforced)
    - Used to load user settings and localization preferences
    
    Security:
    - Requires valid Authorization Bearer token
    - RLS ensures users only see their own profile
    """
)
async def get_profile(
    auth_user: Annotated[AuthenticatedUser, Depends(get_authenticated_user)]
) -> ProfileResponse:
    """
    Get the authenticated user's profile.
    
    
    Auth
    - Handled by get_authenticated_user dependency
    - Extracts user_id and access_token from Supabase Auth
    
    Parse/Validate Request
    - No request body (GET endpoint)

    Domain & Intent Filter
    - This is a straightforward profile fetch request
    - No domain filtering needed

    Call Service
    - Call get_user_profile() service function
    - Service handles RLS enforcement

    Map Output -> ResponseModel
    - Convert profile data to ProfileResponse
    
    Persistence
    - Read-only operation (no persistence needed)
    """
    
    logger.info(f"Fetching profile for user {auth_user.user_id}")
    
    # Create authenticated Supabase client
    supabase_client = get_supabase_client(auth_user.access_token)
    
    try:
        # Fetch profile from database (RLS enforced)
        profile = await get_user_profile(
            supabase_client=supabase_client,
            user_id=auth_user.user_id
        )
        
        if not profile:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail={
                    "error": "not_found",
                    "details": "Profile not found for this user"
                }
            )
        
        logger.info(f"Returning profile for user {auth_user.user_id}")
        
        # Helper to coerce optional DB values into strings for required fields
        def _as_str(val: Any) -> str:
            return str(val) if val is not None else ""

        return ProfileResponse(
            user_id=_as_str(profile.get("user_id")),
            first_name=_as_str(profile.get("first_name")),
            last_name=profile.get("last_name") if profile.get("last_name") is not None else None,
            avatar_url=profile.get("avatar_url") if profile.get("avatar_url") is not None else None,
            currency_preference=_as_str(profile.get("currency_preference")),
            locale=_as_str(profile.get("locale")),
            country=_as_str(profile.get("country")),
            created_at=_as_str(profile.get("created_at")),
            updated_at=_as_str(profile.get("updated_at")),
        )
        
    except HTTPException:
        # Re-raise HTTP exceptions (like 404)
        raise
    except Exception as e:
        logger.error(f"Failed to fetch profile for user {auth_user.user_id}: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={
                "error": "fetch_error",
                "details": "Failed to retrieve profile from database"
            }
        )


@router.patch(
    "",
    response_model=ProfileUpdateResponse,
    status_code=status.HTTP_200_OK,
    summary="Update user profile",
    description="""
    Update the authenticated user's profile.
    
    This endpoint:
    - Accepts partial updates (only provided fields are updated)
    - Returns the complete updated profile
    - Requires valid Authorization Bearer token
    
    Security:
    - Only the profile owner can update their profile
    - RLS enforces user_id = auth.uid()
    """
)
async def update_profile(
    request: ProfileUpdateRequest,
    auth_user: Annotated[AuthenticatedUser, Depends(get_authenticated_user)]
) -> ProfileUpdateResponse:
    """
    Update the user's profile.

    Auth
    - Handled by get_authenticated_user dependency
    - Extracts user_id and access_token from Supabase Auth token

    Parse/Validate Request
    - FastAPI validates ProfileUpdateRequest automatically
    - At least one field should be provided for a valid update

    Domain & Intent Filter
    - Validate that this is a valid profile update request
    - Check that at least one field is being updated

    Call Service
    - Call update_user_profile() service function
    - Service handles RLS enforcement

    Map Output -> ResponseModel
    - Convert updated profile to ProfileResponse
    - Return ProfileUpdateResponse with updated profile

    Persistence
    - Service layer handles persistence via authenticated Supabase client
    """
    
    logger.info(f"Updating profile for user {auth_user.user_id}")
    
    # Extract only non-None fields from request
    updates = request.model_dump(exclude_none=True)
    
    if not updates:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={
                "error": "invalid_request",
                "details": "At least one field must be provided for update"
            }
        )
    
    # Create authenticated Supabase client
    supabase_client = get_supabase_client(auth_user.access_token)
    
    try:
        # Update profile (service handles RLS enforcement)
        updated_profile = await update_user_profile(
            supabase_client=supabase_client,
            user_id=auth_user.user_id,
            **updates
        )
        
        if not updated_profile:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail={
                    "error": "not_found",
                    "details": "Profile not found for this user"
                }
            )
        
        # Map to response model
        # Helper to coerce optional DB values into strings for required fields
        def _as_str(val: Any) -> str:
            return str(val) if val is not None else ""

        profile_response = ProfileResponse(
            user_id=_as_str(updated_profile.get("user_id")),
            first_name=_as_str(updated_profile.get("first_name")),
            last_name=updated_profile.get("last_name") if updated_profile.get("last_name") is not None else None,
            avatar_url=updated_profile.get("avatar_url") if updated_profile.get("avatar_url") is not None else None,
            currency_preference=_as_str(updated_profile.get("currency_preference")),
            locale=_as_str(updated_profile.get("locale")),
            country=_as_str(updated_profile.get("country")),
            created_at=_as_str(updated_profile.get("created_at")),
            updated_at=_as_str(updated_profile.get("updated_at")),
        )
        
        logger.info(f"Profile updated successfully for user {auth_user.user_id}")
        
        return ProfileUpdateResponse(
            status="UPDATED",
            profile=profile_response,
            message="Profile updated successfully"
        )
        
    except HTTPException:
        # Re-raise HTTP exceptions
        raise
    except ValueError as e:
        logger.error(f"Invalid profile data: {e}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={
                "error": "invalid_request",
                "details": str(e)
            }
        )
    except Exception as e:
        logger.error(f"Failed to update profile for user {auth_user.user_id}: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={
                "error": "update_error",
                "details": "Failed to update profile"
            }
        )


@router.post(
    "",
    response_model=ProfileResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create user profile",
    description="Create a profile for the authenticated user."
)
async def create_profile(
    request: ProfileCreateRequest,
    auth_user: Annotated[AuthenticatedUser, Depends(get_authenticated_user)]
) -> ProfileResponse:
    """
    Create the authenticated user's profile.
    """
    logger.info(f"Creating profile for user {auth_user.user_id}")

    supabase_client = get_supabase_client(auth_user.access_token)

    try:
        created = await create_user_profile(
            supabase_client=supabase_client,
            user_id=auth_user.user_id,
            first_name=request.first_name,
            currency_preference=request.currency_preference,
            country=request.country,
            last_name=request.last_name,
            avatar_url=request.avatar_url,
            locale=request.locale or "system",
        )

        # Helper to coerce optional DB values into strings for required fields
        def _as_str(val: Any) -> str:
            return str(val) if val is not None else ""

        return ProfileResponse(
            user_id=_as_str(created.get("user_id")),
            first_name=_as_str(created.get("first_name")),
            last_name=created.get("last_name") if created.get("last_name") is not None else None,
            avatar_url=created.get("avatar_url") if created.get("avatar_url") is not None else None,
            currency_preference=_as_str(created.get("currency_preference")),
            locale=_as_str(created.get("locale")),
            country=_as_str(created.get("country")),
            created_at=_as_str(created.get("created_at")),
            updated_at=_as_str(created.get("updated_at")),
        )

    except APIError as e:
        # Handle database constraint violations (e.g. duplicate key)
        if e.code == "23505":  # unique_violation
            logger.warning(f"Profile already exists for user {auth_user.user_id}")
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail={
                    "error": "profile_exists",
                    "details": "Profile already exists for this user. Use PATCH /profile to update it."
                }
            )
        # Re-raise other APIErrors as 500
        logger.error(f"Database error creating profile for user {auth_user.user_id}: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={"error": "create_error", "details": "Failed to create profile"}
        )
    except Exception as e:
        logger.error(f"Failed to create profile for user {auth_user.user_id}: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={"error": "create_error", "details": "Failed to create profile"}
        )


@router.delete(
    "",
    response_model=ProfileDeleteResponse,
    status_code=status.HTTP_200_OK,
    summary="Delete (anonymize) user profile",
    description="""
    Delete (anonymize) the authenticated user's profile.
    
    IMPORTANT: Following DB documentation delete rule:
    - Profile is NOT physically deleted
    - Instead, personal fields are cleared/anonymized
    - Country and currency_preference are kept for system consistency
    - The profile row remains to support localization for agents
    
    This endpoint:
    - Clears first_name, last_name, avatar_url
    - Sets first_name to "Deleted User"
    - Keeps country and currency_preference
    - Requires valid Authorization Bearer token
    
    Security:
    - Only the profile owner can delete their profile
    - RLS enforces user_id = auth.uid()
    """
)
async def delete_profile(
    auth_user: Annotated[AuthenticatedUser, Depends(get_authenticated_user)]
) -> ProfileDeleteResponse:
    """
    Delete (anonymize) the user's profile.
    
    **6-STEP ENDPOINT FLOW:**
    
    Step 1: Auth
    - Handled by get_authenticated_user dependency
    - Extracts user_id and access_token from Supabase Auth token
    
    Step 2: Parse/Validate Request
    - No request body (DELETE endpoint)
    
    Step 3: Domain & Intent Filter
    - Validate that this is a valid profile delete request
    - Check that profile exists and belongs to authenticated user
    
    Step 4: Call Service
    - Call delete_user_profile() service function
    - Service handles RLS enforcement and anonymization
    
    Step 5: Map Output -> ResponseModel
    - Return ProfileDeleteResponse
    
    Step 6: Persistence
    - Service layer handles anonymization via authenticated Supabase client
    - Profile is updated (not deleted) per DB delete rule
    """
    
    logger.info(f"Deleting (anonymizing) profile for user {auth_user.user_id}")
    
    # Create authenticated Supabase client
    supabase_client = get_supabase_client(auth_user.access_token)
    
    try:
        # Delete (anonymize) profile (service handles RLS enforcement)
        anonymized_profile = await delete_user_profile(
            supabase_client=supabase_client,
            user_id=auth_user.user_id,
        )
        
        if not anonymized_profile:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail={
                    "error": "not_found",
                    "details": "Profile not found for this user"
                }
            )
        
        logger.info(f"Profile anonymized successfully for user {auth_user.user_id}")
        
        return ProfileDeleteResponse(
            status="DELETED",
            message="Profile deleted successfully"
        )
        
    except HTTPException:
        # Re-raise HTTP exceptions
        raise
    except Exception as e:
        logger.error(f"Failed to delete profile for user {auth_user.user_id}: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={
                "error": "delete_error",
                "details": "Failed to delete profile"
            }
        )
