import asyncio
from datetime import datetime, timedelta
from typing import Dict, Optional, Union

import tiktoken
from fastapi import Depends
from jose import JWTError, jwt
from loguru import logger
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.crud.crud_user import user_crud
from app.db.session import get_db
from app.models.models import User
from app.schemas.token import TokenPayload


class TokenService:
    """Service for handling JWT tokens and token estimation"""
    
    def __init__(self):
        self.encoding = tiktoken.encoding_for_model(settings.OPENAI_CHAT_MODEL)
    
    def create_access_token(self, subject: Union[str, Dict], expires_delta: Optional[timedelta] = None) -> str:
        """
        Create JWT access token
        """
        if expires_delta:
            expire = datetime.utcnow() + expires_delta
        else:
            expire = datetime.utcnow() + timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
        
        to_encode = {"exp": expire, "sub": str(subject)}
        encoded_jwt = jwt.encode(to_encode, settings.JWT_SECRET, algorithm=settings.JWT_ALGORITHM)
        return encoded_jwt
    
    def create_refresh_token(self, subject: Union[str, Dict]) -> str:
        """
        Create JWT refresh token
        """
        expire = datetime.utcnow() + timedelta(days=settings.REFRESH_TOKEN_EXPIRE_DAYS)
        to_encode = {"exp": expire, "sub": str(subject), "type": "refresh"}
        encoded_jwt = jwt.encode(to_encode, settings.JWT_SECRET, algorithm=settings.JWT_ALGORITHM)
        return encoded_jwt
    
    def decode_token(self, token: str) -> TokenPayload:
        """
        Decode JWT token
        """
        try:
            payload = jwt.decode(token, settings.JWT_SECRET, algorithms=[settings.JWT_ALGORITHM])
            token_data = TokenPayload(**payload)
            return token_data
        except JWTError as e:
            logger.error(f"Error decoding token: {e}")
            raise ValueError("Could not validate credentials")
    
    async def get_current_user(
        self, token: str, db: AsyncSession = Depends(get_db)
    ) -> User:
        """
        Get current user from JWT token
        """
        try:
            payload = self.decode_token(token)
            user_id: str = payload.sub
            if not user_id:
                raise ValueError("Invalid authentication credentials")
        except (JWTError, ValueError) as e:
            logger.error(f"Error validating token: {e}")
            raise ValueError("Could not validate credentials")
        
        user = await user_crud.get(db, id=user_id)
        if not user:
            raise ValueError("User not found")
        if not user.is_active:
            raise ValueError("Inactive user")
        
        return user
    
    def count_tokens(self, text: str) -> int:
        """
        Count the number of tokens in a text
        """
        return len(self.encoding.encode(text))
    
    def count_message_tokens(self, messages: list) -> int:
        """
        Count the number of tokens in a list of chat messages
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


# Create singleton instance
token_service = TokenService()