"""
Service layer for Kashi Finances Backend.

Contains business logic orchestration that:
- Adapts endpoint requests to adk agent calls
- Enforces domain filtering and scope checking before calling agents
- Maps agent outputs into Pydantic ResponseModels
- Handles persistence coordination (calling DB layer under RLS)

Services act as the glue between routes (HTTP layer) and agents/database.

TODO: Add service modules as features are implemented (invoice_service.py, 
      recommendation_service.py, etc.)
"""
