import uuid
from datetime import datetime
from enum import Enum
from typing import List, Optional

from sqlalchemy import (
    Boolean, Column, DateTime, Float, ForeignKey, Integer, 
    String, Text, JSON, func, Enum as SQLAEnum
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship

from app.db.base_class import Base


class UserRole(str, Enum):
    """User role enum"""
    ADMIN = "admin"
    USER = "user"


class InterviewStatus(str, Enum):
    """Interview status enum"""
    CREATED = "created"
    UPLOADED = "uploaded"
    PROCESSING = "processing"
    PROCESSED = "processed"
    TRANSCRIBING = "transcribing"
    TRANSCRIBED = "transcribed"
    ERROR = "error"


class User(Base):
    """User model"""
    __tablename__ = "users"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    email = Column(String, unique=True, index=True, nullable=False)
    hashed_password = Column(String, nullable=False)
    full_name = Column(String, nullable=True)
    is_active = Column(Boolean, default=True)
    role = Column(SQLAEnum(UserRole), default=UserRole.USER)
    
    # Timestamps
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
    
    # Relationships
    organizations = relationship("OrganizationMember", back_populates="user")
    interviews = relationship("Interview", back_populates="owner")
    questionnaires = relationship("Questionnaire", back_populates="creator")
    
    # Credits
    available_interview_credits = Column(Integer, default=0)
    available_chat_tokens = Column(Integer, default=0)
    
    # Transactions
    transactions = relationship("Transaction", back_populates="user")


class Organization(Base):
    """Organization model"""
    __tablename__ = "organizations"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name = Column(String, nullable=False)
    description = Column(Text, nullable=True)
    
    # Organization credits
    available_interview_credits = Column(Integer, default=0)
    available_chat_tokens = Column(Integer, default=0)
    
    # Timestamps
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
    
    # Relationships
    members = relationship("OrganizationMember", back_populates="organization")
    interviews = relationship("Interview", back_populates="organization")
    questionnaires = relationship("Questionnaire", back_populates="organization")


class OrganizationRole(str, Enum):
    """Organization role enum"""
    OWNER = "owner"
    ADMIN = "admin"
    MEMBER = "member"


class OrganizationMember(Base):
    """Organization member model"""
    __tablename__ = "organization_members"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    organization_id = Column(UUID(as_uuid=True), ForeignKey("organizations.id"), nullable=False)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    role = Column(SQLAEnum(OrganizationRole), default=OrganizationRole.MEMBER)
    
    # Timestamps
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
    
    # Relationships
    organization = relationship("Organization", back_populates="members")
    user = relationship("User", back_populates="organizations")


class Questionnaire(Base):
    """Questionnaire model"""
    __tablename__ = "questionnaires"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    title = Column(String, nullable=False)
    description = Column(Text, nullable=True)
    content = Column(Text, nullable=False)
    questions = Column(JSON, nullable=False)  # List of questions
    
    # Ownership
    creator_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    organization_id = Column(UUID(as_uuid=True), ForeignKey("organizations.id"), nullable=True)
    
    # Timestamps
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
    
    # Relationships
    creator = relationship("User", back_populates="questionnaires")
    organization = relationship("Organization", back_populates="questionnaires")
    interviews = relationship("Interview", back_populates="questionnaire")


class Interview(Base):
    """Interview model"""
    __tablename__ = "interviews"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    title = Column(String, nullable=False)
    interviewee_name = Column(String, nullable=False)
    date = Column(DateTime(timezone=True), default=datetime.utcnow)
    location = Column(String, nullable=True)
    notes = Column(Text, nullable=True)
    status = Column(SQLAEnum(InterviewStatus), default=InterviewStatus.CREATED)
    
    # Audio related fields
    original_filenames = Column(JSON, nullable=True)  # List of original filenames
    processed_filenames = Column(JSON, nullable=True)  # List of processed filenames
    duration = Column(Float, nullable=True)  # Duration in seconds
    
    # Transcription related fields
    transcription = Column(Text, nullable=True)  # Full transcription text
    transcript_segments = Column(JSON, nullable=True)  # Detailed transcript segments with timestamps
    language = Column(String, nullable=True)
    
    # Generated answers
    generated_answers = Column(JSON, nullable=True)  # Answers to questionnaire questions
    
    # Error information
    error_message = Column(Text, nullable=True)
    
    # References
    questionnaire_id = Column(UUID(as_uuid=True), ForeignKey("questionnaires.id"), nullable=True)
    owner_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    organization_id = Column(UUID(as_uuid=True), ForeignKey("organizations.id"), nullable=True)
    
    # Token usage
    remaining_chat_tokens = Column(Integer, default=0)
    
    # Timestamps
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
    
    # Relationships
    questionnaire = relationship("Questionnaire", back_populates="interviews")
    owner = relationship("User", back_populates="interviews")
    organization = relationship("Organization", back_populates="interviews")
    chat_messages = relationship("ChatMessage", back_populates="interview")


class ChatMessage(Base):
    """Chat message model for interview conversations"""
    __tablename__ = "chat_messages"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    interview_id = Column(UUID(as_uuid=True), ForeignKey("interviews.id"), nullable=False)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    role = Column(String, nullable=False)  # 'user' or 'assistant'
    content = Column(Text, nullable=False)
    tokens_used = Column(Integer, nullable=False, default=0)  # Number of tokens used
    
    # Timestamps
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    
    # Relationships
    interview = relationship("Interview", back_populates="chat_messages")


class TransactionType(str, Enum):
    """Transaction type enum"""
    INTERVIEW_CREDIT_PURCHASE = "interview_credit_purchase"
    CHAT_TOKEN_PURCHASE = "chat_token_purchase"
    INTERVIEW_CREDIT_USAGE = "interview_credit_usage"
    CHAT_TOKEN_USAGE = "chat_token_usage"


class Transaction(Base):
    """Transaction model for tracking credit purchases and usage"""
    __tablename__ = "transactions"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    organization_id = Column(UUID(as_uuid=True), ForeignKey("organizations.id"), nullable=True)
    interview_id = Column(UUID(as_uuid=True), ForeignKey("interviews.id"), nullable=True)
    
    transaction_type = Column(SQLAEnum(TransactionType), nullable=False)
    amount = Column(Integer, nullable=False)  # Number of credits or tokens
    price = Column(Float, nullable=True)  # Price paid (if a purchase)
    reference = Column(String, nullable=True)  # Reference number or other identifier
    
    # Timestamps
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    
    # Relationships
    user = relationship("User", back_populates="transactions")