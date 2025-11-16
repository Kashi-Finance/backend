-- Migration: Create delete_transaction RPC
-- Purpose: Soft-delete transaction by setting deleted_at
-- Date: 2025-11-15

CREATE OR REPLACE FUNCTION delete_transaction(
    p_transaction_id UUID,
    p_user_id UUID
)
RETURNS TABLE(
    transaction_soft_deleted BOOLEAN,
    deleted_at TIMESTAMPTZ,
    paired_transaction_affected BOOLEAN
)
LANGUAGE plpgsql
SECURITY DEFINER
AS $$
DECLARE
    v_deleted_at TIMESTAMPTZ;
    v_paired_id UUID;
    v_paired_affected BOOLEAN := FALSE;
BEGIN
    -- Validate transaction exists and belongs to user
    IF NOT EXISTS (
        SELECT 1 FROM "transaction" 
        WHERE id = p_transaction_id AND user_id = p_user_id AND deleted_at IS NULL
    ) THEN
        RAISE EXCEPTION 'Transaction not found, already deleted, or not accessible';
    END IF;
    
    -- Check if this transaction is part of a paired transfer
    SELECT paired_transaction_id INTO v_paired_id
    FROM "transaction"
    WHERE id = p_transaction_id;
    
    -- Set deletion timestamp
    v_deleted_at := now();
    
    -- Soft-delete the transaction
    UPDATE "transaction"
    SET 
        deleted_at = v_deleted_at,
        updated_at = v_deleted_at
    WHERE id = p_transaction_id AND user_id = p_user_id;
    
    -- If part of a paired transfer, clear the paired_transaction_id on the partner
    IF v_paired_id IS NOT NULL THEN
        UPDATE "transaction"
        SET 
            paired_transaction_id = NULL,
            updated_at = v_deleted_at
        WHERE id = v_paired_id AND user_id = p_user_id;
        
        v_paired_affected := TRUE;
    END IF;
    
    -- TODO: Update account.cached_balance via trigger or separate call
    -- TODO: Update budget.cached_consumption if transaction affects active budget
    
    -- Return results
    transaction_soft_deleted := TRUE;
    deleted_at := v_deleted_at;
    paired_transaction_affected := v_paired_affected;
    RETURN NEXT;
END;
$$;

GRANT EXECUTE ON FUNCTION delete_transaction(UUID, UUID) TO authenticated;

COMMENT ON FUNCTION delete_transaction IS 
'Soft-deletes a transaction by setting deleted_at timestamp.
If the transaction is part of a paired transfer (paired_transaction_id set), clears the partner reference.
RLS policies hide soft-deleted transactions from users (deleted_at IS NULL filter).
IMPORTANT: Cached balances (account.cached_balance, budget.cached_consumption) should be updated separately.
To recover a soft-deleted transaction, set deleted_at = NULL via service_role.';
