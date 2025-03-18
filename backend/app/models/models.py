import uuid
from datetime import datetime
from enum import Enum
from typing import List, Optional

from sqlalchemy import (
    Boolean, Column, DateTime, Float, ForeignKey, Integer, 
    String, Text, JSON, func, Enum as SQLAEnum, Table
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
    chat_messages = relationship("ChatMessage", back_populates="user")
    
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


# Association table for many-to-many relationship between Interview and Questionnaire
interview_questionnaire = Table(
    "interview_questionnaire",
    Base.metadata,
    Column("interview_id", UUID(as_uuid=True), ForeignKey("interviews.id"), primary_key=True),
    Column("questionnaire_id", UUID(as_uuid=True), ForeignKey("questionnaires.id"), primary_key=True),
    Column("created_at", DateTime(timezone=True), server_default=func.now()),
)

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
    interviews = relationship("Interview", secondary=interview_questionnaire, back_populates="questionnaires")


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
    
    # Generated answers - update to store answers by questionnaire ID
    generated_answers = Column(JSON, nullable=True)  # Now a dictionary mapping questionnaire_id to answers
    
    # Error information
    error_message = Column(Text, nullable=True)
    
    # References - keep this for backward compatibility during migration
    questionnaire_id = Column(UUID(as_uuid=True), ForeignKey("questionnaires.id"), nullable=True)
    owner_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    organization_id = Column(UUID(as_uuid=True), ForeignKey("organizations.id"), nullable=True)
    
    # Token usage
    remaining_chat_tokens = Column(Integer, default=0)
    
    # Timestamps
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
    
    # Relationships - keep the direct relationship for backward compatibility
    questionnaire = relationship("Questionnaire", foreign_keys=[questionnaire_id])
    # Add the many-to-many relationship
    questionnaires = relationship("Questionnaire", secondary=interview_questionnaire, back_populates="interviews")
    owner = relationship("User", back_populates="interviews")
    organization = relationship("Organization", back_populates="interviews")
    chat_messages = relationship("ChatMessage", back_populates="interview", cascade="all, delete-orphan")
    chat_sessions = relationship("ChatSession", back_populates="interview", cascade="all, delete-orphan")


class ChatMessage(Base):
    """Model for chat messages"""
    __tablename__ = "chat_messages"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4, index=True)
    interview_id = Column(UUID(as_uuid=True), ForeignKey("interviews.id", ondelete="CASCADE"), nullable=False)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    role = Column(String, nullable=False)  # "user" or "assistant"
    content = Column(Text, nullable=False)
    tokens_used = Column(Integer, default=0, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    chat_session_id = Column(UUID(as_uuid=True), ForeignKey("chat_sessions.id", ondelete="CASCADE"), nullable=True)

    # Relationships
    interview = relationship("Interview", back_populates="chat_messages")
    user = relationship("User", back_populates="chat_messages")
    chat_session = relationship("ChatSession", back_populates="messages")


class ChatSession(Base):
    """Model for chat sessions (conversations)"""
    __tablename__ = "chat_sessions"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4, index=True)
    interview_id = Column(UUID(as_uuid=True), ForeignKey("interviews.id", ondelete="CASCADE"), nullable=False)
    title = Column(String, nullable=False, default="New Chat")
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)
    
    # Relationships
    interview = relationship("Interview", back_populates="chat_sessions")
    messages = relationship("ChatMessage", back_populates="chat_session", cascade="all, delete-orphan")


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