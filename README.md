# Kashi Finances — Backend

A production-oriented backend service that orchestrates domain logic, database access, and AI-driven agents for an intelligent personal finance platform. The project focuses on secure data handling, robust API design, and integration with AI agent frameworks and Supabase (Postgres) to provide features such as semantic search, invoice OCR processing, recommendations, budgets, and advanced transaction workflows.

---

## Purpose & Functionality

Kashi Finances Backend provides:
- A FastAPI-based HTTP API surface for client apps and AI agents.
- Orchestration for domain-specific AI agents (e.g., invoice processing, recommendations) built around Google ADK-style agent components.
- Strong integration with Supabase (Postgres) for persistence, security (RLS), and storage for assets (e.g., invoice images).
- Domain services that encapsulate business logic for accounts, transactions, invoices, budgets, and recommendations.
- Support for semantic search via pgvector embeddings (for product search / semantic invoice matching).
- CI-driven deployment patterns that align database migrations with staging/production flows.

The service is engineered to be the backend core of a modern, AI-enabled personal finance product: handling ingestion (OCR/receipts), storage, user-level access control, AI-powered suggestions, and domain coordination among agents.

---

## Main Technologies & Frameworks

- Python (type-checked, pyproject-managed)
- FastAPI — API framework and dependency injection
- Pydantic — request and response validation / schema models
- Supabase / PostgreSQL — primary datastore, row-level security, storage buckets
- pgvector — vector embeddings support for semantic search
- Google ADK-style agents (agent orchestration pattern) — AI agent modules for workflows
- Docker — containerization (Dockerfile present)
- CI pipelines (GitHub Actions) — branch-based deployment and migration automation
- Supporting tooling: linters/type checkers (pyright), tests, and performance documentation

---

## Architecture & Core Components

The codebase follows a clear modular layout to separate concerns and enable maintainability:

- backend/main.py
  - FastAPI application entrypoint. Registers routers and middleware and configures app-level dependencies.

- backend/routes/
  - APIRouter modules: exposes domain endpoints (health checks, accounts, transactions, invoices, recommendations, etc.). Routes map HTTP requests to schema-validated handlers.

- backend/schemas/
  - Pydantic models for request/response validation and typed data transfer across layers.

- backend/auth/
  - Supabase authentication and token verification utilities used by route dependencies and middleware.

- backend/services/
  - Business logic layer: orchestrates domain rules, coordinates agents, composes DB operations, and implements features independent from transport.

- backend/db/
  - Database access layer and SQL/migration guidance (RLS-aware). Implements patterns for safe schema changes and query encapsulation.

- backend/agents/
  - AI agent definitions and orchestrators (e.g., invoice processing agent, recommendation coordinator). These modules implement workflows that combine AI capabilities with deterministic business logic.

- backend/utils/
  - Shared utilities (logging helpers, common helpers, and ancillary tools).

Cross-cutting documentation:
- docs/ and docs/api/ contain domain API references optimized for AI agent consumption (Anthropic progressive disclosure style).
- Database docs (DB-documentation.md, cached-values.md, rls.md) define the schema, RLS policies, caching strategies, and index recommendations.

---

## Notable Design Patterns & Best Practices

- Layered / modular architecture
  - Clear separation between transport (routes), validation (schemas), application logic (services), persistence (db), and AI orchestration (agents). This enables testability and replaceable implementations.

- Dependency injection via FastAPI
  - Uses FastAPI's DI for components like DB clients, auth verifiers, and configuration—improving testability and runtime configuration.

- Domain-driven service layer
  - Business rules and orchestration live in services to avoid routing logic leakage into controllers.

- Secure-by-design database practices
  - Supabase/Postgres with Row-Level Security (RLS) policies and careful migration processes to maintain multi-tenant and per-user privacy guarantees.

- Pydantic schemas & type checking
  - Strong typing across the stack for input validation and to reduce runtime errors (pyright configs present).

- Agent orchestration pattern
  - AI functionality is encapsulated as agents coordinating smaller tasks, allowing hybrid flows where deterministic logic and LLM/agent reasoning interact safely.

- Semantic search & caching
  - Uses pgvector for embeddings and caching patterns (cached-values.md) to keep expensive computations efficient and to speed balance/consumption reads.

- Progressive disclosure documentation
  - API docs are deliberately split for readability and for efficient consumption by AI agents and developers.

---

## Key Features & Modules Worth Highlighting

- Agents (AI workflows)
  - Invoice Agent: end-to-end OCR + classification pipeline for receipts and invoices (see invoice-agent-specs.md).
  - Recommendation Coordinator: semantic search and product recommendation orchestration (see recommendation-system-specs.md).

- Robust DB model with RLS
  - Database schema and RLS policies are documented and designed to allow safe queries while enforcing per-user access control and minimal attack surface.

- Semantic search (pgvector)
  - Enables features like natural-language product search and similarity-based invoice matching.

- Performance & architecture docs
  - Contains performance comparisons, quick-start guidelines for profiling, and optimization recommendations (PERFORMANCE-*.md).

- CI-driven deployment & migrations
  - Branch-oriented deployment model where merges to develop/main trigger staged and production Supabase migrations and deployments.

- API documentation tailored for AI agents
  - docs/api organized by domain and optimized for AI consumption, enabling agent-driven automation and context-aware prompts.

---

## Unique Aspects & Differentiators

- Agent-first backend design
  - Unlike typical service-only backends, Kashi Finances integrates agent orchestration as first-class runtime components, allowing AI agents to coordinate multi-step, cross-domain finance tasks under programmatic control.

- Documentation shaped for AI consumers
  - The API and domain docs are intentionally split and structured for progressive disclosure so AI agents can retrieve focused context efficiently.

- Strong emphasis on DB security and operational safety
  - RLS-first schema design, separate staging/production migration flows, and CI protections reduce the risk of accidental data exposure or migration mistakes.

- Hybrid architecture for determinism and ML
  - Services and agents combine deterministic domain logic with AI capabilities—ensuring predictable business outcomes while taking advantage of semantic/ML features where appropriate.
