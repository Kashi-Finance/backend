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
Automates OCR and structured extraction from receipts or invoices.

- **Purpose:** Convert image → structured JSON → confirmed transaction.  
- **Status flow:**  
  - `INVALID_IMAGE`: unreadable or non-invoice image.  
  - `DRAFT`: valid extraction, pending user confirmation.  
- **Outputs:** store name, purchase date, total amount, suggested category.  
- **Persistence:** Data is stored only after human confirmation through `/invoices/commit`.  
- **Tables affected:** `invoice`, `transaction`.  
- **Frontend role:** Acts as human validation layer; never stores data automatically.

---

### 2. **RecommendationCoordinatorAgent**
Central orchestrator for all recommendation tasks.

- **Purpose:** Interpret user intent and route to appropriate subagents.
- **Flow control:**  
  1. Validates and sanitizes query (`query_raw`, `budget_hint`).  
  2. Rejects illegal or irrelevant intents.  
  3. Routes valid requests to `SearchAgent` → `FormatterAgent`.  
- **Possible statuses:**  
  - `NEEDS_CLARIFICATION` – asks user for missing details.  
  - `OK` – returns structured product options.  
  - `NO_VALID_OPTION` – no reliable result found.  
- **Endpoint:** `/recommendations/query`.

---

### 3. **SearchAgent**
Executes product searches or goal lookups according to user context.

- **Input:** validated query from the coordinator plus user metadata.  
- **Tasks:**  
  - Convert natural language into technical search filters.  
  - Query product APIs or embeddings.  
  - Return up to 3 verified results.

---

### 4. **FormatterAgent**
Finalizes results for user display.

- **Responsibilities:**  
  - Validate and clean raw data from `SearchAgent`.  
  - Match results to user preferences (`user_note`, `preferred_store`).  
  - Generate natural copy (`copy_for_user`) and badges.  
- **Output example:**
  ```json
  {
    "status": "OK",
    "results_for_user": [
      {
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