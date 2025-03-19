import uuid
from typing import Any, List

from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_active_user
from app.core.exceptions import InsufficientCreditsError
from app.crud.crud_interview import interview_crud
from app.crud.crud_chat_session import chat_session_crud
from app.db.session import get_db
from app.models.models import User, ChatMessage
from app.schemas.chat import (
    ChatMessageCreate,
    ChatMessageOut,
    ChatRequest,
    ChatResponse,
    ChatSessionOut,
    ChatSessionCreate,
    ChatSessionUpdate
)
from app.services.chat_service import chat_service

from fastapi.responses import StreamingResponse
import json
import asyncio
import openai

router = APIRouter()


@router.get("/{interview_id}/messages", response_model=List[ChatMessageOut])
async def get_chat_messages(
    interview_id: uuid.UUID,
    chat_session_id: uuid.UUID = None,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
) -> Any:
    """
    Get chat messages for an interview, optionally filtered by chat session.
    """
    # Check if the interview exists and user has access
    interview = await interview_crud.get(db, id=interview_id)
    if not interview:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Interview not found",
        )
    
    # Check ownership
    if interview.owner_id != current_user.id:
        # TODO: Add organization-based permissions
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not enough permissions",
        )
    
    try:
        # Get chat messages - use SQLAlchemy to fetch related messages
        from sqlalchemy import select
        
        query = select(ChatMessage).filter(ChatMessage.interview_id == interview_id)
        
        # Filter by chat session if provided
        if chat_session_id:
            query = query.filter(ChatMessage.chat_session_id == chat_session_id)
        
        # Order by created_at
        query = query.order_by(ChatMessage.created_at)
        
        result = await db.execute(query)
        messages = result.scalars().all()
        
        return messages
    except Exception as e:
        # Log and handle exceptions
        import logging
        logging.error(f"Error fetching chat messages: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error fetching chat messages: {str(e)}",
        )


@router.post("/{interview_id}/chat", response_model=ChatResponse)
async def chat_with_interview(
    interview_id: uuid.UUID,
    chat_request: ChatRequest,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
) -> Any:
    """
    Chat with an interview transcript.
    """
    try:
        # Check if the interview exists and user has access
        interview = await interview_crud.get(db, id=interview_id)
        if not interview:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Interview not found",
            )
        
        # Check ownership
        if interview.owner_id != current_user.id:
            # TODO: Add organization-based permissions
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Not enough permissions",
            )
        
        # Check if interview has a transcription
        if not interview.transcription:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Interview has no transcription",
            )
        
        # Check if there are chat tokens available
        if interview.remaining_chat_tokens <= 0:
            raise InsufficientCreditsError("No chat tokens available for this interview")
        
        # Get or create chat session
        chat_session = None
        if chat_request.chat_session_id:
            chat_session = await chat_session_crud.get(db, session_id=chat_request.chat_session_id)
            if not chat_session or chat_session.interview_id != interview_id:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="Chat session not found or does not belong to this interview",
                )
        elif not chat_request.chat_session_id:
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
            chat_session_id=chat_session.id if chat_session else None,
        )
        
        # Get recent context using a proper query instead of accessing relationship directly
        from sqlalchemy import select
        
        # Query for messages in this chat session or general interview messages if no session
        if chat_session:
            query = select(ChatMessage).filter(
                ChatMessage.chat_session_id == chat_session.id
            ).order_by(ChatMessage.created_at.desc()).limit(10)
        else:
            query = select(ChatMessage).filter(
                ChatMessage.interview_id == interview_id,
                ChatMessage.chat_session_id.is_(None)
            ).order_by(ChatMessage.created_at.desc()).limit(10)
        
        result = await db.execute(query)
        recent_messages = list(reversed(result.scalars().all()))
        
        # Add the new user message to the context
        messages = recent_messages + [user_message]
        
        # Generate AI response
        assistant_message = await chat_service.generate_assistant_response(
            db=db,
            interview=interview,
            user=current_user,
            context_messages=messages,
            chat_session_id=chat_session.id if chat_session else None,
        )
        
        # Update the chat session title if it's a new session
        if chat_session and chat_session.title == "New Chat":
            # Try to generate a better title based on the first exchange
            title_prompt = f"USER: {user_message.content[:100]}\nASSISTANT: {assistant_message.content[:100]}\n\nGenerately a very concise title (maximum 5 words) for this conversation:"
            
            try:
                title_response = openai.chat.completions.create(
                    model="gpt-3.5-turbo",
                    messages=[{"role": "system", "content": "You are a helpful assistant that generates very concise chat titles."}, 
                              {"role": "user", "content": title_prompt}],
                    max_tokens=10,
                    temperature=0.7,
                )
                new_title = title_response.choices[0].message.content.strip()
                
                # Update the title if we got a reasonable response
                if new_title and len(new_title) < 50:
                    chat_session = await chat_session_crud.update(
                        db, 
                        session_id=chat_session.id, 
                        title=new_title
                    )
            except Exception as e:
                # Log error but continue - title generation isn't critical
                import logging
                logging.error(f"Error generating chat title: {str(e)}")
        
        # Commit changes
        await db.commit()
        
        # Return both messages
        return ChatResponse(
            user_message=ChatMessageOut.model_validate(user_message),
            assistant_message=ChatMessageOut.model_validate(assistant_message),
            remaining_tokens=interview.remaining_chat_tokens,
            chat_session_id=chat_session.id if chat_session else None,
        )
    
    except InsufficientCreditsError as e:
        raise HTTPException(
            status_code=status.HTTP_402_PAYMENT_REQUIRED,
            detail=str(e),
        )
    except Exception as e:
        # Rollback transaction on error
        await db.rollback()
        import logging
        logging.error(f"Error in chat_with_interview: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e),
        )


@router.post("/{interview_id}/chat/stream")
async def stream_chat_with_interview(
    interview_id: uuid.UUID,
    chat_request: ChatRequest,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
) -> StreamingResponse:
    """
    Chat with an interview transcript and stream the response.
    """
    try:
        # Check if the interview exists and user has access
        interview = await interview_crud.get(db, id=interview_id)
        if not interview:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Interview not found",
            )
        
        # Check ownership
        if interview.owner_id != current_user.id:
            # TODO: Add organization-based permissions
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Not enough permissions",
            )
        
        # Check if interview has a transcription
        if not interview.transcription:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Interview has no transcription",
            )
        
        # Check if there are chat tokens available
        if interview.remaining_chat_tokens <= 0:
            raise InsufficientCreditsError("No chat tokens available for this interview")
        
        # Get or create chat session
        chat_session = None
        if chat_request.chat_session_id:
            chat_session = await chat_session_crud.get(db, session_id=chat_request.chat_session_id)
            if not chat_session or chat_session.interview_id != interview_id:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="Chat session not found or does not belong to this interview",
                )
        elif not chat_request.chat_session_id:
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
            chat_session_id=chat_session.id if chat_session else None,
        )
        
        # Get recent context using a proper query instead of accessing relationship directly
        from sqlalchemy import select
        
        # Query for messages in this chat session or general interview messages if no session
        if chat_session:
            query = select(ChatMessage).filter(
                ChatMessage.chat_session_id == chat_session.id
            ).order_by(ChatMessage.created_at.desc()).limit(10)
        else:
            query = select(ChatMessage).filter(
                ChatMessage.interview_id == interview_id,
                ChatMessage.chat_session_id.is_(None)
            ).order_by(ChatMessage.created_at.desc()).limit(10)
        
        result = await db.execute(query)
        recent_messages = list(reversed(result.scalars().all()))
        
        # Add the new user message to the context
        messages = recent_messages + [user_message]
        
        # Stream the response
        return StreamingResponse(
            chat_service.stream_assistant_response(
                db=db,
                interview=interview,
                user=current_user,
                context_messages=messages,
                chat_session_id=chat_session.id if chat_session else None,
            ),
            media_type="text/event-stream",
        )
    
    except InsufficientCreditsError as e:
        await db.rollback()
        raise HTTPException(
            status_code=status.HTTP_402_PAYMENT_REQUIRED,
            detail=str(e),
        )
    except Exception as e:
        # Rollback transaction on error
        await db.rollback()
        import logging
        logging.error(f"Error in stream_chat_with_interview: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e),
        )


@router.get("/{interview_id}/chat-sessions", response_model=List[ChatSessionOut])
async def get_chat_sessions(
    interview_id: uuid.UUID,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
    skip: int = 0,
    limit: int = 100,
) -> List[ChatSessionOut]:
    """
    Get chat sessions for an interview.
    """
    # Check if the interview exists and user has access
    interview = await interview_crud.get(db, id=interview_id)
    if not interview:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Interview not found",
        )
    
    # Check ownership
    if interview.owner_id != current_user.id:
        # TODO: Add organization-based permissions
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not enough permissions",
        )
    
    # Get chat sessions
    chat_sessions = await chat_session_crud.get_by_interview(
        db, 
        interview_id=interview_id, 
        skip=skip, 
        limit=limit
    )
    
    return chat_sessions


@router.post("/{interview_id}/chat-sessions", response_model=ChatSessionOut)
async def create_chat_session(
    interview_id: uuid.UUID,
    chat_session: ChatSessionCreate,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
) -> ChatSessionOut:
    """
    Create a new chat session for an interview.
    """
    # Check if the interview exists and user has access
    interview = await interview_crud.get(db, id=interview_id)
    if not interview:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Interview not found",
        )
    
    # Check ownership
    if interview.owner_id != current_user.id:
        # TODO: Add organization-based permissions
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not enough permissions",
        )
    
    # Create chat session
    new_session = await chat_session_crud.create(
        db, 
        interview_id=interview_id,
        title=chat_session.title
    )
    
    await db.commit()
    
    return new_session


@router.put("/{interview_id}/chat-sessions/{session_id}", response_model=ChatSessionOut)
async def update_chat_session(
    interview_id: uuid.UUID,
    session_id: uuid.UUID,
    chat_session: ChatSessionUpdate,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
) -> ChatSessionOut:
    """
    Update a chat session.
    """
    # Check if the interview exists and user has access
    interview = await interview_crud.get(db, id=interview_id)
    if not interview:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Interview not found",
        )
    
    # Check ownership
    if interview.owner_id != current_user.id:
        # TODO: Add organization-based permissions
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not enough permissions",
        )
    
    # Check if chat session exists and belongs to this interview
    existing_session = await chat_session_crud.get(db, session_id=session_id)
    if not existing_session or existing_session.interview_id != interview_id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Chat session not found or does not belong to this interview",
        )
    
    # Update chat session
    updated_session = await chat_session_crud.update(
        db, 
        session_id=session_id,
        title=chat_session.title
    )
    
    if not updated_session:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Chat session not found",
        )
    
    await db.commit()
    
    return updated_session


@router.delete("/{interview_id}/chat-sessions/{session_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_chat_session(
    interview_id: uuid.UUID,
    session_id: uuid.UUID,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
) -> None:
    """
    Delete a chat session.
    """
    # Check if the interview exists and user has access
    interview = await interview_crud.get(db, id=interview_id)
    if not interview:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Interview not found",
        )
    
    # Check ownership
    if interview.owner_id != current_user.id:
        # TODO: Add organization-based permissions
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not enough permissions",
        )
    
    # Check if chat session exists and belongs to this interview
    existing_session = await chat_session_crud.get(db, session_id=session_id)
    if not existing_session or existing_session.interview_id != interview_id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Chat session not found or does not belong to this interview",
        )
    
    # Delete chat session
    result = await chat_session_crud.delete(db, session_id=session_id)
    
    if not result:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Chat session not found",
        )
    
    await db.commit()
    
    return None