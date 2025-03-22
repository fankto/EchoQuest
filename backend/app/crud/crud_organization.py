from typing import List, Optional, Dict, Any
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
        await db.refresh(organization)

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
    ) -> List[Dict[str, Any]]:
        """Get organizations for a user with member counts"""
        # First get basic organizations
        query = select(Organization) \
            .join(OrganizationMember, Organization.id == OrganizationMember.organization_id) \
            .where(OrganizationMember.user_id == user_id) \
            .order_by(Organization.name) \
            .offset(skip).limit(limit)

        result = await db.execute(query)
        organizations = result.scalars().all()

        # Get member count for each organization
        result_list = []
        for org in organizations:
            # Get member count
            count_query = select(func.count()) \
                .select_from(OrganizationMember) \
                .where(OrganizationMember.organization_id == org.id)

            count_result = await db.execute(count_query)
            member_count = count_result.scalar_one()

            # Get user's role in the organization
            role_query = select(OrganizationMember.role) \
                .where(
                OrganizationMember.organization_id == org.id,
                OrganizationMember.user_id == user_id
            )

            role_result = await db.execute(role_query)
            user_role = role_result.scalar_one_or_none()

            # Convert to dict and add count and role
            org_dict = {
                **org.__dict__,
                "member_count": member_count,
                "user_role": user_role.value if user_role else None,
            }

            # Remove SQLAlchemy state attributes
            org_dict.pop('_sa_instance_state', None)

            result_list.append(org_dict)

        return result_list

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
        role = result.scalar_one_or_none()
        return role

    async def is_user_in_org(
            self, db: AsyncSession, *, organization_id: UUID, user_id: UUID
    ) -> bool:
        """Check if user is a member of the organization"""
        result = await db.execute(
            select(func.count())
            .select_from(OrganizationMember)
            .where(
                OrganizationMember.organization_id == organization_id,
                OrganizationMember.user_id == user_id,
            )
        )
        count = result.scalar_one()
        return count > 0

    async def get_organization_members(
            self,
            db: AsyncSession,
            *,
            organization_id: UUID,
            skip: int = 0,
            limit: int = 100,
    ) -> List[Dict[str, Any]]:
        """Get members of an organization with user details"""
        query = select(OrganizationMember, User) \
            .join(User, OrganizationMember.user_id == User.id) \
            .where(OrganizationMember.organization_id == organization_id) \
            .order_by(OrganizationMember.role) \
            .offset(skip).limit(limit)

        result = await db.execute(query)
        members_with_users = result.all()

        result_list = []
        for member, user in members_with_users:
            member_dict = {
                "id": member.id,
                "user_id": user.id,
                "organization_id": member.organization_id,
                "role": member.role,
                "email": user.email,
                "full_name": user.full_name,
                "created_at": member.created_at
            }
            result_list.append(member_dict)

        return result_list

    async def add_member(
            self,
            db: AsyncSession,
            *,
            organization_id: UUID,
            user_id: UUID,
            role: OrganizationRole = OrganizationRole.MEMBER,
    ) -> OrganizationMember:
        """Add a member to the organization"""
        # Check if member already exists
        existing = await db.execute(
            select(OrganizationMember)
            .where(
                OrganizationMember.organization_id == organization_id,
                OrganizationMember.user_id == user_id,
            )
        )
        existing_member = existing.scalar_one_or_none()

        if existing_member:
            # Update role if different
            if existing_member.role != role:
                existing_member.role = role
                db.add(existing_member)
                await db.flush()
                await db.refresh(existing_member)
            return existing_member

        # Create new member
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
        await db.flush()
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
        await db.flush()
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
        db.add(organization)
        await db.flush()
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
        db.add(organization)
        await db.flush()
        await db.refresh(organization)
        return organization


organization_crud = CRUDOrganization(Organization)