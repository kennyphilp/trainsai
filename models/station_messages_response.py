"""Model for station messages/incidents API response."""

from typing import List
from pydantic import BaseModel, Field
from .incident import Incident


class StationMessagesResponse(BaseModel):
    """Model for station messages/incidents API response."""
    messages: List[Incident] = Field(default_factory=list, description="List of incidents")
    message: str = Field(..., description="Summary message")
