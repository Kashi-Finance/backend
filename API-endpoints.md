# Kashi Finances — API Endpoints (Draft v1.1)
  
> This canvas lists every public REST endpoint the mobile app (Flutter frontend) will call. It also describes purpose, request, response shape at a high level, and important rules. Internal agent-to-agent calls are **not** exposed directly to the app.
> Base URL to define
> All endpoints require an authenticated user unless explicitly marked as `public`.

---

## 0. Authentication Flow (VERY IMPORTANT)

All endpoints in this document assume the mobile app includes a valid access token on every request:

```http

Authorization: Bearer <access_token>

```

How the backend knows "who is calling":

1. The backend verifies the token signature (Supabase Auth).
2. The backend extracts the authenticated `user_id` from that token (this is equivalent to `auth.uid()` under RLS).
3. The backend uses that `user_id` to:

* Fetch the user's profile from the `profile` table.
* Enforce Row-Level Security so the caller only sees/updates rows where `user_id` = them.
  
This means:

* The client does **not** need to send `user_id` in most requests. If it sends one anyway, the backend will still override/validate it against the token.
* If the token is missing/invalid/expired, the backend answers `401 Unauthorized`.
* `GET /auth/me` does **not** need a body.

---

## 1. Auth & Profile

These endpoints cover login context for the app and the basic user profile data needed by agents.

### `GET /auth/me`

Purpose: return the authenticated user's core identity for the session.

* Input: header `Authorization: Bearer <access_token>`. No body.
* Backend flow:
	1. Validate token.
	2. Extract `user_id`.
	3. Query `profile` table by that `user_id`.
* Returns:
	* `user_id`
	* `email`
	* `profile` (first_name, last_name, avatar_url, country, currency_preference, locale)


Use in frontend:
* On app boot, call this once to hydrate global session state.
* Also confirms token is still valid.

### `PATCH /profile`

Purpose: update mutable profile fields.

* Body allowed fields: `first_name`, `last_name`, `avatar_url`, `country`, `currency_preference`, `locale`.
* Returns updated profile.
* Why `country` matters: RecommendationCoordinatorAgent uses it via `getUserCountry(user_id)` to localize sellers/prices.

---

## 2. Accounts & Categories

Money lives in accounts. Spending is labeled with categories.

### `GET /accounts`

Purpose: list all financial accounts for the current user.

* Each item: `id`, `name`, `type`, `currency`, derived `balance` (server-calculated from `transaction`), timestamps.
* We **never** store running balance in DB. It's computed on read.

### `POST /accounts`

Purpose: create a new account.

* Body: `name`, `type` (`cash`, `bank`, `credit_card`, `loan`, `remittance`, `crypto`, `investment`), `currency`.
* Returns: created account row.

### `PATCH /accounts/{account_id}`

Purpose: rename account, change type, etc. Only editable if it belongs to the caller.

### `GET /categories`

Purpose: list categories available to the user.

* Includes both global system categories (`user_id = null`, readonly) and user-created categories.
* Each item: `id`, `name`, `flow_type` (`income` / `outcome`), and a flag that tells the UI if it's system or user-owned.
* Used by: invoice flow (dropdown), manual transaction entry, budgets.

### `POST /categories`

Purpose: create a **user** category.

* Body: `name`, `flow_type`.
* Returns: new category row.
* Typical trigger: user accepts an InvoiceAgent suggestion `match_type = "NEW_PROPOSED"`.
  
---

## 3. Transactions (manual + generated)

A `transaction` is one money movement (income or outcome). It may optionally be linked to an `invoice`.
### Shape of a transaction object

```json

{

"id": "...",

"account_id": "...",

"category_id": "...",

"flow_type": "income" | "outcome",

"amount": 128.50,

"date": "2025-10-30T14:32:00-06:00",

"description": "Super Despensa Familiar Zona 11",

"invoice_id": "..." | null,

"paired_transaction_id": "..." | null,

"account_name": "...", // convenience for UI

"category_name": "Supermercado" // convenience for UI

}

```

Notes:
* `paired_transaction_id` is set if this transaction is part of an internal transfer between two of the user's own accounts. The frontend should NOT count internal transfers as "spending" or "income" in insights.

### `GET /transactions`

Purpose: fetch user's transactions.

* Query params (optional):
* `from` / `to` (date range)
* `account_id`
* `category_id`
* `search` (text or semantic query)
* Returns array of `transaction` objects as defined above.

### `POST /transactions`

Purpose: insert a transaction manually (not from OCR, not from an automation rule).

* Body:
* `account_id`
* `flow_type` (`income` | `outcome`)
* `amount`
* `date` (TIMESTAMPTZ)
* `description`
* `category_id` (nullable)
* Returns: created transaction object (including `paired_transaction_id` if this was created as part of a transfer helper flow).

### `PATCH /transactions/{transaction_id}`

Purpose: edit a transaction (amount, description, category, account reassignment, etc.).

### `DELETE /transactions/{transaction_id}`

Purpose: delete a single transaction.

* If it was part of a transfer (`paired_transaction_id`), backend updates the pair accordingly.

---

## 4. Invoice Flow (OCR → preview → commit)

This flow is tightly defined by the InvoiceAgent contract.
It writes to real tables: `invoice`, `invoice_item`, and `transaction`.

### `POST /invoices/ocr`

Purpose: the user just took / selected a photo of a receipt. Frontend uploads the image here.

* Body: multipart form-data with:
* `image` (binary, the photo)
* Behavior:
	* Backend validates token → knows `user_id`.
	* Backend calls `InvoiceAgent`.
	* Backend returns **one** of two shapes:

**A. status = "INVALID_IMAGE"**

```json

{

"status": "INVALID_IMAGE",

"reason": "No pude leer datos suficientes para construir la transacción. Intenta otra foto donde se vea el total y el nombre del comercio."

}

```

Front-end: show error / pedir nueva foto. Nothing is stored.


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

"match_type": "EXISTING" | "NEW_PROPOSED",

"category_id": "uuid-de-supermercado" | null,

"category_name": "Supermercado" | "Mascotas"

}

}

```

Front-end: render preview screen. User can edit account, category, etc. Still nothing persisted yet.

Rules:
* `/invoices/ocr` NEVER persists to DB. No `invoice`, no `transaction`, no `invoice_item` row is inserted yet.
* If the image is unreadable or not actually a receipt, you only get `INVALID_IMAGE`.

### `POST /invoices/commit`

Purpose: the user confirmed / edited the OCR draft and wants to save it as a real expense.

* Body:

```json

{

"invoice_data": {

"store_name": "Super Despensa Familiar Zona 11",

"purchase_datetime": "2025-10-30T14:32:00-06:00",

"total_amount": 128.50,

"currency": "GTQ",

"items": [

{"description": "Leche deslactosada 1L", "quantity": 2, "total_price": 35.00},

{"description": "Pan molde integral", "quantity": 1, "total_price": 22.50}

],

"category_id": "uuid-category-seleccionada",

"account_id": "uuid-cuenta-a-afectar",

"flow_type": "outcome"

},

"image": (optional binary OR reference to temp buffer)

}

```


* Backend behavior (atomic):
1. Resolve `user_id` from the token.
2. Upload the receipt image to storage and record the `storage_path` + `extracted_text`.
3. Insert new row in `invoice` (and `invoice_item` rows for line items).
4. Insert new row in `transaction`:
	* `user_id`
	* `account_id`
	* `category_id` (or fallback `General` if user left default)
	* `flow_type` = `outcome`
	* `amount` = `total_amount`
	* `date` = `purchase_datetime`
	* `description` = `store_name`
	* `invoice_id` = the created invoice row

* Returns:

```json

{

"status": "COMMITTED",

"transaction_id": "...",

"invoice_id": "..."

}

```


Frontend rules:
* Do NOT write directly into invoice/transaction tables. Always go through `/invoices/commit`.
* If `/invoices/ocr` returned `INVALID_IMAGE`, you never call `/invoices/commit`.

---

## 5. Budgets

A Budget = spending limit window that can repeat (`monthly`, etc.) or be one-off (`once`).
These map to the `budget` table and its join table to categories.

### Frequency enum

`frequency` accepts:
* `once`
* `daily`
* `weekly`
* `monthly`
* `yearly`

`interval` works with it (e.g. `frequency = "weekly"`, `interval = 2` = every 2 weeks).

### `GET /budgets`

Purpose: list all active budgets for the user.

Each item returns:
* `id`
* `limit_amount`
* `frequency`, `interval`
* `start_date`, `end_date` (nullable)
* `is_active`
* `category_ids[]` (categories linked via the `budget_category` join table)
* calculated helpers:
	* `current_spend` (how much you've spent in the current active cycle)
	* `remaining`

### `POST /budgets`

Purpose: create a budget / goal cap.
* Body:
	* `limit_amount`
	* `frequency`
	* `interval`
	* `start_date`
	* `end_date` (nullable)
	* `category_ids[]`
* Behavior: backend inserts row in `budget` and populates the join table with the provided categories.
* Returns: created budget + categories.

### `PATCH /budgets/{budget_id}`

Purpose: edit amount, `is_active`, `end_date`, or tracked categories.

### `GET /budgets/{budget_id}/usage`

Purpose: detail view for a single budget.
* Returns breakdown of spend per category and time window logic.

---

## 6. Recurring Transactions (automation rules)

Recurring transactions are templates like "Netflix Q90 cada mes" or "Salario cada 15". They backfill real rows in `transaction` on schedule.

This maps to a table like `recurring_transaction`.
Important:
* `frequency` here is for repeating events. There is **no** `once` here. A one-time payment should be created with `POST /transactions`.

Typical fields of a recurring rule:
* `id`
* `account_id`
* `category_id` (nullable)
* `flow_type` (`income` / `outcome`)
* `amount`
* `description`
* `frequency` (`daily`, `weekly`, `monthly`, `yearly`)
* `interval` (e.g. every 2 weeks = `weekly` + `interval=2`)
* optional scheduling detail like `by_weekday`, `by_monthday`
* `start_date`
* `end_date` (nullable)
* `next_run_date`
* `is_active`

`end_date` means: last date on which this rule is allowed to generate a NEW transaction. After `end_date`, backend stops materializing it even if `is_active=true`.

### `GET /recurring-transactions`

Purpose: list all recurring rules for the user.
* Returns array of rule objects with the fields above.
* Used to render "suscripciones" / cargos fijos / ingresos fijos en UI.
  
### `POST /recurring-transactions`
  
Purpose: create a new recurring rule.
* Body: same fields except system-managed ones like `next_run_date`.
* Behavior:
* Backend validates cadence.
* Calculates and stores `next_run_date`.

### `PATCH /recurring-transactions/{recurring_id}`

Purpose: pause (`is_active=false`), change amount, change cadence, update `end_date`, etc.

### `DELETE /recurring-transactions/{recurring_id}`

Purpose: remove that automation rule.

* Deleting the rule doesn’t delete historical transactions already inserted.

---

## 7. Wishlist / Goals / Recommendations integration

`/wishlist` in the API corresponds to physical rows in the `wishlist_item` (or similar) table in the DB.

Wishlist = what the user *wants* to buy. Recommendation Agent helps fill it.

### `GET /wishlist`

Purpose: list wishlist items (goals) for the current user.
* Each item:
	* `id`
	* `item_name`
	* `target_price`
	* `notes` (user notes, preference like "nada gamer con luces RGB")
	* `url` (seller link / reference)
	* `status` (`planned`, `purchased`, `abandoned`)
	* `target_date`
	* timestamps

### `POST /wishlist`

Purpose: create a wishlist item / savings goal.
* Body:
* `item_name`
* `target_price`
* `notes`
* `target_date` (optional)
* Returns: created wishlist row.
* Typical usage: user says "guarda esta laptop recomendada".

### `PATCH /wishlist/{wishlist_id}`

Purpose: update fields like `status` → `purchased`, adjust `target_price`, etc.

---

## 8. Recommendation Agent Entry Point

Single public entry for all product suggestions / purchase guidance. The frontend NEVER calls subagents directly.

### `POST /recommendations/query`

Purpose: ask for product suggestions or continue an ongoing clarification loop.
* Body must include:

```json

{

"query_raw": "texto libre que el usuario escribió",

"budget_hint": 7000,

"extra_details": {

// merged answers the user already gave in previous steps

}

}

```

`extra_details` starts as `{}` and grows as the agent asks follow-ups.

Backend flow:
1. FastAPI calls `RecommendationCoordinatorAgent`.
2. That agent validates intent:
	* rejects sexual / crimen / cosas prohibidas → `NO_VALID_OPTION`.
	* also rejects cosas incoherentes ("quiero un misil").
3. If info is incomplete:
	* returns `NEEDS_CLARIFICATION` with questions.
4. If info is good:
	* calls SearchAgent → FormatterAgent
	* returns up to 3 ranked options.

Possible responses:

**A. status = "NEEDS_CLARIFICATION"**


```json

{

"status": "NEEDS_CLARIFICATION",

"missing_fields": [

{ "field": "use_case", "question": "¿Para qué la vas a usar? (oficina, diseño...)" }

]

}

```

Frontend: show these exact `question`s, collect answers, merge them into `extra_details` and re-call this same endpoint.


**B. status = "OK"**

```json

{

"status": "OK",

"results_for_user": [

{

"product_title": "HP Envy Ryzen 7 16GB RAM 512GB SSD 15.6\"",

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

Rules for frontend:
* Render cards exactly in this order. Do not reorder. Do not rewrite `copy_for_user`.
* Ofrezca CTA "Guardar en mi wishlist" que hace `POST /wishlist` usando estos datos.
  

**C. status = "NO_VALID_OPTION"**

```json

{

"status": "NO_VALID_OPTION"

}

```


Meaning:
* Agent searched but filtered everything (estafa, precios falsos, incoherente, producto bloqueado).
* Frontend shows "No encontramos una oferta confiable con esos criterios." + CTA para ajustar presupuesto / marca.

---

## 9. Insights / Analytics (future)

These endpoints are CALCULATED VIEWS, not direct tables. They read from `transaction`, `budget`, and related joins.
They are reserved for post-Beta reporting screens.

### `GET /insights/spending-overview`

Purpose: summary of recent spending (e.g. last 30 days).
* Returns high-level buckets like groceries / transport / eating out, and total outcome vs income.
* Backed by `transaction` + semantic grouping of `category`.

### `GET /insights/budget-health`

Purpose: check which budgets are close to being exceeded.
* Returns a list of budgets + usage %.

---
## 10. Security / RLS expectations

* Every request runs as the currently authenticated user (token in `Authorization` header).
* Row-Level Security in Supabase enforces `user_id = auth.uid()` for all user-owned rows (`account`, `transaction`, `invoice`, `invoice_item`, `budget`, `recurring_transaction`, `wishlist_item`, etc.).
* Global rows (example: global categories) are readable but not editable by normal users.

The backend is responsible for:
1. Making sure the token is valid (reject unauthenticated calls).
2. Making sure cross-user access is impossible (ignore/override any spoofed `user_id` in the body).
3. Refusing creation of illegal/blocked content in `/recommendations/query`.

---

## 11. Summary checklist for frontend devs

Boot / session:
* Read saved token from secure storage.
* Call `GET /auth/me` → hydrate session (`user_id`, `country`, `currency_preference`, etc.).
* If 401, force login again.

Invoice flow:
* Send photo → `POST /invoices/ocr`.
* If `DRAFT`, show preview. Let user pick `account_id`, `category_id` from `/accounts` + `/categories`.
* On confirm → `POST /invoices/commit`.

Wishlist / metas / compras:
* User writes goal or taps "dame opciones" → `POST /recommendations/query`.
* Show `NEEDS_CLARIFICATION` Q&A loop OR show ranked `OK` cards.
* Allow "Guardar en mi wishlist" → `POST /wishlist`.

Budgets & suscripciones:
* `/budgets` for spending caps (frequency can be `once`).
* `/recurring-transactions` for repeating charges/income (frequency cannot be `once`; supports `end_date`, `next_run_date`).

Activity / historia financiera:
* `/transactions` powers the activity feed and balance per account. Treat transactions with `paired_transaction_id` as transfers, not spending.