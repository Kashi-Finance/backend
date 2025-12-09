# Kashi Finances — Formal Technical Presentation

**Last Updated:** December 2025  
**Version:** 1.0  
**Architecture:** Supabase + FastAPI + Flutter + Gemini AI

---

## Executive Summary

Kashi Finances is a production-grade personal finance management platform designed for Latin American markets. The system combines mobile-first design with AI-powered automation, offering receipt OCR, intelligent product recommendations, and comprehensive budget tracking.

**Key Differentiators:**
- AI-powered receipt scanning with multimodal vision (Gemini)
- Real-time product recommendations grounded in web search data
- Bank-grade security with Row-Level Security (RLS) and JWT authentication
- Enterprise-ready CI/CD pipeline with automated testing and deployments
- Scalable serverless architecture on Google Cloud Run

---

## 1. Technology Stack

### 1.1 Frontend
| Component | Technology | Purpose |
|-----------|------------|---------|
| **Framework** | Flutter 3.x | Cross-platform mobile (iOS/Android) |
| **State Management** | Riverpod | Reactive state with dependency injection |
| **Language** | Dart | Type-safe development |
| **Localization** | Built-in Flutter i18n | Spanish/English support |

### 1.2 Backend
| Component | Technology | Purpose |
|-----------|------------|---------|
| **Framework** | FastAPI | High-performance async REST API |
| **Language** | Python 3.12 | Type-hinted, modern Python |
| **Package Manager** | uv | Fast, reproducible dependency management |
| **Validation** | Pydantic v2 | Strict request/response schemas |
| **Server** | Uvicorn | ASGI production server |

### 1.3 Database & Infrastructure
| Component | Technology | Purpose |
|-----------|------------|---------|
| **Database** | Supabase (PostgreSQL 15) | Relational data with RLS |
| **Authentication** | Supabase Auth (JWT ES256) | Secure user identity |
| **Storage** | Supabase Storage | Receipt image storage |
| **Vector Search** | pgvector | Semantic search embeddings |
| **Deployment** | Google Cloud Run | Serverless container hosting |
| **Container** | Docker (multi-stage) | Optimized production images |
| **CI/CD** | GitHub Actions | Automated testing and deployment |

### 1.4 AI Components
| Component | Technology | Purpose |
|-----------|------------|---------|
| **Invoice OCR** | Gemini 2.5 (Vision) | Multimodal receipt extraction |
| **Recommendations** | Gemini 2.5 Flash + Google Search | Web-grounded product suggestions |
| **Embeddings** | text-embedding-3-small | Semantic transaction search |

---

## 2. System Architecture

### 2.1 High-Level Architecture

```
┌─────────────────────────────────────────────────────────────────────────┐
│                          KASHI FINANCES ARCHITECTURE                    │
└─────────────────────────────────────────────────────────────────────────┘

┌──────────────┐      HTTPS/JWT      ┌──────────────────────────────────┐
│   Flutter    │ ◄─────────────────► │         FastAPI Backend          │
│  Mobile App  │                     │       (Google Cloud Run)         │
│  (Riverpod)  │                     │                                  │
└──────────────┘                     │  ┌─────────────┐ ┌────────────┐  │
                                     │  │   Routes    │ │  Schemas   │  │
                                     │  │ (Endpoints) │ │ (Pydantic) │  │
                                     │  └─────────────┘ └────────────┘  │
                                     │  ┌─────────────┐ ┌────────────┐  │
                                     │  │  Services   │ │   Agents   │  │
                                     │  │  (Logic)    │ │  (AI/LLM)  │  │
                                     │  └─────────────┘ └────────────┘  │
                                     └─────────────────────────────────┬┘
                                                    │                  │
                    ┌───────────────────────────────┼──────────────────┘
                    │                               │
                    ▼                               ▼
         ┌──────────────────┐            ┌──────────────────┐
         │   Supabase       │            │    Google AI     │
         │ ┌──────────────┐ │            │   ┌──────────┐   │
         │ │  PostgreSQL  │ │            │   │  Gemini  │   │
         │ │    + RLS     │ │            │   │  Vision  │   │
         │ └──────────────┘ │            │   └──────────┘   │
         │ ┌──────────────┐ │            │   ┌──────────┐   │
         │ │  Auth (JWT)  │ │            │   │  Google  │   │
         │ │   ES256      │ │            │   │  Search  │   │
         │ └──────────────┘ │            │   └──────────┘   │
         │ ┌──────────────┐ │            └──────────────────┘
         │ │   Storage    │ │
         │ │  (Images)    │ │
         │ └──────────────┘ │
         └──────────────────┘
```

### 2.2 Request Flow

1. **Authentication**: Mobile app sends `Authorization: Bearer <JWT>` header
2. **Token Validation**: Backend verifies ES256 signature via Supabase JWKS
3. **User Resolution**: `user_id` extracted from token claims (`auth.uid()`)
4. **Request Validation**: Pydantic model validates request body
5. **Business Logic**: Service layer processes request
6. **RLS Enforcement**: Database queries automatically scoped to user
7. **Response**: Pydantic model validates and serializes response

---

## 3. Security Architecture

### 3.1 Authentication Pipeline

```
┌─────────────────────────────────────────────────────────────────────┐
│                    AUTHENTICATION PIPELINE                           │
└─────────────────────────────────────────────────────────────────────┘

Client Request                Backend Validation                Database
     │                              │                               │
     │  Authorization: Bearer xyz   │                               │
     ├─────────────────────────────►│                               │
     │                              │                               │
     │                    ┌─────────▼─────────┐                     │
     │                    │ 1. Extract Bearer │                     │
     │                    │    token from     │                     │
     │                    │    header         │                     │
     │                    └─────────┬─────────┘                     │
     │                              │                               │
     │                    ┌─────────▼─────────┐                     │
     │                    │ 2. Fetch JWKS     │                     │
     │                    │    from Supabase  │                     │
     │                    │    (cached)       │                     │
     │                    └─────────┬─────────┘                     │
     │                              │                               │
     │                    ┌─────────▼─────────┐                     │
     │                    │ 3. Verify ES256   │                     │
     │                    │    signature +    │                     │
     │                    │    expiration     │                     │
     │                    └─────────┬─────────┘                     │
     │                              │                               │
     │                    ┌─────────▼─────────┐                     │
     │                    │ 4. Extract        │                     │
     │                    │    user_id from   │                     │
     │                    │    'sub' claim    │                     │
     │                    └─────────┬─────────┘                     │
     │                              │                               │
     │                              │   Query with user_id          │
     │                              ├──────────────────────────────►│
     │                              │                               │
     │                              │◄──────────────────────────────│
     │                              │   RLS: user_id = auth.uid()   │
     │◄─────────────────────────────│                               │
     │  Validated Response          │                               │
```

### 3.2 Row-Level Security (RLS)

All user-owned tables enforce automatic data isolation:

```sql
-- Standard RLS pattern for all user tables
CREATE POLICY "Users can only access own data"
ON public.transaction
FOR ALL
USING (user_id = auth.uid() AND deleted_at IS NULL)
WITH CHECK (user_id = auth.uid());
```

**Protected Tables:**
- `profile` — User preferences and localization
- `account` — Financial accounts (bank, cash, credit card)
- `transaction` — Income/expense records
- `invoice` — Receipt OCR data
- `budget` — Spending limits
- `recurring_transaction` — Automated transaction templates
- `wishlist` — Saved product recommendations

### 3.3 Security Guarantees

| Principle | Implementation |
|-----------|----------------|
| **User isolation** | RLS enforces `user_id = auth.uid()` on every query |
| **Token-based identity** | `user_id` extracted only from validated JWT |
| **Minimal data exposure** | Logs redact sensitive financial data |
| **Non-root containers** | Docker runs as `nonroot` user (UID 1000) |
| **Secret management** | Environment variables, never in code |

---

## 4. AI Components

### 4.1 InvoiceAgent — Receipt OCR

**Architecture:** Single-shot multimodal LLM workflow (NOT multi-agent)

```
┌──────────────────────────────────────────────────────────────────┐
│                    INVOICE AGENT WORKFLOW                        │
└──────────────────────────────────────────────────────────────────┘

Receipt Image                    Gemini Vision                    Response
(Base64)                            │                                │
    │                               │                                │
    │    1. User Context            │                                │
    │    (categories, currency)     │                                │
    ├──────────────────────────────►│                                │
    │                               │                                │
    │    2. Single Vision Call      │                                │
    │    (temperature=0.0)          │                                │
    │                               │                                │
    │                    ┌──────────▼──────────┐                     │
    │                    │   Gemini extracts:  │                     │
    │                    │   • Store name      │                     │
    │                    │   • Date/time       │                     │
    │                    │   • Total amount    │                     │
    │                    │   • Line items      │                     │
    │                    │   • Category match  │                     │
    │                    └──────────┬──────────┘                     │
    │                               │                                │
    │    3. Structured JSON         │                                │
    │◄──────────────────────────────┤                                │
    │                               │                                │
```

**Key Characteristics:**
- **Deterministic**: `temperature=0.0` for consistent extraction
- **Structured output**: `response_mime_type="application/json"`
- **No database access**: Agent returns data; API layer persists
- **Category matching**: Suggests existing category or proposes new

**Response Statuses:**
| Status | Description |
|--------|-------------|
| `DRAFT` | Successful extraction with structured data |
| `INVALID_IMAGE` | Cannot read image (blurry, not a receipt) |
| `OUT_OF_SCOPE` | Request not related to invoice processing |

### 4.2 Recommendation System — Web-Grounded LLM

**Architecture:** Gemini with Google Search grounding (real web data)

```
┌──────────────────────────────────────────────────────────────────┐
│              RECOMMENDATION SYSTEM WORKFLOW                      │
└──────────────────────────────────────────────────────────────────┘

User Query                      Gemini + Search                   Response
"laptop para diseño"                 │                               │
    │                                │                               │
    │    1. Build Prompt             │                               │
    │    (budget, country,           │                               │
    │     preferences)               │                               │
    ├───────────────────────────────►│                               │
    │                                │                               │
    │                     ┌──────────▼──────────┐                    │
    │                     │  Google Search      │                    │
    │                     │  Grounding Tool     │                    │
    │                     │  (live web data)    │                    │
    │                     └──────────┬──────────┘                    │
    │                                │                               │
    │                     ┌──────────▼──────────┐                    │
    │                     │  Filter & Rank      │                    │
    │                     │  • Budget match     │                    │
    │                     │  • Availability     │                    │
    │                     │  • User preferences │                    │
    │                     └──────────┬──────────┘                    │
    │                                │                               │
    │    2. Product Recommendations  │                               │
    │    (with real URLs/prices)     │                               │
    │◄───────────────────────────────┤                               │
    │                                │                               │
```

**Key Advantages:**
- **Real web data**: All URLs and prices from live Google Search
- **Single API call**: Search is automatic via grounding tool
- **Verified sources**: Grounding metadata includes source URLs
- **Localized**: Adapts to user's country and currency

**Response Statuses:**
| Status | Description |
|--------|-------------|
| `OK` | 1-3 product recommendations with URLs |
| `NO_VALID_OPTION` | No suitable products or prohibited request |

---

## 5. Database Design

### 5.1 Core Tables

| Table | Purpose | Relationships |
|-------|---------|---------------|
| `profile` | User preferences | 1:1 with auth.users |
| `account` | Financial accounts | Has many transactions |
| `category` | Transaction categories | Used by transactions, budgets |
| `transaction` | Income/expense records | Belongs to account, category |
| `invoice` | Receipt OCR data | May link to transaction |
| `budget` | Spending limits | Tracks categories via junction |
| `recurring_transaction` | Automation templates | Generates transactions |
| `wishlist` | Saved recommendations | Contains wishlist_items |

### 5.2 Key Design Patterns

**Soft-Delete Strategy:**
```sql
-- Records are never physically deleted
deleted_at TIMESTAMPTZ DEFAULT NULL

-- RLS automatically filters deleted records
WHERE user_id = auth.uid() AND deleted_at IS NULL
```

**Cached Balances:**
```sql
-- Account balance computed from transactions
account.cached_balance = SUM(income) - SUM(outcome)

-- Budget consumption computed from transactions in period
budget.cached_consumption = SUM(transactions in category during period)

-- Recomputation RPCs for reconciliation
SELECT recompute_account_balance(account_id);
SELECT recompute_budget_consumption(budget_id, category_id, start_date, end_date);
```

**Single Currency per User:**
- All financial data uses `profile.currency_preference`
- Currency can only be changed if no financial data exists
- Prevents multi-currency complexity

### 5.3 PostgreSQL Extensions

| Extension | Purpose |
|-----------|---------|
| `pgvector` | Semantic search embeddings |
| `pg_cron` | Scheduled jobs (streak reset) |
| `uuid-ossp` | UUID generation |

---

## 6. RPC Functions

The system uses **25 PostgreSQL RPC functions** with `SECURITY DEFINER` for atomic operations:

### 6.1 Categories by Domain

| Domain | Functions | Purpose |
|--------|-----------|---------|
| **Accounts** | 5 | Delete (2 strategies), favorites management |
| **Transactions** | 1 | Soft-delete with balance update |
| **Categories** | 1 | Delete with transaction reassignment |
| **Transfers** | 3 | Create/update/delete paired transactions |
| **Recurring** | 4 | Sync, create pairs, delete |
| **Wishlists** | 1 | Atomic create with items |
| **Budgets** | 2 | Delete, recompute consumption |
| **Engagement** | 3 | Streak update, status, weekly reset |
| **Currency** | 3 | Validate, get, check changeable |
| **Cache** | 2 | Recompute account balance, budget consumption |

### 6.2 Example: Transfer Creation

```sql
-- Creates two paired transactions atomically
SELECT * FROM create_transfer(
    p_user_id := auth.uid(),
    p_source_account_id := 'uuid-source',
    p_destination_account_id := 'uuid-dest',
    p_amount := 1000.00,
    p_description := 'Monthly savings',
    p_transaction_date := '2025-12-01'
);
-- Returns: (source_tx_id, destination_tx_id)
```

---

## 7. CI/CD Pipeline

### 7.1 Workflow Architecture

```
┌─────────────────────────────────────────────────────────────────────┐
│                      CI/CD PIPELINE                                  │
└─────────────────────────────────────────────────────────────────────┘

Feature Branch              Develop Branch               Main Branch
     │                           │                            │
     │  Push/PR                  │                            │
     ▼                           │                            │
┌─────────────┐                  │                            │
│     CI      │                  │                            │
│  ─────────  │                  │                            │
│  • mypy     │                  │                            │
│  • ruff     │                  │                            │
│  • pytest   │                  │                            │
│  • Docker   │                  │                            │
└──────┬──────┘                  │                            │
       │                         │                            │
       │ Merge                   ▼                            │
       └────────────────► ┌─────────────┐                     │
                          │   Staging   │                     │
                          │  ─────────  │                     │
                          │  • Wait CI  │                     │
                          │  • DB Push  │                     │
                          │  • Deploy   │                     │
                          └──────┬──────┘                     │
                                 │                            │
                                 │ Merge                      ▼
                                 └────────────────► ┌─────────────┐
                                                    │ Production  │
                                                    │  ─────────  │
                                                    │  • Wait CI  │
                                                    │  • DB Push  │
                                                    │  • Canary   │
                                                    │    (10%)    │
                                                    │  • Full     │
                                                    └─────────────┘
```

### 7.2 CI Checks

| Check | Tool | Purpose |
|-------|------|---------|
| **Type checking** | mypy | Static type analysis |
| **Linting** | ruff | Code style and errors |
| **Unit tests** | pytest | 150+ test cases |
| **Schema validation** | supabase db diff | Migration consistency |
| **Docker build** | BuildKit | Container validation |
| **Health check** | curl | Smoke test |

### 7.3 Deployment Features

- **CI Gate**: CD waits for CI to pass (`lewagon/wait-on-check-action`)
- **Concurrency groups**: Cancel in-progress on new push
- **Frozen dependencies**: `uv sync --frozen` for reproducibility
- **Canary deployment**: 10% traffic to new version on production
- **Environment isolation**: Separate Supabase projects per environment

---

## 8. API Design

### 8.1 Endpoint Categories

| Domain | Endpoints | Key Operations |
|--------|-----------|----------------|
| **Auth & Profile** | 5 | Identity, preferences, soft-delete |
| **Accounts** | 8 | CRUD, favorites, delete strategies |
| **Categories** | 6 | CRUD, tree view, subcategories |
| **Transactions** | 6 | CRUD, filters, recurring sync |
| **Invoices** | 4 | OCR, commit, list, detail |
| **Budgets** | 5 | CRUD with category linking |
| **Recurring** | 5 | CRUD, paired templates |
| **Transfers** | 3 | Create, update, delete pairs |
| **Wishlists** | 6 | CRUD, items, AI integration |
| **Recommendations** | 2 | Query, retry |
| **Engagement** | 3 | Streak, summary, budget score |

### 8.2 Response Patterns

**Success (200/201):**
```json
{
  "status": "CREATED",
  "transaction_id": "uuid-here",
  "transaction": { ... },
  "message": "Transaction created successfully"
}
```

**Error (4xx/5xx):**
```json
{
  "error": "validation_error",
  "details": "Amount must be positive"
}
```

---

## 9. Differentiators from Academic Projects

### 9.1 Production-Grade Practices

| Aspect | Academic Project | Kashi Finances |
|--------|------------------|----------------|
| **Security** | Basic auth | JWT ES256 + RLS + JWKS validation |
| **Data isolation** | Application-level | Database-level (RLS) |
| **Testing** | Manual | 150+ automated tests, CI required |
| **Deployment** | Manual | Automated CD with canary releases |
| **Secrets** | Hardcoded | Environment variables, never in code |
| **Containers** | Root user | Non-root (UID 1000) |
| **Dependencies** | pip install | Locked with uv.lock |
| **Schema changes** | Direct DB edits | Version-controlled migrations |

### 9.2 Engineering Principles

1. **Separation of Concerns**
   - Routes → Services → Agents → Database
   - Each layer has single responsibility

2. **Contracts First**
   - `API-endpoints.md` is source of truth
   - Pydantic enforces exact contracts

3. **Fail Gracefully**
   - All AI errors return structured responses
   - Never expose stack traces to clients

4. **Privacy by Design**
   - Logs redact sensitive data
   - Minimal context to AI components
   - RLS at database level

5. **Cost Optimization**
   - Single LLM calls vs multi-agent
   - 80% cost reduction in recommendations
   - 5-10s response vs 15-25s

### 9.3 Compliance Readiness

- **GDPR**: Soft-delete with 90-day retention
- **Data portability**: RPC for user data export
- **Audit trail**: `created_at`, `updated_at` on all tables
- **Anonymization**: Profile soft-delete anonymizes PII

---

## 10. Key Metrics

### 10.1 System Capabilities

| Metric | Value |
|--------|-------|
| **API Endpoints** | 47+ |
| **RPC Functions** | 25 |
| **Database Tables** | 11 core tables |
| **Test Cases** | 150+ |
| **Type Coverage** | 100% (mypy strict) |

### 10.2 Performance Characteristics

| Operation | Target |
|-----------|--------|
| **Invoice OCR** | < 5 seconds |
| **Recommendations** | < 10 seconds |
| **Standard API** | < 200ms |
| **Cold start** | < 3 seconds |

---

## 11. Summary

Kashi Finances demonstrates enterprise-ready software engineering:

✅ **Security**: Multi-layer authentication with database-level isolation  
✅ **AI Integration**: Practical LLM workflows with real web data  
✅ **Scalability**: Serverless architecture on Cloud Run  
✅ **Reliability**: Automated testing and canary deployments  
✅ **Maintainability**: Typed contracts and version-controlled schemas  
✅ **Cost Efficiency**: Optimized AI architectures (80% cost reduction)  

The system is designed to operate in production environments with real users while maintaining data privacy, security, and compliance standards.

---

*For detailed API documentation, see [API-endpoints.md](./API-endpoints.md)*  
*For database schemas, see [DB-documentation.md](./DB-documentation.md)*  
*For system design diagrams, see [docs/system-design-diagrams.md](./docs/system-design-diagrams.md)*


