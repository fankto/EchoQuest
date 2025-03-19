from datetime import datetime
from typing import Optional
from uuid import UUID

from pydantic import BaseModel, EmailStr, Field, ConfigDict

from app.models.models import UserRole
from app.schemas.base import IdentifiedBase


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

    model_config = ConfigDict(extra="ignore")


class UserInDB(UserBase, IdentifiedBase):
    """User in database schema with hashed password"""
    role: UserRole
    is_active: bool = True
    hashed_password: str
    available_interview_credits: int = 0
    available_chat_tokens: int = 0


class UserOut(UserBase, IdentifiedBase):
    """User output schema without sensitive information"""
    role: UserRole
    is_active: bool
    available_interview_credits: int = 0
    available_chat_tokens: int = 0


class UserAdminUpdate(UserUpdate):
    """User update schema for admins with additional fields"""
    role: Optional[UserRole] = None
    is_active: Optional[bool] = None
    available_interview_credits: Optional[int] = None
    available_chat_tokens: Optional[int] = None


class PasswordReset(BaseModel):
    """Password reset request schema"""
    email: EmailStr


class PasswordResetConfirm(BaseModel):
    """Password reset confirmation schema"""
    token: str
    password: str = Field(..., min_length=8)


class UserWithStats(UserOut):
    """User output schema with additional statistics"""
    interview_count: int = 0
    questionnaire_count: int = 0
    organization_count: int = 0
    total_credits_used: int = 0