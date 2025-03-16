import uuid
from datetime import datetime
from typing import Dict, List, Optional, Any, Union

from pydantic import BaseModel, Field

from app.models.models import InterviewStatus


class TranscriptSegment(BaseModel):
    """Transcript segment schema"""
    text: str
    start_time: float
    end_time: float
    speaker: str = "Speaker"


class InterviewBase(BaseModel):
    """Base Interview schema with common attributes"""
    title: str
    interviewee_name: str
    date: datetime
    location: Optional[str] = None
    notes: Optional[str] = None


class InterviewCreate(InterviewBase):
    """Interview creation schema"""
    questionnaire_id: Optional[uuid.UUID] = None


class InterviewPatch(BaseModel):
    """Interview update schema with optional fields"""
    title: Optional[str] = None
    interviewee_name: Optional[str] = None
    date: Optional[datetime] = None
    location: Optional[str] = None
    notes: Optional[str] = None
    questionnaire_id: Optional[uuid.UUID] = None


class InterviewOut(InterviewBase):
    """Interview output schema"""
    id: uuid.UUID
    status: InterviewStatus
    created_at: datetime
    updated_at: Optional[datetime] = None
    duration: Optional[float] = None
    error_message: Optional[str] = None
    original_filenames: Optional[List[str]] = None
    processed_filenames: Optional[List[str]] = None
    questionnaire_id: Optional[uuid.UUID] = None
    owner_id: uuid.UUID
    organization_id: Optional[uuid.UUID] = None
    remaining_chat_tokens: Optional[int] = None
    
    class Config:
        from_attributes = True


class InterviewDetailOut(InterviewOut):
    """Interview detail output schema with transcription and answers"""
    transcription: Optional[str] = None
    transcript_segments: Optional[List[TranscriptSegment]] = None
    generated_answers: Optional[Dict[str, str]] = None
    
    class Config:
        from_attributes = True


class InterviewWithQuestionnaire(InterviewOut):
    """Interview output schema with questionnaire"""
    questionnaire: Optional[Dict[str, Any]] = None
    
    class Config:
        from_attributes = True


class InterviewTaskResponse(BaseModel):
    """Response for interview processing tasks"""
    status: str
    message: str