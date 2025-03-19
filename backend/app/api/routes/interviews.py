import json
import uuid
from typing import Any, List, Optional
import openai
import asyncio

from fastapi import (
    APIRouter, BackgroundTasks, Depends, File, Form,
    HTTPException, Path, Query, UploadFile, status
)
from fastapi.responses import JSONResponse
from fastapi_pagination import Page, Params
from fastapi_pagination.ext.sqlalchemy import paginate
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import delete, select, or_
from loguru import logger

from app.api.deps import get_current_active_user, validate_interview_ownership
from app.core.config import settings
from app.core.exceptions import InsufficientCreditsError
from app.crud.crud_interview import interview_crud
from app.crud.crud_transaction import transaction_crud
from app.crud.crud_questionnaire import questionnaire_crud
from app.db.session import get_db
from app.models.models import Interview, InterviewStatus, TransactionType, User, Transaction, Questionnaire, \
    interview_questionnaire
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
from app.services.ai_service import generate_answers_from_transcript
from app.utils.pagination import get_pagination_params

router = APIRouter()


@router.get("/", response_model=Page[InterviewOut])
async def list_interviews(
        status: Optional[str] = None,
        page: int = Query(1, ge=1, description="Page number"),
        size: int = Query(10, ge=1, le=100, description="Items per page"),
        current_user: User = Depends(get_current_active_user),
        db: AsyncSession = Depends(get_db),
) -> Any:
    """
    List interviews for the current user.
    """
    filters = {}
    if status:
        filters["status"] = status

    # Use the paginate helper from fastapi_pagination
    return await paginate(
        db,
        interview_crud.get_multi_by_owner_query(db, owner_id=current_user.id, **filters),
        params=Params(page=page, size=size)
    )


@router.post("/", response_model=InterviewOut, status_code=status.HTTP_201_CREATED)
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

    # If questionnaire_id is provided, add it to the many-to-many relationship
    if interview_in.questionnaire_id:
        # Verify questionnaire exists
        questionnaire = await questionnaire_crud.get(db, id=interview_in.questionnaire_id)
        if questionnaire:
            # Add to the many-to-many relationship
            stmt = interview_questionnaire.insert().values(
                interview_id=interview.id,
                questionnaire_id=interview_in.questionnaire_id
            )
            await db.execute(stmt)

    await db.commit()
    await db.refresh(interview)

    return interview


@router.get("/{interview_id}", response_model=InterviewDetailOut)
async def get_interview(
        interview_id: uuid.UUID = Path(..., description="The ID of the interview to retrieve"),
        current_user: User = Depends(get_current_active_user),
        db: AsyncSession = Depends(get_db),
) -> Any:
    """
    Get interview by ID.
    """
    try:
        # Validate ownership
        interview = await validate_interview_ownership(db, interview_id, current_user.id)
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
        interview_in: InterviewPatch,
        interview_id: uuid.UUID = Path(..., description="The ID of the interview to update"),
        current_user: User = Depends(get_current_active_user),
        db: AsyncSession = Depends(get_db),
) -> Any:
    """
    Update interview details.
    """
    # Validate ownership
    interview = await validate_interview_ownership(db, interview_id, current_user.id)

    # Update interview
    updated_interview = await interview_crud.update(db, db_obj=interview, obj_in=interview_in)
    return updated_interview


@router.delete("/{interview_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_interview(
        interview_id: uuid.UUID = Path(..., description="The ID of the interview to delete"),
        current_user: User = Depends(get_current_active_user),
        db: AsyncSession = Depends(get_db),
) -> None:
    """
    Delete interview and all associated resources.
    """
    try:
        logger.info(f"Attempting to delete interview {interview_id}")

        # Validate ownership
        interview = await validate_interview_ownership(db, interview_id, current_user.id)

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
        original_filenames = interview.get_original_filenames()
        if original_filenames:
            logger.info(f"Deleting {len(original_filenames)} original files")
            for filename in original_filenames:
                await file_service.delete_file(filename, settings.UPLOAD_DIR)

        processed_filenames = interview.get_processed_filenames()
        if processed_filenames:
            logger.info(f"Deleting {len(processed_filenames)} processed files")
            for filename in processed_filenames:
                await file_service.delete_file(filename, settings.PROCESSED_DIR)

        # Delete from database (this will cascade to chat_messages and chat_sessions)
        logger.info(f"Removing interview {interview_id} from database")
        await interview_crud.remove(db, id=interview_id)

        logger.info(f"Successfully deleted interview {interview_id}")

    except Exception as e:
        logger.error(f"Error deleting interview {interview_id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error deleting interview: {str(e)}"
        )


@router.post("/{interview_id}/upload", response_model=InterviewOut)
async def upload_audio(
        interview_id: uuid.UUID = Path(..., description="The ID of the interview to upload audio for"),
        files: List[UploadFile] = File(..., description="Audio files to upload"),
        current_user: User = Depends(get_current_active_user),
        db: AsyncSession = Depends(get_db),
) -> Any:
    """
    Upload audio files for an interview.
    """
    try:
        # Validate ownership
        interview = await validate_interview_ownership(db, interview_id, current_user.id)

        # Process and save files
        filenames = []
        for file in files:
            # Check file type
            content_type = file.content_type or ""
            if not content_type.startswith("audio/"):
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"File {file.filename} is not an audio file",
                )

            # Check file size
            file_size = 0
            chunk = await file.read(1024)
            while chunk:
                file_size += len(chunk)
                if file_size > settings.MAX_UPLOAD_SIZE:
                    raise HTTPException(
                        status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
                        detail=f"File {file.filename} exceeds maximum size of {settings.MAX_UPLOAD_SIZE / 1024 / 1024}MB",
                    )
                chunk = await file.read(1024)

            # Reset file position
            await file.seek(0)

            # Save file
            filename = await file_service.save_file(file, settings.UPLOAD_DIR)
            filenames.append(filename)

        # Update interview
        current_filenames = interview.get_original_filenames()
        current_filenames.extend(filenames)

        interview.set_original_filenames(current_filenames)
        interview.status = InterviewStatus.UPLOADED
        await db.commit()
        await db.refresh(interview)

        return interview
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error uploading audio for interview {interview_id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error uploading audio: {str(e)}"
        )


@router.post("/{interview_id}/process", response_model=InterviewTaskResponse)
async def process_audio(
        interview_id: uuid.UUID = Path(..., description="The ID of the interview to process"),
        background_tasks: BackgroundTasks = BackgroundTasks(),
        current_user: User = Depends(get_current_active_user),
        db: AsyncSession = Depends(get_db),
) -> Any:
    """
    Process audio files for an interview.
    """
    # Validate ownership
    interview = await validate_interview_ownership(db, interview_id, current_user.id)

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
        interview_id: uuid.UUID = Path(..., description="The ID of the interview to transcribe"),
        language: Optional[str] = Form(None, description="Language code for transcription"),
        background_tasks: BackgroundTasks = BackgroundTasks(),
        current_user: User = Depends(get_current_active_user),
        db: AsyncSession = Depends(get_db),
) -> Any:
    """
    Transcribe processed audio files for an interview.
    """
    # Validate ownership
    interview = await validate_interview_ownership(db, interview_id, current_user.id)

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
        interview_id: uuid.UUID = Path(..., description="The ID of the interview to get audio for"),
        current_user: User = Depends(get_current_active_user),
        db: AsyncSession = Depends(get_db),
) -> Any:
    """
    Get audio URL for an interview.
    """
    # Validate ownership
    interview = await validate_interview_ownership(db, interview_id, current_user.id)

    # First check for processed files (preferred if available)
    processed_filenames = interview.get_processed_filenames()
    if processed_filenames:
        audio_filename = processed_filenames[0]
        return {
            "audio_url": f"/api/media/processed/{audio_filename}",
            "is_processed": True
        }

    # If no processed files, try original files
    original_filenames = interview.get_original_filenames()
    if original_filenames:
        audio_filename = original_filenames[0]
        return {
            "audio_url": f"/api/media/uploads/{audio_filename}",
            "is_processed": False
        }

    # If we get here, no audio files are available
    raise HTTPException(
        status_code=status.HTTP_400_BAD_REQUEST,
        detail="No audio files available",
    )


@router.put("/{interview_id}/transcription", response_model=InterviewOut)
async def update_transcription(
        transcription_update: TranscriptUpdateRequest,
        interview_id: uuid.UUID = Path(..., description="The ID of the interview to update transcription for"),
        current_user: User = Depends(get_current_active_user),
        db: AsyncSession = Depends(get_db),
) -> Any:
    """
    Update transcription text for an interview.
    """
    # Validate ownership
    interview = await validate_interview_ownership(db, interview_id, current_user.id)

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


@router.put("/{interview_id}/transcript-segments", response_model=InterviewOut)
async def update_transcript_segments(
        segments_update: TranscriptSegmentsUpdateRequest,
        interview_id: uuid.UUID = Path(..., description="The ID of the interview to update segments for"),
        current_user: User = Depends(get_current_active_user),
        db: AsyncSession = Depends(get_db),
) -> Any:
    """
    Update transcript segments for an interview.
    """
    # Validate ownership
    interview = await validate_interview_ownership(db, interview_id, current_user.id)

    # Check if the interview has been transcribed
    if interview.status != InterviewStatus.TRANSCRIBED:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Interview must be transcribed first",
        )

    # Update segments
    interview.set_transcript_segments(segments_update.segments)
    await db.commit()
    await db.refresh(interview)

    return interview


@router.post("/{interview_id}/questionnaires/{questionnaire_id}", response_model=InterviewOut)
async def attach_questionnaire(
        interview_id: uuid.UUID = Path(..., description="The ID of the interview"),
        questionnaire_id: uuid.UUID = Path(..., description="The ID of the questionnaire to attach"),
        current_user: User = Depends(get_current_active_user),
        db: AsyncSession = Depends(get_db),
) -> Any:
    """
    Attach a questionnaire to an interview.
    """
    # Validate ownership
    interview = await validate_interview_ownership(db, interview_id, current_user.id)

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

    await db.commit()
    await db.refresh(interview)

    return interview


@router.delete("/{interview_id}/questionnaires/{questionnaire_id}", response_model=InterviewOut)
async def detach_questionnaire(
        interview_id: uuid.UUID = Path(..., description="The ID of the interview"),
        questionnaire_id: uuid.UUID = Path(..., description="The ID of the questionnaire to detach"),
        current_user: User = Depends(get_current_active_user),
        db: AsyncSession = Depends(get_db),
) -> Any:
    """
    Detach a questionnaire from an interview.
    """
    try:
        # Validate ownership
        interview = await validate_interview_ownership(db, interview_id, current_user.id)

        # Check if the questionnaire is attached
        query = select(interview_questionnaire).where(
            interview_questionnaire.c.interview_id == interview_id,
            interview_questionnaire.c.questionnaire_id == questionnaire_id
        )
        result = await db.execute(query)
        existing = result.first()

        if not existing:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Questionnaire is not attached to this interview",
            )

        # Remove from the many-to-many relationship
        stmt = interview_questionnaire.delete().where(
            interview_questionnaire.c.interview_id == interview_id,
            interview_questionnaire.c.questionnaire_id == questionnaire_id
        )
        await db.execute(stmt)

        # Remove any answers generated for this questionnaire
        if interview.generated_answers:
            generated_answers = interview.get_generated_answers()
            if str(questionnaire_id) in generated_answers:
                generated_answers.pop(str(questionnaire_id))
                interview.set_generated_answers(generated_answers)

        await db.commit()
        await db.refresh(interview)

        return interview
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error detaching questionnaire: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error detaching questionnaire: {str(e)}"
        )


@router.get("/questionnaires/{questionnaire_id}/interviews", response_model=Page[InterviewOut])
async def list_interviews_by_questionnaire(
        questionnaire_id: uuid.UUID = Path(..., description="The ID of the questionnaire"),
        page: int = Query(1, ge=1, description="Page number"),
        size: int = Query(10, ge=1, le=100, description="Items per page"),
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
    if questionnaire.creator_id != current_user.id and questionnaire.organization_id is None:
        # TODO: Add organization-based permissions
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not enough permissions",
        )

    # Query for interviews with this questionnaire through many-to-many relationship
    query = select(Interview).outerjoin(
        interview_questionnaire,
        Interview.id == interview_questionnaire.c.interview_id
    ).where(
        Interview.owner_id == current_user.id,
        interview_questionnaire.c.questionnaire_id == questionnaire_id
    ).order_by(Interview.updated_at.desc())

    # Use the paginate helper from fastapi_pagination
    return await paginate(
        db,
        query,
        params=Params(page=page, size=size)
    )


@router.post("/{interview_id}/generate-answers", response_model=InterviewTaskResponse)
async def generate_answers(
        interview_id: uuid.UUID = Path(..., description="The ID of the interview"),
        questionnaire_id: Optional[uuid.UUID] = Query(None, description="Optional specific questionnaire ID"),
        background_tasks: BackgroundTasks = BackgroundTasks(),
        current_user: User = Depends(get_current_active_user),
        db: AsyncSession = Depends(get_db),
) -> Any:
    """
    Generate answers for questionnaire questions based on interview transcript.
    """
    # Validate ownership
    interview = await validate_interview_ownership(db, interview_id, current_user.id)

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

        if not existing:
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