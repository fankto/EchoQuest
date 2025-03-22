from datetime import datetime
from typing import List, Optional
from uuid import UUID

from pydantic import BaseModel, EmailStr, ConfigDict

from app.models.models import OrganizationRole
from app.schemas.base import IdentifiedBase


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

    model_config = ConfigDict(extra="ignore")


class OrganizationMemberBase(BaseModel):
    """Base OrganizationMember schema"""
    role: OrganizationRole


class OrganizationMemberCreate(BaseModel):
    """OrganizationMember creation schema"""
    email: EmailStr  # Email of the user to add
    role: OrganizationRole = OrganizationRole.MEMBER


class OrganizationMemberUpdate(BaseModel):
    """OrganizationMember update schema"""
    role: OrganizationRole

    model_config = ConfigDict(extra="ignore")


class OrganizationMemberOut(BaseModel):
    """OrganizationMember output schema"""
    id: UUID
    user_id: UUID
    organization_id: UUID
    role: OrganizationRole
    email: EmailStr
    full_name: Optional[str] = None
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class OrganizationWithMembers(OrganizationBase, IdentifiedBase):
    """Organization with members output schema"""
    members: List[OrganizationMemberOut] = []
    available_interview_credits: int = 0
    available_chat_tokens: int = 0


class OrganizationOut(OrganizationBase, IdentifiedBase):
    """Organization output schema without members"""
    member_count: int = 0
    available_interview_credits: int = 0
    available_chat_tokens: int = 0
    user_role: Optional[str] = None


class OrganizationInvite(BaseModel):
    """Organization invite schema"""
    email: EmailStr
    role: OrganizationRole = OrganizationRole.MEMBER


class OrganizationInviteResponse(BaseModel):
    """Organization invite response schema"""
    success: bool
    message: str
    invite_url: Optional[str] = None