"""
InvoiceAgent Runner

Main agent execution logic. Orchestrates interaction with Gemini,
manages tool calls, and returns structured output.
"""

import logging
import base64
from typing import Optional

from google import genai
from google.genai import types

from backend.config import settings
from backend.agents.invoice.types import InvoiceAgentOutput, PurchasedItem, CategorySuggestion
from backend.agents.invoice.prompts import INVOICE_AGENT_SYSTEM_PROMPT
from backend.agents.invoice.tools import fetch_adk_spec, get_user_profile, get_user_categories

logger = logging.getLogger(__name__)


def run_invoice_agent(
    user_id: str,
    receipt_image_id: str,
    receipt_image_base64: Optional[str] = None,
    ocr_text: Optional[str] = None,
    country: str = "GT",
    currency_preference: str = "GTQ"
) -> InvoiceAgentOutput:
    """
    Process an invoice/receipt image and extract structured data using Gemini.
    
    This is the main entry point for the InvoiceAgent. It orchestrates the
    interaction with Gemini using function calling, manages tool calls, and
    returns structured output.
    
    Args:
        user_id: Authenticated user UUID from Supabase Auth (NEVER from client)
        receipt_image_id: Reference to uploaded image in storage
        receipt_image_base64: Optional base64-encoded image data
        ocr_text: Optional pre-extracted OCR text
        country: User's country code (from getUserProfile)
        currency_preference: User's preferred currency (from getUserProfile)
        
    Returns:
        InvoiceAgentOutput with status DRAFT, INVALID_IMAGE, or OUT_OF_SCOPE
        
    Security:
        - Assumes backend has validated Supabase token and resolved user_id
        - Does NOT log full invoice images or sensitive financial data
        - Does NOT write to database (persistence handled by API layer)
    """
    logger.info(f"InvoiceAgent invoked for receipt_id={receipt_image_id}")
    
    # Validate that we have either image or OCR text
    if not receipt_image_base64 and not ocr_text:
        logger.error("Neither receipt_image_base64 nor ocr_text provided")
        return {
            "status": "INVALID_IMAGE",
            "store_name": None,
            "transaction_time": None,
            "total_amount": None,
            "currency": None,
            "purchased_items": None,
            "category_suggestion": None,
            "extracted_text": None,
            "reason": "No image or OCR text provided"
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
        
        # Define function declarations for tools
        fetch_tool = types.FunctionDeclaration(
            name="fetch",
            description="Retrieve the most recent ADK runtime / tool invocation spec / policy docs. Call this FIRST.",
            parameters={
                "type": "object",
                "properties": {},
                "required": []
            }
        )
        
        get_profile_tool = types.FunctionDeclaration(
            name="getUserProfile",
            description="Get user profile with country, currency_preference, and locale.",
            parameters={
                "type": "object",
                "properties": {
                    "user_id": {
                        "type": "string",
                        "description": "Authenticated user UUID"
                    }
                },
                "required": ["user_id"]
            }
        )
        
        get_categories_tool = types.FunctionDeclaration(
            name="getUserCategories",
            description="Get user's expense categories for category suggestion matching.",
            parameters={
                "type": "object",
                "properties": {
                    "user_id": {
                        "type": "string",
                        "description": "Authenticated user UUID"
                    }
                },
                "required": ["user_id"]
            }
        )
        
        # Create tools configuration
        tools = types.Tool(function_declarations=[
            fetch_tool,
            get_profile_tool,
            get_categories_tool
        ])
        
        # Build the user prompt
        if receipt_image_base64:
            prompt_parts = [
                types.Part(
                    text=f"""Extract invoice data from this receipt image.

User context:
- user_id: {user_id}
- country: {country}
- currency_preference: {currency_preference}
- receipt_id: {receipt_image_id}

Instructions:
1. First call fetch() to get the latest ADK spec
2. Then call getUserProfile(user_id="{user_id}") and getUserCategories(user_id="{user_id}")
3. Extract all invoice fields from the image
4. Match to existing categories or propose new ones
5. Return JSON with status DRAFT, INVALID_IMAGE, or OUT_OF_SCOPE"""
                ),
                types.Part(
                    inline_data=types.Blob(
                        mime_type="image/jpeg",
                        data=base64.b64decode(receipt_image_base64)
                    )
                )
            ]
        else:
            # Use OCR text if no image
            prompt_parts = [
                types.Part(
                    text=f"""Extract invoice data from this receipt OCR text:

{ocr_text}

User context:
- user_id: {user_id}
- country: {country}
- currency_preference: {currency_preference}
- receipt_id: {receipt_image_id}

Instructions:
1. First call fetch() to get the latest ADK spec
2. Then call getUserProfile(user_id="{user_id}") and getUserCategories(user_id="{user_id}")
3. Extract all invoice fields from the OCR text
4. Match to existing categories or propose new ones
5. Return JSON with status DRAFT, INVALID_IMAGE, or OUT_OF_SCOPE"""
                )
            ]
        
        # Configure generation with tools
        config = types.GenerateContentConfig(
            tools=[tools],
            system_instruction=INVOICE_AGENT_SYSTEM_PROMPT,
            temperature=0.0,  # Deterministic for structured extraction
            response_mime_type="application/json"
        )
        
        # Send initial request to Gemini
        contents = [types.Content(role="user", parts=prompt_parts)]
        response = client.models.generate_content(
            model="gemini-2.5-flash",
            contents=contents,
            config=config
        )
        
        # Handle function calls iteratively
        max_iterations = 5
        iteration = 0
        
        while iteration < max_iterations:
            iteration += 1
            
            # Check if there are function calls to execute
            if not response.candidates:
                logger.error("No candidates in response")
                break
                
            candidate = response.candidates[0]
            if not candidate.content or not candidate.content.parts:
                logger.error("No content parts in candidate")
                break
            
            # Check for function calls
            function_calls = [
                part.function_call
                for part in candidate.content.parts
                if part.function_call
            ]
            
            if not function_calls:
                # No more function calls - extract final response
                logger.info("No more function calls - extracting final response")
                break
            
            # Execute function calls and collect responses
            function_responses = []
            for fc in function_calls:
                logger.info(f"Executing function: {fc.name}")
                
                if fc.name == "fetch":
                    result = fetch_adk_spec()
                elif fc.name == "getUserProfile":
                    result = get_user_profile(user_id)
                elif fc.name == "getUserCategories":
                    result = get_user_categories(user_id)
                else:
                    logger.warning(f"Unknown function call: {fc.name}")
                    result = {"error": f"Unknown function: {fc.name}"}
                
                # Create function response
                function_responses.append(
                    types.Part.from_function_response(
                        name=fc.name,
                        response={"result": result}
                    )
                )
            
            # Append model's response and function results to conversation
            contents.append(candidate.content)
            contents.append(types.Content(role="user", parts=function_responses))
            
            # Continue conversation with function results
            response = client.models.generate_content(
                model="gemini-2.5-flash",
                contents=contents,
                config=config
            )
        
        # Extract final response as JSON
        if not response.candidates or not response.candidates[0].content:
            logger.error("No final response from model")
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
        import json
        response_text = response.text.strip()
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
        
        # Ensure the result matches InvoiceAgentOutput schema
        output: InvoiceAgentOutput = {
            "status": status,
            "store_name": result.get("store_name"),
            "transaction_time": result.get("transaction_time"),
            "total_amount": result.get("total_amount"),
            "currency": result.get("currency"),
            "purchased_items": result.get("purchased_items"),
            "category_suggestion": result.get("category_suggestion"),
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

