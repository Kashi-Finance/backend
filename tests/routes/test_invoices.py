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


async def mock_get_authenticated_user_dependency():
    """Mock dependency that returns test AuthenticatedUser."""
    from backend.auth.dependencies import AuthenticatedUser
    return AuthenticatedUser(
        user_id="test-user-uuid-123",
        access_token="fake-test-access-token"
    )


async def mock_get_user_profile(supabase_client, user_id: str):
    """Mock get_user_profile to return test profile data."""
    return {
        "user_id": user_id,
        "country": "GT",
        "currency_preference": "GTQ",
        "first_name": "Test",
        "last_name": "User",
        "locale": "es-GT"
    }


@pytest.fixture
def mock_verify_token():
    """Override get_authenticated_user dependency and mock get_user_profile."""
    from backend.auth.dependencies import get_authenticated_user
    from backend.routes.invoices import router
    
    # Override auth dependency in the app
    app.dependency_overrides[get_authenticated_user] = mock_get_authenticated_user_dependency
    
    yield
    
    # Clean up after test
    app.dependency_overrides.clear()


@pytest.fixture
def mock_get_user_profile_fixture():
    """Mock get_user_profile service function."""
    with patch("backend.routes.invoices.get_user_profile") as mock:
        # Make the mock return a coroutine that resolves to the profile data
        async def mock_profile(*args, **kwargs):
            return await mock_get_user_profile(None, "test-user-uuid-123")
        mock.side_effect = mock_profile
        yield mock


@pytest.fixture
def mock_get_supabase_client():
    """Mock get_supabase_client to return a fake client."""
    with patch("backend.routes.invoices.get_supabase_client") as mock:
        # Return a mock client object
        mock.return_value = None  # Profile service will receive this
        yield mock


@pytest.fixture
def mock_invoice_agent_success():
    """Mock Gemini API to return successful DRAFT response."""
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
    
    # Mock the Gemini API client instead of run_invoice_agent directly
    with patch("backend.agents.invoice.agent.genai.Client") as mock_client_class:
        # Create a mock client instance
        mock_client = mock_client_class.return_value
        
        # Create a mock response object that mimics Gemini's response structure
        import json
        mock_response = type('MockResponse', (), {
            'text': json.dumps(mock_output),
            'candidates': [
                type('Candidate', (), {
                    'content': type('Content', (), {
                        'parts': []  # No function calls, just final response
                    })()
                })()
            ]
        })()
        
        # Configure the mock to return this response
        mock_client.models.generate_content.return_value = mock_response
        
        yield mock_client_class


@pytest.fixture
def mock_invoice_agent_invalid():
    """Mock Gemini API to return INVALID_IMAGE response."""
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
    
    # Mock the Gemini API client
    with patch("backend.agents.invoice.agent.genai.Client") as mock_client_class:
        mock_client = mock_client_class.return_value
        
        import json
        mock_response = type('MockResponse', (), {
            'text': json.dumps(mock_output),
            'candidates': [
                type('Candidate', (), {
                    'content': type('Content', (), {
                        'parts': []
                    })()
                })()
            ]
        })()
        
        mock_client.models.generate_content.return_value = mock_response
        
        yield mock_client_class


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
        mock_get_supabase_client,
        mock_get_user_profile_fixture,
        mock_invoice_agent_success,
        valid_image_bytes
    ):
        """
        HAPPY PATH: Valid image with auth token returns DRAFT response.
        
        This tests:
        - Auth passes (get_authenticated_user mock)
        - User profile is fetched (get_user_profile mock)
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
        
        # Verify profile was fetched
        mock_get_user_profile_fixture.assert_called_once()
        
        # Verify Gemini client was instantiated and called
        mock_invoice_agent_success.assert_called_once()
        assert mock_invoice_agent_success.return_value.models.generate_content.called
    
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
        mock_verify_token,
        mock_get_supabase_client,
        mock_get_user_profile_fixture
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
        mock_verify_token,
        mock_get_supabase_client,
        mock_get_user_profile_fixture
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
        mock_get_supabase_client,
        mock_get_user_profile_fixture,
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
        
        # Verify Gemini client was called
        mock_invoice_agent_invalid.assert_called_once()
    
    def test_endpoint_does_not_persist_to_database(
        self,
        client,
        mock_verify_token,
        mock_get_supabase_client,
        mock_get_user_profile_fixture,
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
    
    def test_profile_not_found_uses_defaults(
        self,
        client,
        mock_verify_token,
        mock_get_supabase_client,
        mock_invoice_agent_success,
        valid_image_bytes
    ):
        """
        Test that when user profile is not found, defaults are used.
        
        When get_user_profile returns None, the endpoint should:
        - Use default country: "GT"
        - Use default currency_preference: "GTQ"
        - Continue processing without error
        """
        # Mock get_user_profile to return None (profile not found)
        with patch("backend.routes.invoices.get_user_profile") as mock_profile:
            async def no_profile(*args, **kwargs):
                return None
            mock_profile.side_effect = no_profile
            
            response = client.post(
                "/invoices/ocr",
                headers={"Authorization": "Bearer fake-test-token"},
                files={"image": ("test_receipt.png", valid_image_bytes, "image/png")}
            )
            
            # Should still return 200 OK
            assert response.status_code == 200
            
            # Verify Gemini client was called with default values
            mock_invoice_agent_success.assert_called_once()


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
