"""
Supabase client factory with RLS enforcement.

This module provides authenticated Supabase clients that automatically
enforce Row Level Security (RLS) by setting the user's JWT token.

CRITICAL SECURITY RULES:
1. NEVER use the service_role key for user operations
2. ALWAYS use the user's JWT token from Supabase Auth
3. RLS policies will enforce user_id = auth.uid() automatically
4. The client MUST be created per-request with the user's token
"""

import logging

from backend.config import settings
from supabase import Client, create_client

logger = logging.getLogger(__name__)


def get_supabase_client(access_token: str) -> Client:
    """
    Create an authenticated Supabase client for a specific user.

    This client respects Row Level Security (RLS) policies because it uses
    the user's JWT access token from Supabase Auth. All queries will be
    scoped to rows where user_id = auth.uid().

    Args:
        access_token: The user's JWT access token from Supabase Auth.
                     This is the token verified in backend/auth/dependencies.py.

    Returns:
        An authenticated Supabase client that enforces RLS.

    Security:
        - Uses SUPABASE_PUBLISHABLE_KEY (modern replacement for anon key)
        - Sets the user's access_token in the Authorization header
        - All database operations will be subject to RLS policies
        - The user can ONLY access their own data (user_id = auth.uid())

    Example:
        >>> from backend.auth.dependencies import verify_token
        >>> user_id = verify_token(request)  # Returns user_id
        >>> # To get the actual token, we need it from the request header
        >>> token = request.headers.get("Authorization").replace("Bearer ", "")
        >>> client = get_supabase_client(token)
        >>> # Now all operations respect RLS
        >>> result = client.table("invoice").select("*").execute()
    """
    # Create client with publishable key (respects RLS)
    client: Client = create_client(
        supabase_url=settings.SUPABASE_URL,
        supabase_key=settings.SUPABASE_PUBLISHABLE_KEY
    )

    # Set the user's JWT token - this is what makes RLS work
    # The token contains the user_id in the 'sub' claim
    # Supabase will use this to enforce auth.uid() in RLS policies
    client.auth.set_session(access_token, access_token)

    logger.debug(
        "Created authenticated Supabase client with user token "
        "(RLS enforced)"
    )

    return client


def get_service_role_client() -> Client:
    """
    Create a Supabase client with service_role privileges.

    WARNING: This bypasses RLS and should ONLY be used for:
    - System-level operations (creating global categories, etc.)
    - Background jobs that need cross-user access
    - Administrative tasks

    NEVER use this for user-initiated requests.

    Returns:
        A Supabase client with service_role privileges (bypasses RLS).
    """
    # TODO(db-team): Add SUPABASE_SECRET_KEY to config when needed
    # For now, we don't expose this - all user operations use RLS
    raise NotImplementedError(
        "Service role client not implemented. "
        "All user operations must use RLS via get_supabase_client()."
    )
