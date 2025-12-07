"""
Recommendation Service - Perplexity Sonar with Native Web Grounding

This service implements product recommendations using Perplexity's Sonar model,
which has built-in web search grounding. All recommendations are based on
real, current web data - NOT LLM training knowledge.

Architecture:
- Pattern: Grounded LLM (single API call with native web search)
- Model: Perplexity Sonar (sonar or sonar-pro)
- Web Search: Built-in (always-on web grounding)
- API: Perplexity Python SDK
- Temperature: 0.2 (near-deterministic for factual queries)
- Output: Structured JSON (via response_format with JSON schema)

IMPORTANT: URLs in JSON structured output may be hallucinated. 
Use search_results field from API response for verified URLs.

Response includes:
- search_results: Array of {title, url, date} from web search
- citations: URLs referenced in the response
"""

import os
import logging
import json
from typing import Dict, Any, Optional, List, cast
from decimal import Decimal

from supabase import Client

from backend.agents.recommendation.prompts import (
    RECOMMENDATION_SYSTEM_PROMPT,
    build_recommendation_user_prompt,
)
from backend.schemas.recommendations import (
    RecommendationQueryResponseOK,
    RecommendationQueryResponseNoValidOption,
    ProductRecommendation,
)

logger = logging.getLogger(__name__)

# Perplexity API Configuration
PERPLEXITY_API_KEY = os.getenv("PERPLEXITY_API_KEY", "")

# Initialize Perplexity client (lazy initialization)
_perplexity_client = None


def _get_perplexity_client():
    """
    Lazy initialization of Perplexity client.
    Uses the official Perplexity SDK.
    """
    global _perplexity_client

    if _perplexity_client is not None:
        return _perplexity_client

    if not PERPLEXITY_API_KEY:
        logger.warning(
            "PERPLEXITY_API_KEY not configured. Recommendation service will not work. "
            "Please set PERPLEXITY_API_KEY in your .env file."
        )
        return None

    try:
        from perplexity import Perplexity  # type: ignore[import-untyped]
        _perplexity_client = Perplexity(api_key=PERPLEXITY_API_KEY)
        logger.info("Perplexity client initialized successfully")
        return _perplexity_client
    except ImportError:
        logger.error(
            "perplexityai package not installed. "
            "Run: uv add perplexityai"
        )
        return None
    except Exception as e:
        logger.error(f"Failed to initialize Perplexity client: {e}")
        return None


def _validate_llm_response(response_data: Dict[str, Any]) -> bool:
    """Validate that LLM response conforms to expected schema."""
    if "status" not in response_data:
        logger.error("LLM response missing 'status' field")
        return False

    if "products" not in response_data:
        logger.error("LLM response missing 'products' field")
        return False

    if "metadata" not in response_data:
        logger.error("LLM response missing 'metadata' field")
        return False

    valid_statuses = ["OK", "NO_VALID_OPTION"]
    if response_data["status"] not in valid_statuses:
        logger.error(f"Invalid status: {response_data['status']}")
        return False

    if response_data["status"] == "OK":
        if not isinstance(response_data["products"], list) or len(response_data["products"]) == 0:
            logger.error("Status OK but products list is empty")
            return False
        
        for idx, product in enumerate(response_data["products"]):
            required_fields = [
                "product_title", "price_total", "seller_name", "url",
                "pickup_available", "warranty_info", "copy_for_user", "badges",
            ]
            for field in required_fields:
                if field not in product:
                    logger.error(f"Product {idx} missing field: {field}")
                    return False

    return True


def _extract_search_results(response: Any) -> List[Dict[str, Any]]:
    """Extract search_results from Perplexity API response."""
    try:
        if hasattr(response, 'search_results') and response.search_results:
            return [
                {
                    "title": r.title if hasattr(r, 'title') else "",
                    "url": r.url if hasattr(r, 'url') else "",
                    "date": r.date if hasattr(r, 'date') else "",
                }
                for r in response.search_results
            ]
    except Exception as e:
        logger.warning(f"Error extracting search_results: {e}")
    
    return []


async def _get_user_profile(supabase_client: Client, user_id: str) -> Dict[str, Any]:
    """Fetch user profile for context (country, currency_preference)."""
    try:
        response = supabase_client.table("profile").select("*").eq("user_id", user_id).execute()
        
        if response.data and len(response.data) > 0:
            profile = cast(dict[str, Any], response.data[0])
            return {
                "country": str(profile.get("country", "GT")),
                "currency_preference": str(profile.get("currency_preference", "GTQ")),
                "locale": str(profile.get("locale", "es-GT")),
            }
        else:
            logger.warning(f"No profile found for user_id={user_id}, using defaults")
            return {"country": "GT", "currency_preference": "GTQ", "locale": "es-GT"}

    except Exception as e:
        logger.error(f"Error fetching user profile: {e}")
        return {"country": "GT", "currency_preference": "GTQ", "locale": "es-GT"}


def _get_recommendation_json_schema() -> Dict[str, Any]:
    """Get JSON schema for Perplexity structured output."""
    return {
        "type": "object",
        "properties": {
            "status": {"type": "string", "enum": ["OK", "NO_VALID_OPTION"]},
            "products": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "product_title": {"type": "string"},
                        "price_total": {"type": "number"},
                        "seller_name": {"type": "string"},
                        "url": {"type": "string"},
                        "pickup_available": {"type": "boolean"},
                        "warranty_info": {"type": "string"},
                        "copy_for_user": {"type": "string"},
                        "badges": {"type": "array", "items": {"type": "string"}, "maxItems": 3}
                    },
                    "required": ["product_title", "price_total", "seller_name", "url", 
                                 "pickup_available", "warranty_info", "copy_for_user", "badges"]
                },
                "maxItems": 3
            },
            "metadata": {
                "type": "object",
                "properties": {
                    "total_results": {"type": "integer"},
                    "query_understood": {"type": "boolean"},
                    "search_successful": {"type": "boolean"},
                    "reason": {"type": "string"}
                },
                "required": ["total_results", "query_understood", "search_successful"]
            }
        },
        "required": ["status", "products", "metadata"]
    }


async def query_recommendations(
    supabase_client: Client,
    user_id: str,
    query_raw: str,
    budget_hint: Optional[Decimal] = None,
    preferred_store: Optional[str] = None,
    user_note: Optional[str] = None,
    extra_details: Optional[Dict[str, Any]] = None,
) -> RecommendationQueryResponseOK | RecommendationQueryResponseNoValidOption:
    """
    Query product recommendations using Perplexity Sonar with web grounding.
    
    This function:
    1. Fetches user profile for country/currency context
    2. Builds the prompt with user query and context
    3. Calls Perplexity Sonar API with structured output
    4. Parses and validates the response
    5. Returns typed Pydantic model
    """
    logger.info(f"query_recommendations called for user_id={user_id}, query='{query_raw[:50]}...'")
    
    client = _get_perplexity_client()
    if client is None:
        logger.error("Perplexity client not available")
        return RecommendationQueryResponseNoValidOption(
            status="NO_VALID_OPTION",
            reason="Recommendation service is not configured. Please contact support."
        )
    
    profile = await _get_user_profile(supabase_client, user_id)
    country = profile["country"]
    currency = profile["currency_preference"]
    
    user_prompt = build_recommendation_user_prompt(
        query_raw=query_raw,
        country=country,
        currency=currency,
        budget_hint=float(budget_hint) if budget_hint else None,
        preferred_store=preferred_store,
        user_note=user_note,
        extra_details=extra_details,
    )
    
    messages = [
        {"role": "system", "content": RECOMMENDATION_SYSTEM_PROMPT},
        {"role": "user", "content": user_prompt},
    ]
    
    try:
        logger.info("Calling Perplexity Sonar API...")
        
        response = client.chat.completions.create(
            model="sonar",
            messages=messages,
            temperature=0.2,
            response_format={
                "type": "json_schema",
                "json_schema": {"schema": _get_recommendation_json_schema()}
            },
            search_recency_filter="month",
        )
        
        content = response.choices[0].message.content
        if not content:
            logger.error("Empty response from Perplexity API")
            return RecommendationQueryResponseNoValidOption(
                status="NO_VALID_OPTION",
                reason="No response from recommendation service."
            )
        
        search_results = _extract_search_results(response)
        logger.info(f"Got {len(search_results)} search results from Perplexity")
        
        try:
            response_data = json.loads(content)
        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse JSON response: {e}")
            logger.error(f"Raw content: {content[:500]}")
            return RecommendationQueryResponseNoValidOption(
                status="NO_VALID_OPTION",
                reason="Failed to parse recommendation response."
            )
        
        if not _validate_llm_response(response_data):
            logger.error("Invalid response structure from Perplexity")
            return RecommendationQueryResponseNoValidOption(
                status="NO_VALID_OPTION",
                reason="Invalid response format from recommendation service."
            )
        
        if response_data["status"] == "NO_VALID_OPTION":
            logger.info("Perplexity returned NO_VALID_OPTION")
            reason = response_data.get("metadata", {}).get("reason", "No valid products found.")
            return RecommendationQueryResponseNoValidOption(
                status="NO_VALID_OPTION",
                reason=reason
            )
        
        products = []
        for p in response_data["products"]:
            products.append(ProductRecommendation(
                product_title=p["product_title"],
                price_total=float(p["price_total"]),
                seller_name=p["seller_name"],
                url=p["url"],
                pickup_available=p["pickup_available"],
                warranty_info=p["warranty_info"],
                copy_for_user=p["copy_for_user"],
                badges=p["badges"][:3] if p["badges"] else [],
            ))
        
        logger.info(f"Returning {len(products)} product recommendations")
        
        # Store search_results for debugging/logging but don't include in response
        # (schema only has status and results_for_user)
        if search_results:
            logger.debug(f"Web search citations: {search_results}")
        
        return RecommendationQueryResponseOK(
            status="OK",
            results_for_user=products,
        )
        
    except Exception as e:
        logger.error(f"Error calling Perplexity API: {e}")
        return RecommendationQueryResponseNoValidOption(
            status="NO_VALID_OPTION",
            reason=f"Error querying recommendation service: {str(e)}"
        )


async def retry_recommendations(
    supabase_client: Client,
    user_id: str,
    query_raw: str,
    budget_hint: Optional[Decimal] = None,
    preferred_store: Optional[str] = None,
    user_note: Optional[str] = None,
    extra_details: Optional[Dict[str, Any]] = None,
) -> RecommendationQueryResponseOK | RecommendationQueryResponseNoValidOption:
    """
    Retry recommendations with updated criteria.
    
    Same as query_recommendations but semantically used for retries.
    """
    logger.info(f"retry_recommendations called for user_id={user_id}")
    
    return await query_recommendations(
        supabase_client=supabase_client,
        user_id=user_id,
        query_raw=query_raw,
        budget_hint=budget_hint,
        preferred_store=preferred_store,
        user_note=user_note,
        extra_details=extra_details,
    )
