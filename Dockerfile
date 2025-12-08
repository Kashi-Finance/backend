# Multi-stage build for Kashi Finances FastAPI backend

# ============================================================================
# Stage 1: Builder - Install dependencies using uv
# ============================================================================
FROM ghcr.io/astral-sh/uv:0.9.9-python3.12-bookworm-slim AS builder

# Set working directory
WORKDIR /app

# Install system dependencies required for building Python packages
# (psycopg2 requires libpq-dev, some packages need gcc/g++)
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    g++ \
    libpq-dev \
    && rm -rf /var/lib/apt/lists/* \
    && apt-get clean

# Configure uv for optimal Docker builds
ENV UV_LINK_MODE=copy \
    UV_COMPILE_BYTECODE=1 \
    UV_PROJECT_ENVIRONMENT=/app/.venv

# Copy dependency files first to leverage Docker layer caching
# Changes to application code won't invalidate the dependency layer
COPY pyproject.toml uv.lock ./

# Install Python dependencies using uv sync (reads pyproject.toml + uv.lock)
# --frozen ensures we use exact versions from uv.lock
# --no-dev excludes development dependencies from production image
RUN uv sync --frozen --no-dev

# ============================================================================
# Stage 2: Runtime - Minimal production image
# ============================================================================
FROM python:3.12-slim-bookworm AS runtime

# OCI Image labels for metadata
LABEL org.opencontainers.image.source="https://github.com/kashi-finances/backend" \
      org.opencontainers.image.title="Kashi Finances Backend" \
      org.opencontainers.image.description="FastAPI backend for Kashi Finances mobile app" \
      org.opencontainers.image.vendor="Kashi Finances"

# Set working directory
WORKDIR /app

# Install only runtime system dependencies
# libpq5 is the runtime library for PostgreSQL connections
RUN apt-get update && apt-get install -y --no-install-recommends \
    libpq5 \
    curl \
    && rm -rf /var/lib/apt/lists/* \
    && apt-get clean

# Set environment variables for Python
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONPATH=/app \
    PATH="/app/.venv/bin:$PATH" \
    PORT=8080

# Create non-root user for security (before copying files)
RUN useradd --create-home --shell /bin/bash --uid 1000 nonroot \
    && mkdir -p /app/.venv \
    && chown -R nonroot:nonroot /app

# Copy virtual environment from builder stage
COPY --from=builder --chown=nonroot:nonroot /app/.venv /app/.venv

# Copy application code (after dependencies for better layer caching)
COPY --chown=nonroot:nonroot backend/ ./backend/

# Switch to non-root user for security
USER nonroot

# Expose Cloud Run default port
EXPOSE 8080

# Health check for container orchestration
# Cloud Run handles health checks via /health endpoint
HEALTHCHECK --interval=30s --timeout=3s --start-period=5s --retries=3 \
    CMD curl -f http://localhost:${PORT}/health || exit 1

# Start FastAPI with uvicorn
# Using exec form to ensure proper signal handling
CMD ["sh", "-c", "uvicorn backend.main:app --host 0.0.0.0 --port ${PORT} --workers 1 --log-level info"]
