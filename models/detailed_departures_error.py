"""Model for detailed departures error response."""

from pydantic import BaseModel, Field


class DetailedDeparturesError(BaseModel):
    """Model for detailed departures error response."""
    error: str = Field(..., description="Error message")
    message: str = Field(..., description="Detailed error description")
