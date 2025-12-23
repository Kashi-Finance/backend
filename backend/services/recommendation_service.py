"""
Recommendation Service - Gemini with Google Search Grounding

This service implements product recommendations using Google's Gemini model
with the Google Search grounding tool for real-time web data.

Architecture:
- Pattern: Grounded LLM (single API call with Google Search tool)
- Model: Gemini 2.5 Flash
- Web Search: Google Search grounding tool (real-time web data)
- API: Google Gen AI Python SDK (google-genai)
- Temperature: 0.2 (near-deterministic for factual queries)
- Output: JSON response parsed from text (Google Search tool doesn't support response_schema)

Key Features:
- All recommendations are grounded in real web search results
- URLs and prices come from actual web pages found during search
- Grounding metadata includes source URLs for verification

IMPORTANT: Google Search grounding tool doesn't support response_mime_type='application/json'
or response_schema. We ask for JSON in the prompt and parse it from the response text.

Response includes:
- products: List of verified product recommendations
- grounding_metadata: Web search queries and source URLs
"""

import json
import logging
import os
import re
from decimal import Decimal
from typing import Any, Dict, List, Optional, cast

from google import genai
from google.genai import types
from pydantic import BaseModel

from backend.agents.recommendation.prompts import (
    RECOMMENDATION_SYSTEM_PROMPT,
    build_recommendation_user_prompt,
)
from backend.config import settings
from backend.schemas.recommendations import (
    ProductRecommendation,
    RecommendationQueryResponseNoValidOption,
    RecommendationQueryResponseOK,
)
from supabase import Client

logger = logging.getLogger(__name__)

# Initialize Gemini client (lazy initialization)
_gemini_client = None


# =============================================================================
# PYDANTIC MODELS FOR STRUCTURED OUTPUT
# =============================================================================

class ProductSchema(BaseModel):
    """Schema for a single product recommendation."""
    product_title: str
    price_total: float
    seller_name: str
    url: str
    pickup_available: bool
    warranty_info: str
    copy_for_user: str
    badges: List[str]


class MetadataSchema(BaseModel):
    """Schema for response metadata."""
    total_results: int
    query_understood: bool
    search_successful: bool
    reason: Optional[str] = None


class RecommendationResponseSchema(BaseModel):
    """Schema for the complete recommendation response."""
    status: str  # "OK" or "NO_VALID_OPTION"
    products: List[ProductSchema]
    metadata: MetadataSchema


def _get_gemini_client():
    """
    Lazy initialization of Gemini client.
    Uses the Google Gen AI SDK.
    """
    global _gemini_client

    if _gemini_client is not None:
        return _gemini_client

    api_key = settings.GOOGLE_API_KEY if hasattr(settings, 'GOOGLE_API_KEY') else os.getenv("GOOGLE_API_KEY", "")

    if not api_key:
        logger.warning(
            "GOOGLE_API_KEY not configured. Recommendation service will not work. "
            "Please set GOOGLE_API_KEY in your .env file."
        )
        return None

    try:
        _gemini_client = genai.Client(api_key=api_key)
        logger.info("Gemini client initialized successfully for recommendations")
        return _gemini_client
    except Exception as e:
        logger.error(f"Failed to initialize Gemini client: {e}")
        return None


def _extract_reason_from_text(text: str) -> str:
    """
    Extract a meaningful reason from a text response when JSON parsing fails.

    This happens when the model explains why it can't fulfill the request
    instead of returning structured JSON (e.g., budget too low, impossible request).
    """
    # Limit text length
    text = text[:1500] if len(text) > 1500 else text

    # Common patterns that indicate budget issues
    budget_patterns = [
        r'precio.*(?:mínimo|desde|inicia).*?(\d[\d,\.]+)',
        r'(?:cuesta|cuestan|precio).*?Q?(\d[\d,\.]+)',
        r'(?:desde|a partir de).*?Q?(\d[\d,\.]+)',
    ]

    # Check for budget-related issues
    for pattern in budget_patterns:
        match = re.search(pattern, text, re.IGNORECASE)
        if match:
            match.group(1)
            # Extract a summary
            sentences = text.split('.')
            relevant = [s.strip() for s in sentences[:3] if s.strip()]
            if relevant:
                summary = '. '.join(relevant)
                if len(summary) > 300:
                    summary = summary[:300] + "..."
                return summary

    # Check if it's explaining impossibility
    impossibility_keywords = [
        'presupuesto', 'budget', 'precio', 'price',
        'no es posible', 'impossible', 'cannot', 'no se puede',
        'significativamente', 'significantly', 'higher', 'mayor'
    ]

    text_lower = text.lower()
    if any(keyword in text_lower for keyword in impossibility_keywords):
        # Extract first meaningful sentences
        sentences = text.split('.')
        relevant = [s.strip() for s in sentences[:3] if s.strip() and len(s.strip()) > 20]
        if relevant:
            summary = '. '.join(relevant)
            if len(summary) > 400:
                summary = summary[:400] + "..."
            return summary

    # Default: return a truncated version of the text
    if len(text) > 300:
        return text[:300] + "..."
    return text if text else "No se pudo procesar la solicitud."


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


def _extract_grounding_info(response) -> Dict[str, Any]:
    """Extract grounding metadata from Gemini response."""
    grounding_info: Dict[str, Any] = {
        "web_search_queries": [],
        "source_urls": [],
    }

    try:
        if response.candidates and len(response.candidates) > 0:
            candidate = response.candidates[0]
            if hasattr(candidate, 'grounding_metadata') and candidate.grounding_metadata:
                metadata = candidate.grounding_metadata

                # Extract web search queries
                if hasattr(metadata, 'web_search_queries') and metadata.web_search_queries:
                    grounding_info["web_search_queries"] = list(metadata.web_search_queries)

                # Extract grounding chunks (source URLs)
                if hasattr(metadata, 'grounding_chunks') and metadata.grounding_chunks:
                    for chunk in metadata.grounding_chunks:
                        if hasattr(chunk, 'web') and chunk.web:
                            grounding_info["source_urls"].append({
                                "title": chunk.web.title if hasattr(chunk.web, 'title') else "",
                                "uri": chunk.web.uri if hasattr(chunk.web, 'uri') else "",
                                "domain": chunk.web.domain if hasattr(chunk.web, 'domain') else "",
                            })
    except Exception as e:
        logger.warning(f"Error extracting grounding info: {e}")

    return grounding_info


async def _get_user_profile(supabase_client: Client, user_id: str) -> Dict[str, Any]:
    """Fetch user profile for context (country, currency_preference, locale)."""
    try:
        response = supabase_client.table("profile").select("*").eq("user_id", user_id).execute()

        if response.data and len(response.data) > 0:
            # Cast from Supabase JSON type to dict
            profile = cast(Dict[str, Any], response.data[0])
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


def _extract_language_from_locale(locale: str, country: str) -> str:
    """
    Extract the language code from a locale string.

    Examples:
        - "es-GT" -> "Spanish"
        - "en-US" -> "English"
        - "pt-BR" -> "Portuguese"
        - "system" -> infer from country

    Returns human-readable language name for use in prompts.
    """
    # Map of language codes to human-readable names
    LANGUAGE_NAMES = {
        "es": "Spanish",
        "en": "English",
        "pt": "Portuguese",
        "fr": "French",
        "de": "German",
        "it": "Italian",
        "zh": "Chinese",
        "ja": "Japanese",
        "ko": "Korean",
    }

    # Map of countries to default languages (for "system" locale)
    COUNTRY_LANGUAGES = {
        "GT": "es",  # Guatemala -> Spanish
        "MX": "es",  # Mexico -> Spanish
        "SV": "es",  # El Salvador -> Spanish
        "HN": "es",  # Honduras -> Spanish
        "NI": "es",  # Nicaragua -> Spanish
        "CR": "es",  # Costa Rica -> Spanish
        "PA": "es",  # Panama -> Spanish
        "CO": "es",  # Colombia -> Spanish
        "PE": "es",  # Peru -> Spanish
        "EC": "es",  # Ecuador -> Spanish
        "VE": "es",  # Venezuela -> Spanish
        "AR": "es",  # Argentina -> Spanish
        "CL": "es",  # Chile -> Spanish
        "BO": "es",  # Bolivia -> Spanish
        "PY": "es",  # Paraguay -> Spanish
        "UY": "es",  # Uruguay -> Spanish
        "DO": "es",  # Dominican Republic -> Spanish
        "CU": "es",  # Cuba -> Spanish
        "PR": "es",  # Puerto Rico -> Spanish
        "ES": "es",  # Spain -> Spanish
        "US": "en",  # United States -> English
        "CA": "en",  # Canada -> English (default)
        "GB": "en",  # United Kingdom -> English
        "AU": "en",  # Australia -> English
        "BR": "pt",  # Brazil -> Portuguese
        "PT": "pt",  # Portugal -> Portuguese
        "FR": "fr",  # France -> French
        "DE": "de",  # Germany -> German
        "IT": "it",  # Italy -> Italian
    }

    lang_code = None

    # Handle "system" locale - infer from country
    if locale.lower() == "system":
        lang_code = COUNTRY_LANGUAGES.get(country.upper(), "es")
    else:
        # Extract language code from locale (e.g., "es" from "es-GT")
        lang_code = locale.split("-")[0].lower() if "-" in locale else locale.lower()

    # Return human-readable name, default to Spanish for Latin America focus
    return LANGUAGE_NAMES.get(lang_code, "Spanish")


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
    Query product recommendations using Gemini with Google Search grounding.

    This function:
    1. Fetches user profile for country/currency context
    2. Builds the prompt with user query and context
    3. Calls Gemini API with Google Search tool for web grounding
    4. Parses and validates the structured JSON response
    5. Returns typed Pydantic model

    Args:
        supabase_client: Authenticated Supabase client
        user_id: User UUID from auth token
        query_raw: User's natural language product query
        budget_hint: Maximum budget in local currency (optional)
        preferred_store: User's preferred store (optional)
        user_note: Additional user preferences (optional)
        extra_details: Additional context from progressive Q&A (optional)

    Returns:
        RecommendationQueryResponseOK or RecommendationQueryResponseNoValidOption
    """
    logger.info(f"query_recommendations called for user_id={user_id}, query='{query_raw[:50]}...'")

    client = _get_gemini_client()
    if client is None:
        logger.error("Gemini client not available")
        return RecommendationQueryResponseNoValidOption(
            status="NO_VALID_OPTION",
            reason="Recommendation service is not configured. Please contact support."
        )

    # Fetch user profile for localization
    profile = await _get_user_profile(supabase_client, user_id)
    country = profile["country"]
    currency = profile["currency_preference"]
    locale = profile["locale"]

    # Extract language from locale for response language
    language = _extract_language_from_locale(locale, country)

    # Build the user prompt with full context
    user_prompt = build_recommendation_user_prompt(
        query_raw=query_raw,
        country=country,
        currency=currency,
        language=language,
        budget_hint=float(budget_hint) if budget_hint else None,
        preferred_store=preferred_store,
        user_note=user_note,
        extra_details=extra_details,
    )

    try:
        logger.info("Calling Gemini API with Google Search grounding...")

        # Configure the request with Google Search tool
        # NOTE: Google Search grounding doesn't support response_mime_type='application/json'
        # or response_schema. We ask for JSON in the prompt and parse it from text.
        config = types.GenerateContentConfig(
            system_instruction=RECOMMENDATION_SYSTEM_PROMPT,
            temperature=0.3,  # Slightly higher for more variety in recommendations
            max_output_tokens=4096,  # Ensure complete responses with multiple products
            tools=[
                types.Tool(google_search=types.GoogleSearch())
            ],
        )

        # Make the API call
        response = client.models.generate_content(
            model="gemini-2.5-flash",
            contents=user_prompt,
            config=config,
        )

        # Check for valid response
        if not response.candidates or not response.candidates[0].content:
            logger.error("Empty response from Gemini API")
            return RecommendationQueryResponseNoValidOption(
                status="NO_VALID_OPTION",
                reason="No response from recommendation service."
            )

        # Extract grounding info for logging
        grounding_info = _extract_grounding_info(response)
        if grounding_info["web_search_queries"]:
            logger.info(f"Web search queries: {grounding_info['web_search_queries']}")
        if grounding_info["source_urls"]:
            logger.info(f"Found {len(grounding_info['source_urls'])} source URLs")

        # Get the response text - extract from parts directly for reliability
        # The response.text property can sometimes be None even when parts have text
        content = None

        # First try to get text from parts (more reliable)
        candidate = response.candidates[0]
        if candidate.content and candidate.content.parts:
            for part in candidate.content.parts:
                if hasattr(part, 'text') and part.text:
                    content = part.text
                    break

        # Fall back to response.text if parts didn't work
        if not content:
            content = response.text

        if not content:
            logger.error("Empty text in Gemini response")
            logger.debug(f"Response candidate content: {candidate.content if candidate else 'No candidate'}")
            return RecommendationQueryResponseNoValidOption(
                status="NO_VALID_OPTION",
                reason="No response from recommendation service."
            )

        # Parse JSON response - may be wrapped in markdown code blocks or have text before
        try:
            # First, try to find JSON block in the response
            json_content = content.strip()

            # If there's text before the JSON block, extract just the JSON
            # Look for ```json ... ``` pattern anywhere in the response
            json_block_match = re.search(r'```json\s*([\s\S]*?)```', json_content, re.IGNORECASE)
            if json_block_match:
                json_content = json_block_match.group(1).strip()
            else:
                # Try ``` ... ``` pattern
                code_block_match = re.search(r'```\s*([\s\S]*?)```', json_content)
                if code_block_match:
                    json_content = code_block_match.group(1).strip()
                else:
                    # No code blocks - try to find raw JSON (starting with {)
                    json_start = json_content.find('{')
                    if json_start > 0:
                        json_content = json_content[json_start:]

            # Remove trailing commas before } or ] (common LLM mistake)
            json_content = re.sub(r',(\s*[}\]])', r'\1', json_content)

            # Clean control characters that can break JSON parsing
            # This includes: NUL, SOH, STX, ETX, EOT, ENQ, ACK, BEL, BS, VT, FF, CR, SO-US, DEL
            json_content = re.sub(r'[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]', '', json_content)

            # Replace curly/smart quotes with regular quotes (common LLM output issue)
            json_content = json_content.replace('"', '"').replace('"', '"')
            json_content = json_content.replace(''', "'").replace(''', "'")

            # Replace special dashes with regular dashes
            json_content = json_content.replace('–', '-').replace('—', '-')

            response_data = json.loads(json_content)
        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse JSON response: {e}")
            logger.error(f"Raw content: {content[:500]}")

            # Try to recover partial product data from truncated JSON
            # This happens when the response is cut off mid-stream
            if '"status": "OK"' in content and '"products"' in content:
                try:
                    # Try to extract at least one complete product
                    product_matches = re.findall(
                        r'\{\s*"product_title":\s*"([^"]+)"[^}]*"price_total":\s*([\d.]+)[^}]*"seller_name":\s*"([^"]+)"[^}]*"url":\s*"([^"]+)"',
                        content,
                        re.DOTALL
                    )
                    if product_matches:
                        logger.warning(f"Recovered {len(product_matches)} partial products from truncated response")
                        # Build a minimal valid response
                        products = []
                        for title, price, seller, url in product_matches[:3]:
                            products.append(ProductRecommendation(
                                product_title=title,
                                price_total=float(price),
                                seller_name=seller,
                                url=url,
                                pickup_available=False,
                                warranty_info="Información no disponible",
                                copy_for_user=title,
                                badges=[]
                            ))
                        if products:
                            return RecommendationQueryResponseOK(
                                status="OK",
                                results_for_user=products,
                            )
                except Exception as recovery_error:
                    logger.debug(f"Failed to recover partial products: {recovery_error}")

            # Try to extract a meaningful reason from the text response
            # This can happen when the model explains why it can't fulfill the request
            extracted_reason = _extract_reason_from_text(content)

            return RecommendationQueryResponseNoValidOption(
                status="NO_VALID_OPTION",
                reason=extracted_reason
            )

        # Validate response structure
        if not _validate_llm_response(response_data):
            logger.error("Invalid response structure from Gemini")
            return RecommendationQueryResponseNoValidOption(
                status="NO_VALID_OPTION",
                reason="Invalid response format from recommendation service."
            )

        # Handle NO_VALID_OPTION status
        if response_data["status"] == "NO_VALID_OPTION":
            logger.info("Gemini returned NO_VALID_OPTION")
            reason = response_data.get("metadata", {}).get("reason", "No valid products found.")
            return RecommendationQueryResponseNoValidOption(
                status="NO_VALID_OPTION",
                reason=reason
            )

        # Build product list from response
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

        return RecommendationQueryResponseOK(
            status="OK",
            results_for_user=products,
        )

    except Exception as e:
        logger.error(f"Error calling Gemini API: {e}")
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
