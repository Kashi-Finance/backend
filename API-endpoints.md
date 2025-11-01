# Kashi Finances — API Endpoints v1

> This canvas lists every public REST endpoint the mobile app (Flutter frontend) will call. It also describes purpose, request, response shape at a high level, and important rules. Internal agent-to-agent calls are **not** exposed directly to the app.
>
> Base URL to define 
> All endpoints require an authenticated user unless explicitly marked as `public`.

---

## 1. Auth & Profile
These endpoints cover login context for the app and the basic user profile data needed by agents.

### `GET /auth/me`
Purpose: return the authenticated user's core identity for the session.
- Extracts and verifies the token’s signature.
- Reads the `user_id` claim from the token (`auth.uid()` in Supabase).
- Fetches the matching `profile` record using that `user_id`.
- Returns: `user_id`, `email`, `profile` (first_name, last_name, avatar_url, country, currency_preference, locale).
- Used by: frontend boot flow, to know which `user_id` to include in other calls.

### `PATCH /profile`
Purpose: update mutable profile fields.
- Body allowed fields: `first_name`, `last_name`, `avatar_url`, `country`, `currency_preference`, `locale`.
- Returns updated profile.
- Why `country` matters: RecommendationCoordinatorAgent uses it via `getUserCountry(user_id)` to localize sellers/prices.

---

## 2. Accounts & Categories
Money lives in accounts. Spending is labeled with categories.

### `GET /accounts`
Purpose: list all financial accounts for the current user.
- Each item: `id`, `name`, `type`, `currency`, derived `balance` (server-calculated from transactions), timestamps.
- Note: we **never** store running balance in DB. It's always derived from `transaction`.

### `POST /accounts`
Purpose: create a new account.
- Body: `name`, `type` (`cash`, `bank`, `credit_card`, `loan`, `remittance`, `crypto`, `investment`), `currency`.
- Returns: created account row.

### `PATCH /accounts/{account_id}`
Purpose: rename account, change type, etc.
- Only editable for accounts owned by the user.

### `GET /categories`
Purpose: list categories available to the user.
- Includes both global system categories (`user_id = null`, have `key`) and user-created categories.
- Each item: `id`, `name`, `flow_type` (`income` / `outcome`), flags that tell the UI if it's system or user category.
- Used by: invoice flow (dropdown), manual transaction entry, budgets.

### `POST /categories`
Purpose: create a **user** category.
- Body: `name`, `flow_type`.
- Returns: new category row.
- This is triggered e.g. when the InvoiceAgent suggested `match_type = "NEW_PROPOSED"` like "Mascotas" and user taps "crear".

---

## 3. Transactions (manual + generated)
A `transaction` is one money movement (income or outcome). It may optionally be linked to an `invoice`.

### `GET /transactions`
Purpose: fetch user's transactions.
- Query params (optional):
  - `from` / `to` (date range)
  - `account_id`
  - `category_id`
  - `search` (text or semantic query)
- Returns array of: `id`, `account_id`, `category_id`, `flow_type` (`income` | `outcome`), `amount`, `date`, `description` (nullable), `invoice_id` (nullable).
- May also include server-calculated helpers like `account_name`, `category_name` for convenience in the app list.

### `POST /transactions`
Purpose: insert a transaction manually (not from OCR and not from recurring automation).
- Body:
  - `account_id`
  - `flow_type` (`income` | `outcome`)
  - `amount`
  - `date` (TIMESTAMPTZ)
  - `description` (nullable)
  - `category_id` (nullable)
- Returns: created transaction.

### `PATCH /transactions/{transaction_id}`
Purpose: edit a transaction (amount, description, category, etc.).
- Can also update `account_id` (to "move" which account it belongs to) as long as it's still same user.

### `DELETE /transactions/{transaction_id}`
Purpose: delete a single transaction.
- If it was paired as part of a transfer (via `paired_transaction_id`), backend may also update the pair accordingly.

---

## 4. Invoice Flow (OCR → preview → commit)
This flow is tightly defined by the InvoiceAgent contract.

### `POST /invoices/ocr`
Purpose: the user just took / selected a photo of a receipt. Frontend uploads the image here.
- Body: multipart form-data with:
  - `user_id` (string UUID)
  - `image` (binary, the photo)
- Behavior:
  - Backend calls `InvoiceAgent`.
  - Returns **one** of two shapes:

  **A. status = "INVALID_IMAGE"**
  ```json
  {
    "status": "INVALID_IMAGE",
    "reason": "No pude leer datos suficientes para construir la transacción. Intenta tomar otra foto donde se vea el total y el nombre del comercio."
  }
  ```
  Frontend must *not* show edit screen. User either retries or cancels. Nothing is saved.

  **B. status = "DRAFT"**
  ```json
  {
    "status": "DRAFT",
    "store_name": "Super Despensa Familiar Zona 11",
    "purchase_datetime": "2025-10-30T14:32:00-06:00",
    "total_amount": 128.50,
    "currency": "GTQ",
    "items": [
      {"description": "Leche deslactosada 1L", "quantity": 2, "unit_price": 17.50, "total_price": 35.00},
      {"description": "Pan molde integral", "quantity": 1, "unit_price": 22.50, "total_price": 22.50}
    ],
    "category_suggestion": {
      "match_type": "EXISTING",
      "category_id": "uuid-de-supermercado",
      "category_name": "Supermercado"
    }
  }
  ```
  Frontend now shows a preview screen that the user can edit before saving.

Rules:
- The agent never persists anything on `ocr`. Absolutely nothing is committed to DB yet.
- If the image is unreadable or not actually a receipt, we only get `INVALID_IMAGE`.

### `POST /invoices/commit`
Purpose: the user confirmed / edited the OCR draft and wants to save it as a real expense.
- Body:
  ```json
  {
    "user_id": "uuid",
    "invoice_data": {
      "store_name": "Super Despensa Familiar Zona 11",
      "purchase_datetime": "2025-10-30T14:32:00-06:00",
      "total_amount": 128.50,
      "currency": "GTQ",
      "items": [
        {"description": "Leche deslactosada 1L", "quantity": 2, "total_price": 35.00},
        {"description": "Pan molde integral", "quantity": 1, "total_price": 22.50}
      ],
      "category_id": "uuid-de-category-seleccionada",
      "account_id": "uuid-de-la-cuenta-a-afectar",
      "flow_type": "outcome"
    },
    "image": (optional binary OR reference to temp image buffer)
  }
  ```
- Behavior server-side:
  1. Uploads the image to Supabase Storage and stores `storage_path` + `extracted_text` into `invoice`.
  2. Inserts a new row in `transaction`:
     - `user_id`
     - `account_id`
     - `category_id` (`General` if user kept default)
     - `flow_type` = `outcome`
     - `amount` = `total_amount`
     - `date`   = `purchase_datetime`
     - `description` = `store_name`
     - `invoice_id` = the created invoice row
- Returns: `{ "status": "COMMITTED", "transaction_id": "...", "invoice_id": "..." }`

Notes:
- If the invoice was `INVALID_IMAGE` we never call `/invoices/commit`.
- Frontend never writes directly into `invoice` or `transaction` tables. It always goes through this endpoint.

---

## 5. Budgets
A Budget = spending limit window that can repeat (`monthly`, `weekly`, etc.) or be one-off (`once`).

### `GET /budgets`
Purpose: list all active budgets for the user.
- Each item:
  - `id`, `limit_amount`, `frequency` (`once`, `daily`, `weekly`, `monthly`, `yearly`), `interval`, `start_date`, `end_date`, `is_active`.
  - Also include: which categories are attached to this budget.
  - Also include (calculated): `current_spend` and `remaining` for the **current active cycle**.

### `POST /budgets`
Purpose: create a budget / goal cap.
- Body:
  - `limit_amount`
  - `frequency` + `interval`
  - `start_date`
  - `end_date` (nullable)
  - `category_ids[]` (the spending categories this budget watches)
- Behavior: server inserts row in `budget` AND populates `budget_category` with those `category_ids`.
- Returns: created budget + categories.

### `PATCH /budgets/{budget_id}`
Purpose: edit amount, active flag, end_date, etc.
- Can also update which categories are tracked.

### `GET /budgets/{budget_id}/usage`
Purpose: return usage numbers for a single budget.
- Returns breakdown of spend per category and time window logic.
- Frontend can use this for budget detail screens / progress bars.

---

## 6. Recurring Transactions (automation rules)
These are templates like "Netflix Q90 every month" or "Salario cada 15". They eventually materialize into real `transaction` rows.

### `GET /recurring-transactions`
Purpose: list all recurring rules.
- Each item:
  - `id`, `account_id`, `category_id` (nullable), `flow_type`, `amount`, `description`,
  - `frequency` (`daily`, `weekly`, `monthly`, `yearly`), `interval`,
  - scheduling detail (`by_weekday`, `by_monthday`),
  - `start_date`, `end_date`, `next_run_date`, `is_active`.
- Used to render "suscripciones" / cargos fijos / ingresos fijos.

### `POST /recurring-transactions`
Purpose: create or programar una transacción recurrente.
- Body includes all the rule fields listed arriba.
- Returns: created rule.
- Backend guarantees:
  - `next_run_date` is calculated/validated.
  - `flow_type` is enforced (`income` / `outcome`).

### `PATCH /recurring-transactions/{recurring_id}`
Purpose: pause (`is_active=false`), change amount, change cadence, etc.

### `DELETE /recurring-transactions/{recurring_id}`
Purpose: fully remove that automation rule.
- Deleting the rule doesn’t delete past transactions already inserted.

---

## 7. Wishlist / Goals / Recommendations integration
Wishlist = what the user *wants* to buy. Recommendation Agent helps fill it.

### `GET /wishlist`
Purpose: list wishlist items (goals) for the current user.
- Each item:
  - `id`, `item_name`, `target_price`, `notes`, `url`, `status` (`planned`, `purchased`, `abandoned`), `target_date`, timestamps.
- Used by: wishlist screen; also lets the user reopen a goal and ask for better deals.

### `POST /wishlist`
Purpose: create a wishlist item / goal.
- Body:
  - `item_name` (what they want: e.g. "Laptop para diseño gráfico")
  - `target_price` (often becomes `budget_hint`)
  - `notes` (user_note / preferences like "nada gamer con luces RGB")
  - `target_date` (optional)
- Returns: created wishlist row.

### `PATCH /wishlist/{wishlist_id}`
Purpose: update fields like `status` → `purchased`, update `target_price`, etc.
- Also used when user taps "Guardar en mi wishlist/meta" on a recommended product.

---

## 8. Recommendation Agent Entry Point
Single public entry for all product suggestions / purchase guidance. The frontend NEVER calls subagents directly.

### `POST /recommendations/query`
Purpose: ask for product suggestions or continue an ongoing clarification loop.
- Body **must always** include:
  ```json
  {
    "user_id": "uuid",
    "query_raw": "texto libre que el usuario escribió",
    "budget_hint": 7000,
    "extra_details": {
      // merged answers the user already gave in previous steps
    }
  }
  ```
- `extra_details` starts as `{}` and grows as the agent asks questions.

- Backend flow:
  1. FastAPI calls `RecommendationCoordinatorAgent`.
  2. That agent validates intent (no sexual / crime / forbidden things; if invalid → `NO_VALID_OPTION`).
  3. If info is incomplete, returns `NEEDS_CLARIFICATION` with questions.
  4. If info is good, it calls SearchAgent → FormatterAgent and returns `OK` with up to 3 options.

- Possible responses:

  **A. status = "NEEDS_CLARIFICATION"**
  ```json
  {
    "status": "NEEDS_CLARIFICATION",
    "missing_fields": [
      { "field": "use_case", "question": "¿Para qué la vas a usar? (oficina, diseño...)" }
    ]
  }
  ```
  • Frontend job: show a generic message like "Necesitamos más información para encontrar una buena oferta.", render each `question` exactly as-is as an input, collect answers, merge into `extra_details`, then call `/recommendations/query` otra vez.

  **B. status = "OK"**
  ```json
  {
    "status": "OK",
    "results_for_user": [
      {
        "product_title": "HP Envy Ryzen 7 16GB RAM 512GB SSD 15.6"",
        "price_total_gtq": 6200.00,
        "seller_name": "ElectroCentro Guatemala",
        "url": "https://electrocentro.gt/hp-envy-ryzen7",
        "pickup_available": true,
        "warranty_info": "Garantía HP 12 meses",
        "copy_for_user": "Opción recomendada para diseño gráfico. Buen rendimiento con Ryzen 7 y 16GB RAM. Está alrededor de Q100 más barata que otras opciones similares.",
        "badges": ["Más barata", "Pantalla antirreflejo", "Garantía 12 meses"]
      }
    ]
  }
  ```
  • Frontend job: render each card with `product_title`, price, store, warranty, pickup, `copy_for_user` exactly as provided, and `badges` as visual chips. Also allow "Guardar en mi wishlist".

  **C. status = "NO_VALID_OPTION"**
  ```json
  {
    "status": "NO_VALID_OPTION"
  }
  ```
  • Meaning: the agent searched but filtered everything out (estafas, precios falsos, incoherente, producto prohibido, etc.).
  • Frontend job: show a fixed message like "No encontramos una oferta confiable con esos criterios." + CTAs para ajustar presupuesto / marca / volver a la meta.

Rules:
- The frontend MUST NOT invent technical explanations. `copy_for_user` is final.
- The order of `results_for_user` is already ranked by the agent. Do not reorder.
- The frontend always re-sends the full context (same `query_raw`, same `budget_hint`, merged `extra_details`) when asking again.

---

## 9. Analytics / Insights (future)
Endpoints below are placeholders for upcoming features like spending insights, trends, etc. They are not required for the first Beta but we are reserving them.

### `GET /insights/spending-overview`
Purpose: summary of recent spending (e.g. last 30 days).
- Returns high-level buckets like groceries / transport / eating out, and total outcome vs income.
- Backed by transaction table + embeddings for semantic grouping.

### `GET /insights/budget-health`
Purpose: check which budgets are close to being exceeded.
- Returns a list of budgets + usage %.

---

## 10. Security / RLS expectations
- Every request runs as the currently authenticated user.
- Row-Level Security in Supabase enforces `user_id = auth.uid()` for all user-owned rows (`account`, `transaction`, `invoice`, `budget`, `wishlist_item`, etc.).
- System/global rows (example: global categories) are readable but not editable by normal users.
- The app backend is responsible for:
  - making sure the `user_id` in the body actually matches the token
  - refusing cross-user access
  - refusing creation of illegal/blocked content in `/recommendations/query`.

---

## 11. Summary checklist for frontend devs
- Needs for onboarding screen:
  - Call `GET /auth/me` → save `user_id`.
  - Call `GET /profile` (implicitly via `/auth/me`) → get `country` for geo-recs.
- Needs for wishlist / meta screen:
  - User types goal + budget → send `POST /recommendations/query`.
- Needs for invoice capture:
  - Send photo to `POST /invoices/ocr`.
  - If `DRAFT`, show editable preview with category dropdown from `GET /categories` + list of accounts from `GET /accounts`.
  - On confirm, call `POST /invoices/commit`.
- Needs for budgets and recurring charges:
  - Use `/budgets`, `/recurring-transactions` to display limits and subscriptions.
- Needs for activity / history:
  - Use `/transactions` to render transaction list and account balances.

This is the full surface area expected for the mobile app in Beta, including finance tracking, OCR ingestion, recommendations, budgets, recurring payments, wishlist goals, and profile context.

