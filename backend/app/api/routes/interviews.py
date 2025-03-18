import json
import uuid
from typing import Any, List, Optional
import openai
import asyncio

from fastapi import APIRouter, BackgroundTasks, Depends, File, Form, HTTPException, Query, UploadFile, status
from fastapi.responses import JSONResponse
from fastapi_pagination import Page
from fastapi_pagination.ext.sqlalchemy import paginate
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import delete, select
from loguru import logger

from app.api.deps import get_current_active_user
from app.core.config import settings
from app.core.exceptions import InsufficientCreditsError
from app.crud.crud_interview import interview_crud
from app.crud.crud_transaction import transaction_crud
from app.crud.crud_questionnaire import questionnaire_crud
from app.db.session import get_db
from app.models.models import Interview, InterviewStatus, TransactionType, User, Transaction, Questionnaire
from app.schemas.interview import (
    InterviewCreate,
    InterviewOut,
    InterviewPatch,
    InterviewTaskResponse,
    InterviewDetailOut,
    TranscriptUpdateRequest,
    TranscriptSegmentsUpdateRequest,
)
from app.services.file_service import file_service
from app.services.transcription_service import transcription_service

router = APIRouter()


# Function to generate answers from transcript using OpenAI API
async def generate_answers_from_transcript(interview_id: str, db: AsyncSession):
    """
    Generate answers for questionnaire questions using OpenAI's GPT model.
    This runs as a background task.
    
    Args:
        interview_id: Interview ID
        db: Database session
    """
    try:
        # Create a new session for background task
        async with db:
            # Get interview
            result = await db.execute(
                select(Interview).where(Interview.id == uuid.UUID(interview_id))
            )
            interview = result.scalars().first()
            
            if not interview or not interview.transcription or not interview.questionnaire_id:
                logger.error(f"Invalid interview state for answer generation: {interview_id}")
                return
            
            # Get questionnaire directly from Questionnaire model
            result = await db.execute(
                select(Questionnaire).where(Questionnaire.id == interview.questionnaire_id)
            )
            questionnaire = result.scalars().first()
            
            if not questionnaire or not questionnaire.questions:
                logger.error(f"No questions found in questionnaire: {interview.questionnaire_id}")
                return
            
            # Get questions
            questions = questionnaire.questions
            
            # Initialize answers dict
            answers = {}
            
            # Set up OpenAI client
            client = openai.AsyncOpenAI(api_key=settings.OPENAI_API_KEY)
            
            # Process each question
            for question in questions:
                try:
                    # Use GPT-4o-mini to generate the answer
                    response = await client.chat.completions.create(
                        model="gpt-4o-mini",  # Using GPT-4o-mini for answer generation
                        messages=[
                            {"role": "system", "content": "You are an AI assistant that analyzes interview transcripts and answers questions based on the content. Provide concise and accurate answers."},
                            {"role": "user", "content": f"Here is an interview transcript:\n\n{interview.transcription}\n\nBased on this transcript, please answer the following question:\n{question}"}
                        ],
                        temperature=0.3,
                        max_tokens=500,
                    )
                    
                    # Extract answer
                    answer = response.choices[0].message.content.strip()
                    
                    # Store answer
                    answers[question] = answer
                    
                    # Add some delay to avoid rate limiting
                    await asyncio.sleep(1)
                    
                except Exception as e:
                    logger.error(f"Error generating answer for question: {e}")
                    answers[question] = f"Error generating answer: {str(e)}"
            
            # Update interview with generated answers
            interview.generated_answers = answers
            await db.commit()
            
            logger.info(f"Successfully generated answers for interview {interview_id}")
    
    except Exception as e:
        logger.error(f"Error in generate_answers_from_transcript: {e}")


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


@router.get("/{interview_id}", response_model=InterviewDetailOut)
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


@router.get("/{interview_id}/audio", response_model=dict)
async def get_audio_url(
    interview_id: uuid.UUID,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
) -> Any:
    """
    Get audio URL for an interview.
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
    
    # First check for processed files (preferred if available)
    if interview.processed_filenames:
        try:
            processed_filenames = json.loads(interview.processed_filenames)
            if processed_filenames and len(processed_filenames) > 0:
                audio_filename = processed_filenames[0]
                return {
                    "audio_url": f"/api/media/processed/{audio_filename}",
                    "is_processed": True
                }
        except (json.JSONDecodeError, TypeError):
            # Fall through to original files if processed files can't be parsed
            pass
    
    # If no processed files or if couldn't parse, try original files
    if interview.original_filenames:
        try:
            original_filenames = json.loads(interview.original_filenames)
            if original_filenames and len(original_filenames) > 0:
                audio_filename = original_filenames[0]
                return {
                    "audio_url": f"/api/media/uploads/{audio_filename}",
                    "is_processed": False
                }
        except (json.JSONDecodeError, TypeError):
            pass
    
    # If we get here, no audio files are available
    raise HTTPException(
        status_code=status.HTTP_400_BAD_REQUEST,
        detail="No audio files available",
    )


@router.put("/{interview_id}/update-transcription", response_model=InterviewOut)
async def update_transcription(
    interview_id: uuid.UUID,
    transcription_update: TranscriptUpdateRequest,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
) -> Any:
    """
    Update transcription text for an interview.
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
    
    # Check if the interview has been transcribed
    if interview.status != InterviewStatus.TRANSCRIBED:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Interview must be transcribed first",
        )
    
    # Update transcription
    interview.transcription = transcription_update.transcription
    await db.commit()
    await db.refresh(interview)
    
    return interview


@router.put("/{interview_id}/update-segments", response_model=InterviewOut)
async def update_segments(
    interview_id: uuid.UUID,
    segments_update: TranscriptSegmentsUpdateRequest,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
) -> Any:
    """
    Update transcript segments for an interview.
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
    
    # Check if the interview has been transcribed
    if interview.status != InterviewStatus.TRANSCRIBED:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Interview must be transcribed first",
        )
    
    # Update segments
    interview.transcript_segments = segments_update.segments
    await db.commit()
    await db.refresh(interview)
    
    return interview


@router.post("/{interview_id}/attach-questionnaire", response_model=InterviewOut)
async def attach_questionnaire(
    interview_id: uuid.UUID,
    questionnaire_id: uuid.UUID = Form(...),
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
) -> Any:
    """
    Attach a questionnaire to an existing interview.
    This can be done even after transcription, allowing the user to add a questionnaire later.
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
    
    # Check if the interview has been transcribed
    if interview.status != InterviewStatus.TRANSCRIBED:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Interview must be transcribed first",
        )
    
    # Update questionnaire_id
    interview.questionnaire_id = questionnaire_id
    
    # Reset any previously generated answers since we're changing the questionnaire
    interview.generated_answers = None
    
    await db.commit()
    await db.refresh(interview)
    
    return interview


@router.delete("/{interview_id}/remove-questionnaire", response_model=InterviewOut)
async def remove_questionnaire(
    interview_id: uuid.UUID,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
) -> Any:
    """
    Remove a questionnaire from an interview.
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
    
    # Check if interview has a questionnaire
    if not interview.questionnaire_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Interview does not have a questionnaire attached",
        )
    
    # Remove questionnaire_id and any generated answers
    interview.questionnaire_id = None
    interview.generated_answers = None
    
    await db.commit()
    await db.refresh(interview)
    
    return interview


@router.get("/by-questionnaire/{questionnaire_id}", response_model=List[InterviewOut])
async def list_interviews_by_questionnaire(
    questionnaire_id: uuid.UUID,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
) -> Any:
    """
    List interviews that use a specific questionnaire.
    """
    # Get the questionnaire first to check permissions
    questionnaire = await questionnaire_crud.get(db, id=questionnaire_id)
    
    if not questionnaire:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Questionnaire not found",
        )
    
    # Check if user can access the questionnaire
    if questionnaire.creator_id != current_user.id:
        # TODO: Add organization-based permissions
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not enough permissions",
        )
    
    # Query for interviews with this questionnaire
    query = select(Interview).where(
        Interview.questionnaire_id == questionnaire_id,
        Interview.owner_id == current_user.id,
    ).order_by(Interview.updated_at.desc())
    
    result = await db.execute(query)
    interviews = result.scalars().all()
    
    return interviews


@router.post("/{interview_id}/generate-answers", response_model=InterviewTaskResponse)
async def generate_answers(
    interview_id: uuid.UUID,
    background_tasks: BackgroundTasks,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
) -> Any:
    """
    Generate answers for questionnaire questions based on interview transcript.
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
    
    # Check if the interview has been transcribed
    if interview.status != InterviewStatus.TRANSCRIBED:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Interview must be transcribed first",
        )
    
    # Check if a questionnaire is attached
    if not interview.questionnaire_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No questionnaire attached to this interview",
        )
    
    # Add to background task
    background_tasks.add_task(
        generate_answers_from_transcript,
        str(interview_id),
        db,
    )
    
    return {"status": "processing", "message": "Answer generation started"}