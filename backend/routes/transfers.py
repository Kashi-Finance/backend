"""
Transfer endpoints for creating and managing transfers between accounts.

All transfers are paired transactions that move money internally between
the user's own accounts.
"""

import logging
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException

from backend.auth.dependencies import get_authenticated_user, AuthenticatedUser
from backend.db.client import get_supabase_client
from backend.schemas.transfers import (
    TransferCreateRequest,
    TransferCreateResponse,
    TransferResponse,
    RecurringTransferCreateRequest,
    RecurringTransferCreateResponse,
    RecurringTransferResponse,
)
from backend.services import transfer_service

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/transfers", tags=["transfers"])


@router.post(
    "",
    response_model=TransferCreateResponse,
    status_code=201,
    summary="Create a one-time transfer between accounts"
)
async def create_transfer(
    request: TransferCreateRequest,
    user: Annotated[AuthenticatedUser, Depends(get_authenticated_user)]
):
    """
    Create a one-time internal transfer between two accounts.
    
    Creates two paired transactions:
    - Outcome transaction from source account
    - Income transaction to destination account
    
    Both transactions are linked via `paired_transaction_id`.
    
    **Requirements:**
    - Both accounts must belong to the authenticated user
    - Amount must be positive
    - Date must be in ISO-8601 format (YYYY-MM-DD)
    
    **Returns:**
    - 201 CREATED: Transfer created successfully
    - 400 BAD REQUEST: Invalid accounts or validation error
    - 401 UNAUTHORIZED: Missing or invalid authentication
    - 500 INTERNAL SERVER ERROR: Database error
    """
    user_id = user.user_id
    supabase_client = get_supabase_client(user.access_token)
    
    logger.info(
        f"POST /transfers: user {user_id} transferring {request.amount} "
        f"from {request.from_account_id} to {request.to_account_id}"
    )
    
    try:
        outgoing, incoming = await transfer_service.create_transfer(
            supabase_client=supabase_client,
            user_id=user_id,
            from_account_id=request.from_account_id,
            to_account_id=request.to_account_id,
            amount=request.amount,
            date=request.date,
            description=request.description
        )
        
        transfer_response = TransferResponse(
            from_transaction_id=outgoing["id"],
            to_transaction_id=incoming["id"],
            from_account_id=request.from_account_id,
            to_account_id=request.to_account_id,
            amount=request.amount,
            date=request.date,
            description=request.description
        )
        
        return TransferCreateResponse(
            status="CREATED",
            transfer=transfer_response,
            message="Transfer created successfully"
        )
    
    except ValueError as e:
        logger.warning(f"Validation error creating transfer: {e}")
        raise HTTPException(status_code=400, detail={"error": "validation_error", "details": str(e)})
    
    except Exception as e:
        logger.error(f"Error creating transfer: {e}")
        raise HTTPException(status_code=500, detail={"error": "internal_error", "details": "Failed to create transfer"})


@router.post(
    "/recurring",
    response_model=RecurringTransferCreateResponse,
    status_code=201,
    summary="Create a recurring transfer template"
)
async def create_recurring_transfer(
    request: RecurringTransferCreateRequest,
    user: Annotated[AuthenticatedUser, Depends(get_authenticated_user)]
):
    """
    Create a recurring transfer template between two accounts.
    
    Creates two paired recurring_transaction rules:
    - Outcome template for source account
    - Income template for destination account
    
    Both rules are linked via `paired_recurring_transaction_id`.
    
    **Requirements:**
    - Both accounts must belong to the authenticated user
    - Amount must be positive
    - Frequency: 'daily', 'weekly', 'monthly', or 'yearly'
    - Interval must be >= 1
    - Weekly frequency requires `by_weekday` (e.g., ["monday", "wednesday"])
    - Monthly frequency requires `by_monthday` (e.g., [1, 15, 30])
    - Dates must be in ISO-8601 format (YYYY-MM-DD)
    
    **Returns:**
    - 201 CREATED: Recurring transfer created successfully
    - 400 BAD REQUEST: Invalid accounts or validation error
    - 401 UNAUTHORIZED: Missing or invalid authentication
    - 500 INTERNAL SERVER ERROR: Database error
    """
    user_id = user.user_id
    supabase_client = get_supabase_client(user.access_token)
    
    logger.info(
        f"POST /transfers/recurring: user {user_id} creating {request.frequency} transfer "
        f"of {request.amount} from {request.from_account_id} to {request.to_account_id}"
    )
    
    # Frequency-specific validation
    if request.frequency == "weekly" and not request.by_weekday:
        raise HTTPException(
            status_code=400,
            detail={"error": "validation_error", "details": "Weekly frequency requires by_weekday"}
        )
    
    if request.frequency == "monthly" and not request.by_monthday:
        raise HTTPException(
            status_code=400,
            detail={"error": "validation_error", "details": "Monthly frequency requires by_monthday"}
        )
    
    try:
        outgoing_rule, incoming_rule = await transfer_service.create_recurring_transfer(
            supabase_client=supabase_client,
            user_id=user_id,
            from_account_id=request.from_account_id,
            to_account_id=request.to_account_id,
            amount=request.amount,
            description_outgoing=request.description_outgoing,
            description_incoming=request.description_incoming,
            frequency=request.frequency,
            interval=request.interval,
            start_date=request.start_date,
            by_weekday=request.by_weekday,
            by_monthday=request.by_monthday,
            end_date=request.end_date,
            is_active=request.is_active
        )
        
        recurring_transfer_response = RecurringTransferResponse(
            outgoing_rule_id=outgoing_rule["id"],
            incoming_rule_id=incoming_rule["id"],
            from_account_id=request.from_account_id,
            to_account_id=request.to_account_id,
            amount=request.amount,
            description_outgoing=request.description_outgoing,
            description_incoming=request.description_incoming,
            frequency=request.frequency,
            interval=request.interval,
            by_weekday=request.by_weekday,
            by_monthday=request.by_monthday,
            start_date=request.start_date,
            next_run_date=outgoing_rule["next_run_date"],
            end_date=request.end_date,
            is_active=request.is_active,
            created_at=outgoing_rule["created_at"]
        )
        
        return RecurringTransferCreateResponse(
            status="CREATED",
            recurring_transfer=recurring_transfer_response,
            message="Recurring transfer created successfully"
        )
    
    except ValueError as e:
        logger.warning(f"Validation error creating recurring transfer: {e}")
        raise HTTPException(status_code=400, detail={"error": "validation_error", "details": str(e)})
    
    except Exception as e:
        logger.error(f"Error creating recurring transfer: {e}")
        raise HTTPException(status_code=500, detail={"error": "internal_error", "details": "Failed to create recurring transfer"})
