import uuid
from datetime import datetime
from typing import Any, Dict, List, Optional, Union

from pydantic import BaseModel, Field


class QuestionnaireBase(BaseModel):
    """Base Questionnaire schema"""
    title: str
    description: Optional[str] = None
    content: str


class QuestionnaireCreate(QuestionnaireBase):
    """Questionnaire creation schema"""
    pass


class QuestionnairePatch(BaseModel):
    """Questionnaire update schema with optional fields"""
    title: Optional[str] = None
    description: Optional[str] = None
    content: Optional[str] = None
    questions: Optional[List[str]] = None


class QuestionnaireOut(QuestionnaireBase):
    """Questionnaire output schema"""
    id: uuid.UUID
    created_at: datetime
    updated_at: Optional[datetime] = None
    questions: List[str]
    creator_id: uuid.UUID
    organization_id: Optional[uuid.UUID] = None
    interview_count: Optional[int] = Field(0, description="Number of interviews using this questionnaire")

    class Config:
        from_attributes = True


class QuestionExtractionRequest(BaseModel):
    """Request to extract questions from content"""
    content: str


class QuestionExtractionResponse(BaseModel):
    """Response with extracted questions"""
    questions: List[str]