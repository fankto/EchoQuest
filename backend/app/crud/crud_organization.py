from typing import List, Optional, Union, Dict, Any
from uuid import UUID

from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import joinedload

from app.crud.base import CRUDBase
from app.models.models import Organization, OrganizationMember, OrganizationRole, User
from app.schemas.organization import OrganizationCreate, OrganizationUpdate


class CRUDOrganization(CRUDBase[Organization, OrganizationCreate, OrganizationUpdate]):
    """CRUD operations for Organization model"""
    
    async def create_with_owner(
        self,
        db: AsyncSession,
        *,
        obj_in: OrganizationCreate,
        owner_id: UUID,
    ) -> Organization:
        """Create a new organization with owner"""
        organization = Organization(
            name=obj_in.name,
            description=obj_in.description,
        )
        
        db.add(organization)
        await db.flush()
        
        # Create owner membership
        owner_member = OrganizationMember(
            organization_id=organization.id,
            user_id=owner_id,
            role=OrganizationRole.OWNER,
        )
        
        db.add(owner_member)
        await db.flush()
        
        return organization
    
    async def get_organization_with_members(
        self, db: AsyncSession, id: UUID
    ) -> Optional[Organization]:
        """Get organization with members"""
        result = await db.execute(
            select(Organization)
            .options(joinedload(Organization.members).joinedload(OrganizationMember.user))
            .where(Organization.id == id)
        )
        return result.scalars().first()
    
    async def get_user_organizations(
        self,
        db: AsyncSession,
        *,
        user_id: UUID,
        skip: int = 0,
        limit: int = 100,
    ) -> List[Organization]:
        """Get organizations for a user"""
        result = await db.execute(
            select(Organization)
            .join(OrganizationMember, Organization.id == OrganizationMember.organization_id)
            .where(OrganizationMember.user_id == user_id)
            .order_by(Organization.name)
            .offset(skip)
            .limit(limit)
        )
        return result.scalars().all()
    
    async def get_member_role(
        self, db: AsyncSession, *, organization_id: UUID, user_id: UUID
    ) -> Optional[OrganizationRole]:
        """Get member role in organization"""
        result = await db.execute(
            select(OrganizationMember.role)
            .where(
                OrganizationMember.organization_id == organization_id,
                OrganizationMember.user_id == user_id,
            )
        )
        member = result.scalar_one_or_none()
        return member
    
    async def is_user_in_org(
        self, db: AsyncSession, *, organization_id: UUID, user_id: UUID
    ) -> bool:
        """Check if user is a member of the organization"""
        result = await db.execute(
            select(func.count())
            .where(
                OrganizationMember.organization_id == organization_id,
                OrganizationMember.user_id == user_id,
            )
        )
        count = result.scalar_one()
        return count > 0
    
    async def add_member(
        self,
        db: AsyncSession,
        *,
        organization_id: UUID,
        user_id: UUID,
        role: OrganizationRole = OrganizationRole.MEMBER,
    ) -> OrganizationMember:
        """Add a member to the organization"""
        member = OrganizationMember(
            organization_id=organization_id,
            user_id=user_id,
            role=role,
        )
        
        db.add(member)
        await db.flush()
        await db.refresh(member)
        return member
    
    async def remove_member(
        self, db: AsyncSession, *, organization_id: UUID, user_id: UUID
    ) -> bool:
        """Remove a member from the organization"""
        result = await db.execute(
            select(OrganizationMember)
            .where(
                OrganizationMember.organization_id == organization_id,
                OrganizationMember.user_id == user_id,
            )
        )
        member = result.scalar_one_or_none()
        
        if not member:
            return False
        
        await db.delete(member)
        await db.commit()
        return True
    
    async def update_member_role(
        self,
        db: AsyncSession,
        *,
        organization_id: UUID,
        user_id: UUID,
        role: OrganizationRole,
    ) -> Optional[OrganizationMember]:
        """Update member role"""
        result = await db.execute(
            select(OrganizationMember)
            .where(
                OrganizationMember.organization_id == organization_id,
                OrganizationMember.user_id == user_id,
            )
        )
        member = result.scalar_one_or_none()
        
        if not member:
            return None
        
        member.role = role
        
        db.add(member)
        await db.commit()
        await db.refresh(member)
        return member
    
    async def add_credits(
        self, db: AsyncSession, organization_id: UUID, credits: int
    ) -> Organization:
        """Add interview credits to organization"""
        organization = await self.get(db, id=organization_id)
        if not organization:
            raise ValueError(f"Organization {organization_id} not found")
        
        organization.available_interview_credits += credits
        await db.commit()
        await db.refresh(organization)
        return organization
    
    async def add_chat_tokens(
        self, db: AsyncSession, organization_id: UUID, tokens: int
    ) -> Organization:
        """Add chat tokens to organization"""
        organization = await self.get(db, id=organization_id)
        if not organization:
            raise ValueError(f"Organization {organization_id} not found")
        
        organization.available_chat_tokens += tokens
        await db.commit()
        await db.refresh(organization)
        return organization


organization_crud = CRUDOrganization(Organization)