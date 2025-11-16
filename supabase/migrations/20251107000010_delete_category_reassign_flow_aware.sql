-- Migration: Update delete_category_reassign RPC to be flow-type aware
-- Purpose: When deleting a category, reassign transactions to matching general category (same flow_type)
-- Date: 2025-11-07

-- Drop old version
DROP FUNCTION IF EXISTS delete_category_reassign(UUID, UUID);

-- Create new flow-type aware version
CREATE OR REPLACE FUNCTION delete_category_reassign(
  p_category_id UUID, 
  p_user_id UUID,
  p_cascade BOOLEAN DEFAULT FALSE  -- If true, cascade delete transactions instead of reassigning
)
RETURNS TABLE(
    transactions_reassigned INT,
    budget_links_removed INT,
    transactions_deleted INT
)
LANGUAGE plpgsql
SECURITY DEFINER
AS $$
DECLARE
  v_general_category_id UUID;
  v_category_flow_type text;
  v_txn_count INT := 0;
  v_links_count INT := 0;
  v_deleted_count INT := 0;
BEGIN
  -- Get the flow_type of the category being deleted
  SELECT flow_type INTO v_category_flow_type
  FROM category
  WHERE id = p_category_id AND user_id = p_user_id;

  IF v_category_flow_type IS NULL THEN
    RAISE EXCEPTION 'category not found or not owned by user';
  END IF;

  -- If cascade mode, delete all transactions referencing this category
  IF p_cascade THEN
    DELETE FROM "transaction"
    WHERE category_id = p_category_id;
    GET DIAGNOSTICS v_deleted_count = ROW_COUNT;
    
    v_txn_count := 0;  -- No reassignment in cascade mode
  ELSE
    -- Find the matching general category (same flow_type, system category)
    SELECT id INTO v_general_category_id
    FROM category
    WHERE key = 'general' 
      AND user_id IS NULL 
      AND flow_type = v_category_flow_type::flow_type_enum
    LIMIT 1;

    IF v_general_category_id IS NULL THEN
      RAISE EXCEPTION 'system general category not found for flow_type=%', v_category_flow_type;
    END IF;

    -- Reassign transactions to the matching general category
    UPDATE "transaction"
    SET category_id = v_general_category_id
    WHERE category_id = p_category_id;
    GET DIAGNOSTICS v_txn_count = ROW_COUNT;
  END IF;

  -- Remove budget_category links for this category (always happens)
  DELETE FROM budget_category
  WHERE category_id = p_category_id;
  GET DIAGNOSTICS v_links_count = ROW_COUNT;

  -- Delete the category (only if it belongs to the provided user_id)
  DELETE FROM category
  WHERE id = p_category_id AND user_id = p_user_id;

  IF NOT FOUND THEN
    RAISE EXCEPTION 'category not found or not owned by user during deletion';
  END IF;

  -- Return counts
  transactions_reassigned := v_txn_count;
  budget_links_removed := v_links_count;
  transactions_deleted := v_deleted_count;
  RETURN NEXT;
END;
$$;

GRANT EXECUTE ON FUNCTION delete_category_reassign(UUID, UUID, BOOLEAN) TO authenticated;

COMMENT ON FUNCTION delete_category_reassign IS 
'Delete a user category with flow-type aware reassignment. 
- Default (p_cascade=false): Reassigns transactions to general category matching the deleted category flow_type
- Cascade (p_cascade=true): Deletes all transactions referencing the category
Always removes budget_category links before deletion.';
