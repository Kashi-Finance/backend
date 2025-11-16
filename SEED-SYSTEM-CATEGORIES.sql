-- =========================================================
-- Seed System Categories
-- 
-- This script creates the required system categories that
-- must exist for the application to function correctly.
--
-- These categories are global (user_id IS NULL) and
-- immutable (users cannot modify or delete them).
--
-- Run this script ONCE after deploying DB-DDL.txt
-- Must be run with service_role credentials
-- =========================================================

-- System Categories (8 total: 4 keys × 2 flow_types)

INSERT INTO public.category (user_id, key, name, flow_type, created_at, updated_at) VALUES
  -- Initial balance categories (for seeding account balances)
  (NULL, 'initial_balance', 'Initial Balance (Income)', 'income', now(), now()),
  (NULL, 'initial_balance', 'Initial Balance (Outcome)', 'outcome', now(), now()),
  
  -- Manual balance adjustment categories (for corrections)
  (NULL, 'balance_update_income', 'Manual Balance Adjustment (Income)', 'income', now(), now()),
  (NULL, 'balance_update_outcome', 'Manual Balance Adjustment (Outcome)', 'outcome', now(), now()),
  
  -- Transfer categories (for internal account transfers)
  (NULL, 'transfer', 'Transfer (Income)', 'income', now(), now()),
  (NULL, 'transfer', 'Transfer (Outcome)', 'outcome', now(), now()),
  
  -- General/default categories (fallback for uncategorized transactions)
  (NULL, 'general', 'General Income', 'income', now(), now()),
  (NULL, 'general', 'General Outcome', 'outcome', now(), now());

-- =========================================================
-- Verification Query
-- Run this to verify all system categories were created
-- =========================================================

-- Expected result: 8 rows
SELECT 
  key,
  name,
  flow_type,
  user_id IS NULL as is_system_category
FROM public.category
WHERE user_id IS NULL
ORDER BY key, flow_type;

-- =========================================================
-- Expected Output:
-- 
-- | key                    | name                                  | flow_type | is_system_category |
-- |------------------------|---------------------------------------|-----------|-------------------|
-- | balance_update_income  | Manual Balance Adjustment (Income)    | income    | true              |
-- | balance_update_outcome | Manual Balance Adjustment (Outcome)   | outcome   | true              |
-- | general                | General Income                        | income    | true              |
-- | general                | General Outcome                       | outcome   | true              |
-- | initial_balance        | Initial Balance (Income)              | income    | true              |
-- | initial_balance        | Initial Balance (Outcome)             | outcome   | true              |
-- | transfer               | Transfer (Income)                     | income    | true              |
-- | transfer               | Transfer (Outcome)                    | outcome   | true              |
-- =========================================================
