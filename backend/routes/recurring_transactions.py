"""
Recurring transaction CRUD and sync API endpoints.

Provides endpoints for managing recurring transaction rules that
automatically generate transactions based on schedules.

Endpoints:
- GET /recurring-transactions - List all recurring rules
- POST /recurring-transactions - Create a new recurring rule
- GET /recurring-transactions/{id} - Get single recurring rule
- PATCH /recurring-transactions/{id} - Update recurring rule
- DELETE /recurring-transactions/{id} - Delete recurring rule
- POST /transactions/sync-recurring - Synchronize and generate pending transactions
"""

import logging
from typing import Annotated, Any
from fastapi import APIRouter, Depends, HTTPException, status, Path

from backend.auth.dependencies import get_authenticated_user, AuthenticatedUser
from backend.db.client import get_supabase_client
from backend.services.recurring_transaction_service import (
    get_all_recurring_transactions,
    get_recurring_transaction_by_id,
    create_recurring_transaction,
    update_recurring_transaction,
    delete_recurring_transaction,
    sync_recurring_transactions,
)
from backend.schemas.recurring_transactions import (
    RecurringTransactionResponse,
    RecurringTransactionListResponse,
    RecurringTransactionCreateRequest,
    RecurringTransactionCreateResponse,
    RecurringTransactionUpdateRequest,
    RecurringTransactionUpdateResponse,
    RecurringTransactionDeleteResponse,
    SyncRecurringTransactionsRequest,
    SyncRecurringTransactionsResponse,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/recurring-transactions", tags=["recurring-transactions"])


@router.get(
    "",
    response_model=RecurringTransactionListResponse,
    status_code=status.HTTP_200_OK,
    summary="List all recurring transaction rules",
    description="""
    Retrieve all recurring transaction rules for the authenticated user.
    
    This endpoint:
    - Returns all user's recurring rules
    - Ordered by creation date (newest first)
    - Only accessible to the rule owner (RLS enforced)
    
    Security:
    - Requires valid Authorization Bearer token
    - RLS ensures users only see their own rules
    """
)
async def list_recurring_transactions(
    auth_user: Annotated[AuthenticatedUser, Depends(get_authenticated_user)]
) -> RecurringTransactionListResponse:
    """List all recurring transaction rules for the authenticated user."""
    logger.info(f"Listing recurring transactions for user {auth_user.user_id}")
    
    supabase_client = get_supabase_client(auth_user.access_token)
    
    try:
        rules = await get_all_recurring_transactions(
            supabase_client=supabase_client,
            user_id=auth_user.user_id
        )
        
        # Helper to coerce DB values
        def _as_str(v: Any) -> str:
            return str(v) if v is not None else ""
        
        def _as_float(v: Any) -> float:
            try:
                return float(v) if v is not None else 0.0
            except (ValueError, TypeError):
                return 0.0
        
        def _as_int(v: Any) -> int:
            try:
                return int(v) if v is not None else 1
            except (ValueError, TypeError):
                return 1
        
        def _as_bool(v: Any) -> bool:
            return bool(v) if v is not None else True
        
        rule_responses = [
            RecurringTransactionResponse(
                id=_as_str(r.get("id")),
                user_id=_as_str(r.get("user_id")),
                account_id=_as_str(r.get("account_id")),
                category_id=_as_str(r.get("category_id")),
                flow_type=r.get("flow_type", "outcome"),  # type: ignore
                amount=_as_float(r.get("amount")),
                description=_as_str(r.get("description")),
                paired_recurring_transaction_id=_as_str(r.get("paired_recurring_transaction_id")) if r.get("paired_recurring_transaction_id") else None,
                frequency=r.get("frequency", "monthly"),  # type: ignore
                interval=_as_int(r.get("interval")),
                by_weekday=r.get("by_weekday"),
                by_monthday=r.get("by_monthday"),
                start_date=_as_str(r.get("start_date")),
                next_run_date=_as_str(r.get("next_run_date")),
                end_date=_as_str(r.get("end_date")) if r.get("end_date") else None,
                is_active=_as_bool(r.get("is_active")),
                created_at=_as_str(r.get("created_at")),
                updated_at=_as_str(r.get("updated_at"))
            )
            for r in rules
        ]
        
        logger.info(f"Returning {len(rule_responses)} recurring rules for user {auth_user.user_id}")
        
        return RecurringTransactionListResponse(
            recurring_transactions=rule_responses,
            count=len(rule_responses)
        )
        
    except Exception as e:
        logger.error(f"Failed to fetch recurring transactions: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={
                "error": "fetch_error",
                "details": "Failed to retrieve recurring transactions from database"
            }
        )


@router.post(
    "",
    response_model=RecurringTransactionCreateResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create a new recurring transaction rule",
    description="""
    Create a new recurring transaction rule.
    
    This endpoint:
    - Creates a new rule that will automatically generate transactions
    - Validates frequency-specific constraints (by_weekday, by_monthday)
    - Validates interval >= 1
    
    Security:
    - Requires valid Authorization Bearer token
    - RLS enforces rule is owned by authenticated user
    """
)
async def create_new_recurring_transaction(
    request: RecurringTransactionCreateRequest,
    auth_user: Annotated[AuthenticatedUser, Depends(get_authenticated_user)]
) -> RecurringTransactionCreateResponse:
    """Create a new recurring transaction rule."""
    logger.info(f"Creating recurring transaction for user {auth_user.user_id}: {request.description}")
    
    # Validate frequency-specific constraints
    if request.frequency == "weekly":
        if not request.by_weekday or len(request.by_weekday) == 0:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail={
                    "error": "validation_error",
                    "details": "by_weekday is required and must not be empty for weekly frequency"
                }
            )
    
    if request.frequency == "monthly":
        if not request.by_monthday or len(request.by_monthday) == 0:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail={
                    "error": "validation_error",
                    "details": "by_monthday is required and must not be empty for monthly frequency"
                }
            )
    
    supabase_client = get_supabase_client(auth_user.access_token)
    
    try:
        created_rule = await create_recurring_transaction(
            supabase_client=supabase_client,
            user_id=auth_user.user_id,
            account_id=request.account_id,
            category_id=request.category_id,
            flow_type=request.flow_type,
            amount=request.amount,
            description=request.description,
            frequency=request.frequency,
            interval=request.interval,
            start_date=request.start_date,
            paired_recurring_transaction_id=request.paired_recurring_transaction_id,
            by_weekday=request.by_weekday,
            by_monthday=request.by_monthday,
            end_date=request.end_date,
            is_active=request.is_active
        )
        
        # Helper to coerce DB values
        def _as_str(v: Any) -> str:
            return str(v) if v is not None else ""
        
        def _as_float(v: Any) -> float:
            try:
                return float(v) if v is not None else 0.0
            except (ValueError, TypeError):
                return 0.0
        
        def _as_int(v: Any) -> int:
            try:
                return int(v) if v is not None else 1
            except (ValueError, TypeError):
                return 1
        
        def _as_bool(v: Any) -> bool:
            return bool(v) if v is not None else True
        
        rule_response = RecurringTransactionResponse(
            id=_as_str(created_rule.get("id")),
            user_id=_as_str(created_rule.get("user_id")),
            account_id=_as_str(created_rule.get("account_id")),
            category_id=_as_str(created_rule.get("category_id")),
            flow_type=created_rule.get("flow_type", "outcome"),  # type: ignore
            amount=_as_float(created_rule.get("amount")),
            description=_as_str(created_rule.get("description")),
            paired_recurring_transaction_id=_as_str(created_rule.get("paired_recurring_transaction_id")) if created_rule.get("paired_recurring_transaction_id") else None,
            frequency=created_rule.get("frequency", "monthly"),  # type: ignore
            interval=_as_int(created_rule.get("interval")),
            by_weekday=created_rule.get("by_weekday"),
            by_monthday=created_rule.get("by_monthday"),
            start_date=_as_str(created_rule.get("start_date")),
            next_run_date=_as_str(created_rule.get("next_run_date")),
            end_date=_as_str(created_rule.get("end_date")) if created_rule.get("end_date") else None,
            is_active=_as_bool(created_rule.get("is_active")),
            created_at=_as_str(created_rule.get("created_at")),
            updated_at=_as_str(created_rule.get("updated_at"))
        )
        
        logger.info(f"Recurring transaction created successfully: {rule_response.id}")
        
        return RecurringTransactionCreateResponse(
            status="CREATED",
            recurring_transaction=rule_response,
            message="Recurring transaction rule created successfully"
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to create recurring transaction: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={
                "error": "create_error",
                "details": "Failed to create recurring transaction"
            }
        )


@router.get(
    "/{recurring_transaction_id}",
    response_model=RecurringTransactionResponse,
    status_code=status.HTTP_200_OK,
    summary="Get recurring transaction rule details",
    description="""
    Retrieve details of a single recurring transaction rule by ID.
    
    This endpoint:
    - Returns rule details for the specified ID
    - Only accessible to the rule owner (RLS enforced)
    
    Security:
    - Requires valid Authorization Bearer token
    - Returns 404 if rule doesn't exist or belongs to another user
    """
)
async def get_recurring_transaction(
    recurring_transaction_id: Annotated[str, Path(description="Recurring transaction UUID")],
    auth_user: Annotated[AuthenticatedUser, Depends(get_authenticated_user)]
) -> RecurringTransactionResponse:
    """Get recurring transaction rule by ID."""
    logger.info(f"Fetching recurring transaction {recurring_transaction_id} for user {auth_user.user_id}")
    
    supabase_client = get_supabase_client(auth_user.access_token)
    
    try:
        rule = await get_recurring_transaction_by_id(
            supabase_client=supabase_client,
            user_id=auth_user.user_id,
            recurring_transaction_id=recurring_transaction_id
        )
        
        if not rule:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail={
                    "error": "not_found",
                    "details": "Recurring transaction not found"
                }
            )
        
        # Helper to coerce DB values
        def _as_str(v: Any) -> str:
            return str(v) if v is not None else ""
        
        def _as_float(v: Any) -> float:
            try:
                return float(v) if v is not None else 0.0
            except (ValueError, TypeError):
                return 0.0
        
        def _as_int(v: Any) -> int:
            try:
                return int(v) if v is not None else 1
            except (ValueError, TypeError):
                return 1
        
        def _as_bool(v: Any) -> bool:
            return bool(v) if v is not None else True
        
        return RecurringTransactionResponse(
            id=_as_str(rule.get("id")),
            user_id=_as_str(rule.get("user_id")),
            account_id=_as_str(rule.get("account_id")),
            category_id=_as_str(rule.get("category_id")),
            flow_type=rule.get("flow_type", "outcome"),  # type: ignore
            amount=_as_float(rule.get("amount")),
            description=_as_str(rule.get("description")),
            paired_recurring_transaction_id=_as_str(rule.get("paired_recurring_transaction_id")) if rule.get("paired_recurring_transaction_id") else None,
            frequency=rule.get("frequency", "monthly"),  # type: ignore
            interval=_as_int(rule.get("interval")),
            by_weekday=rule.get("by_weekday"),
            by_monthday=rule.get("by_monthday"),
            start_date=_as_str(rule.get("start_date")),
            next_run_date=_as_str(rule.get("next_run_date")),
            end_date=_as_str(rule.get("end_date")) if rule.get("end_date") else None,
            is_active=_as_bool(rule.get("is_active")),
            created_at=_as_str(rule.get("created_at")),
            updated_at=_as_str(rule.get("updated_at"))
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to fetch recurring transaction {recurring_transaction_id}: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={
                "error": "fetch_error",
                "details": "Failed to retrieve recurring transaction"
            }
        )


@router.patch(
    "/{recurring_transaction_id}",
    response_model=RecurringTransactionUpdateResponse,
    status_code=status.HTTP_200_OK,
    summary="Update recurring transaction rule",
    description="""
    Update recurring transaction rule details.
    
    This endpoint:
    - Accepts partial updates (only provided fields are updated)
    - Returns the complete updated rule
    - Special handling for start_date changes (apply_retroactive_change flag)
    - Special handling for is_active false → true transitions
    
    Security:
    - Only the rule owner can update their rule
    - RLS enforces user_id = auth.uid()
    """
)
async def update_existing_recurring_transaction(
    recurring_transaction_id: Annotated[str, Path(description="Recurring transaction UUID")],
    request: RecurringTransactionUpdateRequest,
    auth_user: Annotated[AuthenticatedUser, Depends(get_authenticated_user)]
) -> RecurringTransactionUpdateResponse:
    """Update recurring transaction rule details."""
    logger.info(f"Updating recurring transaction {recurring_transaction_id} for user {auth_user.user_id}")
    
    # Extract non-None updates (exclude apply_retroactive_change as it's not a DB field)
    updates = request.model_dump(exclude_none=True, exclude={"apply_retroactive_change"})
    
    if not updates:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={
                "error": "invalid_request",
                "details": "At least one field must be provided for update"
            }
        )
    
    supabase_client = get_supabase_client(auth_user.access_token)
    
    try:
        updated_rule, retroactive_deletes = await update_recurring_transaction(
            supabase_client=supabase_client,
            user_id=auth_user.user_id,
            recurring_transaction_id=recurring_transaction_id,
            apply_retroactive_change=request.apply_retroactive_change,
            **updates
        )
        
        if not updated_rule:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail={
                    "error": "not_found",
                    "details": "Recurring transaction not found"
                }
            )
        
        # Helper to coerce DB values
        def _as_str(v: Any) -> str:
            return str(v) if v is not None else ""
        
        def _as_float(v: Any) -> float:
            try:
                return float(v) if v is not None else 0.0
            except (ValueError, TypeError):
                return 0.0
        
        def _as_int(v: Any) -> int:
            try:
                return int(v) if v is not None else 1
            except (ValueError, TypeError):
                return 1
        
        def _as_bool(v: Any) -> bool:
            return bool(v) if v is not None else True
        
        rule_response = RecurringTransactionResponse(
            id=_as_str(updated_rule.get("id")),
            user_id=_as_str(updated_rule.get("user_id")),
            account_id=_as_str(updated_rule.get("account_id")),
            category_id=_as_str(updated_rule.get("category_id")),
            flow_type=updated_rule.get("flow_type", "outcome"),  # type: ignore
            amount=_as_float(updated_rule.get("amount")),
            description=_as_str(updated_rule.get("description")),
            paired_recurring_transaction_id=_as_str(updated_rule.get("paired_recurring_transaction_id")) if updated_rule.get("paired_recurring_transaction_id") else None,
            frequency=updated_rule.get("frequency", "monthly"),  # type: ignore
            interval=_as_int(updated_rule.get("interval")),
            by_weekday=updated_rule.get("by_weekday"),
            by_monthday=updated_rule.get("by_monthday"),
            start_date=_as_str(updated_rule.get("start_date")),
            next_run_date=_as_str(updated_rule.get("next_run_date")),
            end_date=_as_str(updated_rule.get("end_date")) if updated_rule.get("end_date") else None,
            is_active=_as_bool(updated_rule.get("is_active")),
            created_at=_as_str(updated_rule.get("created_at")),
            updated_at=_as_str(updated_rule.get("updated_at"))
        )
        
        logger.info(f"Recurring transaction {recurring_transaction_id} updated successfully")
        
        return RecurringTransactionUpdateResponse(
            status="UPDATED",
            recurring_transaction=rule_response,
            retroactive_deletes=retroactive_deletes,
            message="Recurring transaction rule updated successfully"
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to update recurring transaction {recurring_transaction_id}: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={
                "error": "update_error",
                "details": "Failed to update recurring transaction"
            }
        )


@router.delete(
    "/{recurring_transaction_id}",
    response_model=RecurringTransactionDeleteResponse,
    status_code=status.HTTP_200_OK,
    summary="Delete recurring transaction rule",
    description="""
    Delete a recurring transaction rule following DB deletion rules.
    
    This endpoint:
    - Deletes the recurring rule
    - If rule has a paired_recurring_transaction_id, deletes that rule too
    - Does NOT delete past generated transactions (they remain as history)
    
    Security:
    - Requires valid Authorization Bearer token
    - Only the rule owner can delete their rule
    
    DB Rules:
    1. Record can be deleted without touching past transactions
    2. If paired rule exists, it must be deleted together
    3. Future auto-generation stops but existing records preserved
    """
)
async def delete_existing_recurring_transaction(
    recurring_transaction_id: Annotated[str, Path(description="Recurring transaction UUID to delete")],
    auth_user: Annotated[AuthenticatedUser, Depends(get_authenticated_user)]
) -> RecurringTransactionDeleteResponse:
    """Delete recurring transaction rule following DB delete rules."""
    logger.info(f"Deleting recurring transaction {recurring_transaction_id} for user {auth_user.user_id}")
    
    supabase_client = get_supabase_client(auth_user.access_token)
    
    try:
        success, paired_rule_deleted = await delete_recurring_transaction(
            supabase_client=supabase_client,
            user_id=auth_user.user_id,
            recurring_transaction_id=recurring_transaction_id
        )
        
        if not success:
            logger.warning(f"Recurring transaction {recurring_transaction_id} not found or not accessible")
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail={
                    "error": "not_found",
                    "details": f"Recurring transaction {recurring_transaction_id} not found or not accessible"
                }
            )
        
        message = "Recurring transaction rule deleted successfully."
        if paired_rule_deleted:
            message += " Paired rule was also deleted."
        
        logger.info(
            f"Recurring transaction {recurring_transaction_id} deleted successfully. "
            f"Paired rule deleted: {paired_rule_deleted}"
        )
        
        return RecurringTransactionDeleteResponse(
            status="DELETED",
            recurring_transaction_id=str(recurring_transaction_id),
            paired_rule_deleted=paired_rule_deleted,
            message=message
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to delete recurring transaction {recurring_transaction_id}: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={
                "error": "delete_error",
                "details": "Failed to delete recurring transaction"
            }
        )


# Sync endpoint (separate router for transactions)
sync_router = APIRouter(prefix="/transactions", tags=["transactions", "recurring-sync"])


@sync_router.post(
    "/sync-recurring",
    response_model=SyncRecurringTransactionsResponse,
    status_code=status.HTTP_200_OK,
    summary="Synchronize recurring transactions",
    description="""
    Synchronize and generate pending transactions from recurring rules.
    
    This endpoint is designed to be called ONCE from the splash screen on app launch.
    It handles everything atomically in a single database transaction:
    
    **What it does:**
    - Generates all pending transactions up to today
    - Links paired recurring transfers via paired_transaction_id
    - Updates account cached_balance for all affected accounts
    - Updates budget cached_consumption for outcome transactions only
    
    **Efficiency:**
    - Single API call replaces multiple separate calls
    - Batch updates: one recompute per affected account/budget
    - Transfers don't affect budget consumption (correct behavior)
    
    **Best Practice:**
    - Call from splash screen on app launch
    - Throttle to max 1 call per 5 minutes
    - Force sync on pull-to-refresh or after 24h background
    
    Security:
    - Requires valid Authorization Bearer token
    - Only generates transactions for the authenticated user
    """
)
async def sync_recurring_transactions_endpoint(
    request: SyncRecurringTransactionsRequest,
    auth_user: Annotated[AuthenticatedUser, Depends(get_authenticated_user)]
) -> SyncRecurringTransactionsResponse:
    """Synchronize recurring transactions."""
    logger.info(f"Syncing recurring transactions for user {auth_user.user_id}")
    
    supabase_client = get_supabase_client(auth_user.access_token)
    
    try:
        transactions_generated, rules_processed, accounts_updated, budgets_updated = await sync_recurring_transactions(
            supabase_client=supabase_client,
            user_id=auth_user.user_id
        )
        
        logger.info(
            f"Sync complete for user {auth_user.user_id}: "
            f"{transactions_generated} transactions from {rules_processed} rules, "
            f"{accounts_updated} accounts, {budgets_updated} budgets updated"
        )
        
        return SyncRecurringTransactionsResponse(
            status="SYNCED",
            transactions_generated=transactions_generated,
            rules_processed=rules_processed,
            accounts_updated=accounts_updated,
            budgets_updated=budgets_updated,
            message=f"Generated {transactions_generated} transactions from {rules_processed} recurring rules. Updated {accounts_updated} accounts and {budgets_updated} budgets."
        )
        
    except Exception as e:
        logger.error(f"Failed to sync recurring transactions: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={
                "error": "sync_error",
                "details": "Failed to synchronize recurring transactions"
            }
        )
