---
description: "Scaffold a new FastAPI endpoint in the Kashi Finances backend (non-agent logic)"
mode: Beast Mode
---

You are helping build or update a FastAPI endpoint in the **Kashi Finances backend**.

Follow **ALL the rules below**. Do not skip any step. Do not introduce new database tables, fields, or logic that are not defined in the documentation.

---

## 1. Scope and References

* This backend serves the **Kashi Finances mobile app** via HTTP.
* Endpoints expose RESTful domain functionality such as **accounts**, **categories**, **budgets**, and **transactions**.
* You MUST comply with and frequently consult:

  * `.github/instructions/api-architecture.instructions.md`
  * `.github/instructions/db.instructions.md`
  * `DB documentation.md`
* Always verify table fields, relationships, and deletion rules directly from **DB documentation.md** before adding or modifying any database logic.

---

## 2. Auth Rules

* Unless explicitly documented as `public`, every route is **protected**.
* Implement the **Supabase Auth pipeline**:

  1. Read `Authorization: Bearer <token>`.
  2. Verify token signature and expiration using Supabase Auth.
  3. Extract `user_id = auth.uid()`.
  4. If invalid or missing, raise `HTTP 401 Unauthorized`.
  5. Ignore any `user_id` in client request body or parameters; always trust the token.
* The endpoint acts **only** on behalf of that authenticated `user_id`.

---

## 3. Request / Response Models

* Define a **Pydantic RequestModel** and **ResponseModel** in `backend/schemas/...`.
* Use **strict typing** for all fields (no implicit types or `Any`).
* Add docstrings or comments for each field: meaning, allowed values, and units.
* The FastAPI route MUST declare `response_model=ResponseModel`.
* The function MUST return data that exactly matches the `ResponseModel`.

---

## 4. Database and Persistence

* **Never write raw SQL** inline.
* Always reference schemas, relationships, and constraints from `DB documentation.md`.
* Apply the correct **delete rules** exactly as defined.
* Assume **Row Level Security (RLS)** is active and scope queries by `user_id = auth.uid()`.
* For create, read, update, or delete operations, follow the existing CRUD patterns used in similar modules.
* For complex operations, ensure transactional safety using existing helper functions or ORM patterns.

---

## 5. Validation and Domain Logic

* Validate request data carefully before any DB operation.
* Reject malformed input with clear `HTTP 400` errors.
* Use helper functions or services for repetitive domain logic.
* If the endpoint affects multiple entities (e.g., category deletion affects budgets), ensure cascading updates comply with DB rules.

---

## 6. Logging and Observability

* Use `logger = logging.getLogger(__name__)`.
* Log high-level actions only, for example:

  * "Account created successfully"
  * "Budget updated"
* **Never** log sensitive data (user tokens, financial values, or identifiers).

---

## 7. Output and Structure

* The generated code MUST:

  * Add or extend a router file under `backend/routes/...`
  * Define or reuse schemas in `backend/schemas/...`
  * Implement FastAPI routes using `@router.post(...)`, `@router.get(...)`, etc., with `response_model=ResponseModel`.
  * Follow all authentication, validation, and persistence steps outlined above.

* After implementation, update **`API-endpoints.md`** to include:

  * Route path and HTTP method.
  * Request and response model summaries.
  * Auth requirements.
  * Domain-specific notes such as immutability, ownership, or deletion behavior.

---

## 8. Style and Quality

* Every function and class MUST include explicit type hints.
* Follow existing backend conventions for naming, file organization, and imports.
* Remove unused imports or dead code.
* Do not use placeholder or temporary logic.
* Ensure **API-endpoints.md** accurately documents your changes.

Return ONLY the code or diffs needed to implement the new or updated endpoint following all the rules above.

---

## 9. Documentation Update

* After implementing or modifying any endpoint, ensure all related details are added or updated in API-endpoints.md, including:

  * Route path and HTTP method

  * Request and response models

  * Auth requirements

  * Domain rules or special notes (immutability, ownership, deletion behavior)

Each update must summarize the purpose, inputs/outputs, and how the endpoint or agent integrates within the Kashi Finances system.