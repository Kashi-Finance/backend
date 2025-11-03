"""
InvoiceAgent JSON Schemas

OpenAPI-compatible schemas for API/runtime validation.
These mirror the TypedDict definitions in types.py exactly.
"""

# Input schema for InvoiceAgent
INPUT_SCHEMA = {
    "type": "object",
    "properties": {
        "user_id": {
            "type": "string",
            "description": "Authenticated user UUID from Supabase Auth (never from client)"
        },
        "receipt_image_id": {
            "type": "string",
            "description": "Reference to uploaded image in storage"
        },
        "receipt_image_base64": {
            "type": "string",
            "description": "Optional base64-encoded image data"
        },
        "ocr_text": {
            "type": "string",
            "description": "Optional pre-extracted OCR text"
        },
        "country": {
            "type": "string",
            "description": "User's country code (e.g., 'GT')"
        },
        "currency_preference": {
            "type": "string",
            "description": "User's preferred currency (e.g., 'GTQ')"
        }
    },
    "required": ["user_id", "receipt_image_id", "country", "currency_preference"]
}

# Output schema for InvoiceAgent
OUTPUT_SCHEMA = {
    "type": "object",
    "properties": {
        "status": {
            "type": "string",
            "enum": ["DRAFT", "INVALID_IMAGE", "OUT_OF_SCOPE"],
            "description": "Processing status"
        },
        "store_name": {
            "type": "string",
            "description": "Merchant/store name (present if status=DRAFT)"
        },
        "transaction_time": {
            "type": "string",
            "description": "ISO-8601 datetime string (present if status=DRAFT)"
        },
        "total_amount": {
            "type": "number",
            "description": "Total invoice amount (present if status=DRAFT)"
        },
        "currency": {
            "type": "string",
            "description": "Currency code or symbol (present if status=DRAFT)"
        },
        "purchased_items": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "description": {"type": "string"},
                    "quantity": {"type": "number"},
                    "unit_price": {"type": "number"},
                    "line_total": {"type": "number"}
                },
                "required": ["description", "quantity", "line_total"]
            },
            "description": "List of purchased items (present if status=DRAFT)"
        },
        "category_suggestion": {
            "type": "object",
            "properties": {
                "match_type": {
                    "type": "string",
                    "enum": ["EXISTING", "NEW_PROPOSED"]
                },
                "category_id": {"type": "string"},
                "category_name": {"type": "string"},
                "proposed_name": {"type": "string"}
            },
            "required": ["match_type"],
            "description": "Category assignment suggestion (present if status=DRAFT)"
        },
        "extracted_text": {
            "type": "string",
            "description": "Canonical multi-line snapshot for DB storage (present if status=DRAFT)"
        },
        "reason": {
            "type": "string",
            "description": "Short factual explanation (present if status!=DRAFT)"
        }
    },
    "required": ["status"]
}

# Gemini function declarations for the tools
FETCH_DECLARATION = {
    "name": "fetch",
    "description": "Retrieve the latest ADK runtime / tool invocation spec",
    "parameters": {
        "type": "object",
        "properties": {},
        "required": []
    }
}

GET_USER_PROFILE_DECLARATION = {
    "name": "getUserProfile",
    "description": "Get user's profile context (country, currency_preference, locale) for localization",
    "parameters": {
        "type": "object",
        "properties": {
            "user_id": {
                "type": "string",
                "description": "Authenticated user UUID (provided by backend, never from client)"
            }
        },
        "required": ["user_id"]
    }
}

GET_USER_CATEGORIES_DECLARATION = {
    "name": "getUserCategories",
    "description": "Get user's expense categories to build category_suggestion",
    "parameters": {
        "type": "object",
        "properties": {
            "user_id": {
                "type": "string",
                "description": "Authenticated user UUID (provided by backend, never from client)"
            }
        },
        "required": ["user_id"]
    }
}
