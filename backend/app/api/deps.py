from typing import Annotated, Optional, Union
import uuid

from fastapi import Depends, HTTPException, status, Path
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.crud.crud_interview import interview_crud
from app.crud.crud_organization import organization_crud
from app.db.session import get_db
from app.models.models import Interview, Organization, User, UserRole, OrganizationRole
from app.services.token_service import token_service
from app.utils.rate_limit import RateLimiter

# OAuth2 scheme for token extraction
oauth2_scheme = OAuth2PasswordBearer(tokenUrl=f"{settings.API_V1_STR}/auth/login")

# Rate limiter
rate_limiter = RateLimiter()


async def get_current_user(
        token: Annotated[str, Depends(oauth2_scheme)],
        db: AsyncSession = Depends(get_db),
) -> User:
    """
    Dependency for getting the current authenticated user.
    """
    try:
        # Apply rate limiting
        await rate_limiter.check_rate_limit(token)

        # Decode token
        user = await token_service.get_current_user(token, db)
        return user
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=str(e),
            headers={"WWW-Authenticate": "Bearer"},
        )


async def get_current_active_user(
        current_user: Annotated[User, Depends(get_current_user)],
) -> User:
    """
    Dependency for getting the current active user.
    """
    if not current_user.is_active:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Inactive user",
        )
    return current_user


async def get_current_admin_user(
        current_user: Annotated[User, Depends(get_current_active_user)],
) -> User:
    """
    Dependency for getting the current admin user.
    """
    if current_user.role != UserRole.ADMIN:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Insufficient permissions",
        )
    return current_user


async def get_optional_user(
        token: Optional[str] = Depends(oauth2_scheme),
        db: AsyncSession = Depends(get_db),
) -> Optional[User]:
    """
    Dependency for getting the current user (if authenticated),
    but allowing unauthenticated access.
    """
    if not token:
        return None

    try:
        user = await token_service.get_current_user(token, db)
        if not user.is_active:
            return None
        return user
    except Exception:
        return None


async def validate_interview_ownership(
        db: AsyncSession,
        interview_id: uuid.UUID,
        user_id: uuid.UUID,
) -> Interview:
    """
    Validate that the user owns the interview.

    Args:
        db: Database session
        interview_id: Interview ID to check
        user_id: User ID to check ownership against

    Returns:
        Interview object if ownership is valid

    Raises:
        HTTPException if interview doesn't exist or user doesn't own it
    """
    interview = await interview_crud.get(db, id=interview_id)
    if not interview:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Interview not found",
        )

    # Check ownership
    if interview.owner_id != user_id:
        # Check organization access (if interview belongs to an organization)
        has_org_access = False
        if interview.organization_id:
            org_role = await organization_crud.get_member_role(
                db,
                organization_id=interview.organization_id,
                user_id=user_id
            )
            if org_role in [OrganizationRole.OWNER, OrganizationRole.ADMIN, OrganizationRole.MEMBER]:
                has_org_access = True

        if not has_org_access:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Not enough permissions",
            )

    return interview


async def validate_organization_admin(
        db: AsyncSession,
        organization_id: uuid.UUID,
        user_id: uuid.UUID,
) -> Organization:
    """
    Validate that the user is an admin of the organization.

    Args:
        db: Database session
        organization_id: Organization ID to check
        user_id: User ID to check admin role against

    Returns:
        Organization object if user is admin

    Raises:
        HTTPException if organization doesn't exist or user isn't admin
    """
    organization = await organization_crud.get(db, id=organization_id)
    if not organization:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Organization not found",
        )

    # Check admin role
    role = await organization_crud.get_member_role(
        db, organization_id=organization_id, user_id=user_id
    )
    if not role or role not in [OrganizationRole.ADMIN, OrganizationRole.OWNER]:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not an admin of this organization",
        )

    return organization