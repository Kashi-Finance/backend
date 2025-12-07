"""
Pydantic schemas for authentication endpoints.

These models define the strict request/response contracts for auth endpoints.
"""

from typing import Optional
from pydantic import BaseModel, Field


class ProfileSummary(BaseModel):
    """
    Condensed profile info for auth/me response.
    
    Contains only the essential profile fields needed for session hydration.
    """
    first_name: str = Field(..., description="User's first name")
    last_name: Optional[str] = Field(None, description="User's last name")
    avatar_url: Optional[str] = Field(None, description="Public URL to user's avatar image")
    country: str = Field(
        ...,
        description="User's country (ISO-2 code)",
        examples=["GT", "US", "MX"]
    )
    currency_preference: str = Field(
        ...,
        description="Preferred currency (ISO code)",
        examples=["GTQ", "USD", "EUR"]
    )
    locale: str = Field(
        ...,
        description="Language/localization preference",
        examples=["system", "es-GT", "en-US"]
    )


class AuthMeResponse(BaseModel):
    """
    Response for GET /auth/me - Authenticated user identity.
    
    Used on app boot to hydrate global session state and confirm token validity.
    """
    user_id: str = Field(..., description="User UUID (from JWT 'sub' claim)")
    email: Optional[str] = Field(
        None,
        description="User's email (from JWT 'email' claim, if present)"
    )
    profile: Optional[ProfileSummary] = Field(
        None,
        description="User's profile if it exists. Null if profile hasn't been created yet."
    )
    
    model_config = {
        "json_schema_extra": {
            "examples": [
                {
                    "user_id": "38f7d540-23fa-497a-8df2-3ab9cbe13da5",
                    "email": "user@example.com",
                    "profile": {
                        "first_name": "Samuel",
                        "last_name": "Marroquín",
                        "avatar_url": "https://storage.kashi.app/avatars/u1.png",
                        "country": "GT",
                        "currency_preference": "GTQ",
                        "locale": "es"
                    }
                }
            ]
        }
    }
