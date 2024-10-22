# backend/src/questionnaire_manager/schemas.py
from pydantic import BaseModel, validator
from typing import List, Union, Dict
from datetime import datetime

class InterviewBrief(BaseModel):
    id: int
    interviewee_name: str
    date: datetime
    status: str

    class Config:
        orm_mode = True

class QuestionnaireBase(BaseModel):
    title: str
    content: str
    file_type: str

class QuestionnaireCreate(QuestionnaireBase):
    pass

class Questionnaire(QuestionnaireBase):
    id: int
    questions: Union[List[str], Dict[str, List[str]]]
    created_at: datetime
    updated_at: datetime
    title: str
    content: str
    file_type: str
    interviews: List[InterviewBrief]

    @validator('questions', pre=True)
    def format_questions(cls, v):
        if isinstance(v, dict) and 'items' in v:
            return v['items']
        return v

    @validator('updated_at', pre=True)
    def set_updated_at(cls, v, values):
        return v or values.get('created_at')

    class Config:
        from_attributes = True
        orm_mode = True
