# RLS Database Integration - Implementation Complete

This document summarizes the **Row Level Security (RLS) database integration** implementation for Kashi Finances backend.

## ✅ What Was Implemented

### 1. Authenticated Supabase Client Factory

**File**: `backend/db/client.py`

Created a secure client factory that:
- Creates per-request Supabase clients with user JWT tokens
- Automatically enforces RLS by setting the user's access token
- Uses `SUPABASE_PUBLISHABLE_KEY` (respects RLS, replaces legacy anon key)
- Prevents bypassing RLS for user operations

**Key Function**:
```python
def get_supabase_client(access_token: str) -> Client:
    """
    Create an authenticated Supabase client for a specific user.
    RLS policies automatically enforce user_id = auth.uid().
    """
```

**Security Guarantees**:
- ✅ Every database query is subject to RLS policies
- ✅ Users can ONLY access their own data
- ✅ No way to bypass RLS from application code
- ✅ Service role client is intentionally not implemented (raises NotImplementedError)

---

### 2. Invoice Persistence Service

**File**: `backend/services/invoice_service.py`

Implements invoice persistence following `db.instructions.md`:

**Canonical Format Enforcement**:
```python
EXTRACTED_INVOICE_TEXT_FORMAT = """Store Name: {store_name}
Transaction Time: {transaction_time}
Total Amount: {total_amount}
Currency: {currency}
Purchased Items:
{purchased_items}
NIT: {nit}"""
```

**Key Functions**:
1. `format_extracted_text()` - Formats data into canonical template
2. `create_invoice()` - Persists invoice with RLS enforcement
3. `get_user_invoices()` - Fetches user's invoices (RLS filtered)

**Data Flow**:
```
InvoiceAgent → Structured Data → format_extracted_text() → 
invoice.extracted_text (canonical format) → Supabase (RLS enforced)
```

**Important**: 
- ✅ Invoice data is NOT stored in separate columns
- ✅ All data goes into `extracted_text` following the canonical template
- ✅ "Receipt Image ID" was replaced with "NIT" as specified
- ✅ RLS automatically filters by `user_id = auth.uid()`

---

### 3. User Profile Service

**File**: `backend/services/profile_service.py`

Manages user profile data with RLS:

**Key Functions**:
1. `get_user_profile()` - Fetch user profile (country, currency_preference, etc.)
2. `create_user_profile()` - Create new profile during onboarding
3. `update_user_profile()` - Update profile fields

**Profile Fields**:
- `country` (ISO-2 code, e.g., "GT")
- `currency_preference` (e.g., "GTQ")
- `locale`, `first_name`, `last_name`, `avatar_url`

**RLS Enforcement**:
- ✅ Users can only read/update their own profile
- ✅ Profile is 1:1 with `auth.users`

---

### 4. Enhanced Authentication Dependencies

**File**: `backend/auth/dependencies.py`

Added new dependency for endpoints that need both user_id AND token:

**New Class**:
```python
@dataclass
class AuthenticatedUser:
    user_id: str
    access_token: str
```

**New Dependency**:
```python
async def get_authenticated_user(...) -> AuthenticatedUser:
    """
    Returns both user_id and access_token.
    Use this when you need to create a Supabase client.
    """
```

**Usage Pattern**:
```python
@router.post("/invoices/commit")
async def commit_invoice(
    request: InvoiceCommitRequest,
    auth_user: AuthenticatedUser = Depends(get_authenticated_user)
):
    # Create authenticated client
    supabase_client = get_supabase_client(auth_user.access_token)
    
    # RLS automatically enforces user_id = auth_user.user_id
    invoice = await create_invoice(supabase_client, ...)
```

---

### 5. New Endpoint: POST /invoices/commit

**File**: `backend/routes/invoices.py`

Implemented the invoice commit endpoint:

**Request Schema**:
```python
class InvoiceCommitRequest(BaseModel):
    store_name: str
    transaction_time: str
    total_amount: str
    currency: str
    purchased_items: str
    nit: str
    storage_path: str
```

**Response Schema**:
```python
class InvoiceCommitResponse(BaseModel):
    status: Literal["COMMITTED"]
    invoice_id: str
    message: str
```

**Flow**:
1. Authenticate user via `get_authenticated_user`
2. Validate request data
3. Create authenticated Supabase client
4. Call `create_invoice()` service
5. RLS enforces user_id automatically
6. Return invoice_id

**Security**:
- ✅ Requires valid JWT token
- ✅ User can only create invoices for themselves
- ✅ `extracted_text` follows canonical format
- ✅ RLS policies enforced at database level

---

## Testing Results

### All Tests Passing: 13/13 ✅

**Existing Tests** (8 tests):
- ✅ Invoice OCR endpoint tests
- ✅ Authentication tests
- ✅ Schema validation tests

**New Tests** (5 tests):
```bash
tests/services/test_invoice_service.py
✅ test_format_extracted_text_produces_correct_template
✅ test_format_extracted_text_handles_empty_items
✅ test_create_invoice_formats_and_inserts_correctly
✅ test_create_invoice_raises_on_empty_result
✅ test_get_user_invoices_returns_list
```

**Run All Tests**:
```bash
pytest -v
# Result: 13 passed in 0.49s
```

---

## Architecture Overview

```
┌─────────────────────────────────────────────────────────────┐
│                     HTTP REQUEST                            │
│              Authorization: Bearer <token>                  │
└───────────────────────┬─────────────────────────────────────┘
                        │
                        ▼
┌─────────────────────────────────────────────────────────────┐
│         FastAPI Endpoint (backend/routes/invoices.py)       │
│                                                             │
│  Dependency: get_authenticated_user()                      │
│  → Verifies JWT token (ES256/JWKS)                         │
│  → Returns AuthenticatedUser(user_id, access_token)        │
└───────────────────────┬─────────────────────────────────────┘
                        │
                        ▼
┌─────────────────────────────────────────────────────────────┐
│      Service Layer (backend/services/invoice_service.py)    │
│                                                             │
│  1. Format data into EXTRACTED_INVOICE_TEXT_FORMAT         │
│  2. Create authenticated Supabase client                   │
│     get_supabase_client(access_token)                      │
└───────────────────────┬─────────────────────────────────────┘
                        │
                        ▼
┌─────────────────────────────────────────────────────────────┐
│       Database Layer (backend/db/client.py)                 │
│                                                             │
│  Supabase Client with user JWT token                       │
│  → client.auth.set_session(access_token, access_token)     │
│  → All queries now have auth.uid() context                 │
└───────────────────────┬─────────────────────────────────────┘
                        │
                        ▼
┌─────────────────────────────────────────────────────────────┐
│                    SUPABASE DATABASE                        │
│                                                             │
│  RLS Policy on `invoice` table:                            │
│  ┌────────────────────────────────────────────────────┐   │
│  │ CREATE POLICY "invoice_insert_own"                 │   │
│  │ ON public.invoice FOR INSERT                       │   │
│  │ WITH CHECK (user_id = auth.uid() OR ...)           │   │
│  └────────────────────────────────────────────────────┘   │
│                                                             │
│  Result: User can ONLY insert/read their own invoices     │
└─────────────────────────────────────────────────────────────┘
```

---

## Files Created/Modified

### Created:
- ✅ `backend/db/client.py` - Authenticated Supabase client factory
- ✅ `backend/services/invoice_service.py` - Invoice persistence with canonical format
- ✅ `backend/services/profile_service.py` - User profile management
- ✅ `tests/services/test_invoice_service.py` - Service layer tests
- ✅ `tests/services/__init__.py` - Test package marker
- ✅ `RLS_INTEGRATION_COMPLETE.md` - This document

### Modified:
- ✅ `backend/db/__init__.py` - Export `get_supabase_client`
- ✅ `backend/services/__init__.py` - Export service functions
- ✅ `backend/auth/dependencies.py` - Added `AuthenticatedUser` and `get_authenticated_user()`
- ✅ `backend/routes/invoices.py` - Added `/invoices/commit` endpoint
- ✅ `backend/schemas/invoices.py` - Added commit request/response schemas
- ✅ `SUPABASE_AUTH_IMPLEMENTATION.md` - Updated with RLS completion status
- ✅ `.github/instructions/db.instructions.md` - Updated canonical format (Receipt Image ID → NIT)
- ✅ `DATABASE-DDL.md` - Updated comments to reflect canonical format requirement

---

## How to Use

### 1. Configure Supabase

Ensure your `.env` file has:
```bash
SUPABASE_URL=https://your-project.supabase.co
SUPABASE_PUBLISHABLE_KEY=sb_publishable_your_actual_key_here
```

**Important**: 
- Do NOT use the legacy `SUPABASE_ANON_KEY` (deprecated)
- Do NOT use `service_role`/`secret` key for user operations
- See `.github/instructions/supabase.instructions.md` for details on the new API key system

### 2. Create a User Profile

Before using invoice endpoints, the user must have a profile:
```python
from backend.services import create_user_profile

profile = await create_user_profile(
    supabase_client=client,
    user_id=user_id,
    first_name="John",
    currency_preference="GTQ",
    country="GT"
)
```

### 3. Upload Invoice (OCR Preview)

```bash
curl -X POST http://localhost:8000/invoices/ocr \
  -H "Authorization: Bearer <token>" \
  -F "image=@receipt.jpg"
```

Response:
```json
{
  "status": "DRAFT",
  "store_name": "Super Despensa Familiar",
  "purchase_datetime": "2025-11-02T14:32:00-06:00",
  "total_amount": 128.50,
  "currency": "GTQ",
  "items": [...],
  "category_suggestion": {...}
}
```

### 4. Commit Invoice to Database

```bash
curl -X POST http://localhost:8000/invoices/commit \
  -H "Authorization: Bearer <token>" \
  -H "Content-Type: application/json" \
  -d '{
    "store_name": "Super Despensa Familiar",
    "transaction_time": "2025-11-02T14:32:00-06:00",
    "total_amount": "128.50",
    "currency": "GTQ",
    "purchased_items": "- Leche (2x Q15.50)\n- Pan (1x Q12.00)",
    "nit": "12345678-9",
    "storage_path": "/invoices/user-123/receipt-001.jpg"
  }'
```

Response:
```json
{
  "status": "COMMITTED",
  "invoice_id": "550e8400-e29b-41d4-a716-446655440000",
  "message": "Invoice saved successfully"
}
```

### 5. Verify RLS is Working

Try to access another user's invoice:
```python
# This will return empty list even if other invoices exist
# RLS automatically filters by user_id = auth.uid()
invoices = await get_user_invoices(client, user_id="other-user")
# Result: [] (empty, RLS blocked access)
```

---

## Security Guarantees

### ✅ Row Level Security Enforcement

1. **All database operations are scoped to the authenticated user**
   - User A cannot read User B's invoices
   - User A cannot modify User B's data
   - No way to bypass RLS from application code

2. **Token-based authentication**
   - Every request must have valid JWT token
   - Token is verified using Supabase's JWKS (ES256)
   - Token contains `user_id` in `sub` claim

3. **Client-side user_id is ignored**
   - Even if client sends `user_id` in request body, it's ignored
   - Only source of truth is `auth.uid()` from JWT token
   - Enforced at database level via RLS policies

4. **Service role client is not exposed**
   - `get_service_role_client()` raises `NotImplementedError`
   - All user operations MUST go through RLS
   - Service role should only be used for system tasks (migrations, etc.)

---

## Canonical Format Compliance

The `invoice.extracted_text` field MUST follow this exact format:

```
Store Name: Super Despensa Familiar
Transaction Time: 2025-11-02T14:32:00-06:00
Total Amount: 128.50
Currency: GTQ
Purchased Items:
- Leche deslactosada 1L (2x Q15.50)
- Pan integral (1x Q12.00)
NIT: 12345678-9
```

**Rules**:
- ✅ Exactly this template (no variations)
- ✅ "NIT" (not "Receipt Image ID")
- ✅ All data in `extracted_text` (no separate columns)
- ✅ Enforced by `format_extracted_text()` function
- ✅ Validated in tests

---

## Next Steps

### Recommended:
1. **Integrate User Profile Loading**
   - Update `/invoices/ocr` to fetch user profile
   - Use `country` and `currency_preference` for InvoiceAgent context

2. **Implement Image Storage**
   - Upload receipt images to Supabase Storage
   - Generate `storage_path` before calling `/invoices/commit`

3. **Add GET /invoices Endpoint**
   - List user's invoices with pagination
   - Use `get_user_invoices()` service

4. **Add Embeddings**
   - Generate embeddings for `extracted_text` using `text-embedding-3-small`
   - Enable semantic search over invoices

### Future Enhancements:
- Transaction table integration (link invoices to transactions)
- Category management (create, update, delete categories)
- Budget tracking with invoice data
- Recurring transaction rules
- Wishlist integration

---

## References

- **Database Rules**: `.github/instructions/db.instructions.md`
- **DDL Schema**: `DATABASE-DDL.md`
- **Auth Implementation**: `SUPABASE_AUTH_IMPLEMENTATION.md`
- **API Architecture**: `.github/instructions/api-architecture.instructions.md`
- **Supabase Docs**: https://supabase.com/docs/guides/auth
- **RLS Policies**: https://supabase.com/docs/guides/auth/row-level-security

---
