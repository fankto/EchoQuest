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
from app.models.models import Interview, InterviewStatus, TransactionType, User, Transaction, Questionnaire, interview_questionnaire
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
async def generate_answers_from_transcript(interview_id: str, db: AsyncSession, questionnaire_id: Optional[str] = None):
    """
    Generate answers for questionnaire questions using OpenAI's GPT model.
    This runs as a background task.
    
    Args:
        interview_id: Interview ID
        db: Database session
        questionnaire_id: Questionnaire ID (optional)
    """
    try:
        # Create a new session for background task
        async with db:
            # Get interview
            result = await db.execute(
                select(Interview).where(Interview.id == uuid.UUID(interview_id))
            )
            interview = result.scalars().first()
            
            if not interview or not interview.transcription:
                logger.error(f"Invalid interview state for answer generation: {interview_id}")
                return
            
            # Initialize the answers dict if it doesn't exist
            current_answers = interview.generated_answers or {}
            
            # Determine which questionnaires to process
            questionnaires_to_process = []
            
            if questionnaire_id:
                # Process only the specified questionnaire
                result = await db.execute(
                    select(Questionnaire).where(Questionnaire.id == uuid.UUID(questionnaire_id))
                )
                questionnaire = result.scalars().first()
                if questionnaire:
                    questionnaires_to_process.append(questionnaire)
            else:
                # Process all attached questionnaires
                # First try the many-to-many relationship
                result = await db.execute(
                    select(Questionnaire)
                    .join(interview_questionnaire)
                    .where(interview_questionnaire.c.interview_id == uuid.UUID(interview_id))
                )
                questionnaires = result.scalars().all()
                
                # If no questionnaires found, try the old direct relationship
                if not questionnaires and interview.questionnaire_id:
                    result = await db.execute(
                        select(Questionnaire).where(Questionnaire.id == interview.questionnaire_id)
                    )
                    legacy_questionnaire = result.scalars().first()
                    if legacy_questionnaire:
                        questionnaires_to_process.append(legacy_questionnaire)
                else:
                    questionnaires_to_process.extend(questionnaires)
            
            if not questionnaires_to_process:
                logger.error(f"No questionnaires found for interview: {interview_id}")
                return
            
            # Set up OpenAI client
            client = openai.AsyncOpenAI(api_key=settings.OPENAI_API_KEY)
            
            # Process each questionnaire
            for questionnaire in questionnaires_to_process:
                if not questionnaire.questions:
                    logger.warning(f"No questions found in questionnaire: {questionnaire.id}")
                    continue
                
                # Initialize answers dict for this questionnaire
                questionnaire_answers = {}
                
                # Process each question
                for question in questionnaire.questions:
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
                        questionnaire_answers[question] = answer
                        
                        # Add some delay to avoid rate limiting
                        await asyncio.sleep(1)
                        
                    except Exception as e:
                        logger.error(f"Error generating answer for question: {e}")
                        questionnaire_answers[question] = f"Error generating answer: {str(e)}"
                
                # Update answers dict with the questionnaire's answers
                current_answers[str(questionnaire.id)] = questionnaire_answers
            
            # Update interview with generated answers
            interview.generated_answers = current_answers
            await db.commit()
            
            logger.info(f"Successfully generated answers for interview {interview_id}")
    
    except Exception as e:
        logger.error(f"Error in generate_answers_from_transcript: {e}")
        logger.exception(e)


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
    try:
        logger.info(f"Attempting to delete interview {interview_id}")
        
        interview = await interview_crud.get(db, id=interview_id)
        if not interview:
            logger.error(f"Interview {interview_id} not found")
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Interview not found",
            )
        
        # Check ownership
        if interview.owner_id != current_user.id:
            logger.error(f"User {current_user.id} does not have permission to delete interview {interview_id}")
            # TODO: Add organization-based permissions
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Not enough permissions",
            )
        
        # Delete associated transactions first to avoid foreign key constraint error
        logger.info(f"Deleting transactions for interview {interview_id}")
        transaction_result = await db.execute(
            delete(Transaction).where(Transaction.interview_id == interview_id)
        )
        logger.info(f"Deleted {transaction_result.rowcount} transactions")
        
        # Delete associated questionnaire relationships
        logger.info(f"Deleting questionnaire relationships for interview {interview_id}")
        questionnaire_result = await db.execute(
            delete(interview_questionnaire).where(interview_questionnaire.c.interview_id == interview_id)
        )
        logger.info(f"Deleted {questionnaire_result.rowcount} questionnaire relationships")
        
        # Delete associated files
        if interview.original_filenames:
            try:
                original_filenames = json.loads(interview.original_filenames)
                logger.info(f"Deleting {len(original_filenames)} original files")
                for filename in original_filenames:
                    await file_service.delete_file(filename, settings.UPLOAD_DIR)
            except json.JSONDecodeError:
                logger.error(f"Could not parse original_filenames: {interview.original_filenames}")
        
        if interview.processed_filenames:
            try:
                processed_filenames = json.loads(interview.processed_filenames)
                logger.info(f"Deleting {len(processed_filenames)} processed files")
                for filename in processed_filenames:
                    await file_service.delete_file(filename, settings.PROCESSED_DIR)
            except json.JSONDecodeError:
                logger.error(f"Could not parse processed_filenames: {interview.processed_filenames}")
        
        # Delete from database
        logger.info(f"Removing interview {interview_id} from database")
        await interview_crud.remove(db, id=interview_id)
        
        logger.info(f"Successfully deleted interview {interview_id}")
        return {"status": "success"}
    
    except Exception as e:
        logger.error(f"Error deleting interview {interview_id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error deleting interview: {str(e)}"
        )


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
    This can be done even after transcription, allowing the user to add multiple questionnaires.
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
    
    # Get the questionnaire
    questionnaire = await questionnaire_crud.get(db, id=questionnaire_id)
    if not questionnaire:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Questionnaire not found",
        )
    
    # Check if questionnaire is already attached
    query = select(interview_questionnaire).where(
        interview_questionnaire.c.interview_id == interview_id,
        interview_questionnaire.c.questionnaire_id == questionnaire_id
    )
    result = await db.execute(query)
    existing = result.first()
    
    if not existing:
        # Add to the many-to-many relationship
        stmt = interview_questionnaire.insert().values(
            interview_id=interview_id,
            questionnaire_id=questionnaire_id
        )
        await db.execute(stmt)
    
    # For backward compatibility, also set the questionnaire_id field if there's no questionnaire set yet
    if not interview.questionnaire_id:
        interview.questionnaire_id = questionnaire_id
    
    await db.commit()
    await db.refresh(interview)
    
    return interview


@router.delete("/{interview_id}/remove-questionnaire", response_model=InterviewOut)
async def remove_questionnaire(
    interview_id: uuid.UUID,
    questionnaire_id: uuid.UUID = Query(..., description="ID of the questionnaire to remove"), 
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
) -> Any:
    """
    Remove a specific questionnaire from an interview.
    
    This endpoint expects the questionnaire_id as a query parameter.
    Example: DELETE /api/interviews/{interview_id}/remove-questionnaire?questionnaire_id={questionnaire_id}
    """
    try:
        logger.info(f"Removing questionnaire {questionnaire_id} from interview {interview_id}")
        
        interview = await interview_crud.get(db, id=interview_id)
        if not interview:
            logger.error(f"Interview {interview_id} not found")
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Interview not found",
            )
        
        # Check ownership
        if interview.owner_id != current_user.id:
            logger.error(f"User {current_user.id} does not have permission to modify interview {interview_id}")
            # TODO: Add organization-based permissions
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Not enough permissions",
            )
        
        # Check if the questionnaire is attached
        query = select(interview_questionnaire).where(
            interview_questionnaire.c.interview_id == interview_id,
            interview_questionnaire.c.questionnaire_id == questionnaire_id
        )
        result = await db.execute(query)
        existing = result.first()
        
        if not existing:
            logger.error(f"Questionnaire {questionnaire_id} is not attached to interview {interview_id}")
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Questionnaire is not attached to this interview",
            )
    
        # Log parameters for debugging
        logger.info(f"Parameters valid, proceeding with removal of questionnaire {questionnaire_id} from interview {interview_id}")
        
        # Remove from the many-to-many relationship
        stmt = interview_questionnaire.delete().where(
            interview_questionnaire.c.interview_id == interview_id,
            interview_questionnaire.c.questionnaire_id == questionnaire_id
        )
        await db.execute(stmt)
        logger.info(f"Removed questionnaire {questionnaire_id} from many-to-many relationship")

        # If this was the primary questionnaire, set it to the first remaining one or None
        if interview.questionnaire_id == questionnaire_id:
            logger.info(f"Questionnaire {questionnaire_id} was the primary questionnaire, finding replacement")
            result = await db.execute(
                select(interview_questionnaire)
                .where(interview_questionnaire.c.interview_id == interview_id)
                .order_by(interview_questionnaire.c.created_at)
                .limit(1)
            )
            first_questionnaire = result.first()
            if first_questionnaire:
                interview.questionnaire_id = first_questionnaire.questionnaire_id
                logger.info(f"Set new primary questionnaire: {interview.questionnaire_id}")
            else:
                interview.questionnaire_id = None
                logger.info("No replacement found, setting primary questionnaire to None")

        # Remove any answers generated for this questionnaire
        if interview.generated_answers and str(questionnaire_id) in interview.generated_answers:
            logger.info(f"Removing generated answers for questionnaire {questionnaire_id}")
            generated_answers = interview.generated_answers.copy()
            generated_answers.pop(str(questionnaire_id), None)
            interview.generated_answers = generated_answers if generated_answers else None

        logger.info("Committing changes to database")
        await db.commit()
        await db.refresh(interview)
        
        logger.info(f"Successfully removed questionnaire {questionnaire_id} from interview {interview_id}")
        return interview
    except Exception as e:
        logger.error(f"Error removing questionnaire: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error removing questionnaire: {str(e)}"
        )


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
    questionnaire_id: Optional[uuid.UUID] = None,
    background_tasks: BackgroundTasks = BackgroundTasks(),
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
) -> Any:
    """
    Generate answers for questionnaire questions based on interview transcript.
    If questionnaire_id is provided, only generate answers for that specific questionnaire.
    Otherwise, generate answers for all attached questionnaires.
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
    
    # If questionnaire_id is provided, check if it's attached to the interview
    if questionnaire_id:
        query = select(interview_questionnaire).where(
            interview_questionnaire.c.interview_id == interview_id,
            interview_questionnaire.c.questionnaire_id == questionnaire_id
        )
        result = await db.execute(query)
        existing = result.first()
        
        if not existing:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Specified questionnaire is not attached to this interview",
            )
    else:
        # If no questionnaire_id is provided, check if there are any attached questionnaires
        query = select(interview_questionnaire).where(
            interview_questionnaire.c.interview_id == interview_id
        )
        result = await db.execute(query)
        existing = result.first()
        
        if not existing and not interview.questionnaire_id:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="No questionnaires attached to this interview",
            )
    
    # Add to background task
    background_tasks.add_task(
        generate_answers_from_transcript,
        str(interview_id),
        db,
        str(questionnaire_id) if questionnaire_id else None,
    )
    
    return {"status": "processing", "message": "Answer generation started"}