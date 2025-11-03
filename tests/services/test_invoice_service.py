"""
Tests for invoice persistence service.

Tests the canonical EXTRACTED_INVOICE_TEXT_FORMAT and RLS integration.
"""

import pytest
from unittest.mock import Mock, AsyncMock, patch
from backend.services.invoice_service import (
    format_extracted_text,
    create_invoice,
    get_user_invoices
)


class TestFormatExtractedText:
    """Test the canonical invoice text formatter."""
    
    def test_format_extracted_text_produces_correct_template(self):
        """Verify that format_extracted_text produces the exact canonical format."""
        result = format_extracted_text(
            store_name="Super Despensa Familiar",
            transaction_time="2025-10-30T14:32:00-06:00",
            total_amount="128.50",
            currency="GTQ",
            purchased_items="- Leche deslactosada 1L (2x Q15.50)\n- Pan integral (1x Q12.00)",
            nit="12345678-9"
        )
        
        expected = """Store Name: Super Despensa Familiar
Transaction Time: 2025-10-30T14:32:00-06:00
Total Amount: 128.50
Currency: GTQ
Purchased Items:
- Leche deslactosada 1L (2x Q15.50)
- Pan integral (1x Q12.00)
NIT: 12345678-9"""
        
        assert result == expected
    
    def test_format_extracted_text_handles_empty_items(self):
        """Test formatting with empty purchased items."""
        result = format_extracted_text(
            store_name="Tienda Local",
            transaction_time="2025-11-01T10:00:00Z",
            total_amount="50.00",
            currency="USD",
            purchased_items="",
            nit="N/A"
        )
        
        assert "Store Name: Tienda Local" in result
        assert "NIT: N/A" in result
        assert "Purchased Items:\n" in result


class TestCreateInvoice:
    """Test invoice creation with RLS enforcement."""
    
    @pytest.mark.asyncio
    async def test_create_invoice_formats_and_inserts_correctly(self):
        """Verify create_invoice formats data and calls Supabase correctly."""
        # Mock Supabase client
        mock_client = Mock()
        mock_table = Mock()
        mock_insert = Mock()
        mock_execute = Mock()
        
        mock_client.table.return_value = mock_table
        mock_table.insert.return_value = mock_insert
        mock_execute.data = [{"id": "invoice-uuid-123", "user_id": "user-123"}]
        mock_insert.execute.return_value = mock_execute
        
        # Call service
        result = await create_invoice(
            supabase_client=mock_client,
            user_id="user-123",
            storage_path="/invoices/receipt.jpg",
            store_name="Test Store",
            transaction_time="2025-11-02T12:00:00Z",
            total_amount="100.00",
            currency="GTQ",
            purchased_items="- Item 1 (1x Q100.00)",
            nit="987654321"
        )
        
        # Verify Supabase calls
        mock_client.table.assert_called_once_with("invoice")
        
        # Verify insert was called with correct data structure
        insert_call_args = mock_table.insert.call_args
        inserted_data = insert_call_args[0][0]
        
        assert inserted_data["user_id"] == "user-123"
        assert inserted_data["storage_path"] == "/invoices/receipt.jpg"
        assert "extracted_text" in inserted_data
        
        # Verify extracted_text follows canonical format
        extracted_text = inserted_data["extracted_text"]
        assert "Store Name: Test Store" in extracted_text
        assert "Total Amount: 100.00" in extracted_text
        assert "Currency: GTQ" in extracted_text
        assert "NIT: 987654321" in extracted_text
        
        # Verify result
        assert result["id"] == "invoice-uuid-123"
    
    @pytest.mark.asyncio
    async def test_create_invoice_raises_on_empty_result(self):
        """Test that create_invoice raises when Supabase returns no data."""
        mock_client = Mock()
        mock_table = Mock()
        mock_insert = Mock()
        mock_execute = Mock()
        
        mock_client.table.return_value = mock_table
        mock_table.insert.return_value = mock_insert
        mock_execute.data = []  # Empty result
        mock_insert.execute.return_value = mock_execute
        
        with pytest.raises(Exception, match="Failed to create invoice"):
            await create_invoice(
                supabase_client=mock_client,
                user_id="user-123",
                storage_path="/test.jpg",
                store_name="Store",
                transaction_time="2025-11-02T12:00:00Z",
                total_amount="50.00",
                currency="GTQ",
                purchased_items="",
                nit="N/A"
            )


class TestGetUserInvoices:
    """Test fetching user invoices with RLS."""
    
    @pytest.mark.asyncio
    async def test_get_user_invoices_returns_list(self):
        """Verify get_user_invoices fetches and returns invoice list."""
        # Mock Supabase client
        mock_client = Mock()
        mock_table = Mock()
        mock_select = Mock()
        mock_order = Mock()
        mock_range = Mock()
        mock_execute = Mock()
        
        mock_client.table.return_value = mock_table
        mock_table.select.return_value = mock_select
        mock_select.order.return_value = mock_order
        mock_order.range.return_value = mock_range
        mock_execute.data = [
            {"id": "inv-1", "user_id": "user-123", "store_name": "Store A"},
            {"id": "inv-2", "user_id": "user-123", "store_name": "Store B"}
        ]
        mock_range.execute.return_value = mock_execute
        
        # Call service
        result = await get_user_invoices(
            supabase_client=mock_client,
            user_id="user-123",
            limit=10,
            offset=0
        )
        
        # Verify calls
        mock_client.table.assert_called_once_with("invoice")
        mock_table.select.assert_called_once_with("*")
        mock_select.order.assert_called_once_with("created_at", desc=True)
        mock_order.range.assert_called_once_with(0, 9)  # offset 0, limit 10
        
        # Verify result
        assert len(result) == 2
        assert result[0]["id"] == "inv-1"
        assert result[1]["id"] == "inv-2"
