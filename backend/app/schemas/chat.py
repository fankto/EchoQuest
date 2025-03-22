from datetime import datetime
from typing import List, Optional, Dict, Any
from uuid import UUID

from pydantic import BaseModel, Field, ConfigDict

from app.schemas.base import IdentifiedBase


class ChatMessageBase(BaseModel):
    """Base schema for chat message"""
    role: str
    content: str


class ChatMessageCreate(ChatMessageBase):
    """Create schema for chat message"""
    interview_id: UUID
    user_id: UUID
    tokens_used: int = 0
    chat_session_id: Optional[UUID] = None


class ChatMessageOut(ChatMessageBase, IdentifiedBase):
    """Output schema for chat message"""
    interview_id: UUID
    user_id: UUID
    tokens_used: int = 0
    chat_session_id: Optional[UUID] = None


class ChatRequest(BaseModel):
    """Schema for chat request"""
    message: str
    chat_session_id: Optional[UUID] = None


class ChatResponse(BaseModel):
    """Schema for chat response"""
    user_message: ChatMessageOut
    assistant_message: ChatMessageOut
    remaining_tokens: int
    chat_session_id: Optional[UUID] = None


class ChatSessionBase(BaseModel):
    """Base schema for chat session"""
    title: str = "New Chat"


class ChatSessionCreate(ChatSessionBase):
    """Create schema for chat session"""
    pass


class ChatSessionUpdate(BaseModel):
    """Update schema for chat session"""
    title: str

    model_config = ConfigDict(extra="ignore")


class ChatSessionOut(ChatSessionBase, IdentifiedBase):
    """Output schema for chat session"""
    interview_id: UUID
    message_count: Optional[int] = None
    latest_message: Optional[str] = None
    latest_message_time: Optional[datetime] = None


class TranscriptMatch(BaseModel):
    """Transcript match from vector search"""
    text: str
    start_time: Optional[float] = None
    end_time: Optional[float] = None
    speaker: Optional[str] = None
    chunk_index: Optional[int] = None
    score: float


class TranscriptSearchRequest(BaseModel):
    """Request to search transcript"""
    query: str
    limit: int = 5


class TranscriptSearchResponse(BaseModel):
    """Response with transcript search results"""
    matches: List[TranscriptMatch]