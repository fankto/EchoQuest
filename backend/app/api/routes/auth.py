from datetime import timedelta
from typing import Any, Dict, Optional
import httpx

from fastapi import APIRouter, Depends, HTTPException, status, Request
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user
from app.core.config import settings
from app.crud.crud_user import user_crud
from app.db.session import get_db
from app.models.models import User
from app.schemas.token import Token
from app.schemas.user import UserCreate, UserOut
from app.services.token_service import token_service
from app.services.email_service import email_service

router = APIRouter()


@router.post("/login", response_model=Token)
async def login(
    db: AsyncSession = Depends(get_db),
    form_data: OAuth2PasswordRequestForm = Depends(),
) -> Any:
    """
    OAuth2 compatible token login, get an access token for future requests
    """
    user = await user_crud.authenticate(
        db, email=form_data.username, password=form_data.password
    )
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect email or password",
        )
    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="Inactive user"
        )
    
    access_token_expires = timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    refresh_token_expires = timedelta(days=settings.REFRESH_TOKEN_EXPIRE_DAYS)
    
    return {
        "access_token": token_service.create_access_token(
            subject=str(user.id), expires_delta=access_token_expires
        ),
        "refresh_token": token_service.create_refresh_token(
            subject=str(user.id)
        ),
        "token_type": "bearer",
    }


@router.post("/refresh", response_model=Token)
async def refresh_token(
    refresh_token: str,
    db: AsyncSession = Depends(get_db),
) -> Any:
    """
    Refresh access token
    """
    try:
        # Decode refresh token
        payload = token_service.decode_token(refresh_token)
        user_id = payload.sub
        
        # Check if user exists
        user = await user_crud.get(db, id=user_id)
        if not user:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="User not found",
            )
        if not user.is_active:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Inactive user",
            )
        
        access_token_expires = timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
        
        return {
            "access_token": token_service.create_access_token(
                subject=str(user.id), expires_delta=access_token_expires
            ),
            "refresh_token": refresh_token,
            "token_type": "bearer",
        }
    except Exception:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid refresh token",
        )


@router.get("/me", response_model=dict)
async def read_users_me(
    current_user: User = Depends(get_current_user),
) -> Any:
    """
    Get current user
    """
    return {
        "id": str(current_user.id),
        "email": current_user.email,
        "full_name": current_user.full_name,
        "role": current_user.role,
        "available_interview_credits": current_user.available_interview_credits,
        "available_chat_tokens": current_user.available_chat_tokens,
    }


@router.post("/register", response_model=UserOut)
async def register(
    user_in: UserCreate,
    db: AsyncSession = Depends(get_db),
) -> Any:
    """
    Register a new user
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


@router.post("/auth0/token", response_model=Token)
async def auth0_token(
    code: str,
    db: AsyncSession = Depends(get_db),
) -> Any:
    """
    Exchange Auth0 authorization code for access token
    """
    try:
        # Exchange code for Auth0 tokens
        token_url = f"https://{settings.AUTH0_DOMAIN}/oauth/token"
        token_payload = {
            "grant_type": "authorization_code",
            "client_id": settings.AUTH0_CLIENT_ID,
            "client_secret": settings.AUTH0_CLIENT_SECRET,
            "code": code,
            "redirect_uri": settings.AUTH0_CALLBACK_URL,
        }
        
        async with httpx.AsyncClient() as client:
            token_response = await client.post(token_url, json=token_payload)
            token_data = token_response.json()
            
            if "error" in token_data:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Auth0 error: {token_data.get('error_description', token_data['error'])}",
                )
            
            # Get user info from Auth0
            user_info_url = f"https://{settings.AUTH0_DOMAIN}/userinfo"
            user_info_response = await client.get(
                user_info_url,
                headers={"Authorization": f"Bearer {token_data['access_token']}"},
            )
            user_info = user_info_response.json()
            
            # Check if user exists in our database
            user = await user_crud.get_by_email(db, email=user_info["email"])
            
            if not user:
                # Create new user
                user_create = UserCreate(
                    email=user_info["email"],
                    password=token_service.generate_random_password(),  # Generate a random password
                    full_name=user_info.get("name", ""),
                )
                user = await user_crud.create(db, obj_in=user_create)
            
            # Generate our own tokens
            access_token_expires = timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
            refresh_token_expires = timedelta(days=settings.REFRESH_TOKEN_EXPIRE_DAYS)
            
            return {
                "access_token": token_service.create_access_token(
                    subject=str(user.id), expires_delta=access_token_expires
                ),
                "refresh_token": token_service.create_refresh_token(
                    subject=str(user.id)
                ),
                "token_type": "bearer",
            }
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Auth0 authentication failed: {str(e)}",
        )