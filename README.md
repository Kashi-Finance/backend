# Kashi Finances — Backend

Production-oriented FastAPI backend for an AI-enabled personal finance platform (mobile-first, Latin America / GTQ-first). It owns domain logic, Postgres access, and two AI workflows: receipt/invoice OCR and grounded product recommendations.

This README documents the engineering behind the project: architecture, data/security design, domain invariants, LLM-workflow trade-offs, performance work, and operations.

> Terminology note: the LLM code lives at `backend/llm/` (renamed from `backend/agents/` in 2026). There are **no Google ADK agents** in this project — the `google-adk` package was never adopted (no dependency in `pyproject.toml`/`requirements.txt`) and the one ADK-style multi-agent prototype was deleted in 11/2025. What exists are **two single-shot LLM workflows** (OCR extraction + grounded recommendations) built directly on the **`google-genai` SDK** (`gemini-2.5-flash`). Identifiers like `run_invoice_agent` / `InvoiceAgentOutput` and filenames like `invoice-agent-specs.md` keep legacy names for compatibility. See §8.

> Branch consolidation status (Sep 2026): `feature/invoice-agent` was merged into `main` via PR #4 (`beb6c64`). `origin/main` (`214b638`) already contains the full feature history plus the README revision from PR #5. There is no pending domain code in the feature branch — current `feature/invoice-agent` → `main` diff is README-only. Local analysis docs (`DATABASE-TRIGGERS-ANALYSIS.md`, `PAGINATION-…`, `REDIS-…`, `DECISIONS/`, `docs/monitoring/`, `docs/testing/`) are now consolidated on `main` as working tree files.

---

## Table of contents

1. [Purpose & scope](#1-purpose--scope)
2. [Tech stack & why](#2-tech-stack--why)
3. [Architecture](#3-architecture)
4. [Project structure](#4-project-structure)
5. [Auth & security](#5-auth--security)
6. [Database engineering](#6-database-engineering)
7. [Domain logic highlights](#7-domain-logic-highlights)
8. [LLM-assisted features (legacy name: "agents")](#8-llm-assisted-features-legacy-name-agents)
9. [API design](#9-api-design)
10. [Performance engineering](#10-performance-engineering)
11. [DevOps: Docker, CI/CD, environments](#11-devops-docker-cicd-environments)
12. [Testing & code quality](#12-testing--code-quality)
13. [Documentation map](#13-documentation-map)
14. [Getting started](#14-getting-started)
15. [Key architectural / implementation decisions](#15-key-architectural--implementation-decisions)

---

## 1. Purpose & scope

Kashi Backend provides:

- HTTP API for the Flutter client and for automated consumption (`docs/api/` is structured for progressive disclosure).
- CRUD + business rules for: `profile`, `accounts`, `categories` (+subcategories), `transactions`, `transfers` (paired), `recurring_transactions` (+sync), `budgets`, `wishlists`, `invoices` (OCR), `recommendations`, `engagement` (streak / budget health).
- OCR ingestion: photo → Gemini extraction → human confirmation → committed `transaction` + stored image.
- Grounded recommendations: natural-language query → Gemini 2.5 Flash + Google Search grounding → 2–3 verifiable products.
- Postgres as source of truth with RLS-first security, RPCs for atomic multi-step writes, cached balances for read speed, pgvector for semantic search, pg_cron for streak maintenance.

Non-goals: no server-side sessions, no service-role bypass in app code, no background worker fleet (cron + request-time sync instead), no Redis in production yet (analyzed, not implemented — see §10).

---

## 2. Tech stack & why

| Layer | Choice | Why |
|---|---|---|
| API | `FastAPI ≥0.120` + `uvicorn[standard]` | DI for auth/DB, Pydantic validation, OpenAPI `/docs` for mobile + automation |
| Validation | `Pydantic v2` | `Literal`, `Field(ge/gt)`, `field_validator` / `model_validator` at the edge; typed `Request/Response` per domain |
| DB / Auth / Storage | `Supabase / Postgres + supabase-py ≥2.23`, `PyJWT + cryptography` | Managed Postgres + RLS + Storage buckets + JWKS auth; single `publishable key`, no shared secret |
| LLM | `google-genai ≥1.41` (`gemini-2.5-flash`) — this SDK **is** used | Single-shot OCR (`temp 0.0`) + grounded reco (`temp 0.2–0.3` + `GoogleSearch` tool); call sites: `backend/llm/invoice/agent.py:13,90,131`, `backend/services/recommendation_service.py:35,108,412` |
| Images | `Pillow` | MIME sniffing + 10 MB guard before base64→Gemini |
| Config | `python-dotenv`, `backend/config.py:Settings` | Fail-fast in staging/prod, warn-only in dev (`VALIDATE_CONFIG`) |
| Packaging | `pyproject.toml + uv.lock`, `requires-python ≥3.11` | Reproducible `uv sync --frozen`; `hatchling` wheel (`packages=["backend"]`) |
| Containers | Multi-stage `Dockerfile` (`uv:0.9.9-py3.12` → `python:3.12-slim`) | Layer-cached deps, `nonroot:1000`, `HEALTHCHECK /health`, Cloud Run `PORT=8080`, `workers 1` |
| Quality | `pytest + pytest-asyncio(auto)`, `mypy`, `ruff (line 100)`, `black`, `pyrightconfig.json` | Typed Python, CI gates |
| Infra extras | `pgvector (VECTOR(1536))`, `pg_cron`, `GZipMiddleware`, `PyJWKClient` cache | Semantic search, weekly streak reset, bandwidth/JWKS savings |

Deliberately **not used**: `google-adk` (Agent Development Kit framework — never added as a dependency; removed from requirements history in `ec34233`), `OpenAI SDK`, `DeepSeek/Perplexity SDKs`. Only `google-genai` (plain Gemini API client, no agent loop/runner) is used — see §8.

---

## 3. Architecture

Layered, dependency-injected, RLS-always:

```
Client / Flutter
      │  Bearer JWT (Supabase Auth, ES256)
      ▼
FastAPI (backend/main.py)
 ├─ middleware: CORS (env-based) → GZip(min 1KB) → RequestValidationError→422 logger
 ├─ routes/ (13 APIRouters, thin: auth → client → service → schema)
 ├─ schemas/ (Pydantic edge contracts, incl. ListResponse{items,count,limit,offset})
 ├─ services/ (domain rules, RPC orchestration, recompute, graceful degradation)
 ├─ llm/ (prompt builders + stateless single-shot LLM calls, no agent framework)
 ├─ auth/ + db/ (JWKS verify → user_id; per-request Supabase client with user JWT)
      ▼
Supabase Postgres (RLS) + Storage (invoices bucket) + Gemini 2.5 Flash
 ├─ 25 RPCs (SECURITY DEFINER, explicit p_user_id checks) for atomic writes
 └─ pgvector / pg_cron for search + streak cron
```

Request lifecycle (canonical, e.g. `POST /transfers`):

```python
# backend/routes/transfers.py (pattern shared by all routes)
auth_user: Annotated[AuthenticatedUser, Depends(get_authenticated_user)]  # JWT→sub
supabase_client = get_supabase_client(auth_user.access_token)             # RLS as user
try:
    result = await transfer_service.create_transfer(supabase_client, auth_user.user_id, ...)
    return TransferResponse(...)                                          # Pydantic
except ValueError as e:  # domain error → 400 {error, details}
except Exception:        # unexpected → 500, logged
```

Rules enforced in code, not just docs:

- `user_id` **never** comes from the body — only from `get_authenticated_user()` (`backend/auth/dependencies.py:198`).
- Services are `async fn(supabase_client, user_id, ...)`; routes do coercion (`_as_str/_as_float/...` for `NUMERIC/UUID`) + extra guards (e.g. `PATCH` requires ≥1 field; `weekly→by_weekday`, `monthly→by_monthday`).
- Post-write recomputes run in `try/except` non-blocking: a cache failure never fails the user write (`transfer_service.py`, `transaction_service.py`).

---

## 4. Project structure

```
backend/
├── main.py                 # app factory: CORS/GZip/422-handler + 13 routers + GET /health
├── config.py               # Settings (SUPABASE_URL, PUBLISHABLE_KEY, GOOGLE_API_KEY, ENV, CORS)
├── auth/dependencies.py    # get_jwks_client / verify_token→sub / get_authenticated_user
├── db/client.py            # get_supabase_client(user JWT) [RLS]; get_service_role_client() → NotImplemented
├── routes/                 # auth, accounts, budgets, categories, engagement, health,
│                           # invoices, profile, recommendations, recurring_transactions (+sync),
│                           # transactions, transfers, wishlists
├── schemas/                # 1:1 Pydantic models per route (Create/Update/Response + ListResponse)
├── services/               # account, budget, category, engagement, invoice, profile,
│                           # recommendation, recurring_transaction, storage, transaction,
│                           # transfer, wishlist
├── llm/invoice/            # single-shot OCR workflow (legacy names): agent.py
│                           # (run_invoice_agent), prompts.py, schemas.py, types.py (TypedDict),
│                           # tools.py (pre-LLM RLS helpers, plain Python, not LLM tools)
├── llm/recommendation/     # prompts only (system + user builders, XML-tagged,
│                           # few-shot); actual call lives in services/recommendation_service.py
└── utils/                  # logging (get_logger), constants
supabase/migrations/
├── 20251201000001_all_rpc_functions.sql        # 22 fns, 1924 lines
└── 20251208000001_engagement_rpcs_and_pg_cron.sql  # 3 fns + weekly cron
docs/{api,db,rpc,frontend,guides}  # domain refs, progressive-disclosure style (see §13)
tests/{routes,services,test_*.py}  # 151 passed
scripts/integration/       # 40+ curl scripts + run-all.sh (health→invoices→profile→…→transfers)
.github/workflows/         # ci.yml + staging.yml + prod.yml (active) + legacy .yaml dupes
Dockerfile, pyproject.toml, uv.lock, quickstart.sh
```

---

## 5. Auth & security

File references: `backend/auth/dependencies.py:40,75,198`, `backend/config.py:27-31`, `backend/db/client.py:22,71`, `SUPABASE-auth.md`, `docs/db/rls.md`.

- **JWT verification (ES256 + JWKS, no shared secret):** `Bearer → PyJWKClient.get_signing_key_from_jwt(kid) → jwt.decode(ES256, aud=authenticated, iss={SUPABASE_URL}/auth/v1, verify exp/aud/iss) → sub=user_id`. Migrated from legacy HS256. Typed 401s: `unauthorized | token_expired | jwks_error | invalid_token`.
- **JWKS caching:** `PyJWKClient(cache_keys=True, max_cached_keys=16, cache_jwk_set=True, lifespan=3600)` — 1 h vs 5 min default → ~12× fewer key fetches (see §10).
- **RLS-always:** every app query uses `create_client(URL, PUBLISHABLE_KEY) + auth.set_session(user_token)`, so Postgres enforces `user_id = auth.uid() AND deleted_at IS NULL`. `get_service_role_client()` explicitly raises `NotImplementedError` — service-role bypass is banned in app code.
- **RLS patterns:** `SELECT/INSERT/UPDATE` all check `user_id=auth.uid()`; `category` allows `user_id IS NULL` (system rows, immutable); `wishlist_item` checks parent ownership via `EXISTS`; `budget_category` carries its own `user_id` for efficient RLS. System `key` rows (e.g. `transfer`) are read-only.
- **RPC hardening:** `SECURITY DEFINER` funcs bypass RLS by design, so each validates `p_user_id` + ownership (`IF NOT EXISTS … RAISE EXCEPTION`), uses `SET search_path=''` + `public.` qualification, `GRANT EXECUTE … TO authenticated` only, and UUID/amount guards (`amount ≥ 0`, `limit > 0`). Single-currency invariant enforced by `validate/get/can_change_user_currency` RPCs.
- **Transport:** CORS is environment-based (`backend/main.py:_get_cors_origins`): `production` requires `CORS_ALLOWED_ORIGINS` else `[]` (mobile Flutter sends no `Origin`, so strict-by-default is safe); non-prod allows `*` for local dev.

---

## 6. Database engineering

Sources: `DB-DDL.txt`, `DB-documentation.md`, `docs/db/*.md`, `docs/rpc/*.md`, `RPC-documentation.md`, `DATABASE-TRIGGERS-ANALYSIS.md`.

### 6.1 RPC-first writes (25 functions)

- `20251201` migration: 22 funcs — `create/update/delete_transfer`, `create_recurring_transfer`, `delete_account_reassign/cascade`, `delete_transaction/invoice/budget/recurring`, `delete_category_reassign`, `create_wishlist_with_items`, `sync_recurring_transactions`, `recompute_account_balance / recompute_budgets_for_category`, `validate/get/can_change_user_currency`, `set/clear/get_favorite_account`.
- `20251208` migration: 3 funcs — `update/get_user_streak`, `reset_weekly_streak_freezes` (+ pg_cron schedule).
- Rule of thumb (`docs/rpc/guidelines.md`): direct `.table()` for single-row CRUD (`transaction_service.py:136,216`, `account_service.py:167`, …); `supabase.rpc()` for anything multi-step/atomic (paired transfers, reassign-on-delete, batch sync, recompute). RPC = one Postgres transaction, explicit errors mapped to `400 currency_mismatch` etc. via string-match in services.

### 6.2 Soft-delete + hard-delete (deliberate split)

`docs/db/soft-delete.md`, `docs/api/cross-cutting.md:193`:

- Soft (`deleted_at TIMESTAMPTZ`, RLS-filtered, deleted via RPC): `account`, `transaction`, `invoice`, `budget`, `recurring_transaction`. Preserves history, enables restore, keeps `paired_transaction_id` links intact.
- Hard: `category` (user rows reassign to `general` of same `flow_type`), `wishlist` (+`CASCADE items`), `wishlist_item`, `transaction` in some paths. `profile` = anonymization, not delete. `flow_type` itself is immutable.

### 6.3 Cached balances (read-fast, write-safe)

`docs/db/cached-values.md`:

- `account.cached_balance = SUM(income) − SUM(outcome)` (non-deleted); `budget.cached_consumption = SUM(outcome in budget_category within period)`.
- Maintained by `recompute_account_balance(account,user)` + `recompute_budget_consumption(...)` + `recompute_budgets_for_category(...)` after every create/update/delete. Only `outcome` consumes budgets; transfers do **not** consume budgets. Failures are swallowed (log + continue) to favor write availability over cache freshness.

### 6.4 Indexes, pgvector, pg_cron

- Indexes (`docs/db/indexes.md`): `transaction_user_date_idx(user_id, date DESC)`, `transaction_account_idx`, `recurring_tx_user_active_idx(user_id, is_active, next_run_date)`, `budget_user_active_idx`, partial `deleted_at WHERE IS NOT NULL`, `category_user_id_idx WHERE user_id IS NOT NULL`, FK indexes for `paired/recurring/invoice`. Recent review concluded existing indexes suffice — proposed `user_date_range` extras were rejected (see `PERFORMANCE-SUMMARY.md`).
- Semantic search (`docs/db/semantic-search.md`): `vector` + `pgcrypto` extensions, `transaction.embedding VECTOR(1536)` (`text-embedding-3-small`), `ivfflat (vector_cosine_ops)` index, query pattern `WHERE user_id=auth.uid() AND deleted_at IS NULL ORDER BY embedding <=> query LIMIT 10` — per-user similarity without cross-tenant leakage.
- pg_cron (`20251208:228-300`): only `reset_weekly_streak_freezes()` on `0 0 * * 1` (Mon 00:00 UTC). `cron.schedule` is commented/manual (requires Dashboard enablement); no `GRANT` to `authenticated` (postgres-only) except `update/get_user_streak`.

### 6.5 Single-currency invariant

`profile.currency_preference` is source of truth; `account`/`budget`/`wishlist(amount NUMERIC(12,2))` inherit it. `_normalize_numeric_12_2` (`quantize .01 ROUND_HALF_UP`, max `9999999999.99`). `update_account` blocks `currency/is_favorite` (favorites via dedicated `set/clear_favorite_account` RPCs). Currency change is gated by `can_change_user_currency` (blocks if financial data exists) — migration `20251130_single_currency_per_user`.

### 6.6 Why NOT triggers (explicitly decided)

`DATABASE-TRIGGERS-ANALYSIS.md` → **NOT RECOMMENDED**:

- RPCs already run inside Postgres: 2 round-trips vs 1, ~10–15 ms, ~3 % of a 500 ms p50 — not the bottleneck (real costs: no-cache 70 % + polling 20 % + no-pagination 10 %).
- Triggers would abort the `INSERT` on cache failure (vs current graceful degradation), need ~50 lines vs ~5 to handle soft-delete/restores/`account_id` moves, double-fire on paired transfers, and are harder to test than Python+RPC. Revisit only with multiple writers / raw-SQL ingestion — not the current case.

---

## 7. Domain logic highlights

Sources: `backend/services/*.py`, `docs/api/cross-cutting.md`, `PAGINATION-IMPLEMENTATION-SUMMARY.md`, `DECISIONS/2025-12-01-engagement-strategy.md`.

- **Paired transfers (atomic):** `transfer_service.py:16,118,224,312` + RPCs `create/update/delete_transfer`. One logical transfer = `outcome + income` linked by `paired_transaction_id` + system category `key='transfer'` (flow-aware). Only `amount/date/description` are mutable (`category/flow/pair/accounts` immutable). Post-RPC fetch + `recompute_account_balance` on both accounts. `delete_transaction` with `paired_id` delegates to `delete_transfer` to avoid orphans.
- **Recurring sync (batch, splash-safe):** `recurring_transaction_service.py:296`, `POST /transactions/sync-recurring` (designed 1×/5 min at splash). Single RPC `sync_recurring_transactions(p_user_id, p_today) → {generated, rules_processed, accounts_updated, budgets_updated}` with one recompute per affected account/budget. `next_run_date=start_date`; `update(apply_retroactive_change)` is TODO-scoped (no history rewrite); `False→True` does no backfill; `delete` uses `delete_recurring_and_pair` preserving history. Frontend guide: `docs/guides/recurring-sync-frontend-guide.md`.
- **Budgets:** `limit_amount gt 0`, `frequency ∈ {once,daily,weekly,monthly,yearl}`, optional `name`, `is_active` + soft-delete (`delete_budget` RPC), `frequency/is_active` filters, full category records in responses, `cached_consumption` recomputed only for `outcome` moves (`recompute_budgets_for_category`).
- **Categories:** flow-aware (`income/outcome`), system rows (`user_id NULL`, `key NOT NULL`, read-only) + user rows (`key NULL`); subcategories with inline creation; delete reassigns to `general` of same flow; `flow_type` immutable.
- **Engagement (implemented subset):** `profile{current_streak, longest_streak, last_activity_date, freeze_available, freeze_used_this_week}` + `update/get_user_streak` RPCs + weekly cron. Logic: same-day no-op; `diff=1 → +1`; `diff=2 + freeze → +1 consuming freeze`; else `reset=1`; `longest=GREATEST`. Endpoints `GET /engagement/streak|summary|budget-score`. Budget score 0–100: `≤75%→100`, `75–100% linear 100→75`, `>100%→max(0,50−(u−1)*100)` averaged (`on_track/warning/over`). `wishlist_contribution/saved_amount` remain proposal-only (`DECISIONS/2025-12-01-engagement-strategy.md`), not implemented — intentional scope cut.

---

## 8. LLM-assisted features (legacy name: "agents")

> **Read this first — naming caveat.** Nothing here is a Google ADK agent: no ADK Runner, no AgentTools, no tool loop, no multi-agent orchestration. The package `backend/llm/` (renamed from `backend/agents/` in 2026) and identifiers like `run_invoice_agent` / `InvoiceAgent` are historical names for **two plain single-shot Gemini calls** via the `google-genai` SDK. An ADK-style orchestrator prototype existed briefly and was **deleted in 11/2025** (`PROJECT-TODOS.md:108`, `recommendation-system-specs.md §Migration`). `.github/` instructions/prompts, `kashi-agents-architecture.md`, and `docs/api/recommendations.md` were purged of ADK claims in the same 2026 pass.

### 8.1 Invoice OCR — single-shot multimodal extraction + human-in-the-loop (NOT an agent)

Files: `backend/llm/invoice/{agent,prompts,schemas,tools,types}.py`, `backend/services/{invoice_service,storage}.py`, `backend/routes/invoices.py`, `backend/schemas/invoices.py`, `invoice-agent-specs.md` (legacy filename).

- Model/call: `gemini-2.5-flash` via `google-genai` SDK (`backend/llm/invoice/agent.py:13,90,131` — `genai.Client`, `GenerateContentConfig(system_instruction, temperature=0.0, response_mime_type="application/json")`, `contents=[Part(text=prompt), Part(inline_data=Blob(mime, base64))]`). MIME sniffed by prefix (`/9j/→jpeg`, `iVBOR→png`, `R0lGOD→gif`, `UklGR→webp`); 10 MB cap; non-`image/*` rejected.
- **Why "not an agent":** no tool-loop, no runner. The route (`backend/routes/invoices.py:186-197`) injects minimal RLS-scoped context pre-call (`profile{country,currency,locale}` + `outcome` categories) as prompt text; `tools.py` helpers are plain Python, not LLM tools. The code itself states this (`llm/invoice/agent.py`, `llm/__init__.py`).
- Prompt pattern: `system = <role><capabilities><limitations><guardrails>`; `user = <context><instructions><category_matching_rules><examples><output_schema>` with XML tags + few-shot (e.g. `Super Despensa→EXISTING`, `Mundo Mascota→NEW_PROPOSED`). Locale from `profile.locale` (`_extract_language_from_locale`).
- Triple-mirror schemas: `TypedDict` + JSON `INPUT/OUTPUT_SCHEMA` + Pydantic v2; invariant `category_suggestion{match_type, category_id/name, proposed_name}` enforced by `model_validator` (EXISTING needs id+name, NEW needs proposed_name; missing name → `"Uncategorized"`).
- **Ephemeral state machine (no `pending` row):** `POST /invoices/ocr → DRAFT | INVALID_IMAGE | OUT_OF_SCOPE` (in-memory preview, zero DB/storage side-effects) → user edits in Flutter → `POST /invoices/commit → COMMITTED` (creates `invoice{user_id, storage_path, extracted_text}` in canonical `EXTRACTED_INVOICE_TEXT_FORMAT` + linked `transaction{flow_type=outcome, system_generated_key=INVOICE_OCR, category_id}` + Storage upload `invoices/{user_id}/{uuid}.{ext}` + `create_signed_url(3600)`) / `DELETE /invoices/{id} → DELETED` (soft-delete RPC `delete_invoice`). Cancelled drafts leave nothing behind. Double-`commit` creates distinct UUIDs (no `Idempotency-Key` — safety comes from preview-then-commit, not dedup).
- Defensive parsing: malformed items dropped, missing `store/time/total/currency` degrades to `INVALID_IMAGE`, never a stacktrace. Privacy: `user_id[:8]` logs only, no image/PII logging, minimal LLM context.

### 8.2 Recommendation — grounded single-call LLM (NOT an agent; ex-ADK prototype deleted)

Files: `backend/llm/recommendation/prompts.py` (prompts only), `backend/services/recommendation_service.py:query/retry` (actual `google-genai` call `:35,108,412`), `backend/routes/recommendations.py:POST /recommendations/query|/retry`, `backend/schemas/recommendations.py`, `recommendation-system-specs.md v2.0/v3.1`.

- Current: `gemini-2.5-flash + Tool(google_search=GoogleSearch())`, `temperature 0.2–0.3`, `max_output_tokens 4096`, `system_instruction=RECOMMENDATION_SYSTEM_PROMPT`. Forces 2–3 products from distinct sellers with `ProductRecommendation{title, price_total, seller_name, url, pickup_available, warranty_info, copy_for_user, badges[:3]}` (max 3). `NEEDS_CLARIFICATION` deprecated → always `OK | NO_VALID_OPTION`.
- Evolution (why it matters — history, not current architecture):
  1. `v1 ADK orchestrator-workers prototype` (deleted 11/2025, never stabilized): 3 calls, 15–25 s, 5–10 % error, 15–20 % unknown-tool, 5 % 503, ~$1500/1M. Code (`coordinator.py`, `search_agent.py`, `formatter_agent.py`, ADK `schemas.py`/`tools.py`) no longer exists.
  2. `DeepSeek V3.2 prompt-chaining` (`temp 0.0`): 1 call, 1.5–2 s, <0.5 % error, ~$300/1M (−75 %) — but hallucinated URLs/prices.
  3. `Perplexity Sonar` → **`Gemini 2.5 Flash + Search grounding` (01/2025, current):** one SDK for both workflows, real results + `grounding_metadata{queries, chunks{uri,title,domain}}` for auditability.
- Known limitation: Search tool rejects `response_mime_type/response_schema` (400), so JSON is requested in-prompt and parsed defensively: strip ```` ```json ````, fix trailing commas/control-chars/smart-quotes, partial regex recovery (`product_title|price_total|seller|url` + `_extract_reason_from_text`). `reason` is factual, no apologies; guardrails refuse sexual/weapons/drugs/counterfeit/scam.
- Latency/cost posture: reco target `<10 s`, OCR `<5 s`, standard API `<200 ms` (`Kashi-Finances-technical-doc.md §10`). One call vs three removes cascade failure modes.

---

## 9. API design

`backend/main.py:78-144`, `backend/routes/*.py`, `backend/schemas/*.py`, `docs/api/cross-cutting.md`.

- **13 routers:** `auth, accounts, budgets, categories, invoices, transactions, profile, recurring_transactions (+sync_router), transfers, wishlists, recommendations, engagement` + inline `GET /health` (`routes/health.py` exists but is not the registered one — cleanup TODO).
- **Contracts:** `Create/Update/Response` triples + `ListResponse{items,count,limit,offset}`; `CREATED 201 / UPDATED / DELETED` envelopes; `flow_type: Literal[income,outcome]`, `amount ge/gt 0`, `interval ge 1`, `by_weekday ∈ {monday..sunday}` (lowercased), `by_monthday 1–31`, `description.strip()==""→None`, `NUMERIC(12,2)` normalization.
- **Pagination (consistent):** `?limit=50 (1–100) & offset=0` → `.order(...).range(offset, offset+limit−1)`; `transactions/accounts/wishlists/invoices` already had it; `budgets/recurring` added with `BudgetListResponse/RecurringTransactionListResponse` (`PAGINATION-IMPLEMENTATION-SUMMARY.md`). 50–80 % payload saving, backward-compatible.
- **Errors:** domain `ValueError→400 {error, details}` (e.g. `currency_mismatch`), `RequestValidationError→422 {error, details, body}` with body preview log, unexpected `→500`. Frontend guide: `docs/api/cross-cutting.md:45`, `docs/frontend/engagement-guide.md`.
- **Bandwidth/CORS:** `GZipMiddleware(minimum_size=1000)` (~60–80 % JSON saving, esp. tx lists / budgets / `extracted_text` / reco); CORS env-based (strict in prod, open in dev — §5).

---

## 10. Performance engineering

Sources: `PERFORMANCE-*.md`, `PERFORMANCE-SUMMARY.md`, `DATABASE-TRIGGERS-ANALYSIS.md`, `REDIS-CACHING-IMPLEMENTATION-GUIDE.md`, `PAGINATION-IMPLEMENTATION-SUMMARY.md`.

| Optimization | Status | Effect |
|---|---|---|
| `GZipMiddleware (1 KB threshold)` | ✅ shipped (`main.py:126`) | 60–80 % smaller JSON |
| `JWKS cache 5 min → 1 h` | ✅ shipped (`auth/dependencies.py:64`) | ~12× fewer key fetches |
| `cached_balance / cached_consumption` | ✅ shipped | O(1) reads; recompute only on writes, non-blocking |
| Pagination (`budgets`, `recurring`) | ✅ shipped | 50–80 % smaller list payloads |
| Indexes review | ✅ reviewed — no new indexes | Existing covering indexes sufficient |
| Supabase Realtime (replace polling) | ✅ documented as DONE | 100 % polling elimination, push-based |
| Redis (Upstash free: profiles 1 h, categories 6 h, accounts 5 min; write-through invalidate; **never** balances/txs) | 📄 analyzed, **not implemented** | Projected −70 % DB reads, −200–300 ms; in-memory cache explicitly rejected (Cloud Run restarts) |
| DB triggers for balances | ❌ analyzed, **rejected** | Would hurt resilience/testability for ~3 % gain (§6.6) |
| Invoice dedup (`image_hash`) | 📄 proposed | Avoid re-OCR of same receipt |

Claimed overall posture in docs: ~60 % faster responses (~500 ms → ~200 ms), ~60 % fewer DB queries, $200–500/mo savings headroom — treat as directional (measured per-endpoint, not load-tested globally).

---

## 11. DevOps: Docker, CI/CD, environments

### Docker → Cloud Run

`Dockerfile`: builder `uv sync --frozen --no-dev` (deps cached separately; `README.md` copied because `pyproject.toml` needs it) → runtime `python:3.12-slim + libpq5 + curl`, `nonroot:1000`, `PYTHONUNBUFFERED/DONTWRITEBYTECODE`, `HEALTHCHECK curl /health (30s/3s/5s/3)`, `CMD uvicorn backend.main:app --host 0.0.0.0 --port ${PORT} --workers 1`. Single worker is intentional for Cloud Run scale-to-zero + low-mem; scale via instances, not workers.

### CI/CD (branch-based)

`.github/CI-CD-SETUP.md`, `.github/workflows/`:

```
feature/*, fix/* → develop (staging auto-deploy) → main (prod auto-deploy)
```

- **CI (`ci.yml`, active):** on push to `feature/**, fix/**, develop, main` + PRs to `develop/main`: `mypy backend` + `pip requirements` + `supabase db start` + `db diff` (fail on drift) + `pytest -q` + Docker build (image loaded into daemon for testing — `310936a`).
- **Staging (`staging.yml`, on `develop`):** wait-for-CI → `supabase link + db push (staging)` → build/push → deploy Cloud Run staging → `/health` check.
- **Prod (`prod.yml`, on `main`):** wait-for-CI → PR-merge safety check (warning-only) → `db push (prod)` → deploy with **canary 10 %** → `/health` → manual 100 % promotion.
- Note: repo contains legacy dupes `ci.yaml/prod.yaml/staging.yaml` alongside active `ci.yml/prod.yml/staging.yml` — consolidate to one extension (TODO).
- Secrets per env: `SUPABASE_ACCESS_TOKEN`, `{STAGING,PRODUCTION}_{PROJECT_ID, DB_PASSWORD, SUPABASE_URL, PUBLISHABLE_KEY, GCP_PROJECT_ID, GCP_SA_KEY, SERVICE_ACCOUNT, GOOGLE_API_KEY_SECRET, CORS_ORIGINS}`.

### Environments & config

`ENVIRONMENT ∈ {development, staging, production}` drives CORS + `Settings.is_*()` + fail-fast validation. Supabase migrations are the deploy gate (staging/prod apply on push). Local parity: `supabase start` + `quickstart.sh` (pyenv 3.11–3.13, venv, `supabase start`, import check, pytest, curl examples).

---

## 12. Testing & code quality

- **Unit/integration:** `pytest (asyncio_mode=auto)`, `tests/{routes/test_invoices, services/test_{invoice,recommendation,storage}, test_{accounts,profile,transactions,transfers,transfers_refactor,rpc_delete}}` — **151 passed** at last snapshot. RPC delete atomicity/security covered (`test_rpc_delete_functions.py`).
- **Integration scripts:** `scripts/integration/{00-create-test-user … 71-transfers-list, START-BACKEND, setup-env, run-all.sh}` + `test-receipt.jpeg` — sequential health→OCR/commit/list→auth/profile→accounts→categories→tx→budgets→recurring→transfers. `scripts/test_recommendations.py` (623 lines) for reco prompts.
- **Static:** `mypy (py311, warn_return_any)`, `ruff (E,F,I,W; E501 off)`, `black`, `pyrightconfig.json`; CI runs `mypy backend` as gate + scheduled type-check step (`300bf3a`).
- **Docs-as-tests:** `docs/api/*.md (13 files)` + `API-endpoints.md` + `RPC-documentation.md` double as contract references; `docs/testing/recommendation-local-testing.md`, `docs/monitoring/README.md` cover local + observability loops.

---

## 13. Documentation map

| Path | Contents |
|---|---|
| `docs/api/{README,accounts,auth-profile,budgets,categories,cross-cutting,engagement,invoices,recommendations,recurring,transactions,transfers,wishlists}.md` | Per-domain HTTP refs, progressive-disclosure style |
| `docs/db/{README,tables,enums,rls,soft-delete,cached-values,indexes,semantic-search,system-data}.md` | Schema, RLS, delete semantics, caches, indexes, pgvector, seed system data |
| `docs/rpc/{README,guidelines,accounts,budgets,categories,currency,engagement,favorites,invoices,recurring,transactions,transfers,wishlists}.md` | All 25 RPCs: purpose/signature/behavior |
| `docs/frontend/engagement-guide.md`, `docs/guides/recurring-sync-frontend-guide.md` | Flutter integration checklists |
| `invoice-agent-specs.md`, `recommendation-system-specs.md`, `kashi-agents-architecture.md`, `Kashi-Finances-technical-doc.md` | LLM-workflow contracts (historical "agent" naming), evolution, full technical doc |
| `DB-documentation.md`, `DB-DDL.txt`, `RPC-documentation.md`, `API-endpoints.md`, `SUPABASE-auth.md`, `SEED-SYSTEM-CATEGORIES.sql` | Canonical DB/API/auth refs + seed |
| `PERFORMANCE-{SUMMARY,OPTIMIZATION-RECOMMENDATIONS,ARCHITECTURE-COMPARISON,QUICK-START}.md`, `DATABASE-TRIGGERS-ANALYSIS.md`, `PAGINATION-IMPLEMENTATION-SUMMARY.md`, `REDIS-CACHING-IMPLEMENTATION-GUIDE.md` | Perf analyses + rejected/accepted proposals |
| `DECISIONS/2025-12-01-engagement-strategy.md`, `PROJECT-TODOS.md` | Product strategy + task tracking |
| `docs/monitoring/README.md`, `docs/testing/recommendation-local-testing.md`, `.github/CI-CD-SETUP.md` | Ops/testing/CI guides (consolidated from feature work) |

---

## 14. Getting started

Prereqs: Python 3.11–3.13 (`pyenv`), `uv` (or `pip`), Supabase CLI, `GOOGLE_API_KEY`.

```bash
# 1. env
cp .env.example .env   # set SUPABASE_URL, SUPABASE_PUBLISHABLE_KEY, GOOGLE_API_KEY
# .env is gitignored; .env.example documents required vars

# 2. deps (reproducible)
uv sync --frozen        # or: pip install -r requirements.txt
# dev tools: black, mypy, ruff (pyproject [dev])

# 3. local Supabase + migrations
supabase start
supabase db push        # applies supabase/migrations/*.sql
# prod/staging equivalent: supabase link + db push (see .github/CI-CD-SETUP.md)

# 4. run
uvicorn backend.main:app --reload --port 8000
# or: ./quickstart.sh  (venv + supabase start + import check + pytest + curl examples)
# health: curl localhost:8000/health ; docs: localhost:8000/docs

# 5. verify
pytest -q                                    # unit/integration (151 passed snapshot)
./scripts/integration/run-all.sh             # end-to-end curl suite (needs START-BACKEND.sh + setup-env.sh)
mypy backend && ruff check backend
```

Useful: `demo_endpoint.py` (manual probe), `ENVIRONMENT=development` for open CORS, `VALIDATE_CONFIG=false` to skip fail-fast during introspection.

---

## 15. Key architectural / implementation decisions

| # | Decision | Rationale | Where |
|---|---|---|---|
| 1 | **RLS-first, no `service_role` in app** | Per-user isolation at the DB layer; token is the only `user_id` source; rotation-safe | `db/client.py:71`, `docs/db/rls.md` |
| 2 | **RPCs for atomic multi-step writes, direct queries for single-row CRUD** | One Postgres txn for paired transfers / reassign deletes / batch sync; avoids app-level partial writes | `supabase/migrations/2025*.sql`, `docs/rpc/guidelines.md` |
| 3 | **Soft-delete for financial history, hard-delete for taxonomies** | Auditability + link integrity vs simplicity where history has no value | `docs/db/soft-delete.md` |
| 4 | **Cached balances with graceful degradation** | O(1) reads without risking writes; cache miss ≠ user error | `docs/db/cached-values.md` |
| 5 | **No DB triggers for balances** | 3 % gain not worth abort-on-cache-fail + 10× complexity + double-fire | `DATABASE-TRIGGERS-ANALYSIS.md` |
| 6 | **Single-shot Gemini OCR + human commit (no agent loop, no ADK)** | Deterministic extraction (`temp 0.0`), zero side-effect previews, user-corrected commits | `llm/invoice/`, `invoice-agent-specs.md` (legacy filename) |
| 7 | **Reco: ADK prototype → chaining → Gemini+Search grounding** | ADK prototype deleted (unreliable/costly); single-call grounding fixes hallucinations + audit metadata | `recommendation-system-specs.md` |
| 8 | **XML-tagged prompts + triple-mirror schemas + defensive JSON repair** | Strict contracts surviving LLM variance (trailing commas, quotes, partial JSON) | `llm/*/prompts.py`, `services/recommendation_service.py` |
| 9 | **Paired-transfer immutability + batch recurring sync** | Money conservation; splash-safe single-RPC sync with per-account/budget batch recompute | `services/transfer_service.py`, `services/recurring_transaction_service.py` |
| 10 | **Pagination everywhere + GZip + JWKS 1 h TTL** | Mobile bandwidth/latency wins with 3 one-line-class changes | `main.py:126`, `auth/dependencies.py:64`, `PAGINATION-…` |
| 11 | **Redis analyzed, deferred; in-memory cache rejected** | Correct TTL/write-through design exists, but Cloud Run ephemerality kills local cache; ship when read pressure justifies | `REDIS-CACHING-IMPLEMENTATION-GUIDE.md` |
| 12 | **Branch-gated CI/CD with Supabase migration gate + prod canary** | `feature→develop→main`; `db diff` fail-fast; prod 10 % canary + manual promotion | `.github/workflows/ci.yml`, `staging.yml`, `prod.yml` |
| 13 | **Docs with progressive disclosure** | Split `docs/api|db|rpc` so readers/automation load minimal context per task | `docs/api/README.md` |
| 14 | **Single-currency per user + `NUMERIC(12,2)` discipline** | Avoids FX complexity in MVP; exact-cent arithmetic | `services/*`, `docs/rpc/currency.md` |
| 15 | **Engagement: streak + budget-score shipped, wishlist-savings deferred** | Highest-ROI habit loop first; pg_cron weekly reset; savings tracking stays proposal | `DECISIONS/2025-12-01-engagement-strategy.md` |
