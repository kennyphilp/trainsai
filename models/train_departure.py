"""Model for a single train departure."""

from pydantic import BaseModel, Field


class TrainDeparture(BaseModel):
    """Model for a single train departure."""
    std: str = Field(..., description="Scheduled Time of Departure")
    etd: str = Field(..., description="Estimated Time of Departure")
    destination: str = Field(..., description="Destination station name")
    platform: str = Field(default="TBA", description="Platform number")
    operator: str = Field(default="Unknown", description="Train operating company")
