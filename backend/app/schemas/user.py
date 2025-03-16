import uuid
from datetime import datetime
from typing import Optional

from pydantic import BaseModel, EmailStr, Field

from app.models.models import UserRole


class UserBase(BaseModel):
    """Base User schema with common attributes"""
    email: EmailStr
    full_name: Optional[str] = None


class UserCreate(UserBase):
    """User creation schema"""
    password: str = Field(..., min_length=8)


class UserUpdate(BaseModel):
    """User update schema with optional fields"""
    email: Optional[EmailStr] = None
    full_name: Optional[str] = None
    password: Optional[str] = Field(None, min_length=8)


class UserInDB(UserBase):
    """User in database schema with hashed password"""
    id: uuid.UUID
    role: UserRole
    is_active: bool = True
    hashed_password: str
    created_at: datetime
    updated_at: Optional[datetime] = None
    available_interview_credits: int = 0
    available_chat_tokens: int = 0

    class Config:
        from_attributes = True


class UserOut(UserBase):
    """User output schema without sensitive information"""
    id: uuid.UUID
    role: UserRole
    is_active: bool
    created_at: datetime
    updated_at: Optional[datetime] = None
    available_interview_credits: int = 0
    available_chat_tokens: int = 0

    class Config:
        from_attributes = True


class PasswordReset(BaseModel):
    """Password reset request schema"""
    email: EmailStr


class PasswordResetConfirm(BaseModel):
    """Password reset confirmation schema"""
    token: str
    password: str = Field(..., min_length=8)