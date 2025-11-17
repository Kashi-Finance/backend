-- Migration: Update delete_account_cascade RPC to soft-delete all related data
-- Purpose: Soft-delete recurring templates, transactions, and account (preserves audit trail)
-- Date: 2025-11-15 (Updated to soft-delete strategy)

-- Drop old version
DROP FUNCTION IF EXISTS delete_account_cascade(UUID, UUID);

-- Create updated version that soft-deletes instead of physical delete
CREATE OR REPLACE FUNCTION delete_account_cascade(
    p_account_id UUID,
    p_user_id UUID
)
RETURNS TABLE(
    recurring_transactions_soft_deleted INT,
    recurring_paired_references_cleared INT,
    transactions_soft_deleted INT,
    transaction_paired_references_cleared INT,
    account_soft_deleted BOOLEAN,
    deleted_at TIMESTAMPTZ
)
LANGUAGE plpgsql
SECURITY DEFINER
AS $$
DECLARE
    v_recurring_ids UUID[];
    v_recurring_count INT := 0;
    v_recurring_paired_count INT := 0;
    v_txn_ids UUID[];
    v_txn_count INT := 0;
    v_txn_paired_count INT := 0;
    v_deleted_at TIMESTAMPTZ;
BEGIN
    -- Validate account exists and belongs to user
    IF NOT EXISTS (
        SELECT 1 FROM account 
        WHERE id = p_account_id AND user_id = p_user_id AND deleted_at IS NULL
    ) THEN
        RAISE EXCEPTION 'Account not found, already deleted, or not accessible';
    END IF;
    
    v_deleted_at := now();
    
    -- Step 1: Collect all recurring_transaction IDs for this account
    SELECT ARRAY_AGG(id) INTO v_recurring_ids
    FROM recurring_transaction
    WHERE account_id = p_account_id AND user_id = p_user_id AND deleted_at IS NULL;
    
    -- Count recurring transactions
    v_recurring_count := COALESCE(array_length(v_recurring_ids, 1), 0);
    
    -- Step 2: Clear paired_recurring_transaction_id references
    IF v_recurring_count > 0 THEN
        UPDATE recurring_transaction
        SET paired_recurring_transaction_id = NULL,
            updated_at = v_deleted_at
        WHERE paired_recurring_transaction_id = ANY(v_recurring_ids)
          AND deleted_at IS NULL;
        
        GET DIAGNOSTICS v_recurring_paired_count = ROW_COUNT;
    END IF;
    
    -- Step 3: SOFT-DELETE all recurring_transaction rows for this account
    UPDATE recurring_transaction
    SET deleted_at = v_deleted_at,
        updated_at = v_deleted_at
    WHERE account_id = p_account_id AND user_id = p_user_id AND deleted_at IS NULL;
    
    -- Step 4: Collect all transaction IDs for this account
    SELECT ARRAY_AGG(id) INTO v_txn_ids
    FROM "transaction"
    WHERE account_id = p_account_id AND user_id = p_user_id AND deleted_at IS NULL;
    
    -- Count transactions
    v_txn_count := COALESCE(array_length(v_txn_ids, 1), 0);
    
    -- Step 5: Clear paired_transaction_id references
    IF v_txn_count > 0 THEN
        UPDATE "transaction"
        SET paired_transaction_id = NULL,
            updated_at = v_deleted_at
        WHERE paired_transaction_id = ANY(v_txn_ids)
          AND deleted_at IS NULL;
        
        GET DIAGNOSTICS v_txn_paired_count = ROW_COUNT;
    END IF;
    
    -- Step 6: SOFT-DELETE all transactions for this account
    UPDATE "transaction"
    SET deleted_at = v_deleted_at,
        updated_at = v_deleted_at
    WHERE account_id = p_account_id AND user_id = p_user_id AND deleted_at IS NULL;
    
    -- Step 7: SOFT-DELETE the account
    UPDATE account
    SET deleted_at = v_deleted_at,
        updated_at = v_deleted_at
    WHERE id = p_account_id AND user_id = p_user_id;
    
    IF NOT FOUND THEN
        RAISE EXCEPTION 'Failed to soft-delete account';
    END IF;
    
    -- Recompute cached_balance for this account (should be zeroed since all transactions are soft-deleted)
    PERFORM recompute_account_balance(p_account_id, p_user_id);
    
    -- Return results
    recurring_transactions_soft_deleted := v_recurring_count;
    recurring_paired_references_cleared := v_recurring_paired_count;
    transactions_soft_deleted := v_txn_count;
    transaction_paired_references_cleared := v_txn_paired_count;
    account_soft_deleted := TRUE;
    deleted_at := v_deleted_at;
    RETURN NEXT;
END;
$$;

GRANT EXECUTE ON FUNCTION delete_account_cascade(UUID, UUID) TO authenticated;

COMMENT ON FUNCTION delete_account_cascade IS 
'Atomically soft-deletes account and all related recurring_transaction and transaction rows, handling paired references.
This implements DB delete rule Option 2 (cascade) for accounts with soft-delete strategy.
Updated Nov 2025: Changed from physical DELETE to soft-delete (sets deleted_at timestamp on all affected rows).
Returns counts of recurring_transaction and transaction rows soft-deleted, paired references cleared, and deletion status.
Clears paired references before soft-deletion to prevent orphaned foreign keys.
All data is retained for audit/recovery and hidden by RLS (deleted_at IS NULL filter).';
