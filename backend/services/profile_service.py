"""
User profile service.

Handles fetching and updating user profile data from Supabase.
Profiles are 1:1 with auth.users and contain user preferences.
"""

import logging
from typing import Any, Dict, Optional, cast

from supabase import Client

logger = logging.getLogger(__name__)


async def get_user_profile(
    supabase_client: Client,
    user_id: str
) -> Optional[Dict[str, Any]]:
    """
    Fetch the user's profile from Supabase.

    The profile contains:
    - country (ISO-2 code, e.g. "GT")
    - currency_preference (e.g. "GTQ")
    - locale
    - first_name, last_name
    - avatar_url

    Args:
        supabase_client: Authenticated Supabase client
        user_id: The authenticated user's ID

    Returns:
        The user's profile dict, or None if not found

    Security:
        - RLS enforces user_id = auth.uid()
        - User can only access their own profile
    """
    logger.debug(f"Fetching profile for user {user_id}")

    result = (
        supabase_client.table("profile")
        .select("*")
        .eq("user_id", user_id)
        .execute()
    )

    if not result.data or len(result.data) == 0:
        logger.warning(f"Profile not found for user {user_id}")
        return None

    profile: Dict[str, Any] = cast(Dict[str, Any], result.data[0])
    logger.info(
        f"Profile found for user {user_id}: "
        f"country={profile.get('country')}, "
        f"currency={profile.get('currency_preference')}"
    )

    return profile


async def create_user_profile(
    supabase_client: Client,
    user_id: str,
    first_name: str,
    currency_preference: str,
    country: str,
    last_name: Optional[str] = None,
    avatar_url: Optional[str] = None,
    locale: str = "system"
) -> Dict[str, Any]:
    """
    Create a new user profile.

    This is typically called during user registration/onboarding.

    Args:
        supabase_client: Authenticated Supabase client
        user_id: The authenticated user's ID
        first_name: User's first name
        currency_preference: Default currency (e.g. "GTQ")
        country: ISO-2 country code (e.g. "GT")
        last_name: User's last name (optional)
        avatar_url: URL to user's avatar (optional)
        locale: User's locale preference (default: "system")

    Returns:
        The created profile record

    Security:
        - RLS enforces user_id = auth.uid()
        - User can only create their own profile
    """
    profile_data = {
        "user_id": user_id,
        "first_name": first_name,
        "currency_preference": currency_preference,
        "country": country,
        "locale": locale
    }

    if last_name:
        profile_data["last_name"] = last_name
    if avatar_url:
        profile_data["avatar_url"] = avatar_url

    logger.info(
        f"Creating profile for user {user_id}: "
        f"country={country}, currency={currency_preference}"
    )

    result = supabase_client.table("profile").insert(profile_data).execute()

    if not result.data or len(result.data) == 0:
        raise Exception("Failed to create profile: no data returned")

    created_profile: Dict[str, Any] = cast(Dict[str, Any], result.data[0])
    logger.info(f"Profile created successfully for user {user_id}")

    return created_profile


async def update_user_profile(
    supabase_client: Client,
    user_id: str,
    **updates: Any
) -> Dict[str, Any]:
    """
    Update user profile fields.

    Args:
        supabase_client: Authenticated Supabase client
        user_id: The authenticated user's ID
        **updates: Fields to update (first_name, currency_preference, etc.)

    Returns:
        The updated profile record

    Raises:
        ValueError: If trying to change currency_preference when user has financial data

    Security:
        - RLS enforces user_id = auth.uid()
        - User can only update their own profile
        - Currency changes are blocked if user has accounts/wishlists/budgets
    """
    # If changing currency_preference, verify user has no financial data
    if 'currency_preference' in updates:
        can_change_result = supabase_client.rpc(
            'can_change_user_currency',
            {'p_user_id': user_id}
        ).execute()

        can_change = can_change_result.data if can_change_result.data is not None else False

        if not can_change:
            raise ValueError(
                "Cannot change currency preference. You have existing accounts, wishlists, or budgets. "
                "Delete all financial data first to change your currency."
            )

    logger.info(f"Updating profile for user {user_id}: {list(updates.keys())}")

    result = (
        supabase_client.table("profile")
        .update(updates)
        .eq("user_id", user_id)
        .execute()
    )

    if not result.data or len(result.data) == 0:
        raise Exception("Failed to update profile: no data returned")

    updated_profile: Dict[str, Any] = cast(Dict[str, Any], result.data[0])
    logger.info(f"Profile updated successfully for user {user_id}")

    return updated_profile


async def delete_user_profile(
    supabase_client: Client,
    user_id: str
) -> Dict[str, Any]:
    """
    Delete (anonymize) user profile.

    IMPORTANT:
    - Profiles are NOT physically deleted while user exists in auth_users
    - Instead, we clear/anonymize personal fields while keeping the row
    - This maintains internal consistency for localization data (country, currency)

    The delete operation:
    - Clears first_name, last_name, avatar_url
    - Keeps country and currency_preference (needed by agents)
    - Sets first_name to "Deleted User" for system consistency

    Args:
        supabase_client: Authenticated Supabase client
        user_id: The authenticated user's ID

    Returns:
        The anonymized profile record

    Security:
        - RLS enforces user_id = auth.uid()
        - User can only delete/anonymize their own profile
    """
    logger.info(f"Anonymizing profile for user {user_id}")

    # Anonymize personal fields but keep localization data
    anonymized_data = {
        "first_name": "Deleted User",
        "last_name": None,
        "avatar_url": None,
    }

    result = (
        supabase_client.table("profile")
        .update(anonymized_data)
        .eq("user_id", user_id)
        .execute()
    )

    if not result.data or len(result.data) == 0:
        raise Exception("Failed to anonymize profile: no data returned")

    anonymized_profile: Dict[str, Any] = cast(Dict[str, Any], result.data[0])
    logger.info(f"Profile anonymized successfully for user {user_id}")

    return anonymized_profile
