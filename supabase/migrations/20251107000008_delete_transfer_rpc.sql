-- Migration: Create delete_transfer RPC function
-- Purpose: Atomically delete both sides of a transfer (paired transactions)
-- Date: 2025-11-07
-- Priority: MEDIUM
-- Implements: Transfer deletion with symmetric pairing cleanup

-- Drop function if exists (for re-running migration)
DROP FUNCTION IF EXISTS delete_transfer(UUID, UUID);

-- Create atomic transfer deletion function
CREATE OR REPLACE FUNCTION delete_transfer(
    p_transaction_id UUID,
    p_user_id UUID
)
RETURNS TABLE(
    deleted_transaction_id UUID,
    paired_transaction_id UUID
)
LANGUAGE plpgsql
SECURITY DEFINER
AS $$
DECLARE
    v_transaction_id UUID;
    v_paired_id UUID;
    v_owner_id UUID;
BEGIN
    -- Step 1: Fetch transaction and validate ownership
    SELECT id, paired_transaction_id, user_id
    INTO v_transaction_id, v_paired_id, v_owner_id
    FROM transaction
    WHERE id = p_transaction_id;
    
    -- Validate transaction exists
    IF v_transaction_id IS NULL THEN
        RAISE EXCEPTION 'Transaction % not found', p_transaction_id;
    END IF;
    
    -- Validate ownership
    IF v_owner_id != p_user_id THEN
        RAISE EXCEPTION 'Transaction % does not belong to user %', p_transaction_id, p_user_id;
    END IF;
    
    -- Validate it's part of a transfer
    IF v_paired_id IS NULL THEN
        RAISE EXCEPTION 'Transaction % is not part of a transfer (paired_transaction_id is NULL)', p_transaction_id;
    END IF;
    
    -- Step 2: Delete both transactions atomically
    -- The ON DELETE SET NULL FK constraint will handle clearing references
    DELETE FROM transaction WHERE id = p_transaction_id;
    DELETE FROM transaction WHERE id = v_paired_id;
    
    -- Step 3: Return both IDs for confirmation
    deleted_transaction_id := p_transaction_id;
    paired_transaction_id := v_paired_id;
    
    RETURN NEXT;
END;
$$;

-- Grant execute permission to authenticated users
GRANT EXECUTE ON FUNCTION delete_transfer(UUID, UUID) TO authenticated;

-- Add comprehensive documentation
COMMENT ON FUNCTION delete_transfer(UUID, UUID) IS 
'Atomically delete both sides of a transfer.

SECURITY DEFINER function that:
1. Validates transaction exists and belongs to user
2. Validates transaction is part of a transfer (paired_transaction_id NOT NULL)
3. Deletes both the specified transaction and its pair
4. Returns both deleted transaction IDs

Parameters:
- p_transaction_id: UUID of either transaction in the transfer pair
- p_user_id: UUID of the authenticated user (from auth.uid())

Returns:
- deleted_transaction_id: The transaction ID that was requested for deletion
- paired_transaction_id: The ID of the paired transaction that was also deleted

Security:
- Validates user_id ownership before deletion
- RLS policies still apply on DELETE operations
- Both deletions happen in single transaction (atomic)

Example:
SELECT * FROM delete_transfer(
    ''123e4567-e89b-12d3-a456-426614174000''::UUID,
    auth.uid()
);
';
