# src/interview_manager/models.py

from sqlalchemy import Column, Integer, String, Float, Text, DateTime, ForeignKey, JSON, ARRAY
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

from ..database import Base


class Interview(Base):
    __tablename__ = "interviews"

    id = Column(Integer, primary_key=True, index=True)
    interviewee_name = Column(String, index=True)
    date = Column(DateTime(timezone=True), default=func.now())
    location = Column(String)
    original_filenames = Column(JSON)
    processed_filenames = Column(JSON)
    status = Column(String)
    duration = Column(Float)
    transcriptions = Column(JSON)
    merged_transcription = Column(Text)
    generated_answers = Column(JSON)
    progress = Column(Float, default=0.0)
    error_message = Column(Text)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
    min_speakers = Column(Integer, nullable=True)
    max_speakers = Column(Integer, nullable=True)

    questionnaire_id = Column(Integer, ForeignKey('questionnaires.id'))
    questionnaire = relationship("Questionnaire", back_populates="interviews")

    interview_metadata = relationship("InterviewMetadata", back_populates="interview")
    extracted_answers = relationship("ExtractedAnswer", back_populates="interview")

class InterviewMetadata(Base):
    __tablename__ = "interview_metadata"

    id = Column(Integer, primary_key=True, index=True)
    interview_id = Column(Integer, ForeignKey('interviews.id'))
    key = Column(String, index=True)
    value = Column(String)

    interview = relationship("Interview", back_populates="interview_metadata")


class ExtractedAnswer(Base):
    __tablename__ = "extracted_answers"

    id = Column(Integer, primary_key=True, index=True)
    interview_id = Column(Integer, ForeignKey('interviews.id'))
    question = Column(String)
    answer = Column(Text)

    interview = relationship("Interview", back_populates="extracted_answers")

