-- Migration: Create RPC function for atomic recurring transfer creation
-- Purpose: Create two paired recurring_transaction rules atomically
-- Date: 2025-11-07

CREATE OR REPLACE FUNCTION create_recurring_transfer(
    p_user_id UUID,
    p_from_account_id UUID,
    p_to_account_id UUID,
    p_amount NUMERIC(12,2),
    p_description_outgoing TEXT,
    p_description_incoming TEXT,
    p_frequency TEXT,
    p_interval INT,
    p_start_date DATE,
    p_by_weekday TEXT[],
    p_by_monthday INT[],
    p_end_date DATE,
    p_is_active BOOLEAN,
    p_transfer_category_id UUID
)
RETURNS TABLE(
    outgoing_rule_id UUID,
    incoming_rule_id UUID
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
    
    -- Validate frequency
    IF p_frequency NOT IN ('daily', 'weekly', 'monthly', 'yearly') THEN
        RAISE EXCEPTION 'Invalid frequency. Must be daily, weekly, monthly, or yearly';
    END IF;
    
    -- Step 1: Create outgoing recurring rule (outcome from source)
    INSERT INTO recurring_transaction (
        user_id,
        account_id,
        category_id,
        flow_type,
        amount,
        description,
        frequency,
        interval,
        start_date,
        next_run_date,
        by_weekday,
        by_monthday,
        end_date,
        is_active
    ) VALUES (
        p_user_id,
        p_from_account_id,
        p_transfer_category_id,
        'outcome',
        p_amount,
        p_description_outgoing,
        p_frequency,
        p_interval,
        p_start_date,
        p_start_date,  -- next_run_date starts at start_date
        p_by_weekday,
        p_by_monthday,
        p_end_date,
        p_is_active
    ) RETURNING id INTO v_outgoing_id;
    
    -- Step 2: Create incoming recurring rule (income to destination)
    -- Link to outgoing rule immediately
    INSERT INTO recurring_transaction (
        user_id,
        account_id,
        category_id,
        flow_type,
        amount,
        description,
        frequency,
        interval,
        start_date,
        next_run_date,
        by_weekday,
        by_monthday,
        end_date,
        is_active,
        paired_recurring_transaction_id
    ) VALUES (
        p_user_id,
        p_to_account_id,
        p_transfer_category_id,
        'income',
        p_amount,
        p_description_incoming,
        p_frequency,
        p_interval,
        p_start_date,
        p_start_date,
        p_by_weekday,
        p_by_monthday,
        p_end_date,
        p_is_active,
        v_outgoing_id
    ) RETURNING id INTO v_incoming_id;
    
    -- Step 3: Update outgoing rule to link back to incoming
    UPDATE recurring_transaction
    SET paired_recurring_transaction_id = v_incoming_id
    WHERE id = v_outgoing_id;
    
    -- Return both IDs
    outgoing_rule_id := v_outgoing_id;
    incoming_rule_id := v_incoming_id;
    RETURN NEXT;
END;
$$;

GRANT EXECUTE ON FUNCTION create_recurring_transfer(
    UUID, UUID, UUID, NUMERIC(12,2), TEXT, TEXT, TEXT, INT, DATE, TEXT[], INT[], DATE, BOOLEAN, UUID
) TO authenticated;

COMMENT ON FUNCTION create_recurring_transfer IS 
'Atomically creates a paired recurring transfer (two recurring rules: outcome from source, income to destination).
This function must be called via Supabase RPC from the backend.
Returns IDs of both created recurring rules.
All operations succeed or fail together (true atomicity).
Supports all frequency types (daily, weekly, monthly, yearly) with optional by_weekday and by_monthday constraints.';
