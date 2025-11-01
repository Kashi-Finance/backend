---
description: "Create or update an adk agent module (Google ADK) for this backend"
mode: Beast Mode
---

You are defining or updating an adk agent for the Kashi Finances backend.

Follow ALL rules below. Do not introduce new agents unless explicitly authorized.

1. Allowed agents
   - InvoiceAgent
   - RecommendationCoordinatorAgent
   - SearchAgent
   - FormatterAgent
   These are the ONLY adk agents. SearchAgent and FormatterAgent are AgentTools that RecommendationCoordinatorAgent uses internally.
   Do NOT create any other agent names or variants unless instructed.
   Do NOT expose SearchAgent or FormatterAgent directly to the HTTP layer; they are internal tools.

2. Responsibility
   - Each adk agent MUST have ONE clear business responsibility:
     - InvoiceAgent: extract structured invoice data from a receipt (store_name, transaction_time, total_amount, currency, purchased_items, receipt_id) and provide text for invoice.extracted_text in the canonical template.
     - RecommendationCoordinatorAgent: orchestrate recommendation logic for purchase goals, wishlist, budget hints, country/currency context; internally call SearchAgent and FormatterAgent.
     - SearchAgent (AgentTool): gather product / offer candidates given constraints (budget, preferred_store, country, etc.).
     - FormatterAgent (AgentTool): turn raw candidates into a final, structured, user-facing summary (prices, reasons, warnings).
   - The agent MUST refuse any request outside that scope.

3. Input / output schema
   - Define a clear typed Python interface for the agent:
     def run_agent(...typed params...) -> ReturnType:
   - Every parameter MUST have an explicit type hint (no untyped *args/**kwargs).
   - The ReturnType MUST be a TypedDict / dataclass / Pydantic model or similar strictly typed structure.
   - ALSO define an ADK `input_schema` and `output_schema` that:
     - are strictly JSON-serializable,
     - describe each field (meaning, allowed values),
     - match the Python signature.
   - No silent defaults. If a field is required, mark it required. If optional, mark it optional and explain when it's used.

   Always use the most recent version of the Google ADK documentation when creating or modifying these schemas.

4. Out-of-scope guardrail
   - The agent MUST explicitly detect if the request is out-of-scope.
   - If out-of-scope:
     - DO NOT proceed with Gemini calls or reasoning.
     - Return a structured "out_of_scope" style response. Example fields:
       { "status": "out_of_scope", "reason": "InvoiceAgent only processes receipts" }
   - Never attempt to answer unrelated general questions.

5. Privacy
   - Do NOT log raw invoice images, full purchase history, account balances, or personal info.
   - Only log high-level events, e.g. "InvoiceAgent parsed invoice for store_name='Supertienda XYZ'."
   - NEVER include secrets or Supabase tokens in logs.

6. Persistence boundary
   - adk agents MUST NOT write to the database directly.
   - If something needs to be stored (e.g. invoice info for later accounting), return a structured object and add a comment:
       # handled by API/db layer under RLS
   - For invoice data:
     - Include all fields required to build the canonical multi-line template used for `invoice.extracted_text`:
           Store Name: {store_name}
           Transaction Time: {transaction_time}
           Total Amount: {total_amount}
           Currency: {currency}
           Purchased Items:
           {purchased_items}
           Receipt Image ID: {receipt_id}
     - The API/db layer will persist this text EXACTLY in that format.

7. Country / currency context
   - For recommendation flows, include country and currency_preference (from the user's profile, obtained by the API layer after Supabase Auth).
   - The agent should use these fields to localize price, availability, etc.
   - The agent should return localized info in a structured form (not freeform paragraphs).

8. Return shape
   - The final return value MUST:
     - Be strictly typed.
     - Contain only fields the API actually needs to expose or persist.
     - Be easy to map into a Pydantic ResponseModel.
   - For RecommendationCoordinatorAgent, final output should already be "frontend-friendly":
     - normalized price strings with currency,
     - short reason/explanation,
     - flags like "over_budget": true/false,
     - etc.

9. No DB guessing
   - NEVER define SQL here.
   - NEVER guess table names, column names, or RLS rules.
   - If you need to mention persistence, add:
       # TODO(db-team): persist recommendation snapshot according to backend/db.instructions.md
     and stop there.

10. Style
   - Every function and field MUST have explicit type hints.
   - No implicit globals.
   - No deployment logic (Cloud Run, etc.).
   - The agent MUST be callable programmatically by the FastAPI layer, not by end-users directly.

Return ONLY the code / diffs to create or update the agent module according to these rules.
