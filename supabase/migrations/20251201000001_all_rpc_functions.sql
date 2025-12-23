-- =========================================================
-- Migration: All RPC Functions (Consolidated)
-- Created: 2025-12-01
-- 
-- Purpose:
-- Single consolidated migration containing ALL RPC functions
-- for Kashi Finances backend. This replaces multiple separate
-- migration files with their updates and fixes merged together.
--
-- Includes:
-- 1. Account Management RPCs
-- 2. Transaction Management RPCs  
-- 3. Transfer RPCs
-- 4. Recurring Transaction RPCs
-- 5. Category Management RPCs
-- 6. Wishlist RPCs
-- 7. Cache Recomputation RPCs
-- 8. Currency Validation RPCs
-- 9. Favorite Account RPCs
--
-- Security:
-- All functions use SECURITY DEFINER with SET search_path = ''
-- to prevent search_path manipulation attacks.
-- =========================================================

-- =========================================================
-- SECTION 1: ACCOUNT MANAGEMENT RPCs
-- =========================================================

-- ---------------------------------------------------------
-- 1.1 delete_account_reassign
-- Soft-delete account after reassigning transactions
-- ---------------------------------------------------------

CREATE OR REPLACE FUNCTION public.delete_account_reassign(
    p_account_id UUID,
    p_user_id UUID,
    p_target_account_id UUID
)
RETURNS TABLE(
    recurring_transactions_reassigned INT,
    transactions_reassigned INT,
    account_soft_deleted BOOLEAN,
    deleted_at TIMESTAMPTZ
)
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = ''
AS $$
DECLARE
    v_recurring_count INT := 0;
    v_txn_count INT := 0;
    v_deleted_at TIMESTAMPTZ;
BEGIN
    -- Validate source account exists and belongs to user
    IF NOT EXISTS (
        SELECT 1 FROM public.account 
        WHERE id = p_account_id AND user_id = p_user_id AND deleted_at IS NULL
    ) THEN
        RAISE EXCEPTION 'Source account not found, already deleted, or not accessible';
    END IF;
    
    -- Validate target account exists and belongs to user
    IF NOT EXISTS (
        SELECT 1 FROM public.account 
        WHERE id = p_target_account_id AND user_id = p_user_id AND deleted_at IS NULL
    ) THEN
        RAISE EXCEPTION 'Target account not found, already deleted, or not accessible';
    END IF;
    
    -- Prevent self-reassignment
    IF p_account_id = p_target_account_id THEN
        RAISE EXCEPTION 'Cannot reassign to the same account';
    END IF;
    
    -- Step 1: Reassign all recurring_transaction rows
    UPDATE public.recurring_transaction
    SET account_id = p_target_account_id,
        updated_at = now()
    WHERE account_id = p_account_id AND user_id = p_user_id AND deleted_at IS NULL;
    
    GET DIAGNOSTICS v_recurring_count = ROW_COUNT;
    
    -- Step 2: Reassign all transactions
    UPDATE public.transaction
    SET account_id = p_target_account_id,
        updated_at = now()
    WHERE account_id = p_account_id AND user_id = p_user_id AND deleted_at IS NULL;
    
    GET DIAGNOSTICS v_txn_count = ROW_COUNT;
    
    -- Step 3: Soft-delete the source account
    v_deleted_at := now();
    
    UPDATE public.account
    SET deleted_at = v_deleted_at,
        updated_at = v_deleted_at
    WHERE id = p_account_id AND user_id = p_user_id;
    
    IF NOT FOUND THEN
        RAISE EXCEPTION 'Failed to soft-delete account';
    END IF;
    
    -- Recompute cached_balance for target account
    PERFORM public.recompute_account_balance(p_target_account_id, p_user_id);
    
    -- Return results
    recurring_transactions_reassigned := v_recurring_count;
    transactions_reassigned := v_txn_count;
    account_soft_deleted := TRUE;
    deleted_at := v_deleted_at;
    RETURN NEXT;
END;
$$;

COMMENT ON FUNCTION public.delete_account_reassign(UUID, UUID, UUID) IS 
  'Soft-deletes an account after reassigning all transactions and recurring templates to target account.';

-- ---------------------------------------------------------
-- 1.2 delete_account_cascade
-- Soft-delete account and all related data
-- ---------------------------------------------------------

CREATE OR REPLACE FUNCTION public.delete_account_cascade(
    p_account_id UUID,
    p_user_id UUID
)
RETURNS TABLE(
    recurring_transactions_soft_deleted INT,
    recurring_paired_references_cleared INT,
    transactions_soft_deleted INT,
    transaction_paired_references_cleared INT,
    account_soft_deleted BOOLEAN,
    deleted_at TIMESTAMPTZ
)
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = ''
AS $$
DECLARE
    v_recurring_ids UUID[];
    v_recurring_count INT := 0;
    v_recurring_paired_count INT := 0;
    v_txn_ids UUID[];
    v_txn_count INT := 0;
    v_txn_paired_count INT := 0;
    v_deleted_at TIMESTAMPTZ;
BEGIN
    -- Validate account exists and belongs to user
    IF NOT EXISTS (
        SELECT 1 FROM public.account 
        WHERE id = p_account_id AND user_id = p_user_id AND deleted_at IS NULL
    ) THEN
        RAISE EXCEPTION 'Account not found, already deleted, or not accessible';
    END IF;
    
    v_deleted_at := now();
    
    -- Step 1: Collect recurring_transaction IDs
    SELECT ARRAY_AGG(id) INTO v_recurring_ids
    FROM public.recurring_transaction
    WHERE account_id = p_account_id AND user_id = p_user_id AND deleted_at IS NULL;
    
    v_recurring_count := COALESCE(array_length(v_recurring_ids, 1), 0);
    
    -- Step 2: Clear paired references
    IF v_recurring_count > 0 THEN
        UPDATE public.recurring_transaction
        SET paired_recurring_transaction_id = NULL,
            updated_at = v_deleted_at
        WHERE paired_recurring_transaction_id = ANY(v_recurring_ids)
          AND deleted_at IS NULL;
        
        GET DIAGNOSTICS v_recurring_paired_count = ROW_COUNT;
    END IF;
    
    -- Step 3: Soft-delete recurring transactions
    UPDATE public.recurring_transaction
    SET deleted_at = v_deleted_at,
        updated_at = v_deleted_at
    WHERE account_id = p_account_id AND user_id = p_user_id AND deleted_at IS NULL;
    
    -- Step 4: Collect transaction IDs
    SELECT ARRAY_AGG(id) INTO v_txn_ids
    FROM public.transaction
    WHERE account_id = p_account_id AND user_id = p_user_id AND deleted_at IS NULL;
    
    v_txn_count := COALESCE(array_length(v_txn_ids, 1), 0);
    
    -- Step 5: Clear paired transaction references
    IF v_txn_count > 0 THEN
        UPDATE public.transaction
        SET paired_transaction_id = NULL,
            updated_at = v_deleted_at
        WHERE paired_transaction_id = ANY(v_txn_ids)
          AND deleted_at IS NULL;
        
        GET DIAGNOSTICS v_txn_paired_count = ROW_COUNT;
    END IF;
    
    -- Step 6: Soft-delete transactions
    UPDATE public.transaction
    SET deleted_at = v_deleted_at,
        updated_at = v_deleted_at
    WHERE account_id = p_account_id AND user_id = p_user_id AND deleted_at IS NULL;
    
    -- Step 7: Soft-delete the account
    UPDATE public.account
    SET deleted_at = v_deleted_at,
        updated_at = v_deleted_at
    WHERE id = p_account_id AND user_id = p_user_id;
    
    IF NOT FOUND THEN
        RAISE EXCEPTION 'Failed to soft-delete account';
    END IF;
    
    -- Return results
    recurring_transactions_soft_deleted := v_recurring_count;
    recurring_paired_references_cleared := v_recurring_paired_count;
    transactions_soft_deleted := v_txn_count;
    transaction_paired_references_cleared := v_txn_paired_count;
    account_soft_deleted := TRUE;
    deleted_at := v_deleted_at;
    RETURN NEXT;
END;
$$;

COMMENT ON FUNCTION public.delete_account_cascade(UUID, UUID) IS 
  'Soft-deletes an account and all its transactions and recurring templates.';

-- =========================================================
-- SECTION 2: TRANSACTION MANAGEMENT RPCs
-- =========================================================

-- ---------------------------------------------------------
-- 2.1 delete_transaction
-- Soft-delete a single transaction
-- ---------------------------------------------------------

CREATE OR REPLACE FUNCTION public.delete_transaction(
    p_transaction_id UUID,
    p_user_id UUID
)
RETURNS TABLE(
    transaction_soft_deleted BOOLEAN,
    deleted_at TIMESTAMPTZ,
    paired_transaction_affected BOOLEAN
)
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = ''
AS $$
DECLARE
    v_deleted_at TIMESTAMPTZ;
    v_paired_id UUID;
    v_paired_affected BOOLEAN := FALSE;
    v_account_id UUID;
BEGIN
    -- Validate transaction exists and belongs to user
    IF NOT EXISTS (
        SELECT 1 FROM public.transaction 
        WHERE id = p_transaction_id AND user_id = p_user_id AND deleted_at IS NULL
    ) THEN
        RAISE EXCEPTION 'Transaction not found, already deleted, or not accessible';
    END IF;
    
    -- Store account_id and paired_transaction_id
    SELECT account_id, paired_transaction_id INTO v_account_id, v_paired_id
    FROM public.transaction
    WHERE id = p_transaction_id;
    
    v_deleted_at := now();
    
    -- Soft-delete the transaction
    UPDATE public.transaction
    SET 
        deleted_at = v_deleted_at,
        updated_at = v_deleted_at
    WHERE id = p_transaction_id AND user_id = p_user_id;
    
    -- Clear paired reference if applicable
    IF v_paired_id IS NOT NULL THEN
        UPDATE public.transaction
        SET 
            paired_transaction_id = NULL,
            updated_at = v_deleted_at
        WHERE id = v_paired_id AND user_id = p_user_id;
        
        v_paired_affected := TRUE;
    END IF;
    
    -- Recompute cached_balance
    PERFORM public.recompute_account_balance(v_account_id, p_user_id);
    
    -- Return results
    transaction_soft_deleted := TRUE;
    deleted_at := v_deleted_at;
    paired_transaction_affected := v_paired_affected;
    RETURN NEXT;
END;
$$;

COMMENT ON FUNCTION public.delete_transaction(UUID, UUID) IS 
  'Soft-deletes a single transaction and clears any paired reference.';

-- =========================================================
-- SECTION 3: TRANSFER RPCs
-- =========================================================

-- ---------------------------------------------------------
-- 3.1 create_transfer
-- Atomically create two paired transactions for a transfer
-- ---------------------------------------------------------

CREATE OR REPLACE FUNCTION public.create_transfer(
    p_user_id UUID,
    p_from_account_id UUID,
    p_to_account_id UUID,
    p_amount NUMERIC(12,2),
    p_date DATE,
    p_description TEXT,
    p_transfer_category_id UUID
)
RETURNS TABLE(
    outgoing_transaction_id UUID,
    incoming_transaction_id UUID
)
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = ''
AS $$
DECLARE
    v_outgoing_id UUID;
    v_incoming_id UUID;
BEGIN
    -- Validate both accounts belong to the user
    IF NOT EXISTS (
        SELECT 1 FROM public.account 
        WHERE id = p_from_account_id AND user_id = p_user_id AND deleted_at IS NULL
    ) THEN
        RAISE EXCEPTION 'Source account not found or not accessible';
    END IF;
    
    IF NOT EXISTS (
        SELECT 1 FROM public.account 
        WHERE id = p_to_account_id AND user_id = p_user_id AND deleted_at IS NULL
    ) THEN
        RAISE EXCEPTION 'Destination account not found or not accessible';
    END IF;
    
    -- Step 1: Create outgoing transaction (outcome from source)
    INSERT INTO public.transaction (
        user_id,
        account_id,
        category_id,
        flow_type,
        amount,
        date,
        description,
        source
    ) VALUES (
        p_user_id,
        p_from_account_id,
        p_transfer_category_id,
        'outcome'::public.flow_type_enum,
        p_amount,
        p_date,
        p_description,
        'manual'
    ) RETURNING id INTO v_outgoing_id;
    
    -- Step 2: Create incoming transaction (income to destination)
    INSERT INTO public.transaction (
        user_id,
        account_id,
        category_id,
        flow_type,
        amount,
        date,
        description,
        source,
        paired_transaction_id
    ) VALUES (
        p_user_id,
        p_to_account_id,
        p_transfer_category_id,
        'income'::public.flow_type_enum,
        p_amount,
        p_date,
        p_description,
        'manual',
        v_outgoing_id
    ) RETURNING id INTO v_incoming_id;
    
    -- Step 3: Update outgoing transaction to link back to incoming
    UPDATE public.transaction
    SET paired_transaction_id = v_incoming_id
    WHERE id = v_outgoing_id;
    
    -- Return both IDs
    outgoing_transaction_id := v_outgoing_id;
    incoming_transaction_id := v_incoming_id;
    RETURN NEXT;
END;
$$;

COMMENT ON FUNCTION public.create_transfer(UUID, UUID, UUID, NUMERIC, DATE, TEXT, UUID) IS 
  'Atomically creates two paired transactions for an internal transfer between accounts.';

-- ---------------------------------------------------------
-- 3.2 delete_transfer
-- Delete both legs of a transfer
-- ---------------------------------------------------------

CREATE OR REPLACE FUNCTION public.delete_transfer(
    p_transaction_id UUID,
    p_user_id UUID
)
RETURNS TABLE(
    deleted_transaction_id UUID,
    paired_transaction_id UUID
)
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = ''
AS $$
DECLARE
    v_transaction_id UUID;
    v_paired_id UUID;
    v_owner_id UUID;
BEGIN
    -- Step 1: Fetch transaction and validate ownership
    SELECT id, paired_transaction_id, user_id
    INTO v_transaction_id, v_paired_id, v_owner_id
    FROM public.transaction
    WHERE id = p_transaction_id AND deleted_at IS NULL;
    
    -- Validate transaction exists
    IF v_transaction_id IS NULL THEN
        RAISE EXCEPTION 'Transaction % not found', p_transaction_id;
    END IF;
    
    -- Validate ownership
    IF v_owner_id != p_user_id THEN
        RAISE EXCEPTION 'Transaction % does not belong to user %', p_transaction_id, p_user_id;
    END IF;
    
    -- Validate it's part of a transfer
    IF v_paired_id IS NULL THEN
        RAISE EXCEPTION 'Transaction % is not part of a transfer (paired_transaction_id is NULL)', p_transaction_id;
    END IF;
    
    -- Step 2: Soft-delete both transactions atomically
    UPDATE public.transaction
    SET deleted_at = now(), updated_at = now()
    WHERE id = p_transaction_id;
    
    UPDATE public.transaction
    SET deleted_at = now(), updated_at = now(), paired_transaction_id = NULL
    WHERE id = v_paired_id;
    
    -- Clear the paired reference on the first transaction too
    UPDATE public.transaction
    SET paired_transaction_id = NULL
    WHERE id = p_transaction_id;
    
    -- Step 3: Return both IDs for confirmation
    deleted_transaction_id := p_transaction_id;
    paired_transaction_id := v_paired_id;
    
    RETURN NEXT;
END;
$$;

COMMENT ON FUNCTION public.delete_transfer(UUID, UUID) IS 
  'Soft-deletes both transactions in a transfer pair atomically.';

-- ---------------------------------------------------------
-- 3.3 update_transfer
-- Update both legs of a transfer atomically
-- ---------------------------------------------------------

CREATE OR REPLACE FUNCTION public.update_transfer(
    p_transaction_id UUID,
    p_user_id UUID,
    p_amount NUMERIC DEFAULT NULL,
    p_date DATE DEFAULT NULL,
    p_description TEXT DEFAULT NULL
)
RETURNS json
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = ''
AS $$
DECLARE
    v_transaction record;
    v_paired_transaction record;
    v_result json;
BEGIN
    -- Fetch the transaction and verify it's a transfer
    SELECT * INTO v_transaction
    FROM public.transaction
    WHERE id = p_transaction_id
      AND user_id = p_user_id
      AND paired_transaction_id IS NOT NULL
      AND deleted_at IS NULL;
    
    IF NOT FOUND THEN
        RAISE EXCEPTION 'Transaction not found, not accessible, or not a transfer';
    END IF;
    
    -- Fetch the paired transaction
    SELECT * INTO v_paired_transaction
    FROM public.transaction
    WHERE id = v_transaction.paired_transaction_id
      AND user_id = p_user_id
      AND deleted_at IS NULL;
    
    IF NOT FOUND THEN
        RAISE EXCEPTION 'Paired transaction not found or not accessible';
    END IF;
    
    -- Update the original transaction (only provided fields)
    UPDATE public.transaction
    SET 
        amount = COALESCE(p_amount, amount),
        date = COALESCE(p_date, date),
        description = COALESCE(p_description, description),
        updated_at = now()
    WHERE id = p_transaction_id;
    
    -- Update the paired transaction with the same values
    UPDATE public.transaction
    SET 
        amount = COALESCE(p_amount, amount),
        date = COALESCE(p_date, date),
        description = COALESCE(p_description, description),
        updated_at = now()
    WHERE id = v_transaction.paired_transaction_id;
    
    -- Return both updated transaction IDs
    v_result := json_build_object(
        'updated_transaction_id', p_transaction_id,
        'updated_paired_transaction_id', v_transaction.paired_transaction_id
    );
    
    RETURN v_result;
END;
$$;

COMMENT ON FUNCTION public.update_transfer(UUID, UUID, NUMERIC, DATE, TEXT) IS 
  'Updates both legs of a transfer atomically. Only amount, date, and description can be updated.';

-- =========================================================
-- SECTION 4: RECURRING TRANSACTION RPCs
-- =========================================================

-- ---------------------------------------------------------
-- 4.1 sync_recurring_transactions
-- Generate pending transactions from recurring templates
-- Handles: paired transfers, account balance updates, budget consumption updates
-- ---------------------------------------------------------

CREATE OR REPLACE FUNCTION public.sync_recurring_transactions(
    p_user_id UUID,
    p_today DATE
)
RETURNS TABLE(
    transactions_generated INT,
    rules_processed INT,
    accounts_updated INT,
    budgets_updated INT
) 
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = ''
AS $$
DECLARE
    v_rule RECORD;
    v_transactions_count INT := 0;
    v_rules_count INT := 0;
    v_accounts_updated INT := 0;
    v_budgets_updated INT := 0;
    v_next_occurrence DATE;
    v_new_txn_id UUID;
    v_paired_txn_id UUID;
    v_paired_rule RECORD;
    v_affected_accounts UUID[] := ARRAY[]::UUID[];
    v_affected_categories UUID[] := ARRAY[]::UUID[];
    v_processed_paired_rules UUID[] := ARRAY[]::UUID[];  -- Track already-processed paired rules
    v_account_id UUID;
    v_category_id UUID;
    v_process_as_standalone BOOLEAN;  -- Flag to control standalone processing
BEGIN
    -- =========================================================================
    -- PHASE 1: Generate transactions from recurring rules
    -- =========================================================================
    
    -- Select active recurring rules (skip if already processed as part of a pair)
    FOR v_rule IN
        SELECT 
            id, account_id, category_id, flow_type, amount, description,
            frequency, interval, by_weekday, by_monthday,
            start_date, next_run_date, end_date, paired_recurring_transaction_id
        FROM public.recurring_transaction
        WHERE user_id = p_user_id
          AND is_active = true
          AND deleted_at IS NULL
          AND next_run_date <= p_today
        ORDER BY next_run_date ASC
    LOOP
        -- Skip if this rule was already processed as the "paired" side of a transfer
        IF v_rule.id = ANY(v_processed_paired_rules) THEN
            CONTINUE;
        END IF;
        
        v_rules_count := v_rules_count + 1;
        v_next_occurrence := v_rule.next_run_date;
        v_process_as_standalone := TRUE;  -- Default to standalone, override if paired processing succeeds
        
        -- Check if this is a paired recurring transfer
        IF v_rule.paired_recurring_transaction_id IS NOT NULL THEN
            -- Fetch the paired rule
            SELECT * INTO v_paired_rule
            FROM public.recurring_transaction
            WHERE id = v_rule.paired_recurring_transaction_id
              AND user_id = p_user_id
              AND is_active = true
              AND deleted_at IS NULL;
            
            -- If paired rule exists and is valid, process as a transfer pair
            IF v_paired_rule.id IS NOT NULL THEN
                v_process_as_standalone := FALSE;  -- Will process as paired transfer
                
                -- Mark paired rule as processed so we don't double-process
                v_processed_paired_rules := array_append(v_processed_paired_rules, v_paired_rule.id);
                
                -- Generate paired transactions for each occurrence
                WHILE v_next_occurrence <= p_today LOOP
                    IF v_rule.end_date IS NOT NULL AND v_next_occurrence > v_rule.end_date THEN
                        EXIT;
                    END IF;
                    
                    -- Generate outgoing transaction (first rule)
                    v_new_txn_id := gen_random_uuid();
                    INSERT INTO public.transaction (
                        id, user_id, account_id, category_id, flow_type, amount, description,
                        date, recurring_transaction_id, system_generated_key, created_at, updated_at
                    ) VALUES (
                        v_new_txn_id, p_user_id, v_rule.account_id, v_rule.category_id, 
                        v_rule.flow_type, v_rule.amount, v_rule.description,
                        v_next_occurrence, v_rule.id, 'recurring_sync', NOW(), NOW()
                    );
                    
                    -- Generate incoming transaction (paired rule)
                    v_paired_txn_id := gen_random_uuid();
                    INSERT INTO public.transaction (
                        id, user_id, account_id, category_id, flow_type, amount, description,
                        date, recurring_transaction_id, paired_transaction_id, system_generated_key, created_at, updated_at
                    ) VALUES (
                        v_paired_txn_id, p_user_id, v_paired_rule.account_id, v_paired_rule.category_id,
                        v_paired_rule.flow_type, v_paired_rule.amount, v_paired_rule.description,
                        v_next_occurrence, v_paired_rule.id, v_new_txn_id, 'recurring_sync', NOW(), NOW()
                    );
                    
                    -- Link outgoing to incoming
                    UPDATE public.transaction
                    SET paired_transaction_id = v_paired_txn_id
                    WHERE id = v_new_txn_id;
                    
                    v_transactions_count := v_transactions_count + 2;
                    
                    -- Track affected accounts (both accounts in the transfer)
                    IF NOT v_rule.account_id = ANY(v_affected_accounts) THEN
                        v_affected_accounts := array_append(v_affected_accounts, v_rule.account_id);
                    END IF;
                    IF NOT v_paired_rule.account_id = ANY(v_affected_accounts) THEN
                        v_affected_accounts := array_append(v_affected_accounts, v_paired_rule.account_id);
                    END IF;
                    
                    -- NOTE: Transfers do NOT affect budget consumption
                    -- (they use system category 'transfer' which shouldn't have budgets)
                    
                    -- Calculate next occurrence
                    CASE v_rule.frequency::text
                        WHEN 'daily' THEN v_next_occurrence := v_next_occurrence + (v_rule.interval || ' days')::INTERVAL;
                        WHEN 'weekly' THEN v_next_occurrence := v_next_occurrence + (v_rule.interval || ' weeks')::INTERVAL;
                        WHEN 'monthly' THEN v_next_occurrence := v_next_occurrence + (v_rule.interval || ' months')::INTERVAL;
                        WHEN 'yearly' THEN v_next_occurrence := v_next_occurrence + (v_rule.interval || ' years')::INTERVAL;
                        ELSE EXIT;
                    END CASE;
                END LOOP;
                
                -- Update next_run_date for BOTH rules
                UPDATE public.recurring_transaction
                SET next_run_date = v_next_occurrence, updated_at = NOW()
                WHERE id IN (v_rule.id, v_paired_rule.id);
                
            END IF;
            -- If paired rule not found/inactive, v_process_as_standalone remains TRUE
        END IF;
        
        -- Process as standalone recurring transaction (if not processed as paired)
        IF v_process_as_standalone THEN
            WHILE v_next_occurrence <= p_today LOOP
                IF v_rule.end_date IS NOT NULL AND v_next_occurrence > v_rule.end_date THEN
                    EXIT;
                END IF;
                
                -- Insert standalone transaction
                v_new_txn_id := gen_random_uuid();
                INSERT INTO public.transaction (
                    id, user_id, account_id, category_id, flow_type, amount, description,
                    date, recurring_transaction_id, system_generated_key, created_at, updated_at
                ) VALUES (
                    v_new_txn_id, p_user_id, v_rule.account_id, v_rule.category_id,
                    v_rule.flow_type, v_rule.amount, v_rule.description,
                    v_next_occurrence, v_rule.id, 'recurring_sync', NOW(), NOW()
                );
                
                v_transactions_count := v_transactions_count + 1;
                
                -- Track affected account
                IF NOT v_rule.account_id = ANY(v_affected_accounts) THEN
                    v_affected_accounts := array_append(v_affected_accounts, v_rule.account_id);
                END IF;
                
                -- Track affected category for budget updates (only for OUTCOME transactions)
                IF v_rule.flow_type::text = 'outcome' AND NOT v_rule.category_id = ANY(v_affected_categories) THEN
                    v_affected_categories := array_append(v_affected_categories, v_rule.category_id);
                END IF;
                
                -- Calculate next occurrence
                CASE v_rule.frequency::text
                    WHEN 'daily' THEN v_next_occurrence := v_next_occurrence + (v_rule.interval || ' days')::INTERVAL;
                    WHEN 'weekly' THEN v_next_occurrence := v_next_occurrence + (v_rule.interval || ' weeks')::INTERVAL;
                    WHEN 'monthly' THEN v_next_occurrence := v_next_occurrence + (v_rule.interval || ' months')::INTERVAL;
                    WHEN 'yearly' THEN v_next_occurrence := v_next_occurrence + (v_rule.interval || ' years')::INTERVAL;
                    ELSE EXIT;
                END CASE;
            END LOOP;
            
            -- Update next_run_date
            UPDATE public.recurring_transaction
            SET next_run_date = v_next_occurrence, updated_at = NOW()
            WHERE id = v_rule.id;
        END IF;
    END LOOP;
    
    -- =========================================================================
    -- PHASE 2: Update account balances (batch, once per affected account)
    -- =========================================================================
    
    FOREACH v_account_id IN ARRAY v_affected_accounts LOOP
        -- Recompute balance: income - outcome
        UPDATE public.account a
        SET cached_balance = (
            SELECT COALESCE(SUM(
                CASE WHEN t.flow_type = 'income' THEN t.amount ELSE -t.amount END
            ), 0)
            FROM public.transaction t
            WHERE t.account_id = a.id
              AND t.user_id = p_user_id
              AND t.deleted_at IS NULL
        ),
        updated_at = NOW()
        WHERE a.id = v_account_id AND a.user_id = p_user_id;
        
        v_accounts_updated := v_accounts_updated + 1;
    END LOOP;
    
    -- =========================================================================
    -- PHASE 3: Update budget consumption (batch, once per affected category)
    -- Only for outcome transactions - income doesn't affect budget consumption
    -- Transfers are excluded because they use system category 'transfer'
    -- =========================================================================
    
    FOREACH v_category_id IN ARRAY v_affected_categories LOOP
        -- Find and update all active budgets tracking this category
        UPDATE public.budget b
        SET cached_consumption = (
            SELECT COALESCE(SUM(t.amount), 0)
            FROM public.transaction t
            JOIN public.budget_category bc ON t.category_id = bc.category_id
            WHERE bc.budget_id = b.id
              AND bc.user_id = p_user_id
              AND t.user_id = p_user_id
              AND t.flow_type = 'outcome'
              AND t.deleted_at IS NULL
              -- Use current period boundaries based on budget frequency
              AND t.date >= CASE b.frequency
                  WHEN 'daily' THEN CURRENT_DATE
                  WHEN 'weekly' THEN b.start_date + ((CURRENT_DATE - b.start_date) / (7 * b.interval)) * (7 * b.interval)
                  WHEN 'monthly' THEN (b.start_date + (((CURRENT_DATE - b.start_date) / 30) / b.interval) * b.interval * INTERVAL '1 month')::DATE
                  WHEN 'yearly' THEN (b.start_date + ((EXTRACT(YEAR FROM CURRENT_DATE) - EXTRACT(YEAR FROM b.start_date))::INT / b.interval * b.interval) * INTERVAL '1 year')::DATE
                  WHEN 'once' THEN b.start_date
                  ELSE CURRENT_DATE
              END
              AND t.date <= CASE b.frequency
                  WHEN 'daily' THEN CURRENT_DATE
                  WHEN 'weekly' THEN (b.start_date + ((CURRENT_DATE - b.start_date) / (7 * b.interval)) * (7 * b.interval) + (7 * b.interval) - 1)
                  WHEN 'monthly' THEN ((b.start_date + (((CURRENT_DATE - b.start_date) / 30) / b.interval) * b.interval * INTERVAL '1 month') + b.interval * INTERVAL '1 month' - INTERVAL '1 day')::DATE
                  WHEN 'yearly' THEN ((b.start_date + ((EXTRACT(YEAR FROM CURRENT_DATE) - EXTRACT(YEAR FROM b.start_date))::INT / b.interval * b.interval) * INTERVAL '1 year') + b.interval * INTERVAL '1 year' - INTERVAL '1 day')::DATE
                  WHEN 'once' THEN COALESCE(b.end_date, '9999-12-31'::DATE)
                  ELSE CURRENT_DATE
              END
        ),
        updated_at = NOW()
        WHERE b.id IN (
            SELECT bc.budget_id 
            FROM public.budget_category bc 
            WHERE bc.category_id = v_category_id AND bc.user_id = p_user_id
        )
        AND b.user_id = p_user_id
        AND b.is_active = TRUE
        AND b.deleted_at IS NULL;
        
        v_budgets_updated := v_budgets_updated + (SELECT COUNT(*)::INT FROM public.budget_category WHERE category_id = v_category_id AND user_id = p_user_id);
    END LOOP;
    
    -- Return summary
    RETURN QUERY SELECT v_transactions_count, v_rules_count, v_accounts_updated, v_budgets_updated;
END;
$$;

COMMENT ON FUNCTION public.sync_recurring_transactions(UUID, DATE) IS 
  'Generates pending transactions from recurring templates. Handles paired transfers (links via paired_transaction_id), updates account balances, and updates budget consumption for outcome transactions. Efficient: batches updates per account/category.';

-- ---------------------------------------------------------
-- 4.2 create_recurring_transfer
-- Create paired recurring templates for a transfer
-- ---------------------------------------------------------

CREATE OR REPLACE FUNCTION public.create_recurring_transfer(
    p_user_id UUID,
    p_from_account_id UUID,
    p_to_account_id UUID,
    p_amount NUMERIC(12,2),
    p_description_outgoing TEXT,
    p_description_incoming TEXT,
    p_frequency TEXT,
    p_interval INT,
    p_start_date DATE,
    p_by_weekday TEXT[],
    p_by_monthday INT[],
    p_end_date DATE,
    p_is_active BOOLEAN,
    p_transfer_category_id UUID
)
RETURNS TABLE(
    outgoing_rule_id UUID,
    incoming_rule_id UUID
)
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = ''
AS $$
DECLARE
    v_outgoing_id UUID;
    v_incoming_id UUID;
BEGIN
    -- Validate accounts
    IF NOT EXISTS (
        SELECT 1 FROM public.account 
        WHERE id = p_from_account_id AND user_id = p_user_id AND deleted_at IS NULL
    ) THEN
        RAISE EXCEPTION 'Source account not found or not accessible';
    END IF;
    
    IF NOT EXISTS (
        SELECT 1 FROM public.account 
        WHERE id = p_to_account_id AND user_id = p_user_id AND deleted_at IS NULL
    ) THEN
        RAISE EXCEPTION 'Destination account not found or not accessible';
    END IF;
    
    -- Validate frequency
    IF p_frequency NOT IN ('daily', 'weekly', 'monthly', 'yearly') THEN
        RAISE EXCEPTION 'Invalid frequency. Must be daily, weekly, monthly, or yearly';
    END IF;
    
    -- Create outgoing recurring rule
    INSERT INTO public.recurring_transaction (
        user_id,
        account_id,
        category_id,
        flow_type,
        amount,
        description,
        frequency,
        interval,
        start_date,
        next_run_date,
        by_weekday,
        by_monthday,
        end_date,
        is_active
    ) VALUES (
        p_user_id,
        p_from_account_id,
        p_transfer_category_id,
        'outcome'::public.flow_type_enum,
        p_amount,
        p_description_outgoing,
        p_frequency::public.recurring_frequency_enum,
        p_interval,
        p_start_date,
        p_start_date,
        p_by_weekday,
        p_by_monthday,
        p_end_date,
        p_is_active
    ) RETURNING id INTO v_outgoing_id;
    
    -- Create incoming recurring rule
    INSERT INTO public.recurring_transaction (
        user_id,
        account_id,
        category_id,
        flow_type,
        amount,
        description,
        frequency,
        interval,
        start_date,
        next_run_date,
        by_weekday,
        by_monthday,
        end_date,
        is_active,
        paired_recurring_transaction_id
    ) VALUES (
        p_user_id,
        p_to_account_id,
        p_transfer_category_id,
        'income'::public.flow_type_enum,
        p_amount,
        p_description_incoming,
        p_frequency::public.recurring_frequency_enum,
        p_interval,
        p_start_date,
        p_start_date,
        p_by_weekday,
        p_by_monthday,
        p_end_date,
        p_is_active,
        v_outgoing_id
    ) RETURNING id INTO v_incoming_id;
    
    -- Link outgoing to incoming
    UPDATE public.recurring_transaction
    SET paired_recurring_transaction_id = v_incoming_id
    WHERE id = v_outgoing_id;
    
    -- Return both IDs
    outgoing_rule_id := v_outgoing_id;
    incoming_rule_id := v_incoming_id;
    RETURN NEXT;
END;
$$;

COMMENT ON FUNCTION public.create_recurring_transfer IS 
  'Creates paired recurring transaction templates for an automatic recurring transfer.';

-- ---------------------------------------------------------
-- 4.3 delete_recurring_transaction
-- Soft-delete a recurring template
-- ---------------------------------------------------------

CREATE OR REPLACE FUNCTION public.delete_recurring_transaction(
    p_recurring_transaction_id UUID,
    p_user_id UUID,
    p_also_delete_pair BOOLEAN DEFAULT FALSE
)
RETURNS TABLE(
    recurring_transaction_soft_deleted BOOLEAN,
    deleted_at TIMESTAMPTZ,
    paired_template_also_deleted BOOLEAN
)
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = ''
AS $$
DECLARE
    v_deleted_at TIMESTAMPTZ;
    v_paired_id UUID;
    v_paired_deleted BOOLEAN := FALSE;
BEGIN
    -- Validate recurring transaction exists and belongs to user
    IF NOT EXISTS (
        SELECT 1 FROM public.recurring_transaction 
        WHERE id = p_recurring_transaction_id AND user_id = p_user_id AND deleted_at IS NULL
    ) THEN
        RAISE EXCEPTION 'Recurring transaction not found, already deleted, or not accessible';
    END IF;
    
    -- Check for paired template
    SELECT paired_recurring_transaction_id INTO v_paired_id
    FROM public.recurring_transaction
    WHERE id = p_recurring_transaction_id;
    
    v_deleted_at := now();
    
    -- Soft-delete the recurring transaction
    UPDATE public.recurring_transaction
    SET 
        deleted_at = v_deleted_at,
        updated_at = v_deleted_at,
        is_active = FALSE
    WHERE id = p_recurring_transaction_id AND user_id = p_user_id;
    
    -- Delete pair if requested
    IF v_paired_id IS NOT NULL AND p_also_delete_pair THEN
        UPDATE public.recurring_transaction
        SET 
            deleted_at = v_deleted_at,
            updated_at = v_deleted_at,
            is_active = FALSE
        WHERE id = v_paired_id AND user_id = p_user_id AND deleted_at IS NULL;
        
        v_paired_deleted := (FOUND);
    END IF;
    
    -- Return results
    recurring_transaction_soft_deleted := TRUE;
    deleted_at := v_deleted_at;
    paired_template_also_deleted := v_paired_deleted;
    RETURN NEXT;
END;
$$;

COMMENT ON FUNCTION public.delete_recurring_transaction(UUID, UUID, BOOLEAN) IS 
  'Soft-deletes a recurring transaction template. Optionally deletes paired template too.';

-- ---------------------------------------------------------
-- 4.4 delete_recurring_and_pair
-- Delete both paired recurring templates (legacy function)
-- ---------------------------------------------------------

CREATE OR REPLACE FUNCTION public.delete_recurring_and_pair(
    p_recurring_id UUID,
    p_user_id UUID
)
RETURNS TABLE(
    success BOOLEAN,
    paired_deleted BOOLEAN
)
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = ''
AS $$
DECLARE
  v_paired UUID;
BEGIN
  -- Fetch paired id and validate ownership
  SELECT paired_recurring_transaction_id INTO v_paired
  FROM public.recurring_transaction
  WHERE id = p_recurring_id AND user_id = p_user_id AND deleted_at IS NULL
  LIMIT 1;

  IF NOT FOUND THEN
    RAISE EXCEPTION 'recurring transaction not found or not owned by user';
  END IF;

  -- Soft-delete main rule
  UPDATE public.recurring_transaction
  SET deleted_at = now(), updated_at = now(), is_active = FALSE
  WHERE id = p_recurring_id AND user_id = p_user_id;

  IF NOT FOUND THEN
    success := FALSE;
    paired_deleted := FALSE;
    RETURN NEXT;
    RETURN;
  END IF;

  paired_deleted := FALSE;

  -- Soft-delete paired rule if exists
  IF v_paired IS NOT NULL THEN
    UPDATE public.recurring_transaction
    SET deleted_at = now(), updated_at = now(), is_active = FALSE
    WHERE id = v_paired AND user_id = p_user_id AND deleted_at IS NULL;
    
    IF FOUND THEN
      paired_deleted := TRUE;
    ELSE
      RAISE NOTICE 'Paired recurring transaction % not deleted (not found or different owner)', v_paired;
    END IF;
  END IF;

  success := TRUE;
  RETURN NEXT;
END;
$$;

COMMENT ON FUNCTION public.delete_recurring_and_pair(UUID, UUID) IS 
  'Soft-deletes a recurring template and its paired template atomically.';

-- =========================================================
-- SECTION 5: CATEGORY MANAGEMENT RPCs
-- =========================================================

-- ---------------------------------------------------------
-- 5.1 delete_category_reassign
-- Delete category and reassign transactions
-- ---------------------------------------------------------

CREATE OR REPLACE FUNCTION public.delete_category_reassign(
  p_category_id UUID, 
  p_user_id UUID,
  p_cascade BOOLEAN DEFAULT FALSE
)
RETURNS TABLE(
    transactions_reassigned INT,
    budget_links_removed INT,
    transactions_deleted INT
)
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = ''
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
  FROM public.category
  WHERE id = p_category_id AND user_id = p_user_id;

  IF v_category_flow_type IS NULL THEN
    RAISE EXCEPTION 'category not found or not owned by user';
  END IF;

  -- If cascade mode, delete all transactions
  IF p_cascade THEN
    UPDATE public.transaction
    SET deleted_at = now(), updated_at = now()
    WHERE category_id = p_category_id AND user_id = p_user_id AND deleted_at IS NULL;
    GET DIAGNOSTICS v_deleted_count = ROW_COUNT;
    
    v_txn_count := 0;
  ELSE
    -- Find matching general category
    SELECT id INTO v_general_category_id
    FROM public.category
    WHERE key = 'general' 
      AND user_id IS NULL 
      AND flow_type = v_category_flow_type::public.flow_type_enum
    LIMIT 1;

    IF v_general_category_id IS NULL THEN
      RAISE EXCEPTION 'system general category not found for flow_type=%', v_category_flow_type;
    END IF;

    -- Reassign transactions
    UPDATE public.transaction
    SET category_id = v_general_category_id, updated_at = now()
    WHERE category_id = p_category_id AND user_id = p_user_id AND deleted_at IS NULL;
    GET DIAGNOSTICS v_txn_count = ROW_COUNT;
  END IF;

  -- Remove budget_category links
  DELETE FROM public.budget_category
  WHERE category_id = p_category_id AND user_id = p_user_id;
  GET DIAGNOSTICS v_links_count = ROW_COUNT;

  -- Delete the category (hard delete for categories)
  DELETE FROM public.category
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

COMMENT ON FUNCTION public.delete_category_reassign(UUID, UUID, BOOLEAN) IS 
  'Deletes a user category. Transactions are reassigned to system general category (or deleted if cascade=true).';

-- =========================================================
-- SECTION 6: WISHLIST RPCs
-- =========================================================

-- ---------------------------------------------------------
-- 6.1 create_wishlist_with_items
-- Create wishlist and items atomically
-- ---------------------------------------------------------

CREATE OR REPLACE FUNCTION public.create_wishlist_with_items(
    p_user_id UUID,
    p_goal_title TEXT,
    p_budget_hint NUMERIC(12,2),
    p_currency_code TEXT,
    p_target_date DATE,
    p_preferred_store TEXT,
    p_user_note TEXT,
    p_items JSONB
)
RETURNS TABLE(
    wishlist_id UUID,
    items_created INTEGER
)
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = ''
AS $$
DECLARE
    v_wishlist_id UUID;
    v_item JSONB;
    v_items_count INTEGER := 0;
BEGIN
    -- Create wishlist
    INSERT INTO public.wishlist (
        user_id,
        goal_title,
        budget_hint,
        currency_code,
        target_date,
        preferred_store,
        user_note,
        status
    ) VALUES (
        p_user_id,
        p_goal_title,
        p_budget_hint,
        p_currency_code,
        p_target_date,
        p_preferred_store,
        p_user_note,
        'active'::public.wishlist_status_enum
    ) RETURNING id INTO v_wishlist_id;
    
    -- Create items
    IF p_items IS NOT NULL AND jsonb_array_length(p_items) > 0 THEN
        FOR v_item IN SELECT * FROM jsonb_array_elements(p_items)
        LOOP
            INSERT INTO public.wishlist_item (
                wishlist_id,
                product_title,
                price_total,
                seller_name,
                url,
                pickup_available,
                warranty_info,
                copy_for_user,
                badges
            ) VALUES (
                v_wishlist_id,
                (v_item->>'product_title')::TEXT,
                (v_item->>'price_total')::NUMERIC(12,2),
                (v_item->>'seller_name')::TEXT,
                (v_item->>'url')::TEXT,
                (v_item->>'pickup_available')::BOOLEAN,
                NULLIF(v_item->>'warranty_info', '')::TEXT,
                (v_item->>'copy_for_user')::TEXT,
                (v_item->'badges')::JSONB
            );
            
            v_items_count := v_items_count + 1;
        END LOOP;
    END IF;
    
    -- Return results
    wishlist_id := v_wishlist_id;
    items_created := v_items_count;
    RETURN NEXT;
END;
$$;

COMMENT ON FUNCTION public.create_wishlist_with_items IS 
  'Atomically creates a wishlist with initial items from recommendation results.';

-- =========================================================
-- SECTION 7: SOFT-DELETE RPCs (Invoice, Budget)
-- =========================================================

-- ---------------------------------------------------------
-- 7.1 delete_invoice
-- Soft-delete an invoice
-- ---------------------------------------------------------

CREATE OR REPLACE FUNCTION public.delete_invoice(
    p_invoice_id UUID,
    p_user_id UUID
)
RETURNS TABLE(
    invoice_soft_deleted BOOLEAN,
    deleted_at TIMESTAMPTZ
)
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = ''
AS $$
DECLARE
    v_deleted_at TIMESTAMPTZ;
BEGIN
    -- Validate invoice exists and belongs to user
    IF NOT EXISTS (
        SELECT 1 FROM public.invoice 
        WHERE id = p_invoice_id AND user_id = p_user_id AND deleted_at IS NULL
    ) THEN
        RAISE EXCEPTION 'Invoice not found, already deleted, or not accessible';
    END IF;
    
    v_deleted_at := now();
    
    -- Soft-delete the invoice
    UPDATE public.invoice
    SET deleted_at = v_deleted_at, updated_at = v_deleted_at
    WHERE id = p_invoice_id AND user_id = p_user_id;
    
    -- Return results
    invoice_soft_deleted := TRUE;
    deleted_at := v_deleted_at;
    RETURN NEXT;
END;
$$;

COMMENT ON FUNCTION public.delete_invoice(UUID, UUID) IS 
  'Soft-deletes an invoice. Storage cleanup should be handled by backend service layer.';

-- ---------------------------------------------------------
-- 7.2 delete_budget
-- Soft-delete a budget
-- ---------------------------------------------------------

CREATE OR REPLACE FUNCTION public.delete_budget(
    p_budget_id UUID,
    p_user_id UUID
)
RETURNS TABLE(
    budget_soft_deleted BOOLEAN,
    deleted_at TIMESTAMPTZ
)
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = ''
AS $$
DECLARE
    v_deleted_at TIMESTAMPTZ;
BEGIN
    -- Validate budget exists and belongs to user
    IF NOT EXISTS (
        SELECT 1 FROM public.budget 
        WHERE id = p_budget_id AND user_id = p_user_id AND deleted_at IS NULL
    ) THEN
        RAISE EXCEPTION 'Budget not found, already deleted, or not accessible';
    END IF;
    
    v_deleted_at := now();
    
    -- Soft-delete the budget
    UPDATE public.budget
    SET deleted_at = v_deleted_at, updated_at = v_deleted_at, is_active = FALSE
    WHERE id = p_budget_id AND user_id = p_user_id;
    
    -- Return results
    budget_soft_deleted := TRUE;
    deleted_at := v_deleted_at;
    RETURN NEXT;
END;
$$;

COMMENT ON FUNCTION public.delete_budget(UUID, UUID) IS 
  'Soft-deletes a budget. Budget_category links remain for historical analysis.';

-- =========================================================
-- SECTION 8: CACHE RECOMPUTATION RPCs
-- =========================================================

-- ---------------------------------------------------------
-- 8.1 recompute_account_balance
-- Recalculate account cached_balance from transactions
-- ---------------------------------------------------------

CREATE OR REPLACE FUNCTION public.recompute_account_balance(
    p_account_id UUID,
    p_user_id UUID
)
RETURNS NUMERIC(12,2)
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = ''
AS $$
DECLARE
    v_balance NUMERIC(12,2);
BEGIN
    -- Validate account exists and belongs to user
    IF NOT EXISTS (
        SELECT 1 FROM public.account 
        WHERE id = p_account_id AND user_id = p_user_id
    ) THEN
        RAISE EXCEPTION 'Account not found or not accessible';
    END IF;
    
    -- Calculate balance from transactions
    SELECT COALESCE(
        SUM(
            CASE 
                WHEN flow_type = 'income' THEN amount
                WHEN flow_type = 'outcome' THEN -amount
                ELSE 0
            END
        ), 0
    ) INTO v_balance
    FROM public.transaction
    WHERE account_id = p_account_id 
      AND user_id = p_user_id 
      AND deleted_at IS NULL;
    
    -- Update cached_balance
    UPDATE public.account
    SET cached_balance = v_balance, updated_at = now()
    WHERE id = p_account_id AND user_id = p_user_id;
    
    RETURN v_balance;
END;
$$;

COMMENT ON FUNCTION public.recompute_account_balance(UUID, UUID) IS 
  'Recalculates account.cached_balance from transaction history. Returns new balance.';

-- ---------------------------------------------------------
-- 8.2 recompute_budget_consumption
-- Recalculate budget cached_consumption for a period
-- ---------------------------------------------------------

CREATE OR REPLACE FUNCTION public.recompute_budget_consumption(
    p_budget_id UUID,
    p_user_id UUID,
    p_period_start DATE,
    p_period_end DATE
)
RETURNS NUMERIC(12,2)
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = ''
AS $$
DECLARE
    v_consumption NUMERIC(12,2);
BEGIN
    -- Validate budget exists and belongs to user
    IF NOT EXISTS (
        SELECT 1 FROM public.budget 
        WHERE id = p_budget_id AND user_id = p_user_id AND deleted_at IS NULL
    ) THEN
        RAISE EXCEPTION 'Budget not found or not accessible';
    END IF;
    
    -- Validate date range
    IF p_period_start > p_period_end THEN
        RAISE EXCEPTION 'Invalid date range: start date must be before end date';
    END IF;
    
    -- Calculate consumption from transactions in linked categories
    SELECT COALESCE(SUM(t.amount), 0) INTO v_consumption
    FROM public.transaction t
    JOIN public.budget_category bc ON t.category_id = bc.category_id
    WHERE bc.budget_id = p_budget_id
      AND bc.user_id = p_user_id
      AND t.user_id = p_user_id
      AND t.flow_type = 'outcome'
      AND t.deleted_at IS NULL
      AND t.date >= p_period_start
      AND t.date <= p_period_end;
    
    -- Update cached_consumption
    UPDATE public.budget
    SET cached_consumption = v_consumption, updated_at = now()
    WHERE id = p_budget_id AND user_id = p_user_id;
    
    RETURN v_consumption;
END;
$$;

COMMENT ON FUNCTION public.recompute_budget_consumption(UUID, UUID, DATE, DATE) IS 
  'Recalculates budget.cached_consumption for a given period. Returns new consumption.';

-- ---------------------------------------------------------
-- 8.3 recompute_budgets_for_category
-- Find and recompute all budgets tracking a specific category
-- Called after transaction CRUD to keep budget data in sync
-- ---------------------------------------------------------

CREATE OR REPLACE FUNCTION public.recompute_budgets_for_category(
    p_user_id UUID,
    p_category_id UUID
)
RETURNS TABLE (
    budget_id UUID,
    budget_name TEXT,
    old_consumption NUMERIC(12,2),
    new_consumption NUMERIC(12,2)
)
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = ''
AS $$
DECLARE
    v_budget RECORD;
    v_old_consumption NUMERIC(12,2);
    v_new_consumption NUMERIC(12,2);
    v_period_start DATE;
    v_period_end DATE;
    v_today DATE := CURRENT_DATE;
BEGIN
    -- Find all active budgets that track this category
    FOR v_budget IN
        SELECT DISTINCT b.id, b.name, b.frequency, b.interval, b.start_date, b.end_date, b.cached_consumption
        FROM public.budget b
        JOIN public.budget_category bc ON bc.budget_id = b.id
        WHERE bc.category_id = p_category_id
          AND bc.user_id = p_user_id
          AND b.user_id = p_user_id
          AND b.is_active = TRUE
          AND b.deleted_at IS NULL
    LOOP
        v_old_consumption := v_budget.cached_consumption;
        
        -- Calculate period boundaries based on budget frequency
        CASE v_budget.frequency
            WHEN 'daily' THEN
                v_period_start := v_today;
                v_period_end := v_today;
            WHEN 'weekly' THEN
                -- Find the start of the current week relative to budget start_date
                v_period_start := v_budget.start_date + 
                    ((v_today - v_budget.start_date) / (7 * v_budget.interval)) * (7 * v_budget.interval);
                v_period_end := v_period_start + (7 * v_budget.interval) - 1;
            WHEN 'monthly' THEN
                -- Find the start of the current month period
                v_period_start := v_budget.start_date + 
                    (((v_today - v_budget.start_date) / 30) / v_budget.interval) * v_budget.interval * INTERVAL '1 month';
                v_period_end := v_period_start + v_budget.interval * INTERVAL '1 month' - INTERVAL '1 day';
            WHEN 'yearly' THEN
                -- Find the start of the current yearly period
                v_period_start := v_budget.start_date + 
                    (EXTRACT(YEAR FROM v_today) - EXTRACT(YEAR FROM v_budget.start_date))::INT / v_budget.interval * v_budget.interval * INTERVAL '1 year';
                v_period_end := v_period_start + v_budget.interval * INTERVAL '1 year' - INTERVAL '1 day';
            WHEN 'once' THEN
                -- One-time budget: use start_date to end_date or infinity
                v_period_start := v_budget.start_date;
                v_period_end := COALESCE(v_budget.end_date, '9999-12-31'::DATE);
            ELSE
                -- Default to daily if unknown frequency
                v_period_start := v_today;
                v_period_end := v_today;
        END CASE;
        
        -- Respect end_date if set
        IF v_budget.end_date IS NOT NULL AND v_period_end > v_budget.end_date THEN
            v_period_end := v_budget.end_date;
        END IF;
        
        -- Calculate consumption from transactions in ALL linked categories for this budget
        SELECT COALESCE(SUM(t.amount), 0) INTO v_new_consumption
        FROM public.transaction t
        JOIN public.budget_category bc ON t.category_id = bc.category_id
        WHERE bc.budget_id = v_budget.id
          AND bc.user_id = p_user_id
          AND t.user_id = p_user_id
          AND t.flow_type = 'outcome'
          AND t.deleted_at IS NULL
          AND t.date >= v_period_start
          AND t.date <= v_period_end;
        
        -- Update the budget's cached_consumption
        UPDATE public.budget
        SET cached_consumption = v_new_consumption, updated_at = NOW()
        WHERE id = v_budget.id AND user_id = p_user_id;
        
        -- Return result row
        budget_id := v_budget.id;
        budget_name := v_budget.name;
        old_consumption := v_old_consumption;
        new_consumption := v_new_consumption;
        RETURN NEXT;
    END LOOP;
    
    RETURN;
END;
$$;

COMMENT ON FUNCTION public.recompute_budgets_for_category(UUID, UUID) IS 
  'Finds all active budgets tracking a category and recomputes their cached_consumption. '
  'Called after transaction create/update/delete to keep budget data in sync.';

-- =========================================================
-- SECTION 9: CURRENCY VALIDATION RPCs
-- =========================================================

-- ---------------------------------------------------------
-- 9.1 validate_user_currency
-- Validate currency matches user profile
-- ---------------------------------------------------------

CREATE OR REPLACE FUNCTION public.validate_user_currency(
    p_user_id UUID,
    p_currency TEXT
)
RETURNS BOOLEAN
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = ''
AS $$
DECLARE
    v_user_currency TEXT;
BEGIN
    -- Get user's currency preference
    SELECT currency_preference INTO v_user_currency
    FROM public.profile
    WHERE user_id = p_user_id;
    
    IF v_user_currency IS NULL THEN
        RAISE EXCEPTION 'User profile not found for user_id: %', p_user_id;
    END IF;
    
    IF p_currency != v_user_currency THEN
        RAISE EXCEPTION 'Currency mismatch: provided "%" but user currency is "%". Single-currency-per-user policy enforced.', 
            p_currency, v_user_currency;
    END IF;
    
    RETURN TRUE;
END;
$$;

COMMENT ON FUNCTION public.validate_user_currency(UUID, TEXT) IS 
  'Validates that currency matches user profile. Raises exception on mismatch.';

-- ---------------------------------------------------------
-- 9.2 get_user_currency
-- Get user's currency preference
-- ---------------------------------------------------------

CREATE OR REPLACE FUNCTION public.get_user_currency(
    p_user_id UUID
)
RETURNS TEXT
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = ''
AS $$
DECLARE
    v_currency TEXT;
BEGIN
    SELECT currency_preference INTO v_currency
    FROM public.profile
    WHERE user_id = p_user_id;
    
    IF v_currency IS NULL THEN
        RAISE EXCEPTION 'User profile not found for user_id: %', p_user_id;
    END IF;
    
    RETURN v_currency;
END;
$$;

COMMENT ON FUNCTION public.get_user_currency(UUID) IS 
  'Returns user currency_preference from profile. Used to auto-populate currency fields.';

-- ---------------------------------------------------------
-- 9.3 can_change_user_currency
-- Check if user can safely change their currency
-- ---------------------------------------------------------

CREATE OR REPLACE FUNCTION public.can_change_user_currency(
    p_user_id UUID
)
RETURNS BOOLEAN
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = ''
AS $$
DECLARE
    v_has_accounts BOOLEAN;
    v_has_wishlists BOOLEAN;
    v_has_budgets BOOLEAN;
BEGIN
    -- Check for non-deleted accounts
    SELECT EXISTS(
        SELECT 1 FROM public.account 
        WHERE user_id = p_user_id AND deleted_at IS NULL
    ) INTO v_has_accounts;
    
    -- Check for wishlists (no soft-delete)
    SELECT EXISTS(
        SELECT 1 FROM public.wishlist 
        WHERE user_id = p_user_id
    ) INTO v_has_wishlists;
    
    -- Check for non-deleted budgets
    SELECT EXISTS(
        SELECT 1 FROM public.budget 
        WHERE user_id = p_user_id AND deleted_at IS NULL
    ) INTO v_has_budgets;
    
    -- User can change currency only if they have no financial data
    RETURN NOT (v_has_accounts OR v_has_wishlists OR v_has_budgets);
END;
$$;

COMMENT ON FUNCTION public.can_change_user_currency(UUID) IS 
  'Returns true if user can safely change currency_preference (no existing financial data).';

-- =========================================================
-- SECTION 10: FAVORITE ACCOUNT RPCs
-- =========================================================

-- ---------------------------------------------------------
-- 10.1 set_favorite_account
-- Set an account as the user's favorite
-- ---------------------------------------------------------

CREATE OR REPLACE FUNCTION public.set_favorite_account(
    p_account_id UUID,
    p_user_id UUID
)
RETURNS TABLE(
    previous_favorite_id UUID,
    new_favorite_id UUID,
    success BOOLEAN
)
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = ''
AS $$
DECLARE
    v_previous_favorite_id UUID;
    v_account_owner UUID;
BEGIN
    -- Validate account exists and belongs to user
    SELECT user_id INTO v_account_owner
    FROM public.account
    WHERE id = p_account_id
      AND deleted_at IS NULL;
    
    IF v_account_owner IS NULL THEN
        RAISE EXCEPTION 'Account not found: %', p_account_id;
    END IF;
    
    IF v_account_owner != p_user_id THEN
        RAISE EXCEPTION 'Account % does not belong to user %', p_account_id, p_user_id;
    END IF;
    
    -- Find current favorite (if any)
    SELECT id INTO v_previous_favorite_id
    FROM public.account
    WHERE user_id = p_user_id
      AND is_favorite = TRUE
      AND deleted_at IS NULL;
    
    -- If the requested account is already favorite, no-op
    IF v_previous_favorite_id = p_account_id THEN
        RETURN QUERY SELECT 
            NULL::UUID AS previous_favorite_id,
            p_account_id AS new_favorite_id,
            TRUE AS success;
        RETURN;
    END IF;
    
    -- Unset previous favorite (if any)
    IF v_previous_favorite_id IS NOT NULL THEN
        UPDATE public.account
        SET is_favorite = FALSE, updated_at = now()
        WHERE id = v_previous_favorite_id;
    END IF;
    
    -- Set new favorite
    UPDATE public.account
    SET is_favorite = TRUE, updated_at = now()
    WHERE id = p_account_id;
    
    RETURN QUERY SELECT 
        v_previous_favorite_id AS previous_favorite_id,
        p_account_id AS new_favorite_id,
        TRUE AS success;
END;
$$;

COMMENT ON FUNCTION public.set_favorite_account(UUID, UUID) IS 
  'Sets an account as favorite for a user, automatically unsetting any previous favorite.';

-- ---------------------------------------------------------
-- 10.2 clear_favorite_account
-- Clear favorite status from an account
-- ---------------------------------------------------------

CREATE OR REPLACE FUNCTION public.clear_favorite_account(
    p_account_id UUID,
    p_user_id UUID
)
RETURNS TABLE(
    cleared BOOLEAN
)
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = ''
AS $$
DECLARE
    v_account_owner UUID;
    v_is_favorite BOOLEAN;
BEGIN
    -- Validate account exists and belongs to user
    SELECT user_id, is_favorite INTO v_account_owner, v_is_favorite
    FROM public.account
    WHERE id = p_account_id
      AND deleted_at IS NULL;
    
    IF v_account_owner IS NULL THEN
        RAISE EXCEPTION 'Account not found: %', p_account_id;
    END IF;
    
    IF v_account_owner != p_user_id THEN
        RAISE EXCEPTION 'Account % does not belong to user %', p_account_id, p_user_id;
    END IF;
    
    -- If not favorite, no-op
    IF NOT v_is_favorite THEN
        RETURN QUERY SELECT FALSE AS cleared;
        RETURN;
    END IF;
    
    -- Clear favorite
    UPDATE public.account
    SET is_favorite = FALSE, updated_at = now()
    WHERE id = p_account_id;
    
    RETURN QUERY SELECT TRUE AS cleared;
END;
$$;

COMMENT ON FUNCTION public.clear_favorite_account(UUID, UUID) IS 
  'Clears favorite status from an account. Returns whether status was changed.';

-- ---------------------------------------------------------
-- 10.3 get_favorite_account
-- Get user's favorite account
-- ---------------------------------------------------------

CREATE OR REPLACE FUNCTION public.get_favorite_account(
    p_user_id UUID
)
RETURNS UUID
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = ''
AS $$
DECLARE
    v_favorite_id UUID;
BEGIN
    SELECT id INTO v_favorite_id
    FROM public.account
    WHERE user_id = p_user_id
      AND is_favorite = TRUE
      AND deleted_at IS NULL;
    
    RETURN v_favorite_id;  -- Returns NULL if no favorite set
END;
$$;

COMMENT ON FUNCTION public.get_favorite_account(UUID) IS 
  'Returns the UUID of the user favorite account, or NULL if none set.';

-- =========================================================
-- SECTION 11: GRANT PERMISSIONS
-- =========================================================

-- Account Management
GRANT EXECUTE ON FUNCTION public.delete_account_reassign(UUID, UUID, UUID) TO authenticated;
GRANT EXECUTE ON FUNCTION public.delete_account_cascade(UUID, UUID) TO authenticated;

-- Transaction Management
GRANT EXECUTE ON FUNCTION public.delete_transaction(UUID, UUID) TO authenticated;

-- Transfer RPCs
GRANT EXECUTE ON FUNCTION public.create_transfer(UUID, UUID, UUID, NUMERIC, DATE, TEXT, UUID) TO authenticated;
GRANT EXECUTE ON FUNCTION public.delete_transfer(UUID, UUID) TO authenticated;
GRANT EXECUTE ON FUNCTION public.update_transfer(UUID, UUID, NUMERIC, DATE, TEXT) TO authenticated;

-- Recurring Transaction RPCs
GRANT EXECUTE ON FUNCTION public.sync_recurring_transactions(UUID, DATE) TO authenticated;
GRANT EXECUTE ON FUNCTION public.create_recurring_transfer(UUID, UUID, UUID, NUMERIC, TEXT, TEXT, TEXT, INT, DATE, TEXT[], INT[], DATE, BOOLEAN, UUID) TO authenticated;
GRANT EXECUTE ON FUNCTION public.delete_recurring_transaction(UUID, UUID, BOOLEAN) TO authenticated;
GRANT EXECUTE ON FUNCTION public.delete_recurring_and_pair(UUID, UUID) TO authenticated;

-- Category Management
GRANT EXECUTE ON FUNCTION public.delete_category_reassign(UUID, UUID, BOOLEAN) TO authenticated;

-- Wishlist RPCs
GRANT EXECUTE ON FUNCTION public.create_wishlist_with_items(UUID, TEXT, NUMERIC, TEXT, DATE, TEXT, TEXT, JSONB) TO authenticated;

-- Soft-Delete RPCs
GRANT EXECUTE ON FUNCTION public.delete_invoice(UUID, UUID) TO authenticated;
GRANT EXECUTE ON FUNCTION public.delete_budget(UUID, UUID) TO authenticated;

-- Cache Recomputation RPCs
GRANT EXECUTE ON FUNCTION public.recompute_account_balance(UUID, UUID) TO authenticated;
GRANT EXECUTE ON FUNCTION public.recompute_budget_consumption(UUID, UUID, DATE, DATE) TO authenticated;
GRANT EXECUTE ON FUNCTION public.recompute_budgets_for_category(UUID, UUID) TO authenticated;

-- Currency Validation RPCs
GRANT EXECUTE ON FUNCTION public.validate_user_currency(UUID, TEXT) TO authenticated;
GRANT EXECUTE ON FUNCTION public.get_user_currency(UUID) TO authenticated;
GRANT EXECUTE ON FUNCTION public.can_change_user_currency(UUID) TO authenticated;

-- Favorite Account RPCs
GRANT EXECUTE ON FUNCTION public.set_favorite_account(UUID, UUID) TO authenticated;
GRANT EXECUTE ON FUNCTION public.clear_favorite_account(UUID, UUID) TO authenticated;
GRANT EXECUTE ON FUNCTION public.get_favorite_account(UUID) TO authenticated;

-- =========================================================
-- End of RPC Functions Migration
-- =========================================================
