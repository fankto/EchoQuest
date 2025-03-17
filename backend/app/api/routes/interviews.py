import json
import uuid
from typing import Any, List, Optional

from fastapi import APIRouter, BackgroundTasks, Depends, File, Form, HTTPException, Query, UploadFile, status
from fastapi.responses import JSONResponse
from fastapi_pagination import Page
from fastapi_pagination.ext.sqlalchemy import paginate
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_active_user
from app.core.config import settings
from app.core.exceptions import InsufficientCreditsError
from app.crud.crud_interview import interview_crud
from app.crud.crud_transaction import transaction_crud
from app.db.session import get_db
from app.models.models import Interview, InterviewStatus, TransactionType, User, Transaction
from app.schemas.interview import (
    InterviewCreate,
    InterviewOut,
    InterviewPatch,
    InterviewTaskResponse,
)
from app.services.file_service import file_service
from app.services.transcription_service import transcription_service
from sqlalchemy import delete

router = APIRouter()


@router.get("/", response_model=Page[InterviewOut])
async def list_interviews(
    current_user: User = Depends(get_current_active_user),
    status: Optional[str] = None,
    db: AsyncSession = Depends(get_db),
) -> Any:
    """
    List interviews for the current user.
    """
    filters = {}
    if status:
        filters["status"] = status
    
    return await paginate(
        db, 
        interview_crud.get_multi_by_owner_query(db, owner_id=current_user.id, **filters)
    )


@router.post("/", response_model=InterviewOut)
async def create_interview(
    interview_in: InterviewCreate,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
) -> Any:
    """
    Create a new interview.
    """
    # Check if user has enough interview credits
    if current_user.available_interview_credits <= 0:
        raise InsufficientCreditsError("You don't have any interview credits available")
    
    # Create the interview
    interview = await interview_crud.create(
        db=db,
        obj_in=interview_in,
        owner_id=current_user.id,
    )
    
    # Deduct credit
    current_user.available_interview_credits -= 1
    
    # Create transaction record
    await transaction_crud.create_transaction(
        db=db,
        user_id=current_user.id,
        organization_id=interview.organization_id,
        interview_id=interview.id,
        transaction_type=TransactionType.INTERVIEW_CREDIT_USAGE,
        amount=1,
    )
    
    await db.commit()
    await db.refresh(interview)
    
    return interview


@router.get("/{interview_id}", response_model=InterviewOut)
async def get_interview(
    interview_id: uuid.UUID,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
) -> Any:
    """
    Get interview by ID.
    """
    try:
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
        
        return interview
    except Exception as e:
        if isinstance(e, HTTPException):
            raise e
        logger.error(f"Error retrieving interview {interview_id}: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error retrieving interview: {str(e)}"
        )


@router.patch("/{interview_id}", response_model=InterviewOut)
async def update_interview(
    interview_id: uuid.UUID,
    interview_in: InterviewPatch,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
) -> Any:
    """
    Update interview.
    """
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
    
    interview = await interview_crud.update(db, db_obj=interview, obj_in=interview_in)
    return interview


@router.delete("/{interview_id}", response_model=dict)
async def delete_interview(
    interview_id: uuid.UUID,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
) -> Any:
    """
    Delete interview.
    """
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
    
    # Delete associated transactions first to avoid foreign key constraint error
    await db.execute(
        delete(Transaction).where(Transaction.interview_id == interview_id)
    )
    
    # Delete associated files
    if interview.original_filenames:
        original_filenames = json.loads(interview.original_filenames)
        for filename in original_filenames:
            await file_service.delete_file(filename, settings.UPLOAD_DIR)
    
    if interview.processed_filenames:
        processed_filenames = json.loads(interview.processed_filenames)
        for filename in processed_filenames:
            await file_service.delete_file(filename, settings.PROCESSED_DIR)
    
    # Delete from database
    await interview_crud.remove(db, id=interview_id)
    
    return {"status": "success"}


@router.post("/{interview_id}/upload", response_model=InterviewOut)
async def upload_audio(
    interview_id: uuid.UUID,
    files: List[UploadFile] = File(...),
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
) -> Any:
    """
    Upload audio files for an interview.
    """
    try:
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
        
        # Process and save files
        filenames = []
        for file in files:
            # Check file type
            if not file.content_type.startswith("audio/"):
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"File {file.filename} is not an audio file",
                )
            
            # Check file size
            if file.size > settings.MAX_UPLOAD_SIZE:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"File {file.filename} exceeds maximum size of {settings.MAX_UPLOAD_SIZE/1024/1024}MB",
                )
            
            # Save file
            filename = await file_service.save_file(file, settings.UPLOAD_DIR)
            filenames.append(filename)
        
        # Update interview
        current_filenames = []
        if interview.original_filenames:
            try:
                current_filenames = json.loads(interview.original_filenames)
                if not isinstance(current_filenames, list):
                    current_filenames = []
            except (json.JSONDecodeError, TypeError):
                current_filenames = []
        
        current_filenames.extend(filenames)
        
        interview.original_filenames = json.dumps(current_filenames)
        interview.status = InterviewStatus.UPLOADED
        await db.commit()
        await db.refresh(interview)
        
        return interview
    except Exception as e:
        logger.error(f"Error uploading audio for interview {interview_id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error uploading audio: {str(e)}"
        )


@router.post("/{interview_id}/process", response_model=InterviewTaskResponse)
async def process_audio(
    interview_id: uuid.UUID,
    background_tasks: BackgroundTasks,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
) -> Any:
    """
    Process audio files for an interview.
    """
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
    
    # Check if the interview has audio files
    if not interview.original_filenames:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No audio files uploaded",
        )
    
    # Add to background task
    background_tasks.add_task(
        transcription_service.process_audio,
        str(interview_id),
        db,
    )
    
    return {"status": "processing", "message": "Audio processing started"}


@router.post("/{interview_id}/transcribe", response_model=InterviewTaskResponse)
async def transcribe_audio(
    interview_id: uuid.UUID,
    background_tasks: BackgroundTasks,
    language: Optional[str] = Form(None),
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
) -> Any:
    """
    Transcribe processed audio files for an interview.
    """
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
    
    # Check if the interview has processed audio files
    if not interview.processed_filenames:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No processed audio files found. Please process the audio files first.",
        )
    
    # Update language if provided
    if language:
        interview.language = language
        await db.commit()
    
    # Add to background task
    background_tasks.add_task(
        transcription_service.transcribe_audio,
        str(interview_id),
        db,
    )
    
    return {"status": "transcribing", "message": "Audio transcription started"}