"""Model for departure board error response."""

from pydantic import BaseModel, Field


class DepartureBoardError(BaseModel):
    """Model for departure board error response."""
    error: str = Field(..., description="Error message")
    message: str = Field(..., description="Detailed error description")
