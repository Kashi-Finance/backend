# Row-Level Security (RLS)

> All user-owned tables enforce Row-Level Security to automatically isolate user data at the database level.

---

## RLS Pattern

### User-Owned Tables

**Applies to:** `account`, `transaction`, `invoice`, `budget`, `recurring_transaction`, `profile`

```sql
-- SELECT: Users see only non-deleted rows they own
user_id = auth.uid() AND deleted_at IS NULL

-- INSERT: Users can only insert for themselves
user_id = auth.uid()

-- UPDATE: Users can only update non-deleted rows they own
USING: user_id = auth.uid() AND deleted_at IS NULL
WITH CHECK: user_id = auth.uid()

-- DELETE: Users can only delete rows they own
user_id = auth.uid()
```

---

## Category Table (Special Case)

Categories have mixed ownership: system categories (global) and user categories (personal).

```sql
-- SELECT: Users see their own categories AND global system categories
user_id = auth.uid() OR user_id IS NULL

-- INSERT: Users can only create personal categories (key must be NULL)
user_id = auth.uid() AND key IS NULL

-- UPDATE: Users can only update their own categories (not system categories)
user_id = auth.uid() AND key IS NULL

-- DELETE: Users can only delete their own categories (not system categories)
user_id = auth.uid() AND key IS NULL
```

**Key Rules:**
- System categories have `user_id = NULL` and `key IS NOT NULL`
- User categories have `user_id = auth.uid()` and `key IS NULL`
- Users can read system categories but cannot modify them

---

## Indirect Ownership (wishlist_item)

Items are owned indirectly through their parent wishlist.

```sql
-- Access control via JOIN to wishlist table
EXISTS (
  SELECT 1 FROM public.wishlist w
  WHERE w.id = wishlist_item.wishlist_id
    AND w.user_id = auth.uid()
)
```

---

## Budget Category (Junction Table)

The `budget_category` junction table has its own `user_id` for RLS efficiency.

```sql
-- SELECT/INSERT/UPDATE/DELETE
user_id = auth.uid()
```

---

## Critical Rules for Application Code

1. **Never bypass RLS** — Application code must never use service role key for user operations
2. **Trust auth.uid()** — The only source of truth for user identity
3. **Don't send user_id in requests** — Extract from validated JWT only
4. **Test RLS policies** — Every new table must have comprehensive RLS tests
5. **Soft-delete filtering** — RLS policies automatically filter `deleted_at IS NULL`

---

## Service Role Exceptions

The service role key (bypasses RLS) is **only** used for:

1. Database migrations
2. GDPR hard-delete operations (admin-controlled)
3. Background jobs that need cross-user access (e.g., recurring transaction materialization)
4. System analytics (aggregated, anonymized)

**Never expose service role key to client code or public endpoints.**
