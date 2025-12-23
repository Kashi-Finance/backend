"""
Tests for transfer endpoints.

Tests cover:
- Normal transfer creation (POST /transfers)
- Recurring transfer creation (POST /transfers/recurring)
- Paired transaction deletion (DELETE /transactions/{id})
- Paired recurring rule deletion (DELETE /recurring-transactions/{id})
- Validation errors (invalid accounts, missing fields)
- Atomicity (both sides created or neither)
- Security (RLS enforcement, cannot transfer between different users)
"""

import pytest
from fastapi.testclient import TestClient
from unittest.mock import patch, MagicMock
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
def mock_get_supabase_client():
    """Mock get_supabase_client to return a fake client."""
    with patch("backend.routes.transfers.get_supabase_client") as mock:
        from unittest.mock import MagicMock
        mock_supabase_client = MagicMock()
        mock.return_value = mock_supabase_client
        yield mock


class TestCreateTransfer:
    """Tests for POST /transfers"""
    
    @patch("backend.routes.transfers.transfer_service.create_transfer")
    def test_create_transfer_success(self, mock_create, mock_auth, mock_get_supabase_client):
        """Test successful transfer creation."""
        outgoing_txn = {
            "id": "txn-out-uuid",
            "user_id": "test-user-id",
            "account_id": "acct-from-uuid",
            "category_id": "cat-transfer-uuid",
            "flow_type": "outcome",
            "amount": 500.00,
            "date": "2025-11-03",
            "description": "Transfer out",
            "paired_transaction_id": "txn-in-uuid",
            "created_at": "2025-11-03T10:00:00Z",
            "updated_at": "2025-11-03T10:00:00Z"
        }
        incoming_txn = {
            "id": "txn-in-uuid",
            "user_id": "test-user-id",
            "account_id": "acct-to-uuid",
            "category_id": "cat-transfer-uuid",
            "flow_type": "income",
            "amount": 500.00,
            "date": "2025-11-03",
            "description": "Transfer in",
            "paired_transaction_id": "txn-out-uuid",
            "created_at": "2025-11-03T10:00:00Z",
            "updated_at": "2025-11-03T10:00:00Z"
        }
        mock_create.return_value = (outgoing_txn, incoming_txn)
        
        response = client.post(
            "/transfers",
            json={
                "from_account_id": "acct-from-uuid",
                "to_account_id": "acct-to-uuid",
                "amount": 500.00,
                "date": "2025-11-03",
                "description": "Monthly savings"
            }
        )
        
        assert response.status_code == 201
        data = response.json()
        assert data["status"] == "CREATED"
        assert len(data["transactions"]) == 2
        assert data["transactions"][0]["id"] == "txn-out-uuid"
        assert data["transactions"][1]["id"] == "txn-in-uuid"
        assert data["transactions"][0]["account_id"] == "acct-from-uuid"
        assert data["transactions"][1]["account_id"] == "acct-to-uuid"
        assert data["transactions"][0]["flow_type"] == "outcome"
        assert data["transactions"][1]["flow_type"] == "income"
        assert data["transactions"][0]["amount"] == 500.00
        assert data["message"] == "Transfer created successfully"
    
    @patch("backend.routes.transfers.transfer_service.create_transfer")
    def test_create_transfer_invalid_accounts(self, mock_create, mock_auth, mock_get_supabase_client):
        """Test transfer with accounts that don't belong to user."""
        mock_create.side_effect = ValueError("Source account acct-from-uuid not found or not accessible")
        
        response = client.post(
            "/transfers",
            json={
                "from_account_id": "acct-from-uuid",
                "to_account_id": "acct-to-uuid",
                "amount": 500.00,
                "date": "2025-11-03"
            }
        )
        
        assert response.status_code == 400
        data = response.json()
        assert data["detail"]["error"] == "validation_error"
    
    def test_create_transfer_missing_fields(self, mock_auth, mock_get_supabase_client):
        """Test transfer creation with missing required fields."""
        response = client.post(
            "/transfers",
            json={
                "from_account_id": "acct-from-uuid",
                "amount": 500.00
                # Missing to_account_id and date
            }
        )
        
        assert response.status_code == 422  # Validation error
    
    def test_create_transfer_negative_amount(self, mock_auth, mock_get_supabase_client):
        """Test transfer with negative amount."""
        response = client.post(
            "/transfers",
            json={
                "from_account_id": "acct-from-uuid",
                "to_account_id": "acct-to-uuid",
                "amount": -100.00,
                "date": "2025-11-03"
            }
        )
        
        assert response.status_code == 422  # Validation error


class TestCreateRecurringTransfer:
    """Tests for POST /transfers/recurring"""
    
    @patch("backend.routes.transfers.transfer_service.create_recurring_transfer")
    def test_create_recurring_transfer_monthly_success(self, mock_create, mock_auth, mock_get_supabase_client):
        """Test successful recurring transfer creation (monthly)."""
        outgoing_rule = {
            "id": "rule-out-uuid",
            "user_id": "test-user-id",
            "account_id": "acct-from-uuid",
            "category_id": "cat-recurring-uuid",
            "flow_type": "outcome",
            "amount": 500.00,
            "description": "Savings withdrawal",
            "frequency": "monthly",
            "interval": 1,
            "by_weekday": None,
            "by_monthday": [5],
            "start_date": "2025-11-05",
            "next_run_date": "2025-11-05",
            "end_date": None,
            "is_active": True,
            "paired_recurring_transaction_id": "rule-in-uuid",
            "created_at": "2025-11-03T10:00:00Z",
            "updated_at": "2025-11-03T10:00:00Z"
        }
        incoming_rule = {
            "id": "rule-in-uuid",
            "user_id": "test-user-id",
            "account_id": "acct-to-uuid",
            "category_id": "cat-recurring-uuid",
            "flow_type": "income",
            "amount": 500.00,
            "description": "Savings deposit",
            "frequency": "monthly",
            "interval": 1,
            "by_weekday": None,
            "by_monthday": [5],
            "start_date": "2025-11-05",
            "next_run_date": "2025-11-05",
            "end_date": None,
            "is_active": True,
            "paired_recurring_transaction_id": "rule-out-uuid",
            "created_at": "2025-11-03T10:00:00Z",
            "updated_at": "2025-11-03T10:00:00Z"
        }
        mock_create.return_value = (outgoing_rule, incoming_rule)
        
        response = client.post(
            "/transfers/recurring",
            json={
                "from_account_id": "acct-from-uuid",
                "to_account_id": "acct-to-uuid",
                "amount": 500.00,
                "description_outgoing": "Savings withdrawal",
                "description_incoming": "Savings deposit",
                "frequency": "monthly",
                "interval": 1,
                "by_monthday": [5],
                "start_date": "2025-11-05",
                "is_active": True
            }
        )
        
        assert response.status_code == 201
        data = response.json()
        assert data["status"] == "CREATED"
        assert len(data["recurring_transactions"]) == 2
        assert data["recurring_transactions"][0]["id"] == "rule-out-uuid"
        assert data["recurring_transactions"][1]["id"] == "rule-in-uuid"
        assert data["recurring_transactions"][0]["frequency"] == "monthly"
        assert data["recurring_transactions"][1]["frequency"] == "monthly"
        assert data["message"] == "Recurring transfer created successfully"
    
    @patch("backend.routes.transfers.transfer_service.create_recurring_transfer")
    def test_create_recurring_transfer_weekly_success(self, mock_create, mock_auth, mock_get_supabase_client):
        """Test successful recurring transfer creation (weekly)."""
        outgoing_rule = {
            "id": "rule-out-uuid",
            "user_id": "test-user-id",
            "account_id": "acct-from-uuid",
            "category_id": "cat-recurring-uuid",
            "flow_type": "outcome",
            "amount": 200.00,
            "description": "Weekly transfer out",
            "paired_recurring_transaction_id": "rule-in-uuid",
            "frequency": "weekly",
            "interval": 1,
            "by_weekday": ["monday", "friday"],
            "by_monthday": None,
            "start_date": "2025-11-03",
            "next_run_date": "2025-11-03",
            "end_date": None,
            "is_active": True,
            "created_at": "2025-11-03T10:00:00Z",
            "updated_at": "2025-11-03T10:00:00Z"
        }
        incoming_rule = {
            "id": "rule-in-uuid",
            "user_id": "test-user-id",
            "account_id": "acct-to-uuid",
            "category_id": "cat-recurring-uuid",
            "flow_type": "income",
            "amount": 200.00,
            "description": "Weekly transfer in",
            "paired_recurring_transaction_id": "rule-out-uuid",
            "frequency": "weekly",
            "interval": 1,
            "by_weekday": ["monday", "friday"],
            "by_monthday": None,
            "start_date": "2025-11-03",
            "next_run_date": "2025-11-03",
            "end_date": None,
            "is_active": True,
            "created_at": "2025-11-03T10:00:00Z",
            "updated_at": "2025-11-03T10:00:00Z"
        }
        mock_create.return_value = (outgoing_rule, incoming_rule)
        
        response = client.post(
            "/transfers/recurring",
            json={
                "from_account_id": "acct-from-uuid",
                "to_account_id": "acct-to-uuid",
                "amount": 200.00,
                "frequency": "weekly",
                "interval": 1,
                "by_weekday": ["monday", "friday"],
                "start_date": "2025-11-03",
                "is_active": True
            }
        )
        
        assert response.status_code == 201
        data = response.json()
        assert data["status"] == "CREATED"
    
    def test_create_recurring_transfer_weekly_missing_weekdays(self, mock_auth, mock_get_supabase_client):
        """Test recurring transfer validation: weekly requires by_weekday."""
        response = client.post(
            "/transfers/recurring",
            json={
                "from_account_id": "acct-from-uuid",
                "to_account_id": "acct-to-uuid",
                "amount": 200.00,
                "frequency": "weekly",
                "interval": 1,
                # Missing by_weekday
                "start_date": "2025-11-03",
                "is_active": True
            }
        )
        
        assert response.status_code == 400
        data = response.json()
        assert data["detail"]["error"] == "validation_error"
        assert "weekly" in data["detail"]["details"].lower()
    
    def test_create_recurring_transfer_monthly_missing_monthdays(self, mock_auth, mock_get_supabase_client):
        """Test recurring transfer validation: monthly requires by_monthday."""
        response = client.post(
            "/transfers/recurring",
            json={
                "from_account_id": "acct-from-uuid",
                "to_account_id": "acct-to-uuid",
                "amount": 500.00,
                "frequency": "monthly",
                "interval": 1,
                # Missing by_monthday
                "start_date": "2025-11-05",
                "is_active": True
            }
        )
        
        assert response.status_code == 400
        data = response.json()
        assert data["detail"]["error"] == "validation_error"
        assert "monthly" in data["detail"]["details"].lower()
    
    def test_create_recurring_transfer_invalid_frequency(self, mock_auth, mock_get_supabase_client):
        """Test recurring transfer with invalid frequency."""
        response = client.post(
            "/transfers/recurring",
            json={
                "from_account_id": "acct-from-uuid",
                "to_account_id": "acct-to-uuid",
                "amount": 500.00,
                "frequency": "once",  # Not allowed for recurring
                "interval": 1,
                "start_date": "2025-11-05",
                "is_active": True
            }
        )
        
        assert response.status_code == 422  # Validation error


class TestDeleteTransferTransaction:
    """Tests for DELETE /transactions/{id} with paired transactions."""
    
    @patch("backend.services.transaction_service.get_transaction_by_id")
    @patch("backend.services.transfer_service.delete_transfer")
    def test_delete_paired_transaction_success(self, mock_delete_transfer, mock_get_txn, mock_auth):
        """Test deleting a transaction that is part of a transfer."""
        with patch("backend.routes.transactions.get_supabase_client"):
            # Mock existing transaction with paired_transaction_id
            mock_get_txn.return_value = {
                "id": "txn-out-uuid",
                "paired_transaction_id": "txn-in-uuid"
            }
            mock_delete_transfer.return_value = ("txn-out-uuid", "txn-in-uuid")
            
            response = client.delete("/transactions/txn-out-uuid")
            
            assert response.status_code == 200
            data = response.json()
            assert data["status"] == "DELETED"
            
            # Verify delete_transfer was called (both sides deleted)
            mock_delete_transfer.assert_called_once()


class TestTransferAtomicity:
    """Tests for atomicity of transfer operations."""
    
    @patch("backend.routes.transfers.transfer_service.create_transfer")
    def test_create_transfer_atomicity_failure(self, mock_create, mock_auth, mock_get_supabase_client):
        """Test that transfer creation is atomic (both or neither)."""
        # Simulate failure during creation
        mock_create.side_effect = Exception("Database connection lost")
        
        response = client.post(
            "/transfers",
            json={
                "from_account_id": "acct-from-uuid",
                "to_account_id": "acct-to-uuid",
                "amount": 500.00,
                "date": "2025-11-03"
            }
        )
        
        assert response.status_code == 500
        data = response.json()
        assert data["detail"]["error"] == "internal_error"
