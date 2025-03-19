from typing import Optional, Dict, Any
from datetime import datetime

from pydantic import BaseModel, ConfigDict


class Token(BaseModel):
    """Token schema for authentication response"""
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    expires_at: int  # Unix timestamp


class TokenData(BaseModel):
    """Token data for decoded JWT tokens"""
    sub: str
    exp: datetime
    type: str

    # Optional claims
    user_id: Optional[str] = None
    email: Optional[str] = None
    role: Optional[str] = None
    organization_id: Optional[str] = None

    model_config = ConfigDict(extra="allow")


class TokenPayload(BaseModel):
    """Token payload schema (decoded JWT)"""
    sub: Optional[str] = None
    exp: Optional[datetime] = None
    type: Optional[str] = None

    # Make the model accept any additional fields
    model_config = ConfigDict(extra="allow")


class RefreshToken(BaseModel):
    """Schema for refresh token request"""
    refresh_token: str