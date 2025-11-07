-- Migration: Create RPC function for atomic account deletion with transaction reassignment
-- Purpose: Reassign all transactions to target account and delete source account atomically
-- Date: 2025-11-07

CREATE OR REPLACE FUNCTION delete_account_reassign(
    p_account_id UUID,
    p_user_id UUID,
    p_target_account_id UUID
)
RETURNS TABLE(
    transactions_reassigned INT,
    account_deleted BOOLEAN
)
LANGUAGE plpgsql
SECURITY DEFINER
AS $$
DECLARE
    v_txn_count INT := 0;
BEGIN
    -- Validate source account exists and belongs to user
    IF NOT EXISTS (
        SELECT 1 FROM account 
        WHERE id = p_account_id AND user_id = p_user_id
    ) THEN
        RAISE EXCEPTION 'Source account not found or not accessible';
    END IF;
    
    -- Validate target account exists and belongs to user
    IF NOT EXISTS (
        SELECT 1 FROM account 
        WHERE id = p_target_account_id AND user_id = p_user_id
    ) THEN
        RAISE EXCEPTION 'Target account not found or not accessible';
    END IF;
    
    -- Prevent self-reassignment
    IF p_account_id = p_target_account_id THEN
        RAISE EXCEPTION 'Cannot reassign transactions to the same account';
    END IF;
    
    -- Reassign all transactions from source to target account
    UPDATE "transaction"
    SET account_id = p_target_account_id
    WHERE account_id = p_account_id AND user_id = p_user_id;
    
    GET DIAGNOSTICS v_txn_count = ROW_COUNT;
    
    -- Delete the source account
    DELETE FROM account
    WHERE id = p_account_id AND user_id = p_user_id;
    
    IF NOT FOUND THEN
        RAISE EXCEPTION 'Failed to delete account';
    END IF;
    
    -- Return results
    transactions_reassigned := v_txn_count;
    account_deleted := TRUE;
    RETURN NEXT;
END;
$$;

GRANT EXECUTE ON FUNCTION delete_account_reassign(UUID, UUID, UUID) TO authenticated;

COMMENT ON FUNCTION delete_account_reassign IS 
'Atomically reassigns all transactions from source account to target account, then deletes source account.
This implements DB delete rule Option 1 for accounts.
This function must be called via Supabase RPC from the backend.
Returns count of transactions reassigned and deletion status.
Validates both accounts belong to the user and prevents self-reassignment.';
