import uuid
from typing import Any, List

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_active_user
from app.core.exceptions import InsufficientCreditsError
from app.crud.crud_interview import interview_crud
from app.db.session import get_db
from app.models.models import User
from app.schemas.chat import ChatMessageCreate, ChatMessageOut, ChatRequest, ChatResponse
from app.services.chat_service import chat_service

router = APIRouter()


@router.get("/{interview_id}/messages", response_model=List[ChatMessageOut])
async def get_chat_messages(
    interview_id: uuid.UUID,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
) -> Any:
    """
    Get chat messages for an interview.
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
    
    # Get chat messages
    return interview.chat_messages


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
        
        # Create user message
        user_message = await chat_service.create_chat_message(
            db=db,
            interview=interview,
            user=current_user,
            message_text=chat_request.message,
        )
        
        # Get recent context
        messages = interview.chat_messages[-10:] if interview.chat_messages else []
        
        # Generate AI response
        assistant_message = await chat_service.generate_assistant_response(
            db=db,
            interview=interview,
            user=current_user,
            context_messages=messages + [user_message],
        )
        
        # Commit changes
        await db.commit()
        
        # Return both messages
        return ChatResponse(
            user_message=ChatMessageOut.model_validate(user_message),
            assistant_message=ChatMessageOut.model_validate(assistant_message),
            remaining_tokens=interview.remaining_chat_tokens,
        )
    
    except InsufficientCreditsError as e:
        raise HTTPException(
            status_code=status.HTTP_402_PAYMENT_REQUIRED,
            detail=str(e),
        )
    except Exception as e:
        # Rollback transaction on error
        await db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e),
        )