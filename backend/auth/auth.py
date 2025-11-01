"""
Supabase Authentication verification for Kashi Finances Backend.

This module implements the mandatory auth pipeline described in:
- .github/copilot-instructions.md (Section 3)
- .github/instructions/api-architecture.instructions.md (Section 3)

ALL PROTECTED ENDPOINTS MUST use verify_supabase_token() before any other logic.
"""

from typing import Optional
from fastapi import HTTPException, Header

from backend.utils.logging import get_logger

logger = get_logger(__name__)


def verify_supabase_token(authorization: Optional[str] = Header(None)) -> str:
    """
    Verify Supabase Auth Bearer token and extract authenticated user_id.
    
    This function implements the mandatory authentication pipeline:
    
    Step 1: Read Authorization: Bearer <token> from headers
    Step 2: Verify token signature and expiration using Supabase Auth
    Step 3: Extract user_id from the validated token (equivalent to auth.uid())
    Step 4: If verification fails or token is missing → raise HTTP 401 Unauthorized
    Step 5: Ignore any user_id sent by the client (token is source of truth)
    
    Args:
        authorization: The Authorization header value (injected by FastAPI)
    
    Returns:
        str: The authenticated user_id extracted from the token
    
    Raises:
        HTTPException: 401 if token is missing, invalid, or expired
    
    Usage in protected routes:
        >>> from fastapi import Depends
        >>> from backend.auth.auth import verify_supabase_token
        >>> 
        >>> @router.post("/protected-endpoint")
        >>> async def protected_route(user_id: str = Depends(verify_supabase_token)):
        >>>     # user_id is now verified and safe to use
        >>>     pass
    
    TODO: Implement actual Supabase Auth verification logic:
        - Parse Bearer token from authorization header
        - Call Supabase Auth API or use supabase-py client to verify signature
        - Extract user_id from JWT claims (auth.uid())
        - Handle token expiration, malformed tokens, etc.
        - Return the verified user_id
    
    TODO: Add Supabase client initialization (supabase-py):
        - Install: pip install supabase
        - Configure SUPABASE_URL and SUPABASE_KEY from environment
        - Use supabase.auth.get_user(token) to verify and extract user
    
    TODO: Never bypass RLS - all DB operations using this user_id will be
          subject to Row Level Security policies that enforce user_id = auth.uid()
    """
    
    # Step 1: Check if Authorization header is present
    if not authorization:
        logger.warning("Authentication failed: missing Authorization header")
        raise HTTPException(
            status_code=401,
            detail={
                "error": "unauthorized",
                "details": "Missing Authorization header"
            }
        )
    
    # Step 2: Verify Bearer token format
    if not authorization.startswith("Bearer "):
        logger.warning("Authentication failed: malformed Authorization header")
        raise HTTPException(
            status_code=401,
            detail={
                "error": "unauthorized",
                "details": "Invalid Authorization header format (expected 'Bearer <token>')"
            }
        )
    
    # Extract token
    token = authorization.replace("Bearer ", "").strip()
    
    if not token:
        logger.warning("Authentication failed: empty token")
        raise HTTPException(
            status_code=401,
            detail={
                "error": "unauthorized",
                "details": "Empty authentication token"
            }
        )
    
    # TODO: ACTUAL VERIFICATION LOGIC GOES HERE
    # For now, return a demo user_id for development/testing
    # REMOVE THIS in production and implement real Supabase Auth verification
    
    logger.info("Auth verification placeholder executed (returning demo-user-id)")
    logger.warning("TODO: Implement actual Supabase Auth token verification")
    
    # Placeholder return - REPLACE WITH REAL IMPLEMENTATION
    demo_user_id = "demo-user-id"
    
    # Step 3: In production, this would be:
    # try:
    #     supabase_client = get_supabase_client()
    #     user = supabase_client.auth.get_user(token)
    #     user_id = user.id  # This is auth.uid()
    #     logger.info(f"Successfully authenticated user_id: {user_id[:8]}...")
    #     return user_id
    # except Exception as e:
    #     logger.error(f"Token verification failed: {str(e)}")
    #     raise HTTPException(
    #         status_code=401,
    #         detail={
    #             "error": "unauthorized",
    #             "details": "Invalid or expired token"
    #         }
    #     )
    
    return demo_user_id
