---
description: "Scaffold a new FastAPI endpoint that calls one allowed adk agent"
mode: Beast Mode
---

You are helping build a new FastAPI endpoint in the Kashi Finances backend.

Follow ALL rules below. Do not skip any step. Do not introduce new agents or new database tables.

1. Scope
   - This backend serves the Kashi Finances mobile app via HTTP.
   - Endpoints expose domain-specific functionality backed by adk agents (Google ADK).
   - You MUST comply with:
     - .github/copilot-instructions.md
     - backend/api-architecture.instructions.md
     - backend/agents.instructions.md
     - backend/db.instructions.md
   - Always use the most recent version of the Google ADK documentation when interacting with adk agents.

2. Auth
   - Unless explicitly documented as `public`, the route is protected.
   - Implement the Supabase Auth pipeline:
     a) Read `Authorization: Bearer <token>`
     b) Verify token signature & expiration with Supabase Auth
     c) Extract `user_id = auth.uid()`
     d) If invalid/missing -> raise HTTP 401
     e) Ignore any `user_id` in the client body or params; always trust the token
   - The endpoint will act on behalf of that `user_id` only.

3. Request / response models
   - Create a Pydantic RequestModel with STRICT types for all request fields.
   - Create a Pydantic ResponseModel with STRICT types for the response.
   - Add docstrings / comments for each field (what it means, allowed values).
   - The FastAPI route MUST declare `response_model=ResponseModel`.
   - The function MUST return ONLY data that matches ResponseModel exactly.

4. Domain / intent filter
   - Before calling any agent, check if the request is in-scope for that agent.
   - If it's not in-scope:
     - Do NOT call Gemini / ADK.
     - Raise `HTTPException(status_code=400, detail={"error":"out_of_scope","details":"..."})`.

5. Agent call
   - You may call EXACTLY ONE allowed adk agent:
     - InvoiceAgent
     - RecommendationCoordinatorAgent
     - SearchAgent (AgentTool of RecommendationCoordinatorAgent)
     - FormatterAgent (AgentTool of RecommendationCoordinatorAgent)
   - For recommendation-related flows, call ONLY RecommendationCoordinatorAgent and let it internally use SearchAgent / FormatterAgent as AgentTools.
   - Pass a strictly typed payload to the agent, never raw request JSON.
   - Always use the most recent version of the Google ADK documentation for how to invoke adk agents and their AgentTools.

6. Normalization and output
   - Take the agent's structured output.
   - Normalize / validate it against ResponseModel.
   - Return that ResponseModel instance (or a `return ResponseModel(...)`).
   - For invoice flows, ensure that any `invoice.extracted_text` that will be persisted later matches EXACTLY the canonical multi-line template in backend/api-architecture.instructions.md.
     The endpoint MUST normalize to that template before persistence.

7. Persistence
   - DO NOT write SQL inline.
   - DO NOT guess table names or columns.
   - Instead, insert placeholder comments like:
       # TODO(db-team): persist invoice data according to backend/db.instructions.md
     or
       # TODO(db-team): save embeddings using text-embedding-3-small
   - Assume RLS is active and all queries run with `user_id = auth.uid()`.

8. Logging
   - Use `logger = logging.getLogger(__name__)`.
   - Log only high-level events (e.g. "InvoiceAgent called").
   - Never log sensitive invoice text, raw receipts, or full financial details.

9. Output format
   - The final code you generate MUST:
     - Create/extend a router file in `backend/routes/...`
     - Define RequestModel and ResponseModel in `backend/schemas/...`
     - Import and use the correct adk agent from `backend/agents/...`
     - Expose the FastAPI route with `@router.post(...)` (or `get`, etc.) and `response_model=ResponseModel`.
     - Follow all steps above in order, especially auth and domain filtering.

10. Style
   - Every function and method MUST have explicit type hints.
   - No placeholder logic for deployment or Cloud Run.
   - If you need DB info, add a TODO comment pointing to backend/db.instructions.md
     instead of inventing anything.

Return ONLY the code / diffs needed to add this new endpoint following these rules.
