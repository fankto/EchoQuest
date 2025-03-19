from typing import List, Optional, Dict, Any
import uuid
from datetime import datetime

from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.models import ChatSession, ChatMessage, Interview


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
            title=title,
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow()
        )
        db.add(session)
        await db.flush()
        await db.refresh(session)
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
    ) -> List[Dict[str, Any]]:
        """
        Get chat sessions for an interview with message counts

        Args:
            db: Database session
            interview_id: Interview ID
            skip: Number of records to skip
            limit: Maximum number of records to return

        Returns:
            List of chat sessions with message counts
        """
        # Get the chat sessions
        result = await db.execute(
            select(ChatSession)
            .where(ChatSession.interview_id == interview_id)
            .order_by(ChatSession.updated_at.desc())
            .offset(skip)
            .limit(limit)
        )
        sessions = result.scalars().all()

        # Get message counts for each session
        result_list = []
        for session in sessions:
            # Get message count
            count_query = select(func.count()) \
                .select_from(ChatMessage) \
                .where(ChatMessage.chat_session_id == session.id)

            count_result = await db.execute(count_query)
            message_count = count_result.scalar_one()

            # Get latest message for preview
            latest_query = select(ChatMessage) \
                .where(ChatMessage.chat_session_id == session.id) \
                .order_by(ChatMessage.created_at.desc()) \
                .limit(1)

            latest_result = await db.execute(latest_query)
            latest_message = latest_result.scalars().first()

            # Prepare session dict with extra info
            session_dict = {
                **session.__dict__,
                "message_count": message_count,
                "latest_message": latest_message.content[:100] + "..." if latest_message and len(
                    latest_message.content) > 100 else latest_message.content if latest_message else None,
                "latest_message_time": latest_message.created_at if latest_message else None
            }

            # Remove SQLAlchemy state attributes
            session_dict.pop('_sa_instance_state', None)

            result_list.append(session_dict)

        return result_list

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
        session.updated_at = datetime.utcnow()

        db.add(session)
        await db.flush()
        await db.refresh(session)
        return session

    async def update_timestamp(
            self,
            db: AsyncSession,
            session_id: uuid.UUID
    ) -> Optional[ChatSession]:
        """
        Update chat session timestamp

        Args:
            db: Database session
            session_id: Chat session ID

        Returns:
            Updated chat session if found, None otherwise
        """
        session = await self.get(db, session_id)
        if not session:
            return None

        session.updated_at = datetime.utcnow()

        db.add(session)
        await db.flush()
        await db.refresh(session)
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
            session_id: uuid.UUID,
            skip: int = 0,
            limit: int = 100
    ) -> List[ChatMessage]:
        """
        Get all messages for a chat session

        Args:
            db: Database session
            session_id: Chat session ID
            skip: Number of records to skip
            limit: Maximum number of records to return

        Returns:
            List of chat messages
        """
        result = await db.execute(
            select(ChatMessage)
            .where(ChatMessage.chat_session_id == session_id)
            .order_by(ChatMessage.created_at)
            .offset(skip)
            .limit(limit)
        )
        return result.scalars().all()


# Create a singleton instance
chat_session_crud = CRUDChatSession()