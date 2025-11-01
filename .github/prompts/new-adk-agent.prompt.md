---

description: "Create or update an adk agent module (Google ADK) for this backend"
mode: Beast Mode
----------------

You are defining or updating an adk agent for the Kashi Finances backend.

You MUST obey ALL rules below. Do not introduce new agents unless explicitly authorized.

1. Always load latest ADK documentation

   * Before you define or modify any agent, you MUST assume there is an internal tool called `fetch` that retrieves the latest Google ADK docs, tool invocation spec, and schema format.
   * You MUST include a call/step/comment like:
     `# First, use the fetch tool to read the latest ADK runtime, tool invocation format, and schema rules before calling Gemini.`
   * Never rely on stale assumptions. Always assume `fetch` is available to the agent so it can self-check the most recent ADK contract.

2. Allowed agents (names + roles)
   These are the ONLY adk agents and subagents. Do NOT create any other agent names, variants, or siblings unless explicitly instructed.

   * `InvoiceAgent`
   * `RecommendationCoordinatorAgent`
   * `SearchAgent` (AgentTool)
   * `FormatterAgent` (AgentTool)

   Rules:

   * `RecommendationCoordinatorAgent` can CALL `SearchAgent` and `FormatterAgent`.
   * `SearchAgent` and `FormatterAgent` are NOT public. They are AgentTools that ONLY the coordinator can use. They are NOT exposed directly to FastAPI routes.
   * Do NOT expose any subagent directly to the HTTP layer.

3. Business responsibility of each agent
   Each adk agent MUST have ONE clear, narrow responsibility and MUST refuse anything outside that scope.

   * `InvoiceAgent`
     Goal: given an invoice/receipt image, extract structured purchase data and return a validated draft of the expense.
     It must return:

     * store_name
     * purchase_datetime
     * total_amount
     * currency
     * items[] (description, quantity, unit_price / total_price)
     * category_suggestion (match_type + either category_id/category_name OR proposed_name)
     * status:

       * `"DRAFT"` if usable
       * `"INVALID_IMAGE"` if not usable
         It also must provide the canonical multi-line string that will later go into `invoice.extracted_text` in DB:

     ```
     Store Name: {store_name}
     Transaction Time: {transaction_time}
     Total Amount: {total_amount}
     Currency: {currency}
     Purchased Items:
     {purchased_items}
     Receipt Image ID: {receipt_id}
     ```

   * `RecommendationCoordinatorAgent`
     Goal: orchestrate recommendation logic for purchase goals / wishlist.
     Tasks:

     * Read the user's query (`query_raw`), budget, context (country, preferred_store, user_note, extra_details).
     * Validate intent (block sexual content, weapons/illicit goods, obvious scams or impossible requests).
     * Decide if we already have enough info:

       * If missing info → return `"NEEDS_CLARIFICATION"` with `missing_fields[]`.
       * If info is complete → call internal tools `SearchAgent` then `FormatterAgent`.
     * Produce final structured response for the mobile app:

       * `"OK"` with up to 3 ranked options (`results_for_user[]` with product_title, price_total, seller_name, url, pickup_available, warranty_info, copy_for_user, badges[])
       * `"NO_VALID_OPTION"` if nothing survived filtering.

   * `SearchAgent` (AgentTool)
     Goal: deterministic retrieval step.
     Input fields (example):

     ```json
     {
       "query_raw": "laptop para diseño gráfico",
       "budget_hint": 7000,
       "country": "GT",
       "preferred_store": "Intelaf",
       "user_note": "nada gamer con luces RGB"
     }
     ```

     It gathers at most ~3 real, verifiable offers that match those constraints.
     Output must include raw candidates with:

     * product_title
     * price_total (numeric)
     * seller_name
     * url (MUST be real / verifiable, never invented)
     * pickup_available (bool)
     * warranty_info
       SearchAgent does NOT generate marketing copy, does NOT rank with tone, does NOT hallucinate URLs. If unsure, omit the candidate.

   * `FormatterAgent` (AgentTool)
     Goal: post-process the raw candidates from `SearchAgent`.
     Responsibilities:

     * Remove obvious scams / incoherences / fake prices.
     * Respect budget_hint and user_note (e.g. drop “RGB gamer” laptops if user_note says “no gamer RGB”).
     * Normalize currency/price using the user’s profile country/currency.
     * Generate:

       * `copy_for_user`: short explanation (≤3 sentences, factual, clean tone, no emojis, no hype, no promises like “perfect for you”)
       * `badges`: up to 3 short UI chips such as “Más barata”, “Garantía 12m”, “Recoge hoy”.
     * Return `error: true` if nothing is trustworthy.
       The output from FormatterAgent is what becomes `results_for_user[]` inside `"status": "OK"`.

   Guardrail for ALL agents:

   * MUST refuse (“out_of_scope” / "NO_VALID_OPTION") if the request:

     * is sexual/erótico explícito,
     * is criminal/armas ilegales/conducta peligrosa,
     * is incoherent with personal finance / recommendations / expense logging.
   * MUST NOT answer general chit-chat.
   * MUST NOT provide advice outside its vertical.

4. Tool philosophy (critical)
   In ADK, “tools” are deterministic functions the model can call instead of hallucinating code or data.
   We rely heavily on tools. Copilot must prefer adding / wiring tools over baking logic into the model prompt.

   Rules:

   * Before you let the agent “think”, you MUST explicitly document for the agent which tools exist, what they do, what input they take, and what output they return.
     The agent must be able to infer on its own which tool to call based on that description.
   * Every tool MUST be described with:

     * name
     * purpose / when to use it
     * input parameters and types
     * output shape and types
     * security constraints (ex: “requires user_id, which backend already resolved from Supabase Auth; never accept arbitrary user_id from client”)
   * For deterministic substeps, DO NOT let the LLM freestyle. Instead:

     * Create or reuse a tool like `getUserCountry`, `getUserProfile`, `getUserCategories`, `SearchAgent`, `FormatterAgent`.
     * Clearly tell the agent “call this tool when you need X”.
   * You MAY propose new tools in the diff ONLY if they are deterministic, backend-implementable, and obviously needed (e.g. `getUserProfile`, `getUserCountry`, `getUserCategories`, `getCurrencyPreferenceForUser`).
     But DO NOT create a new AGENT unless explicitly authorized.

5. Core tools that MUST be documented in the agent prompt
   The agent prompt you generate MUST include (at minimum) docs for these tools so the agent can choose them:

   * `fetch`
     Purpose: Retrieve the most recent ADK runtime / tool invocation spec / policy docs.
     Use when: starting execution, before using any other tool, to ensure updated contract.
     Input: none or simple `{}`.
     Output: opaque doc string / JSON with current ADK rules.
     Security: read-only.
     Notes: The agent MUST conceptually call `fetch` first to self-sync with current ADK guidelines.

   * `getUserCountry(user_id)`
     Purpose: Return the user’s ISO-2 country code. Used to localize seller availability and currency context.
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
     * Agent MUST NOT override or guess user_id.
     * Agent cannot invent a country; must use this tool.

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

     * RecommendationCoordinatorAgent uses this to know currency and language context.
     * InvoiceAgent MAY use currency_preference fallback if receipt currency is missing.
       Security:
     * Same rule: backend injects `user_id`. Agent never trusts arbitrary client user_id.

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

     * InvoiceAgent uses this to build `category_suggestion`:

       * `match_type: "EXISTING"` → map to an existing `category_id`
       * `match_type: "NEW_PROPOSED"` → suggest a new name but DO NOT create it
         Security:
     * Read-only.
     * MUST NOT write or create categories.

   * `SearchAgent` (AgentTool callable by RecommendationCoordinatorAgent only)
     Purpose: Fetch raw product candidates that match the user’s request.
     Input fields:

     ```json
     {
       "query_raw": "string",
       "budget_hint": number,
       "country": "GT",
       "preferred_store": "string | null",
       "user_note": "string | null",
       "extra_details": { "...": "..." }
     }
     ```

     Output fields:

     ```json
     {
       "results": [
         {
           "product_title": "string",
           "price_total": number,
           "seller_name": "string",
           "url": "https://valid.example",
           "pickup_available": true,
           "warranty_info": "string"
         }
       ]
     }
     ```

     Notes:

     * No tone. No marketing. No hallucinated URLs.
     * Max ~3 results.
     * If it can’t find anything, return an empty array.

   * `FormatterAgent` (AgentTool callable by RecommendationCoordinatorAgent only)
     Purpose: Clean/validate/rank the raw candidates and produce UI-ready output.
     Input fields:

     ```json
     {
       "candidates": [...from SearchAgent.results...],
       "budget_hint": number,
       "country": "GT",
       "currency_preference": "GTQ",
       "user_note": "string | null",
       "preferred_store": "string | null"
     }
     ```

     Output fields:

     ```json
     {
       "status": "OK" | "NO_VALID_OPTION",
       "results_for_user": [
         {
           "product_title": "string",
           "price_total": number,
           "seller_name": "string",
           "url": "https://valid.example",
           "pickup_available": boolean,
           "warranty_info": "string",
           "copy_for_user": "short factual explanation, <=3 sentences, no emojis",
           "badges": ["short chip", "short chip"]
         }
       ]
     }
     ```

     Notes:

     * If all candidates look like scams / nonsense / violate constraints → return `"NO_VALID_OPTION"`.

6. Input / output typing (critical for backend integration)
   You MUST define a strongly typed Python interface for each agent:

   ```python
   def run_agent(...typed params...) -> ReturnType:
       ...
   ```

   Rules:

   * ALL params MUST have explicit type hints.
     No implicit `*args`, `**kwargs`, or `Any`.
   * `ReturnType` MUST be a TypedDict, `dataclasses.dataclass`, or Pydantic model.
   * You MUST ALSO define matching ADK `input_schema` and `output_schema`.

     * Both MUST be strictly JSON-serializable.
     * Every field MUST include: name, type, description, allowed values or semantics.
     * The JSON schemas MUST match the Python signature exactly.
   * No silent defaults.

     * Required fields MUST be marked required.
     * Optional fields MUST be declared optional and documented when they're used.
   * The agent MUST answer ONLY with valid JSON that conforms to its `output_schema`.

     * No prose, no markdown, no trailing comments in the runtime response.
     * If the request is out of scope, that still must be valid JSON (`status`: "out_of_scope" or `"NO_VALID_OPTION"` depending on the agent).

7. Guardrails / refusal path
   Every agent MUST detect out-of-scope or disallowed intent BEFORE doing heavy reasoning or calling other tools.

   * If disallowed (sexual content, crime, self-harm, weapons, fraud, etc.):

     * DO NOT call `SearchAgent`, `FormatterAgent`, OCR, scraping, etc.
     * Return a structured refusal that matches your `output_schema`.
       Example for RecommendationCoordinatorAgent:

       ```json
       {
         "status": "NO_VALID_OPTION",
         "reason": "Request is not allowed under policy."
       }
       ```
   * If the request is irrelevant to the agent responsibility (e.g. “explícame álgebra” to InvoiceAgent):

     * Return JSON like:

       ```json
       {
         "status": "out_of_scope",
         "reason": "InvoiceAgent only processes receipts."
       }
       ```
   * NEVER attempt to answer general questions outside finance/recommendations/receipt parsing.

8. Privacy and data boundaries

   * Agents MUST NOT log:

     * raw invoice images,
     * full transaction histories,
     * account balances,
     * Supabase tokens,
     * personally identifying profile fields beyond what’s strictly needed for localization (country, currency_preference).
   * Logging is limited to high-level audit strings like:

     * `"Parsed draft invoice from store_name='Super Despensa Familiar Zona 11'."`
     * `"Generated 2 viable offers for budget Q7000."`
   * Agents MUST NOT write directly to the database.
     They ONLY return structured data to the FastAPI layer.
     If something needs persistence, include a comment in code like:
     `# handled by API/db layer under RLS`
     or
     `# TODO(db-team): persist recommendation snapshot according to backend/db.instructions.md`
   * Agents MUST assume backend already validated the Supabase token and resolved the real `user_id`.
     Agents MUST ignore/override any `user_id` passed in by the client.

9. Country / currency / localization context

   * `RecommendationCoordinatorAgent` MUST ALWAYS work with:

     * `country` (from `getUserCountry(user_id)` or `getUserProfile`)
     * `currency_preference` (from `getUserProfile`)
     * `budget_hint` (quetzales in GT use case, numeric)
     * `preferred_store` (string or null)
     * `user_note` (user preference like “no RGB gamer lights”)
     * `extra_details` (progressively built Q&A answers such as `use_case`, `screen_size`, etc.)
   * These context fields MUST be passed down into `SearchAgent` and `FormatterAgent`.
     That allows FormatterAgent to generate `copy_for_user` and `badges` that are already frontend-friendly, localized, and safe to render as-is.
   * The coordinator MUST return one of:

     * `"NEEDS_CLARIFICATION"` + `missing_fields[]`
     * `"OK"` + `results_for_user[]`
     * `"NO_VALID_OPTION"`

10. Return shape (final contract to the API layer / frontend)

* The final Python return type and the ADK `output_schema` MUST be easily serializable to what the FastAPI layer returns to the Flutter app.
* Keep it minimal. Only include fields we actually expose or persist.
* For `InvoiceAgent`:

  * `status` MUST be `"DRAFT"` or `"INVALID_IMAGE"`.
  * If `"DRAFT"`, include all structured invoice fields + `category_suggestion`.
  * If `"INVALID_IMAGE"`, include a short factual `reason`.
* For `RecommendationCoordinatorAgent`:

  * `status` MUST be `"NEEDS_CLARIFICATION"`, `"OK"`, or `"NO_VALID_OPTION"`.
  * `"NEEDS_CLARIFICATION"` MUST include `missing_fields[]` where each entry has:

    * `field`: machine-readable key like `"use_case"`
    * `question`: short Spanish prompt to show directly in UI
  * `"OK"` MUST include up to 3 `results_for_user[]`, each with:

    * `product_title`
    * `price_total` / localized currency string or numeric
    * `seller_name`
    * `url`
    * `pickup_available`
    * `warranty_info`
    * `copy_for_user` (short, factual, <=3 sentences, no emojis, no hype)
    * `badges` (array of up to 3 short tags)
  * `"NO_VALID_OPTION"` MUST still be valid JSON with that status.

11. Style / code quality requirements

* Every function you output MUST include explicit type hints for ALL parameters and return types.
* Document every tool you expect the agent to be able to call (see Rule 5).

  * This documentation MUST be present in the module prompt/config so that the ADK runtime can automatically route tool calls.
  * The agent must be able to infer “oh, I should call `getUserCountry` now” WITHOUT human intervention.
* No implicit globals.
* No deployment logic (Cloud Run, etc.).
* No SQL creation / migration code here.

  * If persistence is relevant, leave a comment like:
    `# TODO(db-team): persist recommendation snapshot according to backend/db.instructions.md`
* No RLS policy logic here other than acknowledging that RLS exists and backend enforces `user_id = auth.uid()`.

12. Final output format for Copilot
    Return ONLY:

* Code and/or diffs to create or update the agent module under these rules.
* That code MUST:

  * Define the agent’s `run_agent(...)` function signature with full type hints.
  * Define (or update) the `input_schema` and `output_schema` that match the signature.
  * Inline-document all tools available to the agent, including `fetch`, `getUserCountry`, `getUserProfile`, `getUserCategories`, `SearchAgent`, `FormatterAgent`, etc., with purpose, inputs, outputs, and when to call them.
  * Explicitly state that the agent MUST call `fetch` first to pull the latest ADK spec before reasoning.
  * Explicitly state that the agent MUST respond ONLY with valid JSON matching `output_schema` (no prose, no markdown).

If any of these are missing, the answer is considered invalid.