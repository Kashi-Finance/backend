# 🧠 Kashi Finances — General Agent Architecture Documentation

## Overview
Kashi Finances is built around a **multi-agent architecture** that combines automation, modularity, and scalability.  
Each agent fulfills a specialized task within the ecosystem — from invoice processing to personalized recommendations — all coordinated through standardized communication channels and cloud infrastructure.

The system is designed to maintain **clarity of responsibility**:
- Agents handle intelligence and automation.
- The backend orchestrates workflows and ensures data integrity.
- The frontend provides a guided, human-confirmed interface.

---

## 🏷️ High-Level Architecture

### Core Components
| Layer | Description | Key Technologies |
|-------|--------------|------------------|
| **Frontend (Flutter + Riverpod)** | Mobile application providing user interface, state management, and connection to backend endpoints. | Flutter, Dart |
| **Backend API (FastAPI)** | RESTful API deployed on Cloud Run. Orchestrates agent calls, handles authentication, and manages persistence. | FastAPI, Python |
| **Database & Storage** | Central data layer with relational structure and vector search for semantic AI operations. | Supabase (PostgreSQL + pgvector, Storage, Auth) |
| **AI Components** | LLM-powered workflows for OCR and recommendations using optimized architectures. | Gemini API, DeepSeek V3.2 |

---

## ⚙️ Agent Ecosystem

### 1. **InvoiceAgent** (Single-Shot Multimodal Workflow)

Automates OCR and structured extraction from receipt/invoice images using a single-shot multimodal workflow.

- **Purpose:** Convert an image into a strict, validated JSON extraction that the frontend shows to the user for confirmation. The agent is responsible only for extraction and structured suggestions — it never persists data.

- **Implementation:**
  - Single-shot LLM workflow (one prompt → one Gemini call)
  - This is a deterministic multimodal extraction step
  - Uses Gemini's native vision capabilities to read images (base64 input required)
  - Deterministic extraction: `temperature = 0.0` and `response_mime_type="application/json"`
  - The backend fetches user context (profile + categories) before calling the agent

- **Expected Statuses:**
  - `DRAFT`: Successful extraction with `store_name`, `transaction_time`, `total_amount`, `currency`, `items[]` and `category_suggestion`
  - `INVALID_IMAGE`: Cannot extract reliable data (too blurry, not a receipt, etc.)
  - `OUT_OF_SCOPE`: Request outside the invoice/extraction domain

- **Category Suggestion Shape** (always present in DRAFT):
  - `match_type`: `EXISTING` | `NEW_PROPOSED`
  - `category_id`: UUID | null
  - `category_name`: string | null
  - `proposed_name`: string | null

- **Behavioral Rules:**
  - The agent must NOT write to the database or call external tools
  - The agent must NOT invent category IDs or persist images
  - All persistence is done by the backend after user confirmation
  - Committed invoices are immutable after `/invoices/commit`

---

### 2. **Recommendation System** (Prompt Chaining Architecture)

> **Architecture Note (November 2025):** The recommendation system was refactored from a multi-agent ADK architecture (RecommendationCoordinatorAgent → SearchAgent → FormatterAgent) to a simplified **Prompt Chaining** approach using DeepSeek V3.2.

- **Purpose:** Provide personalized product recommendations based on user's purchase goals, budget constraints, and preferences.

- **Implementation:**
  - **Pattern:** Prompt Chaining (single LLM call)
  - **Model:** DeepSeek V3.2 (`deepseek-chat`)
  - **API:** OpenAI-compatible
  - **Temperature:** 0.0 (deterministic)
  - **Output:** Structured JSON (forced via `response_format`)

- **Architecture Flow:**
  ```
  User Query → FastAPI Endpoint → recommendation_service.py → DeepSeek API → JSON Response → Pydantic Model
  ```

- **Cost Comparison:**
  | Metric | Previous (ADK) | Current (Prompt Chaining) |
  |--------|----------------|---------------------------|
  | LLM Calls per Request | 3 (Coordinator + Search + Formatter) | 1 |
  | Monthly Cost (1M requests) | ~$1,500 | ~$300 |
  | Response Time | 15-25 seconds | 5-10 seconds |
  | Failure Points | 3 (cascading) | 1 |

- **System Prompt Responsibilities:**
  1. Intent validation (guardrails for prohibited content)
  2. Query intent extraction
  3. Product search logic (using model's knowledge)
  4. Result validation & filtering
  5. Output formatting rules
  6. Graceful degradation

- **Possible Statuses:**
  - `OK`: Returns 1-3 structured product recommendations
  - `NO_VALID_OPTION`: No suitable products found or out-of-scope request
  - `NEEDS_CLARIFICATION`: *Deprecated in Prompt Chaining* (single-shot can't ask follow-up)

- **API Endpoints:**
  - `POST /recommendations/query`: Initial recommendation query
  - `POST /recommendations/retry`: Retry with updated criteria

- **Response Schema (OK status):**
  ```json
  {
    "status": "OK",
    "products": [
      {
        "product_title": "ASUS Vivobook 15 Ryzen 7 16GB 512GB SSD",
        "price_total": 6750.00,
        "seller_name": "TecnoMundo Guatemala",
        "url": "https://tecnomundo.com.gt/asus-vivobook15-ryzen7",
        "pickup_available": true,
        "warranty_info": "Garantía 12 meses tienda",
        "copy_for_user": "Ideal para Photoshop y diseño gráfico. Cumple con GPU dedicada y diseño sobrio sin luces gamer.",
        "badges": ["Buen rendimiento", "Diseño sobrio", "GPU dedicada"]
      }
    ],
    "metadata": {
      "total_results": 1,
      "query_understood": true,
      "search_successful": true
    }
  }
  ```

- **Integration with Wishlists:**
  - Recommendation response → Frontend display → User selection → `POST /wishlists` with `selected_items`
  - Field mapping: `ProductRecommendation` schema matches `WishlistItemFromRecommendation`

---

### 3. **Future Agents** (Planned)

| Agent | Description | Status |
|-------|-------------|--------|
| **InsightAgent** | Analyzes user habits for spending trends | Planned |
| **PriceTrackerAgent** | Monitors price fluctuations for saved items | Planned |
| **BudgetAdvisor** | Suggests budget adjustments aligned with user goals | Planned |

---

## 🗄️ Data Persistence & Context

### Database Overview
- **auth.users / user_profile:** Authentication and user preferences (country, currency)
- **invoice / transaction:** Financial records from confirmed OCR data
- **budget / recurring_transaction / wishlist_item:** Dynamic goals, recurring events, and saved recommendations
- **category:** Predefined + user-created categories (system keys protected)
- **pgvector:** Enables semantic similarity for future search features

### Context Fetching Pattern
Both the InvoiceAgent and Recommendation System follow the same context pattern:
1. FastAPI endpoint authenticates user via Supabase Auth
2. Endpoint fetches user profile (country, currency_preference)
3. Context is passed to the LLM workflow in the prompt
4. Agent/workflow returns structured output (never writes to DB)
5. Endpoint maps output to Pydantic models and returns response

---

## 🔒 Security & Integrity

- **Authentication:** Supabase Auth; every API call requires a valid JWT token
- **RLS Policies:** Row-level security enforced in Supabase (`user_id = auth.uid()`)
- **Data Confirmation:** No record is stored without explicit user approval
- **Context Isolation:** LLM workflows receive only the minimum context needed

---

## 🌐 Deployment

| Component | Platform | Deployment Method |
|-----------|----------|-------------------|
| Backend API | Google Cloud Run | Containerized (Docker) |
| Database | Supabase Cloud | Managed PostgreSQL + pgvector |
| Invoice OCR | Google Gemini API | Direct API calls |
| Recommendations | DeepSeek API | OpenAI-compatible client |

---

## 🧹 Design Principles

- **Single LLM call per workflow:** Minimize latency and failure points
- **Human-in-the-loop confirmation:** For all financial data
- **Strict contracts:** Pydantic models for all request/response types
- **Graceful degradation:** All errors return structured responses, never 500 errors
- **Localization:** System adapts to user's language, country, and currency preferences
- **Cost optimization:** Prefer efficient architectures (Prompt Chaining over multi-agent)

---

## 🚀 Summary

The Kashi Finances agent ecosystem forms an intelligent platform capable of:
- Automating expense recording via OCR (InvoiceAgent)
- Offering verified, contextual product recommendations (Prompt Chaining)
- Managing budgets, goals, and insights with scalable cloud components

This architecture ensures **accuracy, transparency, and user control**, aligning advanced AI workflows with real-world financial management.

---

*Last Updated: November 2025*
