"""
InvoiceAgent Runner

Single-shot LLM extraction workflow. Processes receipt images using Gemini
with a complete context prompt (no iterative function calling).
"""

import base64
import json
import logging
from typing import Dict, List, Optional

from google import genai
from google.genai import types

from backend.agents.invoice.prompts import (
    INVOICE_AGENT_SYSTEM_PROMPT,
    build_invoice_agent_user_prompt,
)
from backend.agents.invoice.types import CategorySuggestion, InvoiceAgentOutput
from backend.config import settings

logger = logging.getLogger(__name__)


def run_invoice_agent(
    user_id: str,
    user_categories: List[Dict],
    receipt_image_base64: str,
    country: str = "GT",
    currency_preference: str = "GTQ"
) -> InvoiceAgentOutput:
    """
    Process an invoice/receipt image and extract structured data using Gemini.

    This is a single-shot multimodal LLM extraction workflow that:
    1. Receives an invoice image (base64) + complete user context
    2. Makes one vision call to Gemini with structured JSON output
    3. Returns validated InvoiceAgentOutput

    Args:
        user_id: Authenticated user UUID from Supabase Auth (NEVER from client)
        user_categories: List of user's expense categories (from endpoint)
        receipt_image_base64: Base64-encoded invoice image (REQUIRED)
        country: User's country code (e.g. "GT")
        currency_preference: User's preferred currency (e.g. "GTQ")

    Returns:
        InvoiceAgentOutput with status DRAFT, INVALID_IMAGE, or OUT_OF_SCOPE

    Security:
        - Assumes backend has validated Supabase token and resolved user_id
        - Does NOT log full invoice images or sensitive financial data
        - Does NOT write to database (persistence handled by API layer)

    Notes:
        - This is NOT an ADK agent with tools - it's a deterministic multimodal LLM workflow
        - Receipt image is REQUIRED for processing
        - All required context (categories, profile) must be provided by caller
        - No iterative function calling - one prompt, one response
        - Uses Gemini's native vision capabilities to read the image
    """
    logger.info(f"InvoiceAgent invoked for user_id={user_id}")

    # Validate that image is provided
    if not receipt_image_base64:
        logger.error("receipt_image_base64 is required but not provided")
        return {
            "status": "INVALID_IMAGE",
            "store_name": None,
            "transaction_time": None,
            "total_amount": None,
            "currency": None,
            "purchased_items": None,
            "category_suggestion": None,
            "extracted_text": None,
            "reason": "Receipt image is required"
        }

    # Check if Google API key is configured
    if not settings.GOOGLE_API_KEY:
        logger.error("GOOGLE_API_KEY not configured")
        raise ValueError(
            "GOOGLE_API_KEY is not configured. "
            "Please set it in your .env file to use InvoiceAgent."
        )

    try:
        # Initialize Gemini client
        client = genai.Client(api_key=settings.GOOGLE_API_KEY)

        # Build the user prompt with dynamic context
        prompt_text = build_invoice_agent_user_prompt(
            user_id=user_id,
            user_categories=user_categories,
            country=country,
            currency_preference=currency_preference
        )

        # Build multimodal content with image
        # Detect MIME type from base64 header or default to jpeg
        mime_type = "image/jpeg"  # default
        if receipt_image_base64.startswith("/9j/"):
            mime_type = "image/jpeg"
        elif receipt_image_base64.startswith("iVBORw0KGgo"):
            mime_type = "image/png"
        elif receipt_image_base64.startswith("R0lGOD"):
            mime_type = "image/gif"
        elif receipt_image_base64.startswith("UklGR"):
            mime_type = "image/webp"

        prompt_parts = [
            types.Part(text=prompt_text),
            types.Part(
                inline_data=types.Blob(
                    mime_type=mime_type,
                    data=base64.b64decode(receipt_image_base64)
                )
            )
        ]

        # Configure generation (no tools, single-shot)
        config = types.GenerateContentConfig(
            system_instruction=INVOICE_AGENT_SYSTEM_PROMPT,
            temperature=0.0,  # Deterministic for structured extraction
            response_mime_type="application/json"
        )

        # Single LLM call with complete context
        logger.debug("Sending single-shot request to Gemini with complete context")
        response = client.models.generate_content(
            model="gemini-2.5-flash",
            contents=prompt_parts,  # type: ignore
            config=config
        )

        # Extract and parse response
        if not response.candidates or not response.candidates[0].content:
            logger.error("No response from model")
            return {
                "status": "INVALID_IMAGE",
                "store_name": None,
                "transaction_time": None,
                "total_amount": None,
                "currency": None,
                "purchased_items": None,
                "category_suggestion": None,
                "extracted_text": None,
                "reason": "Model did not return a response"
            }

        # Parse response text as JSON
        response_text = (response.text or "").strip()
        logger.debug(f"Raw response text: {response_text[:200]}...")

        try:
            result = json.loads(response_text)
        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse JSON response: {e}")
            logger.error(f"Response text: {response_text}")
            return {
                "status": "INVALID_IMAGE",
                "store_name": None,
                "transaction_time": None,
                "total_amount": None,
                "currency": None,
                "purchased_items": None,
                "category_suggestion": None,
                "extracted_text": None,
                "reason": "Failed to parse model response"
            }

        # Validate and return the output
        status = result.get("status", "INVALID_IMAGE")

        logger.info(f"InvoiceAgent completed: status={status}")

        # Normalize category_suggestion to ensure all 4 fields are present
        category_suggestion_normalized: Optional[CategorySuggestion] = None
        category_suggestion_raw = result.get("category_suggestion")
        if category_suggestion_raw and status == "DRAFT":
            category_suggestion_normalized = {
                "match_type": category_suggestion_raw.get("match_type", "NEW_PROPOSED"),
                "category_id": category_suggestion_raw.get("category_id"),
                "category_name": category_suggestion_raw.get("category_name"),
                "proposed_name": category_suggestion_raw.get("proposed_name")
            }
            logger.debug(f"Normalized category_suggestion: {category_suggestion_normalized}")

        # Ensure the result matches InvoiceAgentOutput schema
        output: InvoiceAgentOutput = {
            "status": status,
            "store_name": result.get("store_name"),
            "transaction_time": result.get("transaction_time"),
            "total_amount": result.get("total_amount"),
            "currency": result.get("currency"),
            "purchased_items": result.get("purchased_items"),
            "category_suggestion": category_suggestion_normalized,
            "extracted_text": result.get("extracted_text"),
            "reason": result.get("reason")
        }

        return output

    except Exception as e:
        logger.error(f"InvoiceAgent error: {e}", exc_info=True)
        return {
            "status": "INVALID_IMAGE",
            "store_name": None,
            "transaction_time": None,
            "total_amount": None,
            "currency": None,
            "purchased_items": None,
            "category_suggestion": None,
            "extracted_text": None,
            "reason": f"Agent error: {str(e)}"
        }

