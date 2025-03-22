import uuid
from datetime import datetime
from typing import Optional, List

from pydantic import BaseModel, Field

from app.models.models import TransactionType


class TransactionBase(BaseModel):
    """Base Transaction schema"""
    transaction_type: TransactionType
    amount: int = Field(..., gt=0)
    price: Optional[float] = None
    reference: Optional[str] = None


class TransactionCreate(TransactionBase):
    """Transaction creation schema"""
    user_id: uuid.UUID
    organization_id: Optional[uuid.UUID] = None
    interview_id: Optional[uuid.UUID] = None


class TransactionUpdate(BaseModel):
    """Transaction update schema with optional fields"""
    reference: Optional[str] = None


class TransactionOut(TransactionBase):
    """Transaction output schema"""
    id: uuid.UUID
    user_id: uuid.UUID
    organization_id: Optional[uuid.UUID] = None
    interview_id: Optional[uuid.UUID] = None
    created_at: datetime
    
    class Config:
        from_attributes = True


class TransactionSummary(BaseModel):
    """Transaction summary for reporting"""
    total_interview_credits_purchased: int = 0
    total_interview_credits_used: int = 0
    total_chat_tokens_purchased: int = 0
    total_chat_tokens_used: int = 0
    total_spent: float = 0
    recent_transactions: List[TransactionOut] = []