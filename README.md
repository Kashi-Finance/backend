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

## Rules for Pushing and Merging

These rules define how contributors should work with branches, commits, and pull requests in **Kashi Finances** to ensure a stable CI/CD pipeline and reliable Supabase deployments.

---

### Branch Structure

* **feature/** → individual development branches (e.g., `feature/add-budget-endpoint`).
* **develop** → staging branch connected to the staging Supabase environment.
* **main** → production branch connected to the production Supabase environment.

---

### Direct Push Policy

* **Never push directly to `develop` or `main`.**

  * These branches represent deployed environments and must remain stable.
  * All changes must enter them **through pull requests (PRs)**.

* DO NOT direct push to `develop` or `main` wto prevent accidental migrations.

* You can freely push to your own `feature/*` branches.

---

### Pull Request Rules

#### Creating PRs

* Every change must be proposed via a **pull request**.
* PR titles should be clear and concise (e.g., `Add user analytics endpoint`).
* Each PR should target:

  * `develop` → for staging/testing.
  * `main` → only from `develop` after staging is validated.

#### Continuous Integration (CI)

* All PRs trigger the `CI` workflow (`.github/workflows/ci.yaml`).
* Merging is **blocked** until all CI checks pass successfully.
* CI runs include:

  * Linting / tests (backend)
  * Local Supabase validation
  * Schema integrity checks

---

### Deployment Behavior

* Merging into `develop` triggers **automatic migration** of the staging Supabase database via `staging.yaml`.
* Merging into `main` triggers **production deployment** via `production.yaml`.
* The staging deploy is blocked if the last commit is not a merge PR (protection against direct pushes).

---

### Best Practices

* Use **small, atomic commits** with descriptive messages.
* Keep branches up to date with `develop` before opening a PR.
* Avoid force pushes (`--force`) unless absolutely necessary.
* If a PR introduces schema changes, verify migrations locally with `supabase db push` before committing.

---

### Enforcement Summary

| Branch    | Direct Push | Requires PR | Auto Deploys |
| --------- | ----------- | ----------- | ------------ |
| feature/* | ✅ Allowed   | ❌ Optional  | ❌ No         |
| develop   | 🚫 Blocked  | ✅ Yes       | ✅ Staging    | 
| main      | 🚫 Blocked  | ✅ Yes       | ✅ Production | 

---

> ⚠️ Any direct push to `develop` or `main` may be reverted and trigger an internal review.
