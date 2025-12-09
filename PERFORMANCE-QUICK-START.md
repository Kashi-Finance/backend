# Quick Start: Implementing Phase 1 Optimizations

**Target:** Complete in 1 day  
**Difficulty:** Easy  
**Impact:** 20-30% performance improvement

---

## Overview

This guide walks you through implementing the **3 quickest and easiest** performance optimizations:

1. ✅ Increase JWKS cache TTL (5 minutes)
2. ✅ Enable Gzip compression (1 line)
3. ✅ Add database indexes (30 minutes)

**Prerequisites:**
- Access to backend codebase
- Supabase CLI installed
- Basic knowledge of FastAPI and PostgreSQL

---

## 1. Increase JWKS Cache TTL

**Time:** 5 minutes  
**Impact:** 12x reduction in JWKS fetch frequency

### Current Code
```python
# backend/auth/dependencies.py (line 51)
_jwks_client = PyJWKClient(
    jwks_url,
    cache_keys=True,  # Default TTL is 300 seconds (5 minutes)
    max_cached_keys=16,
)
```

### Updated Code
```python
# backend/auth/dependencies.py (line 51)
_jwks_client = PyJWKClient(
    jwks_url,
    cache_keys=True,
    cache_jwk_set_ttl=3600,  # 1 hour (3600 seconds) instead of 5 minutes ✅
    max_cached_keys=16,
)
```

### Steps
1. Open `backend/auth/dependencies.py`
2. Find the `PyJWKClient` initialization (around line 51)
3. Add `cache_jwk_set_ttl=3600,` parameter
4. Save the file
5. Test locally: `uv run pytest tests/test_auth.py`

### Verification
```bash
# Check logs for reduced JWKS fetches
tail -f logs/app.log | grep "JWKS"

# Before: Every 5 minutes
# After: Every 1 hour ✅
```

---

## 2. Enable Gzip Compression

**Time:** 1 minute  
**Impact:** 50-70% smaller response payloads

### Current Code
```python
# backend/main.py (line 82)
# Create FastAPI app
app = FastAPI(
    title="Kashi Finances API",
    description="Backend service for Kashi Finances mobile app",
    version="0.1.0",
    docs_url="/docs",
    redoc_url="/redoc"
)
```

### Updated Code
```python
# backend/main.py (add after line 82)
from fastapi.middleware.gzip import GZipMiddleware

# Create FastAPI app
app = FastAPI(
    title="Kashi Finances API",
    description="Backend service for Kashi Finances mobile app",
    version="0.1.0",
    docs_url="/docs",
    redoc_url="/redoc"
)

# Enable Gzip compression for responses > 1KB
app.add_middleware(GZipMiddleware, minimum_size=1000)  # ✅
```

### Steps
1. Open `backend/main.py`
2. Add the import at the top
3. Add the middleware line after `app = FastAPI(...)`
4. Save the file
5. Test locally:
   ```bash
   uv run uvicorn backend.main:app --reload
   
   # In another terminal:
   curl -H "Accept-Encoding: gzip" http://localhost:8000/docs -I
   
   # Look for: Content-Encoding: gzip ✅
   ```

### Verification
```bash
# Before compression (example transaction list response)
curl http://localhost:8000/transactions -H "Authorization: Bearer $TOKEN" | wc -c
# Output: ~15000 bytes

# After compression
curl http://localhost:8000/transactions -H "Authorization: Bearer $TOKEN" -H "Accept-Encoding: gzip" --compressed | wc -c
# Output: ~5000 bytes (67% reduction ✅)
```

---

## 3. Add Database Indexes

**Time:** 30 minutes  
**Impact:** 10-50x faster queries

### Create Migration File

```bash
# Generate new migration
supabase migration new add_performance_indexes
```

This creates: `supabase/migrations/YYYYMMDDHHMMSS_add_performance_indexes.sql`

### Migration Content

Open the created file and add:

```sql
-- Performance Indexes for Kashi Finances
-- Created: December 2025
-- Purpose: Optimize common query patterns

-- ============================================================================
-- Transaction Indexes
-- ============================================================================

-- Index for transaction date range queries (used in budget calculations)
-- Example query: SELECT * FROM transaction WHERE user_id = ? AND date BETWEEN ? AND ? AND deleted_at IS NULL
CREATE INDEX IF NOT EXISTS idx_transaction_user_date_range 
ON transaction(user_id, date DESC) 
WHERE deleted_at IS NULL;

-- Index for account transaction history
-- Example query: SELECT * FROM transaction WHERE account_id = ? AND deleted_at IS NULL ORDER BY date DESC
CREATE INDEX IF NOT EXISTS idx_transaction_account_date 
ON transaction(account_id, date DESC) 
WHERE deleted_at IS NULL;

-- Index for category-based transaction filtering
-- Example query: SELECT * FROM transaction WHERE category_id = ? AND deleted_at IS NULL
CREATE INDEX IF NOT EXISTS idx_transaction_category 
ON transaction(category_id) 
WHERE deleted_at IS NULL;

-- ============================================================================
-- Budget Indexes
-- ============================================================================

-- Index for budget category lookups (used in consumption calculations)
-- Example query: SELECT * FROM budget_category WHERE category_id = ?
CREATE INDEX IF NOT EXISTS idx_budget_category_category_id 
ON budget_category(category_id);

-- Composite index for budget category relationships
CREATE INDEX IF NOT EXISTS idx_budget_category_composite 
ON budget_category(category_id, budget_id);

-- Index for active budgets (frequently queried)
-- Example query: SELECT * FROM budget WHERE user_id = ? AND is_active = true AND deleted_at IS NULL
CREATE INDEX IF NOT EXISTS idx_budget_active 
ON budget(user_id, is_active) 
WHERE deleted_at IS NULL AND is_active = true;

-- ============================================================================
-- Recurring Transaction Indexes
-- ============================================================================

-- Index for recurring transaction sync queries
-- Example query: SELECT * FROM recurring_transaction WHERE user_id = ? AND is_active = true AND next_occurrence_date <= NOW()
CREATE INDEX IF NOT EXISTS idx_recurring_tx_user_active 
ON recurring_transaction(user_id, is_active, next_occurrence_date) 
WHERE deleted_at IS NULL AND is_active = true;

-- ============================================================================
-- Invoice Indexes
-- ============================================================================

-- Index for invoice history (user's invoices ordered by date)
-- Example query: SELECT * FROM invoice WHERE user_id = ? AND deleted_at IS NULL ORDER BY created_at DESC
CREATE INDEX IF NOT EXISTS idx_invoice_user_created 
ON invoice(user_id, created_at DESC) 
WHERE deleted_at IS NULL;

-- ============================================================================
-- Account Indexes
-- ============================================================================

-- Index for active accounts (frequently accessed)
-- Example query: SELECT * FROM account WHERE user_id = ? AND deleted_at IS NULL
CREATE INDEX IF NOT EXISTS idx_account_user_active 
ON account(user_id) 
WHERE deleted_at IS NULL;

-- Index for favorite account lookup
-- Example query: SELECT * FROM account WHERE user_id = ? AND is_favorite = true AND deleted_at IS NULL
CREATE INDEX IF NOT EXISTS idx_account_favorite 
ON account(user_id, is_favorite) 
WHERE deleted_at IS NULL AND is_favorite = true;

-- ============================================================================
-- Performance Notes
-- ============================================================================

-- Partial indexes (WHERE deleted_at IS NULL) are more efficient than full indexes
-- because they only index active records, reducing index size and maintenance cost.

-- Composite indexes are ordered by selectivity: most selective column first
-- Example: (user_id, date) is better than (date, user_id) for user-scoped queries

-- Descending indexes (DESC) are used for ORDER BY ... DESC queries
-- PostgreSQL can scan indexes in either direction, but DESC is more explicit
```

### Apply Migration

```bash
# Apply to local database
supabase db reset  # This will replay ALL migrations including the new one

# Or apply just the new migration:
supabase migration up

# Verify indexes were created
supabase db reset
psql $DATABASE_URL -c "\di"  # List all indexes
```

### Verify Index Usage

```sql
-- Check if index is being used (example query)
EXPLAIN ANALYZE 
SELECT * FROM transaction 
WHERE user_id = 'some-user-id' 
  AND date BETWEEN '2025-01-01' AND '2025-12-31' 
  AND deleted_at IS NULL 
ORDER BY date DESC;

-- Look for output like:
-- Index Scan using idx_transaction_user_date_range on transaction  (cost=0.29..8.31 rows=1 width=...)
--                                                                    ^^^^^^^^^ Index is being used ✅
```

---

## Testing All Changes

### Local Testing

```bash
# 1. Start local Supabase
supabase db start

# 2. Apply migrations
supabase db reset

# 3. Start backend
uv run uvicorn backend.main:app --reload

# 4. Run tests
uv run pytest tests/ -v

# 5. Manual API test
curl -X GET http://localhost:8000/transactions \
  -H "Authorization: Bearer $TOKEN" \
  -H "Accept-Encoding: gzip" \
  -w "\nTime: %{time_total}s\n"

# Before optimizations: Time: ~0.5-0.7s
# After optimizations: Time: ~0.2-0.3s ✅
```

### Load Testing (Optional)

```bash
# Install Apache Bench
brew install apache2  # macOS
# or apt install apache2-utils  # Linux

# Test endpoint performance
ab -n 1000 -c 10 -H "Authorization: Bearer $TOKEN" \
   http://localhost:8000/transactions

# Look for:
# - Requests per second (should increase ✅)
# - Time per request (should decrease ✅)
# - Failed requests (should be 0 ✅)
```

---

## Deployment

### Staging Deployment

```bash
# 1. Commit changes
git add .
git commit -m "feat: add Phase 1 performance optimizations

- Increase JWKS cache TTL to 1 hour
- Enable Gzip compression for responses
- Add database indexes for common queries

Estimated impact: 20-30% performance improvement"

# 2. Push to staging branch
git push origin feature/performance-phase1

# 3. Migrations will auto-apply via GitHub Actions
# Monitor: https://github.com/Kashi-Finance/backend/actions

# 4. Verify staging deployment
curl -X GET https://kashi-backend-staging-xxx.run.app/health \
  -w "\nTime: %{time_total}s\n"
```

### Production Deployment

```bash
# 1. Merge to main after staging verification
git checkout main
git merge feature/performance-phase1

# 2. Tag release
git tag -a v0.2.0 -m "Release v0.2.0 - Performance Phase 1"
git push origin main --tags

# 3. Monitor production deployment
# GitHub Actions will deploy automatically

# 4. Verify production
curl -X GET https://kashi-backend-xxx.run.app/health \
  -w "\nTime: %{time_total}s\n"
```

---

## Monitoring Results

### Metrics to Track (First 24 Hours)

```bash
# 1. API Response Times (Cloud Run Console)
# - Go to: Cloud Run → kashi-backend → Metrics
# - Check: Request latency (should decrease 20-30% ✅)

# 2. Database Query Performance (Supabase Dashboard)
# - Go to: Supabase → Database → Performance
# - Check: Slow queries (should decrease ✅)

# 3. Cache Hit Rate (Application Logs)
grep "JWKS" logs/*.log | grep -c "cache hit"
grep "JWKS" logs/*.log | grep -c "cache miss"
# Hit rate should be >90% ✅

# 4. Response Size (Network Tab in Browser)
# - Open Chrome DevTools → Network
# - Check: Size column for /transactions endpoint
# - Should show "xxx B / yyy kB" (compressed / original) ✅
```

### Expected Improvements

| Metric | Before | After | Change |
|--------|--------|-------|--------|
| API Response Time (p95) | 500-700ms | 350-500ms | **30% faster** ✅ |
| JWKS Fetches (per hour) | 12 | 1 | **92% reduction** ✅ |
| Response Size (avg) | 15 KB | 5 KB | **67% smaller** ✅ |
| Query Speed (indexed) | 100-200ms | 10-30ms | **10x faster** ✅ |

---

## Troubleshooting

### Issue: Gzip Not Working

**Symptoms:** Response size unchanged

**Check:**
```bash
curl -I http://localhost:8000/transactions -H "Accept-Encoding: gzip"
```

**Solution:**
- Ensure `Accept-Encoding: gzip` header is sent
- Check minimum_size is appropriate (1000 bytes)
- Verify middleware is added BEFORE route registration

### Issue: Indexes Not Used

**Symptoms:** Queries still slow

**Check:**
```sql
EXPLAIN ANALYZE SELECT * FROM transaction WHERE user_id = '...' ORDER BY date DESC;
```

**Solution:**
- Run `ANALYZE transaction;` to update statistics
- Verify WHERE clause matches index conditions
- Check deleted_at IS NULL is in query (partial index)

### Issue: JWKS Cache Not Working

**Symptoms:** Still fetching JWKS frequently

**Check Application Logs:**
```bash
grep "Initializing JWKS client" logs/*.log
# Should only appear once per app restart
```

**Solution:**
- Verify cache_jwk_set_ttl is set
- Check PyJWT version (should be >=2.10.1)
- Restart application to clear old client instance

---

## Rollback Plan

If any issues occur in production:

### Rollback Code Changes

```bash
# Revert to previous version
git revert HEAD
git push origin main

# Or force rollback to specific tag
git reset --hard v0.1.9
git push origin main --force
```

### Rollback Migrations

```bash
# Migrations are additive (only adding indexes)
# Rollback is safe - just drop indexes:

supabase db execute "DROP INDEX IF EXISTS idx_transaction_user_date_range;"
supabase db execute "DROP INDEX IF EXISTS idx_transaction_account_date;"
# ... (drop all created indexes)
```

**Note:** Dropping indexes is safe - it only affects performance, not data.

---

## Next Steps

After Phase 1 is deployed and verified:

1. ✅ Monitor metrics for 2-3 days
2. ✅ Document actual performance improvements
3. ✅ Plan Phase 2: Redis Caching (see PERFORMANCE-OPTIMIZATION-RECOMMENDATIONS.md)
4. ✅ Schedule team review for next optimizations

---

## Summary Checklist

- [ ] JWKS cache TTL increased to 1 hour
- [ ] Gzip compression enabled
- [ ] Database indexes created and verified
- [ ] All tests passing
- [ ] Changes committed with descriptive message
- [ ] Deployed to staging
- [ ] Verified on staging (performance improved)
- [ ] Deployed to production
- [ ] Monitoring metrics tracking improvements
- [ ] Team notified of changes

**Completion Time:** ~1 day  
**Expected Result:** 20-30% performance improvement ✅

---

**Questions?** Refer to PERFORMANCE-OPTIMIZATION-RECOMMENDATIONS.md for detailed technical explanations.
