# src/questionnaire_manager/models.py
import datetime

from pydantic import BaseModel
from sqlalchemy import Column, Integer, String, Text, DateTime, JSON
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

from ..database import Base


class Questionnaire(Base):
    __tablename__ = "questionnaires"

    id = Column(Integer, primary_key=True, index=True)
    title = Column(String, index=True)
    description = Column(Text, nullable=True)
    content = Column(Text)
    file_type = Column(String)
    questions = Column(JSON)  # Store extracted questions as JSON
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(),onupdate=func.now())

    interviews = relationship("Interview", back_populates="questionnaire")

    @property
    def formatted_questions(self):
        if isinstance(self.questions, dict) and 'items' in self.questions:
            return self.questions['items']
        return self.questions
