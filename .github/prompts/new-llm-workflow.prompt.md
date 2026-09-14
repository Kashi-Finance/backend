---

description: "Create or update a single-shot LLM workflow module (no agent framework) for this backend"
mode: Beast Mode
----------------

You are defining or updating an LLM workflow for the Kashi Finances backend.

There is NO agent framework in this project (no Google ADK, no runners, no tool
loops, no AgentTools). All AI features are single-shot `google-genai` SDK calls.
You MUST obey ALL rules below. Do not introduce agents, frameworks, database
tables, or fields that are not defined in the documentation.

1. Allowed LLM workflows (names + roles)
   These are the ONLY LLM workflows. Do NOT create any other workflow names,
   variants, or siblings unless explicitly instructed.

   * `run_invoice_agent()` in `backend/llm/invoice/` (legacy name; single-shot
     multimodal OCR workflow — NOT an agent)
   * `query_recommendations()` / `retry_recommendations()` in
     `backend/services/recommendation_service.py` (single-shot grounded LLM call;
     prompts in `backend/llm/recommendation/prompts.py`)

   Deleted and FORBIDDEN (do not reference, reintroduce, or scaffold):
   `RecommendationCoordinatorAgent`, `SearchAgent`, `FormatterAgent`, ADK
   `coordinator.py` / `tools.py` / ADK `schemas.py`, ADK Runner integration,
   `NEEDS_CLARIFICATION` status.

   Rules:

   * Recommendation flows live in the service layer, which performs ONE grounded
     Gemini call internally. There are no sub-workflows to call.
   * Do NOT expose any internal helper directly to the HTTP layer.

2. Business responsibility of each workflow
   Each LLM workflow MUST have ONE clear, narrow responsibility and MUST refuse
   anything outside that scope.

   * Invoice OCR workflow (`run_invoice_agent`)
     Goal: given an invoice/receipt image, extract structured purchase data and return a validated draft of the expense.
     It must return:

     * store_name
     * transaction_time
     * total_amount
     * currency
     * purchased_items[] (description, quantity, unit_price / total_price)
     * category_suggestion (match_type + either category_id/category_name OR proposed_name)
     * status:

       * `"DRAFT"` if usable
       * `"INVALID_IMAGE"` if not usable
       * `"OUT_OF_SCOPE"` if not a receipt task
         It also must provide the canonical multi-line string that will later go into `invoice.extracted_text` in DB:

     ```
     Store Name: {store_name}
     Transaction Time: {transaction_time}
     Total Amount: {total_amount}
     Currency: {currency}
     Purchased Items:
     {purchased_items}
     ```

   * Recommendation workflow (`query_recommendations` / `retry_recommendations`)
     Goal: answer a purchase-goal query with grounded product recommendations.
     Tasks:

     * Read the user's query (`query_raw`), budget, context (country, preferred_store, user_note, extra_details).
     * Validate intent (block sexual content, weapons/illicit goods, obvious scams or impossible requests → `"NO_VALID_OPTION"`).
     * Perform ONE Gemini 2.5 Flash call with the Google Search grounding tool
       (`types.Tool(google_search=types.GoogleSearch())`, temperature 0.2–0.3,
       max 4096 output tokens).
     * Produce the final structured response for the mobile app:

       * `"OK"` with up to 3 ranked options (`products[]` with product_title, price_total, seller_name, url, pickup_available, warranty_info, copy_for_user, badges[])
       * `"NO_VALID_OPTION"` with `reason` if nothing survived filtering.
     * Grounding metadata (`web_search_queries`, `grounding_chunks{uri,title,domain}`)
       MUST be captured for auditability.

   Guardrail for ALL workflows:

   * MUST refuse (`out_of_scope` / `INVALID_IMAGE` / `NO_VALID_OPTION`) if the request:

     * is sexual/erótico explícito,
     * is criminal/armas ilegales/conducta peligrosa,
     * is incoherent with personal finance / recommendations / expense logging.
   * MUST NOT answer general chit-chat.
   * MUST NOT provide advice outside its vertical.

3. Context-passing philosophy (critical — replaces the old tool-calling model)
   The model NEVER calls tools or fetches data. The endpoint/service layer fetches
   ALL context BEFORE the single LLM call and injects it into the prompt text.

   Rules:

   * Before the LLM call, the caller MUST resolve: authenticated `user_id`
     (from Supabase Auth only), `getUserProfile` (country, currency_preference,
     locale), `getUserCategories` (expense categories for matching).
   * Document in the prompt builder which context fields exist and their shapes.
   * For deterministic substeps, DO NOT let the LLM freestyle. Instead do the
     deterministic work in Python (e.g. MIME sniffing, JSON repair, Pydantic
     validation) around the single LLM call.
   * You MAY propose new pre-call helper functions ONLY if they are deterministic,
     backend-implementable, and obviously needed (e.g. `getUserProfile`,
     `getUserCountry`, `getUserCategories`). But DO NOT create a new WORKFLOW
     unless explicitly authorized.

4. Pre-call context helpers that MUST be documented in the prompt builder
   The prompt builder you generate MUST document (at minimum) these helpers so
   future readers know what context the prompt expects:

   * `getUserCountry(user_id)`
     Purpose: Return the user's ISO-2 country code. Used to localize seller availability and currency context.
     Input:

     ```json
     { "user_id": "uuid" }
     ```

     Output:

     ```json
     { "country": "GT" }
     ```

     Behavior:

     * Reads from `profile.country`.
     * If missing, default `"GT"`.
       Security:
     * Backend passes the real authenticated `user_id`.
     * The workflow MUST NOT override or guess user_id.
     * The prompt MUST NOT invent a country; it uses the injected value.

   * `getUserProfile(user_id)`
     Purpose: Return basic profile context (country, currency_preference, preferred language hints, etc.) for localization and copy tone.
     Input:

     ```json
     { "user_id": "uuid" }
     ```

     Output (example):

     ```json
     {
       "country": "GT",
       "currency_preference": "GTQ",
       "locale": "es-GT"
     }
     ```

     Use cases:

     * Recommendations use this to know currency and language context.
     * Invoice OCR MAY use currency_preference fallback if receipt currency is missing.
       Security:
     * Same rule: backend injects `user_id`. The prompt never trusts arbitrary client user_id.

   * `getUserCategories(user_id)`
     Purpose: Return the list of categories the user can assign to expenses, including the default `"General"` category and any custom categories.
     Input:

     ```json
     { "user_id": "uuid" }
     ```

     Output (example):

     ```json
     [
       { "category_id": "uuid-1", "name": "Supermercado", "flow_type": "outcome" },
       { "category_id": "uuid-2", "name": "General", "flow_type": "outcome", "is_default": true }
     ]
     ```

     Use cases:

     * Invoice OCR uses this to build `category_suggestion`:

       * `match_type: "EXISTING"` → map to an existing `category_id`
       * `match_type: "NEW_PROPOSED"` → suggest a new name but DO NOT create it
         Security:
     * Read-only.
     * MUST NOT write or create categories.

5. Input / output typing (critical for backend integration)
   You MUST define a strongly typed Python interface for each workflow:

   ```python
   def run_workflow(...typed params...) -> ReturnType:
       ...
   ```

   Rules:

   * ALL params MUST have explicit type hints.
     No implicit `*args`, `**kwargs`, or `Any`.
   * `ReturnType` MUST be a TypedDict, `dataclasses.dataclass`, or Pydantic model.
   * You MUST ALSO define matching JSON `input_schema` and `output_schema`
     (plain dicts mirroring the TypedDicts, for documentation/validation).

     * Both MUST be strictly JSON-serializable.
     * Every field MUST include: name, type, description, allowed values or semantics.
     * The JSON schemas MUST match the Python signature exactly.
   * No silent defaults.

     * Required fields MUST be marked required.
     * Optional fields MUST be declared optional and documented when they're used.
   * The workflow MUST answer ONLY with valid JSON that conforms to its `output_schema`.

     * No prose, no markdown, no trailing comments in the runtime response.
     * If the request is out of scope, that still must be valid JSON (`status`: "out_of_scope" or `"NO_VALID_OPTION"` depending on the workflow).

6. Guardrails / refusal path
   Every workflow MUST detect out-of-scope or disallowed intent BEFORE the LLM call
   (domain filter in the endpoint) AND inside the prompt (model-level refusal).

   * If disallowed (sexual content, crime, self-harm, weapons, fraud, etc.):

     * DO NOT call Gemini at all from the endpoint; return a structured refusal
       that matches your `output_schema`.
       Example for recommendations:

       ```json
       {
         "status": "NO_VALID_OPTION",
         "reason": "Request is not allowed under policy."
       }
       ```
   * If the request is irrelevant to the workflow responsibility (e.g. “explícame álgebra” to invoice OCR):

     * Return JSON like:

       ```json
       {
         "status": "OUT_OF_SCOPE",
         "reason": "Invoice OCR only processes receipts."
       }
       ```
   * NEVER attempt to answer general questions outside finance/recommendations/receipt parsing.

7. Privacy and data boundaries

   * Workflows MUST NOT log:

     * raw invoice images,
     * full transaction histories,
     * account balances,
     * Supabase tokens,
     * personally identifying profile fields beyond what’s strictly needed for localization (country, currency_preference).
   * Logging is limited to high-level audit strings like:

     * `"Parsed draft invoice from store_name='Super Despensa Familiar Zona 11'."`
     * `"Generated 2 viable offers for budget Q7000."`
   * Workflows MUST NOT write directly to the database.
     They ONLY return structured data to the FastAPI layer.
     If something needs persistence, include a comment in code like:
     `# handled by API/db layer under RLS`
     or
     `# TODO(db-team): persist recommendation snapshot according to backend/db.instructions.md`
   * Workflows MUST assume backend already validated the Supabase token and resolved the real `user_id`.
     Workflows MUST ignore/override any `user_id` passed in by the client.

8. Country / currency / localization context

   * Recommendations MUST ALWAYS work with:

     * `country` (from profile)
     * `currency_preference` (from profile)
     * `budget_hint` (quetzales in GT use case, numeric)
     * `preferred_store` (string or null)
     * `user_note` (user preference like “no RGB gamer lights”)
     * `extra_details` (progressively built Q&A answers such as `use_case`, `screen_size`, etc.)
   * These context fields MUST be injected into the user prompt so the model can
     generate `copy_for_user` and `badges` that are already frontend-friendly,
     localized, and safe to render as-is.
   * The workflow MUST return one of:

     * `"OK"` + `products[]`
     * `"NO_VALID_OPTION"`

9. Return shape (final contract to the API layer / frontend)

* The final Python return type MUST be easily serializable to what the FastAPI layer returns to the Flutter app.
* Keep it minimal. Only include fields we actually expose or persist.
* For invoice OCR:

  * `status` MUST be `"DRAFT"`, `"INVALID_IMAGE"`, or `"OUT_OF_SCOPE"`.
  * If `"DRAFT"`, include all structured invoice fields + `category_suggestion`.
  * If `"INVALID_IMAGE"`, include a short factual `reason`.
* For recommendations:

  * `status` MUST be `"OK"` or `"NO_VALID_OPTION"` (`"NEEDS_CLARIFICATION"` is deprecated and MUST NOT be returned).
  * `"OK"` MUST include up to 3 `products[]`, each with:

    * `product_title`
    * `price_total` / localized currency string or numeric
    * `seller_name`
    * `url`
    * `pickup_available`
    * `warranty_info`
    * `copy_for_user` (short, factual, <=3 sentences, no emojis, no hype)
    * `badges` (array of up to 3 short tags)
  * `"NO_VALID_OPTION"` MUST still be valid JSON with that status plus `reason`.

10. Style / code quality requirements

* Every function you output MUST include explicit type hints for ALL parameters and return types.
* Document every pre-call context helper the prompt expects (see Rule 4).
* No implicit globals.
* No deployment logic (Cloud Run, etc.).
* No SQL creation / migration code here.

  * If persistence is relevant, leave a comment like:
    `# TODO(db-team): persist recommendation snapshot according to backend/db.instructions.md`
* No RLS policy logic here other than acknowledging that RLS exists and backend enforces `user_id = auth.uid()`.

11. Final output format for Copilot
    Return ONLY:

* Code and/or diffs to create or update the workflow module under these rules.
* That code MUST:

  * Define the workflow's runner function signature with full type hints.
  * Define (or update) the JSON `input_schema` and `output_schema` that match the signature.
  * Inline-document all pre-call context helpers and their shapes.
  * Explicitly state that the workflow is a SINGLE google-genai SDK call (no framework, no loop, no tools called by the model).
  * Explicitly state that the workflow MUST respond ONLY with valid JSON matching `output_schema` (no prose, no markdown).

If any of these are missing, the answer is considered invalid.
