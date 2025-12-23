---
applyTo: '**'
---

# Supabase Integration

These are the rules you (Copilot) must follow when interacting with **Supabase** for the Kashi Finances project. Your goal is to use Supabase correctly and safely while maintaining the structure, security, and consistency of the database.

Authoritative documentation (always prefer the latest version of these pages):

* Managing environments: [https://supabase.com/docs/guides/deployment/managing-environments](https://supabase.com/docs/guides/deployment/managing-environments)
* Database migrations: [https://supabase.com/docs/guides/deployment/database-migrations](https://supabase.com/docs/guides/deployment/database-migrations)
* Model Context Protocol (MCP): [https://supabase.com/docs/guides/getting-started/mcp](https://supabase.com/docs/guides/getting-started/mcp)
* Supabase MCP server tools: [https://github.com/supabase-community/supabase-mcp](https://github.com/supabase-community/supabase-mcp)

If anything in this file conflicts with those docs, **the docs win**. Always align suggestions with the latest Supabase documentation.

---

## 1. How to use Supabase

### 1.1. Treat Supabase + migrations as the single source of truth

* The **database schema managed by Supabase CLI migrations** is the canonical definition for all data structures.
* The actual databases in each environment (local, staging, production) must be derived **only** by replaying migration files under `supabase/migrations/`.
* Every table, enum, constraint, and policy you reference must exist in the Supabase schema produced by those migrations.
* Never suggest “hotfixing” staging/production via the Dashboard or ad-hoc SQL without also reflecting the changes in a proper migration.

### 1.2. Using the Supabase MCP server (read-only)

The project uses the **Supabase MCP server** to let AI tooling inspect and understand the schema. You (Copilot) may assume:

* The MCP server is configured in **read_only mode** and **scoped to a single project** via `project_ref`, so tools that mutate projects or databases are disabled.
* MCP is only connected to **development / staging** projects with dummy or obfuscated data, never to production.

You **may** use MCP to:

* Inspect database structure:

  * `database.list_tables` – see tables and schemas.
  * `database.list_extensions` – check enabled extensions.
  * `database.list_migrations` – inspect migration history.
* Run **read-only** SQL for exploration:

  * `database.execute_sql` – only for safe queries (e.g. `select`, `explain`) that **do not modify** data or schema.
* Explore documentation and project metadata:

  * `docs.search_docs` – search the Supabase docs for up-to-date patterns, especially for migrations, environments, RLS, auth, and branching.
  * `development.get_project_url` – retrieve project API URL if needed for code.
  * `development.get_publishable_keys` – only if absolutely necessary to verify that keys are of type `sb_publishable_...`, never to print or leak them.
  * `development.generate_typescript_types` – generate TypeScript types based on the database schema when working on client/shared types.

You **must not**:

* Use mutating tools, even if they appear in the tool list, including (but not limited to):
  `database.apply_migration`, `account.create_project`, `account.pause_project`, `functions.deploy_edge_function`, `branching.create_branch`, `branching.merge_branch`, `storage.update_storage_config`.
* Attempt to change schema or data directly via MCP (`execute_sql` must be used only for read-only queries in this project).
* Access or reveal any real production data, connection strings, secrets, or keys.

### 1.3. Environment scope for MCP

* MCP is **scoped to a development or staging environment** that contains **dummy or obfuscated data**.
* Production is private; you must never access or reference its data through MCP.
* Always assume any read operation could touch sensitive information; never echo full result sets into comments or documentation.

---

## 2. Authentication and Authorization Model

Supabase handles authentication and authorization through its **Auth system** and **Row Level Security (RLS)**. You must:

1. Treat `auth.users` as the root of truth for all authenticated users.
2. Assume `user_id` is validated via Supabase Auth; clients cannot set it manually.
3. Never expose or override `user_id` outside the Supabase Auth context.
4. Trust RLS to restrict data access to each user’s own rows.
5. Never generate or suggest policies that disable RLS or bypass ownership checks.

---

## 3. Row Level Security (RLS)

### 3.1. General behavior

* RLS ensures that users can only view or modify rows that belong to them (`user_id = auth.uid()`).
* Always assume that queries must respect this condition.
* Queries must never return data for other users.

### 3.2. Policy rules

Each table with sensitive data must:

* Have RLS **enabled** (`alter table ... enable row level security;`).
* Include at least one **SELECT** and one **INSERT/UPDATE/DELETE** policy.
* Use conditions like `using (user_id = auth.uid())` and `with check (user_id = auth.uid())`.

When suggesting new tables or migrations, always include RLS and policies as part of the DDL.

---

## 4. Schema and Migrations

### 4.1. Environments and migration flow

Assume three main environments:

* **Local development**

  * Uses Supabase CLI and Docker (`supabase db start`, `supabase db reset`) to replay migrations.
  * All schema changes start here as migration files under `supabase/migrations/`.
* **Staging**

  * Separate Supabase project.
  * Receives migrations via GitHub Actions using `supabase db push` and the configuration described in “Managing Environments”.
* **Production**

  * Separate Supabase project.
  * Receives migrations only after they pass CI and have been applied to staging, again via `supabase db push`.

General rule:

> All schema changes must flow **local → staging → production** through version-controlled migration files and CI/CD. Never modify staging or production schemas manually.

### 4.2. Migration workflow for Copilot

Whenever the user asks for changes to the database schema (new table, column, index, constraint, enum, or RLS policy), you must:

1. **Model the change as a migration**

   * Do **not** modify existing migration files that may already be applied.
   * Always create a **new** migration under `supabase/migrations/`.

2. **Use Supabase CLI naming conventions**

   * Suggest running:

     * `supabase migration new <short_description>`
   * In code suggestions, create a file with a timestamp plus description:

     * `supabase/migrations/YYYYMMDDHHMMSS_short_description.sql`
   * Use concise, snake_case descriptions (e.g. `add_wishlist_item_table`).

3. **Write Postgres-compatible SQL in the migration file**

   * For new tables:

     * Define primary keys explicitly.
     * Add foreign keys with appropriate `on delete` behavior.
     * Enable RLS (`alter table public.my_table enable row level security;`).
     * Add indexes for common access patterns.
   * For altering tables:

     * Prefer additive, non-breaking changes.
     * When destructive changes are requested, consider multi-step migrations.

4. **Handle RLS for new tables**

   * Immediately enable RLS.
   * Add policies for `select`, `insert`, `update`, `delete` that respect ownership.
   * Keep policies minimal and explicit; name them clearly (e.g. `policy_wishlist_select_own_rows`).

5. **Keep migrations ordered and re-runnable**

   * Assume environments replay migrations in timestamp order.
   * Avoid assumptions about specific data beyond what previous migrations guarantee.
   * Do not generate migrations that depend on ad-hoc manual operations.

6. **Seed data only via `supabase/seed.sql` when necessary**

   * If the change requires base data for local development, update `supabase/seed.sql`.
   * Never seed production-only confidential data.

7. **Integrate with CI/CD**

   * Assume:

     * `CI.yaml` validates schema and runs tests.
     * `staging.yaml` / `prod.yaml` use `supabase db push` to apply migrations after tests succeed.
   * Keep order: tests → staging migrations → Cloud Run deploy → production migrations.

---

## 5. Business Rules (Database Layer)

### 5.1. Ownership enforcement

All tables with `user_id` must restrict visibility and operations to that user only, via RLS:

* `using (user_id = auth.uid())`
* `with check (user_id = auth.uid())`

### 5.2. Deletion rules

Respect these deletion rules at the schema and application level:

* **Account**: Reassign or delete related transactions.
* **Wishlist**: Delete cascades to `wishlist_item`.
* **Category**: Reassign to the global `general` category.

### 5.3. Data integrity

* Use foreign keys with appropriate `on delete` rules.
* Use `numeric`/`decimal` types for monetary amounts, not `float`.
* Enforce domain logic via `check` constraints.
* Use `timestamptz` with `default now()` for timestamps.

---

## 6. Supabase Enums

* Enums must only be changed via migrations.
* Example enums:

  * `flow_type`: `'income' | 'outcome'`
  * `budget_frequency`: `'daily' | 'weekly' | 'monthly' | 'yearly' | 'once'`

---

## 7. Data Privacy and Safety

* Do not log or expose database rows.
* Do not include project URLs, keys, or tokens in code or docs.
* Never suggest disabling RLS or Auth.
* When generating example data, anonymize it.
* Treat all MCP outputs as potentially sensitive; never echo them verbatim.

---

## 8. API Keys System (Publishable and Secret Keys)

### 8.1. Preferred key types

1. **Publishable Key** (`sb_publishable_...`)

   * Safe for client-side usage.
   * Respects RLS and `auth.uid()`.
2. **Secret Key** (`sb_secret_...`)

   * Elevated privileges; bypasses RLS.
   * **Not used** in this project.

Legacy keys (`anon`, `service_role`) are **deprecated**.

### 8.2. Rules for this project

1. Always use `SUPABASE_PUBLISHABLE_KEY`.
2. Never use deprecated keys.
3. Verify JWTs via ES256 with JWKS.
4. Rely on RLS for access control.
5. Pass user JWTs for authenticated Supabase clients.
6. Never bypass RLS in app code.

---

## 9. JWT & Key System Summary

* Users authenticate via Supabase Auth (ES256 JWTs).
* Applications authenticate via publishable/secret keys.
* Publishable + user JWT → RLS-protected access.
* Secret key bypasses RLS (not used).

---

## 10. Supabase MCP tools for this project

### 10.1. Safe tools to use

* **Knowledge base / docs**:

  * `search_docs`: fetch up-to-date patterns.
* **Database**:

  * `list_tables`, `list_extensions`, `list_migrations`, `execute_sql` (read-only).
* **Development**:

  * `get_project_url`, `get_publishable_keys`, `generate_typescript_types`.
* **Debugging**:

  * `get_logs`, `get_advisors`.

### 10.2. Tools you must avoid

* `database.apply_migration`.
* `create_project`, `pause_project`, `restore_project`, `create_branch`, `merge_branch`, `update_storage_config`, `deploy_edge_function`.
* Any mutating or production-scope tools.

---

## 11. Mandatory behavior for Kashi Finances (summary)

1. Treat `supabase/migrations` as the **only** source of schema changes.
2. Always create new migrations.
3. Always enable RLS and define policies.
4. Respect environment flow local → staging → production.
5. Use MCP tools only in read-only mode.
6. Never reveal secrets or user data.
7. Always use `SUPABASE_PUBLISHABLE_KEY`.
8. Keep CI/CD safe and deterministic.

When uncertain, prioritize **data safety**, **auth integrity**, and **alignment with official Supabase documentation**.
