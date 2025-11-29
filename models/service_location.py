"""Model for service location information."""

from typing import Optional

from pydantic import BaseModel, Field


class ServiceLocation(BaseModel):
    """Model for a location in a service's calling pattern."""
    location_name: str = Field(..., description="Station name")
    crs: str = Field(..., description="CRS code")
    scheduled_time: Optional[str] = Field(default=None, description="Scheduled arrival/departure time")
    estimated_time: Optional[str] = Field(default=None, description="Estimated arrival/departure time")
    actual_time: Optional[str] = Field(default=None, description="Actual arrival/departure time")
    is_cancelled: bool = Field(default=False, description="Whether the call is cancelled")
    length: Optional[str] = Field(default=None, description="Train length at this location")
    platform: Optional[str] = Field(default=None, description="Platform number")
