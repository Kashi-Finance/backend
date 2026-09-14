# Recommendations Endpoints

> **AI-powered product search for purchase goals**

## Table of Contents

- [Recommendations Endpoints](#recommendations-endpoints)
  - [Table of Contents](#table-of-contents)
  - [Endpoint Reference](#endpoint-reference)
  - [Workflow Architecture](#workflow-architecture)
  - [Response Types](#response-types)
    - [1. NEEDS\_CLARIFICATION (deprecated)](#1-needs_clarification-deprecated)
    - [2. OK](#2-ok)
    - [3. NO\_VALID\_OPTION](#3-no_valid_option)
  - [POST /recommendations/query](#post-recommendationsquery)
  - [POST /recommendations/retry](#post-recommendationsretry)
  - [Safety Guardrails](#safety-guardrails)
    - [1. Intent Validation](#1-intent-validation)
    - [2. Budget Enforcement](#2-budget-enforcement)
    - [3. User Preferences](#3-user-preferences)
    - [4. URL Verification](#4-url-verification)
    - [5. RLS](#5-rls)
  - [Integration Flow](#integration-flow)
    - [Complete User Journey](#complete-user-journey)
    - [Field Mapping](#field-mapping)
  - [Performance Notes](#performance-notes)
    - [Timing](#timing)
    - [Determinism](#determinism)
    - [Error Handling](#error-handling)

---

## Endpoint Reference

| Method | Path | Description |
|--------|------|-------------|
| POST | `/recommendations/query` | Query for product recommendations |
| POST | `/recommendations/retry` | Retry with updated criteria |

---

## Workflow Architecture (no agents, no ADK)

```
POST /recommendations/query|/retry
        │
        ├─► Auth (Supabase JWT → user_id)
        ├─► Endpoint fetches profile (country, currency, locale) via RLS
        ├─► Intent guardrails (prohibited content → NO_VALID_OPTION, no LLM call)
        │
        └─► ONE grounded Gemini 2.5 Flash call (google-genai SDK)
                │   Tool: GoogleSearch grounding · temp 0.2–0.3 · max 4096 tokens
                ▼
            Structured products[] + grounding_metadata → Pydantic response
```

**Key Points:**
- Single-shot grounded LLM call (`backend/services/recommendation_service.py`,
  prompts in `backend/llm/recommendation/prompts.py`); the ADK-style
  Coordinator/Search/Formatter prototype was deleted in 11/2025.
- All URLs/prices come from live Google Search grounding (verifiable)
- Workflow rejects prohibited content before/inside the call
- `NEEDS_CLARIFICATION` is deprecated → always `OK` or `NO_VALID_OPTION`

---

## Response Types

### 1. NEEDS_CLARIFICATION (deprecated)

> Deprecated: single-shot calls cannot ask follow-up questions. The workflow
> never returns this status; kept here only for backward compatibility with
> older clients. New clients handle only `OK` and `NO_VALID_OPTION`.

Missing required information:

```json
{
  "status": "NEEDS_CLARIFICATION",
  "missing_fields": [
    {
      "field": "budget_hint",
      "question": "¿Cuál es tu presupuesto aproximado para esta compra?"
    }
  ]
}
```

**Frontend Action:** Display question, collect answer, retry.

### 2. OK

Successful recommendations (1-3 products):

```json
{
  "status": "OK",
  "results_for_user": [
    {
      "product_title": "HP Envy Ryzen 7 16GB RAM 512GB SSD",
      "price_total": 6200.00,
      "seller_name": "ElectroCentro Guatemala",
      "url": "https://electrocentro.gt/hp-envy-ryzen7",
      "pickup_available": true,
      "warranty_info": "HP 12-month warranty",
      "copy_for_user": "Ideal para diseño gráfico. Cumple con GPU dedicada.",
      "badges": ["Cheapest", "12m Warranty", "Pickup Today"]
    }
  ]
}
```

**Frontend Action:** Display options, allow selection, then POST to `/wishlists`.

### 3. NO_VALID_OPTION

No suitable recommendations:

```json
{
  "status": "NO_VALID_OPTION",
  "reason": "No se encontraron productos que cumplan los criterios dentro del presupuesto."
}
```

**Possible Reasons:**
- No products match within budget
- All candidates failed validation
- Out-of-scope/prohibited request
- Search or agent failure

**Frontend Action:** Show reason, offer "Try again" or "Save goal manually".

---

## POST /recommendations/query

**Purpose:** Query for product suggestions based on purchase goal.

**Request Body:**
```json
{
  "query_raw": "laptop para diseño gráfico",
  "budget_hint": 7000.00,
  "preferred_store": "Intelaf Zone 9",
  "user_note": "No RGB lights, minimalist design for university",
  "extra_details": {}
}
```

**Required:**
- `query_raw` (string, 3-1000 chars): Natural or technical description

**Optional:**
- `budget_hint` (decimal, > 0): Maximum budget
- `preferred_store` (string, max 200 chars): Store preference
- `user_note` (string, max 1000 chars): Restrictions, style notes
- `extra_details` (dict): Progressive Q&A answers

**Response:** One of the three types above.

**Status Codes:**
| Code | Description |
|------|-------------|
| 200 | Request processed (check `status` field) |
| 400 | Invalid request data |
| 401 | Missing/invalid token |
| 500 | Server error (rare) |

---

## POST /recommendations/retry

**Purpose:** Retry with updated/refined criteria.

**Use Cases:**
- User received NO_VALID_OPTION, wants to adjust
- User received OK but wants different options
- User provided clarification answers

**Request Body:** Same structure as `/query`.

**Response:** Same three types as `/query`.

**Technical Note:** Identical to `/query` (calls same workflow). Separate endpoint for semantic clarity.

---

## Safety Guardrails

### 1. Intent Validation

Workflow rejects before search:
- Sexual/erotic content → NO_VALID_OPTION
- Weapons, explosives, regulated items → NO_VALID_OPTION
- Scams or fake offers → NO_VALID_OPTION

### 2. Budget Enforcement

- Products significantly over budget (>20%) excluded
- User can allow flexibility via `user_note`

### 3. User Preferences

- Workflow respects `user_note` constraints
- Example: `"nada gamer RGB"` → excludes RGB/gamer products

### 4. URL Verification

- All product URLs must be real (grounded in search results)
- Workflow never invents/hallucinates URLs
- Uncertain validity → product excluded

### 5. RLS

- Endpoint fetches `get_user_profile()` with authenticated `user_id` BEFORE the LLM call
- Workflow itself cannot access other users' data (RLS + prompt-injected context only)

---

## Integration Flow

### Complete User Journey

```
User fills wishlist wizard
       │
       ├─► "Save my goal" (manual)
       │       └─► POST /wishlists (no items)
       │
       └─► "Get recommendations"
               │
               ▼
       POST /recommendations/query
               │
               ├─► NEEDS_CLARIFICATION
               │       │
               │       ▼
               │   User answers question
               │       │
               │       ▼
               │   POST /recommendations/retry
               │
               ├─► OK (1-3 recommendations)
               │       │
               │       ▼
               │   User selects 0-3 options
               │       │
               │       ▼
               │   POST /wishlists (with selected_items)
               │
               └─► NO_VALID_OPTION
                       │
                       ├─► User adjusts → POST /recommendations/retry
                       │
                       └─► User saves manually → POST /wishlists (no items)
```

### Field Mapping

Workflow output matches `WishlistItemFromRecommendation`:

```
results_for_user[].product_title    →  selected_items[].product_title
results_for_user[].price_total      →  selected_items[].price_total
results_for_user[].seller_name      →  selected_items[].seller_name
results_for_user[].url              →  selected_items[].url
results_for_user[].pickup_available →  selected_items[].pickup_available
results_for_user[].warranty_info    →  selected_items[].warranty_info
results_for_user[].copy_for_user    →  selected_items[].copy_for_user
results_for_user[].badges           →  selected_items[].badges
```

Frontend passes through unchanged.

---

## Performance Notes

### Timing

Single grounded LLM call, typically a few seconds (target <10s):

**Frontend should show loading state.**

### Determinism

- Temperature 0.2–0.3 (near-deterministic for factual queries, slight variety)
- Results are fresh per query (not cached)

### Error Handling

All workflow errors caught and returned as NO_VALID_OPTION:
- Workflow execution failure → generic error message
- Invalid user_id → "Invalid request parameters"
- Unexpected errors → "An error occurred"

No exceptions bubble up to HTTP 500 unless catastrophic.
