"""
FastAPI application entry point for Kashi Finances backend.

This module creates the FastAPI app instance and registers all routers.
"""

import logging
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from backend.routes.accounts import router as accounts_router
from backend.routes.budgets import router as budgets_router
from backend.routes.categories import router as categories_router
from backend.routes.invoices import router as invoices_router
from backend.routes.transactions import router as transactions_router
from backend.routes.profile import router as profile_router
from backend.routes.recurring_transactions import router as recurring_transactions_router
from backend.routes.recurring_transactions import sync_router as recurring_sync_router
from backend.routes.transfers import router as transfers_router

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)

logger = logging.getLogger(__name__)

# Create FastAPI app
app = FastAPI(
    title="Kashi Finances API",
    description="Backend service for Kashi Finances mobile app",
    version="0.1.0",
    docs_url="/docs",
    redoc_url="/redoc"
)

# Configure CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # TODO: Restrict to mobile app origins in production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Register routers
app.include_router(accounts_router)
app.include_router(budgets_router)
app.include_router(categories_router)
app.include_router(invoices_router)
app.include_router(transactions_router)
app.include_router(profile_router)
app.include_router(recurring_transactions_router)
app.include_router(recurring_sync_router)
app.include_router(transfers_router)

# Health check endpoint
@app.get("/health", tags=["system"])
async def health_check():
    """Check if API is running."""
    return {"status": "healthy", "service": "kashi-finances-backend"}

logger.info("FastAPI app initialized successfully")
