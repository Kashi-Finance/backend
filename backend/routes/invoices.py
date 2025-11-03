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

from backend.auth.dependencies import verify_token, get_authenticated_user, AuthenticatedUser
from backend.db.client import get_supabase_client
from backend.services import create_invoice, get_user_profile, format_extracted_text
from backend.schemas.invoices import (
    InvoiceOCRResponse,
    InvoiceOCRResponseDraft,
    InvoiceOCRResponseInvalid,
    InvoiceCommitRequest,
    InvoiceCommitResponse,
    PurchasedItemResponse,
    CategorySuggestionResponse,
)
from backend.agents.invoice import run_invoice_agent

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
    user_id: Annotated[str, Depends(verify_token)]
) -> InvoiceOCRResponse:
    """
    Process receipt image and extract structured invoice data.
    
    **6-STEP ENDPOINT FLOW:**
    
    Step 1: Auth
    - Handled by verify_token dependency
    - Extracts user_id from Supabase Auth token
    
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
    
    # --- STEP 4: Call ONE ADK Agent ---
    
    # Generate temporary receipt ID (in production, this would be from storage)
    # TODO(storage-team): Upload image to Supabase Storage and get real receipt_id
    receipt_image_id = f"temp-{user_id[:8]}-{hash(image_bytes) % 10000}"
    
    # TODO(db-team): Fetch user profile for country and currency_preference
    # For now, use defaults
    country = "GT"
    currency_preference = "GTQ"
    
    try:
        agent_output = run_invoice_agent(
            user_id=user_id,
            receipt_image_id=receipt_image_id,
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

        # Determine a safe category_name: prefer explicit category_name, then proposed_name, then a fallback
        category_name = cs.get("category_name") or cs.get("proposed_name") or "Uncategorized"

        category_suggestion = CategorySuggestionResponse(
            match_type=match_type,
            category_id=cs.get("category_id"),
            category_name=category_name,
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
            purchase_datetime=purchase_datetime,
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
    
    **6-STEP ENDPOINT FLOW:**
    
    Step 1: Auth
    - Handled by get_authenticated_user dependency
    - Extracts user_id and access_token from Supabase Auth
    
    Step 2: Parse/Validate Request
    - FastAPI validates InvoiceCommitRequest automatically
    - Ensures all required fields are present
    
    Step 3: Domain & Intent Filter
    - Validate that this is a valid invoice commit request
    - Check that required fields are non-empty

    Step 4: Call ADK Agent
    - No agent needed for commit (data already extracted)

    Step 5: Map Output -> ResponseModel
    - Return InvoiceCommitResponse with invoice_id

    Step 6: Persistence
    - Create authenticated Supabase client
    - Call invoice_service.create_invoice()
    - RLS automatically enforces user_id = auth.uid()
    """
    
    # --- STEP 3: Domain & Intent Filter ---
    
    # Basic validation (Pydantic already enforces non-null)
    if not request.store_name.strip():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={
                "error": "invalid_request",
                "details": "store_name cannot be empty"
            }
        )
    
    if not request.storage_path.strip():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={
                "error": "invalid_request",
                "details": "storage_path cannot be empty"
            }
        )
    
    logger.info(
        f"Committing invoice for user_id={auth_user.user_id}, "
        f"store={request.store_name}, "
        f"amount={request.total_amount} {request.currency}"
    )
    
    # --- STEP 6: Persistence ---
    
    # Create authenticated Supabase client (RLS enforced)
    supabase_client = get_supabase_client(auth_user.access_token)
    
    try:
        # Persist invoice to database
        created_invoice = await create_invoice(
            supabase_client=supabase_client,
            user_id=auth_user.user_id,
            storage_path=request.storage_path,
            store_name=request.store_name,
            transaction_time=request.transaction_time,
            total_amount=request.total_amount,
            currency=request.currency,
            purchased_items=request.purchased_items,
            nit=request.nit
        )
        
        invoice_id = created_invoice.get("id")
        
        if not invoice_id:
            raise Exception("Invoice created but no ID returned")
        
        logger.info(
            f"Invoice committed successfully: "
            f"id={invoice_id}, user_id={auth_user.user_id}"
        )
        
        return InvoiceCommitResponse(
            status="COMMITTED",
            invoice_id=str(invoice_id),
            message="Invoice saved successfully"
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


# TODO: Implement GET /invoices - List user's invoices
# TODO: Implement GET /invoices/{invoice_id} - Get single invoice details
