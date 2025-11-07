-- Migration: Create RPC function for atomic wishlist+items creation
-- Purpose: Create wishlist and items in a single atomic transaction
-- Date: 2025-11-07

CREATE OR REPLACE FUNCTION create_wishlist_with_items(
    p_user_id UUID,
    p_goal_title TEXT,
    p_budget_hint NUMERIC(12,2),
    p_currency_code TEXT,
    p_target_date DATE,
    p_preferred_store TEXT,
    p_user_note TEXT,
    p_items JSONB  -- Array of item objects
)
RETURNS TABLE(
    wishlist_id UUID,
    items_created INTEGER
)
LANGUAGE plpgsql
SECURITY DEFINER
AS $$
DECLARE
    v_wishlist_id UUID;
    v_item JSONB;
    v_items_count INTEGER := 0;
BEGIN
    -- Step 1: Create wishlist
    INSERT INTO wishlist (
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
        'active'
    ) RETURNING id INTO v_wishlist_id;
    
    -- Step 2: Create items (batch insert)
    -- Items are provided as JSONB array, each with required fields
    IF p_items IS NOT NULL AND jsonb_array_length(p_items) > 0 THEN
        FOR v_item IN SELECT * FROM jsonb_array_elements(p_items)
        LOOP
            INSERT INTO wishlist_item (
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
    
    -- Return wishlist ID and items count
    wishlist_id := v_wishlist_id;
    items_created := v_items_count;
    RETURN NEXT;
END;
$$;

GRANT EXECUTE ON FUNCTION create_wishlist_with_items(
    UUID, TEXT, NUMERIC(12,2), TEXT, DATE, TEXT, TEXT, JSONB
) TO authenticated;

COMMENT ON FUNCTION create_wishlist_with_items IS 
'Atomically creates a wishlist with its items in a single transaction.
This function must be called via Supabase RPC from the backend.
Returns wishlist_id and count of items created.
All operations succeed or fail together (true atomicity).
If items array is empty/null, only wishlist is created.';
