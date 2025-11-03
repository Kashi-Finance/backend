# Invoice OCR Endpoint Implementation

This document describes the implementation of the `POST /invoices/ocr` endpoint.

## Overview

The endpoint allows mobile clients to upload receipt images and receive structured invoice data extracted via InvoiceAgent. This is a **preview-only** endpoint - it does NOT persist data to the database.

## Architecture

### Modular Structure

The implementation follows a clean, modular architecture:

```
backend/
├── agents/
│   └── invoice/          # Modular InvoiceAgent
│       ├── __init__.py   # Package exports
│       ├── agent.py      # Main runner function
│       ├── types.py      # TypedDict definitions
│       ├── tools.py      # Backend tool implementations
│       ├── schemas.py    # JSON schemas for validation
│       └── prompts.py    # System prompts
├── routes/
│   └── invoices.py       # FastAPI router with /invoices/ocr endpoint
├── schemas/
│   └── invoices.py       # Pydantic request/response models
├── auth/
│   └── dependencies.py   # Supabase Auth verification
└── main.py               # FastAPI app instance

```

### 6-Step Endpoint Flow

Every endpoint follows this strict pattern:

1. **Auth** - Verify Supabase Bearer token, extract `user_id`
2. **Parse/Validate** - Validate request with Pydantic models
3. **Domain Filter** - Check if request is in-scope before calling agent
4. **Call ONE Agent** - Invoke InvoiceAgent with validated inputs
5. **Map Output** - Convert agent output to Pydantic response model
6. **Persistence** - (None for this endpoint - it's preview only)

## API Specification

### Request

```http
POST /invoices/ocr
Authorization: Bearer <access_token>
Content-Type: multipart/form-data

image: <binary file>
```

**Requirements:**
- Image file (JPEG, PNG, etc.)
- Max file size: 10MB
- Valid Supabase Auth token in Authorization header

### Response (Success - DRAFT)

```json
{
  "status": "DRAFT",
  "store_name": "Super Despensa Familiar Zona 11",
  "purchase_datetime": "2025-11-02T14:30:00-06:00",
  "total_amount": 142.50,
  "currency": "GTQ",
  "items": [
    {
      "description": "Arroz Blanco 1kg",
      "quantity": 2.0,
      "unit_price": 8.50,
      "total_price": 17.00
    }
  ],
  "category_suggestion": {
    "match_type": "EXISTING",
    "category_id": "cat-supermercado-uuid",
    "category_name": "Supermercado"
  }
}
```

### Response (Failure - INVALID_IMAGE)

```json
{
  "status": "INVALID_IMAGE",
  "reason": "No pude leer datos suficientes para construir la transacción. Intenta otra foto donde se vea el total y el nombre del comercio."
}
```

### Error Responses

**401 Unauthorized** - Missing or invalid token
```json
{
  "detail": {
    "error": "unauthorized",
    "details": "Missing Authorization header"
  }
}
```

**400 Bad Request** - Invalid file type
```json
{
  "detail": {
    "error": "invalid_file_type",
    "details": "File must be an image (JPEG, PNG, etc.)"
  }
}
```

**400 Bad Request** - File too large
```json
{
  "detail": {
    "error": "file_too_large",
    "details": "Image must be smaller than 10MB"
  }
}
```

## Testing

### Running Tests

```bash
pytest tests/routes/test_invoices.py -v
```

### Test Coverage

The test suite includes:

1. **Happy Path**: Valid image with auth → DRAFT response
2. **Auth Failure**: Missing token → 401
3. **Invalid File Type**: Non-image file → 400
4. **File Too Large**: > 10MB file → 400
5. **Invalid Image**: Unreadable image → INVALID_IMAGE response
6. **No Persistence**: Endpoint does not write to database
7. **Schema Validation**: Pydantic models validate correctly

All tests use mocked dependencies:
- `verify_token` - Returns test `user_id`
- `run_invoice_agent` - Returns mock DRAFT or INVALID_IMAGE response

## Running the Server

### Start Development Server

```bash
python demo_endpoint.py
```

This starts the server on `http://localhost:8000` with:
- Auto-reload enabled
- API docs at `/docs`
- ReDoc at `/redoc`
- Health check at `/health`

### Test with Interactive Docs

Visit `http://localhost:8000/docs` and use the built-in Swagger UI.

## Security

### Authentication

- All requests MUST include valid Supabase Auth token
- Token is verified before ANY processing
- `user_id` is extracted from token (NEVER from request body)
- Tokens are checked for signature validity and expiration

### Data Privacy

- Endpoint does NOT log sensitive data:
  - Full invoice images
  - Extracted invoice text
  - Personal financial amounts
- High-level events only (e.g., "OCR succeeded for store X")

### Input Validation

- File type checking (must be image/*)
- File size limits (max 10MB)
- Domain filtering (rejects non-invoice tasks)

## Next Steps

### Required for Production

2. **Upload images to Supabase Storage** - Generate real `receipt_id` references
3. **Fetch user profile** - Get real `country` and `currency_preference` from DB
4. **Integrate real Gemini API** - Replace mock InvoiceAgent runner
5. **Implement `/invoices/commit`** - Endpoint to persist draft to DB

### Tagged TODOs in Code

Search for these patterns:
- `TODO(auth-team):` - Supabase Auth integration needed
- `TODO(storage-team):` - Image storage integration needed
- `TODO(db-team):` - Database persistence needed

### Created

- `backend/agents/invoice/` - Modular InvoiceAgent package
  - `agent.py` - Main runner
  - `types.py` - Type definitions
  - `tools.py` - Backend tools
  - `schemas.py` - JSON schemas
  - `prompts.py` - System prompts
  - `__init__.py` - Package exports
- `backend/routes/invoices.py` - Invoice routes
- `backend/schemas/invoices.py` - Pydantic schemas
- `backend/auth/dependencies.py` - Auth helpers
- `backend/main.py` - FastAPI app
- `tests/routes/test_invoices.py` - Comprehensive tests
- `demo_endpoint.py` - Demo server script

### Updated

- `backend/agents/__init__.py` - Import from modular structure