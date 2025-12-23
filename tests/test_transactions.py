"""
Tests for transaction CRUD endpoints.

Tests cover:
- Transaction creation with account_name and category_name convenience fields
- Transaction listing with enriched fields
- Transaction retrieval by ID with convenience fields
- Transaction updates with field enrichment
- Transaction deletion
- Authentication and authorization
- Error cases
"""

import json
import pytest
from fastapi.testclient import TestClient
from unittest.mock import patch, MagicMock, AsyncMock
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
def mock_transaction():
    """Mock transaction data with all database fields."""
    return {
        "id": "transaction-123",
        "user_id": "test-user-id",
        "account_id": "account-456",
        "category_id": "category-789",
        "invoice_id": None,
        "flow_type": "outcome",
        "amount": 128.50,
        "date": "2025-10-30T14:32:00-06:00",
        "description": "Super Despensa Familiar",
        "embedding": None,
        "paired_transaction_id": None,
        "created_at": "2025-11-03T10:15:00Z",
        "updated_at": "2025-11-03T10:15:00Z"
    }


@pytest.fixture
def mock_get_supabase_client():
    """Mock get_supabase_client to return a fake client."""
    with patch("backend.routes.transactions.get_supabase_client") as mock:
        mock_supabase_client = MagicMock()
        mock.return_value = mock_supabase_client
        yield mock


class TestCreateTransaction:
    """Tests for POST /transactions"""
    
    @patch("backend.routes.transactions.create_transaction")
    def test_create_transaction_success(self, mock_create_txn, mock_auth, mock_get_supabase_client, mock_transaction):
        """Test successful transaction creation with all database fields."""
        mock_create_txn.return_value = mock_transaction
        
        request_body = {
            "account_id": "account-456",
            "category_id": "category-789",
            "flow_type": "outcome",
            "amount": 128.50,
            "date": "2025-10-30T14:32:00-06:00",
            "description": "Super Despensa Familiar"
        }
        
        response = client.post("/transactions", json=request_body)
        
        assert response.status_code == 201
        data = response.json()
        assert data["status"] == "CREATED"
        assert data["transaction"]["id"] == "transaction-123"
        # Verify all transaction fields are present
        assert data["transaction"]["user_id"] == "test-user-id"
        assert data["transaction"]["account_id"] == "account-456"
        assert data["transaction"]["category_id"] == "category-789"
        assert data["transaction"]["amount"] == 128.50
        assert data["transaction"]["flow_type"] == "outcome"
        assert data["transaction"]["embedding"] is None


    @patch("backend.routes.transactions.create_transaction")
    def test_create_transaction_missing_required_field(self, mock_create_txn, mock_auth, mock_get_supabase_client):
        """Test transaction creation fails with missing required field."""
        request_body = {
            "account_id": "account-456",
            # Missing category_id
            "flow_type": "outcome",
            "amount": 128.50,
            "date": "2025-10-30T14:32:00-06:00",
        }
        
        response = client.post("/transactions", json=request_body)
        
        # FastAPI will return 422 for validation error
        assert response.status_code == 422


class TestListTransactions:
    """Tests for GET /transactions"""
    
    @patch("backend.routes.transactions.get_user_transactions")
    def test_list_transactions_success(self, mock_get_txns, mock_auth, mock_get_supabase_client, mock_transaction):
        """Test successful transaction listing with all database fields."""
        mock_get_txns.return_value = [mock_transaction]
        
        response = client.get("/transactions")
        
        assert response.status_code == 200
        data = response.json()
        assert data["count"] == 1
        assert len(data["transactions"]) == 1
        txn = data["transactions"][0]
        assert txn["id"] == "transaction-123"
        # Verify all transaction fields are present
        assert txn["user_id"] == "test-user-id"
        assert txn["account_id"] == "account-456"
        assert txn["category_id"] == "category-789"
        assert txn["amount"] == 128.50
        assert txn["embedding"] is None


    @patch("backend.routes.transactions.get_user_transactions")
    def test_list_transactions_with_filters(self, mock_get_txns, mock_auth, mock_get_supabase_client, mock_transaction):
        """Test transaction listing with query filters."""
        mock_get_txns.return_value = [mock_transaction]
        
        response = client.get(
            "/transactions?limit=10&offset=0&flow_type=outcome&account_id=account-456"
        )
        
        assert response.status_code == 200
        data = response.json()
        assert data["limit"] == 10
        assert data["offset"] == 0


    @patch("backend.routes.transactions.get_user_transactions")
    def test_list_transactions_empty(self, mock_get_txns, mock_auth, mock_get_supabase_client):
        """Test transaction listing returns empty list."""
        mock_get_txns.return_value = []
        
        response = client.get("/transactions")
        
        assert response.status_code == 200
        data = response.json()
        assert data["count"] == 0
        assert data["transactions"] == []


class TestGetTransaction:
    """Tests for GET /transactions/{transaction_id}"""
    
    @patch("backend.routes.transactions.get_transaction_by_id")
    def test_get_transaction_success(self, mock_get_txn, mock_auth, mock_get_supabase_client, mock_transaction):
        """Test successful transaction retrieval with all database fields."""
        mock_get_txn.return_value = mock_transaction
        
        response = client.get("/transactions/transaction-123")
        
        assert response.status_code == 200
        data = response.json()
        assert data["id"] == "transaction-123"
        # Verify all transaction fields are present
        assert data["user_id"] == "test-user-id"
        assert data["account_id"] == "account-456"
        assert data["category_id"] == "category-789"
        assert data["amount"] == 128.50
        assert data["embedding"] is None


    @patch("backend.routes.transactions.get_transaction_by_id")
    def test_get_transaction_not_found(self, mock_get_txn, mock_auth, mock_get_supabase_client):
        """Test transaction retrieval returns 404 when not found."""
        mock_get_txn.return_value = None
        
        response = client.get("/transactions/nonexistent-id")
        
        assert response.status_code == 404
        data = response.json()
        assert data["detail"]["error"] == "not_found"


class TestUpdateTransaction:
    """Tests for PATCH /transactions/{transaction_id}"""
    
    @patch("backend.routes.transactions.update_transaction")
    def test_update_transaction_success(self, mock_update_txn, mock_auth, mock_get_supabase_client, mock_transaction):
        """Test successful transaction update with all database fields."""
        updated_txn = mock_transaction.copy()
        updated_txn["amount"] = 150.00
        mock_update_txn.return_value = updated_txn
        
        # Mock the initial transaction check query
        mock_supabase = mock_get_supabase_client.return_value
        mock_result = MagicMock()
        mock_result.data = [{
            "id": "transaction-123",
            "paired_transaction_id": None,
            "category_id": "category-789"
        }]
        mock_supabase.table.return_value.select.return_value.eq.return_value.eq.return_value.execute.return_value = mock_result
        
        request_body = {
            "amount": 150.00,
            "category_id": "category-999"
        }
        
        response = client.patch("/transactions/transaction-123", json=request_body)
        
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "UPDATED"
        assert data["transaction"]["amount"] == 150.00
        # Verify all transaction fields are present
        assert data["transaction"]["embedding"] is None


    @patch("backend.routes.transactions.update_transaction")
    def test_update_transaction_not_found(self, mock_update_txn, mock_auth, mock_get_supabase_client):
        """Test transaction update returns 404 when not found."""
        mock_update_txn.return_value = None
        
        request_body = {
            "amount": 150.00
        }
        
        response = client.patch("/transactions/nonexistent-id", json=request_body)
        
        assert response.status_code == 404
        data = response.json()
        assert data["detail"]["error"] == "not_found"


class TestDeleteTransaction:
    """Tests for DELETE /transactions/{transaction_id}"""
    
    @patch("backend.routes.transactions.delete_transaction")
    def test_delete_transaction_success(self, mock_delete_txn, mock_auth, mock_get_supabase_client):
        """Test successful transaction deletion."""
        mock_delete_txn.return_value = True
        
        response = client.delete("/transactions/transaction-123")
        
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "DELETED"
        assert data["transaction_id"] == "transaction-123"


    @patch("backend.routes.transactions.delete_transaction")
    def test_delete_transaction_not_found(self, mock_delete_txn, mock_auth, mock_get_supabase_client):
        """Test transaction deletion returns 404 when not found."""
        mock_delete_txn.return_value = False
        
        response = client.delete("/transactions/nonexistent-id")
        
        assert response.status_code == 404
        data = response.json()
        assert data["detail"]["error"] == "not_found"


class TestTransactionAllFields:
    """Tests to verify all transaction database fields are returned."""
    
    @patch("backend.routes.transactions.get_user_transactions")
    def test_transactions_include_all_fields(self, mock_get_txns, mock_auth, mock_get_supabase_client, mock_transaction):
        """Test that all transaction responses include all database fields."""
        mock_get_txns.return_value = [mock_transaction]
        
        response = client.get("/transactions")
        data = response.json()
        
        for txn in data["transactions"]:
            # Verify all required fields are present
            assert "id" in txn
            assert "user_id" in txn
            assert "account_id" in txn
            assert "category_id" in txn
            assert "invoice_id" in txn
            assert "flow_type" in txn
            assert "amount" in txn
            assert "date" in txn
            assert "description" in txn
            assert "embedding" in txn
            assert "paired_transaction_id" in txn
            assert "created_at" in txn
            assert "updated_at" in txn


    @patch("backend.routes.transactions.create_transaction")
    def test_created_transaction_includes_all_fields(self, mock_create_txn, mock_auth, mock_get_supabase_client, mock_transaction):
        """Test that created transaction includes all database fields."""
        mock_create_txn.return_value = mock_transaction
        
        request_body = {
            "account_id": "account-456",
            "category_id": "category-789",
            "flow_type": "outcome",
            "amount": 128.50,
            "date": "2025-10-30T14:32:00-06:00",
        }
        
        response = client.post("/transactions", json=request_body)
        data = response.json()
        
        txn = data["transaction"]
        # Verify all required fields are present
        assert "id" in txn
        assert "user_id" in txn
        assert "account_id" in txn
        assert "category_id" in txn
        assert "invoice_id" in txn
        assert "flow_type" in txn
        assert "amount" in txn
        assert "date" in txn
        assert "description" in txn
        assert "embedding" in txn
        assert "paired_transaction_id" in txn
        assert "created_at" in txn
        assert "updated_at" in txn


class TestTransactionWithInvoice:
    """Tests for transactions linked to invoices."""
    
    @patch("backend.routes.transactions.get_transaction_by_id")
    def test_get_transaction_with_invoice_id(self, mock_get_txn, mock_auth, mock_get_supabase_client):
        """Test retrieving transaction that is linked to an invoice."""
        txn_with_invoice = {
            "id": "transaction-456",
            "user_id": "test-user-id",
            "account_id": "account-456",
            "category_id": "category-789",
            "invoice_id": "invoice-123",
            "flow_type": "outcome",
            "amount": 128.50,
            "date": "2025-10-30T14:32:00-06:00",
            "description": "Super Despensa",
            "embedding": None,
            "paired_transaction_id": None,
            "created_at": "2025-11-03T10:15:00Z",
            "updated_at": "2025-11-03T10:15:00Z"
        }
        mock_get_txn.return_value = txn_with_invoice
        
        response = client.get("/transactions/transaction-456")
        
        assert response.status_code == 200
        data = response.json()
        assert data["invoice_id"] == "invoice-123"
        # Verify all fields including embedding are present
        assert data["embedding"] is None


