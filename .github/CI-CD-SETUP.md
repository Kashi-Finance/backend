# CI/CD Pipeline Documentation

This document describes the GitHub Actions CI/CD pipeline for the Kashi Finances backend.

## Overview

The pipeline consists of three workflows:

1. **CI (`ci.yaml`)** - Continuous Integration for quality gates
2. **Staging (`staging.yaml`)** - Automated deployment to staging environment
3. **Production (`prod.yaml`)** - Controlled deployment to production environment

## Branching Strategy

```
feature/fix branches → develop (staging) → main (production)
```

- **Feature/fix branches**: Development work happens here
- **`develop` branch**: Staging environment (auto-deploys on merge)
- **`main` branch**: Production environment (auto-deploys on merge)

## Workflow Triggers

### CI Workflow
- Triggers on: Push to `feature/**`, `fix/**`, `develop`, or `main` branches; PRs to `develop` or `main`
- Purpose: Quality gates (tests, linting, type checking, Docker build)
- Blocks: CD workflows wait for CI to pass before deploying

### Staging Workflow
- Triggers on: Push to `develop` branch
- **Waits for CI**: Uses `wait-on-check-action` to ensure CI passes before deployment
- Purpose: Deploy to staging Cloud Run service
- Steps:
  1. Wait for CI workflow to complete successfully
  2. Apply Supabase migrations to staging DB
  3. Build and push Docker image
  4. Deploy to Cloud Run staging
  5. Verify health endpoint

### Production Workflow
- Triggers on: Push to `main` branch
- **Waits for CI**: Uses `wait-on-check-action` to ensure CI passes before deployment
- Purpose: Deploy to production Cloud Run service
- Steps:
  1. Wait for CI workflow to complete successfully
  2. Safety check (verify PR merge - warning only)
  3. Apply Supabase migrations to production DB
  4. Build and push Docker image
  5. Deploy to Cloud Run production with canary (10% traffic)
  6. Verify health endpoint
  7. Manual step: Route 100% traffic after monitoring

## Required GitHub Secrets

### Supabase Secrets (shared across environments)
- `SUPABASE_ACCESS_TOKEN` - Your Supabase personal access token

### Staging Secrets
- `STAGING_PROJECT_ID` - Supabase staging project ref
- `STAGING_DB_PASSWORD` - Supabase staging database password
- `STAGING_SUPABASE_URL` - Staging Supabase project URL
- `STAGING_SUPABASE_PUBLISHABLE_KEY` - Staging publishable key
- `STAGING_GCP_PROJECT_ID` - GCP project ID for staging
- `STAGING_GCP_SA_KEY` - GCP service account JSON key for staging
- `STAGING_SERVICE_ACCOUNT` - Service account email for Cloud Run
- `STAGING_GOOGLE_API_KEY_SECRET` - Secret Manager resource name for Google API key
- `STAGING_CORS_ORIGINS` - Allowed CORS origins (comma-separated)

### Production Secrets
- `PRODUCTION_PROJECT_ID` - Supabase production project ref
- `PRODUCTION_DB_PASSWORD` - Supabase production database password
- `PRODUCTION_SUPABASE_URL` - Production Supabase project URL
- `PRODUCTION_SUPABASE_PUBLISHABLE_KEY` - Production publishable key
- `PRODUCTION_GCP_PROJECT_ID` - GCP project ID for production
- `PRODUCTION_GCP_SA_KEY` - GCP service account JSON key for production
- `PRODUCTION_SERVICE_ACCOUNT` - Service account email for Cloud Run
- `PRODUCTION_GOOGLE_API_KEY_SECRET` - Secret Manager resource name for Google API key
- `PRODUCTION_CORS_ORIGINS` - Allowed CORS origins (comma-separated)

### Optional Secrets
- `GCP_REGION` - GCP region (defaults to `us-central1`)
- `SUPABASE_STORAGE_BUCKET` - Storage bucket name (defaults to `invoices`)

## CI Pipeline Details

### Lint and Test Job
- Python 3.12 with uv package manager (10-100x faster than pip)
- Uses `uv sync --frozen` for reproducible builds from `uv.lock`
- Static type checking with mypy (currently continue-on-error)
- Code linting with ruff (currently continue-on-error)
- Local Supabase stack startup
- Migration validation
- Schema diff verification
- Pytest execution
- **Outputs**: `tests-passed` flag for downstream jobs

### Docker Build Test Job
- **Depends on**: lint-and-test (only runs if tests pass)
- Builds Docker image using BuildKit caching
- Tests that container starts successfully
- Verifies health endpoint responds

## CD Pipeline Features

### Key Improvement: CI Gate for CD

Both staging and production workflows now include a `wait-for-ci` job that:
1. Waits for the CI workflow's `lint-and-test` job to complete
2. Only proceeds if CI passes with `success` conclusion
3. Blocks deployment if CI fails or is still running

This solves the problem of CD running before CI finishes (since branch protection is not available).

### Staging Deployment
- **Waits for CI** before proceeding
- **Supabase migrations** applied automatically
- **Docker image** built and pushed to Artifact Registry
- **Cloud Run deployment** with staging configuration:
  - 512Mi memory, 1 CPU
  - 0-10 instances (autoscaling)
  - Environment variables set directly
  - Secrets from Secret Manager
- **Health check** after deployment

### Production Deployment
- **Waits for CI** before proceeding
- **Safety check** for PR merge (warning only, no enforcement)
- **Supabase migrations** applied to production DB
- **Docker image** tagged with commit SHA, `latest`, and `production`
- **Canary deployment** to Cloud Run:
  - 1Gi memory, 2 CPU
  - 1-100 instances (higher capacity)
  - Initial deployment with `--no-traffic`
  - 10% traffic routed to new revision
  - Manual step required to route 100% traffic
- **Health check** with automatic rollback on failure

## Known Limitations

### Branch Protection (GitHub Teams Required)
⚠️ **Current Limitation**: Branch protection rules require GitHub Teams, which is not available in the current plan.

**Impact:**
- Cannot enforce required reviews before merging to `develop` or `main`
- Cannot prevent direct pushes to protected branches
- Manual discipline required to follow PR workflow

**Mitigations Implemented:**
1. **CI Gate for CD**: Both staging and production workflows wait for CI to pass before deploying (using `wait-on-check-action`)
2. **Concurrency controls**: Duplicate runs are cancelled (staging) or serialized (production)
3. **Safety check in production**: Warns (but doesn't block) non-PR commits
4. GitHub Environments with manual approval gates (can be configured)

**Future Improvement:**
When GitHub Teams becomes available:
- Enable branch protection on `develop` and `main`
- Require 1+ review before merge
- Require CI to pass before merge
- Prevent direct pushes

### Manual Production Traffic Routing
Production deployments use canary deployment (10% traffic) by design.

**After deployment:**
1. Monitor staging metrics and logs
2. If healthy, manually route 100% traffic:
   ```bash
   gcloud run services update-traffic kashi-backend \
     --region us-central1 \
     --to-latest
   ```
3. If issues detected, traffic remains at 10% (old revision serves 90%)

## Best Practices

### For Developers
1. **Always use PRs** for code changes (even without enforcement)
2. **Run tests locally** before pushing: `pytest tests/`
3. **Check CI status** before requesting review
4. **Verify staging** after merging to `develop`
5. **Monitor production** after merging to `main`

### For Deployments
1. **Staging first**: Always deploy to staging before production
2. **Test staging**: Verify functionality in staging environment
3. **Monitor metrics**: Check Cloud Run metrics after deployment
4. **Gradual rollout**: Use 10% canary in production, then 100%
5. **Keep migrations reversible**: Plan rollback strategy for DB changes

## Troubleshooting

### CI Failures
- **Mypy errors**: Currently set to `continue-on-error` (TODO: fix types)
- **Pytest failures**: Check test logs, fix tests before merging
- **Schema diff detected**: Create a migration for uncommitted DB changes
- **Docker build fails**: Check Dockerfile syntax and dependencies

### Deployment Failures
- **Supabase migration fails**: Check migration SQL, verify DB state
- **Cloud Run deploy fails**: Check GCP permissions, service account roles
- **Health check fails**: Check application logs in Cloud Run console
- **Traffic routing fails**: Verify revision exists and is healthy

### Rollback Procedure
1. **Immediate rollback**:
   ```bash
   gcloud run services update-traffic kashi-backend \
     --region us-central1 \
     --to-revisions <previous-revision>=100
   ```
2. **Database rollback**: Requires manual intervention (contact DB admin)
3. **Code rollback**: Revert commit and push to `main`

## Monitoring and Observability

### Cloud Run Metrics
- Access in GCP Console > Cloud Run > [service] > Metrics
- Key metrics: Request count, latency, error rate, CPU/memory usage

### Logs
- Cloud Run logs: GCP Console > Cloud Run > [service] > Logs
- Application logs: Structured JSON logs with log levels

### Alerts
TODO: Configure Cloud Monitoring alerts for:
- High error rate (>1%)
- High latency (p95 > 2s)
- Container crashes
- Low memory/CPU margins

## Future Improvements

1. **Enable branch protection** when GitHub Teams available
2. **Add integration tests** to CI pipeline
3. **Configure monitoring alerts** in GCP
4. **Add performance benchmarks** to CI
5. **Implement automated rollback** on health check failures
6. **Add deployment notifications** (Slack/email)
7. **Create staging→production promotion workflow** with manual approval
8. **Add load testing** before production deployment

## References

- [GitHub Actions Documentation](https://docs.github.com/en/actions)
- [Cloud Run Deployment](https://cloud.google.com/run/docs/deploying)
- [Supabase CLI](https://supabase.com/docs/guides/cli)
- [Docker Best Practices](https://docs.docker.com/develop/dev-best-practices/)
