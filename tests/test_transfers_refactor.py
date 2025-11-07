"""
Integration tests for refactored transfer endpoints.

Verifies that transfers now return transaction arrays instead of transfer objects.
"""

import pytest
from unittest.mock import AsyncMock, MagicMock
from fastapi.testclient import TestClient

from backend.main import app
from backend.schemas.transfers import TransferCreateResponse, RecurringTransferCreateResponse
from backend.schemas.transactions import TransactionDetailResponse
from backend.schemas.recurring_transactions import RecurringTransactionResponse


@pytest.fixture
def client():
    """Create FastAPI test client."""
    return TestClient(app)


@pytest.fixture
def mock_auth_user(monkeypatch):
    """Mock authenticated user."""
    def mock_get_authenticated_user():
        return MagicMock(
            user_id="test-user-id",
            access_token="test-token"
        )
    
    monkeypatch.setattr(
        "backend.routes.transfers.get_authenticated_user",
        lambda: mock_get_authenticated_user()
    )


def test_transfer_create_response_has_transactions_array(mock_auth_user, monkeypatch):
    """Verify POST /transfers returns array of TransactionDetailResponse."""
    
    # Mock transaction service
    mock_outgoing = {
        "id": "txn-out-uuid",
        "user_id": "test-user-id",
        "account_id": "acct-source-uuid",
        "category_id": "cat-transfer-uuid",
        "invoice_id": None,
        "flow_type": "outcome",
        "amount": 500.0,
        "date": "2025-11-03T00:00:00Z",
        "description": "Test transfer",
        "paired_transaction_id": "txn-in-uuid",
        "created_at": "2025-11-03T10:15:00Z",
        "updated_at": "2025-11-03T10:15:00Z"
    }
    
    mock_incoming = {
        "id": "txn-in-uuid",
        "user_id": "test-user-id",
        "account_id": "acct-dest-uuid",
        "category_id": "cat-transfer-uuid",
        "invoice_id": None,
        "flow_type": "income",
        "amount": 500.0,
        "date": "2025-11-03T00:00:00Z",
        "description": "Test transfer",
        "paired_transaction_id": "txn-out-uuid",
        "created_at": "2025-11-03T10:15:00Z",
        "updated_at": "2025-11-03T10:15:00Z"
    }
    
    async def mock_create_transfer(*args, **kwargs):
        return (mock_outgoing, mock_incoming)
    
    monkeypatch.setattr(
        "backend.routes.transfers.transfer_service.create_transfer",
        mock_create_transfer
    )
    
    # Mock supabase client
    def mock_get_supabase_client(token):
        return MagicMock()
    
    monkeypatch.setattr(
        "backend.routes.transfers.get_supabase_client",
        mock_get_supabase_client
    )
    
    # Create request
    client = TestClient(app)
    response = client.post(
        "/transfers",
        json={
            "from_account_id": "acct-source-uuid",
            "to_account_id": "acct-dest-uuid",
            "amount": 500.0,
            "date": "2025-11-03",
            "description": "Test transfer"
        },
        headers={"Authorization": "Bearer test-token"}
    )
    
    assert response.status_code == 201
    data = response.json()
    
    # Verify response structure
    assert "status" in data
    assert data["status"] == "CREATED"
    assert "transactions" in data
    assert isinstance(data["transactions"], list)
    assert len(data["transactions"]) == 2
    
    # Verify first transaction (outcome)
    assert data["transactions"][0]["flow_type"] == "outcome"
    assert data["transactions"][0]["account_id"] == "acct-source-uuid"
    assert data["transactions"][0]["amount"] == 500.0
    
    # Verify second transaction (income)
    assert data["transactions"][1]["flow_type"] == "income"
    assert data["transactions"][1]["account_id"] == "acct-dest-uuid"
    assert data["transactions"][1]["amount"] == 500.0
    
    # Verify pairing
    assert data["transactions"][0]["paired_transaction_id"] == data["transactions"][1]["id"]
    assert data["transactions"][1]["paired_transaction_id"] == data["transactions"][0]["id"]


def test_recurring_transfer_create_response_has_rules_array(mock_auth_user, monkeypatch):
    """Verify POST /transfers/recurring returns array of RecurringTransactionResponse."""
    
    # Mock recurring transaction service
    mock_outgoing_rule = {
        "id": "rule-out-uuid",
        "user_id": "test-user-id",
        "account_id": "acct-source-uuid",
        "category_id": "cat-transfer-uuid",
        "flow_type": "outcome",
        "amount": 500.0,
        "description": "Monthly savings out",
        "paired_recurring_transaction_id": "rule-in-uuid",
        "frequency": "monthly",
        "interval": 1,
        "by_weekday": None,
        "by_monthday": [5],
        "start_date": "2025-11-05",
        "next_run_date": "2025-11-05",
        "end_date": None,
        "is_active": True,
        "created_at": "2025-11-03T10:00:00Z",
        "updated_at": "2025-11-03T10:00:00Z"
    }
    
    mock_incoming_rule = {
        "id": "rule-in-uuid",
        "user_id": "test-user-id",
        "account_id": "acct-dest-uuid",
        "category_id": "cat-transfer-uuid",
        "flow_type": "income",
        "amount": 500.0,
        "description": "Monthly savings in",
        "paired_recurring_transaction_id": "rule-out-uuid",
        "frequency": "monthly",
        "interval": 1,
        "by_weekday": None,
        "by_monthday": [5],
        "start_date": "2025-11-05",
        "next_run_date": "2025-11-05",
        "end_date": None,
        "is_active": True,
        "created_at": "2025-11-03T10:00:00Z",
        "updated_at": "2025-11-03T10:00:00Z"
    }
    
    async def mock_create_recurring_transfer(*args, **kwargs):
        return (mock_outgoing_rule, mock_incoming_rule)
    
    monkeypatch.setattr(
        "backend.routes.transfers.transfer_service.create_recurring_transfer",
        mock_create_recurring_transfer
    )
    
    # Mock supabase client
    def mock_get_supabase_client(token):
        return MagicMock()
    
    monkeypatch.setattr(
        "backend.routes.transfers.get_supabase_client",
        mock_get_supabase_client
    )
    
    # Create request
    client = TestClient(app)
    response = client.post(
        "/transfers/recurring",
        json={
            "from_account_id": "acct-source-uuid",
            "to_account_id": "acct-dest-uuid",
            "amount": 500.0,
            "description_outgoing": "Monthly savings out",
            "description_incoming": "Monthly savings in",
            "frequency": "monthly",
            "interval": 1,
            "by_monthday": [5],
            "start_date": "2025-11-05"
        },
        headers={"Authorization": "Bearer test-token"}
    )
    
    assert response.status_code == 201
    data = response.json()
    
    # Verify response structure
    assert "status" in data
    assert data["status"] == "CREATED"
    assert "recurring_transactions" in data
    assert isinstance(data["recurring_transactions"], list)
    assert len(data["recurring_transactions"]) == 2
    
    # Verify first rule (outcome)
    assert data["recurring_transactions"][0]["flow_type"] == "outcome"
    assert data["recurring_transactions"][0]["account_id"] == "acct-source-uuid"
    assert data["recurring_transactions"][0]["frequency"] == "monthly"
    
    # Verify second rule (income)
    assert data["recurring_transactions"][1]["flow_type"] == "income"
    assert data["recurring_transactions"][1]["account_id"] == "acct-dest-uuid"
    assert data["recurring_transactions"][1]["frequency"] == "monthly"
    
    # Verify pairing
    assert (
        data["recurring_transactions"][0]["paired_recurring_transaction_id"] ==
        data["recurring_transactions"][1]["id"]
    )
    assert (
        data["recurring_transactions"][1]["paired_recurring_transaction_id"] ==
        data["recurring_transactions"][0]["id"]
    )


def test_response_schemas_match_transaction_schemas():
    """Verify TransferCreateResponse transactions use TransactionDetailResponse."""
    
    # Create sample transaction data
    txn = {
        "id": "txn-uuid",
        "user_id": "user-uuid",
        "account_id": "acct-uuid",
        "category_id": "cat-uuid",
        "invoice_id": None,
        "flow_type": "outcome",
        "amount": 100.0,
        "date": "2025-11-03T00:00:00Z",
        "description": "Test",
        "paired_transaction_id": None,
        "created_at": "2025-11-03T10:15:00Z",
        "updated_at": "2025-11-03T10:15:00Z"
    }
    
    # Validate it can be parsed as TransactionDetailResponse
    txn_response = TransactionDetailResponse(**txn)
    assert txn_response.id == "txn-uuid"
    assert txn_response.flow_type == "outcome"
    
    # Validate it can be used in TransferCreateResponse
    transfer_response = TransferCreateResponse(
        status="CREATED",
        transactions=[txn_response, txn_response],
        message="Test"
    )
    assert len(transfer_response.transactions) == 2
    assert all(isinstance(t, TransactionDetailResponse) for t in transfer_response.transactions)


def test_response_schemas_match_recurring_transaction_schemas():
    """Verify RecurringTransferCreateResponse uses RecurringTransactionResponse."""
    
    # Create sample recurring transaction data
    rule = {
        "id": "rule-uuid",
        "user_id": "user-uuid",
        "account_id": "acct-uuid",
        "category_id": "cat-uuid",
        "flow_type": "outcome",
        "amount": 100.0,
        "description": "Test rule",
        "paired_recurring_transaction_id": None,
        "frequency": "monthly",
        "interval": 1,
        "by_weekday": None,
        "by_monthday": [5],
        "start_date": "2025-11-05",
        "next_run_date": "2025-11-05",
        "end_date": None,
        "is_active": True,
        "created_at": "2025-11-03T10:00:00Z",
        "updated_at": "2025-11-03T10:00:00Z"
    }
    
    # Validate it can be parsed as RecurringTransactionResponse
    rule_response = RecurringTransactionResponse(**rule)
    assert rule_response.id == "rule-uuid"
    assert rule_response.frequency == "monthly"
    
    # Validate it can be used in RecurringTransferCreateResponse
    recurring_transfer_response = RecurringTransferCreateResponse(
        status="CREATED",
        recurring_transactions=[rule_response, rule_response],
        message="Test"
    )
    assert len(recurring_transfer_response.recurring_transactions) == 2
    assert all(
        isinstance(r, RecurringTransactionResponse)
        for r in recurring_transfer_response.recurring_transactions
    )
