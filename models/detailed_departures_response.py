"""Model for detailed departures API response."""

from typing import List
from pydantic import BaseModel, Field
from .detailed_train_departure import DetailedTrainDeparture


class DetailedDeparturesResponse(BaseModel):
    """Model for detailed departures API response."""
    station: str = Field(..., description="Station name")
    trains: List[DetailedTrainDeparture] = Field(default_factory=list, description="List of detailed departures")
    message: str = Field(..., description="Summary message")
