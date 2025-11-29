"""Model for a detailed train departure with extended information."""

from typing import Optional
from pydantic import BaseModel, Field


class DetailedTrainDeparture(BaseModel):
    """Model for a detailed train departure with extended information."""
    std: str = Field(..., description="Scheduled Time of Departure")
    etd: str = Field(..., description="Estimated Time of Departure")
    destination: str = Field(..., description="Destination station name")
    platform: Optional[str] = Field(default="TBA", description="Platform number")
    operator: Optional[str] = Field(default="Unknown", description="Train operating company")
    service_id: Optional[str] = Field(default="N/A", description="Unique service identifier")
    service_type: Optional[str] = Field(default="Unknown", description="Type of service (e.g., Express, Stopping)")
    length: Optional[str] = Field(default="Unknown", description="Number of carriages")
    is_cancelled: Optional[bool] = Field(default=False, description="Whether the service is cancelled")
    cancel_reason: Optional[str] = Field(default=None, description="Reason for cancellation")
    delay_reason: Optional[str] = Field(default=None, description="Reason for delay")
