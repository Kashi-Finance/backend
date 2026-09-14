---
description: "Scaffold a new FastAPI endpoint in the Kashi Finances backend (service or single-shot LLM workflow, no agent framework)"
mode: Beast Mode
---

You are helping build or update a FastAPI endpoint in the **Kashi Finances backend**.

Follow **ALL rules below**. Do not skip any step. Do not introduce LLM workflows, database tables, or fields that are not defined in the documentation.

---

## 1. Scope and references

* This backend serves the **Kashi Finances mobile app** via HTTP.

* Most endpoints are pure CRUD over services. Exactly two endpoints use
  single-shot LLM workflows (no agent framework, no Google ADK):
  invoice OCR (`backend/llm/invoice/`) and recommendations
  (`backend/services/recommendation_service.py`).

* You MUST comply with and frequently consult:

  * `.github/instructions/api-architecture.instructions.md`
  * `.github/instructions/llm-workflows.instructions.md`
  * `.github/instructions/db.instructions.md`
  * `DB-documentation.md`

* Always verify table fields, relationships, and deletion rules directly from **DB-documentation.md** before adding or modifying any database logic.

---

## 2. Auth rules

* Unless explicitly documented as `public`, every route is **protected**.
* Implement the **Supabase Auth pipeline**:

  1. Read `Authorization: Bearer <token>`.
  2. Verify token signature and expiration using Supabase Auth.
  3. Extract `user_id = auth.uid()`.
  4. If invalid or missing, raise `HTTP 401 Unauthorized`.
  5. Ignore any `user_id` in client request body or params; always trust the token.
* The endpoint acts **only** on behalf of that authenticated `user_id`.

---

## 3. Request / Response models

* Define a **Pydantic RequestModel** and **ResponseModel** in `backend/schemas/...`.
* Use **strict typing** for all fields (no implicit types or `Any`).
* Add docstrings/comments for each field: meaning, allowed values, and units.
* The FastAPI route MUST declare `response_model=ResponseModel`.
* The function MUST return data that exactly matches the ResponseModel.

---

## 4. LLM-workflow interaction rules (only if the endpoint uses one)

* Most endpoints MUST NOT call any LLM workflow (pure service + DB logic).
* If the endpoint's domain logic involves the invoice OCR or recommendation
  workflow, it may call **exactly that one workflow's public function**
  (`run_invoice_agent()` or `query_recommendations()`).
* Before calling a workflow, verify that the request is within its supported domain.
* If it's not in-scope, do **not** call Gemini; instead raise `HTTP 400` with:

  ```json
  {"error": "out_of_scope", "details": "..."}
  ```
* Pass a **strictly typed payload** to the workflow, never raw JSON.
* Normalize the workflow's structured response to match the defined `ResponseModel`.

---

## 5. Database and persistence

* **Never write raw SQL** inline.
* Always reference schemas, relationships, and constraints from `DB-documentation.md`.
* Apply the correct **delete rules** exactly as defined.
* Assume **Row Level Security (RLS)** is active and scope queries by `user_id = auth.uid()`.
* For complex transactions, follow existing patterns from other backend modules.

---

## 6. Logging and observability

* Use `logger = logging.getLogger(__name__)`.
* Log only high-level actions, for example:

  * "Workflow invoked successfully"
  * "Data persisted"
* **Never** log sensitive data (invoice text, raw receipts, user financial details, or embeddings).

---

## 7. Output and structure

* The generated code MUST:

  * Add or extend a router file under `backend/routes/...`
  * Define or reuse schemas in `backend/schemas/...`
  * Import and use the correct service or LLM workflow function
    (`backend/services/...` or `backend/llm/...`)
  * Expose a FastAPI route using `@router.post(...)`, `@router.get(...)`, etc., with `response_model=ResponseModel`.
  * Follow all auth, validation, and persistence steps outlined above.

* After implementation, update **`API-endpoints.md`** to include:

  * Route path and HTTP method.
  * Request and response model summaries.
  * Auth requirements.
  * Any specific LLM-workflow interactions.

---

## 8. Style and quality

* Every function and class MUST include explicit type hints.
* Follow existing backend conventions for consistency.
* Remove unused imports or dead code.
* Do not use deployment stubs or placeholder logic.
* Ensure **API-endpoints.md** accurately documents your changes.

Return ONLY the code or diffs needed to implement the new or updated endpoint following all the rules above.

---

## 9. Documentation Update

* After implementing or modifying an LLM-workflow endpoint, ensure you update the following documentation files:

  * API-endpoints.md — Include method, route, models, auth, and workflow interactions.

  * kashi-agents-architecture.md — Reflect structural changes to the LLM workflows
    (note: legacy filename; content describes single-shot workflows, not agents).

  * The specific workflow specification file, for example:

    * For recommendation-related endpoints → update recommendation-system-specs.md

    * For invoice OCR → update invoice-agent-specs.md (legacy filename)

Each update must summarize the purpose, inputs/outputs, and how the endpoint or workflow integrates within the Kashi Finances system.