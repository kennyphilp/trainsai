"""Model for service details error response."""

from pydantic import BaseModel, Field


class ServiceDetailsError(BaseModel):
    """Model for service details error response."""
    error: str = Field(..., description="Error message")
    message: str = Field(..., description="Detailed error description")
