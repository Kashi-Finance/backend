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
    NIT: {nit}
    """

Rules:
- `store_name` should be a clean string.
- `transaction_time` should be a timestamp or datetime string in ISO-8601 or the format defined in backend/db.instructions.md.
- `total_amount` is numeric rendered as string (e.g. "123.45").
- `currency` is a currency code or symbol (e.g. "GTQ").
- `purchased_items` is a bullet/line list of the parsed items, quantities and prices.
- `receipt_id` is the internal ID / storage reference for the uploaded invoice image.

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
