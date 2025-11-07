"""
Pydantic schemas for profile CRUD endpoints.

These models define the strict request/response contracts for user profile management.
Profiles contain user preferences and personal information (1:1 with auth.users).
"""

from typing import Optional
from pydantic import BaseModel, Field


# --- Profile response models ---

class ProfileResponse(BaseModel):
    """
    Response for GET /profile - User profile details.
    
    Contains all user profile fields including preferences and localization settings.
    """
    user_id: str = Field(..., description="User UUID (from auth.users)")
    first_name: str = Field(..., description="User's first name")
    last_name: Optional[str] = Field(None, description="User's last name")
    avatar_url: Optional[str] = Field(None, description="Public URL to user's avatar image")
    currency_preference: str = Field(
        ...,
        description="Preferred currency (ISO code, e.g. 'GTQ')",
        examples=["GTQ", "USD", "EUR"]
    )
    locale: str = Field(
        ...,
        description="Language/localization preference",
        examples=["system", "es-GT", "en-US"]
    )
    country: str = Field(
        ...,
        description="User's country (ISO-2 code, e.g. 'GT'). Used for localized recommendations.",
        examples=["GT", "US", "MX"]
    )
    created_at: str = Field(..., description="ISO-8601 timestamp when profile was created")
    updated_at: str = Field(..., description="ISO-8601 timestamp of last profile update")


# --- Profile update models ---

class ProfileUpdateRequest(BaseModel):
    """
    Request to update user profile.
    
    All fields are optional - only provided fields will be updated.
    At least one field must be provided.
    """
    first_name: Optional[str] = Field(
        None,
        description="Updated first name",
        min_length=1,
        max_length=100
    )
    last_name: Optional[str] = Field(
        None,
        description="Updated last name",
        max_length=100
    )
    avatar_url: Optional[str] = Field(
        None,
        description="Updated avatar URL (must be valid HTTP/HTTPS URL)"
    )
    currency_preference: Optional[str] = Field(
        None,
        description="Updated currency preference (ISO code)",
        examples=["GTQ", "USD", "EUR"]
    )
    locale: Optional[str] = Field(
        None,
        description="Updated locale preference",
        examples=["system", "es-GT", "en-US"]
    )
    country: Optional[str] = Field(
        None,
        description="Updated country (ISO-2 code)",
        min_length=2,
        max_length=2,
        examples=["GT", "US", "MX"]
    )


class ProfileCreateRequest(BaseModel):
    """
    Request to create a new user profile.

    Required fields: first_name, currency_preference, country
    Optional: last_name, avatar_url, locale
    """
    first_name: str = Field(..., min_length=1, max_length=100)
    last_name: Optional[str] = Field(None, max_length=100)
    avatar_url: Optional[str] = Field(None)
    currency_preference: str = Field(..., description="Preferred currency (ISO code)")
    locale: Optional[str] = Field("system", description="Locale preference")
    country: str = Field(..., min_length=2, max_length=2, description="ISO-2 country code")


class ProfileUpdateResponse(BaseModel):
    """
    Response after successfully updating profile.
    """
    status: str = Field("UPDATED", description="Indicates the profile was successfully updated")
    profile: ProfileResponse = Field(..., description="Complete updated profile details")
    message: str = Field(
        ...,
        description="Success message",
        examples=["Profile updated successfully"]
    )


# --- Profile delete response ---

class ProfileDeleteResponse(BaseModel):
    """
    Response after successfully deleting (anonymizing) profile.
    
    Note: Profile is not physically deleted, only anonymized per DB delete rule.
    """
    status: str = Field("DELETED", description="Indicates the profile was successfully anonymized")
    message: str = Field(
        ...,
        description="Success message",
        examples=["Profile deleted successfully"]
    )
