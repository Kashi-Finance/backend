"""
Account CRUD API endpoints.

Provides endpoints for managing user financial accounts (cash, bank, credit card, etc.).
Accounts track balances via transaction history and support two deletion strategies
per DB rules.
"""

import logging
from typing import Annotated, Any
from fastapi import APIRouter, Depends, HTTPException, status, Path, Body, Query

from backend.auth.dependencies import get_authenticated_user, AuthenticatedUser
from backend.db.client import get_supabase_client
from backend.services.account_service import (
    get_user_accounts,
    get_account_by_id,
    create_account,
    update_account,
    delete_account_with_reassignment,
    delete_account_with_transactions,
)
from backend.schemas.accounts import (
    AccountResponse,
    AccountCreateRequest,
    AccountCreateResponse,
    AccountUpdateRequest,
    AccountUpdateResponse,
    AccountDeleteRequest,
    AccountDeleteResponse,
    AccountListResponse,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/accounts", tags=["accounts"])


@router.get(
    "",
    response_model=AccountListResponse,
    status_code=status.HTTP_200_OK,
    summary="List user accounts",
    description="""
    Retrieve all accounts belonging to the authenticated user.
    
    This endpoint:
    - Returns all user's financial accounts
    - Ordered by creation date (newest first)
    - Only accessible to the account owner (RLS enforced)
    - Supports pagination via limit/offset
    
    Security:
    - Requires valid Authorization Bearer token
    - RLS ensures users only see their own accounts
    """
)
async def list_accounts(
    auth_user: Annotated[AuthenticatedUser, Depends(get_authenticated_user)],
    limit: int = Query(50, ge=1, le=100, description="Maximum number of accounts to return"),
    offset: int = Query(0, ge=0, description="Number of accounts to skip for pagination")
) -> AccountListResponse:
    """
    List all accounts for the authenticated user.
    
    **6-STEP ENDPOINT FLOW:**
    
    Auth
    - Handled by get_authenticated_user dependency
    
    Parse/Validate Request
    - Query parameters validated by FastAPI (limit, offset)
    
    Domain & Intent Filter
    - Simple list request, no filtering needed
    
    Call Service
    - Call get_user_accounts() service function with pagination
    
    Map Output -> ResponseModel
    - Convert accounts list to AccountListResponse
    
    Persistence
    - Read-only operation (no persistence needed)
    """
    logger.info(f"Listing accounts for user {auth_user.user_id} (limit={limit}, offset={offset})")
    
    supabase_client = get_supabase_client(auth_user.access_token)
    
    try:
        accounts = await get_user_accounts(
            supabase_client=supabase_client,
            user_id=auth_user.user_id,
            limit=limit,
            offset=offset
        )
        
        # Helper to coerce DB values to strings
        def _as_str(v: Any) -> str:
            return str(v) if v is not None else ""
        
        account_responses = [
            AccountResponse(
                id=_as_str(acc.get("id")),
                user_id=_as_str(acc.get("user_id")),
                name=_as_str(acc.get("name")),
                type=acc.get("type", "cash"),  # type: ignore
                currency=_as_str(acc.get("currency")),
                cached_balance=float(acc.get("cached_balance", 0)),
                created_at=_as_str(acc.get("created_at")),
                updated_at=_as_str(acc.get("updated_at")),
            )
            for acc in accounts
        ]
        
        logger.info(f"Returning {len(account_responses)} accounts for user {auth_user.user_id}")
        
        return AccountListResponse(
            accounts=account_responses,
            count=len(account_responses),
            limit=limit,
            offset=offset
        )
        
    except Exception as e:
        logger.error(f"Failed to list accounts for user {auth_user.user_id}: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={
                "error": "fetch_error",
                "details": "Failed to retrieve accounts from database"
            }
        )


@router.post(
    "",
    response_model=AccountCreateResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create account",
    description="""
    Create a new financial account.
    
    This endpoint:
    - Creates a new account (cash, bank, credit card, etc.)
    - Validates account type matches DB constraints
    - Returns the created account details
    
    Security:
    - Requires valid Authorization Bearer token
    - RLS ensures account is owned by authenticated user
    """
)
async def create_new_account(
    request: AccountCreateRequest,
    auth_user: Annotated[AuthenticatedUser, Depends(get_authenticated_user)]
) -> AccountCreateResponse:
    """
    Create a new account.
    
    **6-STEP ENDPOINT FLOW:**
    
    Step 1: Auth
    - Handled by get_authenticated_user dependency
    
    Step 2: Parse/Validate Request
    - FastAPI validates AccountCreateRequest automatically
    
    Step 3: Domain & Intent Filter
    - Validate account type is in allowed enum
    
    Step 4: Call Service
    - Call create_account() service function
    
    Step 5: Map Output -> ResponseModel
    - Convert created account to AccountCreateResponse
    
    Step 6: Persistence
    - Service layer handles database insert
    """
    logger.info(f"Creating account for user {auth_user.user_id}: {request.name}")
    
    supabase_client = get_supabase_client(auth_user.access_token)
    
    try:
        # Import transaction service for initial balance
        from backend.services.transaction_service import create_transaction
        from backend.utils.constants import SYSTEM_GENERATED_KEYS
        from datetime import datetime, timezone
        
        created_account = await create_account(
            supabase_client=supabase_client,
            user_id=auth_user.user_id,
            name=request.name,
            account_type=request.type,
            currency=request.currency
        )
        
        account_id = created_account.get("id")
        
        # Create initial balance transaction if provided
        if request.initial_balance is not None and request.initial_balance > 0:
            logger.info(
                f"Creating initial balance transaction: "
                f"account={account_id}, amount={request.initial_balance}"
            )
            
            # Fetch system category with key="initial_balance" and flow_type="income"
            # This is a system category (user_id=NULL) used for opening account balances
            category_response = supabase_client.from_("category").select("id").eq(
                "key", "initial_balance"
            ).eq(
                "flow_type", "income"
            ).is_(
                "user_id", "null"
            ).execute()
            
            if not category_response.data or len(category_response.data) == 0:
                logger.error("System category 'initial_balance' with flow_type='income' not found")
                raise HTTPException(
                    status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                    detail={
                        "error": "system_category_missing",
                        "details": "Required system category for initial balance not found. Please contact support."
                    }
                )
            
            category_dict = category_response.data[0]
            if not isinstance(category_dict, dict):
                logger.error(f"Unexpected category data type: {type(category_dict)}")
                raise HTTPException(
                    status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                    detail={
                        "error": "system_error",
                        "details": "Invalid system category data structure"
                    }
                )
            
            initial_balance_category_id = str(category_dict.get("id"))
            logger.debug(f"Using system category for initial balance: {initial_balance_category_id}")
            
            await create_transaction(
                supabase_client=supabase_client,
                user_id=auth_user.user_id,
                account_id=str(account_id),
                category_id=initial_balance_category_id,
                flow_type="income",  # Initial balance is income
                amount=request.initial_balance,
                date=datetime.now(timezone.utc).isoformat(),
                description="Initial balance",
                system_generated_key=SYSTEM_GENERATED_KEYS['INITIAL_BALANCE']
            )
            
            logger.info(f"Initial balance transaction created for account {account_id}")
            
            # CRITICAL FIX: Re-fetch account to get updated cached_balance
            # The create_transaction service now calls recompute_account_balance(),
            # but created_account dict is stale. We must fetch the fresh data.
            from backend.services.account_service import get_account_by_id
            updated_account = await get_account_by_id(
                supabase_client=supabase_client,
                user_id=auth_user.user_id,
                account_id=str(account_id)
            )
            
            if updated_account:
                created_account = updated_account
                logger.debug(f"Account re-fetched after initial balance: cached_balance={created_account.get('cached_balance')}")
        
        # Helper to coerce DB values to strings
        def _as_str(v: Any) -> str:
            return str(v) if v is not None else ""
        
        account_response = AccountResponse(
            id=_as_str(created_account.get("id")),
            user_id=_as_str(created_account.get("user_id")),
            name=_as_str(created_account.get("name")),
            type=created_account.get("type", "cash"),  # type: ignore
            currency=_as_str(created_account.get("currency")),
            cached_balance=float(created_account.get("cached_balance", 0)),
            created_at=_as_str(created_account.get("created_at")),
            updated_at=_as_str(created_account.get("updated_at")),
        )
        
        logger.info(f"Account created successfully: {account_response.id}")
        
        return AccountCreateResponse(
            status="CREATED",
            account=account_response,
            message="Account created successfully"
        )
        
    except Exception as e:
        logger.error(f"Failed to create account for user {auth_user.user_id}: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={
                "error": "create_error",
                "details": "Failed to create account"
            }
        )


@router.get(
    "/{account_id}",
    response_model=AccountResponse,
    status_code=status.HTTP_200_OK,
    summary="Get account details",
    description="""
    Retrieve details of a single account by ID.
    
    This endpoint:
    - Returns account details for the specified ID
    - Only accessible to the account owner (RLS enforced)
    
    Security:
    - Requires valid Authorization Bearer token
    - Returns 404 if account doesn't exist or belongs to another user
    """
)
async def get_account(
    account_id: Annotated[str, Path(description="Account UUID")],
    auth_user: Annotated[AuthenticatedUser, Depends(get_authenticated_user)]
) -> AccountResponse:
    """Get account by ID."""
    logger.info(f"Fetching account {account_id} for user {auth_user.user_id}")
    
    supabase_client = get_supabase_client(auth_user.access_token)
    
    try:
        account = await get_account_by_id(
            supabase_client=supabase_client,
            user_id=auth_user.user_id,
            account_id=account_id
        )
        
        if not account:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail={
                    "error": "not_found",
                    "details": "Account not found"
                }
            )
        
        # Helper to coerce DB values to strings
        def _as_str(v: Any) -> str:
            return str(v) if v is not None else ""
        
        return AccountResponse(
            id=_as_str(account.get("id")),
            user_id=_as_str(account.get("user_id")),
            name=_as_str(account.get("name")),
            type=account.get("type", "cash"),  # type: ignore
            currency=_as_str(account.get("currency")),
            cached_balance=float(account.get("cached_balance", 0)),
            created_at=_as_str(account.get("created_at")),
            updated_at=_as_str(account.get("updated_at")),
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to fetch account {account_id}: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={
                "error": "fetch_error",
                "details": "Failed to retrieve account"
            }
        )


@router.patch(
    "/{account_id}",
    response_model=AccountUpdateResponse,
    status_code=status.HTTP_200_OK,
    summary="Update account",
    description="""
    Update account details.
    
    This endpoint:
    - Accepts partial updates (only provided fields are updated)
    - Returns the complete updated account
    - Requires valid Authorization Bearer token
    
    Security:
    - Only the account owner can update their account
    - RLS enforces user_id = auth.uid()
    """
)
async def update_existing_account(
    account_id: Annotated[str, Path(description="Account UUID")],
    request: AccountUpdateRequest,
    auth_user: Annotated[AuthenticatedUser, Depends(get_authenticated_user)]
) -> AccountUpdateResponse:
    """Update account details."""
    logger.info(f"Updating account {account_id} for user {auth_user.user_id}")
    
    # Extract non-None updates
    updates = request.model_dump(exclude_none=True)
    
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
        updated_account = await update_account(
            supabase_client=supabase_client,
            user_id=auth_user.user_id,
            account_id=account_id,
            **updates
        )
        
        if not updated_account:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail={
                    "error": "not_found",
                    "details": "Account not found"
                }
            )
        
        # Helper to coerce DB values to strings
        def _as_str(v: Any) -> str:
            return str(v) if v is not None else ""
        
        account_response = AccountResponse(
            id=_as_str(updated_account.get("id")),
            user_id=_as_str(updated_account.get("user_id")),
            name=_as_str(updated_account.get("name")),
            type=updated_account.get("type", "cash"),  # type: ignore
            currency=_as_str(updated_account.get("currency")),
            cached_balance=float(updated_account.get("cached_balance", 0)),
            created_at=_as_str(updated_account.get("created_at")),
            updated_at=_as_str(updated_account.get("updated_at")),
        )
        
        logger.info(f"Account {account_id} updated successfully")
        
        return AccountUpdateResponse(
            status="UPDATED",
            account=account_response,
            message="Account updated successfully"
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to update account {account_id}: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={
                "error": "update_error",
                "details": "Failed to update account"
            }
        )


@router.delete(
    "/{account_id}",
    response_model=AccountDeleteResponse,
    status_code=status.HTTP_200_OK,
    summary="Delete account",
    description="""
    Delete an account using one of two strategies per DB delete rule.
    
    **Strategy 1: 'reassign'**
    - Reassigns all transactions to another account (target_account_id required)
    - Then deletes the account
    
    **Strategy 2: 'delete_transactions'**
    - Deletes all transactions for this account
    - Handles paired transfers (clears references)
    - Then deletes the account
    
    Security:
    - Requires valid Authorization Bearer token
    - Only the account owner can delete their account
    - Target account (if strategy='reassign') must belong to same user
    """
)
async def delete_existing_account(
    account_id: Annotated[str, Path(description="Account UUID to delete")],
    request: Annotated[AccountDeleteRequest, Body()],
    auth_user: Annotated[AuthenticatedUser, Depends(get_authenticated_user)]
) -> AccountDeleteResponse:
    """Delete account following DB delete rules."""
    logger.info(
        f"Deleting account {account_id} for user {auth_user.user_id} "
        f"with strategy '{request.strategy}'"
    )
    
    # Validate strategy requirements. We use a consistent request envelope where
    # `target_account_id` is always present in the body. For `delete_transactions`
    # this field must be explicitly null; for `reassign` it must be a non-null UUID.
    if request.strategy == "reassign":
        if not request.target_account_id:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail={
                    "error": "invalid_request",
                    "details": "target_account_id is required when strategy='reassign'"
                }
            )
    elif request.strategy == "delete_transactions":
        if request.target_account_id is not None:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail={
                    "error": "invalid_request",
                    "details": "target_account_id must be null when strategy='delete_transactions'"
                }
            )
    
    supabase_client = get_supabase_client(auth_user.access_token)
    
    try:
        if request.strategy == "reassign":
            transactions_affected = await delete_account_with_reassignment(
                supabase_client=supabase_client,
                user_id=auth_user.user_id,
                account_id=account_id,
                target_account_id=request.target_account_id  # type: ignore
            )
            message = f"Account soft-deleted successfully. {transactions_affected} transactions reassigned."
        else:  # delete_transactions
            recurring_count, transaction_count = await delete_account_with_transactions(
                supabase_client=supabase_client,
                user_id=auth_user.user_id,
                account_id=account_id
            )
            transactions_affected = transaction_count
            message = (
                f"Account soft-deleted successfully. "
                f"{recurring_count} recurring templates and {transaction_count} transactions soft-deleted."
            )
        
        logger.info(
            f"Account {account_id} soft-deleted successfully. "
            f"{transactions_affected} transactions affected."
        )
        
        return AccountDeleteResponse(
            status="DELETED",
            message=message,
            transactions_affected=transactions_affected
        )
        
    except ValueError as e:
        logger.error(f"Invalid delete request: {e}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={
                "error": "invalid_request",
                "details": str(e)
            }
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to delete account {account_id}: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={
                "error": "delete_error",
                "details": "Failed to delete account"
            }
        )
