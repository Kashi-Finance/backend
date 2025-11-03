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

## Flujo 
Dev trabaja en feature/cualquier-cosa.
Hace push a esa rama.
Abre PR → develop.
develop se usa como staging (deploy automático).
Cuando ya está probado en staging, se abre PR de develop → main.
main dispara el pipeline de prod.