---
applyTo: '**'
---
# Supabase Integration

These are the rules you (Copilot) must follow when interacting with **Supabase** for the Kashi Finances project. Your goal is to use Supabase correctly and safely while maintaining the structure, security, and consistency of the database.

---

## 1. How to use Supabase

### 1.1. Treat Supabase as the single source of truth

* The database schema in Supabase is the **canonical definition** for all data structures.
* Every table, enum, constraint, and policy you reference must exist in Supabase.
* Assume the live Supabase schema is always the most accurate version.

### 1.2. Using the Supabase MCP server

* You may use the **Supabase MCP server** (read-only mode) to:

  * Inspect table structures, columns, and relationships.
  * Inspect foreign keys, indexes, and RLS policies.
  * Understand enum definitions and valid values.
  * Propose migrations in SQL format, but never apply them directly.
* You **must not**:

  * Apply schema changes directly to production.
  * Modify or disable RLS or constraints.
  * Access or reveal production data.

### 1.3. Environment scope

* MCP is scoped to a **development or staging** environment that contains **dummy data**.
* Production is private; you must never access or reference its data.
* Always assume any read operation may contain sensitive information and must not be exposed or logged.

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

* Have RLS **enabled** (`ALTER TABLE ... ENABLE ROW LEVEL SECURITY`).
* Include at least one **SELECT** and one **INSERT/UPDATE/DELETE** policy.
* Use conditions like `USING (user_id = auth.uid())` and `WITH CHECK (user_id = auth.uid())`.

---

## 4. Schema and Migrations

### 4.1. Schema management

* The Supabase schema defines tables such as `transaction`, `wishlist`, `wishlist_item`, `account`, `profile`, etc.
* Each migration must include definitions for:

  * Primary and foreign keys.
  * Constraints (`CHECK`, `NOT NULL`, etc.).
  * Indexes for frequently queried fields.
  * Enum types where applicable.

### 4.2. Migration workflow

If schema changes are needed:

1. Propose a migration as SQL (`CREATE TABLE`, `ALTER TABLE`, etc.).
2. Always include enabling RLS and writing policies for new tables.
3. Describe effects on related tables and cascade rules.
4. Never execute DDL commands in production directly.
5. All schema changes go through version-controlled migrations and CI/CD review.

---

## 5. Business Rules (Database Layer)

### 5.1. Ownership enforcement

All tables with `user_id` must restrict visibility and operations to that user only.

### 5.2. Deletion rules

* **Account:** When an account is deleted, the app will either reassign or delete its related transactions.
* **Wishlist:** Deleting a wishlist cascades to delete all related `wishlist_item` rows.
* **Category:** Deleting a category reassigns transactions using that category to the global `general` category.

### 5.3. Data integrity

* Enforce referential integrity via foreign keys and ON DELETE rules.
* Respect enum constraints for fields such as `flow_type`, `frequency`, and `currency`.
* Use numeric/decimal for money amounts, not floating point.
* Maintain consistent timestamps with `DEFAULT now()`.

---

## 6. Supabase Enums

* Enums are part of logic and must not be altered without migration.
* Example enums:

  * `flow_type`: `'income' | 'outcome'`
  * `budget_frequency`: `'daily' | 'weekly' | 'monthly' | 'yearly' | 'once'`

Always use enum values as defined; never invent new string literals.

---

## 7. Data Privacy and Safety

* Do not log or expose database rows to the console or comments.
* Do not include production project URLs, keys, or tokens in code or documentation.
* Never suggest disabling security measures (RLS, Auth) for convenience.
* When generating example data, anonymize or synthesize it.
* Do not attempt to access or describe user data through MCP; only the schema.

---

## 8. Addendum — JWT & Key System Update

* Supabase now uses the **new JWT Signing Keys system** with ECC (P-256) asymmetric signing. The legacy HS256 shared secret is deprecated and no longer used.

* All token validation must rely on the **current public key** (ES256 algorithm) obtained from Supabase, not the old `SUPABASE_JWT_SECRET`.

* Copilot must assume that all API authentication and RLS enforcement rely on **user tokens signed by Supabase Auth** under this new key system.

* The backend validates these tokens using the **public key**, while Supabase continues issuing them using its private key.

* Do not reference or use the old `anon` and `service_role` keys; when necessary, prefer the new **`publishable`** and **`secret`** keys for controlled client and server operations.

* Always follow the latest Supabase documentation regarding JWT key rotation and validation.

---

## 9. Summary

* Supabase is the **source of truth** for schema and data structure.
* Use MCP in **read-only mode** to inspect schema, not to modify or view real data.
* All access must respect **RLS** and **Auth**.
* All schema changes must go through **migrations** under CI/CD.
* Never suggest disabling or bypassing security features.
* Never reveal production data, tokens, or secrets.

When uncertain, always prioritize **data safety**, **auth integrity**, and **schema consistency**.
