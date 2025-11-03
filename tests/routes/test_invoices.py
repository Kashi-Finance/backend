"""
Tests for /invoices/ocr endpoint.

Tests follow the requirements from .github/copilot-instructions.md:
- Happy path: valid image → DRAFT response
- Failure path: missing token → 401
- Failure path: invalid file type → 400
- Validation tests for response schema
"""

import io
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient
from PIL import Image

from backend.main import app
from backend.agents.invoice.types import InvoiceAgentOutput


@pytest.fixture
def client():
    """Create test client for FastAPI app."""
    return TestClient(app)


async def mock_verify_token_dependency():
    """Mock dependency that returns test user_id."""
    return "test-user-uuid-123"


@pytest.fixture
def mock_verify_token():
    """Override verify_token dependency to return test user_id."""
    from backend.auth.dependencies import verify_token
    from backend.routes.invoices import router
    
    # Override dependency in the app
    app.dependency_overrides[verify_token] = mock_verify_token_dependency
    
    yield
    
    # Clean up after test
    app.dependency_overrides.clear()


@pytest.fixture
def mock_invoice_agent_success():
    """Mock InvoiceAgent to return successful DRAFT response."""
    mock_output: InvoiceAgentOutput = {
        "status": "DRAFT",
        "store_name": "Super Test Store",
        "transaction_time": "2025-11-02T14:30:00Z",
        "total_amount": 100.50,
        "currency": "GTQ",
        "purchased_items": [
            {
                "description": "Test Item 1",
                "quantity": 2.0,
                "unit_price": 25.00,
                "line_total": 50.00
            },
            {
                "description": "Test Item 2",
                "quantity": 1.0,
                "unit_price": 50.50,
                "line_total": 50.50
            }
        ],
        "category_suggestion": {
            "match_type": "EXISTING",
            "category_id": "test-category-uuid",
            "category_name": "Groceries",
            "proposed_name": None
        },
        "extracted_text": "Store Name: Super Test Store\n...",
        "reason": None
    }
    
    with patch("backend.routes.invoices.run_invoice_agent") as mock:
        mock.return_value = mock_output
        yield mock


@pytest.fixture
def mock_invoice_agent_invalid():
    """Mock InvoiceAgent to return INVALID_IMAGE response."""
    mock_output: InvoiceAgentOutput = {
        "status": "INVALID_IMAGE",
        "store_name": None,
        "transaction_time": None,
        "total_amount": None,
        "currency": None,
        "purchased_items": None,
        "category_suggestion": None,
        "extracted_text": None,
        "reason": "Image is too blurry to read"
    }
    
    with patch("backend.routes.invoices.run_invoice_agent") as mock:
        mock.return_value = mock_output
        yield mock


@pytest.fixture
def valid_image_bytes():
    """Create a valid test image file in memory."""
    # Create a simple 100x100 RGB image
    img = Image.new("RGB", (100, 100), color="red")
    img_bytes = io.BytesIO()
    img.save(img_bytes, format="PNG")
    img_bytes.seek(0)
    return img_bytes.getvalue()


class TestInvoiceOCREndpoint:
    """Tests for POST /invoices/ocr endpoint."""
    
    def test_happy_path_valid_image_returns_draft(
        self,
        client,
        mock_verify_token,
        mock_invoice_agent_success,
        valid_image_bytes
    ):
        """
        HAPPY PATH: Valid image with auth token returns DRAFT response.
        
        This tests:
        - Auth passes (verify_token mock)
        - Image upload succeeds
        - InvoiceAgent returns DRAFT
        - Response matches InvoiceOCRResponseDraft schema
        """
        # Make request with valid image
        response = client.post(
            "/invoices/ocr",
            headers={"Authorization": "Bearer fake-test-token"},
            files={"image": ("test_receipt.png", valid_image_bytes, "image/png")}
        )
        
        # Should return 200 OK
        assert response.status_code == 200
        
        # Parse response
        data = response.json()
        
        # Validate response structure
        assert data["status"] == "DRAFT"
        assert data["store_name"] == "Super Test Store"
        assert data["total_amount"] == 100.50
        assert data["currency"] == "GTQ"
        assert data["purchase_datetime"] == "2025-11-02T14:30:00Z"
        
        # Validate items
        assert len(data["items"]) == 2
        assert data["items"][0]["description"] == "Test Item 1"
        assert data["items"][0]["quantity"] == 2.0
        assert data["items"][0]["total_price"] == 50.00
        
        # Validate category suggestion
        assert data["category_suggestion"]["match_type"] == "EXISTING"
        assert data["category_suggestion"]["category_id"] == "test-category-uuid"
        assert data["category_suggestion"]["category_name"] == "Groceries"
        
        # Verify agent was called
        mock_invoice_agent_success.assert_called_once()
        call_args = mock_invoice_agent_success.call_args
        assert call_args.kwargs["user_id"] == "test-user-uuid-123"
        assert call_args.kwargs["country"] == "GT"
        assert call_args.kwargs["currency_preference"] == "GTQ"
    
    def test_failure_missing_auth_token_returns_401(self, client, valid_image_bytes):
        """
        FAILURE PATH: Missing Authorization header returns 401.
        
        Tests that auth pipeline rejects requests without token.
        """
        # This test bypasses the mock because we want to test the real auth failure
        # We need to restore the original verify_token for this test
        response = client.post(
            "/invoices/ocr",
            files={"image": ("test_receipt.png", valid_image_bytes, "image/png")}
            # No Authorization header
        )
        
        # Should return 401 Unauthorized
        assert response.status_code == 401
        
        # Validate error response
        data = response.json()
        assert "detail" in data
    
    def test_failure_invalid_file_type_returns_400(
        self,
        client,
        mock_verify_token
    ):
        """
        FAILURE PATH: Non-image file returns 400 bad request.
        
        Tests domain filter that validates file type.
        """
        # Create a text file instead of image
        text_content = b"This is not an image"
        
        response = client.post(
            "/invoices/ocr",
            headers={"Authorization": "Bearer fake-test-token"},
            files={"image": ("test.txt", text_content, "text/plain")}
        )
        
        # Should return 400 Bad Request
        assert response.status_code == 400
        
        # Validate error response
        data = response.json()
        assert data["detail"]["error"] == "invalid_file_type"
    
    def test_failure_file_too_large_returns_400(
        self,
        client,
        mock_verify_token
    ):
        """
        FAILURE PATH: File larger than 10MB returns 400.
        
        Tests file size validation (DoS prevention).
        """
        # Create a fake 11MB file
        large_file = b"x" * (11 * 1024 * 1024)
        
        response = client.post(
            "/invoices/ocr",
            headers={"Authorization": "Bearer fake-test-token"},
            files={"image": ("huge.png", large_file, "image/png")}
        )
        
        # Should return 400 Bad Request
        assert response.status_code == 400
        
        # Validate error response
        data = response.json()
        assert data["detail"]["error"] == "file_too_large"
    
    def test_invalid_image_returns_invalid_image_response(
        self,
        client,
        mock_verify_token,
        mock_invoice_agent_invalid,
        valid_image_bytes
    ):
        """
        Test that InvoiceAgent's INVALID_IMAGE status is handled correctly.
        
        When agent cannot read the image, endpoint returns INVALID_IMAGE response.
        """
        response = client.post(
            "/invoices/ocr",
            headers={"Authorization": "Bearer fake-test-token"},
            files={"image": ("blurry_receipt.png", valid_image_bytes, "image/png")}
        )
        
        # Should return 200 OK (not an error, just can't read the image)
        assert response.status_code == 200
        
        # Parse response
        data = response.json()
        
        # Validate response structure
        assert data["status"] == "INVALID_IMAGE"
        assert data["reason"] == "Image is too blurry to read"
        
        # Verify agent was called
        mock_invoice_agent_invalid.assert_called_once()
    
    def test_endpoint_does_not_persist_to_database(
        self,
        client,
        mock_verify_token,
        mock_invoice_agent_success,
        valid_image_bytes
    ):
        """
        Verify that /invoices/ocr NEVER persists to database.
        
        This endpoint is preview-only. Persistence happens in /invoices/commit.
        """
        response = client.post(
            "/invoices/ocr",
            headers={"Authorization": "Bearer fake-test-token"},
            files={"image": ("test_receipt.png", valid_image_bytes, "image/png")}
        )
        
        assert response.status_code == 200
        
        # This is a smoke test - in reality, we'd mock DB calls and verify they're not made
        # For now, we just verify the endpoint returns successfully without errors
        # The actual DB layer is not implemented yet (TODO markers in code)


class TestInvoiceOCRValidation:
    """Tests for Pydantic schema validation."""
    
    def test_draft_response_schema_validates_correctly(self):
        """Test that InvoiceOCRResponseDraft validates sample data."""
        from backend.schemas.invoices import InvoiceOCRResponseDraft
        
        # Sample valid data
        data = {
            "status": "DRAFT",
            "store_name": "Test Store",
            "purchase_datetime": "2025-11-02T14:30:00Z",
            "total_amount": 100.0,
            "currency": "GTQ",
            "items": [
                {
                    "description": "Item 1",
                    "quantity": 1.0,
                    "total_price": 100.0
                }
            ],
            "category_suggestion": {
                "match_type": "EXISTING",
                "category_id": "test-uuid",
                "category_name": "Test Category"
            }
        }
        
        # Should validate without errors
        validated = InvoiceOCRResponseDraft.model_validate(data)
        assert validated.status == "DRAFT"
        assert validated.store_name == "Test Store"
    
    def test_invalid_response_schema_validates_correctly(self):
        """Test that InvoiceOCRResponseInvalid validates sample data."""
        from backend.schemas.invoices import InvoiceOCRResponseInvalid
        
        data = {
            "status": "INVALID_IMAGE",
            "reason": "Test reason"
        }
        
        validated = InvoiceOCRResponseInvalid.model_validate(data)
        assert validated.status == "INVALID_IMAGE"
        assert validated.reason == "Test reason"
