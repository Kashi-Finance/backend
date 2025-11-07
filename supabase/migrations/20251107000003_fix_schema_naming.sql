-- Migration: Fix schema naming for RPC functions
-- Purpose: Remove 'app' schema prefix, use default 'public' schema
-- Date: 2025-11-07

-- Drop old functions with app schema
DROP FUNCTION IF EXISTS app.delete_category_reassign(UUID, UUID);
DROP FUNCTION IF EXISTS app.delete_recurring_and_pair(UUID, UUID);

-- Recreate delete_category_reassign without schema prefix (defaults to public)
CREATE OR REPLACE FUNCTION delete_category_reassign(p_category_id uuid, p_user_id uuid)
RETURNS TABLE(transactions_reassigned int, budget_links_removed int)
LANGUAGE plpgsql
SECURITY DEFINER
AS $$
DECLARE
  v_general uuid;
  v_txn_count int := 0;
  v_links_count int := 0;
BEGIN
  SELECT id INTO v_general
  FROM category
  WHERE key = 'general' AND user_id IS NULL
  LIMIT 1;

  IF v_general IS NULL THEN
    RAISE EXCEPTION 'system general category not found';
  END IF;

  -- Reassign transactions to the general category
  UPDATE "transaction"
  SET category_id = v_general
  WHERE category_id = p_category_id;
  GET DIAGNOSTICS v_txn_count = ROW_COUNT;

  -- Remove budget_category links for this category
  DELETE FROM budget_category
  WHERE category_id = p_category_id;
  GET DIAGNOSTICS v_links_count = ROW_COUNT;

  -- Delete the category only if it belongs to the provided user_id
  DELETE FROM category
  WHERE id = p_category_id AND user_id = p_user_id;

  IF NOT FOUND THEN
    RAISE EXCEPTION 'category not found or not owned by user';
  END IF;

  -- Return counts
  transactions_reassigned := v_txn_count;
  budget_links_removed := v_links_count;
  RETURN NEXT;
END;
$$;

GRANT EXECUTE ON FUNCTION delete_category_reassign(UUID, UUID) TO authenticated;

COMMENT ON FUNCTION delete_category_reassign IS 
'Atomically reassigns transactions to the general category and deletes a user category. 
This function must be called via Supabase RPC from the backend.
Returns counts of transactions reassigned and budget links removed.';

-- Recreate delete_recurring_and_pair without schema prefix
CREATE OR REPLACE FUNCTION delete_recurring_and_pair(p_recurring_id uuid, p_user_id uuid)
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

GRANT EXECUTE ON FUNCTION delete_recurring_and_pair(UUID, UUID) TO authenticated;

COMMENT ON FUNCTION delete_recurring_and_pair IS 
'Atomically deletes a recurring transaction and its paired rule (for recurring transfers).
This function must be called via Supabase RPC from the backend.
Returns success status and whether paired rule was deleted.';
