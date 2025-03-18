import uuid
from datetime import datetime
from typing import List, Optional, Dict, Any

from pydantic import BaseModel, Field


class ChatMessageBase(BaseModel):
    """Base schema for chat message"""
    role: str
    content: str


class ChatMessageCreate(ChatMessageBase):
    """Create schema for chat message"""
    interview_id: uuid.UUID
    user_id: uuid.UUID
    tokens_used: int = 0
    chat_session_id: Optional[uuid.UUID] = None


class ChatMessageOut(ChatMessageBase):
    """Output schema for chat message"""
    id: uuid.UUID
    created_at: datetime
    chat_session_id: Optional[uuid.UUID] = None

    class Config:
        orm_mode = True


class ChatRequest(BaseModel):
    """Schema for chat request"""
    message: str
    chat_session_id: Optional[uuid.UUID] = None


class ChatResponse(BaseModel):
    """Schema for chat response"""
    user_message: ChatMessageOut
    assistant_message: ChatMessageOut
    remaining_tokens: int
    chat_session_id: Optional[uuid.UUID] = None


class ChatSessionBase(BaseModel):
    """Base schema for chat session"""
    title: str = "New Chat"


class ChatSessionCreate(ChatSessionBase):
    """Create schema for chat session"""
    pass


class ChatSessionUpdate(BaseModel):
    """Update schema for chat session"""
    title: str


class ChatSessionOut(ChatSessionBase):
    """Output schema for chat session"""
    id: uuid.UUID
    interview_id: uuid.UUID
    created_at: datetime
    updated_at: datetime

    class Config:
        orm_mode = True


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