# Project TODOs - Kashi Finances Backend

> **AI Agent Context Note**: This file follows progressive disclosure.
> Start with Priority Matrix. Drill into detail sections only when needed.
> File locations use relative paths from repository root.

**Last Updated:** December 20, 2025  
**Format Version:** 3.2 (AI-agent optimized with progressive disclosure)

---

## Status Key

| Symbol | Status | Description |
|--------|--------|-------------|
| ✅ | Completed | Implemented and verified |
| 🔄 | In Progress | Currently being worked on |
| ⛔ | Blocked | Waiting on external dependency |
| ⬜ | Not Started | Planned but not begun |
| ❌ | Won't Fix | Intentionally skipped with reason |

---

## Priority Matrix

### 🔴 Critical (Block Production)

| ID | Task | Status | Location | Notes |
|----|------|--------|----------|-------|
| C1 | Fix CI mypy errors | ✅ | `.github/workflows/ci.yaml:40` | Fixed Optional[AsyncOpenAI] type |
| C2 | Restrict CORS origins | ✅ | `backend/main.py:67` | Environment-based via CORS_ORIGINS |
| C3 | Configure monitoring alerts | ✅ | `docs/monitoring/README.md` | Alert definitions documented |

### 🟡 Medium Priority (Post-Launch)

| ID | Task | Status | Location | Notes |
|----|------|--------|----------|-------|
| M1 | Transaction embeddings | ⬜ | `backend/services/transaction_service.py:110,362` | Using text-embedding-3-small |
| M2 | Recurring transaction retroactive deletion | ⬜ | `backend/services/recurring_transaction_service.py:199` | On deactivation behavior |
| M3 | Sync endpoint max_occurrences | ⬜ | `backend/routes/recurring_transactions.py:586` | Limit batch generation |
| M4 | Weekday/monthday matching | ⬜ | SQL migrations | Currently simplified interval |

### 🟢 Low Priority (Future Enhancements)

| ID | Task | Status | Location | Notes |
|----|------|--------|----------|-------|
| L1 | Recommendation service tests | ⬜ | `tests/services/` | Unit tests for prompt chaining |
| L2 | Invoice agent tests | ⬜ | `tests/services/` | Integration tests with mocks |
| L3 | Configure ruff rules | ⬜ | `.github/workflows/ci.yaml:45` | Currently non-blocking |
| L4 | Branch protection | ⛔ | GitHub Settings | Requires GitHub Teams |
| L5 | "No Expenses" Check-in Endpoint | ⬜ | `backend/routes/engagement.py` | See [Engagement Check-in Proposal](#engagement-check-in-proposal) |
| L6 | Engagement tests | ⬜ | `tests/` | Tests for streak endpoints |

---

## Completed Items

<details>
<summary>December 2025 Completions (click to expand)</summary>

### Critical Production Items (Dec 20, 2025)
- ✅ C1: Fixed mypy errors (Optional[AsyncOpenAI] type annotation)
- ✅ C2: Environment-based CORS configuration via CORS_ORIGINS env var
- ✅ C3: Monitoring alerts documentation in `docs/monitoring/README.md`

### Test Suite Cleanup (Dec 20, 2025)
- ✅ Fixed favorite account route ordering (static routes before dynamic)
- ✅ Fixed RPC delete tests (5-tuple return value support)
- ✅ Removed outdated test files (1,692 lines):
  - `test_rpc_functions.py` (650 lines)
  - `test_rpc_transfer_and_account_functions.py` (1,042 lines)
- ✅ All 96 tests passing

</details>

<details>
<summary>November 2025 Completions (click to expand)</summary>

### Currency Architecture (Nov 30, 2025)
- ✅ Single-currency-per-user policy implemented
- ✅ Add `budget.currency` field (was missing)
- ✅ Add `validate_user_currency` RPC
- ✅ Add `get_user_currency` RPC
- ✅ Add `can_change_user_currency` RPC
- ✅ Service layer validation for account creation
- ✅ Service layer validation for wishlist creation
- ✅ Service layer validation for profile currency updates
- ✅ Block currency changes on account updates
- ✅ Auto-populate budget currency from profile

### Database & RPC (Nov 16, 2025)
- ✅ RPC naming consistency
- ✅ Remove service_role references from app code
- ✅ `recompute_account_balance` RPC
- ✅ `recompute_budget_consumption` RPC
- ✅ `delete_invoice` RPC (soft-delete)
- ✅ `delete_budget` RPC (soft-delete)
- ✅ Merge `balance_update_income`/`balance_update_outcome` → unified `balance_update` category
- ✅ Remove duplicate category delete RPC migration
- ✅ Update `invoice_service.py` to use `delete_invoice` RPC
- ✅ Update `budget_service.py` to use `delete_budget` RPC
- ✅ `PATCH /transfers/{id}` endpoint for atomic transfer updates
- ✅ Transfer edit validation in `PATCH /transactions/{id}`
- ✅ `update_transfer` RPC
- ✅ Update `.gitignore` with Supabase temp files

### AI Architecture (Nov 17-29, 2025)
- ✅ Migrate recommendation system: ADK multi-agent → Prompt Chaining
- ✅ Implement recommendation service with DeepSeek V3.2
- ✅ Refactor Invoice prompts with XML tags (Anthropic best practices)
- ✅ Refactor Recommendation prompts with XML tags
- ✅ Consolidate recommendation prompts to single file
- ✅ Update all documentation for new architecture

### API Features (Nov 16, 2025)
- ✅ Transaction sorting (`sort_by`, `sort_order` params)
- ✅ Budget filtering (`frequency`, `is_active` params)
- ✅ Response format standardization (API-endpoints.md section 0.1)
- ✅ All wishlist CRUD endpoints
- ✅ Pagination for list endpoints
- ✅ Transaction filtering (account_id, category_id, flow_type, date range)

</details>

---

## Currency Architecture (Resolved)

### Single-Currency-Per-User Policy

**Decision (Nov 30, 2025):** Enforce single currency per user.

| Entity | Currency Field | Enforcement |
|--------|---------------|-------------|
| `profile` | `currency_preference` | ✅ Source of truth |
| `account` | `currency` | ✅ Must match profile (validated on create, cannot change) |
| `wishlist` | `currency_code` | ✅ Must match profile (validated on create) |
| `budget` | `currency` | ✅ Auto-populated from profile |
| `transaction` | None | Inherits from account |
| `recurring_transaction` | None | Inherits from account |

### Validation Rules

1. **Account creation:** `validate_user_currency` RPC ensures currency matches profile
2. **Account update:** Currency field is blocked from updates
3. **Wishlist creation:** `validate_user_currency` RPC ensures currency matches profile
4. **Budget creation:** Currency auto-populated via `get_user_currency` RPC
5. **Profile currency update:** `can_change_user_currency` RPC blocks if user has financial data

### RPC Functions

| Function | Purpose |
|----------|---------|
| `validate_user_currency(user_id, currency)` | Raises exception if mismatch |
| `get_user_currency(user_id)` | Returns user's currency_preference |
| `can_change_user_currency(user_id)` | Returns false if has accounts/wishlists/budgets |

---

## Engagement Check-in Proposal (L5)

> **Status:** Proposed (not yet implemented)
> **Purpose:** Handle "no expenses" days without breaking streak

### Problem

Currently, users can only maintain their streak by logging transactions or invoices.
If a user genuinely has no expenses on a given day, they must either:
1. Use their one streak freeze per week
2. Let their streak break

### Proposed Solution

Add a "No Expenses Check-in" endpoint:

```
POST /engagement/check-in
{
  "type": "no_expenses",
  "note": "Optional note about the day"  // optional
}
```

### Response

```json
{
  "current_streak": 8,
  "longest_streak": 14,
  "streak_continued": true,
  "check_in_recorded": true,
  "message": "Great job being mindful! Streak maintained."
}
```

### Rules

| Rule | Description |
|------|-------------|
| Once per day | Only one check-in allowed per calendar day |
| Evening only | Visible in UI after 6 PM local time (prevent gaming) |
| Counts as activity | Updates streak same as transaction |
| Tracked separately | Record in new table for analytics |

### Database Changes

```sql
CREATE TABLE public.streak_check_in (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id UUID NOT NULL REFERENCES auth.users(id) ON DELETE CASCADE,
  check_in_date DATE NOT NULL,
  type TEXT NOT NULL DEFAULT 'no_expenses',
  note TEXT,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  UNIQUE (user_id, check_in_date)
);

ALTER TABLE public.streak_check_in ENABLE ROW LEVEL SECURITY;
```

### Implementation Files

| File | Changes |
|------|---------|
| `backend/routes/engagement.py` | Add `POST /engagement/check-in` |
| `backend/schemas/engagement.py` | Add `CheckInRequest`, `CheckInResponse` |
| `backend/services/engagement_service.py` | Add `check_in_no_expenses()` |
| `supabase/migrations/` | New migration for `streak_check_in` table |

### Alternatives Considered

| Alternative | Verdict |
|-------------|---------|
| More streak freezes | Could be gamed, reduces urgency |
| Auto-detect from balance | Requires bank sync (out of scope) |
| Skip weekends | Not all users have consistent schedules |

---

## Code-Level TODOs

> These exist in source code. Do NOT delete from code files.
> They serve as inline implementation documentation.

### Embedding Generation (M1)

**Files:**
- `backend/services/transaction_service.py:110` - Generate on create
- `backend/services/transaction_service.py:362` - Regenerate on update

**Implementation Spec:**
```python
# Model: text-embedding-3-small (1536 dimensions)
# 
# For invoice-based transactions (invoice_id NOT NULL):
#   input = invoice.extracted_text + transaction attributes
#
# For manual transactions (invoice_id IS NULL):
#   input = f"Amount: {amount}, Date: {date}, Category: {category_name}, Description: {description}"
```

### Recurring Transaction Service

| File | Line | TODO |
|------|------|------|
| `recurring_transaction_service.py` | 199 | Retroactive deletion on deactivation |
| `recurring_transaction_service.py` | 212 | Recalculate next_run_date on reactivation |


### CORS Configuration ✅

**File:** `backend/main.py`


```python
# Environment-based CORS configuration:
# - Development: allows all origins (*)
# - Production: requires CORS_ORIGINS env var (comma-separated list)
#
# Example: CORS_ORIGINS=https://app.kashi.finance,https://mobile.kashi.finance
```

### Database Client

**File:** `backend/db/client.py:86`
- Secret key configuration (correctly raises NotImplementedError for safety)

---

## Monitoring Alerts ✅

> **Status:** Documented in `docs/monitoring/README.md` (Dec 20, 2025)

| Alert | Threshold | Priority |
|-------|-----------|----------|
| API latency (p95) | > 500ms | High |
| Error rate | > 1% | Critical |
| Uptime | < 99.5% | High |
| Memory usage | > 80% | Medium |
| Invoice OCR failures | > 10% | Medium |
| Recurring sync failures | Any | Low |

See `docs/monitoring/README.md` for full setup instructions and verification checklist.

---

## Testing Status

### Existing Tests

| File | Coverage | Status |
|------|----------|--------|
| `test_accounts.py` | Account CRUD, favorites | ✅ 22 tests |
| `test_profile.py` | Profile CRUD | ✅ 12 tests |
| `test_transactions.py` | Transaction CRUD | ✅ 15 tests |
| `test_transfers.py` | Transfer creation | ✅ All passing |
| `test_transfers_refactor.py` | Transfer updates | ✅ All passing |
| `test_rpc_delete_functions.py` | Delete RPCs (category, recurring) | ✅ 11 tests |

### Missing Tests

- [ ] Recommendation service (prompt chaining)
- [ ] Invoice agent (mocked vision API)
- [ ] Recurring transaction sync
- [ ] Budget consumption calculation

---

## Architecture Reference

### AI Components

| Component | Type | Model | File |
|-----------|------|-------|------|
| InvoiceAgent | Single-shot multimodal | Gemini (vision) | `backend/agents/invoice/` |
| Recommendations | Prompt Chaining | DeepSeek V3.2 | `backend/services/recommendation_service.py` |

> **Note:** The ADK multi-agent architecture (RecommendationCoordinatorAgent → SearchAgent → FormatterAgent) was **deprecated November 2025** in favor of simplified Prompt Chaining.

### Prompt Locations

| System | File |
|--------|------|
| Invoice | `backend/agents/invoice/prompts.py` |
| Recommendations | `backend/agents/recommendation/prompts.py` |

---

## File Reference

> Quick lookup for common implementation tasks.

| Task | Location |
|------|----------|
| Add new RPC | `supabase/migrations/` |
| Add new endpoint | `backend/routes/` + `backend/schemas/` |
| Add new service | `backend/services/` |
| Database schema | `DB-DDL.txt`, `DB-documentation.md` |
| API contracts | `API-endpoints.md`, `docs/api/` |
| RPC documentation | `RPC-documentation.md` |
| Agent prompts | `backend/agents/*/prompts.py` |

---

## Deprecated References

> Do NOT use or reference these. Listed here for context.

| Component | Status | Replaced By |
|-----------|--------|-------------|
| RecommendationCoordinatorAgent | ❌ Deleted | `recommendation_service.py` |
| SearchAgent (ADK AgentTool) | ❌ Deleted | Built into prompt |
| FormatterAgent (ADK AgentTool) | ❌ Deleted | Built into prompt |
| `coordinator.py` | ❌ Deleted | N/A |
| `tools.py` | ❌ Deleted | N/A |
| ADK Runner integration | ❌ Removed | Direct API calls |

---

## Decision Log

| Date | Decision | Rationale |
|------|----------|-----------|
| Nov 16, 2025 | Merge balance_update categories | Simplify system categories |
| Nov 17, 2025 | Deprecate ADK multi-agent | Cost, latency, reliability |
| Nov 29, 2025 | Adopt Anthropic XML prompts | Better structure, examples |
| Nov 30, 2025 | Single-currency-per-user policy | Simplicity, no exchange rate complexity, budget field added |

---

*End of PROJECT-TODOS.md*
