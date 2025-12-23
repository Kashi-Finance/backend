# Kashi Finances – Copilot Instructions (Backend / adk agents API)

## 1. Project Scope

- This repository is ONLY for the backend service that powers Kashi Finances.
- The backend:
  - Exposes a FastAPI HTTP API for the mobile app.
  - Orchestrates domain-specific adk agents built on Google ADK.
  - Performs request validation, authentication, and enforcement of business rules.
- This repository is NOT responsible for:
  - Flutter UI code.
  - Database schema design, migrations, SQL, or RLS policy definitions (those live in backend/db.instructions.md).
  - Academic docs, reports, slides, etc. Do not generate them here.

Always assume this service will be called by an authenticated Kashi Finances client that expects stable JSON contracts.

Always use the most recent version of the Google ADK documentation when creating or modifying adk agents or their schemas.


## 2. Tech Stack and Conventions

- Language: Python.
- Web framework: FastAPI.
- Request and response validation:
  - ALWAYS define a Pydantic request model (strict types, no `Any`) for each endpoint.
  - ALWAYS define a Pydantic response model and set it as `response_model=...` in the FastAPI route decorator.
  - The endpoint must only return instances (or dicts validated against) that response model.
- Each function, method, and agent MUST use explicit Python type hints.
- Directory layout (top-level expectation, do not invent other folders without being asked):
  - `backend/routes/`          → FastAPI routers (HTTP surface)
  - `backend/schemas/`        → Pydantic models for request/response
  - `backend/auth/`           → Auth helpers (Supabase token verification)
  - `backend/agents/`         → adk agents code
  - `backend/services/`       → Business logic wrappers/orchestrators
  - `backend/utils/`          → Logging, common helpers
  - `backend/db/` or similar  → Data access layer (MUST follow backend/db.instructions.md rules)
- Use `logger = logging.getLogger(__name__)` in every module that logs.
- Never log sensitive financial details, invoice images, or full raw invoice text.

Do not assume deployment steps. Local dev is Docker-based. Cloud deployment details are intentionally omitted in this version.

### Package Manager: uv

This project uses **[uv](https://docs.astral.sh/uv/)** as the Python package and project manager (NOT pip).

- **Install dependencies:** `uv sync` (reads from `pyproject.toml` and `uv.lock`)
- **Add a dependency:** `uv add <package>`
- **Add a dev dependency:** `uv add --dev <package>`
- **Run scripts:** `uv run <script.py>` or `uv run pytest`
- **Lock file:** `uv.lock` (committed to version control)
- **Virtual environment:** Managed automatically by uv in `.venv/`

**DO NOT use pip directly.** All dependency management must go through uv.


## 3. Security and Authentication

ALL PROTECTED ENDPOINTS MUST FOLLOW THIS AUTH PIPELINE:

1. Read header: `Authorization: Bearer <token>`.
2. Verify signature and expiration using Supabase Auth.
3. Extract `user_id` from the validated token (`auth.uid()`).
4. If verification fails or token is missing → raise HTTP 401 Unauthorized.
5. Ignore / override any `user_id` sent by the client. The only source of truth for `user_id` is the Supabase Auth token.
6. All DB reads/writes MUST assume Row Level Security (RLS) is active and already enforces `user_id = auth.uid()` on every financial row.
7. Optionally (recommended), fetch the user's profile (country, currency_preference, etc.) for context because some adk agents need this context for localized answers.

No request should ever invoke an adk agent if step 1-4 above did not fully pass, unless the endpoint is explicitly documented as public in the endpoint spec.

The authentication rules and which routes are public vs protected are defined in the endpoint documentation. Obey them exactly.

**IMPORTANT**: When integrating with Supabase (authentication, database, storage, etc.), **always** refer to `.github/instructions/supabase.instructions.md` for the authoritative rules on:
- API key usage (publishable vs secret keys)
- JWT validation and signing keys
- RLS policies and security
- Schema management and migrations
- Best practices and safety guidelines

Never use deprecated `SUPABASE_ANON_KEY` or `SUPABASE_SERVICE_ROLE_KEY`. Always use `SUPABASE_PUBLISHABLE_KEY` for client initialization.


## 4. Endpoint Behavior Requirements

When you create or modify an endpoint:

- Import `APIRouter` from FastAPI.
- Define:
  - `RequestModel` (Pydantic BaseModel) with strict types.
  - `ResponseModel` (Pydantic BaseModel) with strict types.
- In the endpoint function:
  1. Validate auth via the Supabase pipeline described above (unless route is explicitly public).
  2. Parse and validate the incoming request body into `RequestModel`.
  3. Apply domain-intent filtering:
     - Check if the request is actually in-scope for the target adk agent.
     - If the request intent is out-of-scope, immediately raise `HTTPException(status_code=400, detail={ "error": "out_of_scope", "details": "..." })`.
     - Do NOT call Gemini / ADK at all in that case.
  4. Call EXACTLY ONE allowed adk agent (see section 5 below), passing only the structured, validated data.
  5. Receive the agent result, map it into `ResponseModel`.
  6. Return the validated response model. The FastAPI decorator MUST declare `response_model=ResponseModel`.

- Documentation: ALWAYS update `API-endpoints.md` when creating or modifying an endpoint if the change is significant and should be documented for the team or API consumers.

- Error handling:
  - Use `HTTPException` with a `status_code` and a dict like `{ "error": "<short_code>", "details": "<human_readable>" }`.
  - Do not leak stack traces, raw agent messages, or secrets.

- Logging:
  - Log only high-level events (success/fail, which agent got called).
  - Do not log invoice images, extracted invoice text, or personal financial amounts in clear form.


## 5. AI Components (LLM Workflows)

> **Architecture Note:** The project uses simplified LLM workflows instead of complex multi-agent architectures. The recommendation system uses Gemini with Google Search grounding for web-verified product recommendations.

There are exactly **two (2)** AI-powered components in this project:

### 5.1 InvoiceAgent (Single-Shot Multimodal Workflow)
- **Implementation:** Single-shot Gemini vision call
- **Purpose:** OCR and structured extraction from receipt images
- **NOT an ADK agent:** Uses direct Gemini API

### 5.2 Recommendation System (Web-Grounded LLM)
- **Implementation:** Single-shot Gemini call with Google Search grounding
- **Model:** Gemini 2.5 Flash (`gemini-2.5-flash`)
- **Purpose:** Product recommendations with REAL web data via Google Search
- **NOT an ADK agent:** Uses Google Gen AI SDK with Google Search tool
- **Location:** `backend/services/recommendation_service.py`

### Rules:
- Do NOT create new ADK agents
- Do NOT reference the old multi-agent architecture (RecommendationCoordinatorAgent, SearchAgent, FormatterAgent)
- Each AI component MUST:
  - Have a single, well-defined purpose
  - Explicitly reject out-of-domain requests
  - Return strict typed JSON output
  - Never perform database writes directly (persistence handled by API layer under RLS)

For detailed specifications, see `.github/instructions/adk-agents.instructions.md`.


## 6. Database / Persistence Rules

- The source of truth for data access, table structures, queries, and RLS is `backend/db.instructions.md`.
- Application code MUST NOT invent schemas, table names, SQL queries, RLS logic, migrations, triggers, etc.
- If you need to persist or read something, add a comment like:
  `# TODO(db-team): persist invoice data according to backend/db.instructions.md`
  and stop there.
- `invoice.extracted_text` MUST ALWAYS respect the required canonical format described in backend/api-architecture.instructions.md and backend/agents.instructions.md.

Never bypass RLS. Assume every row is protected by `user_id = auth.uid()`.

## 6a. API Contract & Documentation Source of Truth

**CRITICAL: `API-endpoints.md` is the SINGLE SOURCE OF TRUTH for all REST endpoint contracts, request/response shapes, field names, and types.**

### Documentation Structure (Progressive Disclosure)

The API documentation follows Anthropic's progressive disclosure pattern for optimal AI agent consumption:

```
API-endpoints.md           ← Concise index - START HERE
└── docs/api/
    ├── README.md          ← Navigation guide
    ├── cross-cutting.md   ← Auth, response formats, dependencies
    ├── auth-profile.md     ← Auth & Profile endpoints (full details)
    ├── accounts.md        ← Account endpoints (full details)
    ├── categories.md      ← Category endpoints (full details)
    ├── transactions.md    ← Transaction endpoints (full details)
    ├── invoices.md        ← Invoice workflow (full details)
    ├── budgets.md         ← Budget endpoints (full details)
    ├── recurring.md       ← Recurring transactions (full details)
    ├── transfers.md       ← Transfer endpoints (full details)
    ├── wishlists.md       ← Wishlist endpoints (full details)
    └── recommendations.md ← AI recommendations (full details)
```

### How to Navigate the Documentation

1. **Start with `API-endpoints.md`** - the index provides:
   - Quick reference tables for all endpoints
   - Links to detailed documentation per domain
   - Response format summaries
   - Feature dependency overview

2. **Load detailed docs on-demand** - only read `docs/api/<domain>.md` when you need:
   - Full request/response schemas with all fields
   - Complete behavior descriptions
   - All status codes and error conditions
   - Implementation examples

3. **For cross-cutting concerns** - read `docs/api/cross-cutting.md` for:
   - Authentication flow details
   - Standard response format
   - Feature dependencies diagram
   - Security patterns

### When Working on Endpoints

1. **Always refer to `API-endpoints.md` first** for the authoritative contract.
2. If you find **inconsistencies** between `API-endpoints.md` and other instruction files (e.g., `api-architecture.instructions.md`, `invoice-agent-specs.md`), **treat `API-endpoints.md` as correct** and update the conflicting file to match.
3. If you need to change an endpoint contract:
   - Update `API-endpoints.md` index first
   - Update the corresponding `docs/api/<domain>.md` file
   - Propagate changes to tests, schemas, services, agent specs
4. All Pydantic request/response models in `backend/schemas/` **MUST match exactly** the shape and field names documented in `API-endpoints.md`.

This ensures:
- No ambiguity about what the frontend can expect
- Type safety across backend/frontend integration
- Consistency in Pydantic validation
- Single point of reference when debugging API issues
- Optimal context loading for AI agents (progressive disclosure)


## 7. Style, Formatting, and Quality

- Always include full type hints (`def func(arg: str) -> ResponseModel:`).
- Use Pydantic models for any structured request/response payload.
- Keep functions short, single-responsibility.
- Follow the 6-step endpoint flow in section 4 every time.
- All new code MUST be compatible with Docker-based local execution.


## 8. Testing / CI Expectations

All new backend code (routes, services, auth helpers, and adk agent wrappers) MUST include or update **pytest tests** under the `tests/` folder. The CI workflow executes pytest automatically, and missing or failing tests will block merges.

### CI Workflow Context

The GitHub Actions pipeline executes the following steps:

```bash
uv sync                    # Install dependencies from uv.lock
supabase db start          # Local Postgres + Supabase stack
uv run pytest -q           # Run tests via uv
```

If the `tests/` folder exists, pytest must pass. If it doesn't exist, CI will skip tests (but this is not desired long term).

### General Testing Rules

* Place all tests under `tests/` with clear module structure mirroring `backend/`.
* Each new FastAPI endpoint must have corresponding tests that use `TestClient`.
* Include realistic but **mocked** data for ADK agent interactions.
* Use **mocking** for all external dependencies:

  * No real Gemini or Supabase Cloud calls.
  * Mock Supabase Auth validation (simulate valid `user_id`).
  * For DB access, test the logic layer only or use existing local fixtures.

### Required Tests Per Endpoint

Each new endpoint must include:

1. **Happy Path Test**

   * Valid `Authorization: Bearer <fake>` header.
   * Request body conforms to `RequestModel`.
   * Response conforms to `ResponseModel` (validated by `response_model=...`).

2. **Failure Path Tests**

   * Invalid or missing token → Expect `401 Unauthorized`.
   * Out-of-scope request → Expect `400 Bad Request` with `{"error": "out_of_scope"}`.

3. **Validation Tests**

   * Invalid request data must raise validation errors via Pydantic.

### Pydantic Schema Testing

For each new or modified schema in `backend/schemas/`:

* Add a test validating `.model_validate({...})` with sample data.
* Add negative tests for missing/invalid fields.

### Logging and Side Effects

* Tests must not log or store sensitive financial data.
* Never connect to production Supabase or external APIs.

### Prohibited Practices

* Do not invent schema or DB logic in tests (reference `backend/db.instructions.md`).
* Do not use hardcoded credentials or production URLs.

### Summary for Copilot

When generating or updating code:

* **Always** create or update pytest tests under `tests/` for each new module or endpoint.
* Ensure tests import code with absolute imports (e.g. `from backend.routes.x import router`).
* CI expects `pytest` to run cleanly on Docker-based local execution.
* Keep all tests deterministic and network-free.

* Creating documents after finishing a task is not necessary and should only be done if requested.


Do not produce UI code here.
Do not produce deployment scripts here.
Do not produce academic / report prose here.
Only produce backend code, tests, and docs consistent with these rules.
