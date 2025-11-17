-- Migration: Update delete_account_reassign RPC to reassign and soft-delete
-- Purpose: Reassign all transactions/recurring templates to target account, then SOFT-DELETE source account
-- Date: 2025-11-15 (Updated to soft-delete strategy)

-- Drop old version
DROP FUNCTION IF EXISTS delete_account_reassign(UUID, UUID, UUID);

-- Create updated version that soft-deletes instead of physical delete
CREATE OR REPLACE FUNCTION delete_account_reassign(
    p_account_id UUID,
    p_user_id UUID,
    p_target_account_id UUID
)
RETURNS TABLE(
    recurring_transactions_reassigned INT,
    transactions_reassigned INT,
    account_soft_deleted BOOLEAN,
    deleted_at TIMESTAMPTZ
)
LANGUAGE plpgsql
SECURITY DEFINER
AS $$
DECLARE
    v_recurring_count INT := 0;
    v_txn_count INT := 0;
    v_deleted_at TIMESTAMPTZ;
BEGIN
    -- Validate source account exists and belongs to user
    IF NOT EXISTS (
        SELECT 1 FROM account 
        WHERE id = p_account_id AND user_id = p_user_id AND deleted_at IS NULL
    ) THEN
        RAISE EXCEPTION 'Source account not found, already deleted, or not accessible';
    END IF;
    
    -- Validate target account exists and belongs to user
    IF NOT EXISTS (
        SELECT 1 FROM account 
        WHERE id = p_target_account_id AND user_id = p_user_id AND deleted_at IS NULL
    ) THEN
        RAISE EXCEPTION 'Target account not found, already deleted, or not accessible';
    END IF;
    
    -- Prevent self-reassignment
    IF p_account_id = p_target_account_id THEN
        RAISE EXCEPTION 'Cannot reassign to the same account';
    END IF;
    
    -- Step 1: Reassign all recurring_transaction rows from source to target account
    -- This must happen BEFORE transaction reassignment due to FK constraint
    UPDATE recurring_transaction
    SET account_id = p_target_account_id,
        updated_at = now()
    WHERE account_id = p_account_id AND user_id = p_user_id AND deleted_at IS NULL;
    
    GET DIAGNOSTICS v_recurring_count = ROW_COUNT;
    
    -- Step 2: Reassign all transactions from source to target account
    UPDATE "transaction"
    SET account_id = p_target_account_id,
        updated_at = now()
    WHERE account_id = p_account_id AND user_id = p_user_id AND deleted_at IS NULL;
    
    GET DIAGNOSTICS v_txn_count = ROW_COUNT;
    
    -- Step 3: SOFT-DELETE the source account (set deleted_at timestamp)
    v_deleted_at := now();
    
    UPDATE account
    SET deleted_at = v_deleted_at,
        updated_at = v_deleted_at
    WHERE id = p_account_id AND user_id = p_user_id;
    
    IF NOT FOUND THEN
        RAISE EXCEPTION 'Failed to soft-delete account';
    END IF;
    
    -- Recompute cached_balance for target account (reflects reassigned transactions)
    PERFORM recompute_account_balance(p_target_account_id, p_user_id);
    
    -- Return results
    recurring_transactions_reassigned := v_recurring_count;
    transactions_reassigned := v_txn_count;
    account_soft_deleted := TRUE;
    deleted_at := v_deleted_at;
    RETURN NEXT;
END;
$$;

GRANT EXECUTE ON FUNCTION delete_account_reassign(UUID, UUID, UUID) TO authenticated;

COMMENT ON FUNCTION delete_account_reassign IS 
'Atomically reassigns all recurring_transaction and transaction rows from source account to target account, then SOFT-DELETES source account.
This implements DB delete rule Option 1 (reassign) for accounts with soft-delete strategy.
Updated Nov 2025: Changed from physical DELETE to soft-delete (sets deleted_at timestamp).
Returns counts of recurring_transaction and transaction rows reassigned, plus soft-deletion status and timestamp.
Validates both accounts belong to the user and prevents self-reassignment.
After reassignment, source account is marked deleted_at and hidden by RLS, but data is retained for audit/recovery.';
