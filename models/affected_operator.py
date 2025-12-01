"""Model for an affected train operator."""

from typing import Optional
from pydantic import BaseModel, Field


class AffectedOperator(BaseModel):
    """Model for an affected train operator."""
    ref: Optional[str] = Field(default=None, description="Operator reference code")
    name: Optional[str] = Field(default=None, description="Operator name")
