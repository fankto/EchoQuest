from typing import Any, List

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_active_user, get_current_admin_user
from app.db.session import get_db
from app.crud.crud_user import user_crud
from app.models.models import User, UserRole
from app.schemas.user import UserCreate, UserOut, UserUpdate
from app.services.email_service import email_service

router = APIRouter()


@router.get("/me", response_model=UserOut)
async def read_user_me(
    current_user: User = Depends(get_current_active_user),
) -> Any:
    """
    Get current user.
    """
    return current_user


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
    return updated_user


@router.post("/", response_model=UserOut, dependencies=[Depends(get_current_admin_user)])
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
    
    # Send welcome email
    await email_service.send_welcome_email(user.email, user.full_name or "User")
    
    return user


@router.get("/", response_model=List[UserOut], dependencies=[Depends(get_current_admin_user)])
async def read_users(
    skip: int = 0,
    limit: int = 100,
    db: AsyncSession = Depends(get_db),
) -> Any:
    """
    Retrieve users (admin only).
    """
    users = await user_crud.get_multi(db, skip=skip, limit=limit)
    return users


@router.get("/{user_id}", response_model=UserOut, dependencies=[Depends(get_current_admin_user)])
async def read_user(
    user_id: str,
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
    user_id: str,
    user_in: UserUpdate,
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
    return updated_user


@router.post("/{user_id}/activate", response_model=UserOut, dependencies=[Depends(get_current_admin_user)])
async def activate_user(
    user_id: str,
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
    return user


@router.post("/{user_id}/deactivate", response_model=UserOut, dependencies=[Depends(get_current_admin_user)])
async def deactivate_user(
    user_id: str,
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
    return user