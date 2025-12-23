"""
Transaction CRUD API endpoints.

Provides endpoints for managing financial transactions (income/outcome).

Transactions represent individual money movements tied to accounts and categories.
They may be created manually by users or automatically from invoice OCR.
"""

import logging
from typing import Annotated, Literal, Optional, cast

from fastapi import APIRouter, Depends, HTTPException, Query, status

from backend.auth.dependencies import AuthenticatedUser, get_authenticated_user
from backend.db.client import get_supabase_client
from backend.schemas.transactions import (
    TransactionCreateRequest,
    TransactionCreateResponse,
    TransactionDeleteResponse,
    TransactionDetailResponse,
    TransactionListResponse,
    TransactionUpdateRequest,
    TransactionUpdateResponse,
)
from backend.services import (
    create_transaction,
    delete_transaction,
    get_transaction_by_id,
    get_user_transactions,
    update_transaction,
)
from backend.services.engagement_service import update_streak_after_activity

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/transactions", tags=["transactions"])


def _require_field(data: dict, key: str):
    """Return data[key] or raise ValueError if missing/None."""
    val = data.get(key)
    if val is None:
        raise ValueError(f"Missing required field '{key}' in transaction data")
    return val


def _coerce_flow_type(data: dict, key: str) -> Literal["income", "outcome"]:
    val = _require_field(data, key)
    if val not in ("income", "outcome"):
        raise ValueError(f"Invalid flow_type: {val}")
    return cast(Literal["income", "outcome"], val)


def _coerce_float(data: dict, key: str) -> float:
    val = _require_field(data, key)
    try:
        return float(val)
    except Exception:
        raise ValueError(f"Field '{key}' is not convertible to float: {val}")


def _coerce_str(data: dict, key: str) -> str:
    return str(_require_field(data, key))



@router.post(
    "",
    response_model=TransactionCreateResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create a new transaction",
    description="""
    Create a new transaction manually.

    This endpoint:
    - Accepts transaction data from the frontend
    - Inserts record into the transaction table with RLS enforcement
    - Returns the created transaction ID and details

    Use this for:
    - Manual transaction entry by user
    - Recording cash expenses
    - Income transactions

    Security:
    - Requires valid Authorization Bearer token
    - RLS ensures user can only create transactions for themselves
    """
)
async def create_transaction_record(
    request: TransactionCreateRequest,
    auth_user: Annotated[AuthenticatedUser, Depends(get_authenticated_user)]
) -> TransactionCreateResponse:
    """
    Create a new transaction manually.

    **6-STEP ENDPOINT FLOW:**

    Step 1: Auth
    - Handled by get_authenticated_user dependency
    - Extracts user_id and access_token from Supabase Auth

    Step 2: Parse/Validate Request
    - FastAPI validates TransactionCreateRequest automatically
    - Ensures all required fields are present

    Step 3: Domain & Intent Filter
    - Validate that this is a valid transaction creation request
    - Check that required fields are non-empty

    Step 4: Call Service
    - Call create_transaction() service function
    - Service handles RLS enforcement

    Step 5: Map Output -> ResponseModel
    - Return TransactionCreateResponse with transaction details

    Step 6: Persistence
    - Service layer handles persistence via authenticated Supabase client
    """

    logger.info(
        f"Creating transaction for user_id={auth_user.user_id}, "
        f"account={request.account_id}, amount={request.amount}, flow_type={request.flow_type}"
    )

    # Create authenticated Supabase client (RLS enforced)
    supabase_client = get_supabase_client(auth_user.access_token)

    try:
        # Persist transaction to database
        created_transaction = await create_transaction(
            supabase_client=supabase_client,
            user_id=auth_user.user_id,
            account_id=request.account_id,
            category_id=request.category_id,
            flow_type=request.flow_type,
            amount=request.amount,
            date=request.date,
            description=request.description,
        )

        transaction_id = created_transaction.get("id")

        if not transaction_id:
            raise Exception("Transaction created but no ID returned")

        # Update streak after successful transaction creation (non-blocking)
        try:
            await update_streak_after_activity(
                supabase_client=supabase_client,
                user_id=auth_user.user_id
            )
        except Exception as streak_err:
            # Don't fail the transaction if streak update fails
            logger.warning(
                f"Failed to update streak for user_id={auth_user.user_id}: {streak_err}"
            )

        # Map to response model (validate and coerce required fields)
        transaction_detail = TransactionDetailResponse(
            id=str(transaction_id),
            user_id=str(created_transaction.get("user_id")),
            account_id=str(created_transaction.get("account_id")),
            category_id=str(created_transaction.get("category_id")),
            invoice_id=created_transaction.get("invoice_id"),
            flow_type=_coerce_flow_type(created_transaction, "flow_type"),
            amount=_coerce_float(created_transaction, "amount"),
            date=_coerce_str(created_transaction, "date"),
            description=created_transaction.get("description"),
            embedding=created_transaction.get("embedding"),
            paired_transaction_id=created_transaction.get("paired_transaction_id"),
            created_at=_coerce_str(created_transaction, "created_at"),
            updated_at=created_transaction.get("updated_at"),
        )

        logger.info(
            f"Transaction created successfully: "
            f"id={transaction_id}, user_id={auth_user.user_id}"
        )

        return TransactionCreateResponse(
            status="CREATED",
            transaction_id=str(transaction_id),
            transaction=transaction_detail,
            message="Transaction created successfully"
        )

    except ValueError as e:
        logger.error(f"Invalid transaction data: {e}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={
                "error": "invalid_request",
                "details": str(e)
            }
        )
    except Exception as e:
        logger.error(f"Failed to create transaction: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={
                "error": "persistence_error",
                "details": "Failed to save transaction to database"
            }
        )


@router.get(
    "",
    response_model=TransactionListResponse,
    status_code=status.HTTP_200_OK,
    summary="List user's transactions",
    description="""
    Retrieve all transactions belonging to the authenticated user.

    This endpoint:
    - Returns paginated list of transactions
    - Only shows transactions owned by the authenticated user (RLS enforced)
    - Supports filtering by account, category, flow type, and date range
    - Supports sorting by date or amount
    - Orders by date descending (newest first) by default

    Security:
    - Requires valid authentication token
    - RLS ensures users only see their own transactions
    """
)
async def list_transactions(
    auth_user: Annotated[AuthenticatedUser, Depends(get_authenticated_user)],
    limit: int = Query(50, ge=1, le=100, description="Maximum number of transactions to return"),
    offset: int = Query(0, ge=0, description="Number of transactions to skip for pagination"),
    account_id: Optional[str] = Query(None, description="Filter by account UUID"),
    category_id: Optional[str] = Query(None, description="Filter by category UUID"),
    flow_type: Optional[str] = Query(None, description="Filter by flow type (income/outcome)"),
    from_date: Optional[str] = Query(None, description="Filter by start date (ISO-8601)"),
    to_date: Optional[str] = Query(None, description="Filter by end date (ISO-8601)"),
    sort_by: str = Query("date", description="Sort field (date|amount)"),
    sort_order: str = Query("desc", description="Sort order (asc|desc)"),
) -> TransactionListResponse:
    """
    List all transactions for the authenticated user.

    Args:
        auth_user: Authenticated user from token
        limit: Maximum number of transactions to return (default 50, max 100)
        offset: Number of transactions to skip for pagination (default 0)
        account_id: Optional filter by account
        category_id: Optional filter by category
        flow_type: Optional filter by flow type
        from_date: Optional filter by start date
        to_date: Optional filter by end date
        sort_by: Field to sort by (date or amount, default date)
        sort_order: Sort order (asc or desc, default desc)

    Returns:
        TransactionListResponse with list of transactions and pagination metadata
    """
    logger.info(
        f"Listing transactions for user {auth_user.user_id} "
        f"(limit={limit}, offset={offset}, sort_by={sort_by}, sort_order={sort_order}, "
        f"filters: account={account_id}, category={category_id}, flow_type={flow_type})"
    )

    # Create authenticated Supabase client
    supabase_client = get_supabase_client(auth_user.access_token)

    try:
        # Fetch transactions from database (RLS enforced)
        transactions = await get_user_transactions(
            supabase_client=supabase_client,
            user_id=auth_user.user_id,
            limit=limit,
            offset=offset,
            account_id=account_id,
            category_id=category_id,
            flow_type=flow_type,
            from_date=from_date,
            to_date=to_date,
            sort_by=sort_by,
            sort_order=sort_order,
        )

        # Map to response models (validate & coerce required fields)
        transaction_responses = []
        for txn in transactions:
            transaction_responses.append(
                TransactionDetailResponse(
                    id=str(txn.get("id")),
                    user_id=str(txn.get("user_id")),
                    account_id=str(txn.get("account_id")),
                    category_id=str(txn.get("category_id")),
                    invoice_id=txn.get("invoice_id"),
                    flow_type=_coerce_flow_type(txn, "flow_type"),
                    amount=_coerce_float(txn, "amount"),
                    date=_coerce_str(txn, "date"),
                    description=txn.get("description"),
                    embedding=txn.get("embedding"),
                    paired_transaction_id=txn.get("paired_transaction_id"),
                    created_at=_coerce_str(txn, "created_at"),
                    updated_at=txn.get("updated_at"),
                )
            )

        logger.info(f"Returning {len(transaction_responses)} transactions for user {auth_user.user_id}")

        return TransactionListResponse(
            transactions=transaction_responses,
            count=len(transaction_responses),
            limit=limit,
            offset=offset
        )

    except Exception as e:
        logger.error(f"Failed to fetch transactions: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={
                "error": "fetch_error",
                "details": "Failed to retrieve transactions from database"
            }
        )


@router.get(
    "/{transaction_id}",
    response_model=TransactionDetailResponse,
    status_code=status.HTTP_200_OK,
    summary="Get transaction details",
    description="""
    Retrieve a single transaction by its ID.

    This endpoint:
    - Returns detailed transaction information
    - Only returns transaction if it belongs to the authenticated user (RLS enforced)
    - Returns 404 if transaction doesn't exist or belongs to another user

    Security:
    - Requires valid authentication token
    - RLS ensures users can only access their own transactions
    """
)
async def get_transaction(
    transaction_id: str,
    auth_user: Annotated[AuthenticatedUser, Depends(get_authenticated_user)]
) -> TransactionDetailResponse:
    """
    Get details of a single transaction.

    Args:
        transaction_id: UUID of the transaction to retrieve
        auth_user: Authenticated user from token

    Returns:
        TransactionDetailResponse with transaction details

    Raises:
        HTTPException 404: If transaction not found or not accessible by user
    """
    logger.info(f"Fetching transaction {transaction_id} for user {auth_user.user_id}")

    # Create authenticated Supabase client
    supabase_client = get_supabase_client(auth_user.access_token)

    try:
        # Fetch transaction from database (RLS enforced)
        transaction = await get_transaction_by_id(
            supabase_client=supabase_client,
            user_id=auth_user.user_id,
            transaction_id=transaction_id
        )

        if not transaction:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail={
                    "error": "not_found",
                    "details": f"Transaction {transaction_id} not found or not accessible"
                }
            )

        logger.info(f"Returning transaction {transaction_id} for user {auth_user.user_id}")

        return TransactionDetailResponse(
            id=str(transaction.get("id")),
            user_id=str(transaction.get("user_id")),
            account_id=str(transaction.get("account_id")),
            category_id=str(transaction.get("category_id")),
            invoice_id=transaction.get("invoice_id"),
            flow_type=_coerce_flow_type(transaction, "flow_type"),
            amount=_coerce_float(transaction, "amount"),
            date=_coerce_str(transaction, "date"),
            description=transaction.get("description"),
            embedding=transaction.get("embedding"),
            paired_transaction_id=transaction.get("paired_transaction_id"),
            created_at=_coerce_str(transaction, "created_at"),
            updated_at=transaction.get("updated_at"),
        )

    except HTTPException:
        # Re-raise HTTP exceptions (like 404)
        raise
    except Exception as e:
        logger.error(f"Failed to fetch transaction {transaction_id}: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={
                "error": "fetch_error",
                "details": "Failed to retrieve transaction from database"
            }
        )


@router.patch(
    "/{transaction_id}",
    response_model=TransactionUpdateResponse,
    status_code=status.HTTP_200_OK,
    summary="Update transaction details",
    description="""
    Update an existing transaction's details.

    This endpoint:
    - Accepts partial updates (only provided fields are updated)
    - Returns the complete updated transaction details
    - Requires valid Authorization Bearer token

    Security:
    - Only the transaction owner can update their transactions
    - Returns 404 if transaction doesn't exist or belongs to another user
    """
)
async def update_transaction_details(
    transaction_id: str,
    request: TransactionUpdateRequest,
    auth_user: Annotated[AuthenticatedUser, Depends(get_authenticated_user)]
) -> TransactionUpdateResponse:
    """
    Update a transaction record.

    **6-STEP ENDPOINT FLOW:**

    Step 1: Auth
    - Handled by get_authenticated_user dependency
    - Extracts user_id and access_token from Supabase Auth token

    Step 2: Parse/Validate Request
    - FastAPI validates TransactionUpdateRequest automatically
    - At least one field must be provided for a valid update

    Step 3: Domain & Intent Filter
    - Validate that this is a valid transaction update request
    - Check that transaction exists and belongs to authenticated user

    Step 4: Call Service
    - Call update_transaction() service function
    - Service handles RLS enforcement

    Step 5: Map Output -> ResponseModel
    - Convert updated transaction to TransactionDetailResponse
    - Return TransactionUpdateResponse with updated transaction

    Step 6: Persistence
    - Service layer handles persistence via authenticated Supabase client
    """

    logger.info(
        f"Updating transaction {transaction_id} for user {auth_user.user_id}"
    )

    # Create authenticated Supabase client
    supabase_client = get_supabase_client(auth_user.access_token)

    try:
        # First, check if this is a transfer transaction
        transaction_check = (
            supabase_client.table("transaction")
            .select("id, paired_transaction_id, category_id")
            .eq("id", transaction_id)
            .eq("user_id", auth_user.user_id)
            .execute()
        )

        if not transaction_check.data or len(transaction_check.data) == 0:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail={
                    "error": "not_found",
                    "details": f"Transaction {transaction_id} not found or not accessible"
                }
            )

        # Type assertion: we know this is a dict from Supabase
        transaction: dict = transaction_check.data[0]  # type: ignore

        # If this is a transfer (has paired_transaction_id), reject the update
        paired_id = transaction.get("paired_transaction_id")
        if paired_id is not None:
            # Fetch the category to confirm it's a transfer category
            category_id = transaction.get("category_id")
            category_check = (
                supabase_client.table("category")
                .select("key")
                .eq("id", category_id)
                .execute()
            )

            if category_check.data and len(category_check.data) > 0:
                category_row: dict = category_check.data[0]  # type: ignore
                category_key = category_row.get("key")
                if category_key in ("transfer", "from_recurrent_transaction"):
                    logger.warning(
                        f"Attempted to edit transfer transaction {transaction_id} via PATCH /transactions"
                    )
                    raise HTTPException(
                        status_code=status.HTTP_400_BAD_REQUEST,
                        detail={
                            "error": "cannot_edit_transfer",
                            "details": "This transaction is part of an internal transfer. Use PATCH /transfers/{id} to edit it."
                        }
                    )

        # Update transaction (service handles RLS enforcement)
        updated_transaction = await update_transaction(
            supabase_client=supabase_client,
            user_id=auth_user.user_id,
            transaction_id=transaction_id,
            account_id=request.account_id,
            category_id=request.category_id,
            flow_type=request.flow_type,
            amount=request.amount,
            date=request.date,
            description=request.description,
        )

        if not updated_transaction:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail={
                    "error": "not_found",
                    "details": f"Transaction {transaction_id} not found or not accessible"
                }
            )

        # Map to response model
        transaction_detail = TransactionDetailResponse(
            id=str(updated_transaction.get("id")),
            user_id=str(updated_transaction.get("user_id")),
            account_id=str(updated_transaction.get("account_id")),
            category_id=str(updated_transaction.get("category_id")),
            invoice_id=updated_transaction.get("invoice_id"),
            flow_type=_coerce_flow_type(updated_transaction, "flow_type"),
            amount=_coerce_float(updated_transaction, "amount"),
            date=_coerce_str(updated_transaction, "date"),
            description=updated_transaction.get("description"),
            embedding=updated_transaction.get("embedding"),
            paired_transaction_id=updated_transaction.get("paired_transaction_id"),
            created_at=_coerce_str(updated_transaction, "created_at"),
            updated_at=updated_transaction.get("updated_at"),
        )

        logger.info(f"Transaction {transaction_id} updated successfully for user {auth_user.user_id}")

        return TransactionUpdateResponse(
            status="UPDATED",
            transaction_id=str(transaction_id),
            transaction=transaction_detail,
            message="Transaction updated successfully"
        )

    except HTTPException:
        # Re-raise HTTP exceptions
        raise
    except ValueError as e:
        logger.error(f"Invalid transaction data: {e}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={
                "error": "invalid_request",
                "details": str(e)
            }
        )
    except Exception as e:
        logger.error(f"Failed to update transaction {transaction_id}: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={
                "error": "update_error",
                "details": "Failed to update transaction"
            }
        )


@router.delete(
    "/{transaction_id}",
    response_model=TransactionDeleteResponse,
    status_code=status.HTTP_200_OK,
    summary="Delete a transaction",
    description="""
    Delete an existing transaction.

    This endpoint:
    - Permanently removes the transaction from the database
    - If part of a paired transfer, clears the pair reference
    - Does NOT delete linked invoices
    - Requires valid Authorization Bearer token

    Security:
    - Only the transaction owner can delete their transactions
    - Returns 404 if transaction doesn't exist or belongs to another user
    """
)
async def delete_transaction_record(
    transaction_id: str,
    auth_user: Annotated[AuthenticatedUser, Depends(get_authenticated_user)]
) -> TransactionDeleteResponse:
    """
    Delete a transaction record.

    **6-STEP ENDPOINT FLOW:**

    Step 1: Auth
    - Handled by get_authenticated_user dependency
    - Extracts user_id and access_token from Supabase Auth token

    Step 2: Parse/Validate Request
    - FastAPI validates path parameter transaction_id

    Step 3: Domain & Intent Filter
    - Validate that this is a valid transaction delete request
    - Check that transaction exists and belongs to authenticated user

    Step 4: Call Service
    - Call delete_transaction() service function
    - Service handles RLS enforcement and paired transaction cleanup

    Step 5: Map Output -> ResponseModel
    - Return TransactionDeleteResponse

    Step 6: Persistence
    - Service layer handles deletion via authenticated Supabase client
    """

    logger.info(f"Deleting transaction {transaction_id} for user {auth_user.user_id}")

    # Create authenticated Supabase client
    supabase_client = get_supabase_client(auth_user.access_token)

    try:
        # Delete transaction (service handles RLS enforcement and pair cleanup)
        success = await delete_transaction(
            supabase_client=supabase_client,
            user_id=auth_user.user_id,
            transaction_id=transaction_id,
        )

        if not success:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail={
                    "error": "not_found",
                    "details": f"Transaction {transaction_id} not found or not accessible"
                }
            )

        logger.info(f"Transaction {transaction_id} deleted successfully for user {auth_user.user_id}")

        return TransactionDeleteResponse(
            status="DELETED",
            transaction_id=str(transaction_id),
            message="Transaction deleted successfully"
        )

    except HTTPException:
        # Re-raise HTTP exceptions
        raise
    except Exception as e:
        logger.error(f"Failed to delete transaction {transaction_id}: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={
                "error": "delete_error",
                "details": "Failed to delete transaction"
            }
        )
