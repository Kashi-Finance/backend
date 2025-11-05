"""
Tests for the storage service (image upload to Supabase Storage).

Tests follow the requirements from .github/copilot-instructions.md:
- Mock Supabase Storage interactions
- Verify upload_invoice_image returns correct storage path
- Verify get_invoice_image_url generates signed URLs
"""

import pytest
from unittest.mock import MagicMock, patch

from backend.services.storage import upload_invoice_image, get_invoice_image_url


@pytest.fixture
def mock_supabase_client():
    """Create a mock Supabase client with storage capability."""
    client = MagicMock()
    
    # Mock the upload method to return a path
    client.storage.from_().upload.return_value = MagicMock(
        data={'path': 'invoices/test-user/test-image.png'}
    )
    
    # Mock the signed URL generation
    client.storage.from_().create_signed_url.return_value = (
        'https://example.supabase.co/storage/v1/object/sign/invoices/test-user/test-image.png'
    )
    
    return client


class TestUploadInvoiceImage:
    """Tests for upload_invoice_image function."""
    
    @pytest.mark.asyncio
    async def test_upload_success_returns_storage_path(self, mock_supabase_client):
        """
        Test that upload_invoice_image successfully uploads and returns storage path.
        
        Should:
        - Call storage.from_() with bucket name
        - Call upload() with proper file structure
        - Return the storage path
        """
        image_bytes = b"fake-image-data"
        user_id = "test-user-123"
        filename = "receipt.jpg"
        
        # Call the function
        storage_path = await upload_invoice_image(
            supabase_client=mock_supabase_client,
            user_id=user_id,
            image_bytes=image_bytes,
            filename=filename,
            content_type="image/jpeg"
        )
        
        # Verify it called storage correctly
        mock_supabase_client.storage.from_.assert_called()
        mock_supabase_client.storage.from_().upload.assert_called_once()
        
        # Verify return value is a string (storage path)
        assert isinstance(storage_path, str)
        assert storage_path.startswith("invoices/")
    
    @pytest.mark.asyncio
    async def test_upload_infers_mime_type_from_filename(self, mock_supabase_client):
        """
        Test that upload_invoice_image infers MIME type from filename if not provided.
        
        When content_type is None, the function should:
        - Infer MIME type from file extension
        - Pass the inferred type to upload()
        """
        image_bytes = b"fake-png-data"
        
        # Call without content_type
        await upload_invoice_image(
            supabase_client=mock_supabase_client,
            user_id="test-user",
            image_bytes=image_bytes,
            filename="receipt.png",
            content_type=None
        )
        
        # Verify upload was called with PNG content type
        call_args = mock_supabase_client.storage.from_().upload.call_args
        assert call_args is not None
        file_options = call_args[1].get('file_options', {})
        assert file_options.get('content-type') == "image/png"
    
    @pytest.mark.asyncio
    async def test_upload_stores_in_user_directory(self, mock_supabase_client):
        """
        Test that uploaded files are stored in invoices/{user_id}/{uuid} path.
        
        This ensures:
        - Files are organized per user
        - Files have unique names
        - User privacy is maintained
        """
        image_bytes = b"fake-data"
        user_id = "user-uuid-12345"
        
        await upload_invoice_image(
            supabase_client=mock_supabase_client,
            user_id=user_id,
            image_bytes=image_bytes,
            filename="receipt.jpg",
            content_type="image/jpeg"
        )
        
        # Verify the storage path includes the user ID
        call_args = mock_supabase_client.storage.from_().upload.call_args
        storage_path = call_args[1].get('path', '')
        assert user_id in storage_path
        assert storage_path.startswith('invoices/')


class TestGetInvoiceImageUrl:
    """Tests for get_invoice_image_url function."""
    
    def test_get_signed_url_success(self, mock_supabase_client):
        """
        Test that get_invoice_image_url generates a signed URL.
        
        Should:
        - Call storage.from_() with bucket name
        - Call create_signed_url() with path and expiration
        - Return a valid URL string
        """
        storage_path = "invoices/test-user/test-image.png"
        expires_in = 3600
        
        url = get_invoice_image_url(
            supabase_client=mock_supabase_client,
            storage_path=storage_path,
            expires_in=expires_in
        )
        
        # Verify it called storage correctly
        mock_supabase_client.storage.from_.assert_called()
        mock_supabase_client.storage.from_().create_signed_url.assert_called_once()
        
        # Verify return value is a URL string
        assert isinstance(url, str)
        assert url.startswith('https://')
    
    def test_get_signed_url_passes_expiration(self, mock_supabase_client):
        """
        Test that get_invoice_image_url respects the expires_in parameter.
        
        Signed URLs should be time-limited for security.
        """
        storage_path = "invoices/test-user/test-image.png"
        expires_in = 7200  # 2 hours
        
        get_invoice_image_url(
            supabase_client=mock_supabase_client,
            storage_path=storage_path,
            expires_in=expires_in
        )
        
        # Verify create_signed_url was called with the expiration time
        call_args = mock_supabase_client.storage.from_().create_signed_url.call_args
        assert call_args[1].get('expires_in') == expires_in
