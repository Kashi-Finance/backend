"""
Transfer endpoints for creating and managing transfers between accounts.

All transfers are paired transactions that move money internally between
the user's own accounts.
"""

import logging
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException

from backend.auth.dependencies import AuthenticatedUser, get_authenticated_user
from backend.db.client import get_supabase_client
from backend.schemas.recurring_transactions import RecurringTransactionResponse
from backend.schemas.transactions import TransactionDetailResponse
from backend.schemas.transfers import (
    RecurringTransferCreateRequest,
    RecurringTransferCreateResponse,
    TransferCreateRequest,
    TransferCreateResponse,
    TransferUpdateRequest,
    TransferUpdateResponse,
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

        # Map the two transaction dicts to TransactionDetailResponse
        transactions = [
            TransactionDetailResponse(**outgoing),
            TransactionDetailResponse(**incoming)
        ]

        return TransferCreateResponse(
            status="CREATED",
            transactions=transactions,
            message="Transfer created successfully"
        )

    except ValueError as e:
        logger.warning(f"Validation error creating transfer: {e}")
        raise HTTPException(status_code=400, detail={"error": "validation_error", "details": str(e)})

    except Exception as e:
        logger.error(f"Error creating transfer: {e}")
        raise HTTPException(status_code=500, detail={"error": "internal_error", "details": "Failed to create transfer"})


@router.patch(
    "/{transaction_id}",
    response_model=TransferUpdateResponse,
    status_code=200,
    summary="Update a transfer"
)
async def update_transfer(
    transaction_id: str,
    request: TransferUpdateRequest,
    user: Annotated[AuthenticatedUser, Depends(get_authenticated_user)]
):
    """
    Update an existing transfer.

    Updates both paired transactions atomically with the same values.

    **Allowed Updates:**
    - `amount`: New transfer amount (must be > 0)
    - `date`: New transfer date (ISO-8601 format)
    - `description`: New description for both transactions

    **Immutable Fields:**
    - `category_id` (transfers must use system 'transfer' category)
    - `flow_type` (outcome/income are fixed by design)
    - `paired_transaction_id` (cannot be changed)
    - `account_id` (would break the transfer structure)

    **Requirements:**
    - Transaction must be a transfer (have `paired_transaction_id`)
    - Transaction must belong to the authenticated user
    - At least one field must be provided for update

    **Returns:**
    - 200 OK: Transfer updated successfully
    - 400 BAD REQUEST: Not a transfer or validation error
    - 401 UNAUTHORIZED: Missing or invalid authentication
    - 404 NOT FOUND: Transaction not found
    - 500 INTERNAL SERVER ERROR: Database error
    """
    user_id = user.user_id
    supabase_client = get_supabase_client(user.access_token)

    logger.info(
        f"PATCH /transfers/{transaction_id}: user {user_id} updating transfer"
    )

    # Validate at least one field provided
    if request.amount is None and request.date is None and request.description is None:
        raise HTTPException(
            status_code=400,
            detail={
                "error": "validation_error",
                "details": "At least one field (amount, date, or description) must be provided"
            }
        )

    try:
        updated_txn, paired_txn = await transfer_service.update_transfer(
            supabase_client=supabase_client,
            user_id=user_id,
            transaction_id=transaction_id,
            amount=request.amount,
            date=request.date,
            description=request.description
        )

        # Map the two transaction dicts to TransactionDetailResponse
        transactions = [
            TransactionDetailResponse(**updated_txn),
            TransactionDetailResponse(**paired_txn)
        ]

        return TransferUpdateResponse(
            status="UPDATED",
            transactions=transactions,
            message="Transfer updated successfully"
        )

    except ValueError as e:
        logger.warning(f"Validation error updating transfer: {e}")
        error_msg = str(e)
        if "not found" in error_msg.lower() or "not accessible" in error_msg.lower():
            raise HTTPException(status_code=404, detail={"error": "not_found", "details": str(e)})
        elif "not a transfer" in error_msg.lower():
            raise HTTPException(status_code=400, detail={"error": "not_a_transfer", "details": str(e)})
        else:
            raise HTTPException(status_code=400, detail={"error": "validation_error", "details": str(e)})

    except Exception as e:
        logger.error(f"Error updating transfer: {e}")
        raise HTTPException(status_code=500, detail={"error": "internal_error", "details": "Failed to update transfer"})


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

        # Map the two recurring transaction dicts to RecurringTransactionResponse
        recurring_transactions = [
            RecurringTransactionResponse(**outgoing_rule),
            RecurringTransactionResponse(**incoming_rule)
        ]

        return RecurringTransferCreateResponse(
            status="CREATED",
            recurring_transactions=recurring_transactions,
            message="Recurring transfer created successfully"
        )

    except ValueError as e:
        logger.warning(f"Validation error creating recurring transfer: {e}")
        raise HTTPException(status_code=400, detail={"error": "validation_error", "details": str(e)})

    except Exception as e:
        logger.error(f"Error creating recurring transfer: {e}")
        raise HTTPException(status_code=500, detail={"error": "internal_error", "details": "Failed to create recurring transfer"})
