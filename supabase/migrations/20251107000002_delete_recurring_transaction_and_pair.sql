-- Migration: Create delete_recurring_and_pair RPC
-- Purpose: Delete a recurring_transaction and its paired rule atomically
-- Date: 2025-11-07

CREATE OR REPLACE FUNCTION delete_recurring_and_pair(
    p_recurring_id UUID,
    p_user_id UUID
)
RETURNS TABLE(
    success BOOLEAN,
    paired_deleted BOOLEAN
)
LANGUAGE plpgsql
SECURITY DEFINER
AS $$
DECLARE
  v_paired UUID;
BEGIN
  -- Fetch paired id and ensure the rule exists and belongs to user
  SELECT paired_recurring_transaction_id INTO v_paired
  FROM recurring_transaction
  WHERE id = p_recurring_id AND user_id = p_user_id
  LIMIT 1;

  IF NOT FOUND THEN
    RAISE EXCEPTION 'recurring transaction not found or not owned by user';
  END IF;

  -- Delete main rule
  DELETE FROM recurring_transaction
  WHERE id = p_recurring_id AND user_id = p_user_id;

  IF NOT FOUND THEN
    success := FALSE;
    paired_deleted := FALSE;
    RETURN NEXT;
    RETURN;
  END IF;

  paired_deleted := FALSE;

  -- If there's a paired rule, attempt to delete it as well (must belong to same user)
  IF v_paired IS NOT NULL THEN
    DELETE FROM recurring_transaction
    WHERE id = v_paired AND user_id = p_user_id;
    IF FOUND THEN
      paired_deleted := TRUE;
    ELSE
      -- paired rule not deleted (might not belong to user) - log by raising a NOTICE
      RAISE NOTICE 'Paired recurring transaction % not deleted (not found or different owner)', v_paired;
    END IF;
  END IF;

  success := TRUE;
  RETURN NEXT;
END;
$$;

GRANT EXECUTE ON FUNCTION delete_recurring_and_pair(UUID, UUID) TO authenticated;

COMMENT ON FUNCTION delete_recurring_and_pair IS 
'Atomically deletes a recurring transaction and its paired rule (for recurring transfers).
This function must be called via Supabase RPC from the backend.
Returns success status and whether paired rule was deleted.';
