# Invoice Endpoints

> **OCR workflow, receipt processing, and invoice management**

## Table of Contents

1. [Endpoint Reference](#endpoint-reference)
2. [Invoice Workflow Overview](#invoice-workflow-overview)
3. [Immutability Rule](#immutability-rule)
4. [POST /invoices/ocr](#post-invoicesocr)
5. [POST /invoices/commit](#post-invoicescommit)
6. [GET /invoices](#get-invoices)
7. [GET /invoices/{id}](#get-invoicesid)
8. [DELETE /invoices/{id}](#delete-invoicesid)
9. [Integration Notes](#integration-notes)

---

## Endpoint Reference

| Method | Path | Description |
|--------|------|-------------|
| POST | `/invoices/ocr` | Preview extraction from receipt image |
| POST | `/invoices/commit` | Persist invoice + create transaction |
| GET | `/invoices` | List user's invoices |
| GET | `/invoices/{id}` | Get invoice details |
| DELETE | `/invoices/{id}` | Soft-delete invoice |

---

## Invoice Workflow Overview

```
User takes photo
       │
       ▼
POST /invoices/ocr ──────────► INVALID_IMAGE → Show error, retry
       │
       ▼ DRAFT
User previews extraction
User selects account_id, category_id
       │
       ▼
POST /invoices/commit
       │
       ├─► Invoice saved to DB
       ├─► Image uploaded to Storage
       └─► Transaction created automatically
```

**Key Points:**
- `/ocr` is preview-only (no persistence)
- Image is NOT stored until `/commit`
- Frontend must keep image in memory between calls
- `/commit` creates BOTH invoice AND transaction atomically

---

## Immutability Rule

**⚠️ CRITICAL: Invoices cannot be updated after commit**

- Only two operations permitted: **view** and **delete**
- To correct invoice data: delete + create new
- Enforces data integrity and audit trail

---

## POST /invoices/ocr

**Purpose:** Accept receipt image and return preview/draft extraction.

**Request:** 
- Content-Type: `multipart/form-data`
- Field: `image` (binary, max 5MB)

**Response Types:**

### DRAFT (Success)

```json
{
  "status": "DRAFT",
  "store_name": "Super Despensa Familiar Zona 11",
  "transaction_time": "2025-10-30T14:32:00-06:00",
  "total_amount": 128.50,
  "currency": "GTQ",
  "items": [
    {"description": "Leche 1L", "quantity": 2, "total_price": 35.00},
    {"description": "Pan molde", "quantity": 1, "total_price": 22.50}
  ],
  "category_suggestion": {
    "match_type": "EXISTING",
    "category_id": "uuid-de-supermercado",
    "category_name": "Supermercado",
    "proposed_name": null
  }
}
```

### INVALID_IMAGE (Cannot extract)

```json
{
  "status": "INVALID_IMAGE",
  "reason": "No pude leer datos suficientes para construir la transacción..."
}
```

### Category Suggestion Schema

**All 4 fields always present:**

| Field | EXISTING | NEW_PROPOSED |
|-------|----------|--------------|
| `match_type` | "EXISTING" | "NEW_PROPOSED" |
| `category_id` | UUID | null |
| `category_name` | string | null |
| `proposed_name` | null | string |

**Frontend Actions:**
- `EXISTING`: Preselect category in dropdown
- `NEW_PROPOSED`: Select "General", optionally prompt to create new

**Important:**
- Image is NOT uploaded during this phase
- Image is NOT persisted anywhere
- No `invoice` or `transaction` rows created
- Frontend must retain image for commit

**Status Codes:** 200, 400, 401, 500

---

## POST /invoices/commit

**Purpose:** Persist invoice, upload image, and create linked transaction.

**Request Body:**
```json
{
  "store_name": "Super Despensa Familiar",
  "transaction_time": "2025-10-30T14:32:00-06:00",
  "total_amount": 128.50,
  "currency": "GTQ",
  "purchased_items": "- Leche 1L (2x) @ Q12.50 = Q25.00\n- Pan molde @ Q15.00 = Q15.00",
  "image_base64": "/9j/4AAQSkZJRgABAQEAYABgAAD...",
  "image_filename": "receipt_20251030.jpg",
  "account_id": "uuid",
  "category_id": "uuid"
}
```

**Required Fields:**
- `store_name` (string)
- `total_amount` (numeric, > 0)
- `currency` (string, 3 chars)
- `image_base64` (string, base64 encoded)
- `account_id` (UUID)
- `category_id` (UUID)

**Behavior:**
1. Validate required fields
2. Upload image to Supabase Storage
3. Format canonical `extracted_text`
4. Insert `invoice` row
5. Create linked `transaction`:
   - `flow_type`: "outcome" (invoices are always expenses)
   - `amount`: invoice total_amount
   - `date`: invoice transaction_time
   - `description`: invoice store_name
   - `invoice_id`: created invoice ID

**Response (201):**
```json
{
  "status": "COMMITTED",
  "invoice_id": "uuid",
  "transaction_id": "uuid",
  "message": "Invoice and transaction saved successfully"
}
```

**Important:**
- Image uploaded ONLY at this stage
- Both `invoice` and `transaction` created atomically
- Cannot be updated after this point

**Status Codes:** 201, 400, 401, 500

---

## GET /invoices

**Purpose:** List user's invoices (paginated).

**Query Parameters:**
| Param | Type | Default | Description |
|-------|------|---------|-------------|
| `limit` | int | 50 | Max 100 |
| `offset` | int | 0 | Pagination offset |

**Response:**
```json
{
  "invoices": [
    {
      "id": "uuid",
      "user_id": "uuid",
      "storage_path": "invoices/<user_id>/<uuid>.jpg",
      "extracted_text": "Store Name: ...\nTransaction Time: ...",
      "created_at": "2025-11-03T10:15:00Z",
      "updated_at": "2025-11-03T10:15:00Z"
    }
  ],
  "count": 1,
  "limit": 50,
  "offset": 0
}
```

**Status Codes:** 200, 401, 500

---

## GET /invoices/{id}

**Purpose:** Retrieve single invoice details.

**Response:**
```json
{
  "id": "uuid",
  "user_id": "uuid",
  "storage_path": "invoices/<user_id>/<uuid>.jpg",
  "extracted_text": "Store Name: Super Despensa\nTransaction Time: 2025-10-30T14:32:00-06:00\nTotal Amount: 128.50\nCurrency: GTQ\nPurchased Items:\n- Leche 1L (2x) @ Q12.50 = Q25.00\nReceipt Image ID: invoices/<user_id>/<uuid>.jpg",
  "created_at": "2025-11-03T10:15:00Z",
  "updated_at": "2025-11-03T10:15:00Z"
}
```

**Status Codes:** 200, 401, 404, 500

---

## DELETE /invoices/{id}

**Purpose:** Soft-delete an invoice.

**Behavior:**
- Calls `delete_invoice(p_invoice_id, p_user_id)` RPC
- Sets `deleted_at` timestamp
- Soft-deleted invoices hidden via RLS filter
- Does **NOT** delete receipt image from Storage
- Does **NOT** modify linked transaction

**Response:**
```json
{
  "status": "DELETED",
  "invoice_id": "uuid",
  "deleted_at": "2025-11-16T10:30:00-06:00",
  "message": "Invoice soft-deleted successfully"
}
```

**Notes:**
- Transaction remains intact after invoice deletion
- Use `DELETE /transactions/{id}` separately if needed
- Storage cleanup is separate concern

**Status Codes:** 200, 401, 404, 500

---

## Integration Notes

### Invoice → Transaction Link

```
Invoice Creation:
  POST /invoices/commit
       │
       └─► Creates transaction with:
           ├─ flow_type: "outcome"
           ├─ invoice_id: <new_invoice_id>
           ├─ category_id: <from_request>
           └─ account_id: <from_request>
```

### Canonical extracted_text Format

```
Store Name: <store_name>
Transaction Time: <ISO-8601>
Total Amount: <amount>
Currency: <currency>
Purchased Items:
<items_text>
Receipt Image ID: <storage_path>
```

### User Correction Workflow

```
User notices error
       │
       ▼
DELETE /invoices/{id}  ──► Invoice soft-deleted
       │
       ▼
(Optionally) DELETE /transactions/{id}
       │
       ▼
POST /invoices/ocr     ──► New photo
       │
       ▼
POST /invoices/commit  ──► New invoice + transaction
```

### InvoiceAgent

- Gemini-based multimodal vision
- Extracts: store, time, total, currency, items
- Suggests category (EXISTING or NEW_PROPOSED)
- Rejects non-receipt images
