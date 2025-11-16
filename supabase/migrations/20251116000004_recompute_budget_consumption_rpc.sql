-- =========================================================
-- RPC: recompute_budget_consumption
-- Purpose: Recalculate budget.cached_consumption for a given budget period
-- 
-- Security: SECURITY DEFINER (validates user_id ownership)
-- RLS: Bypassed by function, but validates p_user_id explicitly
-- 
-- Behavior:
-- 1. Validates budget belongs to p_user_id
-- 2. Fetches all categories linked to budget via budget_category junction
-- 3. Sums all non-deleted OUTCOME transactions in those categories
--    within the specified date range [p_period_start, p_period_end]
-- 4. Updates budget.cached_consumption with the computed sum
-- 5. Returns the new consumption amount
-- 
-- When to call:
-- - After soft-deleting transactions that affect budget categories
-- - When budget period rolls over
-- - After changing budget category associations
-- - Periodic cache verification (recommended: daily)
-- =========================================================

CREATE OR REPLACE FUNCTION recompute_budget_consumption(
  p_budget_id uuid,
  p_user_id uuid,
  p_period_start date,
  p_period_end date
)
RETURNS numeric(12,2)
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = public
AS $$
DECLARE
  v_new_consumption numeric(12,2);
BEGIN
  -- Validate budget exists and belongs to user
  IF NOT EXISTS (
    SELECT 1 FROM public.budget
    WHERE id = p_budget_id AND user_id = p_user_id
  ) THEN
    RAISE EXCEPTION 'Budget not found or access denied'
      USING HINT = 'p_budget_id must belong to p_user_id';
  END IF;

  -- Validate date range
  IF p_period_start > p_period_end THEN
    RAISE EXCEPTION 'Invalid date range: p_period_start must be <= p_period_end';
  END IF;

  -- Calculate consumption from transactions in budget categories
  -- Only count OUTCOME transactions (expenses)
  SELECT COALESCE(SUM(t.amount), 0) INTO v_new_consumption
  FROM public.transaction t
  INNER JOIN public.budget_category bc ON t.category_id = bc.category_id
  WHERE bc.budget_id = p_budget_id
    AND t.flow_type = 'outcome'  -- Only expenses count toward budget consumption
    AND t.deleted_at IS NULL     -- Only non-deleted transactions
    AND t.date >= p_period_start
    AND t.date <= p_period_end;

  -- Update cached consumption
  UPDATE public.budget
  SET 
    cached_consumption = v_new_consumption,
    updated_at = now()
  WHERE id = p_budget_id
    AND user_id = p_user_id;

  -- Return new consumption
  RETURN v_new_consumption;
END;
$$;

-- Grant execute permission
GRANT EXECUTE ON FUNCTION public.recompute_budget_consumption(uuid, uuid, date, date) TO authenticated;

-- =========================================================
-- Usage Example:
-- 
-- SELECT public.recompute_budget_consumption(
--   p_budget_id := '38f7d540-23fa-497a-8df2-3ab9cbe13da5',
--   p_user_id := '11111111-1111-1111-1111-111111111111',
--   p_period_start := '2025-11-01',
--   p_period_end := '2025-11-30'
-- );
-- 
-- Expected result:
-- | recompute_budget_consumption |
-- |-----------------------------|
-- | 2345.75                     |
-- =========================================================
