"""
Comprehensive tests for all Supabase RPC functions.

Tests atomic operations, error handling, and business rules for:
- create_transfer
- create_recurring_transfer
- create_wishlist_with_items
- delete_transfer_both_sides
- delete_account_reassign
- delete_account_cascade
- delete_category_reassign
- delete_recurring_transaction_and_pair
"""

import pytest
from decimal import Decimal
from datetime import date, datetime
from typing import Dict, Any, cast
import uuid
import json

from supabase import Client


# ============================================================================
# FIXTURES
# ============================================================================

@pytest.fixture
def test_user_id() -> str:
    """Generate a test user UUID."""
    return str(uuid.uuid4())


@pytest.fixture
def test_account(supabase_client: Client, test_user_id: str) -> Dict[str, Any]:
    """Create a test account for RPC operations."""
    account_data = {
        "user_id": test_user_id,
        "name": "Test Account",
        "type": "bank",
        "currency": "GTQ"
    }
    result = supabase_client.table("account").insert(account_data).execute()
    return cast(Dict[str, Any], result.data[0])


@pytest.fixture
def test_category(supabase_client: Client, test_user_id: str) -> Dict[str, Any]:
    """Create a test category for RPC operations."""
    category_data = {
        "user_id": test_user_id,
        "name": "Test Category",
        "flow_type": "outcome"
    }
    result = supabase_client.table("category").insert(category_data).execute()
    return cast(Dict[str, Any], result.data[0])


@pytest.fixture
def transfer_category(supabase_client: Client) -> Dict[str, Any]:
    """Get the system 'transfer' category."""
    result = (
        supabase_client.table("category")
        .select("*")
        .eq("key", "transfer")
        .single()
        .execute()
    )
    return cast(Dict[str, Any], result.data)


# ============================================================================
# TEST: create_transfer RPC
# ============================================================================

def test_create_transfer_success(
    supabase_client: Client,
    test_user_id: str,
    test_account: Dict[str, Any],
    transfer_category: Dict[str, Any]
):
    """Test successful transfer creation between two accounts."""
    # Create second account
    account2_data = {
        "user_id": test_user_id,
        "name": "Test Account 2",
        "type": "cash",
        "currency": "GTQ"
    }
    account2_result = supabase_client.table("account").insert(account2_data).execute()
    account2 = cast(Dict[str, Any], account2_result.data[0])
    
    # Call RPC
    rpc_result = supabase_client.rpc(
        "create_transfer",
        {
            "p_user_id": test_user_id,
            "p_from_account_id": test_account["id"],
            "p_to_account_id": account2["id"],
            "p_amount": "150.00",
            "p_date": str(date.today()),
            "p_description": "Test transfer",
            "p_transfer_category_id": transfer_category["id"]
        }
    ).execute()
    
    # Verify RPC returned both transaction IDs
    assert rpc_result.data is not None
    assert len(rpc_result.data) == 1
    
    result = cast(Dict[str, Any], rpc_result.data[0])
    outgoing_id = result["outgoing_transaction_id"]
    incoming_id = result["incoming_transaction_id"]
    
    assert outgoing_id is not None
    assert incoming_id is not None
    assert outgoing_id != incoming_id
    
    # Verify outgoing transaction
    outgoing = supabase_client.table("transaction").select("*").eq("id", outgoing_id).single().execute()
    outgoing_data = cast(Dict[str, Any], outgoing.data)
    
    assert outgoing_data["account_id"] == test_account["id"]
    assert outgoing_data["flow_type"] == "outcome"
    assert Decimal(str(outgoing_data["amount"])) == Decimal("150.00")
    assert outgoing_data["paired_transaction_id"] == incoming_id
    
    # Verify incoming transaction
    incoming = supabase_client.table("transaction").select("*").eq("id", incoming_id).single().execute()
    incoming_data = cast(Dict[str, Any], incoming.data)
    
    assert incoming_data["account_id"] == account2["id"]
    assert incoming_data["flow_type"] == "income"
    assert Decimal(str(incoming_data["amount"])) == Decimal("150.00")
    assert incoming_data["paired_transaction_id"] == outgoing_id


def test_create_transfer_invalid_source_account(
    supabase_client: Client,
    test_user_id: str,
    test_account: Dict[str, Any],
    transfer_category: Dict[str, Any]
):
    """Test transfer fails with invalid source account."""
    fake_account_id = str(uuid.uuid4())
    
    with pytest.raises(Exception) as exc_info:
        supabase_client.rpc(
            "create_transfer",
            {
                "p_user_id": test_user_id,
                "p_from_account_id": fake_account_id,
                "p_to_account_id": test_account["id"],
                "p_amount": "100.00",
                "p_date": str(date.today()),
                "p_description": "Invalid transfer",
                "p_transfer_category_id": transfer_category["id"]
            }
        ).execute()
    
    assert "Source account not found" in str(exc_info.value)


# ============================================================================
# TEST: create_recurring_transfer RPC
# ============================================================================

def test_create_recurring_transfer_success(
    supabase_client: Client,
    test_user_id: str,
    test_account: Dict[str, Any],
    transfer_category: Dict[str, Any]
):
    """Test successful recurring transfer creation."""
    # Create second account
    account2_data = {
        "user_id": test_user_id,
        "name": "Savings Account",
        "type": "bank",
        "currency": "GTQ"
    }
    account2_result = supabase_client.table("account").insert(account2_data).execute()
    account2 = cast(Dict[str, Any], account2_result.data[0])
    
    # Call RPC
    rpc_result = supabase_client.rpc(
        "create_recurring_transfer",
        {
            "p_user_id": test_user_id,
            "p_from_account_id": test_account["id"],
            "p_to_account_id": account2["id"],
            "p_amount": "500.00",
            "p_description": "Monthly savings",
            "p_frequency": "monthly",
            "p_interval": 1,
            "p_by_monthday": json.dumps([1]),
            "p_start_date": str(date.today()),
            "p_transfer_category_id": transfer_category["id"]
        }
    ).execute()
    
    # Verify RPC returned both recurring transaction IDs
    assert rpc_result.data is not None
    assert len(rpc_result.data) == 1
    
    result = cast(Dict[str, Any], rpc_result.data[0])
    outgoing_id = result["outgoing_recurring_id"]
    incoming_id = result["incoming_recurring_id"]
    
    assert outgoing_id is not None
    assert incoming_id is not None
    
    # Verify both recurring transactions exist and are paired
    outgoing = supabase_client.table("recurring_transaction").select("*").eq("id", outgoing_id).single().execute()
    outgoing_data = cast(Dict[str, Any], outgoing.data)
    
    assert outgoing_data["flow_type"] == "outcome"
    assert outgoing_data["paired_recurring_transaction_id"] == incoming_id
    
    incoming = supabase_client.table("recurring_transaction").select("*").eq("id", incoming_id).single().execute()
    incoming_data = cast(Dict[str, Any], incoming.data)
    
    assert incoming_data["flow_type"] == "income"
    assert incoming_data["paired_recurring_transaction_id"] == outgoing_id


# ============================================================================
# TEST: create_wishlist_with_items RPC
# ============================================================================

def test_create_wishlist_with_items_success(
    supabase_client: Client,
    test_user_id: str
):
    """Test successful atomic wishlist+items creation."""
    items_data = [
        {
            "product_title": "Test Product 1",
            "price_total": "150.00",
            "seller_name": "Test Store",
            "url": "https://example.com/product1",
            "pickup_available": True,
            "warranty_info": "12 months",
            "copy_for_user": "Great product for testing",
            "badges": json.dumps(["Test", "Quality"])
        },
        {
            "product_title": "Test Product 2",
            "price_total": "250.00",
            "seller_name": "Test Store 2",
            "url": "https://example.com/product2",
            "pickup_available": False,
            "warranty_info": "",
            "copy_for_user": "Another test product",
            "badges": json.dumps(["Premium"])
        }
    ]
    
    # Call RPC
    rpc_result = supabase_client.rpc(
        "create_wishlist_with_items",
        {
            "p_user_id": test_user_id,
            "p_goal_title": "Test Wishlist",
            "p_budget_hint": "500.00",
            "p_currency_code": "GTQ",
            "p_target_date": str(date.today()),
            "p_preferred_store": "Test Store",
            "p_user_note": "Testing RPC",
            "p_items": json.dumps(items_data)
        }
    ).execute()
    
    # Verify RPC response
    assert rpc_result.data is not None
    assert len(rpc_result.data) == 1
    
    result = cast(Dict[str, Any], rpc_result.data[0])
    wishlist_id = result["wishlist_id"]
    items_created = result["items_created"]
    
    assert wishlist_id is not None
    assert items_created == 2
    
    # Verify wishlist exists
    wishlist = supabase_client.table("wishlist").select("*").eq("id", wishlist_id).single().execute()
    wishlist_data = cast(Dict[str, Any], wishlist.data)
    
    assert wishlist_data["goal_title"] == "Test Wishlist"
    assert Decimal(str(wishlist_data["budget_hint"])) == Decimal("500.00")
    assert wishlist_data["status"] == "active"
    
    # Verify items exist
    items = supabase_client.table("wishlist_item").select("*").eq("wishlist_id", wishlist_id).execute()
    items_data_result = cast(list, items.data)
    
    assert len(items_data_result) == 2
    assert items_data_result[0]["product_title"] == "Test Product 1"
    assert items_data_result[1]["product_title"] == "Test Product 2"


def test_create_wishlist_with_items_no_items(
    supabase_client: Client,
    test_user_id: str
):
    """Test wishlist creation with empty items array."""
    # Call RPC with no items
    rpc_result = supabase_client.rpc(
        "create_wishlist_with_items",
        {
            "p_user_id": test_user_id,
            "p_goal_title": "Empty Wishlist",
            "p_budget_hint": "1000.00",
            "p_currency_code": "GTQ",
            "p_target_date": None,
            "p_preferred_store": None,
            "p_user_note": None,
            "p_items": json.dumps([])
        }
    ).execute()
    
    result = cast(Dict[str, Any], rpc_result.data[0])
    assert result["items_created"] == 0
    
    # Verify wishlist exists but has no items
    wishlist_id = result["wishlist_id"]
    items = supabase_client.table("wishlist_item").select("*").eq("wishlist_id", wishlist_id).execute()
    
    assert len(cast(list, items.data)) == 0


def test_create_wishlist_with_items_atomicity(
    supabase_client: Client,
    test_user_id: str
):
    """Test that RPC is atomic: if items fail, wishlist is not created."""
    # Create items with invalid data (price_total as invalid string)
    items_data = [
        {
            "product_title": "Test Product",
            "price_total": "invalid_price",  # This should cause failure
            "seller_name": "Test Store",
            "url": "https://example.com/product",
            "pickup_available": True,
            "warranty_info": "",
            "copy_for_user": "Test",
            "badges": json.dumps([])
        }
    ]
    
    # Call RPC - should fail
    with pytest.raises(Exception):
        supabase_client.rpc(
            "create_wishlist_with_items",
            {
                "p_user_id": test_user_id,
                "p_goal_title": "Should Fail",
                "p_budget_hint": "100.00",
                "p_currency_code": "GTQ",
                "p_target_date": None,
                "p_preferred_store": None,
                "p_user_note": None,
                "p_items": json.dumps(items_data)
            }
        ).execute()
    
    # Verify no wishlist was created (atomicity check)
    wishlists = supabase_client.table("wishlist").select("*").eq("user_id", test_user_id).execute()
    assert len(cast(list, wishlists.data)) == 0


# ============================================================================
# TEST: delete_transfer_both_sides RPC
# ============================================================================

def test_delete_transfer_both_sides_success(
    supabase_client: Client,
    test_user_id: str,
    test_account: Dict[str, Any],
    transfer_category: Dict[str, Any]
):
    """Test successful deletion of both sides of a transfer."""
    # Create second account
    account2_data = {
        "user_id": test_user_id,
        "name": "Account 2",
        "type": "cash",
        "currency": "GTQ"
    }
    account2_result = supabase_client.table("account").insert(account2_data).execute()
    account2 = cast(Dict[str, Any], account2_result.data[0])
    
    # Create transfer using RPC
    create_result = supabase_client.rpc(
        "create_transfer",
        {
            "p_user_id": test_user_id,
            "p_from_account_id": test_account["id"],
            "p_to_account_id": account2["id"],
            "p_amount": "200.00",
            "p_date": str(date.today()),
            "p_description": "Transfer to delete",
            "p_transfer_category_id": transfer_category["id"]
        }
    ).execute()
    
    result = cast(Dict[str, Any], create_result.data[0])
    outgoing_id = result["outgoing_transaction_id"]
    incoming_id = result["incoming_transaction_id"]
    
    # Delete transfer using RPC
    delete_result = supabase_client.rpc(
        "delete_transfer_both_sides",
        {
            "p_user_id": test_user_id,
            "p_transaction_id": outgoing_id
        }
    ).execute()
    
    # Verify both transactions are deleted
    outgoing_check = supabase_client.table("transaction").select("*").eq("id", outgoing_id).execute()
    incoming_check = supabase_client.table("transaction").select("*").eq("id", incoming_id).execute()
    
    assert len(cast(list, outgoing_check.data)) == 0
    assert len(cast(list, incoming_check.data)) == 0


# ============================================================================
# TEST: delete_category_reassign RPC
# ============================================================================

def test_delete_category_reassign_success(
    supabase_client: Client,
    test_user_id: str,
    test_account: Dict[str, Any],
    test_category: Dict[str, Any]
):
    """Test successful category deletion with transaction reassignment."""
    # Get general category
    general_cat = supabase_client.table("category").select("*").eq("key", "general").single().execute()
    general_category = cast(Dict[str, Any], general_cat.data)
    
    # Create transactions with test category
    transactions = []
    for i in range(3):
        txn_data = {
            "user_id": test_user_id,
            "account_id": test_account["id"],
            "category_id": test_category["id"],
            "flow_type": "outcome",
            "amount": f"{100 * (i + 1)}.00",
            "date": str(date.today()),
            "description": f"Test transaction {i + 1}",
            "source": "manual"
        }
        txn_result = supabase_client.table("transaction").insert(txn_data).execute()
        transactions.append(cast(Dict[str, Any], txn_result.data[0]))
    
    # Delete category using RPC
    delete_result = supabase_client.rpc(
        "delete_category_reassign",
        {
            "p_user_id": test_user_id,
            "p_category_id": test_category["id"],
            "p_general_category_id": general_category["id"]
        }
    ).execute()
    
    result = cast(Dict[str, Any], delete_result.data[0])
    assert result["transactions_reassigned"] == 3
    assert result["budget_links_removed"] >= 0
    
    # Verify category is deleted
    cat_check = supabase_client.table("category").select("*").eq("id", test_category["id"]).execute()
    assert len(cast(list, cat_check.data)) == 0
    
    # Verify transactions are reassigned to general
    for txn in transactions:
        txn_check = supabase_client.table("transaction").select("*").eq("id", txn["id"]).single().execute()
        txn_data = cast(Dict[str, Any], txn_check.data)
        assert txn_data["category_id"] == general_category["id"]


# ============================================================================
# TEST: delete_account_reassign RPC
# ============================================================================

def test_delete_account_reassign_success(
    supabase_client: Client,
    test_user_id: str,
    test_account: Dict[str, Any],
    test_category: Dict[str, Any]
):
    """Test successful account deletion with transaction reassignment."""
    # Create target account
    target_account_data = {
        "user_id": test_user_id,
        "name": "Target Account",
        "type": "bank",
        "currency": "GTQ"
    }
    target_result = supabase_client.table("account").insert(target_account_data).execute()
    target_account = cast(Dict[str, Any], target_result.data[0])
    
    # Create transactions in source account
    for i in range(2):
        txn_data = {
            "user_id": test_user_id,
            "account_id": test_account["id"],
            "category_id": test_category["id"],
            "flow_type": "outcome",
            "amount": f"{50 * (i + 1)}.00",
            "date": str(date.today()),
            "description": f"Transaction {i + 1}",
            "source": "manual"
        }
        supabase_client.table("transaction").insert(txn_data).execute()
    
    # Delete account using RPC
    delete_result = supabase_client.rpc(
        "delete_account_reassign",
        {
            "p_user_id": test_user_id,
            "p_account_id": test_account["id"],
            "p_target_account_id": target_account["id"]
        }
    ).execute()
    
    result = cast(Dict[str, Any], delete_result.data[0])
    assert result["transactions_reassigned"] == 2
    
    # Verify account is deleted
    account_check = supabase_client.table("account").select("*").eq("id", test_account["id"]).execute()
    assert len(cast(list, account_check.data)) == 0
    
    # Verify transactions are reassigned
    txns = supabase_client.table("transaction").select("*").eq("account_id", target_account["id"]).execute()
    assert len(cast(list, txns.data)) == 2


# ============================================================================
# TEST: delete_account_cascade RPC
# ============================================================================

def test_delete_account_cascade_success(
    supabase_client: Client,
    test_user_id: str,
    test_account: Dict[str, Any],
    test_category: Dict[str, Any]
):
    """Test successful account deletion with transaction cascade."""
    # Create transactions
    transaction_ids = []
    for i in range(2):
        txn_data = {
            "user_id": test_user_id,
            "account_id": test_account["id"],
            "category_id": test_category["id"],
            "flow_type": "income",
            "amount": f"{100 * (i + 1)}.00",
            "date": str(date.today()),
            "description": f"To delete {i + 1}",
            "source": "manual"
        }
        txn_result = supabase_client.table("transaction").insert(txn_data).execute()
        transaction_ids.append(cast(Dict[str, Any], txn_result.data[0])["id"])
    
    # Delete account using cascade RPC
    delete_result = supabase_client.rpc(
        "delete_account_cascade",
        {
            "p_user_id": test_user_id,
            "p_account_id": test_account["id"]
        }
    ).execute()
    
    result = cast(Dict[str, Any], delete_result.data[0])
    assert result["transactions_deleted"] == 2
    
    # Verify account is deleted
    account_check = supabase_client.table("account").select("*").eq("id", test_account["id"]).execute()
    assert len(cast(list, account_check.data)) == 0
    
    # Verify transactions are deleted
    for txn_id in transaction_ids:
        txn_check = supabase_client.table("transaction").select("*").eq("id", txn_id).execute()
        assert len(cast(list, txn_check.data)) == 0


# ============================================================================
# TEST: delete_recurring_transaction_and_pair RPC
# ============================================================================

def test_delete_recurring_transaction_and_pair_success(
    supabase_client: Client,
    test_user_id: str,
    test_account: Dict[str, Any],
    transfer_category: Dict[str, Any]
):
    """Test successful deletion of paired recurring transactions."""
    # Create second account
    account2_data = {
        "user_id": test_user_id,
        "name": "Account 2",
        "type": "savings",
        "currency": "GTQ"
    }
    account2_result = supabase_client.table("account").insert(account2_data).execute()
    account2 = cast(Dict[str, Any], account2_result.data[0])
    
    # Create recurring transfer
    create_result = supabase_client.rpc(
        "create_recurring_transfer",
        {
            "p_user_id": test_user_id,
            "p_from_account_id": test_account["id"],
            "p_to_account_id": account2["id"],
            "p_amount": "300.00",
            "p_description": "Monthly transfer",
            "p_frequency": "monthly",
            "p_interval": 1,
            "p_by_monthday": json.dumps([15]),
            "p_start_date": str(date.today()),
            "p_transfer_category_id": transfer_category["id"]
        }
    ).execute()
    
    result = cast(Dict[str, Any], create_result.data[0])
    outgoing_id = result["outgoing_recurring_id"]
    incoming_id = result["incoming_recurring_id"]
    
    # Delete using RPC
    delete_result = supabase_client.rpc(
        "delete_recurring_transaction_and_pair",
        {
            "p_user_id": test_user_id,
            "p_recurring_transaction_id": outgoing_id
        }
    ).execute()
    
    # Verify both are deleted
    outgoing_check = supabase_client.table("recurring_transaction").select("*").eq("id", outgoing_id).execute()
    incoming_check = supabase_client.table("recurring_transaction").select("*").eq("id", incoming_id).execute()
    
    assert len(cast(list, outgoing_check.data)) == 0
    assert len(cast(list, incoming_check.data)) == 0


