---
applyTo: '**'
---
# AI Agents & LLM Workflows Instructions

This document defines how AI-powered components (agents and LLM workflows) are structured and how they interact with the API layer.

> **Architecture Note (December 2025):** The project uses simplified LLM workflows instead of complex multi-agent architectures. The recommendation system uses Gemini with Google Search grounding - all product recommendations come from real, current web data.


## 1. Active AI Components

There are exactly **two (2)** AI-powered components in this project:

### 1.1 InvoiceAgent (Single-Shot Multimodal Workflow)
- **Implementation:** Single-shot Gemini vision call
- **Model:** Gemini (with vision capabilities)
- **Purpose:** OCR and structured extraction from receipt images
- **NOT an ADK agent:** Uses direct Gemini API, not Google ADK

### 1.2 Recommendation System (Web-Grounded LLM)
- **Implementation:** Single-shot Gemini call with Google Search grounding
- **Model:** Gemini 2.5 Flash (`gemini-2.5-flash`)
- **Purpose:** Product recommendations based on user goals with REAL web data
- **NOT an ADK agent:** Uses Google Gen AI SDK with Google Search tool

No other agents are allowed unless explicitly approved.


## 2. Component Details

### 2.1 InvoiceAgent ⚠️ **Single-Shot Multimodal Workflow**

**Current Implementation:**
InvoiceAgent is implemented as a **single-shot multimodal vision extraction workflow** using Gemini directly, **NOT using ADK**. This is because invoice extraction is a deterministic task that doesn't require agentic reasoning or tool orchestration.

**Purpose:**
- Accept an invoice image (base64-encoded) and user context
- Make ONE multimodal call to Gemini's vision model
- Extract structured financial data directly from the image
- Return validated JSON following `InvoiceAgentOutput` schema

**What it extracts:**
- store_name
- transaction_time
- total_amount
- currency (e.g. GTQ)
- purchased_items list (description, qty, unit_price, line_total)
- category_suggestion (match to existing or propose new)
- extracted_text (canonical formatted summary)

**Architecture:**
```python
def run_invoice_agent(
    user_id: str,
    receipt_image_id: str,
    user_categories: List[Dict],  # Provided by endpoint
    receipt_image_base64: str,    # REQUIRED
    country: str = "GT",
    currency_preference: str = "GTQ"
) -> InvoiceAgentOutput
```

**Key Characteristics:**
- ✅ Single-shot: One prompt → One Gemini call → One response
- ✅ Multimodal: Uses Gemini's native vision capabilities to read receipt images
- ✅ No OCR text fallback: Image is REQUIRED
- ✅ No tools: All context (categories, profile) passed as parameters
- ✅ No iteration: No function-calling loop
- ✅ Deterministic: Temperature=0.0 for structured extraction
- ✅ Response format: JSON with `response_mime_type="application/json"`

**Rules:**
- The agent MUST output fields that allow the backend to build the canonical `EXTRACTED_INVOICE_TEXT_FORMAT`
- The agent MUST refuse to answer anything not related to invoice/receipt extraction
- The agent MUST NOT write to the database (persistence handled by API layer)
- User categories are fetched by the endpoint BEFORE calling the agent (not by the agent itself)

**Canonical Format:**
The API layer formats extracted data into this exact template before persisting:

```
EXTRACTED_INVOICE_TEXT_FORMAT = """
Store Name: {store_name}
Transaction Time: {transaction_time}
Total Amount: {total_amount}
Currency: {currency}
Purchased Items:
{purchased_items}
"""
```

---

### 2.2 Recommendation System ⚠️ **Web-Grounded LLM Architecture**

> **Upgraded January 2025:** The previous Perplexity Sonar architecture was replaced with Gemini + Google Search grounding. All product recommendations now come from real, current web data via Google Search.

**Current Implementation:**
The recommendation system uses **Gemini 2.5 Flash** with the **Google Search grounding tool**. This approach:
- Returns REAL product data from live Google Search results
- Provides verified URLs, current prices, and actual seller information
- Single API call (web search is automatic via grounding tool)
- JSON output parsed from text response (see limitation below)

**Important Limitation:**
Google Search grounding tool **does not support** `response_mime_type='application/json'` or `response_schema`. When used together, Gemini returns a 400 error. We work around this by:
1. Asking for JSON in the prompt
2. Parsing JSON from the response text
3. Stripping markdown code blocks if present

**Architecture:**
```
User Query → FastAPI Endpoint → recommendation_service.py → Gemini API → JSON Response → Pydantic Model
                                                              ↓
                                                    (Google Search grounding)
                                                              ↓
                                                    Real product data returned
```

**Service Location:**
- `backend/services/recommendation_service.py` - Main service file
- `backend/agents/recommendation/prompts.py` - System and user prompt templates (XML-structured)

**Key Functions:**
```python
async def query_recommendations(
    supabase_client: Client,
    user_id: str,
    query_raw: str,
    budget_hint: Optional[Decimal] = None,
    preferred_store: Optional[str] = None,
    user_note: Optional[str] = None,
    extra_details: Optional[Dict[str, Any]] = None,
) -> RecommendationQueryResponseOK | RecommendationQueryResponseNoValidOption

async def retry_recommendations(...) -> ...  # Same interface, for retries
```


**Possible Statuses:**
- `OK`: Returns 1-3 structured product recommendations with real web data
- `NO_VALID_OPTION`: No suitable products found or out-of-scope request
- `NEEDS_CLARIFICATION`: *Deprecated* (single-shot can't ask follow-up questions)

**Configuration:**
- `GOOGLE_API_KEY`: Required environment variable
- Model: `gemini-2.5-flash`
- Temperature: `0.2` (near-deterministic for factual queries)
- Response format: JSON parsed from text (Google Search tool doesn't support response_schema)
- Web grounding: Google Search tool enabled

**Grounding Metadata:**
The response includes grounding metadata with:
- `web_search_queries`: List of search queries used by Gemini
- `grounding_chunks`: List of web sources with URIs and titles


## 3. Deprecated Components

The following components are **deprecated** and should NOT be referenced or used:

| Component | Status | Replaced By |
|-----------|--------|-------------|
| RecommendationCoordinatorAgent | ❌ Deprecated | Prompt Chaining in `recommendation_service.py` |
| SearchAgent (AgentTool) | ❌ Deprecated | Built into system prompt logic |
| FormatterAgent (AgentTool) | ❌ Deprecated | Built into system prompt logic |
| `coordinator.py` | ❌ Deleted | N/A |
| `tools.py` | ❌ Deleted | N/A |
| `schemas.py` (ADK) | ❌ Deleted | Pydantic schemas in `backend/schemas/` |

**Do NOT:**
- Create new ADK agents
- Reference the old multi-agent architecture
- Import from `backend.agents.recommendation.coordinator`
- Import from `backend.agents.recommendation.tools`


## 4. Input/Output Contracts

All AI components MUST define:
- Strictly typed Python interfaces with type hints
- Pydantic models for request/response validation
- JSON-serializable output only

**InvoiceAgent Output:**
- Structured invoice data (store_name, total_amount, items, etc.)
- Fields required to render `EXTRACTED_INVOICE_TEXT_FORMAT`
- Status: `DRAFT`, `INVALID_IMAGE`, or `OUT_OF_SCOPE`

**Recommendation System Output:**
- Status: `OK` or `NO_VALID_OPTION`
- For `OK`: `results_for_user` list (max 3 products) with: product_title, price_total, seller_name, url, pickup_available, warranty_info, copy_for_user, badges
- For `NO_VALID_OPTION`: optional `reason` field explaining why

Never return unbounded free text. Always use structured JSON.


## 5. Domain Guardrails

Every AI component MUST have guardrails:

**InvoiceAgent:**
- Rejects non-receipt images
- Rejects non-image inputs
- Returns `INVALID_IMAGE` or `OUT_OF_SCOPE` for invalid requests

**Recommendation System:**
- Rejects prohibited content (sexual, weapons, illegal)
- Rejects non-product queries (mental health, relationship advice)
- Returns `NO_VALID_OPTION` with reason for out-of-scope

The API layer converts rejections into HTTP 400 with `{"error": "out_of_scope", ...}`.


## 6. Privacy and Persistence

- AI components do NOT access the database directly
- AI components do NOT bypass Row Level Security
- AI components do NOT store or retrieve user data on their own
- The API layer handles all persistence under RLS

**Pattern:**
1. Endpoint fetches user context (profile, categories) via Supabase
2. Context is passed to AI component in the prompt
3. AI component returns structured output
4. Endpoint persists data according to `db.instructions.md`


## 7. Logging Guidelines

**DO log:**
- High-level events: "InvoiceAgent called", "Recommendations returned OK"
- Performance metrics: response time, token usage
- Error conditions: validation failures, API errors

**DO NOT log:**
- Full invoice images or receipt text
- Personal financial amounts
- User PII (names, addresses, account numbers)
- API keys or tokens


## 8. Adding New AI Components

If a new AI component is needed:

1. **Evaluate if ADK is truly needed:**
   - Does the task require multi-step reasoning?
   - Does it need dynamic tool selection?
   - Can it be solved with a single prompt?

2. **Prefer simple architectures:**
   - Single-shot prompts for deterministic tasks
   - Prompt Chaining for complex but predictable flows
   - ADK only when agentic reasoning is unavoidable

3. **Follow the established patterns:**
   - Fetch context before calling the AI component
   - Use structured JSON output
   - Handle errors gracefully (return structured error, never 500)
   - Document the component in this file

---

*Last Updated: December 2025*
