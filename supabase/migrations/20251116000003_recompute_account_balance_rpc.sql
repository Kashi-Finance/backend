-- =========================================================
-- RPC: recompute_account_balance
-- Purpose: Recalculate account.cached_balance from transaction history
-- 
-- Security: SECURITY DEFINER (validates user_id ownership)
-- RLS: Bypassed by function, but validates p_user_id explicitly
-- 
-- Behavior:
-- 1. Validates account belongs to p_user_id
-- 2. Sums all non-deleted transactions for the account:
--    - Income transactions: positive contribution
--    - Outcome transactions: negative contribution
-- 3. Updates account.cached_balance with the computed sum
-- 4. Returns the new balance
-- 
-- When to call:
-- - After bulk transaction reassignment
-- - After soft-deleting transactions
-- - After restoring soft-deleted transactions
-- - Periodic cache verification (recommended: daily)
-- =========================================================

CREATE OR REPLACE FUNCTION recompute_account_balance(
  p_account_id uuid,
  p_user_id uuid
)
RETURNS numeric(12,2)
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = public
AS $$
DECLARE
  v_new_balance numeric(12,2);
BEGIN
  -- Validate account exists and belongs to user
  IF NOT EXISTS (
    SELECT 1 FROM public.account
    WHERE id = p_account_id AND user_id = p_user_id
  ) THEN
    RAISE EXCEPTION 'Account not found or access denied'
      USING HINT = 'p_account_id must belong to p_user_id';
  END IF;

  -- Calculate balance from transaction history
  -- Income = positive, Outcome = negative
  SELECT COALESCE(
    SUM(
      CASE 
        WHEN flow_type = 'income' THEN amount
        WHEN flow_type = 'outcome' THEN -amount
        ELSE 0
      END
    ),
    0
  ) INTO v_new_balance
  FROM public.transaction
  WHERE account_id = p_account_id
    AND deleted_at IS NULL;  -- Only count non-deleted transactions

  -- Update cached balance
  UPDATE public.account
  SET 
    cached_balance = v_new_balance,
    updated_at = now()
  WHERE id = p_account_id
    AND user_id = p_user_id;

  -- Return new balance
  RETURN v_new_balance;
END;
$$;

-- Grant execute permission
GRANT EXECUTE ON FUNCTION public.recompute_account_balance(uuid, uuid) TO authenticated;

-- =========================================================
-- Usage Example:
-- 
-- SELECT public.recompute_account_balance(
--   p_account_id := '38f7d540-23fa-497a-8df2-3ab9cbe13da5',
--   p_user_id := '11111111-1111-1111-1111-111111111111'
-- );
-- 
-- Expected result:
-- | recompute_account_balance |
-- |--------------------------|
-- | 15234.50                 |
-- =========================================================
