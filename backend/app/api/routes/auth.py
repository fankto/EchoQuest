from datetime import datetime, timedelta
from typing import Any, Dict, Optional
import httpx

from fastapi import APIRouter, Depends, HTTPException, status, Request, Response
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user
from app.core.config import settings
from app.crud.crud_user import user_crud
from app.db.session import get_db
from app.models.models import User
from app.schemas.token import Token, RefreshToken
from app.schemas.user import UserCreate, UserOut, PasswordReset, PasswordResetConfirm
from app.services.token_service import token_service
from app.services.email_service import email_service
from app.utils.security import create_password_reset_token, verify_password_reset_token

router = APIRouter()


@router.post("/login", response_model=Token)
async def login(
        db: AsyncSession = Depends(get_db),
        form_data: OAuth2PasswordRequestForm = Depends(),
        response: Response = None,
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

    # Create additional claims
    claims = {
        "email": user.email,
        "role": user.role.value
    }

    # Create tokens
    access_token = token_service.create_access_token(
        subject=str(user.id),
        expires_delta=access_token_expires,
        additional_claims=claims
    )

    refresh_token = token_service.create_refresh_token(
        subject=str(user.id),
        additional_claims=claims
    )

    # Calculate expiration timestamp
    expires_at = int((datetime.utcnow() + access_token_expires).timestamp())

    # Set refresh token in HTTP-only cookie if response is provided
    if response:
        response.set_cookie(
            key="refresh_token",
            value=refresh_token,
            httponly=True,
            max_age=settings.REFRESH_TOKEN_EXPIRE_DAYS * 24 * 3600,
            samesite="lax",
            secure=settings.ENVIRONMENT == "production"
        )

    return {
        "access_token": access_token,
        "refresh_token": refresh_token,
        "token_type": "bearer",
        "expires_at": expires_at
    }


@router.post("/refresh", response_model=Token)
async def refresh_token(
        refresh_data: RefreshToken = None,
        db: AsyncSession = Depends(get_db),
        request: Request = None,
) -> Any:
    """
    Refresh access token using refresh token from body or cookie
    """
    # Get refresh token from request body or cookie
    token = None
    if refresh_data and refresh_data.refresh_token:
        token = refresh_data.refresh_token
    elif request and "refresh_token" in request.cookies:
        token = request.cookies.get("refresh_token")

    if not token:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Missing refresh token",
        )

    try:
        # Decode refresh token
        payload = token_service.decode_token(token)
        if payload.type != "refresh":
            raise ValueError("Invalid token type")

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

        # Create additional claims
        claims = {
            "email": user.email,
            "role": user.role.value
        }

        # Create new access token
        access_token_expires = timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
        access_token = token_service.create_access_token(
            subject=str(user.id),
            expires_delta=access_token_expires,
            additional_claims=claims
        )

        # Calculate expiration timestamp
        expires_at = int((datetime.utcnow() + access_token_expires).timestamp())

        return {
            "access_token": access_token,
            "refresh_token": token,  # Return the same refresh token
            "token_type": "bearer",
            "expires_at": expires_at
        }
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=f"Invalid refresh token: {str(e)}",
        )


@router.get("/me", response_model=UserOut)
async def read_users_me(
        current_user: User = Depends(get_current_user),
) -> Any:
    """
    Get current user
    """
    return current_user


@router.post("/register", response_model=UserOut, status_code=status.HTTP_201_CREATED)
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

    # Give new users some starter credits
    user.available_interview_credits = 1
    user.available_chat_tokens = 5000
    await db.commit()
    await db.refresh(user)

    # Send welcome email
    await email_service.send_welcome_email(user.email, user.full_name or "User")

    return user


@router.post("/password-reset", response_model=Dict[str, str])
async def request_password_reset(
        reset_request: PasswordReset,
        db: AsyncSession = Depends(get_db),
) -> Any:
    """
    Request password reset
    """
    user = await user_crud.get_by_email(db, email=reset_request.email)
    if not user:
        # Don't reveal that the user doesn't exist
        return {"message": "If your email is registered, you will receive a password reset link"}

    # Create password reset token
    token = create_password_reset_token(user.id)

    # Send email with reset link
    await email_service.send_password_reset(user.email, token)

    return {"message": "If your email is registered, you will receive a password reset link"}


@router.post("/password-reset/confirm", response_model=Dict[str, str])
async def confirm_password_reset(
        reset_confirm: PasswordResetConfirm,
        db: AsyncSession = Depends(get_db),
) -> Any:
    """
    Confirm password reset
    """
    # Verify token
    user_id = verify_password_reset_token(reset_confirm.token)
    if not user_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid or expired token",
        )

    # Get user
    user = await user_crud.get(db, id=user_id)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found",
        )

    # Update password
    user_in = {"password": reset_confirm.password}
    await user_crud.update(db, db_obj=user, obj_in=user_in)

    # Clear user cache to force re-login
    token_service.clear_user_cache(str(user.id))

    return {"message": "Password updated successfully"}


@router.post("/auth0/token", response_model=Token)
async def auth0_token(
        code: str,
        db: AsyncSession = Depends(get_db),
        response: Response = None,
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

        async with httpx.AsyncClient(timeout=30.0) as client:
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

                # Give new users some starter credits
                user.available_interview_credits = 1
                user.available_chat_tokens = 5000
                await db.commit()
                await db.refresh(user)

            # Create additional claims
            claims = {
                "email": user.email,
                "role": user.role.value,
                "auth0_id": user_info.get("sub")
            }

            # Generate our own tokens
            access_token_expires = timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
            access_token = token_service.create_access_token(
                subject=str(user.id),
                expires_delta=access_token_expires,
                additional_claims=claims
            )

            refresh_token = token_service.create_refresh_token(
                subject=str(user.id),
                additional_claims=claims
            )

            # Calculate expiration timestamp
            expires_at = int((datetime.utcnow() + access_token_expires).timestamp())

            # Set refresh token in HTTP-only cookie if response is provided
            if response:
                response.set_cookie(
                    key="refresh_token",
                    value=refresh_token,
                    httponly=True,
                    max_age=settings.REFRESH_TOKEN_EXPIRE_DAYS * 24 * 3600,
                    samesite="lax",
                    secure=settings.ENVIRONMENT == "production"
                )

            return {
                "access_token": access_token,
                "refresh_token": refresh_token,
                "token_type": "bearer",
                "expires_at": expires_at
            }
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Auth0 authentication failed: {str(e)}",
        )