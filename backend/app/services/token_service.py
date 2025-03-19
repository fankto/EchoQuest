import asyncio
from datetime import datetime, timedelta
from typing import Dict, Optional, Union
from uuid import UUID

import tiktoken
from fastapi import Depends, HTTPException, status
from jose import JWTError, jwt
from loguru import logger
from sqlalchemy.ext.asyncio import AsyncSession
import secrets
import string

from app.core.config import settings
from app.crud.crud_user import user_crud
from app.db.session import get_db
from app.models.models import User
from app.schemas.token import TokenPayload


class TokenService:
    """Service for handling JWT tokens and token estimation"""

    def __init__(self):
        try:
            # Try to get encoding for the specified model
            self.encoding = tiktoken.encoding_for_model(settings.OPENAI_CHAT_MODEL)
        except KeyError:
            # If the model isn't recognized (like gpt-4o-mini), use cl100k_base which is used for GPT-4 models
            logger.warning(f"Could not find tokenizer for {settings.OPENAI_CHAT_MODEL}, falling back to cl100k_base")
            self.encoding = tiktoken.get_encoding("cl100k_base")

        # Cache for users to avoid frequent database lookups
        self.user_cache = {}
        self.cache_timeout = 300  # 5 minutes

    def create_access_token(
            self,
            subject: Union[str, UUID, Dict],
            expires_delta: Optional[timedelta] = None,
            additional_claims: Optional[Dict] = None
    ) -> str:
        """
        Create JWT access token

        Args:
            subject: Subject identifier (user ID)
            expires_delta: Optional expiration time override
            additional_claims: Optional additional claims to include

        Returns:
            JWT token string
        """
        if expires_delta:
            expire = datetime.utcnow() + expires_delta
        else:
            expire = datetime.utcnow() + timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)

        to_encode = {"exp": expire, "sub": str(subject), "type": "access"}

        # Add additional claims if provided
        if additional_claims:
            to_encode.update(additional_claims)

        encoded_jwt = jwt.encode(
            to_encode,
            settings.JWT_SECRET,
            algorithm=settings.JWT_ALGORITHM
        )
        return encoded_jwt

    def create_refresh_token(
            self,
            subject: Union[str, UUID, Dict],
            additional_claims: Optional[Dict] = None
    ) -> str:
        """
        Create JWT refresh token

        Args:
            subject: Subject identifier (user ID)
            additional_claims: Optional additional claims to include

        Returns:
            JWT refresh token string
        """
        expire = datetime.utcnow() + timedelta(days=settings.REFRESH_TOKEN_EXPIRE_DAYS)

        to_encode = {"exp": expire, "sub": str(subject), "type": "refresh"}

        # Add additional claims if provided
        if additional_claims:
            to_encode.update(additional_claims)

        encoded_jwt = jwt.encode(
            to_encode,
            settings.JWT_SECRET,
            algorithm=settings.JWT_ALGORITHM
        )
        return encoded_jwt

    def decode_token(self, token: str) -> TokenPayload:
        """
        Decode JWT token

        Args:
            token: JWT token string

        Returns:
            Token payload

        Raises:
            ValueError: If token is invalid
        """
        try:
            payload = jwt.decode(
                token,
                settings.JWT_SECRET,
                algorithms=[settings.JWT_ALGORITHM]
            )
            token_data = TokenPayload(**payload)
            return token_data
        except JWTError as e:
            logger.error(f"Error decoding token: {e}")
            raise ValueError("Could not validate credentials")

    async def get_current_user(
            self, token: str, db: AsyncSession
    ) -> User:
        """
        Get current user from JWT token

        Args:
            token: JWT token string
            db: Database session

        Returns:
            User object

        Raises:
            ValueError: If token is invalid or user not found
        """
        try:
            payload = self.decode_token(token)
            user_id: str = payload.sub
            if not user_id:
                raise ValueError("Invalid authentication credentials")

            # Check cache first
            cached_user = self.user_cache.get(user_id)
            if cached_user and cached_user.get("expires_at", 0) > datetime.utcnow().timestamp():
                return cached_user["user"]

            # Get from database
            user = await user_crud.get(db, id=user_id)
            if not user:
                raise ValueError("User not found")

            # Cache user
            self.user_cache[user_id] = {
                "user": user,
                "expires_at": (datetime.utcnow() + timedelta(seconds=self.cache_timeout)).timestamp()
            }

            return user
        except (JWTError, ValueError) as e:
            logger.error(f"Error validating token: {e}")
            raise ValueError("Could not validate credentials")

    def count_tokens(self, text: str) -> int:
        """
        Count the number of tokens in a text

        Args:
            text: Text to count tokens in

        Returns:
            Number of tokens
        """
        if not text:
            return 0
        return len(self.encoding.encode(text))

    def count_message_tokens(self, messages: list) -> int:
        """
        Count the number of tokens in a list of chat messages

        Args:
            messages: List of chat messages

        Returns:
            Number of tokens
        """
        num_tokens = 0
        for message in messages:
            # Count tokens in the message
            if isinstance(message, dict):
                for key, value in message.items():
                    if key == "content" and value:
                        num_tokens += self.count_tokens(value)
                    elif key == "role" and value:
                        num_tokens += 1  # Add token for role
            elif isinstance(message, str):
                num_tokens += self.count_tokens(message)

        # Add tokens for ChatML format overhead
        num_tokens += 3  # Every reply is primed with <|start|>assistant<|message|>

        return num_tokens

    def generate_random_password(self, length: int = 16) -> str:
        """
        Generate a secure random password

        Args:
            length: Password length

        Returns:
            Random password string
        """
        # Use a mix of letters, digits, and punctuation for strong passwords
        alphabet = string.ascii_letters + string.digits + string.punctuation
        return ''.join(secrets.choice(alphabet) for _ in range(length))

    def clear_user_cache(self, user_id: Optional[str] = None) -> None:
        """
        Clear user cache

        Args:
            user_id: Optional specific user ID to clear, or all if None
        """
        if user_id:
            self.user_cache.pop(str(user_id), None)
        else:
            self.user_cache.clear()


# Create singleton instance
token_service = TokenService()