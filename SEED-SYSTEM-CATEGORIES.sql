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

INSERT INTO public.category (user_id, key, name, flow_type, icon, color, created_at, updated_at) VALUES
  -- Initial balance categories (for seeding account balances)
  (NULL, 'initial_balance', 'Initial Balance (Income)', 'income', 'account_balance', '#4CAF50', now(), now()),
  (NULL, 'initial_balance', 'Initial Balance (Outcome)', 'outcome', 'account_balance', '#F44336', now(), now()),
  
  -- Manual balance adjustment categories (for corrections)
  (NULL, 'balance_update', 'Manual Balance Adjustment (Income)', 'income', 'tune', '#2196F3', now(), now()),
  (NULL, 'balance_update', 'Manual Balance Adjustment (Outcome)', 'outcome', 'tune', '#FF9800', now(), now()),
  
  -- Transfer categories (for internal account transfers)
  (NULL, 'transfer', 'Transfer (Income)', 'income', 'swap_horiz', '#9C27B0', now(), now()),
  (NULL, 'transfer', 'Transfer (Outcome)', 'outcome', 'swap_horiz', '#9C27B0', now(), now()),
  
  -- General/default categories (fallback for uncategorized transactions)
  (NULL, 'general', 'General Income', 'income', 'attach_money', '#607D8B', now(), now()),
  (NULL, 'general', 'General Outcome', 'outcome', 'money_off', '#607D8B', now(), now());

-- =========================================================
-- Verification Query
-- Run this to verify all system categories were created
-- =========================================================

-- Expected result: 8 rows
SELECT 
  key,
  name,
  flow_type,
  icon,
  color,
  user_id IS NULL as is_system_category
FROM public.category
WHERE user_id IS NULL
ORDER BY key, flow_type;

-- =========================================================
-- Expected Output:
-- 
-- | key                    | name                                  | flow_type | icon            | color   | is_system_category |
-- |------------------------|---------------------------------------|-----------|-----------------|---------|-------------------|
-- | balance_update         | Manual Balance Adjustment (Income)    | income    | tune            | #2196F3 | true              |
-- | balance_update         | Manual Balance Adjustment (Outcome)   | outcome   | tune            | #FF9800 | true              |
-- | general                | General Income                        | income    | attach_money    | #607D8B | true              |
-- | general                | General Outcome                       | outcome   | money_off       | #607D8B | true              |
-- | initial_balance        | Initial Balance (Income)              | income    | account_balance | #4CAF50 | true              |
-- | initial_balance        | Initial Balance (Outcome)             | outcome   | account_balance | #F44336 | true              |
-- | transfer               | Transfer (Income)                     | income    | swap_horiz      | #9C27B0 | true              |
-- | transfer               | Transfer (Outcome)                    | outcome   | swap_horiz      | #9C27B0 | true              |
-- =========================================================
