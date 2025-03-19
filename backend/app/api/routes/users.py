from typing import Any, List, Optional, Dict

from fastapi import APIRouter, Depends, HTTPException, Path, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_active_user, get_current_admin_user
from app.db.session import get_db
from app.crud.crud_user import user_crud
from app.crud.crud_transaction import transaction_crud
from app.models.models import User, UserRole
from app.schemas.user import UserCreate, UserOut, UserUpdate, UserAdminUpdate, UserWithStats
from app.services.email_service import email_service
from app.services.token_service import token_service

router = APIRouter()


@router.get("/me", response_model=UserWithStats)
async def read_user_me(
        current_user: User = Depends(get_current_active_user),
        db: AsyncSession = Depends(get_db),
) -> Any:
    """
    Get current user with statistics.
    """
    # Get interview count
    interview_count = await db.execute(
        f"SELECT COUNT(*) FROM interviews WHERE owner_id = '{current_user.id}'"
    )
    total_interviews = interview_count.scalar_one() or 0

    # Get questionnaire count
    questionnaire_count = await db.execute(
        f"SELECT COUNT(*) FROM questionnaires WHERE creator_id = '{current_user.id}'"
    )
    total_questionnaires = questionnaire_count.scalar_one() or 0

    # Get organization count
    organization_count = await db.execute(
        f"SELECT COUNT(*) FROM organization_members WHERE user_id = '{current_user.id}'"
    )
    total_organizations = organization_count.scalar_one() or 0

    # Get total credits used
    credits_used = await db.execute(
        f"SELECT COALESCE(SUM(amount), 0) FROM transactions WHERE user_id = '{current_user.id}' AND transaction_type = 'INTERVIEW_CREDIT_USAGE'"
    )
    total_credits_used = credits_used.scalar_one() or 0

    return {
        **current_user.__dict__,
        "interview_count": total_interviews,
        "questionnaire_count": total_questionnaires,
        "organization_count": total_organizations,
        "total_credits_used": total_credits_used
    }


@router.patch("/me", response_model=UserOut)
async def update_user_me(
        user_in: UserUpdate,
        current_user: User = Depends(get_current_active_user),
        db: AsyncSession = Depends(get_db),
) -> Any:
    """
    Update current user.
    """
    updated_user = await user_crud.update(db, db_obj=current_user, obj_in=user_in)
    await db.commit()

    # Clear user cache if email or password is updated
    if user_in.email or user_in.password:
        token_service.clear_user_cache(str(current_user.id))

    return updated_user


@router.post("/", response_model=UserOut, status_code=status.HTTP_201_CREATED,
             dependencies=[Depends(get_current_admin_user)])
async def create_user(
        user_in: UserCreate,
        db: AsyncSession = Depends(get_db),
) -> Any:
    """
    Create new user (admin only).
    """
    # Check if user with this email already exists
    user = await user_crud.get_by_email(db, email=user_in.email)
    if user:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Email already registered",
        )

    # Create new user
    user = await user_crud.create(db, obj_in=user_in)

    # Give new users some starter credits
    user.available_interview_credits = 1
    user.available_chat_tokens = 5000
    await db.commit()

    # Send welcome email
    await email_service.send_welcome_email(user.email, user.full_name or "User")

    return user


@router.get("/", response_model=List[UserOut], dependencies=[Depends(get_current_admin_user)])
async def read_users(
        skip: int = Query(0, ge=0, description="Number of users to skip"),
        limit: int = Query(100, ge=1, le=100, description="Maximum number of users to return"),
        db: AsyncSession = Depends(get_db),
) -> Any:
    """
    Retrieve users (admin only).
    """
    users = await user_crud.get_multi(db, skip=skip, limit=limit)
    return users


@router.get("/{user_id}", response_model=UserOut, dependencies=[Depends(get_current_admin_user)])
async def read_user(
        user_id: uuid.UUID = Path(..., description="The ID of the user to retrieve"),
        db: AsyncSession = Depends(get_db),
) -> Any:
    """
    Get user by ID (admin only).
    """
    user = await user_crud.get(db, id=user_id)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found",
        )
    return user


@router.patch("/{user_id}", response_model=UserOut, dependencies=[Depends(get_current_admin_user)])
async def update_user(
        user_id: uuid.UUID = Path(..., description="The ID of the user to update"),
        user_in: UserAdminUpdate = None,
        db: AsyncSession = Depends(get_db),
) -> Any:
    """
    Update user by ID (admin only).
    """
    user = await user_crud.get(db, id=user_id)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found",
        )

    updated_user = await user_crud.update(db, db_obj=user, obj_in=user_in)
    await db.commit()

    # Clear user cache
    token_service.clear_user_cache(str(user_id))

    return updated_user


@router.post("/{user_id}/activate", response_model=UserOut, dependencies=[Depends(get_current_admin_user)])
async def activate_user(
        user_id: uuid.UUID = Path(..., description="The ID of the user to activate"),
        db: AsyncSession = Depends(get_db),
) -> Any:
    """
    Activate a user (admin only).
    """
    user = await user_crud.get(db, id=user_id)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found",
        )

    if user.is_active:
        return user

    user.is_active = True
    db.add(user)
    await db.commit()
    await db.refresh(user)

    # Clear user cache
    token_service.clear_user_cache(str(user_id))

    return user


@router.post("/{user_id}/deactivate", response_model=UserOut, dependencies=[Depends(get_current_admin_user)])
async def deactivate_user(
        user_id: uuid.UUID = Path(..., description="The ID of the user to deactivate"),
        db: AsyncSession = Depends(get_db),
) -> Any:
    """
    Deactivate a user (admin only).
    """
    user = await user_crud.get(db, id=user_id)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found",
        )

    if user.role == UserRole.ADMIN:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cannot deactivate admin user",
        )

    if not user.is_active:
        return user

    user.is_active = False
    db.add(user)
    await db.commit()
    await db.refresh(user)

    # Clear user cache
    token_service.clear_user_cache(str(user_id))

    return user