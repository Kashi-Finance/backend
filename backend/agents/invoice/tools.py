"""
InvoiceAgent Tool Implementations

These are the backend tools that InvoiceAgent can call during execution.
Each tool is documented with purpose, inputs, outputs, and security constraints.
"""

import logging
from typing import Dict, List

logger = logging.getLogger(__name__)


def get_user_profile(supabase_client, user_id: str) -> Dict:
    """
    Get user profile (country, currency_preference, locale).
    
    Fetches the user's profile from the database for localization and
    currency preference context.
    
    Args:
        supabase_client: Authenticated Supabase client (with user's JWT token)
        user_id: Authenticated user UUID from Supabase Auth
        
    Returns:
        Profile dict with country, currency_preference, locale
        Example: {
            "country": "GT",
            "currency_preference": "GTQ",
            "locale": "es-GT"
        }
        
    Security:
        - supabase_client MUST be created with user's JWT token via get_supabase_client()
        - RLS enforces user_id = auth.uid()
        - User can only access their own profile
    """
    logger.info(f"Fetching profile for user_id={user_id[:8]}...")
    
    try:
        # Query profile table using authenticated client (RLS enforced)
        result = (
            supabase_client.table("profile")
            .select("country, currency_preference, locale")
            .eq("user_id", user_id)
            .execute()
        )
        
        if not result.data or len(result.data) == 0:
            logger.warning(f"No profile found for user {user_id[:8]}, using defaults")
            # Return sensible defaults for Guatemala
            return {
                "country": "GT",
                "currency_preference": "GTQ",
                "locale": "es-GT"
            }
        
        profile = result.data[0]
        
        # Format profile data
        profile_data = {
            "country": profile.get("country", "GT"),
            "currency_preference": profile.get("currency_preference", "GTQ"),
            "locale": profile.get("locale", "es-GT")
        }
        
        logger.info(f"Fetched profile for user {user_id[:8]}: country={profile_data['country']}")
        return profile_data
        
    except Exception as e:
        logger.error(f"Error fetching profile for user {user_id[:8]}: {e}", exc_info=True)
        # Return fallback to prevent agent failure
        return {
            "country": "GT",
            "currency_preference": "GTQ",
            "locale": "es-GT"
        }


def get_user_categories(supabase_client, user_id: str) -> List[Dict]:
    """
    Get user's expense categories from the database.
    
    Fetches both system categories (user_id IS NULL) and user-specific categories.
    Returns categories with flow_type='outcome' since invoices are expenses.
    
    Args:
        supabase_client: Authenticated Supabase client (with user's JWT token)
        user_id: Authenticated user UUID from Supabase Auth
        
    Returns:
        List of category dicts with id and name fields
        Example: [
            {"id": "uuid-1", "name": "Supermercado"},
            {"id": "uuid-2", "name": "General"}
        ]
        
    Security:
        - supabase_client MUST be created with user's JWT token via get_supabase_client()
        - RLS enforces that users can only see their own categories plus system categories
        - Read-only; MUST NOT create categories
        
    Implementation:
        - Queries the 'category' table 
        - Fetches categories where (user_id = auth.uid() OR user_id IS NULL) AND flow_type = 'outcome'
        - RLS automatically enforces access control
    """
    logger.info(f"Fetching categories for user_id={user_id[:8]}...")
    
    try:
        # Query categories table using authenticated client (RLS enforced)
        # Fetch both system categories (user_id IS NULL) and user's personal categories
        result = (
            supabase_client.table("category")
            .select("id, name, flow_type, user_id")
            .eq("flow_type", "outcome")  # Only expense categories for invoices
            .or_(f"user_id.eq.{user_id},user_id.is.null")  # User's categories + system categories
            .order("name")
            .execute()
        )
        
        if not result.data:
            logger.warning(f"No categories found for user {user_id[:8]}")
            # Return at least the system 'general' category as fallback
            return [{"id": "system-general", "name": "General"}]
        
        # Format categories for LLM consumption
        categories = []
        for cat in result.data:
            if isinstance(cat, dict):
                categories.append({
                    "id": cat.get("id", ""),
                    "name": cat.get("name", "Unknown")
                })
        
        logger.info(f"Fetched {len(categories)} categories for user {user_id[:8]}")
        return categories
        
    except Exception as e:
        logger.error(f"Error fetching categories for user {user_id[:8]}: {e}", exc_info=True)
        # Return fallback to prevent agent failure
        return [{"id": "system-general", "name": "General"}]
