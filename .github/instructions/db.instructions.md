---
applyTo: '**'
---
# Database / Persistence Instructions (Authoritative Source)

This file is the ONLY place where database behavior, table structures, queries, and Row Level Security (RLS) rules are defined for the backend.

Application code MUST treat this file as the source of truth. Do not invent schemas or SQL in other files.

Always refer to DB-DDL.txt for exact table definitions and RLS policies.

## Documentation Structure (Progressive Disclosure)

The database documentation follows Anthropic's progressive disclosure pattern:

```
DB-documentation.md           ← Concise index - START HERE
└── docs/db/
    ├── README.md             ← Navigation guide
    ├── tables.md             ← Full table schemas
    ├── rls.md                ← Row-Level Security policies
    ├── enums.md              ← PostgreSQL enum definitions
    ├── indexes.md            ← Index definitions and strategy
    ├── soft-delete.md        ← Soft-delete patterns
    ├── cached-values.md      ← Cached balance/consumption
    ├── semantic-search.md    ← pgvector embeddings
    └── system-data.md        ← System categories and keys
```

**How to navigate:**
1. Start with `DB-documentation.md` for overview and quick reference
2. Load `docs/db/<topic>.md` only when you need full details
3. For table schemas, use `docs/db/tables.md`
4. For RLS policies, use `docs/db/rls.md`

## 1. Ownership

- Maintained by the data / RLS / persistence team.
- All reads/writes MUST follow these rules.
- All tables MUST enforce RLS such that `user_id = auth.uid()` for every financial row.
- The API layer MUST assume RLS is active and MUST pass the Supabase Auth user_id instead of anything provided by the client.

If the application code needs to save or fetch data and you (Copilot) don't have explicit instructions here:
- Insert a comment like:
    # TODO(db-team): persist/fetch <resource> according to backend/db.instructions.md
- Do not guess the table name or columns.
- Do not write raw SQL unless they are explicitly defined here.


## 2. invoice.extracted_text Format (MANDATORY)

When inserting or updating a record in the `invoice` table, the `extracted_text` column MUST always follow this canonical multi-line template:

    EXTRACTED_INVOICE_TEXT_FORMAT = """
    Store Name: {store_name}
    Transaction Time: {transaction_time}
    Total Amount: {total_amount}
    Currency: {currency}
    Purchased Items:
    {purchased_items}
    """

Where:
- `store_name`: cleaned human-readable merchant name.
- `transaction_time`: datetime string (ISO-8601 or the format we define here).
- `total_amount`: numeric rendered as string (e.g. "123.45").
- `currency`: currency code / symbol (e.g. "GTQ").
- `purchased_items`: multi-line list of the items with quantity and price.

Any service that prepares an insert into `invoice` MUST normalize text to this exact template before persistence. This ensures a consistent snapshot for audit and review.

The logic to actually INSERT this data and link it to `user_id` lives here in db.instructions.md and under RLS.
External layers (FastAPI endpoints, agents) MUST NOT directly craft SQL outside these rules.


## 3. Embeddings Strategy (for semantic search)

We will maintain vector embeddings for semantically searchable content such as:
- **Transactions:** generated from `invoice.extracted_text` (when available) combined with transaction attributes (`description`, `amount`, `category_name`, `date`)

Recommended embedding model:
- `text-embedding-3-small` by OpenAI.
  - Produces 1536-dimensional vectors. This model is described as cost-effective and suitable for general-purpose vector search and multilingual retrieval. It is positioned as the "most cost-effective" option compared to previous generations like `text-embedding-ada-002`. :contentReference[oaicite:0]{index=0} :contentReference[oaicite:1]{index=1}
  - Typical cost is on the order of $0.02 USD per 1M tokens of input, which is significantly cheaper (around 5x cheaper) than older embedding models while still improving multilingual retrieval quality. :contentReference[oaicite:2]{index=2} :contentReference[oaicite:3]{index=3} :contentReference[oaicite:4]{index=4}
  - It supports up to ~1536 dimensions by default and can be configured downwards (shorter vectors) using the model's `dimensions` parameter in some deployments, which lets us trade accuracy for storage cost. :contentReference[oaicite:5]{index=5} :contentReference[oaicite:6]{index=6}
  - This is appropriate for storing vectors in pgvector / Supabase and doing semantic search over user goals, preferred products, etc., with a good balance between accuracy and cost. :contentReference[oaicite:7]{index=7} :contentReference[oaicite:8]{index=8}

### Transaction Embeddings (Specific Rules)

For `transaction.embedding`, the vector MUST be generated from:

1. **If the transaction was created from an invoice (`invoice_id` is not NULL):**
   - Fetch the associated `invoice.extracted_text` (contains store name, items, total, transaction time)
   - Combine it with transaction data: `description`, `amount`, `category_name`, `date`
   - Generate embedding from the combined text using `text-embedding-3-small`

2. **If the transaction was manually created (`invoice_id` is NULL):**
   - Generate embedding from transaction attributes only: `description`, `amount`, `category_name`, `date`

This ensures:
- Invoice-based transactions benefit from rich OCR context (vendor, itemized products)
- Manual transactions still have meaningful semantic vectors
- Semantic search works uniformly across both types

Example input text for embedding generation:
```
# Invoice-based transaction:
"Store: Super Despensa Familiar, Items: Milk 2L Q15.00, Bread Q8.50, Total: Q128.50, Date: 2025-10-30, Category: Groceries, Description: Weekly shopping"

# Manual transaction:
"Amount: Q450.00, Date: 2025-10-28, Category: Utilities, Description: Monthly electricity bill"
```

Operational notes:
- All embeddings MUST be stored in a dedicated vector column (e.g. `vector(1536)` using pgvector or its equivalent in Supabase).
- The row containing the embedding MUST still respect RLS (only visible to the correct `user_id`).
- Any future retrieval / similarity search MUST filter by `user_id` first (RLS) and THEN perform vector similarity among that user's own data.

Do NOT inline the exact table / column definitions here until the persistence team finalizes them. The final schema (table names, column names, indexes, and RLS policies) will be added to this file when approved.

Until then, other parts of the code SHOULD NOT guess table names, column names, or pgvector usage details. They should only add comments such as:
    # TODO(db-team): generate embedding for transaction using text-embedding-3-small (from invoice.extracted_text + transaction data)
    # TODO(db-team): upsert embedding for wishlist_item.description using text-embedding-3-small


## 4. Supabase Auth and RLS Expectations

- All financial data tables MUST include a `user_id` column.
- RLS MUST enforce that every row is only visible / writable to the row owner: `user_id = auth.uid()`.
- API code MUST:
  - Verify the Supabase token.
  - Extract the `user_id`.
  - Perform all reads/writes AS that `user_id`.
- If the client sends any other `user_id`, the server MUST ignore it.

Any function in the service layer that touches persistence MUST follow this flow:
1. Receive the authenticated `user_id` from the API/auth layer (never from the client body).
2. Perform actions only for that `user_id`.
3. If an action would affect multiple rows, it must still be scoped to that same `user_id`.
4. If cross-user access is ever required, it MUST be documented explicitly here before being implemented.


## 5. TODO Sections

The following details are intentionally pending and MUST NOT be invented elsewhere:
- Exact table definitions (invoice, wishlist, wishlist_item, transactions, categories, budgets, profiles, etc.).
- Exact RLS policies.
- Exact SQL queries for inserts/updates/selects.
- Migrations and indexing strategy for embeddings and pgvector.

Any code that needs those details MUST reference this file and add:
    # TODO(db-team): see backend/db.instructions.md for final schema

Do not guess.
Do not "draft a possible schema" unless explicitly instructed to update this file.
