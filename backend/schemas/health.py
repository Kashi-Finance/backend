"""
Health check endpoint schemas.

The health endpoint is PUBLIC (no authentication required) and returns
a simple status indicator.
"""

from pydantic import BaseModel, Field


class HealthResponse(BaseModel):
    """
    Response model for GET /health endpoint.
    
    This endpoint is explicitly documented as public (no auth required).
    Used by load balancers, monitoring systems, and deployment checks.
    """
    
    status: str = Field(
        default="ok",
        description="Health status of the API (always 'ok' if responding)",
        examples=["ok"]
    )
    
    class Config:
        """Pydantic model configuration."""
        json_schema_extra = {
            "example": {
                "status": "ok"
            }
        }
