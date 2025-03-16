import uuid
from datetime import datetime
from typing import List, Optional

from pydantic import BaseModel, Field


class ChatMessageBase(BaseModel):
    """Base Chat Message schema"""
    interview_id: uuid.UUID
    role: str = Field(..., description="Either 'user' or 'assistant'")
    content: str = Field(..., description="Message content")


class ChatMessageCreate(ChatMessageBase):
    """Chat Message creation schema"""
    user_id: uuid.UUID
    tokens_used: int = Field(0, description="Tokens used for this message")


class ChatMessageOut(BaseModel):
    """Chat Message output schema"""
    id: uuid.UUID
    interview_id: uuid.UUID
    role: str
    content: str
    created_at: datetime
    tokens_used: Optional[int] = None
    
    class Config:
        from_attributes = True


class ChatRequest(BaseModel):
    """Chat request schema"""
    message: str = Field(..., description="User message to send")


class ChatResponse(BaseModel):
    """Chat response schema"""
    user_message: ChatMessageOut
    assistant_message: ChatMessageOut
    remaining_tokens: int


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