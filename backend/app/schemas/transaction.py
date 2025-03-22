from datetime import datetime
from typing import Optional
from uuid import UUID

from pydantic import BaseModel, Field

from app.models.models import TransactionType
from app.schemas.base import IdentifiedBase


class TransactionBase(BaseModel):
    """Base Transaction schema"""
    transaction_type: TransactionType
    amount: int = Field(..., gt=0)
    price: Optional[float] = None
    reference: Optional[str] = None


class TransactionCreate(TransactionBase):
    """Transaction creation schema"""
    user_id: UUID
    organization_id: Optional[UUID] = None
    interview_id: Optional[UUID] = None


class TransactionUpdate(BaseModel):
    """Transaction update schema with optional fields"""
    reference: Optional[str] = None


class TransactionOut(TransactionBase, IdentifiedBase):
    """Transaction output schema"""
    user_id: UUID
    organization_id: Optional[UUID] = None
    interview_id: Optional[UUID] = None