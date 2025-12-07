"""
FastAPI application entry point for Kashi Finances backend.

This module creates the FastAPI app instance and registers all routers.
"""

import os
import logging
from fastapi import FastAPI, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware

from backend.routes.accounts import router as accounts_router
from backend.routes.auth import router as auth_router
from backend.routes.budgets import router as budgets_router
from backend.routes.categories import router as categories_router
from backend.routes.invoices import router as invoices_router
from backend.routes.transactions import router as transactions_router
from backend.routes.profile import router as profile_router
from backend.routes.recurring_transactions import router as recurring_transactions_router
from backend.routes.recurring_transactions import sync_router as recurring_sync_router
from backend.routes.transfers import router as transfers_router
from backend.routes.wishlists import router as wishlists_router
from backend.routes.recommendations import router as recommendations_router
from backend.routes.engagement import router as engagement_router

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)

logger = logging.getLogger(__name__)


def _get_cors_origins() -> list[str]:
    """
    Get allowed CORS origins based on environment.
    
    Environment-based configuration:
    - ENVIRONMENT=production: Uses CORS_ALLOWED_ORIGINS env var (required)
    - ENVIRONMENT=testing/development: Allows all origins for local dev
    
    For mobile apps:
    - Native mobile apps (Flutter) don't send Origin headers, so CORS
      doesn't restrict them. CORS primarily affects web browsers.
    - If a web client is added later, origins should be explicitly listed.
    
    Returns:
        List of allowed origin URLs, or ["*"] for development.
    """
    environment = os.getenv("ENVIRONMENT", "development")
    
    if environment == "production":
        # Production: Require explicit origins
        cors_origins = os.getenv("CORS_ALLOWED_ORIGINS", "")
        if cors_origins:
            origins = [origin.strip() for origin in cors_origins.split(",")]
            logger.info(f"CORS configured for production with {len(origins)} allowed origins")
            return origins
        else:
            # In production without explicit origins, allow none (strict)
            # This is safest - mobile apps don't need CORS, web clients must be configured
            logger.warning(
                "CORS_ALLOWED_ORIGINS not set in production. "
                "No web origins allowed. Set CORS_ALLOWED_ORIGINS for web clients."
            )
            return []
    else:
        # Development/Testing: Allow all for local development
        logger.info(f"CORS configured for {environment}: allowing all origins")
        return ["*"]


# Create FastAPI app
app = FastAPI(
    title="Kashi Finances API",
    description="Backend service for Kashi Finances mobile app",
    version="0.1.0",
    docs_url="/docs",
    redoc_url="/redoc"
)

# Custom validation error handler to log detailed errors
@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    """
    Log detailed validation errors for debugging.
    
    This helps diagnose 422 errors from the frontend.
    """
    logger.error(
        f"Validation error on {request.method} {request.url.path}: {exc.errors()}"
    )
    logger.error(f"Request body preview: {str(await request.body())[:500]}")
    
    return JSONResponse(
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        content={
            "error": "validation_error",
            "details": exc.errors(),
            "body": exc.body
        }
    )

# Configure CORS with environment-based origins
cors_origins = _get_cors_origins()
app.add_middleware(
    CORSMiddleware,
    allow_origins=cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Register routers
app.include_router(auth_router)
app.include_router(accounts_router)
app.include_router(budgets_router)
app.include_router(categories_router)
app.include_router(invoices_router)
app.include_router(transactions_router)
app.include_router(profile_router)
app.include_router(recurring_transactions_router)
app.include_router(recurring_sync_router)
app.include_router(transfers_router)
app.include_router(wishlists_router)
app.include_router(recommendations_router)
app.include_router(engagement_router)

# Health check endpoint
@app.get("/health", tags=["system"])
async def health_check():
    """Check if API is running."""
    return {"status": "healthy", "service": "kashi-finances-backend"}

logger.info("FastAPI app initialized successfully")
