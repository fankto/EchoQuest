from datetime import datetime
from typing import Optional
from uuid import UUID

from pydantic import BaseModel, ConfigDict


class TimestampedBase(BaseModel):
    """Base schema for models with timestamps"""
    created_at: datetime
    updated_at: Optional[datetime] = None

    model_config = ConfigDict(from_attributes=True)


class IdentifiedBase(TimestampedBase):
    """Base schema for models with ID and timestamps"""
    id: UUID

    model_config = ConfigDict(from_attributes=True)