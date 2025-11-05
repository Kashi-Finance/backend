"""
Supabase Storage service for invoice receipt images.

Handles uploading invoice images to Supabase Storage and generating
storage paths for use in invoice.extracted_text.
"""

import logging
import mimetypes
from typing import Optional
from uuid import uuid4

from supabase import Client

from backend.config import settings

logger = logging.getLogger(__name__)


async def upload_invoice_image(
    supabase_client: Client,
    user_id: str,
    image_bytes: bytes,
    filename: str,
    content_type: Optional[str] = None,
) -> str:
    """
    Upload an invoice receipt image to Supabase Storage.

    This function:
    1. Generates a unique storage path: invoices/{user_id}/{uuid}.{ext}
    2. Uploads the image bytes to the storage bucket
    3. Returns the storage path for use in invoice records

    Args:
        supabase_client: Authenticated Supabase client
        user_id: The authenticated user's ID (for path organization)
        image_bytes: Raw image file bytes
        filename: Original filename (used to infer MIME type)
        content_type: Optional MIME type (e.g. "image/jpeg").
                     If not provided, inferred from filename.

    Returns:
        Storage path in the format: invoices/{user_id}/{uuid}.{ext}
        This path can be stored in invoice.storage_path.

    Raises:
        Exception: If upload fails

    Security:
        - RLS ensures user can only see their own invoice images
        - Path includes user_id for organization
        - Supabase Storage policies enforce access control
    """
    # Infer MIME type if not provided
    if not content_type:
        content_type, _ = mimetypes.guess_type(filename)
        if not content_type:
            content_type = "image/jpeg"  # default fallback

    # Extract file extension from original filename
    file_ext = None
    if "." in filename:
        file_ext = filename.rsplit(".", 1)[1].lower()
    else:
        # If no extension, infer from MIME type
        ext_map = {
            "image/jpeg": "jpg",
            "image/png": "png",
            "image/gif": "gif",
            "image/webp": "webp",
        }
        file_ext = ext_map.get(content_type, "jpg")

    # Generate unique filename using UUID
    unique_filename = f"{uuid4()}.{file_ext}"

    # Build storage path: invoices/{user_id}/{unique_filename}
    storage_path = f"invoices/{user_id}/{unique_filename}"

    logger.info(
        f"Uploading invoice image for user {user_id}: "
        f"filename={filename}, size={len(image_bytes)} bytes, "
        f"content_type={content_type}, storage_path={storage_path}"
    )

    try:
        # Upload to Supabase Storage
        supabase_client.storage.from_(
            settings.SUPABASE_STORAGE_BUCKET
        ).upload(
            path=storage_path,
            file=image_bytes,
            file_options={"content-type": content_type}
        )

        logger.info(
            f"Successfully uploaded invoice image to storage: "
            f"storage_path={storage_path}"
        )

        return storage_path

    except Exception as e:
        logger.error(
            f"Failed to upload invoice image to storage: {e}",
            exc_info=True
        )
        raise


async def delete_invoice_image(
    supabase_client: Client,
    storage_path: str,
) -> bool:
    """
    Delete an invoice receipt image from Supabase Storage.

    This function:
    1. Removes the file at storage_path from the configured storage bucket
    2. Returns True if deletion was successful or file didn't exist
    3. Logs deletion attempts for audit purposes

    Args:
        supabase_client: Authenticated Supabase client
        storage_path: The storage path to delete (e.g. "invoices/{user_id}/{uuid}.jpg")

    Returns:
        True if deletion was successful or file doesn't exist
        False if deletion failed with a recoverable error

    Raises:
        Exception: If a critical storage error occurs

    Security:
        - RLS ensures user can only delete their own images (path includes user_id)
        - Supabase Storage policies enforce access control
        - Always safe to call even if file doesn't exist

    Notes:
        - Called when invoice is deleted
        - Safe to call even if the file was already removed
        - Non-critical failure won't prevent invoice deletion
    """
    if not storage_path:
        logger.warning("delete_invoice_image called with empty storage_path")
        return False

    logger.info(f"Deleting invoice image from storage: storage_path={storage_path}")

    try:
        # Delete from Supabase Storage
        supabase_client.storage.from_(
            settings.SUPABASE_STORAGE_BUCKET
        ).remove([storage_path])

        logger.info(
            f"Successfully deleted invoice image from storage: "
            f"storage_path={storage_path}"
        )

        return True

    except Exception as e:
        logger.error(
            f"Failed to delete invoice image from storage: "
            f"storage_path={storage_path}, error={e}",
            exc_info=True
        )
        # Return False but don't raise - non-critical error
        # Invoice DB deletion already succeeded
        return False


def get_invoice_image_url(
    supabase_client: Client,
    storage_path: str,
    expires_in: int = 3600,
) -> str:
    """
    Generate a public URL for a stored invoice image.

    Args:
        supabase_client: Authenticated Supabase client
        storage_path: The storage path returned from upload_invoice_image()
        expires_in: URL expiration time in seconds (default 1 hour)

    Returns:
        A signed URL that can be used to access the image

    Raises:
        Exception: If URL generation fails
    """
    try:
        response = supabase_client.storage.from_(
            settings.SUPABASE_STORAGE_BUCKET
        ).create_signed_url(
            path=storage_path,
            expires_in=expires_in
        )
        # Extract URL from response - handle both dict-like and object responses
        if isinstance(response, dict):
            url = response.get("signedURL") or response.get("signed_url") or str(response)
        elif hasattr(response, "signedURL"):
            url = response.signedURL
        elif hasattr(response, "signed_url"):
            url = response.signed_url
        else:
            url = str(response)
        
        logger.debug(f"Generated signed URL for storage_path={storage_path}")
        return url

    except Exception as e:
        logger.error(
            f"Failed to generate signed URL for storage_path={storage_path}: {e}",
            exc_info=True
        )
        raise
