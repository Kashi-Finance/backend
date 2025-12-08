"""
Auth API endpoints.

Provides endpoints for authentication-related operations:
- GET /auth/me - Get authenticated user identity

All endpoints require valid Bearer token authentication.
"""

import logging
from typing import Annotated, Any, cast

from fastapi import APIRouter, Depends, HTTPException, status
from jwt import decode

from backend.auth.dependencies import (
    AuthenticatedUser,
    get_authenticated_user,
    get_jwks_client,
)
from backend.config import settings
from backend.db.client import get_supabase_client
from backend.schemas.auth import AuthMeResponse, ProfileSummary

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/auth", tags=["auth"])


def _extract_email_from_token(token: str) -> str | None:
    """
    Extract email claim from JWT token.

    The token is already verified by get_authenticated_user, so we just decode
    without verification to extract additional claims.
    """
    try:
        # We can decode without verification since the token is already verified
        # by the dependency. We just need to extract the email claim.
        jwks_client = get_jwks_client()
        signing_key = jwks_client.get_signing_key_from_jwt(token)
        issuer = f"{settings.SUPABASE_URL.rstrip('/')}/auth/v1"

        payload = decode(
            token,
            signing_key.key,
            algorithms=["ES256"],
            audience="authenticated",
            issuer=issuer,
        )
        email = payload.get("email")
        return str(email) if email is not None else None
    except Exception as e:
        logger.warning(f"Could not extract email from token: {e}")
        return None


async def _get_profile_summary(
    supabase_client: Any,
    user_id: str
) -> ProfileSummary | None:
    """
    Fetch condensed profile for auth/me response.

    Returns None if profile doesn't exist (new user who hasn't created profile).
    """
    try:
        response = supabase_client.table("profile").select(
            "first_name, last_name, avatar_url, country, currency_preference, locale"
        ).eq("user_id", user_id).execute()

        if response.data and len(response.data) > 0:
            profile = cast(dict[str, Any], response.data[0])
            return ProfileSummary(
                first_name=profile.get("first_name", ""),
                last_name=profile.get("last_name"),
                avatar_url=profile.get("avatar_url"),
                country=profile.get("country", "GT"),
                currency_preference=profile.get("currency_preference", "GTQ"),
                locale=profile.get("locale", "system"),
            )
        else:
            logger.debug(f"No profile found for user_id={user_id}")
            return None

    except Exception as e:
        logger.error(f"Error fetching profile for auth/me: {e}")
        return None


@router.get(
    "/me",
    response_model=AuthMeResponse,
    status_code=status.HTTP_200_OK,
    summary="Get authenticated user identity",
    description="""
    Get the authenticated user's core identity for session hydration.

    This endpoint:
    - Validates the bearer token
    - Returns user_id and email from JWT claims
    - Includes profile summary if profile exists

    Use this for:
    - App boot to hydrate global session state
    - Confirming token is still valid
    - Getting user identity before profile exists

    Note: Profile may be null for new users who haven't completed onboarding.

    Security:
    - Requires valid Authorization Bearer token
    - RLS ensures users only see their own data
    """
)
async def get_auth_me(
    auth_user: Annotated[AuthenticatedUser, Depends(get_authenticated_user)]
) -> AuthMeResponse:
    """
    Get the authenticated user's identity.
    """
    try:
        # Extract email from token
        email = _extract_email_from_token(auth_user.access_token)

        # Fetch profile summary
        supabase_client = get_supabase_client(auth_user.access_token)
        profile = await _get_profile_summary(supabase_client, auth_user.user_id)

        return AuthMeResponse(
            user_id=auth_user.user_id,
            email=email,
            profile=profile,
        )

    except Exception as e:
        logger.error(f"Error in get_auth_me for user_id={auth_user.user_id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={"error": "auth_me_failed", "details": str(e)}
        )
