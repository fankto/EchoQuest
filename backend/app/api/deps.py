from typing import Annotated, Optional, Union
import uuid
from contextlib import contextmanager

from fastapi import Depends, HTTPException, status, Path
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.exceptions import (
    AuthenticationError, AuthorizationError, ResourceNotFoundError,
    CredentialsException, PermissionDeniedException
)
from app.crud.crud_interview import interview_crud
from app.crud.crud_organization import organization_crud
from app.db.session import get_db
from app.models.models import Interview, Organization, User, UserRole, OrganizationRole
from app.services.token_service import token_service
from app.utils.rate_limit import rate_limiter

# OAuth2 scheme for token extraction
oauth2_scheme = OAuth2PasswordBearer(tokenUrl=f"{settings.API_V1_STR}/auth/login")


async def get_current_user(
        token: Annotated[str, Depends(oauth2_scheme)],
        db: AsyncSession = Depends(get_db),
) -> User:
    """
    Dependency for getting the current authenticated user.

    Args:
        token: OAuth2 token
        db: Database session

    Returns:
        User object

    Raises:
        AuthenticationError: If token is invalid or user does not exist
    """
    try:
        # Apply rate limiting
        await rate_limiter.check_rate_limit(token)

        # Decode token and get user
        user = await token_service.get_current_user(token, db)
        if not user:
            raise AuthenticationError("Invalid authentication credentials")
        return user
    except ValueError as e:
        raise AuthenticationError(str(e))


async def get_current_active_user(
        current_user: Annotated[User, Depends(get_current_user)],
) -> User:
    """
    Dependency for getting the current active user.

    Args:
        current_user: User from get_current_user dependency

    Returns:
        User object if active

    Raises:
        AuthorizationError: If user is inactive
    """
    if not current_user.is_active:
        raise AuthorizationError("Inactive user")
    return current_user


async def get_current_admin_user(
        current_user: Annotated[User, Depends(get_current_active_user)],
) -> User:
    """
    Dependency for getting the current admin user.

    Args:
        current_user: User from get_current_active_user dependency

    Returns:
        User object if admin

    Raises:
        AuthorizationError: If user is not an admin
    """
    if current_user.role != UserRole.ADMIN:
        raise AuthorizationError("Admin privileges required")
    return current_user


async def get_optional_user(
        token: Optional[str] = Depends(oauth2_scheme),
        db: AsyncSession = Depends(get_db),
) -> Optional[User]:
    """
    Dependency for getting the current user (if authenticated),
    but allowing unauthenticated access.

    Args:
        token: Optional OAuth2 token
        db: Database session

    Returns:
        User object if authenticated, None otherwise
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
        require_admin: bool = False,
) -> Interview:
    """
    Validate that the user has access to the interview.

    Args:
        db: Database session
        interview_id: Interview ID to check
        user_id: User ID to check access against
        require_admin: Whether to require admin permissions for organization interviews

    Returns:
        Interview object if access is valid

    Raises:
        ResourceNotFoundError: If interview doesn't exist
        AuthorizationError: If user doesn't have access
    """
    interview = await interview_crud.get(db, id=interview_id)
    if not interview:
        raise ResourceNotFoundError("Interview", str(interview_id))

    # Direct ownership
    if interview.owner_id == user_id:
        return interview

    # Organization access (if interview belongs to an organization)
    if interview.organization_id:
        org_role = await organization_crud.get_member_role(
            db,
            organization_id=interview.organization_id,
            user_id=user_id
        )

        # If admin access is required
        if require_admin and org_role not in [OrganizationRole.OWNER, OrganizationRole.ADMIN]:
            raise AuthorizationError("Admin or owner role required")

        # For regular access, any member role is sufficient
        if org_role in [OrganizationRole.OWNER, OrganizationRole.ADMIN, OrganizationRole.MEMBER]:
            return interview

    # If we reach here, user doesn't have access
    raise AuthorizationError("You don't have access to this interview")


async def validate_organization_access(
        db: AsyncSession,
        organization_id: uuid.UUID,
        user_id: uuid.UUID,
        require_admin: bool = False,
) -> Organization:
    """
    Validate that the user has access to the organization.

    Args:
        db: Database session
        organization_id: Organization ID to check
        user_id: User ID to check access against
        require_admin: Whether to require admin permissions

    Returns:
        Organization object if access is valid

    Raises:
        ResourceNotFoundError: If organization doesn't exist
        AuthorizationError: If user doesn't have access
    """
    organization = await organization_crud.get(db, id=organization_id)
    if not organization:
        raise ResourceNotFoundError("Organization", str(organization_id))

    # Check membership and role
    role = await organization_crud.get_member_role(
        db, organization_id=organization_id, user_id=user_id
    )

    if not role:
        raise AuthorizationError("Not a member of this organization")

    if require_admin and role not in [OrganizationRole.ADMIN, OrganizationRole.OWNER]:
        raise AuthorizationError("Admin or owner role required")

    return organization


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
        Organization object if user is admin/owner
    """
    return await validate_organization_access(db, organization_id, user_id, require_admin=True)


@contextmanager
async def db_transaction(db: AsyncSession):
    """
    Context manager for handling database transactions with proper error handling.

    Args:
        db: Database session

    Usage:
        async with db_transaction(db):
            # Database operations
    """
    try:
        yield
        await db.commit()
    except Exception as e:
        await db.rollback()
        raise e