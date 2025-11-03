# Supabase Authentication Setup Guide

This guide explains how to configure and use Supabase Authentication in the Kashi Finances backend.

## Overview

The backend uses **Supabase Auth** with **JWT Signing Keys (ES256)** to authenticate all protected API endpoints. This ensures that:

1. Only authenticated users can access their own financial data
2. Row Level Security (RLS) in the database enforces `user_id = auth.uid()` on all queries
3. The backend never trusts client-provided `user_id` values - only the verified token
4. Uses ECC (P-256) asymmetric cryptography for enhanced security

## Architecture

```
Mobile App → Bearer Token (ES256) → FastAPI verify_token() → JWKS Fetch → Public Key Verification → Extract user_id → Protected Route
                                                              ↓
                                                    Supabase JWKS Endpoint
                                                    (public keys only)
```

## What's New: JWT Signing Keys

**The legacy JWT Secret (HS256) is deprecated.** This backend now uses Supabase's new **JWT Signing Keys system**:

- **Algorithm:** ES256 (ECC P-256) instead of HS256 (HMAC)
- **Keys:** Asymmetric (public/private) instead of symmetric (shared secret)
- **Verification:** JWKS endpoint (`/.well-known/jwks.json`) instead of hardcoded secret
- **Security:** Private keys never leave Supabase, backend only has public keys
- **Rotation:** Zero-downtime key rotation supported

### Benefits
✅ No shared secrets to leak or manage  
✅ Better performance (public key verification)  
✅ Automatic key rotation without downtime  
✅ Full audit trails in Supabase  
✅ SOC2/PCI-DSS/ISO27001 compliance  


## How Token Verification Works

### Flow

1. **Client sends request** with `Authorization: Bearer <token>` header
2. **FastAPI dependency** (`verify_token()`) extracts the token
3. **JWKS client** fetches public keys from `https://<project>.supabase.co/auth/v1/.well-known/jwks.json`
   - **Cached** for 5 minutes to avoid repeated network calls
   - **Automatic refresh** when keys are rotated
4. **PyJWT verifies** using the public key matching the token's `kid` (key ID)
5. **Verification checks**:
   - Signature is valid (ES256 algorithm with ECC P-256)
   - Token has not expired (`exp` claim)
   - Audience is `authenticated` (`aud` claim)
   - Issuer matches our project URL (`iss` claim)
   - Subject (user ID) exists (`sub` claim)
6. **Extract user_id** from the `sub` (subject) claim
7. **Return user_id** to the route handler
8. **Route handler** uses `user_id` for all DB operations (RLS enforces ownership)

### Token Structure

Supabase ES256 JWT tokens contain these claims:
```json
{
  "alg": "ES256",                      // Algorithm (ECC P-256)
  "kid": "unique-key-id",              // Key ID pointing to JWKS entry
  "typ": "JWT"
}
.
{
  "sub": "user-uuid-here",             // User ID (this is what we extract)
  "aud": "authenticated",              // Audience
  "iss": "https://project.supabase.co/auth/v1", // Issuer
  "exp": 12345678,                     // Expiration timestamp
  "iat": 12345678,                     // Issued at timestamp
  "email": "user@example.com",         // User's email
  "role": "authenticated"              // User's role
}
```

### JWKS Response Example

The backend fetches public keys from the JWKS endpoint:

```json
{
  "keys": [
    {
      "kid": "abc123",
      "alg": "ES256",
      "kty": "EC",
      "key_ops": ["verify"],
      "crv": "P-256",
      "x": "<base64url-x-coordinate>",
      "y": "<base64url-y-coordinate>"
    }
  ]
}
```

**Security:** Only public keys are exposed. Private keys never leave Supabase.

### Error Handling

The `verify_token()` dependency returns these errors:

| Error Code | HTTP Status | Cause |
|------------|-------------|-------|
| `unauthorized` | 401 | Missing `Authorization` header |
| `unauthorized` | 401 | Invalid header format (not `Bearer <token>`) |
| `token_expired` | 401 | Token's `exp` claim is in the past |
| `jwks_error` | 401 | JWKS endpoint unreachable or key not found |
| `invalid_token` | 401 | Invalid signature, malformed JWT, or missing `sub` claim |

## Troubleshooting

### "Missing Authorization header" (401)
**Cause**: Request doesn't include `Authorization` header  
**Fix**: Add header: `Authorization: Bearer <token>`

### "Invalid Authorization header format" (401)
**Cause**: Header is not in `Bearer <token>` format  
**Fix**: Ensure header starts with `Bearer ` (note the space)

### "Authentication token has expired" (401)
**Cause**: Token's `exp` claim is in the past  
**Fix**: Get a fresh token from Supabase Auth

### "Unable to verify token signature" (jwks_error 401)
**Cause**: JWKS endpoint unreachable or token's `kid` not found in JWKS  
**Fix**: 
- Verify `SUPABASE_URL` is correct in `.env`
- Check JWT Signing Keys are enabled in Supabase Dashboard
- Ensure network connectivity to Supabase
- Verify token is from the correct Supabase project
- Check token at jwt.io to inspect `alg` (should be ES256) and `kid` claims

### "Invalid authentication token" (401)
**Cause**: Token signature invalid or token malformed  
**Fix**: 
- Ensure Supabase is issuing ES256 tokens (not legacy HS256)
- Verify token is from the same Supabase project
- Check token hasn't been tampered with
- Decode token at jwt.io to inspect claims

### "Missing required environment variables" (startup warning)
**Cause**: `.env` file is missing or incomplete  
**Fix**: Copy `.env.example` to `.env` and set `SUPABASE_URL`

## Related Documentation

- [Supabase JWT Signing Keys](https://supabase.com/docs/guides/auth/signing-keys)
- [Supabase Auth JWTs](https://supabase.com/docs/guides/auth/jwts)
- [JWT.io - Token Inspector](https://jwt.io) (decode tokens for debugging)
- [PyJWT Documentation](https://pyjwt.readthedocs.io/)
- [PyJWKClient Documentation](https://pyjwt.readthedocs.io/en/stable/usage.html#retrieve-rsa-signing-keys-from-a-jwks-endpoint)
- `backend/auth/dependencies.py` - Token verification implementation
- `backend/config.py` - Configuration management
- `JWT_SIGNING_KEYS_MIGRATION.md` - Migration details and technical reference
- `.github/copilot-instructions.md` - Authentication pipeline rules

