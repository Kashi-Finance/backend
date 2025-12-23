-- =========================================================
-- Migration: Engagement RPCs and pg_cron Scheduling
-- Created: 2025-12-08
-- 
-- Purpose:
-- 1. Create engagement/streak-related RPC functions
-- 2. Schedule weekly streak freeze reset via pg_cron
--
-- Prerequisites:
-- - pg_cron extension must be enabled in Supabase Dashboard
--   (Database → Extensions → pg_cron → Enable)
--
-- Functions:
-- - update_user_streak: Update streak after financial activity
-- - get_user_streak: Get streak status with risk assessment
-- - reset_weekly_streak_freezes: Reset all freezes (cron job)
--
-- Security:
-- All functions use SECURITY DEFINER with SET search_path = ''
-- =========================================================

-- =========================================================
-- SECTION 1: ENGAGEMENT / STREAK RPCs
-- =========================================================

-- ---------------------------------------------------------
-- 1.1 update_user_streak
-- Update user's streak after logging financial activity
-- Called automatically when creating transactions or invoices
-- ---------------------------------------------------------

CREATE OR REPLACE FUNCTION public.update_user_streak(
    p_user_id UUID
)
RETURNS TABLE(
    current_streak INT,
    longest_streak INT,
    streak_extended BOOLEAN,
    streak_reset BOOLEAN,
    freeze_used BOOLEAN
)
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = ''
AS $$
DECLARE
    v_profile RECORD;
    v_today DATE;
    v_days_since_activity INT;
    v_streak_extended BOOLEAN := FALSE;
    v_streak_reset BOOLEAN := FALSE;
    v_freeze_used BOOLEAN := FALSE;
    v_new_current_streak INT;
    v_new_longest_streak INT;
BEGIN
    -- Get current date in UTC
    v_today := CURRENT_DATE;
    
    -- Fetch user's current streak data
    SELECT 
        p.current_streak,
        p.longest_streak,
        p.last_activity_date,
        p.streak_freeze_available,
        p.streak_freeze_used_this_week
    INTO v_profile
    FROM public.profile p
    WHERE p.user_id = p_user_id;
    
    IF NOT FOUND THEN
        RAISE EXCEPTION 'Profile not found for user %', p_user_id;
    END IF;
    
    -- If already logged today, no change needed
    IF v_profile.last_activity_date = v_today THEN
        RETURN QUERY SELECT 
            v_profile.current_streak::INT,
            v_profile.longest_streak::INT,
            FALSE,
            FALSE,
            FALSE;
        RETURN;
    END IF;
    
    -- Calculate days since last activity
    IF v_profile.last_activity_date IS NULL THEN
        -- First ever activity
        v_days_since_activity := NULL;
    ELSE
        v_days_since_activity := v_today - v_profile.last_activity_date;
    END IF;
    
    -- Determine new streak value
    IF v_days_since_activity IS NULL THEN
        -- First activity ever: start streak at 1
        v_new_current_streak := 1;
        v_streak_extended := TRUE;
        
    ELSIF v_days_since_activity = 1 THEN
        -- Consecutive day: extend streak
        v_new_current_streak := v_profile.current_streak + 1;
        v_streak_extended := TRUE;
        
    ELSIF v_days_since_activity = 2 AND v_profile.streak_freeze_available THEN
        -- Missed 1 day but have freeze: use freeze and extend
        v_new_current_streak := v_profile.current_streak + 1;
        v_streak_extended := TRUE;
        v_freeze_used := TRUE;
        
    ELSE
        -- Missed too many days: reset streak
        v_new_current_streak := 1;
        v_streak_reset := TRUE;
    END IF;
    
    -- Update longest streak if needed
    v_new_longest_streak := GREATEST(v_profile.longest_streak, v_new_current_streak);
    
    -- Update profile
    UPDATE public.profile
    SET 
        current_streak = v_new_current_streak,
        longest_streak = v_new_longest_streak,
        last_activity_date = v_today,
        streak_freeze_available = CASE 
            WHEN v_freeze_used THEN FALSE 
            ELSE streak_freeze_available 
        END,
        streak_freeze_used_this_week = CASE 
            WHEN v_freeze_used THEN TRUE 
            ELSE streak_freeze_used_this_week 
        END,
        updated_at = now()
    WHERE user_id = p_user_id;
    
    RETURN QUERY SELECT 
        v_new_current_streak,
        v_new_longest_streak,
        v_streak_extended,
        v_streak_reset,
        v_freeze_used;
END;
$$;

COMMENT ON FUNCTION public.update_user_streak IS 
'Updates user streak after financial activity. Returns new streak values and whether streak was extended, reset, or freeze was used.';


-- ---------------------------------------------------------
-- 1.2 get_user_streak
-- Get complete streak status with risk assessment
-- ---------------------------------------------------------

CREATE OR REPLACE FUNCTION public.get_user_streak(
    p_user_id UUID
)
RETURNS TABLE(
    current_streak INT,
    longest_streak INT,
    last_activity_date DATE,
    streak_freeze_available BOOLEAN,
    streak_at_risk BOOLEAN,
    days_until_streak_break INT
)
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = ''
AS $$
DECLARE
    v_profile RECORD;
    v_today DATE;
    v_days_since_activity INT;
    v_at_risk BOOLEAN := FALSE;
    v_days_until_break INT := NULL;
BEGIN
    v_today := CURRENT_DATE;
    
    -- Fetch user's streak data
    SELECT 
        p.current_streak,
        p.longest_streak,
        p.last_activity_date,
        p.streak_freeze_available
    INTO v_profile
    FROM public.profile p
    WHERE p.user_id = p_user_id;
    
    IF NOT FOUND THEN
        RAISE EXCEPTION 'Profile not found for user %', p_user_id;
    END IF;
    
    -- Calculate risk assessment
    IF v_profile.last_activity_date IS NOT NULL THEN
        v_days_since_activity := v_today - v_profile.last_activity_date;
        
        IF v_days_since_activity >= 1 THEN
            -- No activity today
            v_at_risk := TRUE;
            
            IF v_profile.streak_freeze_available THEN
                -- Have freeze: can miss 1 more day
                v_days_until_break := 2 - v_days_since_activity;
            ELSE
                -- No freeze: breaks end of today
                v_days_until_break := 1 - v_days_since_activity;
            END IF;
            
            -- Clamp to 0 minimum
            v_days_until_break := GREATEST(v_days_until_break, 0);
        END IF;
    END IF;
    
    RETURN QUERY SELECT 
        v_profile.current_streak::INT,
        v_profile.longest_streak::INT,
        v_profile.last_activity_date,
        v_profile.streak_freeze_available,
        v_at_risk,
        v_days_until_break;
END;
$$;

COMMENT ON FUNCTION public.get_user_streak IS 
'Returns user streak status with risk assessment. streak_at_risk is TRUE if no activity logged today.';


-- ---------------------------------------------------------
-- 1.3 reset_weekly_streak_freezes
-- Reset freeze availability for all users (cron job only)
-- Called every Monday at 00:00 UTC via pg_cron
-- ---------------------------------------------------------

CREATE OR REPLACE FUNCTION public.reset_weekly_streak_freezes()
RETURNS INT
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = ''
AS $$
DECLARE
    v_count INT;
BEGIN
    -- Reset freeze for all users who used it this week
    UPDATE public.profile
    SET 
        streak_freeze_available = TRUE,
        streak_freeze_used_this_week = FALSE,
        updated_at = now()
    WHERE streak_freeze_used_this_week = TRUE;
    
    GET DIAGNOSTICS v_count = ROW_COUNT;
    
    RETURN v_count;
END;
$$;

COMMENT ON FUNCTION public.reset_weekly_streak_freezes IS 
'Resets streak freeze availability for all users. Called weekly by pg_cron on Mondays at 00:00 UTC.';


-- =========================================================
-- SECTION 2: PG_CRON SCHEDULING (OPTIONAL)
-- =========================================================

-- NOTE: pg_cron scheduling is optional and only available in production
-- Local Supabase instances don't have pg_cron enabled by default
-- 
-- To enable in production Supabase:
-- 1. Go to Database → Extensions in Supabase Dashboard
-- 2. Enable pg_cron extension
-- 3. Run the following SQL manually in the SQL editor:
--
-- SELECT cron.schedule(
--     'reset-streak-freezes-weekly',
--     '0 0 * * 1',
--     $$SELECT public.reset_weekly_streak_freezes()$$
-- );
--
-- Cron expression: '0 0 * * 1'
--   0 = minute (00)
--   0 = hour (00:00 UTC)
--   * = day of month (any)
--   * = month (any)
--   1 = day of week (Monday, where 0=Sunday)
--
-- For local development without pg_cron:
-- The reset_weekly_streak_freezes() function can be called manually
-- or via a scheduled job in your deployment environment


-- =========================================================
-- SECTION 3: GRANT PERMISSIONS
-- =========================================================

-- Engagement functions are called via authenticated client
GRANT EXECUTE ON FUNCTION public.update_user_streak(UUID) TO authenticated;
GRANT EXECUTE ON FUNCTION public.get_user_streak(UUID) TO authenticated;

-- reset_weekly_streak_freezes is internal (pg_cron only)
-- No GRANT to authenticated - only postgres role can call it
-- pg_cron runs as the postgres superuser
