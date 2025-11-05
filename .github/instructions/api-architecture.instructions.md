---
applyTo: '**'
---
# API Architecture Instructions (FastAPI layer)

This file tells you how to build and modify HTTP endpoints that expose our adk agents to the mobile app.

Always use the most recent version of the Google ADK documentation when interacting with adk agents.


## 1. Purpose of the HTTP layer

The FastAPI layer is the ONLY public surface for the mobile client. It is responsible for:

1. Authentication (Supabase Auth).
2. Input validation with Pydantic.
3. Domain/intention filtering (only forward valid, in-scope requests to the correct adk agent).
4. Calling exactly one adk agent.
5. Normalizing the agent output into a typed response model.
6. Returning a clean JSON response to the app.
7. Calling persistence logic (if any) through the DB layer, never directly inside the agent.

No endpoint may hand unvalidated or unauthenticated raw user input directly to Gemini / ADK.


## 2. Directory Layout (expected)

- `backend/routes/`
  - FastAPI routers grouped by feature (e.g. invoices, recommendations).
  - Each router defines:
    - A `router = APIRouter(prefix="...")`
    - One or more route functions with explicit `response_model=...`

- `backend/schemas/`
  - `RequestModel` and `ResponseModel` Pydantic classes.
  - Only strict, explicit fields. No `dict[str, Any]` unless explicitly approved.
  - Example naming:
    - `InvoiceOCRRequest`
    - `InvoiceOCRResponse`

- `backend/auth/`
  - Supabase Auth verification utilities:
    - read and verify `Authorization: Bearer <token>`
    - return `user_id` (`auth.uid()`)
    - raise an HTTP 401 if invalid

- `backend/agents/`
  - Implementations of the adk agents (InvoiceAgent, RecommendationCoordinatorAgent, SearchAgent, FormatterAgent).
  - These are not FastAPI endpoints. They are internal callable logic powered by Google ADK.

- `backend/services/`
  - Glue/orchestration code that adapts endpoint requests to agent calls.
  - Enforces domain filtering and scope checking before calling an agent.
  - Maps agent output into `ResponseModel`.

- `backend/db/` (or equivalent data access layer)
  - Functions that perform reads/writes under RLS rules.
  - MUST follow backend/db.instructions.md.
  - Endpoints should never talk directly to SQL; they should call a service function that will have `# TODO(db-team): ...` if persistence logic isn't defined yet.


## 3. Authentication Pipeline (MANDATORY for protected routes)

Every protected FastAPI endpoint MUST do:

1. Read `Authorization: Bearer <token>` from headers.
2. Verify token signature and expiration using Supabase Auth.
3. Extract `user_id` from the token (`auth.uid()`).
4. If verification fails or token is missing → raise `HTTPException(status_code=401, detail={"error":"unauthorized","details":"invalid or missing token"})`.
5. Ignore any `user_id` passed in the body or querystring. The caller cannot override it.
6. From that point on, all downstream actions (DB reads/writes, agent calls) are assumed to happen on behalf of that `user_id`.
7. Optionally load the user's profile (country, currency_preference, etc.) for localization / recommendation context.

This step happens BEFORE any interaction with an adk agent, unless the endpoint is explicitly documented as public.


## 4. Endpoint Flow (STRICT CONTRACT)

All new or updated endpoints MUST follow this 6-step flow:

Step 1. Auth
- Run the Supabase Auth pipeline above (if route is protected).

Step 2. Parse / Validate Request
- Parse the incoming JSON body into a Pydantic `RequestModel`.
- The `RequestModel` MUST:
  - use explicit field names and types,
  - include docstring or inline comments describing each field,
  - reject unexpected fields (no generic `**kwargs`),
  - enforce ranges / enums where known.

Step 3. Domain & Intent Filter
- Determine which adk agent will be called.
- Check if the request intent is in-scope for that agent.
  - If it's out of scope:
    - DO NOT call the agent.
    - return `HTTPException(status_code=400, detail={"error":"out_of_scope","details":"...explanation..."})`.
- The reason for this filter:
  - adk agents MUST NOT handle unrelated questions.
  - We must not waste compute / money on Gemini for irrelevant prompts.
  - We avoid leaking sensitive financial data to the wrong context.

Step 4. Call ONE adk Agent
- Create a structured payload for the selected adk agent.
- Call the agent using its public method, not by chatting with it as if it were a general model.
- The allowed adk agents are:
  - InvoiceAgent
  - RecommendationCoordinatorAgent
  - SearchAgent (AgentTool of RecommendationCoordinatorAgent)
  - FormatterAgent (AgentTool of RecommendationCoordinatorAgent)
- For recommendation-related flows:
  - The FastAPI endpoint should call `RecommendationCoordinatorAgent`.
  - `SearchAgent` and `FormatterAgent` are internal AgentTools that `RecommendationCoordinatorAgent` uses. Do NOT call them directly from the HTTP layer.

Always use the most recent version of the Google ADK documentation for how to invoke these adk agents and their AgentTools.

Step 5. Map Output -> ResponseModel
- Take the agent's structured output.
- Convert / validate it into a Pydantic `ResponseModel`.
- The FastAPI route decorator MUST set `response_model=ResponseModel`.
- Return that `ResponseModel` (or a dict that exactly matches it). Do not wrap it arbitrarily in `{ "status": "ok", ... }` unless the response model explicitly has that shape.

Step 6. (Optional) Persistence
- If the result needs to be stored (for example, storing parsed invoice data after OCR), DO NOT write SQL inline.
- Instead add a clearly marked comment like:
  `# TODO(db-team): persist invoice structured data according to backend/db.instructions.md`
- All persistence MUST respect RLS and will be implemented following backend/db.instructions.md.

Note: The endpoint layer is allowed to call a `backend/services/...` function that encapsulates DB logic, as long as that function itself still respects the TODO(db-team) and defers schema details to backend/db.instructions.md.


## 5. InvoiceAgent special rule: invoice.extracted_text format

When an invoice is processed (OCR, extraction, structuring), we eventually will insert a row into the `invoice` table (exact details of that table are defined in backend/db.instructions.md).

That row includes a column `extracted_text`. Its value MUST always follow this canonical multi-line template:

    EXTRACTED_INVOICE_TEXT_FORMAT = """
    Store Name: {store_name}
    Transaction Time: {transaction_time}
    Total Amount: {total_amount}
    Currency: {currency}
    Purchased Items:
    {purchased_items}
    """

Rules:
- `store_name` should be a clean string.
- `transaction_time` should be a timestamp or datetime string in ISO-8601 or the format defined in backend/db.instructions.md.
- `total_amount` is numeric rendered as string (e.g. "123.45").
- `currency` is a currency code or symbol (e.g. "GTQ").
- `purchased_items` is a bullet/line list of the parsed items, quantities and prices.

The FastAPI layer is responsible for making sure that when we go to persist `extracted_text`, it exactly matches this template.

If the agent output does not match, normalize it before persisting.


## 6. Error Handling and Logging

- Use `HTTPException` from FastAPI for all error responses.
- The `detail` field should always be a dict with `error` and `details`.
- Example:
    raise HTTPException(
        status_code=400,
        detail={"error": "out_of_scope", "details": "SearchAgent cannot answer personal finance therapy questions."}
    )

- Logging:
  - Create `logger = logging.getLogger(__name__)`.
  - Log high-level actions (e.g. "InvoiceAgent invoked", "RecommendationCoordinatorAgent rejected out_of_scope").
  - Do NOT log:
    - raw invoice images,
    - full `extracted_text`,
    - account balances,
    - card numbers,
    - PII.

No stack traces or secret keys in API responses.


## 7. Database and RLS (Do not inline schema here)

- The DB layer is authoritative for persistence. See backend/db.instructions.md.
- NEVER inline SQL or define table schemas in route code.
- If you need to indicate persistence or retrieval, insert a placeholder comment like:
    # TODO(db-team): fetch user profile (country, currency_preference) for this user_id
- All DB calls must assume:
  - RLS is active,
  - `user_id` from Supabase Auth is enforced server-side,
  - the caller cannot impersonate another user.


## 8. Summary Checklist for New Endpoints

- [ ] Auth via Supabase Bearer token (unless public by design).
- [ ] Parse request into strict Pydantic RequestModel.
- [ ] Domain/intention filter BEFORE calling any adk agent.
- [ ] Call ONE allowed adk agent.
- [ ] Map output into strict Pydantic ResponseModel and return it with `response_model=...`.
- [ ] If invoice data is involved, enforce the exact EXTRACTED_INVOICE_TEXT_FORMAT for `invoice.extracted_text`.
- [ ] No direct SQL or schema invention; leave `# TODO(db-team): ...`.
- [ ] Log non-sensitive info only.


## 9. Invoice Endpoints Reference

This section documents the complete invoice API surface.

### 9.1 POST /invoices/ocr

**Purpose:** Upload receipt image for OCR extraction (PREVIEW ONLY).

**Authentication:** Required (Supabase JWT token).

**Request:**
- Content-Type: `multipart/form-data`
- Field: `image` (file, required) - Receipt/invoice image (JPEG, PNG)
- Max size: 5MB

**Response Models:**
- `InvoiceOCRResponseDraft` - Successful extraction
  - `status: "DRAFT"`
  - `store_name: str`
  - `transaction_time: str` (ISO-8601)
  - `total_amount: float`
  - `currency: str` (e.g. "GTQ")
  - `items: List[PurchasedItemResponse]`
  - `category_suggestion: CategorySuggestionResponse`
- `InvoiceOCRResponseInvalid` - Image cannot be processed
  - `status: "INVALID_IMAGE"`
  - `reason: str` (human-readable explanation)

**Agent Interaction:**
- Calls `run_invoice_agent()` (single-shot multimodal vision workflow)
- Passes `user_categories` fetched from endpoint (not fetched by agent)
- Uses Gemini's native vision capabilities to read receipt image
- NO OCR text fallback - image is REQUIRED
- Temperature=0.0 for deterministic extraction
- Returns structured JSON via `response_mime_type="application/json"`

**RLS Behavior:**
- User profile and categories fetched with user's access token
- NO database persistence (preview only)
- Agent receives user context but does not write to DB

**Error Codes:**
- 401: Missing or invalid authentication token
- 400: Invalid file type, file too large, or out-of-scope request
- 500: Agent error or internal server error

---

### 9.2 POST /invoices/commit

**Purpose:** Persist a confirmed invoice to the database.

**Authentication:** Required (Supabase JWT token).

**Request Model:** `InvoiceCommitRequest`
```json
{
  "store_name": "Super Despensa Familiar",
  "transaction_time": "2025-10-30T14:32:00-06:00",
  "total_amount": "128.50",
  "currency": "GTQ",
  "purchased_items": "- Leche 1L (2x) @ Q12.50 = Q25.00\n- Pan integral @ Q15.00 = Q15.00",
  "storage_path": "12345678-9",
  "storage_path": "receipts/user-uuid/image-uuid.jpg"
}
```

**Response Model:** `InvoiceCommitResponse`
```json
{
  "status": "COMMITTED",
  "invoice_id": "invoice-uuid-here",
  "message": "Invoice saved successfully"
}
```

**Database Behavior:**
- Inserts record into `invoice` table
- Formats data into canonical `EXTRACTED_INVOICE_TEXT_FORMAT`
- RLS enforces `user_id = auth.uid()` automatically
- User can only create invoices for themselves

**Error Codes:**
- 401: Missing or invalid authentication token
- 400: Invalid request data (validation error)
- 500: Database persistence error

---

### 9.3 GET /invoices

**Purpose:** List all invoices belonging to the authenticated user.

**Authentication:** Required (Supabase JWT token).

**Query Parameters:**
- `limit: int = 50` - Maximum number of invoices to return
- `offset: int = 0` - Number of invoices to skip (pagination)

**Response Model:** `InvoiceListResponse`
```json
{
  "invoices": [
    {
      "id": "invoice-uuid",
      "user_id": "user-uuid",
      "storage_path": "receipts/user-uuid/image-uuid.jpg",
      "extracted_text": "Store Name: ...\nTransaction Time: ...\n...",
      "created_at": "2025-11-03T10:15:00Z",
      "updated_at": "2025-11-03T10:15:00Z"
    }
  ],
  "count": 1,
  "limit": 50,
  "offset": 0
}
```

**Database Behavior:**
- Queries `invoice` table with `.order("created_at", desc=True)`
- RLS automatically filters to `user_id = auth.uid()`
- Supports pagination via limit/offset
- Returns invoices newest first

**Error Codes:**
- 401: Missing or invalid authentication token
- 500: Database query error

---

### 9.4 GET /invoices/{invoice_id}

**Purpose:** Retrieve details of a single invoice by its ID.

**Authentication:** Required (Supabase JWT token).

**Path Parameters:**
- `invoice_id: str` - UUID of the invoice to retrieve

**Response Model:** `InvoiceDetailResponse`
```json
{
  "id": "invoice-uuid",
  "user_id": "user-uuid",
  "storage_path": "receipts/user-uuid/image-uuid.jpg",
  "extracted_text": "Store Name: Super Despensa\nTransaction Time: 2025-10-30T14:32:00-06:00\nTotal Amount: 128.50\nCurrency: GTQ\nPurchased Items:\n- Leche 1L (2x) @ Q12.50 = Q25.00\nNIT: 12345678-9",
  "created_at": "2025-11-03T10:15:00Z",
  "updated_at": "2025-11-03T10:15:00Z"
}
```

**Database Behavior:**
- Queries `invoice` table with `.eq("id", invoice_id)`
- RLS automatically enforces `user_id = auth.uid()`
- Returns 404 if invoice doesn't exist or belongs to another user

**Error Codes:**
- 401: Missing or invalid authentication token
- 404: Invoice not found or not accessible by user
- 500: Database query error

---

### 9.5 InvoiceAgent Architecture Summary

**Current Implementation (as of Nov 2025):**
- **NOT an ADK agent** - uses single-shot multimodal LLM workflow
- **Why:** Invoice extraction is deterministic; doesn't need agentic reasoning
- **Input:** Base64-encoded receipt image (REQUIRED, no OCR text fallback)
- **Context:** User categories and profile passed as parameters by endpoint
- **Process:** One call to Gemini's vision model with complete context
- **Output:** Structured JSON (`InvoiceAgentOutput`) with extracted data
- **Temperature:** 0.0 for deterministic extraction
- **Format:** `response_mime_type="application/json"` for structured output

**Endpoint Responsibilities:**
1. Authenticate user via Supabase Auth
2. Fetch `user_profile` (country, currency_preference)
3. Fetch `user_categories` (for category matching)
4. Call `run_invoice_agent()` with image + context
5. Map agent output to response model
6. Handle DRAFT vs INVALID_IMAGE status

**Agent Does NOT:**
- Fetch its own data (categories, profile)
- Use function-calling or tool orchestration
- Iterate or retry extractions
- Write to database directly
- Support OCR text input (image-only)
