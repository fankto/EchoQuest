from typing import Any, Dict, List, Optional
import uuid

from fastapi import APIRouter, Depends, HTTPException, Path, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_active_user, validate_organization_admin
from app.core.config import settings
from app.crud.crud_organization import organization_crud
from app.crud.crud_user import user_crud
from app.crud.crud_transaction import transaction_crud
from app.db.session import get_db
from app.models.models import Organization, OrganizationRole, User, TransactionType
from app.schemas.organization import (
    OrganizationCreate,
    OrganizationInvite,
    OrganizationInviteResponse,
    OrganizationMemberCreate,
    OrganizationMemberOut,
    OrganizationMemberUpdate,
    OrganizationOut,
    OrganizationUpdate,
    OrganizationWithMembers,
)
from app.services.email_service import email_service
from app.utils.security import create_invitation_token
from app.utils.pagination import get_pagination_params

router = APIRouter()


@router.post("/", response_model=OrganizationOut, status_code=status.HTTP_201_CREATED)
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

    # Initialize with some default credits
    organization.available_interview_credits = 10
    organization.available_chat_tokens = 50000

    await db.commit()
    await db.refresh(organization)

    return {
        **organization.__dict__,
        "member_count": 1,
        "user_role": OrganizationRole.OWNER.value
    }


@router.get("/", response_model=List[OrganizationOut])
async def read_organizations(
        current_user: User = Depends(get_current_active_user),
        page: int = Query(1, ge=1, description="Page number"),
        size: int = Query(10, ge=1, le=100, description="Page size"),
        db: AsyncSession = Depends(get_db),
) -> Any:
    """
    Retrieve organizations for current user.
    """
    # Calculate skip based on page and size
    skip = (page - 1) * size

    organizations = await organization_crud.get_user_organizations(
        db, user_id=current_user.id, skip=skip, limit=size
    )

    return organizations


@router.get("/{organization_id}", response_model=OrganizationWithMembers)
async def read_organization(
        organization_id: uuid.UUID = Path(..., description="The ID of the organization to retrieve"),
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

    # Format response
    members = []
    for member in organization.members:
        members.append({
            "id": member.id,
            "user_id": member.user_id,
            "organization_id": member.organization_id,
            "role": member.role,
            "email": member.user.email,
            "full_name": member.user.full_name,
            "created_at": member.created_at
        })

    return {
        **organization.__dict__,
        "members": members
    }


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
    # Validate admin access and get organization
    organization = await validate_organization_admin(db, organization_id, current_user.id)

    # Update organization
    updated_organization = await organization_crud.update(
        db, db_obj=organization, obj_in=organization_in
    )

    await db.commit()
    await db.refresh(updated_organization)

    # Get user's role in the organization
    role = await organization_crud.get_member_role(
        db, organization_id=organization_id, user_id=current_user.id
    )

    # Get member count
    member_count = len(updated_organization.members) if hasattr(updated_organization, "members") else 0

    return {
        **updated_organization.__dict__,
        "member_count": member_count,
        "user_role": role.value if role else None
    }


@router.get("/{organization_id}/members", response_model=List[OrganizationMemberOut])
async def list_organization_members(
        organization_id: uuid.UUID = Path(..., description="The ID of the organization"),
        page: int = Query(1, ge=1, description="Page number"),
        size: int = Query(50, ge=1, le=100, description="Page size"),
        current_user: User = Depends(get_current_active_user),
        db: AsyncSession = Depends(get_db),
) -> Any:
    """
    List members of an organization.
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

    # Calculate skip based on page and size
    skip = (page - 1) * size

    # Get members with user details
    members = await organization_crud.get_organization_members(
        db, organization_id=organization_id, skip=skip, limit=size
    )

    return members


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
    # Validate admin access and get organization
    organization = await validate_organization_admin(db, organization_id, current_user.id)

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
        # Update role if already a member
        member = await organization_crud.update_member_role(
            db, organization_id=organization_id, user_id=user.id, role=member_in.role
        )

        await db.commit()

        return OrganizationMemberOut(
            id=member.id,
            user_id=user.id,
            organization_id=organization_id,
            role=member.role,
            email=user.email,
            full_name=user.full_name,
            created_at=member.created_at
        )

    # Add member
    member = await organization_crud.add_member(
        db, organization_id=organization_id, user_id=user.id, role=member_in.role
    )

    await db.commit()

    return OrganizationMemberOut(
        id=member.id,
        user_id=user.id,
        organization_id=organization_id,
        role=member.role,
        email=user.email,
        full_name=user.full_name,
        created_at=member.created_at
    )


@router.post("/{organization_id}/invite", response_model=OrganizationInviteResponse)
async def invite_organization_member(
        organization_id: uuid.UUID,
        invite_in: OrganizationInvite,
        current_user: User = Depends(get_current_active_user),
        db: AsyncSession = Depends(get_db),
) -> Any:
    """
    Invite user to organization via email.
    """
    # Validate admin access and get organization
    organization = await validate_organization_admin(db, organization_id, current_user.id)

    # Create invitation token (contains org id, email, role, inviter id)
    invitation_data = {
        "organization_id": str(organization_id),
        "email": invite_in.email,
        "role": invite_in.role.value,
        "inviter_id": str(current_user.id)
    }

    invite_token = create_invitation_token(invitation_data)

    # Create invitation URL
    invite_url = f"{settings.FRONTEND_URL}/organizations/accept-invite?token={invite_token}"

    # Send invitation email
    email_sent = await email_service.send_organization_invite(
        invite_in.email, organization.name, invite_url
    )

    if not email_sent:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to send invitation email",
        )

    return {
        "success": True,
        "message": f"Invitation sent to {invite_in.email}",
        "invite_url": invite_url
    }


@router.delete("/{organization_id}/members/{user_id}", status_code=status.HTTP_204_NO_CONTENT)
async def remove_organization_member(
        organization_id: uuid.UUID,
        user_id: uuid.UUID,
        current_user: User = Depends(get_current_active_user),
        db: AsyncSession = Depends(get_db),
) -> None:
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

    # Check if organization exists
    organization = await organization_crud.get(db, id=organization_id)
    if not organization:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Organization not found",
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

    await db.commit()


@router.patch("/{organization_id}/members/{user_id}/role", response_model=OrganizationMemberOut)
async def update_member_role(
        organization_id: uuid.UUID,
        user_id: uuid.UUID,
        role_update: OrganizationMemberUpdate,
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

    # Get organization
    organization = await organization_crud.get(db, id=organization_id)
    if not organization:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Organization not found",
        )

    # Update role
    member = await organization_crud.update_member_role(
        db, organization_id=organization_id, user_id=user_id, role=role_update.role
    )

    if not member:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Member not found",
        )

    await db.commit()

    # Get user details for response
    user = await user_crud.get(db, id=user_id)

    return OrganizationMemberOut(
        id=member.id,
        user_id=user.id,
        organization_id=organization_id,
        role=member.role,
        email=user.email,
        full_name=user.full_name,
        created_at=member.created_at
    )


@router.get("/{organization_id}/transactions", response_model=Dict)
async def get_organization_transactions(
        organization_id: uuid.UUID,
        page: int = Query(1, ge=1, description="Page number"),
        size: int = Query(20, ge=1, le=100, description="Page size"),
        current_user: User = Depends(get_current_active_user),
        db: AsyncSession = Depends(get_db),
) -> Any:
    """
    Get organization transaction history
    """
    # Validate admin access and get organization
    organization = await validate_organization_admin(db, organization_id, current_user.id)

    # Calculate skip
    skip = (page - 1) * size

    # Get transactions
    transactions = await transaction_crud.get_organization_transactions(
        db, organization_id=organization_id, skip=skip, limit=size
    )

    # Format for output
    result = {
        "transactions": [
            {
                "id": str(t.id),
                "transaction_type": t.transaction_type.value,
                "amount": t.amount,
                "price": t.price,
                "reference": t.reference,
                "created_at": t.created_at.isoformat(),
                "user_id": str(t.user_id),
                "interview_id": str(t.interview_id) if t.interview_id else None,
            }
            for t in transactions
        ],
        "total": len(transactions),
        "page": page,
        "size": size
    }

    return result