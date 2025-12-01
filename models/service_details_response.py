"""Model for detailed service information response."""

from typing import List, Optional

from pydantic import BaseModel, Field

from .service_location import ServiceLocation


class ServiceDetailsResponse(BaseModel):
    """Model for service details API response."""
    service_id: str = Field(..., description="Unique service identifier")
    operator: Optional[str] = Field(default=None, description="Train operating company")
    operator_code: Optional[str] = Field(default=None, description="Operator code")
    service_type: Optional[str] = Field(default=None, description="Type of service")
    is_cancelled: bool = Field(default=False, description="Whether the service is cancelled")
    cancel_reason: Optional[str] = Field(default=None, description="Reason for cancellation")
    delay_reason: Optional[str] = Field(default=None, description="Reason for delay")
    origin: Optional[str] = Field(default=None, description="Origin station")
    destination: Optional[str] = Field(default=None, description="Destination station")
    std: Optional[str] = Field(default=None, description="Scheduled time of departure")
    etd: Optional[str] = Field(default=None, description="Estimated time of departure")
    sta: Optional[str] = Field(default=None, description="Scheduled time of arrival")
    eta: Optional[str] = Field(default=None, description="Estimated time of arrival")
    platform: Optional[str] = Field(default=None, description="Platform number")
    calling_points: List[ServiceLocation] = Field(default_factory=list, description="List of calling points")
    message: str = Field(..., description="Summary message")
