# Multi-stage build for Kashi Finances FastAPI backend

# ============================================================================
# Stage 1: Builder - Install dependencies using uv
# ============================================================================
FROM ghcr.io/astral-sh/uv:0.9.9-python3.12-bookworm-slim AS builder

# Set working directory
WORKDIR /app

# Install system dependencies required for building Python packages
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    g++ \
    libpq-dev \
    && rm -rf /var/lib/apt/lists/*

# Configure uv for optimal Docker builds
ENV UV_LINK_MODE=copy \
    UV_COMPILE_BYTECODE=1

# Copy only requirements first to leverage Docker cache
COPY requirements.txt .

# Install Python dependencies using uv
# Note: Cache mount not available in Cloud Run standard builder
RUN uv pip install --system -r requirements.txt

# ============================================================================
# Stage 2: Runtime - Minimal production image
# ============================================================================
FROM python:3.12-slim AS runtime

# Set working directory
WORKDIR /app

# Install only runtime system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    libpq5 \
    && rm -rf /var/lib/apt/lists/*

# Copy installed packages from builder (uv installs to system Python)
COPY --from=builder /usr/local/lib/python3.12/site-packages /usr/local/lib/python3.12/site-packages
COPY --from=builder /usr/local/bin /usr/local/bin

# Set environment variables
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PORT=8080

# Create non-root user for security
RUN useradd -m -u 1000 nonroot && \
    chown -R nonroot:nonroot /app

# Copy application code
COPY --chown=nonroot:nonroot . .

# Switch to non-root user
USER nonroot

# Expose Cloud Run default port
EXPOSE 8080

# Start FastAPI with uvicorn
CMD exec uvicorn backend.main:app --host 0.0.0.0 --port ${PORT} --workers 1 --log-level info
