import uuid
from typing import Any, List

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi_pagination import Page
from fastapi_pagination.ext.sqlalchemy import paginate
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_active_user
from app.core.config import settings
from app.crud.crud_organization import organization_crud
from app.crud.crud_user import user_crud
from app.db.session import get_db
from app.models.models import Organization, OrganizationRole, User
from app.schemas.organization import (
    OrganizationCreate,
    OrganizationInvite,
    OrganizationMemberCreate,
    OrganizationMemberOut,
    OrganizationOut,
    OrganizationUpdate,
    OrganizationWithMembers,
)
from app.services.email_service import email_service

router = APIRouter()


@router.post("/", response_model=OrganizationOut)
async def create_organization(
    organization_in: OrganizationCreate,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
) -> Any:
    """
    Create new organization.
    """
    organization = await organization_crud.create_with_owner(
        db, obj_in=organization_in, owner_id=current_user.id
    )
    return organization


@router.get("/", response_model=List[OrganizationOut])
async def read_organizations(
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
) -> Any:
    """
    Retrieve organizations for current user.
    """
    organizations = await organization_crud.get_user_organizations(
        db, user_id=current_user.id
    )
    return organizations


@router.get("/{organization_id}", response_model=OrganizationWithMembers)
async def read_organization(
    organization_id: uuid.UUID,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
) -> Any:
    """
    Get organization by ID.
    """
    # Check if user is a member of the organization
    is_member = await organization_crud.is_user_in_org(
        db, organization_id=organization_id, user_id=current_user.id
    )
    if not is_member:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not a member of this organization",
        )
    
    organization = await organization_crud.get_organization_with_members(
        db, id=organization_id
    )
    if not organization:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Organization not found",
        )
    
    return organization


@router.patch("/{organization_id}", response_model=OrganizationOut)
async def update_organization(
    organization_id: uuid.UUID,
    organization_in: OrganizationUpdate,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
) -> Any:
    """
    Update organization.
    """
    # Check if user is an admin or owner of the organization
    role = await organization_crud.get_member_role(
        db, organization_id=organization_id, user_id=current_user.id
    )
    if not role or role not in [OrganizationRole.ADMIN, OrganizationRole.OWNER]:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not an admin of this organization",
        )
    
    organization = await organization_crud.get(db, id=organization_id)
    if not organization:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Organization not found",
        )
    
    updated_organization = await organization_crud.update(
        db, db_obj=organization, obj_in=organization_in
    )
    return updated_organization


@router.post("/{organization_id}/members", response_model=OrganizationMemberOut)
async def add_organization_member(
    organization_id: uuid.UUID,
    member_in: OrganizationMemberCreate,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
) -> Any:
    """
    Add member to organization.
    """
    # Check if user is an admin or owner of the organization
    role = await organization_crud.get_member_role(
        db, organization_id=organization_id, user_id=current_user.id
    )
    if not role or role not in [OrganizationRole.ADMIN, OrganizationRole.OWNER]:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not an admin of this organization",
        )
    
    # Check if organization exists
    organization = await organization_crud.get(db, id=organization_id)
    if not organization:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Organization not found",
        )
    
    # Get user by email
    user = await user_crud.get_by_email(db, email=member_in.email)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"User with email {member_in.email} not found",
        )
    
    # Check if user is already a member
    is_member = await organization_crud.is_user_in_org(
        db, organization_id=organization_id, user_id=user.id
    )
    if is_member:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="User is already a member of this organization",
        )
    
    # Add member
    member = await organization_crud.add_member(
        db, organization_id=organization_id, user_id=user.id, role=member_in.role
    )
    
    return OrganizationMemberOut(
        id=member.id,
        user_id=user.id,
        organization_id=organization_id,
        role=member.role,
        email=user.email,
        full_name=user.full_name,
    )


@router.post("/{organization_id}/invite", response_model=dict)
async def invite_organization_member(
    organization_id: uuid.UUID,
    invite_in: OrganizationInvite,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
) -> Any:
    """
    Invite user to organization via email.
    """
    # Check if user is an admin or owner of the organization
    role = await organization_crud.get_member_role(
        db, organization_id=organization_id, user_id=current_user.id
    )
    if not role or role not in [OrganizationRole.ADMIN, OrganizationRole.OWNER]:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not an admin of this organization",
        )
    
    # Check if organization exists
    organization = await organization_crud.get(db, id=organization_id)
    if not organization:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Organization not found",
        )
    
    # Create invitation link
    invite_token = str(uuid.uuid4())
    invite_url = f"{settings.FRONTEND_URL}/organizations/accept-invite?token={invite_token}&email={invite_in.email}&organization={organization_id}"
    
    # Send invitation email
    email_sent = await email_service.send_organization_invite(
        invite_in.email, organization.name, invite_url
    )
    
    if not email_sent:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to send invitation email",
        )
    
    # In a real system, save the invitation to database with expiration
    
    return {"message": "Invitation sent successfully"}


@router.delete("/{organization_id}/members/{user_id}", response_model=dict)
async def remove_organization_member(
    organization_id: uuid.UUID,
    user_id: uuid.UUID,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
) -> Any:
    """
    Remove member from organization.
    """
    # Check if user is an admin or owner of the organization
    role = await organization_crud.get_member_role(
        db, organization_id=organization_id, user_id=current_user.id
    )
    if not role or role not in [OrganizationRole.ADMIN, OrganizationRole.OWNER]:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not an admin of this organization",
        )
    
    # Prevent removing yourself if you're the owner
    if current_user.id == user_id and role == OrganizationRole.OWNER:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cannot remove yourself as the owner",
        )
    
    # Prevent removing another owner if you're just an admin
    if role == OrganizationRole.ADMIN:
        member_role = await organization_crud.get_member_role(
            db, organization_id=organization_id, user_id=user_id
        )
        if member_role == OrganizationRole.OWNER:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Cannot remove an owner as an admin",
            )
    
    # Remove member
    removed = await organization_crud.remove_member(
        db, organization_id=organization_id, user_id=user_id
    )
    
    if not removed:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Member not found",
        )
    
    return {"message": "Member removed successfully"}


@router.patch("/{organization_id}/members/{user_id}/role", response_model=OrganizationMemberOut)
async def update_member_role(
    organization_id: uuid.UUID,
    user_id: uuid.UUID,
    role: OrganizationRole,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
) -> Any:
    """
    Update member role.
    """
    # Check if user is an owner of the organization
    current_role = await organization_crud.get_member_role(
        db, organization_id=organization_id, user_id=current_user.id
    )
    if not current_role or current_role != OrganizationRole.OWNER:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only organization owners can update roles",
        )
    
    # Update role
    member = await organization_crud.update_member_role(
        db, organization_id=organization_id, user_id=user_id, role=role
    )
    
    if not member:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Member not found",
        )
    
    # Get user details for response
    user = await user_crud.get(db, id=user_id)
    
    return OrganizationMemberOut(
        id=member.id,
        user_id=user.id,
        organization_id=organization_id,
        role=member.role,
        email=user.email,
        full_name=user.full_name,
    )