from datetime import datetime
from typing import Any, Dict, List, Optional
from uuid import UUID

from pydantic import BaseModel, Field, ConfigDict

from app.schemas.base import IdentifiedBase


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

    model_config = ConfigDict(extra="ignore")


class QuestionnaireOut(QuestionnaireBase, IdentifiedBase):
    """Questionnaire output schema"""
    questions: List[str]
    creator_id: UUID
    organization_id: Optional[UUID] = None
    interview_count: Optional[int] = Field(0, description="Number of interviews using this questionnaire")


class QuestionnaireWithInterviews(QuestionnaireOut):
    """Questionnaire with associated interviews"""
    interviews: List[Dict[str, Any]] = []


class QuestionExtractionRequest(BaseModel):
    """Request to extract questions from content"""
    content: str


class QuestionExtractionResponse(BaseModel):
    """Response with extracted questions"""
    questions: List[str]