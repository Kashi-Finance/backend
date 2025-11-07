"""
Invoice OCR API endpoints.

Provides endpoints for uploading and processing receipt images using InvoiceAgent.

Flow:
1. POST /invoices/ocr - Upload image, get draft extraction (PREVIEW ONLY, not persisted)
2. POST /invoices/commit - Confirm/edit draft and persist to DB
"""

import base64
import logging
from typing import Annotated
from fastapi import APIRouter, Depends, File, HTTPException, UploadFile, status

from backend.auth.dependencies import get_authenticated_user, AuthenticatedUser
from backend.db.client import get_supabase_client
from backend.services import (
    create_invoice,
    get_user_profile,
    get_user_invoices,
    get_invoice_by_id,
    upload_invoice_image,
    delete_invoice,
    create_transaction,
)
from backend.schemas.invoices import (
    InvoiceOCRResponse,
    InvoiceOCRResponseDraft,
    InvoiceOCRResponseInvalid,
    InvoiceCommitRequest,
    InvoiceCommitResponse,
    InvoiceListResponse,
    InvoiceDetailResponse,
    PurchasedItemResponse,
    CategorySuggestionResponse,
    InvoiceDeleteResponse,
)
from backend.agents.invoice import run_invoice_agent
from backend.agents.invoice.tools import get_user_categories

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/invoices", tags=["invoices"])


@router.post(
    "/ocr",
    response_model=InvoiceOCRResponse,
    status_code=status.HTTP_200_OK,
    summary="Process receipt image with OCR",
    description="""
    Upload a receipt/invoice image for OCR extraction.
    
    This endpoint:
    - Accepts image files (JPEG, PNG, etc.)
    - Calls InvoiceAgent to extract structured data
    - Returns either a DRAFT preview or INVALID_IMAGE error
    - NEVER persists to database (preview only)
    
    Frontend should:
    - Show DRAFT data to user for editing/confirmation
    - Call /invoices/commit to actually save the transaction
    - Handle INVALID_IMAGE by asking user to retake photo
    
    Security:
    - Requires valid Authorization Bearer token
    - Only processes invoices for authenticated user
    """
)
async def process_invoice_ocr(
    image: Annotated[UploadFile, File(description="Receipt/invoice image file")],
    auth_user: Annotated[AuthenticatedUser, Depends(get_authenticated_user)]
) -> InvoiceOCRResponse:
    """
    Process receipt image and extract structured invoice data.
    
    **6-STEP ENDPOINT FLOW:**
    
    Step 1: Auth
    - Handled by get_authenticated_user dependency
    - Extracts user_id and access_token from Supabase Auth token
    
    Step 2: Parse/Validate Request
    - FastAPI validates UploadFile automatically
    - Type checking ensures image is present
    
    Step 3: Domain & Intent Filter
    - Check if uploaded file is actually an image
    - Verify file size is reasonable (prevent DoS)

    Step 4: Call ONE ADK Agent
    - Call InvoiceAgent with validated inputs
    - Agent returns structured output or out_of_scope

    Step 5: Map Output -> ResponseModel
    - Convert agent output to Pydantic response
    - Return InvoiceOCRResponseDraft or InvoiceOCRResponseInvalid

    Step 6: Persistence
    - NONE - this endpoint is preview only
    - Actual persistence happens in /invoices/commit
    """
    
    user_id = auth_user.user_id
    
    # --- STEP 3: Domain & Intent Filter ---
    
    # Validate file type
    if not image.content_type or not image.content_type.startswith("image/"):
        logger.warning(f"Invalid content type: {image.content_type}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={
                "error": "invalid_file_type",
                "details": "File must be an image (JPEG, PNG, etc.)"
            }
        )
    
    # Read image data
    try:
        image_bytes = await image.read()
    except Exception as e:
        logger.error(f"Failed to read uploaded file: {e}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={
                "error": "file_read_error",
                "details": "Could not read uploaded image file"
            }
        )
    
    # Validate file size (max 10MB for now)
    max_size_mb = 10
    max_size_bytes = max_size_mb * 1024 * 1024
    if len(image_bytes) > max_size_bytes:
        logger.warning(f"Image too large: {len(image_bytes)} bytes")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={
                "error": "file_too_large",
                "details": f"Image must be smaller than {max_size_mb}MB"
            }
        )
    
    # Encode image as base64 for agent
    image_base64 = base64.b64encode(image_bytes).decode("utf-8")
    
    logger.info(
        f"Processing OCR for user_id={user_id}, "
        f"filename={image.filename}, "
        f"size={len(image_bytes)} bytes"
    )
    
    # Create authenticated Supabase client for profile and categories
    supabase_client = get_supabase_client(auth_user.access_token)
    
    # NOTE: Image will NOT be uploaded to storage during OCR (draft phase).
    # Upload happens ONLY when user confirms via /invoices/commit endpoint.
    # We do NOT pass storage_path to the agent because the image doesn't exist in storage yet.
    
    # Fetch user profile for country and currency_preference
    # This allows the InvoiceAgent to provide localized extraction
    # (e.g. recognize GTQ for Guatemala, MXN for Mexico, etc.)
    profile = await get_user_profile(supabase_client=supabase_client, user_id=user_id)
    
    if profile:
        country = profile.get("country", "GT")
        currency_preference = profile.get("currency_preference", "GTQ")
        logger.debug(
            f"Using profile settings for user {user_id}: "
            f"country={country}, currency={currency_preference}"
        )
    else:
        # Profile not found - use sensible defaults for Guatemala
        # In production, you might want to create a profile here or return an error
        country = "GT"
        currency_preference = "GTQ"
        logger.warning(
            f"Profile not found for user {user_id}, using defaults: "
            f"country={country}, currency={currency_preference}"
        )
    
    # Fetch user's categories for the agent
    try:
        user_categories = get_user_categories(supabase_client, user_id)
    except Exception as e:
        logger.error(f"Error fetching user categories: {e}", exc_info=True)
        # If we can't fetch categories, provide empty list rather than failing
        user_categories = []
    

    # --- STEP 4: Call Agent ---
    try:
        agent_output = run_invoice_agent(
            user_id=user_id,
            user_categories=user_categories,
            receipt_image_base64=image_base64,
            country=country,
            currency_preference=currency_preference
        )
    except Exception as e:
        logger.error(f"InvoiceAgent error: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={
                "error": "agent_error",
                "details": "Failed to process invoice with OCR agent"
            }
        )
    
    # --- STEP 5: Map Output -> ResponseModel ---
    
    if agent_output["status"] == "INVALID_IMAGE":
        logger.info(f"InvoiceAgent returned INVALID_IMAGE: {agent_output.get('reason', 'Unknown')}")
        return InvoiceOCRResponseInvalid(
            status="INVALID_IMAGE",
            reason=agent_output.get("reason") or "Could not extract invoice data from image"
        )
    
    elif agent_output["status"] == "OUT_OF_SCOPE":
        logger.warning(f"InvoiceAgent returned OUT_OF_SCOPE: {agent_output.get('reason', 'Unknown')}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={
                "error": "out_of_scope",
                "details": agent_output.get("reason") or "Request is not a valid invoice processing task"
            }
        )
    
    elif agent_output["status"] == "DRAFT":
        logger.info(
            f"InvoiceAgent extracted DRAFT: "
            f"store={agent_output.get('store_name')}, "
            f"total={agent_output.get('total_amount')} {agent_output.get('currency')}"
        )
        
        # Map agent output to response schema
        # Normalize optional agent fields safely (agent_output keys may exist but be None)
        purchased_items_raw = agent_output.get("purchased_items") or []
        items = []
        for item in purchased_items_raw:
            # Basic validation for each item; if required fields missing, skip the item
            if not item or item.get("description") is None or item.get("line_total") is None or item.get("quantity") is None:
                logger.debug("Skipping malformed purchased item from agent output")
                continue
            items.append(
                PurchasedItemResponse(
                    description=item["description"],
                    quantity=item["quantity"],
                    unit_price=item.get("unit_price"),
                    total_price=item["line_total"]
                )
            )

        # Validate category_suggestion exists and has the required match_type
        cs = agent_output.get("category_suggestion") or {}
        match_type = cs.get("match_type")
        if match_type not in ("EXISTING", "NEW_PROPOSED"):
            logger.debug("Agent returned missing or invalid category_suggestion; defaulting to NEW_PROPOSED")
            match_type = "NEW_PROPOSED"

        # Build category_suggestion with all 4 fields (some may be null depending on match_type)
        # Invariant: EXISTING has category_id + category_name, NEW_PROPOSED has proposed_name
        if match_type == "EXISTING":
            category_suggestion = CategorySuggestionResponse(
                match_type="EXISTING",
                category_id=cs.get("category_id"),
                category_name=cs.get("category_name"),
                proposed_name=None
            )
        else:  # NEW_PROPOSED
            category_suggestion = CategorySuggestionResponse(
                match_type="NEW_PROPOSED",
                category_id=None,
                category_name=None,
                proposed_name=cs.get("proposed_name") or "Uncategorized"
            )

        # Ensure required top-level fields are present; if any are missing, treat as INVALID_IMAGE
        store_name = agent_output.get("store_name")
        purchase_datetime = agent_output.get("transaction_time")
        total_amount = agent_output.get("total_amount")
        currency = agent_output.get("currency")

        missing_required = []
        if store_name is None:
            missing_required.append("store_name")
        if purchase_datetime is None:
            missing_required.append("transaction_time")
        if total_amount is None:
            missing_required.append("total_amount")
        if currency is None:
            missing_required.append("currency")

        if missing_required:
            logger.warning(f"Agent returned DRAFT but missing required fields: {missing_required}")
            return InvoiceOCRResponseInvalid(
                status="INVALID_IMAGE",
                reason=(
                    "Agent could not extract all required fields: " + ", ".join(missing_required)
                )
            )

        # Narrow types for the type checker (we validated above these are not None)
        assert store_name is not None
        assert purchase_datetime is not None
        assert total_amount is not None
        assert currency is not None

        return InvoiceOCRResponseDraft(
            status="DRAFT",
            store_name=store_name,
            transaction_time=purchase_datetime,
            total_amount=total_amount,
            currency=currency,
            items=items,
            category_suggestion=category_suggestion
        )
    
    else:
        # Unknown status from agent
        logger.error(f"Unknown agent status: {agent_output.get('status')}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={
                "error": "unknown_agent_status",
                "details": "Agent returned unexpected status"
            }
        )


@router.post(
    "/commit",
    response_model=InvoiceCommitResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Commit invoice to database",
    description="""
    Persist confirmed invoice data to the database.
    
    This endpoint:
    - Accepts edited/confirmed data from the frontend
    - Formats data into the canonical EXTRACTED_INVOICE_TEXT_FORMAT
    - Inserts record into the invoice table with RLS enforcement
    - Returns the created invoice ID
    
    Security:
    - Requires valid Authorization Bearer token
    - RLS ensures user can only create invoices for themselves
    - The invoice.extracted_text field follows the canonical format
    """
)
async def commit_invoice(
    request: InvoiceCommitRequest,
    auth_user: Annotated[AuthenticatedUser, Depends(get_authenticated_user)]
) -> InvoiceCommitResponse:
    """
    Persist invoice data to Supabase with RLS enforcement.
    
    Auth
    - Handled by get_authenticated_user dependency
    - Extracts user_id and access_token from Supabase Auth
    
    Parse/Validate Request
    - FastAPI validates InvoiceCommitRequest automatically
    - Ensures all required fields are present
    
    Domain & Intent Filter
    - Validate that this is a valid invoice commit request
    - Check that required fields are non-empty

    Map Output -> ResponseModel
    - Return InvoiceCommitResponse with invoice_id

    Persistence
    - Create authenticated Supabase client
    - Call invoice_service.create_invoice()
    - RLS automatically enforces user_id = auth.uid()
    """
    
    # --- Domain & Intent Filter ---
    
    # Basic validation (Pydantic already enforces non-null)
    if not request.store_name.strip():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={
                "error": "invalid_request",
                "details": "store_name cannot be empty"
            }
        )
    
    if not request.image_base64.strip():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={
                "error": "invalid_request",
                "details": "image_base64 cannot be empty"
            }
        )
    
    logger.info(
        f"Committing invoice for user_id={auth_user.user_id}, "
        f"store={request.store_name}, "
        f"amount={request.total_amount} {request.currency}"
    )
    
    # Create authenticated Supabase client (RLS enforced)
    supabase_client = get_supabase_client(auth_user.access_token)
    
    # --- UPLOAD IMAGE TO STORAGE (only happens on commit) ---
    try:
        # Decode base64 to bytes
        try:
            image_bytes = base64.b64decode(request.image_base64)
        except Exception as e:
            logger.error(f"Failed to decode base64 image: {e}")
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail={
                    "error": "invalid_image_base64",
                    "details": "Could not decode image_base64 field"
                }
            )
        
        # Upload image to Supabase Storage
        storage_path = await upload_invoice_image(
            supabase_client=supabase_client,
            user_id=auth_user.user_id,
            image_bytes=image_bytes,
            filename=request.image_filename,
            content_type="image/jpeg"  # Will be detected/overridden by upload_invoice_image
        )
        logger.info(f"Image uploaded to storage: {storage_path}")
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to upload image to storage: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={
                "error": "storage_error",
                "details": "Failed to upload receipt image to storage"
            }
        )
    
    try:
        # Persist invoice to database
        created_invoice = await create_invoice(
            supabase_client=supabase_client,
            user_id=auth_user.user_id,
            storage_path=storage_path,  # Use the uploaded storage path
            store_name=request.store_name,
            transaction_time=request.transaction_time,
            total_amount=request.total_amount,
            currency=request.currency,
            purchased_items=request.purchased_items,
        )
        
        invoice_id = created_invoice.get("id")
        
        if not invoice_id:
            raise Exception("Invoice created but no ID returned")
        
        logger.info(
            f"Invoice committed successfully: "
            f"id={invoice_id}, user_id={auth_user.user_id}"
        )
        
        # Create linked transaction
        created_transaction = await create_transaction(
            supabase_client=supabase_client,
            user_id=auth_user.user_id,
            account_id=request.account_id,
            category_id=request.category_id,
            flow_type="outcome",  # Invoices are always expenses
            amount=float(request.total_amount),
            date=request.transaction_time,
            description=request.store_name,
            invoice_id=str(invoice_id),  # Link to invoice
        )
        
        transaction_id = created_transaction.get("id")
        
        if not transaction_id:
            # Log warning but don't fail the entire operation
            # Invoice is already committed at this point
            logger.warning(
                f"Invoice {invoice_id} committed but transaction creation failed"
            )
            raise Exception("Transaction created but no ID returned")
        
        logger.info(
            f"Transaction created successfully: "
            f"id={transaction_id}, invoice_id={invoice_id}, user_id={auth_user.user_id}"
        )
        
        return InvoiceCommitResponse(
            status="COMMITTED",
            invoice_id=str(invoice_id),
            transaction_id=str(transaction_id),
            message="Invoice and transaction saved successfully"
        )
        
    except Exception as e:
        logger.error(f"Failed to commit invoice: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={
                "error": "persistence_error",
                "details": "Failed to save invoice to database"
            }
        )


@router.get(
    "",
    response_model=InvoiceListResponse,
    status_code=status.HTTP_200_OK,
    summary="List user's invoices",
    description="""
    Retrieve all invoices belonging to the authenticated user.
    
    This endpoint:
    - Returns paginated list of invoices
    - Only shows invoices owned by the authenticated user (RLS enforced)
    - Orders by created_at descending (newest first)
    - Supports pagination via limit/offset query parameters
    
    Security:
    - Requires valid authentication token
    - RLS ensures users only see their own invoices
    """
)
async def list_invoices(
    auth_user: Annotated[AuthenticatedUser, Depends(get_authenticated_user)],
    limit: int = 50,
    offset: int = 0
) -> InvoiceListResponse:
    """
    List all invoices for the authenticated user.
    
    Args:
        auth_user: Authenticated user from token
        limit: Maximum number of invoices to return (default 50)
        offset: Number of invoices to skip for pagination (default 0)
    
    Returns:
        InvoiceListResponse with list of invoices and pagination metadata
    """
    logger.info(f"Listing invoices for user {auth_user.user_id} (limit={limit}, offset={offset})")
    
    # Create authenticated Supabase client
    supabase_client = get_supabase_client(auth_user.access_token)
    
    try:
        # Fetch invoices from database (RLS enforced)
        invoices = await get_user_invoices(
            supabase_client=supabase_client,
            user_id=auth_user.user_id,
            limit=limit,
            offset=offset
        )
        
        # Map to response models
        invoice_responses = [
            InvoiceDetailResponse(
                id=str(inv.get("id")),
                user_id=str(inv.get("user_id")),
                storage_path=inv.get("storage_path", ""),
                extracted_text=inv.get("extracted_text", ""),
                created_at=inv.get("created_at", ""),
                updated_at=inv.get("updated_at")
            )
            for inv in invoices
        ]
        
        logger.info(f"Returning {len(invoice_responses)} invoices for user {auth_user.user_id}")
        
        return InvoiceListResponse(
            invoices=invoice_responses,
            count=len(invoice_responses),
            limit=limit,
            offset=offset
        )
        
    except Exception as e:
        logger.error(f"Failed to fetch invoices: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={
                "error": "fetch_error",
                "details": "Failed to retrieve invoices from database"
            }
        )


@router.get(
    "/{invoice_id}",
    response_model=InvoiceDetailResponse,
    status_code=status.HTTP_200_OK,
    summary="Get invoice details",
    description="""
    Retrieve a single invoice by its ID.
    
    This endpoint:
    - Returns detailed invoice information
    - Only returns invoice if it belongs to the authenticated user (RLS enforced)
    - Returns 404 if invoice doesn't exist or belongs to another user
    
    Security:
    - Requires valid authentication token
    - RLS ensures users can only access their own invoices
    """
)
async def get_invoice(
    invoice_id: str,
    auth_user: Annotated[AuthenticatedUser, Depends(get_authenticated_user)]
) -> InvoiceDetailResponse:
    """
    Get details of a single invoice.
    
    Args:
        invoice_id: UUID of the invoice to retrieve
        auth_user: Authenticated user from token
    
    Returns:
        InvoiceDetailResponse with invoice details
    
    Raises:
        HTTPException 404: If invoice not found or not accessible by user
    """
    logger.info(f"Fetching invoice {invoice_id} for user {auth_user.user_id}")
    
    # Create authenticated Supabase client
    supabase_client = get_supabase_client(auth_user.access_token)
    
    try:
        # Fetch invoice from database (RLS enforced)
        invoice = await get_invoice_by_id(
            supabase_client=supabase_client,
            user_id=auth_user.user_id,
            invoice_id=invoice_id
        )
        
        if not invoice:
            logger.warning(
                f"Invoice {invoice_id} not found or not accessible by user {auth_user.user_id}"
            )
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail={
                    "error": "not_found",
                    "details": f"Invoice {invoice_id} not found or not accessible"
                }
            )
        
        logger.info(f"Returning invoice {invoice_id} for user {auth_user.user_id}")
        
        return InvoiceDetailResponse(
            id=str(invoice.get("id")),
            user_id=str(invoice.get("user_id")),
            storage_path=invoice.get("storage_path", ""),
            extracted_text=invoice.get("extracted_text", ""),
            created_at=invoice.get("created_at", ""),
            updated_at=invoice.get("updated_at")
        )
        
    except HTTPException:
        # Re-raise HTTP exceptions (like 404)
        raise
    except Exception as e:
        logger.error(f"Failed to fetch invoice {invoice_id}: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={
                "error": "fetch_error",
                "details": "Failed to retrieve invoice from database"
            }
        )


@router.delete(
    "/{invoice_id}",
    response_model=InvoiceDeleteResponse,
    status_code=status.HTTP_200_OK,
    summary="Delete an invoice",
    description="""
    Delete an existing invoice and its associated receipt image from storage.
    
    This endpoint:
    - Permanently removes the invoice from the database
    - Deletes the associated receipt image from Supabase Storage
    - Requires valid Authorization Bearer token
    
    Security:
    - Only the invoice owner can delete their invoices
    - Returns 404 if invoice doesn't exist or belongs to another user
    """
)
async def delete_invoice_record(
    invoice_id: str,
    auth_user: Annotated[AuthenticatedUser, Depends(get_authenticated_user)]
) -> InvoiceDeleteResponse:
    """
    Delete an invoice record and associated receipt image.
    
    Auth
    - Handled by get_authenticated_user dependency
    - Extracts user_id and access_token from Supabase Auth token

    Parse/Validate Request
    - FastAPI validates path parameter invoice_id

    Domain & Intent Filter
    - Validate that this is a valid invoice delete request
    - Check that invoice exists and belongs to authenticated user

    Call Service
    - Call delete_invoice() service function
    - Service handles RLS enforcement and storage deletion

    Map Output -> ResponseModel
    - Return InvoiceDeleteResponse

    Persistence
    - Service layer handles deletion via authenticated Supabase client
    - Service also deletes receipt image from Supabase Storage
    """
    
    logger.info(f"Deleting invoice {invoice_id} for user {auth_user.user_id}")
    
    # Create authenticated Supabase client
    supabase_client = get_supabase_client(auth_user.access_token)
    
    try:
        # Delete invoice and storage (service handles RLS enforcement)
        success = await delete_invoice(
            supabase_client=supabase_client,
            user_id=auth_user.user_id,
            invoice_id=invoice_id,
        )
        
        if not success:
            logger.warning(
                f"Invoice {invoice_id} not found or not accessible by user {auth_user.user_id}"
            )
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail={
                    "error": "not_found",
                    "details": f"Invoice {invoice_id} not found or not accessible"
                }
            )
        
        logger.info(f"Invoice {invoice_id} deleted successfully for user {auth_user.user_id}")
        
        return InvoiceDeleteResponse(
            status="DELETED",
            invoice_id=str(invoice_id),
            message="Invoice deleted successfully"
        )
        
    except HTTPException:
        # Re-raise HTTP exceptions
        raise
    except Exception as e:
        logger.error(f"Failed to delete invoice {invoice_id}: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={
                "error": "delete_error",
                "details": "Failed to delete invoice"
            }
        )
