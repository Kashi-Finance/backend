---
applyTo: '**'
---
# adk Agents Instructions

This document defines how adk agents are structured and how they interact with the API layer.

Always use the most recent version of the Google ADK documentation when creating or modifying adk agents or their schemas.


## 1. The Only Allowed adk Agents

There are exactly four (4) adk agents in this project:

1. InvoiceAgent
2. RecommendationCoordinatorAgent
3. SearchAgent
4. FormatterAgent

No other agents are allowed unless explicitly approved.
Do not rename them, do not create "v2" variants, and do not add subagents unless instructed.


## 2. Agent Responsibilities and Boundaries

### 2.1 InvoiceAgent
Purpose:
- Take an invoice input (typically an uploaded receipt image, OCR text, and contextual info).
- Extract structured financial data:
  - store_name
  - transaction_time
  - total_amount
  - currency (e.g. GTQ)
  - purchased_items list (item, qty, unit price, line total)
  - receipt_id (reference to stored image)
- Produce:
  - A structured JSON-like object with those fields, suitable for storage.
  - A text snapshot formatted EXACTLY as `EXTRACTED_INVOICE_TEXT_FORMAT`:

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
- The agent MUST output fields that allow the backend to build that exact template.
- The agent MUST refuse to answer anything that is not "extract data from an invoice / receipt". It must NOT become a general Q&A bot.
- The agent MUST NOT write to the database. It only returns structured data. The API layer (and DB layer) handle persistence later.
- The agent MUST NOT leak sensitive user information beyond what is strictly required for that invoice.

### 2.2 RecommendationCoordinatorAgent
Purpose:
- Orchestrate recommendation logic for purchases / wishlist / budgets / planning.
- Take the user's intent (goal, budget hint, time horizon, store preference, country/profile context).
- Use internal tools to:
  - check if the request is valid and in-scope,
  - search for candidate products / offers,
  - organize results,
  - produce a final recommendation response that the app can show.

This agent is the single entry point for recommendation-style features from the API layer.

Most importantly:
- `SearchAgent` and `FormatterAgent` are NOT called directly by the API layer.
- They are AgentTools exclusively used internally by `RecommendationCoordinatorAgent`.

The RecommendationCoordinatorAgent MUST:
- Reject requests that are out of domain (e.g. mental health advice, random personal questions).
- Enforce budget and profile constraints (country, currency_preference, etc.) provided by the API layer.
- Produce a typed structured output that the API can map into a Pydantic ResponseModel.

### 2.3 SearchAgent (AgentTool)
Purpose:
- Search, collect, or compare potential products/offers/prices given constraints like:
  - user goal ("laptop para diseño gráfico que no sea gamer"),
  - budget_hint,
  - preferred_store,
  - user country / availability.
- Return raw candidate options (product name, store, price, link/reference, etc.).

This agent is an AgentTool, not a top-level public agent. It is only called by RecommendationCoordinatorAgent.

Rules:
- It MUST refuse prompts that are not about product/offer discovery in the financial planning / wishlist context.
- It MUST NOT answer random unrelated questions.
- It MUST NOT persist anything to DB.
- It MUST return structured data, not free-form chatty prose.

### 2.4 FormatterAgent (AgentTool)
Purpose:
- Take raw results (e.g. list of candidate products from SearchAgent) and shape them into a clean, concise, user-facing structure:
  - normalized prices with currency,
  - short explanation of why each option fits the user's stated goal and budget,
  - any constraints or warnings (e.g. "over budget", "low stock").
- Produce a final structured summary that can be sent back through the API to the mobile client.

This agent is also an AgentTool, ONLY callable from RecommendationCoordinatorAgent.

Rules:
- It MUST NOT invent financial advice outside of the purchase/recommendation domain.
- It MUST produce deterministic, well-structured fields (no giant paragraphs unless explicitly required).
- It MUST use consistent field naming and currency formatting so the frontend can render easily.
- It MUST NOT directly persist anything.

Summary of orchestration:

    RecommendationCoordinatorAgent
      ├── uses SearchAgent (AgentTool)
      └── uses FormatterAgent (AgentTool)

The FastAPI endpoints should call RecommendationCoordinatorAgent for recommendation-related flows.
They should never call SearchAgent or FormatterAgent directly.


## 3. Input / Output Contracts

All adk agents MUST define:
- A strictly typed Python interface, including type hints for every parameter and the return type.
- An ADK `input_schema` and `output_schema` that:
  - mirror the function signature,
  - only use JSON-serializable field types,
  - describe each field's meaning, required/optional status, and any constraints.
- No silent defaults. If a field is required, mark it required. Missing required fields should cause the agent to return a structured error or ask for that field (depending on our ADK pattern).

The output MUST be structured data:
- For InvoiceAgent: structured invoice data (store_name, total_amount, etc.) and all fields required to render EXTRACTED_INVOICE_TEXT_FORMAT.
- For RecommendationCoordinatorAgent: structured recommendations, not plain text blobs.
- For SearchAgent: raw candidate offers, structured as machine-readable rows/items.
- For FormatterAgent: a cleaned, final response object ready for the frontend.

Never return unbounded free text unless the spec explicitly requires it.


## 4. Domain Guardrail / Out-of-Scope Rejection

Every adk agent MUST have a guardrail:
- If the incoming request is unrelated to its domain, it MUST NOT attempt to answer.
- Instead, it should return a controlled "out_of_scope" style response that indicates rejection.

The API layer will convert that into an HTTP 400 with `{"error":"out_of_scope", ...}`.

Reasons:
- Latency / cost: we do not call Gemini / ADK for nonsense.
- Safety: we avoid exposing user financial context to irrelevant prompts.
- UX consistency: the app sees a predictable error format instead of random LLM chatter.


## 5. Privacy and Persistence

- adk agents do NOT access the database directly.
- adk agents do NOT bypass Row Level Security.
- adk agents do NOT try to store or retrieve user financial history on their own.
- If persistence is needed, the agent returns a structured object and the API layer (or a service behind the API layer) will handle storage under RLS, following backend/db.instructions.md.

In other words:
- InvoiceAgent returns parsed invoice data.
- The API layer (or DB service) later persists that data, including `invoice.extracted_text` in the exact canonical format.
- RecommendationCoordinatorAgent returns structured recommendations.
- The API layer (or DB service) can save relevant parts (wishlist updates, etc.) according to backend/db.instructions.md.

The agent itself NEVER writes.


## 6. Logging and Sensitive Data

- adk agents must avoid logging:
  - full invoice images,
  - raw personal financial amounts,
  - personally identifying information.
- It's acceptable to log high-level events like:
  - "InvoiceAgent extracted store_name='Supertienda XYZ' total_amount='123.45 GTQ'"
    - If logged, redact or round as needed; do not dump the entire receipt.
- Never log private tokens, Supabase headers, or auth debug info.


## 7. Interaction Pattern With FastAPI

- The FastAPI endpoint is the gateway.
- The endpoint:
  - authenticates the caller via Supabase Auth,
  - validates and normalizes the request (country, currency_preference, etc.),
  - forces intent/domain filtering,
  - then calls the correct agent method with a well-typed payload.
- The agent returns structured output (or out_of_scope).
- The endpoint converts that output into a strict Pydantic ResponseModel and returns it.

Agents MUST assume:
- They are NOT talking directly to an end-user.
- They are being called programmatically with already validated, minimal, domain-specific inputs.

Always use the most recent version of the Google ADK documentation when creating or modifying adk agents, including their AgentTools and schemas.
