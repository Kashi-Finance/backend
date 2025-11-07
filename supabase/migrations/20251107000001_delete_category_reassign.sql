-- Migration: create RPC to reassign transactions to 'general' and delete a user category atomically
-- This function performs the update -> delete sequence inside the DB to avoid race conditions
-- Returns number of transactions reassigned and budget links removed
CREATE OR REPLACE FUNCTION app.delete_category_reassign(p_category_id uuid, p_user_id uuid)
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
