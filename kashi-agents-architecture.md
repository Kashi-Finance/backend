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
| **Backend API (FastAPI + ADK)** | RESTful API deployed on Cloud Run. Orchestrates agent calls, handles authentication, and manages persistence. | FastAPI, Python, Google ADK |
| **Database & Storage** | Central data layer with relational structure and vector search for semantic AI operations. | Supabase (PostgreSQL + pgvector, Storage, Auth) |
| **Agents** | Modular AI components that execute specialized tasks such as OCR, product recommendation, and insight generation. | Google ADK, Gemini API |

---

## ⚙️ Agent Ecosystem

### 1. **InvoiceAgent**

Automates OCR and structured extraction from receipt/invoice images using a single-shot multimodal workflow.

- Purpose: Convert an image into a strict, validated JSON extraction that the frontend shows to the user for confirmation. The agent is responsible only for extraction and structured suggestions — it never persists data.
- Implementation specifics:
  - Single-shot LLM workflow (one prompt → one Gemini call). This is a deterministic multimodal extraction step and is intentionally **NOT** implemented as an ADK agent or with tool orchestration.
  - Uses Gemini's native vision capabilities to read images. The agent requires an image (base64) as input.
  - Deterministic extraction: temperature = 0.0 and `response_mime_type="application/json"` so the output is always a JSON object following the agreed schema.
  - The backend must fetch user context before calling the agent (authenticated `user_profile` for `country`/`currency_preference`, and `user_categories`) and pass that context to the agent in the prompt.

- Expected statuses and surface contract:
  - `INVALID_IMAGE`: Agent cannot extract reliable data (too blurry, not a receipt, etc.). Returns a short factual `reason`. No fields like `store_name`/`items` are returned in this case.
  - `DRAFT`: Agent produced a structured extraction: `store_name`, `transaction_time`, `total_amount`, `currency`, `items[]` and a `category_suggestion` object.
  - `OUT_OF_SCOPE`: If the prompt is outside the invoice/extraction domain (the agent should refuse).

- `category_suggestion` shape (always present in the DRAFT case with all fields set to either value or null):
  - `match_type`: `EXISTING` | `NEW_PROPOSED`
  - `category_id`: UUID | null
  - `category_name`: string | null
  - `proposed_name`: string | null

- Important behavioral rules and invariants:
  - The agent must NOT write to the database or call external tools. All persistence is done by the backend after user confirmation.
  - The agent must NOT invent category IDs, create categories automatically, or persist images.
  - The image is processed in memory during the `/invoices/ocr` preview flow. The image is uploaded to storage only when the frontend calls `/invoices/commit` (commit phase).
  - The backend maps agent output into strict Pydantic response models (`InvoiceOCRResponseDraft` / `InvoiceOCRResponseInvalid`) and enforces validation.
  - On commit, the backend uploads the image to Supabase Storage, formats the canonical `extracted_text` template, inserts an `invoice` row, and atomically creates a linked `transaction` (the category chosen by the user is stored on the `transaction`, not the `invoice`).
  - Committed invoices are immutable: after `/invoices/commit` the invoice row cannot be updated (only viewed or deleted according to the endpoint rules).

This design keeps the agent focused on deterministic extraction while the backend enforces persistence, RLS, and audit rules.

---

### 2. **RecommendationCoordinatorAgent**
Central orchestrator for all recommendation tasks.

- **Purpose:** Interpret user intent and route to appropriate subagents.
- **Implementation:** Full ADK agent with AgentTool orchestration
  - Uses `LlmAgent` from Google ADK
  - Temperature 0.2 for consistent orchestration with slight flexibility
  - Enforces strict guardrails (rejects prohibited content)
  - Has access to helper tools (`get_user_profile`, `get_user_country`, `get_user_categories`)
- **Flow control:**  
  1. Validates and sanitizes query (`query_raw`, `budget_hint`).  
  2. Rejects illegal or irrelevant intents (sexual content, weapons, illegal items).  
  3. Checks for missing required fields (e.g., `budget_hint`).
  4. Calls `get_user_profile(user_id)` for country/currency context.
  5. Routes valid requests to `SearchAgent` AgentTool → `FormatterAgent` AgentTool.  
- **Possible statuses:**  
  - `NEEDS_CLARIFICATION` – asks user for missing details.  
  - `OK` – returns structured product options (1-3 recommendations).  
  - `NO_VALID_OPTION` – no reliable result found or out-of-scope.  
- **API Endpoints:**
  - **POST `/recommendations/query`**: Initial recommendation query
    - Accepts: `query_raw`, `budget_hint`, `preferred_store`, `user_note`, `extra_details`
    - Returns: one of three response types based on agent status
  - **POST `/recommendations/retry`**: Retry with updated criteria
    - Same request/response format as `/query`
    - Semantically represents retry action (adjusted budget, refined query, etc.)
- **Integration with Wishlists:**
  - Agent output → Frontend display → User selection → POST `/wishlists` with `selected_items`
  - Field mapping: `ProductRecommendation` schema matches `WishlistItemFromRecommendation` exactly

---

### 3. **SearchAgent (AgentTool)**
Executes product searches according to user context.

- **Implementation:** AgentTool (NOT a standalone agent)
  - Called exclusively by RecommendationCoordinatorAgent
  - Uses `LlmAgent` from Google ADK
  - Temperature 0.0 for deterministic, factual results
  - No tools (performs search internally via Gemini knowledge)
- **Input:** validated query from coordinator plus user metadata
  - `query_raw`: User's product description
  - `budget_hint`: Maximum price
  - `country`: ISO-2 country code (from `get_user_profile`)
  - `preferred_store`: Store name or None
  - `user_note`: User preferences/constraints
- **Tasks:**  
  - Find real, verifiable products matching criteria
  - Return up to 3 product candidates with factual data only
  - NO marketing copy, NO interpretation
  - All URLs must be real (never hallucinated)
- **Output:** Raw product data for FormatterAgent
  - `product_title`, `price_total`, `seller_name`, `url`, `pickup_available`, `warranty_info`
- **Safety:** Rejects prohibited content (returns empty results)

---

### 4. **FormatterAgent (AgentTool)**
Finalizes results for user display.

- **Implementation:** AgentTool (NOT a standalone agent)
  - Called exclusively by RecommendationCoordinatorAgent
  - Uses `LlmAgent` from Google ADK
  - Temperature 0.0 for consistent, deterministic formatting
  - No tools (processes data internally)
- **Responsibilities:**  
  - Validate and clean raw data from `SearchAgent`
  - Remove suspicious/inconsistent products (fake prices, invalid URLs)
  - Verify budget alignment (exclude products >20% over budget)
  - Match results to user preferences (`user_note`, `preferred_store`)
  - Generate natural copy (`copy_for_user`) - max 3 sentences, factual, no emojis
  - Create UI badges (max 3 per product) - factual labels like "Cheapest", "12m Warranty"
- **Voice Guidelines:**
  - Tone: informative, professional, brief
  - NO emojis, NO hype, NO subjective promises ("perfect for you")
  - Can mention: price advantage, warranty, availability, concrete specs
  - Example: "Ideal para Photoshop y diseño gráfico. Cumple con GPU dedicada y diseño sobrio sin luces gamer."
- **Output example:**
  ```json
  {
    "status": "OK",
    "results_for_user": [
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
    ]
  }
  ```
        "product_title": "ASUS Vivobook Ryzen 7 16GB",
        "price_total": 6750,
        "seller_name": "TecnoMundo Guatemala",
        "copy_for_user": "Ideal for Photoshop and design. No RGB lights.",
        "badges": ["Good performance", "Discrete design", "Dedicated GPU"]
      }
    ]
  }
  ```

---

### 5. **Auxiliary & Future Agents**
| Agent | Description |
|--------|--------------|
| **getUserCountry Tool** | Returns country from user profile or defaults to `GT`. Enables localized recommendations. |
| **InsightAgent** | (Planned) Analyzes user habits for spending trends. |
| **PriceTrackerAgent** | (Planned) Monitors price fluctuations for saved items. |
| **BudgetAdvisor** | (Planned) Suggests budget adjustments aligned with user goals. |

---

## 🔁 Agent Communication

### Interaction Model
- **A2A (Agent-to-Agent)** communication follows an *orchestrated pattern*:
  ```
  Frontend → Coordinator → Search → Formatter → Coordinator → Frontend
  ```
- **Data contracts** between layers are strictly typed (JSON schemas).
- **Frontend never interprets AI logic**; it only renders structured data.

---

## 🗄️ Data Persistence & Context

### Database Overview
- **auth.users / profile:** authentication and user preferences.  
- **invoice / transaction:** financial records from confirmed OCR data.  
- **budget / recurring_transaction / wishlist_item:** dynamic goals, recurring events, and saved recommendations.  
- **category:** predefined + user-created categories (system keys protected).  
- **pgvector:** enables semantic similarity for search and recommendations.

### Context Sharing
Each agent can call helper tools (e.g., `getUserCountry`, `getUserCategories`) using user_id as a secure key, ensuring consistent contextual awareness across agents.

---

## 🔒 Security & Integrity
- **Authentication:** Supabase Auth; every API call includes a valid user token.  
- **RLS Policies:** Row-level security enforced in Supabase (user_id-scoped).  
- **Data Confirmation:** No record is stored without explicit user approval.  
- **Isolation:** Each agent runs within its own container and scope, preventing data leakage between subsystems.

---

## 🌐 Deployment
| Component | Platform | Deployment Method |
|------------|-----------|-------------------|
| Agents | Google Cloud Run | Containerized (Docker) |
| API Backend | Cloud Run | FastAPI REST endpoints |
| Database | Supabase Cloud | Managed PostgreSQL + pgvector |
| OCR & AI | Google Gemini + ADK | External call integration |

---

## 🧹 Design Principles
- **Single entry point per subsystem** (Coordinator/Orchestrator pattern).  
- **Human-in-the-loop confirmation** for all financial data.  
- **Strict contracts** between frontend ↔ backend ↔ agents.  
- **Scalable modularity:** each agent can evolve independently.  
- **Localization:** system adapts to user’s language, country, and currency preferences.

---

## 🚀 Summary
The Kashi Finances agent ecosystem forms an intelligent, distributed platform capable of:
- Automating expense recording via OCR.  
- Offering verified, contextual product and financial recommendations.  
- Managing budgets, goals, and insights with scalable cloud components.

This architecture ensures **accuracy, transparency, and user control**, aligning advanced AI workflows with real-world financial management.

---