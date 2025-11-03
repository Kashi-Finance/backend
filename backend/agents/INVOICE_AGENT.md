# InvoiceAgent Documentation

## Overview

`InvoiceAgent` is an adk agent built on Google ADK/Gemini that extracts structured financial data from invoice and receipt images for the Kashi Finances backend.

## Responsibility

- **Single Purpose**: Parse invoice/receipt images and extract structured purchase data
- **Returns**: Validated draft expense data suitable for persistence under RLS
- **Does NOT**: 
  - Provide general finance advice
  - Answer non-invoice questions
  - Write to database (handled by API layer)
  - Log sensitive data (full images, transaction histories)

## Input Schema

```python
class InvoiceAgentInput(TypedDict):
    user_id: str                         # Authenticated user UUID (from Supabase Auth)
    receipt_image_id: str                # Reference to uploaded image in storage
    receipt_image_base64: Optional[str]  # Base64-encoded image data (if available)
    ocr_text: Optional[str]              # Pre-extracted OCR text (optional)
    country: str                         # User's country (e.g., "GT")
    currency_preference: str             # User's preferred currency (e.g., "GTQ")
```

### Required Fields
- `user_id`: MUST be the authenticated user from Supabase Auth token (never from client body)
- `receipt_image_id`: Reference to the image in storage
- `country`: ISO-2 country code
- `currency_preference`: Currency code/symbol

### Optional Fields
- `receipt_image_base64`: If provided, used for vision-based extraction
- `ocr_text`: If provided, used as fallback/supplement to vision extraction

## Output Schema

```python
class InvoiceAgentOutput(TypedDict):
    status: Literal["DRAFT", "INVALID_IMAGE", "OUT_OF_SCOPE"]
    
    # Present when status == "DRAFT"
    store_name: Optional[str]
    transaction_time: Optional[str]      # ISO-8601 datetime string
    total_amount: Optional[float]
    currency: Optional[str]
    purchased_items: Optional[list[PurchasedItem]]
    category_suggestion: Optional[CategorySuggestion]
    extracted_text: Optional[str]        # Canonical multi-line snapshot
    
    # Present when status != "DRAFT"
    reason: Optional[str]                # Short factual explanation
```

### Status Values

1. **`DRAFT`**: Invoice successfully processed
   - All structured fields populated
   - `extracted_text` contains canonical snapshot for DB
   - Ready for API layer to persist under RLS

2. **`INVALID_IMAGE`**: Image not usable
   - `reason` explains why (corrupted, not an invoice, unreadable)
   - No structured data returned

3. **`OUT_OF_SCOPE`**: Request is not invoice processing
   - `reason` explains rejection
   - No structured data returned

### Structured Types

**PurchasedItem**:
```python
{
    "description": str,      # Item name/description
    "quantity": float,       # Quantity purchased
    "unit_price": float?,    # Price per unit (optional)
    "line_total": float      # Total for this line
}
```

**CategorySuggestion**:
```python
{
    "match_type": "EXISTING" | "NEW_PROPOSED",
    "category_id": str?,      # UUID if EXISTING
    "category_name": str?,    # Name if EXISTING or NEW_PROPOSED
    "proposed_name": str?     # Only if NEW_PROPOSED
}
```

## Canonical `extracted_text` Format

The agent MUST generate `extracted_text` using this exact template:

```
Store Name: {store_name}
Transaction Time: {transaction_time}
Total Amount: {total_amount}
Currency: {currency}
Purchased Items:
{purchased_items}
Receipt Image ID: {receipt_id}
```

This format is mandated by `backend/db.instructions.md` and `backend/api-architecture.instructions.md`.

## Available Tools

The agent has access to these tools (defined in `invoice_agent.py`):

### 1. `fetch()`
- **Purpose**: Retrieve latest ADK runtime spec
- **When**: MUST be called first before any other action
- **Input**: `{}`
- **Output**: ADK spec/policy docs
- **Security**: Read-only

### 2. `getUserProfile(user_id: str)`
- **Purpose**: Get user profile context (country, currency_preference, locale)
- **Input**: `{"user_id": "uuid"}`
- **Output**: `{"country": "GT", "currency_preference": "GTQ", "locale": "es-GT"}`
- **Use**: Fallback currency if receipt currency missing, localization
- **Security**: Backend provides user_id; agent MUST NOT trust client-provided user_id

### 3. `getUserCategories(user_id: str)`
- **Purpose**: Get user's expense categories for matching
- **Input**: `{"user_id": "uuid"}`
- **Output**: `[{"category_id": "uuid", "name": "Supermercado", "flow_type": "outcome", "is_default": true}, ...]`
- **Use**: Build `category_suggestion` (match existing or propose new)
- **Security**: Read-only; MUST NOT create categories

## Workflow

1. **Call `fetch()`** to get latest ADK spec
2. **Validate scope**: Ensure request is invoice/receipt processing
3. **Check image validity**: If corrupted/not-invoice → return `INVALID_IMAGE`
4. **If out-of-scope** (e.g., general questions) → return `OUT_OF_SCOPE`
5. **If valid invoice**:
   - Call `getUserProfile(user_id)` for currency fallback
   - Call `getUserCategories(user_id)` for category matching
   - Extract structured data: store_name, transaction_time, total_amount, currency, items
   - Build `category_suggestion`:
     - If store/items match existing category → `"EXISTING"` + `category_id`
     - If no match → `"NEW_PROPOSED"` + `proposed_name`
   - Generate `extracted_text` using exact template
   - Return `status: "DRAFT"` with all fields

## Guardrails

The agent MUST refuse:
- Sexual content
- Weapons, illegal goods, criminal activity
- Scams or fraudulent content
- General finance advice unrelated to invoice processing
- Random chat or questions

Refusal format:
```python
{
    "status": "OUT_OF_SCOPE",
    "reason": "InvoiceAgent only processes receipts."
}
```

## Security Rules

- **NEVER** trust `user_id` from client body
  - Backend validates Supabase token and provides real `user_id`
- **NEVER** log:
  - Full invoice images
  - Complete transaction histories
  - Sensitive financial amounts in clear form
  - Supabase tokens or auth headers
- **NEVER** write to database directly
  - Return structured data only
  - API layer handles persistence under RLS

## Usage Example

```python
from backend.agents import run_invoice_agent

result = run_invoice_agent(
    user_id="authenticated-user-uuid",  # From Supabase Auth token
    receipt_image_id="receipt-12345",
    receipt_image_base64="...",          # Optional
    ocr_text="...",                      # Optional
    country="GT",
    currency_preference="GTQ"
)

if result["status"] == "DRAFT":
    # Persist to database under RLS
    # TODO(db-team): Implement according to backend/db.instructions.md
    print(f"Extracted: {result['store_name']}, Q{result['total_amount']}")
    print(f"Canonical text:\n{result['extracted_text']}")
elif result["status"] == "INVALID_IMAGE":
    # Handle invalid image
    print(f"Invalid: {result['reason']}")
else:
    # OUT_OF_SCOPE
    print(f"Out of scope: {result['reason']}")
```

## Integration with FastAPI

The FastAPI endpoint for invoice OCR should:

1. **Authenticate** via Supabase Bearer token
2. **Extract** `user_id` from validated token
3. **Fetch** user profile (country, currency_preference)
4. **Upload** receipt image to storage (get `receipt_image_id`)
5. **Optional**: Pre-run OCR to get `ocr_text`
6. **Call** `run_invoice_agent(...)` with validated inputs
7. **Check** result `status`:
   - If `DRAFT`: Persist via DB layer (RLS)
   - If `INVALID_IMAGE` or `OUT_OF_SCOPE`: Return HTTP 400 with `reason`
8. **Return** Pydantic `ResponseModel` to client

## Current Implementation Status

**✅ Completed**:
- Type definitions (Input/Output schemas)
- Tool declarations (fetch, getUserProfile, getUserCategories)
- System prompt with workflow and guardrails
- Mock runner function with example output structure
- JSON schemas for API/runtime validation
- Canonical `extracted_text` template enforcement

**🚧 Pending** (TODO):
- Real Gemini API integration (replace mock response)
- Actual tool execution (getUserProfile, getUserCategories DB queries)
- Image/OCR processing via Gemini vision API
- Error handling for Gemini API failures
- Rate limiting and retry logic

Expected output: Valid `InvoiceAgentOutput` with `status: "DRAFT"` and all structured fields.

## References

- Prompt definition: `.github/prompts/new-adk-agent.prompt.md`
- Agent rules: `.github/instructions/adk-agents.instructions.md`
- API architecture: `.github/instructions/api-architecture.instructions.md`
- DB rules: `.github/instructions/db.instructions.md`
- Google Gemini function calling: https://ai.google.dev/gemini-api/docs/function-calling
