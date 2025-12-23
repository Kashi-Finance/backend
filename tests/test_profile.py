"""
Tests for profile CRUD endpoints.

Tests cover:
- Profile retrieval
- Profile updates
- Profile deletion (anonymization)
- Authentication and authorization
- Error cases
"""

import pytest
from fastapi.testclient import TestClient
from unittest.mock import patch
from backend.main import app
from backend.auth.dependencies import get_authenticated_user, AuthenticatedUser

client = TestClient(app)


async def mock_get_authenticated_user_dependency():
    """Mock dependency that returns test AuthenticatedUser."""
    return AuthenticatedUser(
        user_id="test-user-id",
        access_token="test-access-token"
    )


@pytest.fixture
def mock_auth():
    """Override get_authenticated_user dependency."""
    app.dependency_overrides[get_authenticated_user] = mock_get_authenticated_user_dependency
    yield
    app.dependency_overrides.clear()


@pytest.fixture
def mock_profile():
    """Mock profile data."""
    return {
        "user_id": "test-user-id",
        "first_name": "Test",
        "last_name": "User",
        "avatar_url": "https://example.com/avatar.jpg",
        "currency_preference": "GTQ",
        "locale": "es-GT",
        "country": "GT",
        "created_at": "2025-11-05T10:00:00Z",
        "updated_at": "2025-11-05T10:00:00Z"
    }


@pytest.fixture
def mock_get_supabase_client():
    """Mock get_supabase_client to return a fake client."""
    with patch("backend.routes.profile.get_supabase_client") as mock:
        # Create a mock Supabase client using MagicMock
        from unittest.mock import MagicMock
        mock_supabase_client = MagicMock()
        
        # Set the return value to the mock client
        mock.return_value = mock_supabase_client
        yield mock


class TestGetProfile:
    """Tests for GET /profile"""
    
    @patch("backend.routes.profile.get_user_profile")
    def test_get_profile_success(self, mock_get_profile, mock_auth, mock_get_supabase_client, mock_profile):
        """Test successful profile retrieval."""
        mock_get_profile.return_value = mock_profile
        
        response = client.get("/profile")
        
        assert response.status_code == 200
        data = response.json()
        assert data["user_id"] == mock_profile["user_id"]
        assert data["first_name"] == mock_profile["first_name"]
        assert data["currency_preference"] == mock_profile["currency_preference"]
        assert data["country"] == mock_profile["country"]
    
    @patch("backend.routes.profile.get_user_profile")
    def test_get_profile_not_found(self, mock_get_profile, mock_auth, mock_get_supabase_client):
        """Test profile retrieval when profile doesn't exist."""
        mock_get_profile.return_value = None
        
        response = client.get("/profile")
        
        assert response.status_code == 404
        data = response.json()
        assert data["detail"]["error"] == "not_found"


class TestUpdateProfile:
    """Tests for PATCH /profile"""
    
    @patch("backend.routes.profile.update_user_profile")
    def test_update_profile_success(self, mock_update, mock_auth, mock_get_supabase_client, mock_profile):
        """Test successful profile update."""
        updated_profile = {**mock_profile, "first_name": "Updated"}
        mock_update.return_value = updated_profile
        
        response = client.patch(
            "/profile",
            json={"first_name": "Updated"}
        )
        
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "UPDATED"
        assert data["profile"]["first_name"] == "Updated"
        assert data["message"] == "Profile updated successfully"
    
    @patch("backend.routes.profile.update_user_profile")
    def test_update_profile_multiple_fields(self, mock_update, mock_auth, mock_get_supabase_client, mock_profile):
        """Test updating multiple profile fields."""
        updated_profile = {
            **mock_profile,
            "first_name": "Updated",
            "currency_preference": "USD",
            "locale": "en-US"
        }
        mock_update.return_value = updated_profile
        
        response = client.patch(
            "/profile",
            json={
                "first_name": "Updated",
                "currency_preference": "USD",
                "locale": "en-US"
            }
        )
        
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "UPDATED"
        assert data["profile"]["first_name"] == "Updated"
        assert data["profile"]["currency_preference"] == "USD"
        assert data["profile"]["locale"] == "en-US"
    
    def test_update_profile_no_fields(self, mock_auth, mock_get_supabase_client):
        """Test update with no fields provided."""
        response = client.patch(
            "/profile",
            json={}
        )
        
        assert response.status_code == 400
        data = response.json()
        assert data["detail"]["error"] == "invalid_request"
        assert "At least one field" in data["detail"]["details"]
    
    @patch("backend.routes.profile.update_user_profile")
    def test_update_profile_not_found(self, mock_update, mock_auth, mock_get_supabase_client):
        """Test updating non-existent profile."""
        mock_update.return_value = None
        
        response = client.patch(
            "/profile",
            json={"first_name": "New Name"}
        )
        
        assert response.status_code == 404
        data = response.json()
        assert data["detail"]["error"] == "not_found"


class TestDeleteProfile:
    """Tests for DELETE /profile"""
    
    @patch("backend.routes.profile.delete_user_profile")
    def test_delete_profile_success(self, mock_delete, mock_auth, mock_get_supabase_client, mock_profile):
        """Test successful profile deletion (anonymization)."""
        anonymized_profile = {
            **mock_profile,
            "first_name": "Deleted User",
            "last_name": None,
            "avatar_url": None
        }
        mock_delete.return_value = anonymized_profile
        
        response = client.delete("/profile")
        
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "DELETED"
        assert data["message"] == "Profile deleted successfully"
    
    @patch("backend.routes.profile.delete_user_profile")
    def test_delete_profile_not_found(self, mock_delete, mock_auth, mock_get_supabase_client):
        """Test deleting non-existent profile."""
        mock_delete.return_value = None
        
        response = client.delete("/profile")
        
        assert response.status_code == 404
        data = response.json()
        assert data["detail"]["error"] == "not_found"


class TestProfileValidation:
    """Tests for profile field validation"""
    
    def test_update_profile_invalid_country_length(self, mock_auth, mock_get_supabase_client):
        """Test update with invalid country code length."""
        response = client.patch(
            "/profile",
            json={"country": "INVALID"}  # Should be 2 chars
        )
        
        assert response.status_code == 422  # Validation error
    
    def test_update_profile_empty_first_name(self, mock_auth, mock_get_supabase_client):
        """Test update with empty first_name."""
        response = client.patch(
            "/profile",
            json={"first_name": ""}  # min_length=1
        )
        
        assert response.status_code == 422  # Validation error
