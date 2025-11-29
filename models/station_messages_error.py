"""Model for station messages error response."""

from pydantic import BaseModel, Field


class StationMessagesError(BaseModel):
    """Model for station messages error response."""
    error: str = Field(..., description="Error message")
    message: str = Field(..., description="Detailed error description")
