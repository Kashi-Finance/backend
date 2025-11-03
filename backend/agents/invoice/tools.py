"""
InvoiceAgent Tool Implementations

These are the backend tools that InvoiceAgent can call during execution.
Each tool is documented with purpose, inputs, outputs, and security constraints.
"""

import logging
from typing import Dict, List

logger = logging.getLogger(__name__)


def fetch_adk_spec() -> Dict:
    """
    Fetches the latest ADK runtime spec.
    
    In production, this would call an actual endpoint or cache.
    For now, returns a placeholder.
    
    Returns:
        ADK spec dict with version and notes
    """
    return {
        "version": "2025-11-02",
        "spec": "Google ADK with Gemini function calling",
        "notes": "Use OpenAPI-compatible schema for function declarations"
    }


def get_user_profile(user_id: str) -> Dict:
    """
    Get user profile (country, currency_preference, locale).
    
    TODO(db-team): Implement actual DB query following backend/db.instructions.md
    
    Args:
        user_id: Authenticated user UUID from Supabase Auth
        
    Returns:
        Profile dict with country, currency_preference, locale
        
    Security:
        - user_id MUST come from authenticated Supabase token (never from client)
        - Assumes RLS enforces user_id = auth.uid()
    """
    logger.info(f"Fetching profile for user_id={user_id[:8]}...")
    # TODO(db-team): Real implementation following backend/db.instructions.md
    return {
        "country": "GT",
        "currency_preference": "GTQ",
        "locale": "es-GT"
    }


def get_user_categories(user_id: str) -> List[Dict]:
    """
    Get user's expense categories.
    
    TODO(db-team): Implement actual DB query following backend/db.instructions.md
    
    Args:
        user_id: Authenticated user UUID from Supabase Auth
        
    Returns:
        List of category dicts with category_id, name, flow_type, is_default
        
    Security:
        - user_id MUST come from authenticated Supabase token (never from client)
        - Assumes RLS enforces user_id = auth.uid()
        - Read-only; MUST NOT create categories
    """
    logger.info(f"Fetching categories for user_id={user_id[:8]}...")
    # TODO(db-team): Real implementation following backend/db.instructions.md
    return [
        {
            "category_id": "default-general-uuid",
            "name": "General",
            "flow_type": "outcome",
            "is_default": True
        },
        {
            "category_id": "cat-supermercado-uuid",
            "name": "Supermercado",
            "flow_type": "outcome",
            "is_default": False
        }
    ]
