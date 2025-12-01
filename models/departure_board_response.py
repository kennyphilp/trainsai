"""Model for departure board API response."""

from typing import List
from pydantic import BaseModel, Field
from .train_departure import TrainDeparture


class DepartureBoardResponse(BaseModel):
    """Model for departure board API response."""
    station: str = Field(..., description="Station name")
    trains: List[TrainDeparture] = Field(default_factory=list, description="List of departing trains")
    message: str = Field(..., description="Summary message")
