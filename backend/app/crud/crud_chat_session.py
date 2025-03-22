from typing import List, Optional
import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.models import ChatSession, ChatMessage


class CRUDChatSession:
    """CRUD operations for chat sessions"""
    
    async def create(
        self, 
        db: AsyncSession, 
        interview_id: uuid.UUID,
        title: str = "New Chat"
    ) -> ChatSession:
        """
        Create a new chat session
        
        Args:
            db: Database session
            interview_id: ID of the interview this session belongs to
            title: Session title (defaults to "New Chat")
            
        Returns:
            Created chat session
        """
        session = ChatSession(
            interview_id=interview_id,
            title=title
        )
        db.add(session)
        await db.flush()
        return session
    
    async def get(
        self, 
        db: AsyncSession, 
        session_id: uuid.UUID
    ) -> Optional[ChatSession]:
        """
        Get a chat session by ID
        
        Args:
            db: Database session
            session_id: Chat session ID
            
        Returns:
            Chat session if found, None otherwise
        """
        result = await db.execute(
            select(ChatSession).where(ChatSession.id == session_id)
        )
        return result.scalars().first()
    
    async def get_by_interview(
        self, 
        db: AsyncSession, 
        interview_id: uuid.UUID,
        skip: int = 0,
        limit: int = 100
    ) -> List[ChatSession]:
        """
        Get chat sessions for an interview
        
        Args:
            db: Database session
            interview_id: Interview ID
            skip: Number of records to skip
            limit: Maximum number of records to return
            
        Returns:
            List of chat sessions
        """
        result = await db.execute(
            select(ChatSession)
            .where(ChatSession.interview_id == interview_id)
            .order_by(ChatSession.updated_at.desc())
            .offset(skip)
            .limit(limit)
        )
        return list(result.scalars().all())
    
    async def update(
        self, 
        db: AsyncSession, 
        session_id: uuid.UUID, 
        title: str
    ) -> Optional[ChatSession]:
        """
        Update a chat session title
        
        Args:
            db: Database session
            session_id: Chat session ID
            title: New title
            
        Returns:
            Updated chat session if found, None otherwise
        """
        session = await self.get(db, session_id)
        if not session:
            return None
        
        session.title = title
        await db.flush()
        return session
    
    async def delete(
        self, 
        db: AsyncSession, 
        session_id: uuid.UUID
    ) -> bool:
        """
        Delete a chat session
        
        Args:
            db: Database session
            session_id: Chat session ID
            
        Returns:
            True if deleted, False if not found
        """
        session = await self.get(db, session_id)
        if not session:
            return False
        
        await db.delete(session)
        await db.flush()
        return True
    
    async def get_messages(
        self, 
        db: AsyncSession, 
        session_id: uuid.UUID
    ) -> List[ChatMessage]:
        """
        Get all messages for a chat session
        
        Args:
            db: Database session
            session_id: Chat session ID
            
        Returns:
            List of chat messages
        """
        result = await db.execute(
            select(ChatMessage)
            .where(ChatMessage.chat_session_id == session_id)
            .order_by(ChatMessage.created_at)
        )
        return list(result.scalars().all())


# Create a singleton instance
chat_session_crud = CRUDChatSession() 