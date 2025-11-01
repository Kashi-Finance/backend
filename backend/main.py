"""
Kashi Finances Backend - Main FastAPI application entrypoint.

This module creates the FastAPI app instance and mounts all routers.
Future routers (invoices, recommendations, transactions, etc.) will follow
the patterns defined in .github/instructions/api-architecture.instructions.md.
"""

import logging
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from backend.routes import health
from backend.utils.logging import get_logger

logger = get_logger(__name__)

# Create FastAPI application instance
app = FastAPI(
    title="Kashi Finances API",
    description="Backend API for orchestrating adk agents built on Google ADK",
    version="0.1.0",
)

# Configure CORS for mobile app (adjust origins as needed for production)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # TODO: Restrict to actual mobile app origins in production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Mount routers
# Health check (public, no auth required)
app.include_router(health.router, tags=["health"])

# Future routers will be mounted here following api-architecture.instructions.md:
# - /invoices/* → InvoiceAgent flows (OCR, commit)
# - /recommendations/* → RecommendationCoordinatorAgent flows
# - /transactions/* → manual transaction CRUD
# - /accounts/* → account management
# - /budgets/* → budget management
# - /wishlists/* → wishlist/goals management
# Each will enforce Supabase Auth via backend/auth/auth.py verify_supabase_token()

logger.info("Kashi Finances API initialized successfully")
