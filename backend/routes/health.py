"""
Health check route for Kashi Finances Backend.

This endpoint is PUBLIC (no authentication required) and provides a simple
status check for load balancers, monitoring, and deployment verification.

Follows api-architecture.instructions.md Section 4 (Endpoint Flow):
- Step 1: Auth → SKIPPED (explicitly public endpoint)
- Step 2: Parse/Validate → No request body needed
- Step 3: Domain Filter → N/A (no agent call)
- Step 4: Call Agent → N/A
- Step 5: Map to ResponseModel → Always returns HealthResponse
- Step 6: Persistence → N/A
"""

from fastapi import APIRouter

from backend.schemas.health import HealthResponse
from backend.utils.logging import get_logger

logger = get_logger(__name__)

# Create router with no prefix (mounted at root level in main.py)
router = APIRouter()


@router.get(
    "/health",
    response_model=HealthResponse,
    summary="Health check endpoint",
    description=(
        "Public health check endpoint (no authentication required). "
        "Returns a simple status indicator for monitoring and load balancing."
    ),
    status_code=200,
)
async def health_check() -> HealthResponse:
    """
    Public health check endpoint.
    
    This endpoint is explicitly documented as PUBLIC - no authentication required.
    
    Returns:
        HealthResponse: Simple status object with "ok" status
    
    Example response:
        {
            "status": "ok"
        }
    """
    logger.debug("Health check endpoint called")
    
    return HealthResponse(status="ok")
