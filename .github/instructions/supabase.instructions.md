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

## 8. API Keys System (Publishable and Secret Keys)

### 8.1. Modern API Key Types

Supabase provides **four types of API keys**, but only the first two should be used in new code:

1. **Publishable Key** (`sb_publishable_...`)
   - **Purpose**: Low-privilege key safe to expose in client-side code
   - **Replaces**: Legacy `anon` JWT key
   - **Behavior**: Identical to `anon` key — respects RLS, works with `auth.uid()`
   - **Rotation**: Can be rotated independently without affecting JWT signing keys
   - **Use case**: All client-side and server-side operations that require RLS enforcement

2. **Secret Key** (`sb_secret_...`)
   - **Purpose**: Elevated privileges, server-only, bypasses RLS
   - **Replaces**: Legacy `service_role` JWT key
   - **Behavior**: Identical to `service_role` — bypasses RLS, has full database access
   - **Security**: Never expose in client code or version control
   - **Use case**: Administrative operations that need to bypass RLS (NOT used in this project)

3. **anon** (Legacy JWT long-lived)
   - **Status**: DEPRECATED — do not use in new code
   - **Problem**: Tied to JWT secret rotation, causes production downtime
   - **Migration**: Replace with `publishable` key

4. **service_role** (Legacy JWT long-lived)
   - **Status**: DEPRECATED — do not use in new code
   - **Problem**: Tied to JWT secret rotation, 10-year expiry is a security risk
   - **Migration**: Replace with `secret` key (if needed)

### 8.2. Why Legacy Keys Are Deprecated

Legacy `anon` and `service_role` keys have critical flaws:

- **Tight Coupling**: Bound to JWT secret; rotating JWT secret forces key rotation
- **Downtime Risk**: Mobile apps can't update instantly; forced rotation = weeks of downtime
- **Security Concerns**: 10-year JWT expiry, symmetric signing (HS256)
- **Inflexibility**: Can't independently rotate keys without affecting all JWTs

New keys solve these problems:

- **Independent Rotation**: Change keys without affecting JWT signing
- **Rollback Support**: Can revert problematic key rotations
- **Short-Lived**: API Gateway mints temporary JWTs internally
- **Asymmetric**: ES256 signing with better security properties

### 8.3. How Publishable Keys Work

When you use a publishable key:

1. **Request**: Client sends `apikey: sb_publishable_...` header
2. **API Gateway**: Verifies publishable key validity
3. **JWT Minting**: Gateway creates a short-lived JWT with `anon` role
4. **Forwarding**: JWT is sent to Postgres with the request
5. **RLS**: Postgres enforces RLS policies using `auth.uid()` from user's access token
6. **Response**: Data filtered by RLS is returned

**Important**: The publishable key does NOT replace the user's access token (JWT). Users still authenticate with Supabase Auth and get a JWT. The publishable key just authenticates the *client application*, not the *user*.

### 8.4. Using Keys in Python (supabase-py)

```python
import os
from supabase import create_client, Client

# ✅ CORRECT: Use publishable key
url: str = os.environ.get("SUPABASE_URL")
key: str = os.environ.get("SUPABASE_PUBLISHABLE_KEY")  # or SUPABASE_KEY
supabase: Client = create_client(url, key)

# ❌ WRONG: Don't use these deprecated names
# SUPABASE_ANON_KEY (legacy)
# SUPABASE_SERVICE_ROLE_KEY (legacy)
```

The key passed to `create_client()` can be either:
- A publishable key (`sb_publishable_...`) for RLS-protected operations
- A secret key (`sb_secret_...`) for admin operations that bypass RLS (not used in this project)

### 8.5. Important Limitations

**Cannot Use in Authorization Header**:
```python
# ❌ WRONG: Publishable/secret keys don't work in Authorization header
headers = {
    "Authorization": f"Bearer {publishable_key}"  # Will fail!
}

# ✅ CORRECT: User access tokens (JWTs) go in Authorization header
headers = {
    "Authorization": f"Bearer {user_access_token}"  # JWT from Supabase Auth
}
```

**Edge Functions**:
- If using Supabase Edge Functions with new keys, you may need `--no-verify-jwt` flag
- See Supabase docs for Edge Function configuration with new key system

### 8.6. Migration Path from Legacy Keys

For existing code using `SUPABASE_ANON_KEY`:

1. **Update Environment Variable**:
   ```bash
   # .env
   - SUPABASE_ANON_KEY=eyJhbG...  # Remove this
   + SUPABASE_PUBLISHABLE_KEY=sb_publishable_...  # Add this
   ```

2. **Update Configuration**:
   ```python
   # backend/config.py
   - SUPABASE_ANON_KEY: str = Field(...)
   + SUPABASE_PUBLISHABLE_KEY: str = Field(...)
   ```

3. **Update Client Creation**:
   ```python
   # backend/db/client.py
   - supabase_key=settings.SUPABASE_ANON_KEY
   + supabase_key=settings.SUPABASE_PUBLISHABLE_KEY
   ```

4. **Behavior**: No code changes needed! Publishable key works identically to anon key:
   - RLS still enforced
   - `auth.uid()` still works
   - User access tokens still required for authentication

### 8.7. JWT & Key System Summary

* Supabase uses **JWT Signing Keys** (ECC P-256 asymmetric signing) for user authentication
* User JWTs are validated using ES256 algorithm with public keys from `/.well-known/jwks.json`
* The old HS256 shared secret (`SUPABASE_JWT_SECRET`) is deprecated

**Two Separate Concepts**:
1. **User Authentication** (JWT Signing Keys): How users prove their identity
   - Users get JWTs from Supabase Auth (`sign_in_with_password`, `sign_up`, etc.)
   - Backend validates JWTs using public key (ES256)
   - JWT contains `user_id` used for RLS (`auth.uid()`)

2. **Application Authentication** (Publishable/Secret Keys): How the app authenticates to Supabase
   - App uses publishable key to make requests on behalf of users
   - Publishable key + user JWT = RLS-protected data access
   - Secret key = bypass RLS (admin operations)

---

## 9. Mandatory Rules for Kashi Finances Backend

For this project, you MUST:

1. **Always use `SUPABASE_PUBLISHABLE_KEY`** in `create_client()`
2. **Never use `SUPABASE_ANON_KEY`** or `SUPABASE_SERVICE_ROLE_KEY`
3. **Verify user JWTs** using ES256 with JWKS endpoint
4. **Rely on RLS** for all data access control
5. **Pass user access token** when creating authenticated Supabase clients
6. **Never bypass RLS** in application code (we don't use secret keys)

---

## 10. Summary

* Supabase is the **source of truth** for schema and data structure.
* Use MCP in **read-only mode** to inspect schema, not to modify or view real data.
* All access must respect **RLS** and **Auth**.
* All schema changes must go through **migrations** under CI/CD.
* Never suggest disabling or bypassing security features.
* Never reveal production data, tokens, or secrets.
* **Always use `SUPABASE_PUBLISHABLE_KEY`** instead of deprecated `SUPABASE_ANON_KEY`.
* **User JWTs** are validated using ES256/JWKS, not the old HS256 shared secret.

When uncertain, always prioritize **data safety**, **auth integrity**, and **schema consistency**.

---

## References

- [Supabase API Keys Documentation](https://supabase.com/docs/guides/api/api-keys)
- [Supabase JWT Signing Keys Guide](https://supabase.com/docs/guides/auth/signing-keys)
- [Supabase Python Client Reference](https://supabase.com/docs/reference/python/initializing)
