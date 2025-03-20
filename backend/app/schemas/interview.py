from datetime import datetime
from typing import Dict, List, Optional, Any
from uuid import UUID
import json

from pydantic import BaseModel, Field, validator, ConfigDict

from app.models.models import InterviewStatus
from app.schemas.base import IdentifiedBase


class TranscriptSegment(BaseModel):
    """Transcript segment schema"""
    text: str
    start_time: float
    end_time: float
    speaker: str = "Speaker"
    words: List[Dict[str, Any]] = []


class InterviewBase(BaseModel):
    """Base Interview schema with common attributes"""
    title: str
    interviewee_name: str
    date: datetime
    location: Optional[str] = None
    notes: Optional[str] = None


class InterviewCreate(InterviewBase):
    """Interview creation schema"""
    questionnaire_id: Optional[UUID] = None


class InterviewPatch(BaseModel):
    """Interview update schema with optional fields"""
    title: Optional[str] = None
    interviewee_name: Optional[str] = None
    date: Optional[datetime] = None
    location: Optional[str] = None
    notes: Optional[str] = None

    model_config = ConfigDict(extra="ignore")


class InterviewOut(InterviewBase, IdentifiedBase):
    """Interview output schema"""
    status: InterviewStatus
    duration: Optional[float] = None
    error_message: Optional[str] = None
    original_filenames: Optional[List[str]] = None
    processed_filenames: Optional[List[str]] = None
    owner_id: UUID
    organization_id: Optional[UUID] = None
    remaining_chat_tokens: Optional[int] = None

    @validator('original_filenames', pre=True)
    def parse_original_filenames(cls, v):
        if isinstance(v, str):
            try:
                return json.loads(v)
            except json.JSONDecodeError:
                return []
        return v

    @validator('processed_filenames', pre=True)
    def parse_processed_filenames(cls, v):
        if isinstance(v, str):
            try:
                return json.loads(v)
            except json.JSONDecodeError:
                return []
        return v


class InterviewDetailOut(InterviewOut):
    """Interview detail output schema with transcription and answers"""
    transcription: Optional[str] = None
    transcript_segments: Optional[List[TranscriptSegment]] = None
    generated_answers: Optional[Dict[str, Dict[str, str]]] = None
    questionnaires: Optional[List[Dict[str, Any]]] = None


class InterviewWithQuestionnaire(InterviewOut):
    """Interview output schema with questionnaire"""
    questionnaire: Optional[Dict[str, Any]] = None


class InterviewTaskResponse(BaseModel):
    """Response for interview processing tasks"""
    status: str
    message: str
    task_id: Optional[str] = None


class TranscriptUpdateRequest(BaseModel):
    """Request schema for updating transcript text"""
    transcription: str


class TranscriptSegmentsUpdateRequest(BaseModel):
    """Request schema for updating transcript segments"""
    segments: List[TranscriptSegment]


class AudioUrlResponse(BaseModel):
    """Response schema for audio URL"""
    audio_url: str
    is_processed: bool
    duration: Optional[float] = None