# Auth & Profile Endpoints

> **User authentication, session management, and profile CRUD**

## Table of Contents

1. [Endpoint Reference](#endpoint-reference)
2. [GET /auth/me](#get-authme)
3. [GET /profile](#get-profile)
4. [POST /profile](#post-profile)
5. [PATCH /profile](#patch-profile)
6. [DELETE /profile](#delete-profile)
7. [Integration Notes](#integration-notes)

---

## Endpoint Reference

| Method | Path | Description |
|--------|------|-------------|
| GET | `/auth/me` | Get authenticated user's identity |
| GET | `/profile` | Get user's profile |
| POST | `/profile` | Create user's profile |
| PATCH | `/profile` | Update user's profile |
| DELETE | `/profile` | Anonymize user's profile (soft-delete) |

---

## GET /auth/me

**Purpose:** Return the authenticated user's core identity for the session.

**Request:**
- Header: `Authorization: Bearer <access_token>`
- Body: None

**Backend Flow:**
1. Validate token
2. Extract `user_id`
3. Query `profile` table by `user_id`

**Response:**
```json
{
  "user_id": "38f7d540-23fa-497a-8df2-3ab9cbe13da5",
  "email": "user@example.com",
  "profile": {
    "first_name": "Samuel",
    "last_name": "Marroquín",
    "avatar_url": "https://storage.kashi.app/avatars/u1.png",
    "country": "GT",
    "currency_preference": "GTQ",
    "locale": "es"
  }
}
```

**Use in Frontend:**
- Call on app boot to hydrate global session state
- Confirms token is still valid

---

## GET /profile

**Purpose:** Retrieve the authenticated user's profile.

**Request:** No body. Authorization required.

**Response:**
```json
{
  "user_id": "38f7d540-23fa-497a-8df2-3ab9cbe13da5",
  "first_name": "Samuel",
  "last_name": "Marroquín",
  "avatar_url": "https://storage.kashi.app/avatars/u1.png",
  "currency_preference": "GTQ",
  "locale": "es",
  "country": "GT",
  "created_at": "2025-10-31T12:00:00-06:00",
  "updated_at": "2025-10-31T12:00:00-06:00"
}
```

**Status Codes:**
| Code | Description |
|------|-------------|
| 200 | Profile retrieved |
| 401 | Missing/invalid token |
| 404 | Profile not found |
| 500 | Database error |

---

## POST /profile

**Purpose:** Create a profile for the authenticated user.

**Request Body:**
```json
{
  "first_name": "Andres",
  "last_name": "Gonzalez",
  "avatar_url": "https://storage.kashi.app/avatars/andres.png",
  "currency_preference": "GTQ",
  "locale": "system",
  "country": "GT"
}
```

**Required Fields:**
- `first_name` (string)
- `currency_preference` (string, ISO currency code)
- `country` (string, ISO-2 code)

**Behavior:**
- `user_id` derived from bearer token (client MUST NOT provide it)
- RLS enforces profile created for authenticated user only

**Response (201 Created):**
```json
{
  "user_id": "e3a6e0f1-625f-4f4f-a142-1aba8633a601",
  "first_name": "Andres",
  "last_name": "Gonzalez",
  "avatar_url": "https://storage.kashi.app/avatars/andres.png",
  "currency_preference": "GTQ",
  "locale": "system",
  "country": "GT",
  "created_at": "2025-11-07T04:44:16.022189+00:00",
  "updated_at": "2025-11-07T04:44:16.022189+00:00"
}
```

**Status Codes:**
| Code | Description |
|------|-------------|
| 201 | Profile created |
| 400 | Invalid request (missing required fields) |
| 401 | Missing/invalid token |
| 409 | Profile already exists |
| 500 | Database error |

---

## PATCH /profile

**Purpose:** Update the authenticated user's profile.

**Request Body (all optional, at least one required):**
```json
{
  "first_name": "Samuel",
  "last_name": "Marroquín",
  "avatar_url": "https://storage.kashi.app/avatars/new-avatar.png",
  "currency_preference": "USD",
  "locale": "es",
  "country": "GT"
}
```

**Response:**
```json
{
  "status": "UPDATED",
  "profile": {
    "user_id": "38f7d540-23fa-497a-8df2-3ab9cbe13da5",
    "first_name": "Samuel",
    "last_name": "Marroquín",
    "avatar_url": "https://storage.kashi.app/avatars/new-avatar.png",
    "currency_preference": "USD",
    "locale": "es-GT",
    "country": "GT",
    "created_at": "2025-10-31T12:00:00-06:00",
    "updated_at": "2025-11-05T10:30:00-06:00"
  },
  "message": "Profile updated successfully"
}
```

**Status Codes:**
| Code | Description |
|------|-------------|
| 200 | Profile updated |
| 400 | Invalid request or no fields provided |
| 401 | Missing/invalid token |
| 404 | Profile not found |
| 500 | Database error |

**Notes:**
- `country` is used by agents for localized recommendations
- `currency_preference` sets default currency for financial data

---

## DELETE /profile

**Purpose:** Delete (anonymize) the authenticated user's profile.

**Request:** No body. Authorization required.

**Behavior:**
- Profile is **NOT** physically deleted
- Personal fields are cleared/anonymized:
  - `first_name` → "Deleted User"
  - `last_name` → null
  - `avatar_url` → null
- `country` and `currency_preference` are **kept** for system consistency
- Row remains for localization data used by agents

**Response:**
```json
{
  "status": "DELETED",
  "message": "Profile deleted successfully"
}
```

**Status Codes:**
| Code | Description |
|------|-------------|
| 200 | Profile anonymized |
| 401 | Missing/invalid token |
| 404 | Profile not found |
| 500 | Database error |

**Important:** This is an anonymization operation, not true deletion. Profile remains while user exists in `auth_users`.

---

## Integration Notes

### Profile Data Usage

- **RecommendationCoordinatorAgent**: Uses `country` and `currency_preference` for localized searches
- **InvoiceAgent**: Uses profile context for category suggestions
- **All endpoints**: Profile establishes user's localization context

### Session Hydration Flow

```
App Boot
    │
    ├─► Read token from secure storage
    │
    ├─► GET /auth/me
    │       │
    │       ├─► 200 OK → Hydrate session
    │       │
    │       └─► 401 → Force re-login
    │
    └─► Ready for authenticated requests
```

### RLS Enforcement

- Profile protected by `user_id = auth.uid()`
- Users can only access their own profile
- Backend ignores any `user_id` in request body
