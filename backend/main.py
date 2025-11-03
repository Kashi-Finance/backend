"""
FastAPI application entry point for Kashi Finances backend.

This module creates the FastAPI app instance and registers all routers.
"""

import logging
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from backend.routes.invoices import router as invoices_router

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
app.include_router(invoices_router)

# Health check endpoint
@app.get("/health", tags=["system"])
async def health_check():
    """Check if API is running."""
    return {"status": "healthy", "service": "kashi-finances-backend"}

logger.info("FastAPI app initialized successfully")
