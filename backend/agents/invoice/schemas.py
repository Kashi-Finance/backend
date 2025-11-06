"""
InvoiceAgent JSON Schemas

OpenAPI-compatible schemas for API/runtime validation.
These mirror the TypedDict definitions in types.py exactly.

NOTE: This agent is implemented as a single-shot multimodal workflow (not ADK),
so tool declarations are not needed. These schemas are kept for documentation
and potential future validation needs.
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
        "user_categories": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "id": {"type": "string"},
                    "name": {"type": "string"}
                },
                "required": ["id", "name"]
            },
            "description": "List of user's expense categories"
        },
        "receipt_image_base64": {
            "type": "string",
            "description": "Base64-encoded image data (REQUIRED)"
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
    "required": ["user_id", "receipt_image_id", "user_categories", "receipt_image_base64", "country", "currency_preference"]
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
                    "enum": ["EXISTING", "NEW_PROPOSED"],
                    "description": "Discriminator: whether category exists or is newly proposed"
                },
                "category_id": {
                    "type": ["string", "null"],
                    "description": "UUID of existing category (non-null IF match_type=EXISTING)"
                },
                "category_name": {
                    "type": ["string", "null"],
                    "description": "Name of existing category (non-null IF match_type=EXISTING)"
                },
                "proposed_name": {
                    "type": ["string", "null"],
                    "description": "Suggested name for new category (non-null IF match_type=NEW_PROPOSED)"
                }
            },
            "required": ["match_type", "category_id", "category_name", "proposed_name"],
            "description": "Category assignment suggestion (present if status=DRAFT). INVARIANT: if match_type=EXISTING then category_id and category_name are non-null, proposed_name is null. If match_type=NEW_PROPOSED then proposed_name is non-null, category_id and category_name are null."
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
