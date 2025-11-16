-- Migration: Create delete_recurring_transaction RPC
-- Purpose: Soft-delete recurring transaction template by setting deleted_at
-- Date: 2025-11-15

CREATE OR REPLACE FUNCTION delete_recurring_transaction(
    p_recurring_transaction_id UUID,
    p_user_id UUID,
    p_also_delete_pair BOOLEAN DEFAULT FALSE
)
RETURNS TABLE(
    recurring_transaction_soft_deleted BOOLEAN,
    deleted_at TIMESTAMPTZ,
    paired_template_also_deleted BOOLEAN
)
LANGUAGE plpgsql
SECURITY DEFINER
AS $$
DECLARE
    v_deleted_at TIMESTAMPTZ;
    v_paired_id UUID;
    v_paired_deleted BOOLEAN := FALSE;
BEGIN
    -- Validate recurring transaction exists and belongs to user
    IF NOT EXISTS (
        SELECT 1 FROM recurring_transaction 
        WHERE id = p_recurring_transaction_id AND user_id = p_user_id AND deleted_at IS NULL
    ) THEN
        RAISE EXCEPTION 'Recurring transaction not found, already deleted, or not accessible';
    END IF;
    
    -- Check if this template is part of a paired recurring transfer
    SELECT paired_recurring_transaction_id INTO v_paired_id
    FROM recurring_transaction
    WHERE id = p_recurring_transaction_id;
    
    -- Set deletion timestamp
    v_deleted_at := now();
    
    -- Soft-delete the recurring transaction template
    UPDATE recurring_transaction
    SET 
        deleted_at = v_deleted_at,
        updated_at = v_deleted_at,
        is_active = FALSE  -- Also deactivate to stop future materialization
    WHERE id = p_recurring_transaction_id AND user_id = p_user_id;
    
    -- If part of a paired recurring transfer AND user requested pair deletion
    IF v_paired_id IS NOT NULL AND p_also_delete_pair THEN
        UPDATE recurring_transaction
        SET 
            deleted_at = v_deleted_at,
            updated_at = v_deleted_at,
            is_active = FALSE
        WHERE id = v_paired_id AND user_id = p_user_id AND deleted_at IS NULL;
        
        v_paired_deleted := (FOUND);
    END IF;
    
    -- Return results
    recurring_transaction_soft_deleted := TRUE;
    deleted_at := v_deleted_at;
    paired_template_also_deleted := v_paired_deleted;
    RETURN NEXT;
END;
$$;

GRANT EXECUTE ON FUNCTION delete_recurring_transaction(UUID, UUID, BOOLEAN) TO authenticated;

COMMENT ON FUNCTION delete_recurring_transaction IS 
'Soft-deletes a recurring transaction template by setting deleted_at and is_active=FALSE.
Stops future materialization without affecting already-created transactions.
If p_also_delete_pair=TRUE and template is part of a recurring transfer, soft-deletes both sides.
RLS policies hide soft-deleted templates from users (deleted_at IS NULL filter).
Already-materialized transactions remain unchanged and visible (they have their own deleted_at).
To recover a soft-deleted template, set deleted_at = NULL and is_active = TRUE via service_role.';
