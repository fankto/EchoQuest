import uuid
from typing import Any, List, Dict

from fastapi import APIRouter, Depends, HTTPException, Path, Query, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from fastapi.responses import StreamingResponse
from loguru import logger

from app.api.deps import get_current_active_user, validate_interview_ownership
from app.core.exceptions import InsufficientCreditsError
from app.crud.crud_interview import interview_crud
from app.crud.crud_chat_session import chat_session_crud
from app.db.session import get_db
from app.models.models import User, ChatMessage
from app.schemas.chat import (
    ChatMessageOut,
    ChatRequest,
    ChatResponse,
    ChatSessionOut,
    ChatSessionCreate,
    ChatSessionUpdate,
    TranscriptSearchRequest,
    TranscriptSearchResponse
)
from app.services.chat_service import chat_service
from app.services.qdrant_service import QdrantService

router = APIRouter()


@router.get("/sessions/{interview_id}", response_model=List[ChatSessionOut])
async def get_chat_sessions(
        interview_id: uuid.UUID = Path(..., description="The ID of the interview"),
        page: int = Query(1, ge=1, description="Page number"),
        size: int = Query(20, ge=1, le=100, description="Page size"),
        current_user: User = Depends(get_current_active_user),
        db: AsyncSession = Depends(get_db),
) -> Any:
    """
    Get chat sessions for an interview.
    """
    # Validate interview ownership
    await validate_interview_ownership(db, interview_id, current_user.id)

    # Calculate skip
    skip = (page - 1) * size

    # Get chat sessions with message counts
    chat_sessions = await chat_session_crud.get_by_interview(
        db,
        interview_id=interview_id,
        skip=skip,
        limit=size
    )

    return chat_sessions


@router.post("/sessions/{interview_id}", response_model=ChatSessionOut, status_code=status.HTTP_201_CREATED)
async def create_chat_session(
        interview_id: uuid.UUID = Path(..., description="The ID of the interview"),
        chat_session: ChatSessionCreate = None,
        current_user: User = Depends(get_current_active_user),
        db: AsyncSession = Depends(get_db),
) -> Any:
    """
    Create a new chat session for an interview.
    """
    # Validate interview ownership
    await validate_interview_ownership(db, interview_id, current_user.id)

    # Create chat session
    title = chat_session.title if chat_session else "New Chat"
    new_session = await chat_session_crud.create(
        db,
        interview_id=interview_id,
        title=title
    )

    await db.commit()
    await db.refresh(new_session)

    return {
        **new_session.__dict__,
        "message_count": 0
    }


@router.put("/sessions/{session_id}", response_model=ChatSessionOut)
async def update_chat_session(
        session_id: uuid.UUID = Path(..., description="The ID of the chat session"),
        chat_session: ChatSessionUpdate = None,
        current_user: User = Depends(get_current_active_user),
        db: AsyncSession = Depends(get_db),
) -> Any:
    """
    Update a chat session.
    """
    # Get the chat session
    session = await chat_session_crud.get(db, session_id=session_id)
    if not session:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Chat session not found",
        )

    # Validate interview ownership
    await validate_interview_ownership(db, session.interview_id, current_user.id)

    # Update chat session
    if chat_session:
        updated_session = await chat_session_crud.update(
            db,
            session_id=session_id,
            title=chat_session.title
        )
    else:
        # Just update timestamp
        updated_session = await chat_session_crud.update_timestamp(db, session_id=session_id)

    await db.commit()

    # Get message count
    count_query = select(ChatMessage).filter(ChatMessage.chat_session_id == session_id)
    result = await db.execute(count_query)
    messages = result.scalars().all()
    message_count = len(messages)

    # Get latest message
    latest_message = None
    latest_time = None
    if messages:
        latest_msg = max(messages, key=lambda x: x.created_at)
        latest_message = latest_msg.content[:100] + "..." if len(latest_msg.content) > 100 else latest_msg.content
        latest_time = latest_msg.created_at

    return {
        **updated_session.__dict__,
        "message_count": message_count,
        "latest_message": latest_message,
        "latest_message_time": latest_time
    }


@router.delete("/sessions/{session_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_chat_session(
        session_id: uuid.UUID = Path(..., description="The ID of the chat session"),
        current_user: User = Depends(get_current_active_user),
        db: AsyncSession = Depends(get_db),
) -> None:
    """
    Delete a chat session.
    """
    # Get the chat session
    session = await chat_session_crud.get(db, session_id=session_id)
    if not session:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Chat session not found",
        )

    # Validate interview ownership
    await validate_interview_ownership(db, session.interview_id, current_user.id)

    # Delete chat session (this will cascade delete all associated messages)
    result = await chat_session_crud.delete(db, session_id=session_id)
    if not result:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Chat session not found",
        )

    await db.commit()


@router.get("/messages/{session_id}", response_model=List[ChatMessageOut])
async def get_chat_messages(
        session_id: uuid.UUID = Path(..., description="The ID of the chat session"),
        page: int = Query(1, ge=1, description="Page number"),
        size: int = Query(50, ge=1, le=100, description="Page size"),
        current_user: User = Depends(get_current_active_user),
        db: AsyncSession = Depends(get_db),
) -> Any:
    """
    Get chat messages for a specific session.
    """
    # Get the chat session
    session = await chat_session_crud.get(db, session_id=session_id)
    if not session:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Chat session not found",
        )

    # Validate interview ownership
    await validate_interview_ownership(db, session.interview_id, current_user.id)

    # Calculate skip
    skip = (page - 1) * size

    # Get chat messages
    messages = await chat_session_crud.get_messages(
        db,
        session_id=session_id,
        skip=skip,
        limit=size
    )

    return messages


@router.post("/chat/{interview_id}", response_model=ChatResponse)
async def chat_with_interview(
        interview_id: uuid.UUID = Path(..., description="The ID of the interview"),
        chat_request: ChatRequest = None,
        current_user: User = Depends(get_current_active_user),
        db: AsyncSession = Depends(get_db),
) -> Any:
    """
    Chat with an interview transcript.
    """
    try:
        # Validate interview ownership and get interview
        interview = await validate_interview_ownership(db, interview_id, current_user.id)

        # Check if interview has a transcription
        if not interview.transcription:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Interview has no transcription",
            )

        # Check if there are chat tokens available
        if interview.remaining_chat_tokens <= 0:
            raise InsufficientCreditsError("No chat tokens available for this interview")

        # Validate message
        if not chat_request or not chat_request.message:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Message is required",
            )

        # Get or create chat session
        chat_session = None
        if chat_request.chat_session_id:
            chat_session = await chat_session_crud.get(db, session_id=chat_request.chat_session_id)
            if not chat_session or chat_session.interview_id != interview_id:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="Chat session not found or does not belong to this interview",
                )
        else:
            # Create a new chat session if none provided
            chat_session = await chat_session_crud.create(
                db,
                interview_id=interview_id,
                title=chat_request.message[:50] if chat_request.message else "New Chat"
            )

        # Create user message
        user_message = await chat_service.create_chat_message(
            db=db,
            interview=interview,
            user=current_user,
            message_text=chat_request.message,
            chat_session_id=chat_session.id,
        )

        # Get recent context
        query = select(ChatMessage).filter(
            ChatMessage.chat_session_id == chat_session.id
        ).order_by(ChatMessage.created_at.desc()).limit(10)

        result = await db.execute(query)
        recent_messages = list(reversed(result.scalars().all()))

        # Generate AI response
        assistant_message = await chat_service.generate_assistant_response(
            db=db,
            interview=interview,
            user=current_user,
            context_messages=recent_messages + [user_message],
            chat_session_id=chat_session.id,
        )

        # Update the chat session timestamp
        await chat_session_crud.update_timestamp(db, session_id=chat_session.id)

        # Commit changes
        await db.commit()

        # Return both messages
        return ChatResponse(
            user_message=ChatMessageOut.model_validate(user_message),
            assistant_message=ChatMessageOut.model_validate(assistant_message),
            remaining_tokens=interview.remaining_chat_tokens,
            chat_session_id=chat_session.id,
        )

    except InsufficientCreditsError as e:
        raise HTTPException(
            status_code=status.HTTP_402_PAYMENT_REQUIRED,
            detail=str(e),
        )
    except Exception as e:
        # Rollback transaction on error
        await db.rollback()
        logger.error(f"Error in chat_with_interview: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e),
        )


@router.post("/chat/{interview_id}/stream")
async def stream_chat_with_interview(
        interview_id: uuid.UUID = Path(..., description="The ID of the interview"),
        chat_request: ChatRequest = None,
        current_user: User = Depends(get_current_active_user),
        db: AsyncSession = Depends(get_db),
) -> StreamingResponse:
    """
    Chat with an interview transcript and stream the response.
    """
    try:
        # Validate interview ownership and get interview
        interview = await validate_interview_ownership(db, interview_id, current_user.id)

        # Check if interview has a transcription
        if not interview.transcription:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Interview has no transcription",
            )

        # Check if there are chat tokens available
        if interview.remaining_chat_tokens <= 0:
            raise InsufficientCreditsError("No chat tokens available for this interview")

        # Validate message
        if not chat_request or not chat_request.message:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Message is required",
            )

        # Get or create chat session
        chat_session = None
        if chat_request.chat_session_id:
            chat_session = await chat_session_crud.get(db, session_id=chat_request.chat_session_id)
            if not chat_session or chat_session.interview_id != interview_id:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="Chat session not found or does not belong to this interview",
                )
        else:
            # Create a new chat session if none provided
            chat_session = await chat_session_crud.create(
                db,
                interview_id=interview_id,
                title=chat_request.message[:50] if chat_request.message else "New Chat"
            )

        # Create user message
        user_message = await chat_service.create_chat_message(
            db=db,
            interview=interview,
            user=current_user,
            message_text=chat_request.message,
            chat_session_id=chat_session.id,
        )

        # Get recent context
        query = select(ChatMessage).filter(
            ChatMessage.chat_session_id == chat_session.id
        ).order_by(ChatMessage.created_at.desc()).limit(10)

        result = await db.execute(query)
        recent_messages = list(reversed(result.scalars().all()))

        # Update the chat session timestamp
        await chat_session_crud.update_timestamp(db, session_id=chat_session.id)

        # Commit changes to save the user message
        await db.commit()

        # Stream the response
        return StreamingResponse(
            chat_service.stream_assistant_response(
                db=db,
                interview=interview,
                user=current_user,
                context_messages=recent_messages + [user_message],
                chat_session_id=chat_session.id,
            ),
            media_type="text/event-stream",
        )

    except InsufficientCreditsError as e:
        raise HTTPException(
            status_code=status.HTTP_402_PAYMENT_REQUIRED,
            detail=str(e),
        )
    except Exception as e:
        # Rollback transaction on error
        await db.rollback()
        logger.error(f"Error in stream_chat_with_interview: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e),
        )


@router.post("/search/{interview_id}", response_model=TranscriptSearchResponse)
async def search_transcript(
        interview_id: uuid.UUID = Path(..., description="The ID of the interview"),
        search_request: TranscriptSearchRequest = None,
        current_user: User = Depends(get_current_active_user),
        db: AsyncSession = Depends(get_db),
) -> Any:
    """
    Search transcript for relevant segments.
    """
    # Validate interview ownership
    interview = await validate_interview_ownership(db, interview_id, current_user.id)

    # Check if interview has a transcription
    if not interview.transcription:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Interview has no transcription",
        )

    # Validate search request
    if not search_request or not search_request.query:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Search query is required",
        )

    # Search transcript using vector search
    qdrant_service = QdrantService()
    matches = await qdrant_service.search_transcript(
        interview_id=str(interview_id),
        query=search_request.query,
        limit=search_request.limit
    )

    return TranscriptSearchResponse(matches=matches)