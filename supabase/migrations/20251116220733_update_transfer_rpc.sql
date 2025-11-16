-- Migration: update_transfer RPC
-- Description: Allows atomic updates to both legs of a transfer
-- Date: 2025-11-16
-- Author: Backend Service

-- Purpose:
-- Transfers are two paired transactions that must stay synchronized.
-- This RPC updates both transactions atomically with the same values.

-- Allowed updates:
-- - amount (must be identical on both legs)
-- - date (must be identical on both legs)
-- - description (mirrored to both legs)

-- Disallowed updates:
-- - category_id (transfers must use system 'transfer' category)
-- - flow_type (outcome/income are fixed by design)
-- - paired_transaction_id (cannot be changed)
-- - account_id (would break the transfer structure)

CREATE OR REPLACE FUNCTION public.update_transfer(
    p_transaction_id uuid,
    p_user_id uuid,
    p_amount numeric DEFAULT NULL,
    p_date date DEFAULT NULL,
    p_description text DEFAULT NULL
)
RETURNS json
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = public
AS $$
DECLARE
    v_transaction record;
    v_paired_transaction record;
    v_result json;
BEGIN
    -- Fetch the transaction and verify it's a transfer
    SELECT * INTO v_transaction
    FROM public.transaction
    WHERE id = p_transaction_id
      AND user_id = p_user_id
      AND paired_transaction_id IS NOT NULL;
    
    IF NOT FOUND THEN
        RAISE EXCEPTION 'Transaction not found, not accessible, or not a transfer';
    END IF;
    
    -- Fetch the paired transaction
    SELECT * INTO v_paired_transaction
    FROM public.transaction
    WHERE id = v_transaction.paired_transaction_id
      AND user_id = p_user_id;
    
    IF NOT FOUND THEN
        RAISE EXCEPTION 'Paired transaction not found or not accessible';
    END IF;
    
    -- Update the original transaction (only provided fields)
    UPDATE public.transaction
    SET 
        amount = COALESCE(p_amount, amount),
        date = COALESCE(p_date, date),
        description = COALESCE(p_description, description),
        updated_at = now()
    WHERE id = p_transaction_id;
    
    -- Update the paired transaction with the same values
    UPDATE public.transaction
    SET 
        amount = COALESCE(p_amount, amount),
        date = COALESCE(p_date, date),
        description = COALESCE(p_description, description),
        updated_at = now()
    WHERE id = v_transaction.paired_transaction_id;
    
    -- Return both updated transaction IDs
    v_result := json_build_object(
        'updated_transaction_id', p_transaction_id,
        'updated_paired_transaction_id', v_transaction.paired_transaction_id
    );
    
    RETURN v_result;
END;
$$;

-- Grant execute permission to authenticated users
GRANT EXECUTE ON FUNCTION public.update_transfer(uuid, uuid, numeric, date, text) TO authenticated;

-- Add comment for documentation
COMMENT ON FUNCTION public.update_transfer IS 
'Updates both legs of a transfer atomically. Only amount, date, and description can be updated. Both transactions receive the same updates to maintain synchronization.';
