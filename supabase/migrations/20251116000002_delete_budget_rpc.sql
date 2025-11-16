c-- =========================================================
-- RPC: delete_budget
-- Purpose: Soft-delete a budget (set deleted_at timestamp)
-- 
-- Security: SECURITY DEFINER (validates user_id ownership)
-- RLS: Bypassed by function, but validates p_user_id explicitly
-- 
-- Behavior:
-- 1. Validates budget belongs to p_user_id
-- 2. Sets deleted_at = now() on the budget
-- 3. Returns soft-delete status and timestamp
-- 
-- Note: budget_category junction rows are NOT deleted
-- (they remain for historical analysis but budget is hidden via RLS)
-- =========================================================

CREATE OR REPLACE FUNCTION delete_budget(
  p_budget_id uuid,
  p_user_id uuid
)
RETURNS TABLE(
  budget_soft_deleted BOOLEAN,
  deleted_at TIMESTAMPTZ
)
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = public
AS $$
DECLARE
  v_deleted_at TIMESTAMPTZ;
  v_rows_affected INT;
BEGIN
  -- Validate budget exists and belongs to user
  IF NOT EXISTS (
    SELECT 1 FROM public.budget
    WHERE id = p_budget_id AND user_id = p_user_id
  ) THEN
    RAISE EXCEPTION 'Budget not found or access denied'
      USING HINT = 'p_budget_id must belong to p_user_id';
  END IF;

  -- Soft-delete the budget
  UPDATE public.budget
  SET 
    deleted_at = now(),
    updated_at = now()
  WHERE id = p_budget_id
    AND user_id = p_user_id
  RETURNING deleted_at INTO v_deleted_at;

  GET DIAGNOSTICS v_rows_affected = ROW_COUNT;

  -- Return result
  RETURN QUERY
  SELECT 
    (v_rows_affected > 0) AS budget_soft_deleted,
    v_deleted_at AS deleted_at;
END;
$$;

-- Grant execute permission
GRANT EXECUTE ON FUNCTION public.delete_budget(uuid, uuid) TO authenticated;

-- =========================================================
-- Usage Example:
-- 
-- SELECT * FROM public.delete_budget(
--   p_budget_id := '38f7d540-23fa-497a-8df2-3ab9cbe13da5',
--   p_user_id := '11111111-1111-1111-1111-111111111111'
-- );
-- 
-- Expected result:
-- | budget_soft_deleted | deleted_at                |
-- |--------------------|---------------------------|
-- | true               | 2025-11-16T10:30:00-06:00 |
-- =========================================================
