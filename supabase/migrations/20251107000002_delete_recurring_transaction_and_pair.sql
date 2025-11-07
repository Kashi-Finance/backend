-- Migration: create RPC to delete a recurring_transaction and its paired rule atomically
-- Returns success boolean and whether paired rule was deleted
CREATE OR REPLACE FUNCTION app.delete_recurring_and_pair(p_recurring_id uuid, p_user_id uuid)
RETURNS TABLE(success boolean, paired_deleted boolean)
LANGUAGE plpgsql
SECURITY DEFINER
AS $$
DECLARE
  v_paired uuid;
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
    RETURN QUERY SELECT false, false;
  END IF;

  paired_deleted := false;

  -- If there's a paired rule, attempt to delete it as well (must belong to same user)
  IF v_paired IS NOT NULL THEN
    DELETE FROM recurring_transaction
    WHERE id = v_paired AND user_id = p_user_id;
    IF FOUND THEN
      paired_deleted := true;
    ELSE
      -- paired rule not deleted (might not belong to user) - log by raising a NOTICE
      RAISE NOTICE 'Paired recurring transaction % not deleted (not found or different owner)', v_paired;
    END IF;
  END IF;

  success := true;
  RETURN NEXT;
END;
$$;
