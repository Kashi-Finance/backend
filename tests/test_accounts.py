"""
Tests for account CRUD endpoints.

Tests cover:
- Account creation
- Account listing
- Account retrieval by ID
- Account updates
- Account deletion with both strategies (reassign and delete_transactions)
- Authentication and authorization
- Error cases
"""

import json
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
def mock_account():
    """Mock account data."""
    return {
        "id": "account-123",
        "user_id": "test-user-id",
        "name": "Test Checking Account",
        "type": "bank",
        "currency": "GTQ",
        "created_at": "2025-11-05T10:00:00Z",
        "updated_at": "2025-11-05T10:00:00Z"
    }


@pytest.fixture
def mock_get_supabase_client():
    """Mock get_supabase_client to return a fake client."""
    with patch("backend.routes.accounts.get_supabase_client") as mock:
        # Create a mock Supabase client using MagicMock
        from unittest.mock import MagicMock
        mock_supabase_client = MagicMock()
        
        # Set the return value to the mock client
        mock.return_value = mock_supabase_client
        yield mock


class TestListAccounts:
    """Tests for GET /accounts"""
    
    @patch("backend.routes.accounts.get_user_accounts")
    def test_list_accounts_success(self, mock_get_accounts, mock_auth, mock_get_supabase_client, mock_account):
        """Test successful account listing."""
        mock_get_accounts.return_value = [mock_account]
        
        response = client.get("/accounts")
        
        assert response.status_code == 200
        data = response.json()
        assert data["count"] == 1
        assert len(data["accounts"]) == 1
        assert data["accounts"][0]["id"] == mock_account["id"]
        assert data["accounts"][0]["name"] == mock_account["name"]
    
    @patch("backend.routes.accounts.get_user_accounts")
    def test_list_accounts_empty(self, mock_get_accounts, mock_auth, mock_get_supabase_client):
        """Test listing accounts when user has none."""
        mock_get_accounts.return_value = []
        
        response = client.get("/accounts")
        
        assert response.status_code == 200
        data = response.json()
        assert data["count"] == 0
        assert len(data["accounts"]) == 0


class TestCreateAccount:
    """Tests for POST /accounts"""
    
    @patch("backend.routes.accounts.create_account")
    def test_create_account_success(self, mock_create, mock_auth, mock_get_supabase_client, mock_account):
        """Test successful account creation."""
        mock_create.return_value = mock_account
        
        response = client.post(
            "/accounts",
            json={
                "name": "Test Checking Account",
                "type": "bank",
                "currency": "GTQ"
            }
        )
        
        assert response.status_code == 201
        data = response.json()
        assert data["status"] == "CREATED"
        assert data["account"]["id"] == mock_account["id"]
        assert data["account"]["name"] == mock_account["name"]
        assert data["message"] == "Account created successfully"
    
    def test_create_account_invalid_type(self, mock_auth, mock_get_supabase_client):
        """Test account creation with invalid type."""
        response = client.post(
            "/accounts",
            json={
                "name": "Test Account",
                "type": "invalid_type",  # Not in enum
                "currency": "GTQ"
            }
        )
        
        assert response.status_code == 422  # Validation error
    
    def test_create_account_missing_fields(self, mock_auth, mock_get_supabase_client):
        """Test account creation with missing required fields."""
        response = client.post(
            "/accounts",
            json={
                "name": "Test Account"
                # Missing type and currency
            }
        )
        
        assert response.status_code == 422  # Validation error


class TestGetAccount:
    """Tests for GET /accounts/{account_id}"""
    
    @patch("backend.routes.accounts.get_account_by_id")
    def test_get_account_success(self, mock_get_account, mock_auth, mock_get_supabase_client, mock_account):
        """Test successful account retrieval."""
        mock_get_account.return_value = mock_account
        
        response = client.get(f"/accounts/{mock_account['id']}")
        
        assert response.status_code == 200
        data = response.json()
        assert data["id"] == mock_account["id"]
        assert data["name"] == mock_account["name"]
    
    @patch("backend.routes.accounts.get_account_by_id")
    def test_get_account_not_found(self, mock_get_account, mock_auth, mock_get_supabase_client):
        """Test account retrieval when account doesn't exist."""
        mock_get_account.return_value = None
        
        response = client.get("/accounts/nonexistent-id")
        
        assert response.status_code == 404
        data = response.json()
        assert data["detail"]["error"] == "not_found"


class TestUpdateAccount:
    """Tests for PATCH /accounts/{account_id}"""
    
    @patch("backend.routes.accounts.update_account")
    def test_update_account_success(self, mock_update, mock_auth, mock_get_supabase_client, mock_account):
        """Test successful account update."""
        updated_account = {**mock_account, "name": "Updated Account Name"}
        mock_update.return_value = updated_account
        
        response = client.patch(
            f"/accounts/{mock_account['id']}",
            json={"name": "Updated Account Name"}
        )
        
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "UPDATED"
        assert data["account"]["name"] == "Updated Account Name"
        assert data["message"] == "Account updated successfully"
    
    def test_update_account_no_fields(self, mock_auth, mock_get_supabase_client, mock_account):
        """Test update with no fields provided."""
        response = client.patch(
            f"/accounts/{mock_account['id']}",
            json={}
        )
        
        assert response.status_code == 400
        data = response.json()
        assert data["detail"]["error"] == "invalid_request"
    
    @patch("backend.routes.accounts.update_account")
    def test_update_account_not_found(self, mock_update, mock_auth, mock_get_supabase_client):
        """Test updating non-existent account."""
        mock_update.return_value = None
        
        response = client.patch(
            "/accounts/nonexistent-id",
            json={"name": "New Name"}
        )
        
        assert response.status_code == 404
        data = response.json()
        assert data["detail"]["error"] == "not_found"


class TestDeleteAccount:
    """Tests for DELETE /accounts/{account_id}"""
    
    @patch("backend.routes.accounts.delete_account_with_reassignment")
    def test_delete_account_with_reassignment(self, mock_delete, mock_auth, mock_get_supabase_client, mock_account):
        """Test account deletion with transaction reassignment."""
        mock_delete.return_value = 5  # 5 transactions reassigned
        
        response = client.request(
            "DELETE",
            f"/accounts/{mock_account['id']}",
            content=json.dumps({
                "strategy": "reassign",
                "target_account_id": "target-account-123"
            }),
            headers={"Content-Type": "application/json"}
        )
        
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "DELETED"
        assert data["transactions_affected"] == 5
        assert "5 transactions reassigned" in data["message"]
    
    @patch("backend.routes.accounts.delete_account_with_transactions")
    def test_delete_account_with_transactions(self, mock_delete, mock_auth, mock_get_supabase_client, mock_account):
        """Test account deletion by deleting transactions."""
        mock_delete.return_value = (2, 3)  # (2 recurring templates, 3 transactions deleted)
        
        response = client.request(
            "DELETE",
            f"/accounts/{mock_account['id']}",
            content=json.dumps({"strategy": "delete_transactions", "target_account_id": None}),
            headers={"Content-Type": "application/json"}
        )
        
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "DELETED"
        assert data["transactions_affected"] == 3  # Only transactions count
        assert "2 recurring templates" in data["message"]
        assert "3 transactions" in data["message"]
    
    def test_delete_account_missing_target_for_reassign(self, mock_auth, mock_get_supabase_client, mock_account):
        """Test reassign strategy without target_account_id."""
        response = client.request(
            "DELETE",
            f"/accounts/{mock_account['id']}",
            content=json.dumps({"strategy": "reassign", "target_account_id": None}),
            headers={"Content-Type": "application/json"}
        )
        
        assert response.status_code == 400
        data = response.json()
        assert data["detail"]["error"] == "invalid_request"
        assert "target_account_id is required" in data["detail"]["details"]
