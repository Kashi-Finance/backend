-- Migration: Create RPC function for atomic account deletion with transaction cascade
-- Purpose: Delete account and all related transactions, handling paired transfer references
-- Date: 2025-11-07

CREATE OR REPLACE FUNCTION delete_account_cascade(
    p_account_id UUID,
    p_user_id UUID
)
RETURNS TABLE(
    transactions_deleted INT,
    paired_references_cleared INT,
    account_deleted BOOLEAN
)
LANGUAGE plpgsql
SECURITY DEFINER
AS $$
DECLARE
    v_txn_ids UUID[];
    v_txn_count INT := 0;
    v_paired_count INT := 0;
BEGIN
    -- Validate account exists and belongs to user
    IF NOT EXISTS (
        SELECT 1 FROM account 
        WHERE id = p_account_id AND user_id = p_user_id
    ) THEN
        RAISE EXCEPTION 'Account not found or not accessible';
    END IF;
    
    -- Step 1: Collect all transaction IDs for this account
    SELECT ARRAY_AGG(id) INTO v_txn_ids
    FROM "transaction"
    WHERE account_id = p_account_id AND user_id = p_user_id;
    
    -- Count transactions
    v_txn_count := COALESCE(array_length(v_txn_ids, 1), 0);
    
    -- Step 2: Clear paired_transaction_id for transactions that reference our transactions
    -- This prevents foreign key violations when we delete our transactions
    IF v_txn_count > 0 THEN
        UPDATE "transaction"
        SET paired_transaction_id = NULL
        WHERE paired_transaction_id = ANY(v_txn_ids);
        
        GET DIAGNOSTICS v_paired_count = ROW_COUNT;
    END IF;
    
    -- Step 3: Delete all transactions for this account
    DELETE FROM "transaction"
    WHERE account_id = p_account_id AND user_id = p_user_id;
    
    -- Step 4: Delete the account
    DELETE FROM account
    WHERE id = p_account_id AND user_id = p_user_id;
    
    IF NOT FOUND THEN
        RAISE EXCEPTION 'Failed to delete account';
    END IF;
    
    -- Return results
    transactions_deleted := v_txn_count;
    paired_references_cleared := v_paired_count;
    account_deleted := TRUE;
    RETURN NEXT;
END;
$$;

GRANT EXECUTE ON FUNCTION delete_account_cascade(UUID, UUID) TO authenticated;

COMMENT ON FUNCTION delete_account_cascade IS 
'Atomically deletes account and all related transactions, properly handling paired transfer references.
This implements DB delete rule Option 2 for accounts.
This function must be called via Supabase RPC from the backend.
Returns counts of transactions deleted, paired references cleared, and deletion status.
Clears paired_transaction_id references to prevent orphaned foreign keys.';
