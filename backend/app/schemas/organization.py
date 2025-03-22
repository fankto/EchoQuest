import uuid
from datetime import datetime
from typing import List, Optional

from pydantic import BaseModel, EmailStr

from app.models.models import OrganizationRole


class OrganizationBase(BaseModel):
    """Base Organization schema"""
    name: str
    description: Optional[str] = None


class OrganizationCreate(OrganizationBase):
    """Organization creation schema"""
    pass


class OrganizationUpdate(BaseModel):
    """Organization update schema with optional fields"""
    name: Optional[str] = None
    description: Optional[str] = None


class OrganizationMemberBase(BaseModel):
    """Base OrganizationMember schema"""
    role: OrganizationRole


class OrganizationMemberCreate(OrganizationMemberBase):
    """OrganizationMember creation schema"""
    email: EmailStr  # Email of the user to add


class OrganizationMemberUpdate(BaseModel):
    """OrganizationMember update schema"""
    role: Optional[OrganizationRole] = None


class OrganizationMemberOut(OrganizationMemberBase):
    """OrganizationMember output schema"""
    id: uuid.UUID
    user_id: uuid.UUID
    organization_id: uuid.UUID
    email: EmailStr
    full_name: Optional[str] = None
    
    class Config:
        from_attributes = True


class OrganizationWithMembers(OrganizationBase):
    """Organization with members output schema"""
    id: uuid.UUID
    created_at: datetime
    updated_at: Optional[datetime] = None
    members: List[OrganizationMemberOut] = []
    available_interview_credits: int = 0
    available_chat_tokens: int = 0
    
    class Config:
        from_attributes = True


class OrganizationOut(OrganizationBase):
    """Organization output schema without members"""
    id: uuid.UUID
    created_at: datetime
    updated_at: Optional[datetime] = None
    member_count: int = 0
    available_interview_credits: int = 0
    available_chat_tokens: int = 0
    
    class Config:
        from_attributes = True


class OrganizationInvite(BaseModel):
    """Organization invite schema"""
    email: EmailStr
    role: OrganizationRole = OrganizationRole.MEMBER