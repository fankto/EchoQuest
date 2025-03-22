from typing import Optional, List
from uuid import UUID

from pydantic import BaseModel, Field


class CreditPackage(BaseModel):
    """Credit package schema"""
    id: str = Field(..., description="Package identifier")
    name: str = Field(..., description="Package name")
    description: str = Field(..., description="Package description")
    credits: int = Field(..., gt=0, description="Number of credits in package")
    price: float = Field(..., gt=0, description="Price in USD")
    validity_days: int = Field(..., gt=0, description="Validity in days")


class TokenPackage(BaseModel):
    """Token package schema"""
    id: str = Field(..., description="Package identifier")
    name: str = Field(..., description="Package name")
    description: str = Field(..., description="Package description")
    tokens: int = Field(..., gt=0, description="Number of tokens in package")
    price: float = Field(..., gt=0, description="Price in USD")


class CreditPurchase(BaseModel):
    """Credit purchase request schema"""
    package_id: str = Field(..., description="Package ID to purchase")


class CreditPurchaseResponse(BaseModel):
    """Credit purchase response schema"""
    success: bool = Field(..., description="Whether purchase was successful")
    message: str = Field(..., description="Success or error message")
    credits_added: int = Field(..., description="Number of credits or tokens added")
    total_credits: int = Field(..., description="New total credits or tokens")
    transaction_id: str = Field(..., description="Transaction ID for reference")


class CreditSummary(BaseModel):
    """Credit summary schema"""
    available_interview_credits: int
    available_chat_tokens: int
    interview_credits_used: int
    chat_tokens_used: int


class TransactionResponse(BaseModel):
    """Transaction response schema"""
    id: UUID = Field(..., description="Transaction ID")
    transaction_type: str = Field(..., description="Type of transaction")
    amount: int = Field(..., description="Amount of credits or tokens")
    price: Optional[float] = Field(None, description="Price paid (if a purchase)")
    reference: Optional[str] = Field(None, description="Reference number or identifier")
    created_at: str = Field(..., description="Transaction timestamp")
    interview_id: Optional[UUID] = Field(None, description="Associated interview ID (if any)")


class TransactionSummary(BaseModel):
    """Transaction summary for reporting"""
    total_interview_credits_purchased: int = 0
    total_interview_credits_used: int = 0
    total_chat_tokens_purchased: int = 0
    total_chat_tokens_used: int = 0
    total_spent: float = 0
    recent_transactions: List[TransactionResponse] = []