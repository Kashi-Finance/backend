"""
FastAPI dependency functions for authentication.

These functions are used as FastAPI dependencies to verify tokens
and extract authenticated user_id from Supabase Auth.

Uses Supabase's new JWT Signing Keys system with ECC (P-256) public key verification.
"""

import logging
from dataclasses import dataclass
from typing import Annotated

from fastapi import Header, HTTPException, status
from jwt import PyJWKClient, decode
from jwt.exceptions import ExpiredSignatureError, InvalidTokenError, PyJWKClientError

from backend.config import settings

logger = logging.getLogger(__name__)

# Initialize JWKS client for fetching and caching Supabase's public keys
# The client automatically handles caching and key rotation (cache_keys=True by default)
_jwks_client: PyJWKClient | None = None


@dataclass
class AuthenticatedUser:
    """
    Represents an authenticated user with their token.

    Attributes:
        user_id: The user's UUID from the JWT token's 'sub' claim
        access_token: The full JWT access token (for creating authenticated Supabase clients)
    """
    user_id: str
    access_token: str


def get_jwks_client() -> PyJWKClient:
    """
    Get or create the JWKS client instance.

    Lazy initialization ensures we only create the client when needed.
    The client caches JWKS responses to minimize network calls.

    Returns:
        PyJWKClient: Configured JWKS client for Supabase

    Raises:
        ValueError: If SUPABASE_URL is not configured
    """
    global _jwks_client

    if _jwks_client is None:
        jwks_url = settings.SUPABASE_JWKS_URL
        if not jwks_url:
            raise ValueError(
                "SUPABASE_URL is not configured. "
                "Cannot construct JWKS URL for JWT verification."
            )

        logger.info(f"Initializing JWKS client with URL: {jwks_url}")
        _jwks_client = PyJWKClient(
            jwks_url,
            cache_keys=True,  # Enable caching (default TTL is 300 seconds)
            max_cached_keys=16,  # Reasonable limit for key rotation scenarios
        )

    return _jwks_client


async def verify_token(authorization: Annotated[str | None, Header()] = None) -> str:
    """
    Verify Supabase Auth Bearer token and extract user_id.

    This is a FastAPI dependency that:
    1. Reads Authorization header (format: "Bearer <token>")
    2. Verifies token signature and expiration with Supabase Auth
    3. Extracts user_id (equivalent to auth.uid() in RLS)
    4. Returns user_id for use in route handler

    Args:
        authorization: Authorization header value

    Returns:
        user_id: UUID string from validated token (auth.uid())

    Raises:
        HTTPException: 401 if token is missing, invalid, or expired

    Security:
        - This is the ONLY source of truth for user_id
        - Any user_id sent in request body is ignored
        - All downstream DB operations assume RLS enforces user_id = auth.uid()

    Usage:
        @app.get("/protected")
        async def protected_route(user_id: str = Depends(verify_token)):
            # user_id is now validated and safe to use
            pass
    """
    if not authorization:
        logger.warning("Missing Authorization header")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={"error": "unauthorized", "details": "Missing Authorization header"}
        )

    # Extract token from "Bearer <token>" format
    parts = authorization.split()
    if len(parts) != 2 or parts[0].lower() != "bearer":
        logger.warning("Invalid Authorization header format")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={"error": "unauthorized", "details": "Invalid Authorization header format"}
        )

    token = parts[1]

    # Verify JWT token using Supabase's JWT Signing Keys (JWKS)
    # This uses ECC (P-256) asymmetric cryptography with ES256 algorithm
    try:
        # Get JWKS client (lazy-initialized, cached)
        jwks_client = get_jwks_client()

        # Fetch the signing key from JWKS based on the token's 'kid' header
        # The client caches keys and automatically handles key rotation
        signing_key = jwks_client.get_signing_key_from_jwt(token)

        # Decode and verify the JWT token
        # Supabase now uses ES256 (ECC P-256) for signing
        # Supabase tokens use an issuer that includes the /auth/v1 path, e.g.
        #  https://<project>.supabase.co/auth/v1
        issuer = f"{settings.SUPABASE_URL.rstrip('/')}/auth/v1"

        payload = decode(
            token,
            signing_key.key,  # Public key from JWKS
            algorithms=["ES256"],  # ECC P-256 asymmetric algorithm
            audience="authenticated",  # Supabase uses 'authenticated' as the audience
            issuer=issuer,  # Verify the token is from our project
            options={
                "verify_signature": True,
                "verify_exp": True,
                "verify_aud": True,
                "verify_iss": True,
            }
        )

        # Extract user_id from the 'sub' (subject) claim
        # In Supabase, the 'sub' claim contains the user's UUID
        user_id = payload.get("sub")

        if not user_id:
            logger.error("Token payload missing 'sub' claim")
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail={"error": "unauthorized", "details": "Invalid token: missing user ID"}
            )

        logger.info(f"Token verified successfully for user_id={user_id}")
        return str(user_id)

    except ExpiredSignatureError:
        logger.warning("Token has expired")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={"error": "token_expired", "details": "Authentication token has expired"}
        )

    except PyJWKClientError as e:
        # JWKS fetch or key resolution errors
        logger.error(f"JWKS client error: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={"error": "jwks_error", "details": "Unable to verify token signature"}
        )

    except InvalidTokenError as e:
        logger.warning(f"Invalid token: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={"error": "invalid_token", "details": "Invalid authentication token"}
        )

    except Exception as e:
        # Catch-all for unexpected errors (should be rare)
        logger.error(f"Unexpected error during token verification: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={"error": "unauthorized", "details": "Token verification failed"}
        )


async def get_authenticated_user(
    authorization: Annotated[str | None, Header()] = None
) -> AuthenticatedUser:
    """
    Verify token and return authenticated user with token.

    Similar to verify_token(), but returns both user_id AND the token itself.
    This is useful when you need to create an authenticated Supabase client.

    Args:
        authorization: Authorization header value

    Returns:
        AuthenticatedUser: Contains user_id and access_token

    Raises:
        HTTPException: 401 if token is missing, invalid, or expired

    Usage:
        @app.post("/invoices/ocr")
        async def create_invoice(
            auth_user: AuthenticatedUser = Depends(get_authenticated_user)
        ):
            # Create authenticated Supabase client
            supabase_client = get_supabase_client(auth_user.access_token)
            # Use auth_user.user_id for logging/validation
            pass
    """
    if not authorization:
        logger.warning("Missing Authorization header")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={"error": "unauthorized", "details": "Missing Authorization header"}
        )

    # Extract token from "Bearer <token>" format
    parts = authorization.split()
    if len(parts) != 2 or parts[0].lower() != "bearer":
        logger.warning("Invalid Authorization header format")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={"error": "unauthorized", "details": "Invalid Authorization header format"}
        )

    token = parts[1]

    # Verify JWT token using Supabase's JWT Signing Keys (JWKS)
    try:
        jwks_client = get_jwks_client()
        signing_key = jwks_client.get_signing_key_from_jwt(token)

        issuer = f"{settings.SUPABASE_URL.rstrip('/')}/auth/v1"

        payload = decode(
            token,
            signing_key.key,
            algorithms=["ES256"],
            audience="authenticated",
            issuer=issuer,
            options={
                "verify_signature": True,
                "verify_exp": True,
                "verify_aud": True,
                "verify_iss": True,
            }
        )

        user_id = payload.get("sub")

        if not user_id:
            logger.error("Token payload missing 'sub' claim")
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail={"error": "unauthorized", "details": "Invalid token: missing user ID"}
            )

        logger.info(f"Token verified successfully for user_id={user_id}")

        return AuthenticatedUser(user_id=user_id, access_token=token)

    except ExpiredSignatureError:
        logger.warning("Token has expired")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={"error": "token_expired", "details": "Authentication token has expired"}
        )

    except PyJWKClientError as e:
        logger.error(f"JWKS client error: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={"error": "jwks_error", "details": "Unable to verify token signature"}
        )

    except InvalidTokenError as e:
        logger.warning(f"Invalid token: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={"error": "invalid_token", "details": "Invalid authentication token"}
        )

    except Exception as e:
        logger.error(f"Unexpected error during token verification: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={"error": "unauthorized", "details": "Token verification failed"}
        )
