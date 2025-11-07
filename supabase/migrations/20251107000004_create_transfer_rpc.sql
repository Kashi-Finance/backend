-- Migration: Create RPC function for atomic transfer creation
-- Purpose: Create two paired transactions (income/outcome) atomically
-- Date: 2025-11-07

CREATE OR REPLACE FUNCTION create_transfer(
    p_user_id UUID,
    p_from_account_id UUID,
    p_to_account_id UUID,
    p_amount NUMERIC(12,2),
    p_date DATE,
    p_description TEXT,
    p_transfer_category_id UUID
)
RETURNS TABLE(
    outgoing_transaction_id UUID,
    incoming_transaction_id UUID
)
LANGUAGE plpgsql
SECURITY DEFINER
AS $$
DECLARE
    v_outgoing_id UUID;
    v_incoming_id UUID;
BEGIN
    -- Validate both accounts belong to the user
    IF NOT EXISTS (
        SELECT 1 FROM account 
        WHERE id = p_from_account_id AND user_id = p_user_id
    ) THEN
        RAISE EXCEPTION 'Source account not found or not accessible';
    END IF;
    
    IF NOT EXISTS (
        SELECT 1 FROM account 
        WHERE id = p_to_account_id AND user_id = p_user_id
    ) THEN
        RAISE EXCEPTION 'Destination account not found or not accessible';
    END IF;
    
    -- Step 1: Create outgoing transaction (outcome from source)
    INSERT INTO "transaction" (
        user_id,
        account_id,
        category_id,
        flow_type,
        amount,
        date,
        description,
        source
    ) VALUES (
        p_user_id,
        p_from_account_id,
        p_transfer_category_id,
        'outcome',
        p_amount,
        p_date,
        p_description,
        'manual'
    ) RETURNING id INTO v_outgoing_id;
    
    -- Step 2: Create incoming transaction (income to destination)
    -- Link to outgoing transaction immediately
    INSERT INTO "transaction" (
        user_id,
        account_id,
        category_id,
        flow_type,
        amount,
        date,
        description,
        source,
        paired_transaction_id
    ) VALUES (
        p_user_id,
        p_to_account_id,
        p_transfer_category_id,
        'income',
        p_amount,
        p_date,
        p_description,
        'manual',
        v_outgoing_id
    ) RETURNING id INTO v_incoming_id;
    
    -- Step 3: Update outgoing transaction to link back to incoming
    UPDATE "transaction"
    SET paired_transaction_id = v_incoming_id
    WHERE id = v_outgoing_id;
    
    -- Return both IDs
    outgoing_transaction_id := v_outgoing_id;
    incoming_transaction_id := v_incoming_id;
    RETURN NEXT;
END;
$$;

GRANT EXECUTE ON FUNCTION create_transfer(UUID, UUID, UUID, NUMERIC(12,2), DATE, TEXT, UUID) TO authenticated;

COMMENT ON FUNCTION create_transfer IS 
'Atomically creates a paired transfer (two transactions: outcome from source, income to destination).
This function must be called via Supabase RPC from the backend.
Returns IDs of both created transactions.
All operations succeed or fail together (true atomicity).';
