from typing import Optional
from datetime import datetime
from pydantic import BaseModel


class Token(BaseModel):
    """Token schema for authentication response"""
    access_token: str
    refresh_token: str
    token_type: str = "bearer"


class TokenPayload(BaseModel):
    """Token payload schema (decoded JWT)"""
    sub: Optional[str] = None
    exp: Optional[datetime] = None
    type: Optional[str] = None


class RefreshToken(BaseModel):
    """Schema for refresh token request"""
    refresh_token: str