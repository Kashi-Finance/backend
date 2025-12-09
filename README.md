# Kashi Finances Backend

FastAPI backend service for orchestrating adk agents built on Google ADK.

## Project Structure

```
backend/
├── main.py              # FastAPI app entrypoint
├── routes/              # HTTP endpoints (APIRouter modules)
│   ├── health.py        # Public health check endpoint
│   └── ...              # Future: invoices, recommendations, etc.
├── schemas/             # Pydantic RequestModel and ResponseModel classes
│   ├── health.py        # Health check schemas
│   └── ...              # Future: invoice, recommendation schemas
├── auth/                # Supabase Auth verification
│   └── auth.py          # verify_supabase_token() function
├── agents/              # adk agents (Google ADK)
│   └── ...              # Future: InvoiceAgent, RecommendationCoordinatorAgent, etc.
├── services/            # Business logic orchestration
│   └── ...              # Future: invoice_service, recommendation_service
├── utils/               # Common utilities
│   └── logging.py       # get_logger() helper
└── db/                  # Database access layer (governed by db.instructions.md)
    └── ...              # Future: Supabase client, RLS-compliant queries
```

## Testing

### Unit Tests (Default)

```bash
pytest tests/
```

All tests use mocks by default. Safe for CI/CD. Fast (~2-5 seconds).

### Integration Tests

```bash
# 1. Navigate to backend directory
cd /Users/andres/Documents/Kashi/backend

# 2. Setup environment variables
source scripts/integration/setup-env.sh

# 3. Start backend server in a separate terminal
./scripts/integration/START-BACKEND.sh

# 4. Create/renew test user (updates .env with fresh token)
./scripts/integration/00-create-test-user.sh

# 5. Run all tests
./scripts/integration/run-all.sh

# Or run individual test:
source scripts/integration/setup-env.sh
./scripts/integration/11-profile-get.sh
```

## Flujo 
Dev trabaja en feature/cualquier-cosa.
Hace push a esa rama.
Abre PR → develop.
develop se usa como staging (deploy automático).
Cuando ya está probado en staging, se abre PR de develop → main.
main dispara el pipeline de prod.


**Deployment Command:**
```bash
gcloud run deploy kashi-backend-staging \
  --source . \
  --region=us-central1 \
  --allow-unauthenticated
```


## Database Migrations

```bash
supabase login
supabase link --project-ref gzdwagvbbykzwwdesuac
supabase db push
```