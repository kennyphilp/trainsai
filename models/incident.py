"""Model for a service incident/disruption."""

from typing import List, Optional
from pydantic import BaseModel, Field
from .affected_operator import AffectedOperator


class Incident(BaseModel):
    """Model for a service incident/disruption."""
    id: Optional[str] = Field(default=None, description="Incident number")
    category: str = Field(..., description="Incident category (planned/unplanned)")
    severity: Optional[str] = Field(default=None, description="Incident priority/severity")
    title: Optional[str] = Field(default=None, description="Incident summary")
    message: Optional[str] = Field(default=None, description="Detailed incident description")
    start_time: Optional[str] = Field(default=None, description="Incident start time")
    end_time: Optional[str] = Field(default=None, description="Incident end time")
    last_updated: Optional[str] = Field(default=None, description="Last update timestamp")
    operators: List[AffectedOperator] = Field(default_factory=list, description="Affected operators")
    routes_affected: Optional[str] = Field(default=None, description="Routes affected by incident")
    is_planned: bool = Field(default=False, description="Whether incident is planned work")
