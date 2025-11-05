---
description: "Scaffold a new FastAPI endpoint that calls one allowed ADK agent"
mode: Beast Mode
---

You are helping build or update a FastAPI endpoint in the **Kashi Finances backend**.

Follow **ALL rules below**. Do not skip any step. Do not introduce new agents, database tables, or fields that are not defined in the documentation.

---

## 1. Scope and references

* This backend serves the **Kashi Finances mobile app** via HTTP.

* Some endpoints expose domain-specific functionality backed by **ADK agents (Google ADK)**.

* You MUST comply with and frequently consult:

  * `.github/instructions/api-architecture.instructions.md`
  * `.github/instructions/adk-agents.instructions.md`
  * `.github/instructions/db.instructions.md`
  * `DB documentation.md`

* Always use the **most recent version** of the Google ADK documentation, available at [https://google.github.io/adk-docs/](https://google.github.io/adk-docs/).

* Always verify table fields, relationships, and deletion rules directly from **DB documentation.md** before adding or modifying any database logic.

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

## 4. Agent interaction rules

* If the endpoint’s domain logic involves AI assistance or semantic reasoning, it may call **exactly one allowed ADK agent** or an **AgentTool** (another adk agent but as a tool for the main Agent).
* Always check the **latest ADK docs** for correct invocation syntax and payload structure.
* Before calling an agent, verify that the request is within the agent’s supported domain.
* If it’s not in-scope, do **not** call ADK or Gemini; instead raise `HTTP 400` with:

  ```json
  {"error": "out_of_scope", "details": "..."}
  ```
* Pass a **strictly typed payload** to the agent, never raw JSON.
* Normalize the agent’s structured response to match the defined `ResponseModel`.

---

## 5. Database and persistence

* **Never write raw SQL** inline.
* Always reference schemas, relationships, and constraints from `DB documentation.md`.
* Apply the correct **delete rules** exactly as defined.
* Assume **Row Level Security (RLS)** is active and scope queries by `user_id = auth.uid()`.
* For complex transactions, follow existing patterns from other backend modules.

---

## 6. Logging and observability

* Use `logger = logging.getLogger(__name__)`.
* Log only high-level actions, for example:

  * "Agent invoked successfully"
  * "Data persisted"
* **Never** log sensitive data (invoice text, raw receipts, user financial details, or embeddings).

---

## 7. Output and structure

* The generated code MUST:

  * Add or extend a router file under `backend/routes/...`
  * Define or reuse schemas in `backend/schemas/...`
  * Import and use the correct ADK agent from `backend/agents/...`
  * Expose a FastAPI route using `@router.post(...)`, `@router.get(...)`, etc., with `response_model=ResponseModel`.
  * Follow all auth, validation, and persistence steps outlined above.

* After implementation, update **`API-endpoints.md`** to include:

  * Route path and HTTP method.
  * Request and response model summaries.
  * Auth requirements.
  * Any specific agent interactions or orchestration details.

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

* After implementing or modifying an ADK-related endpoint, ensure you update the following documentation files:

  * API-endpoints.md — Include method, route, models, auth, and agent interactions.

  * kashi-agents-architecture.md — Reflect structural or orchestration changes among agents.

  * The specific agent specification file, for example:

    * For recommendation-related endpoints → update recommendation-agent-specs.md

    * For search tools → update search-agent-specs.md

    * For formatter tools → update formatter-agent-specs.md

Each update must summarize the purpose, inputs/outputs, and how the endpoint or agent integrates within the Kashi Finances system.