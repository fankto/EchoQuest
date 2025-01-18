# backend/src/interview_manager/audio_endpoints.py
import gc
import json
import mimetypes
import os
import tempfile
import uuid
from datetime import datetime
from itertools import chain
from os.path import basename
from typing import Optional, List, Dict

import torch
from dateutil import parser

from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks, File, UploadFile, Form, Body, Query
from pydantic import BaseModel, validator
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session
from starlette.responses import FileResponse

from .models import Interview, InterviewMetadata
from ..audio_processor.audio_processing_pipeline import AudioProcessingPipeline
from ..audio_processor.config import settings as audio_settings
from ..audio_transcription.models import TranscriptionUpdate
from ..database import get_db
from ..question_answerer.question_answerer import question_answerer
from ..questionnaire_manager import crud as questionnaire_crud
import logging

from ..questionnaire_manager.models import Questionnaire
from ..transcription.transcription import TranscriptionModule

logger = logging.getLogger(__name__)


router = APIRouter()

class QuestionnaireResponse(BaseModel):
    id: int
    title: str
    description: Optional[str] = None  # Ensure this is Optional
    questions: List[str]

    class Config:
        orm_mode = True

class InterviewResponse(BaseModel):
    id: int
    interviewee_name: str
    date: datetime
    location: str
    status: str
    duration: Optional[float]
    error_message: Optional[str]
    original_filenames: Optional[List[str]]
    processed_filenames: Optional[List[str]]
    questionnaire: Optional[QuestionnaireResponse] = None
    transcriptions: Optional[List[Dict]] = None
    merged_transcription: Optional[str] = None
    generated_answers: Optional[Dict] = None
    min_speakers: Optional[int] = None
    max_speakers: Optional[int] = None

    @validator('original_filenames', pre=True)
    def parse_original_filenames(cls, v):
        if isinstance(v, str):
            return json.loads(v)
        return v

    @validator('processed_filenames', pre=True)
    def parse_processed_filenames(cls, v):
        if isinstance(v, str):
            return json.loads(v)
        return v

    @validator('transcriptions', pre=True)
    def parse_transcriptions(cls, v):
        if isinstance(v, str):
            return json.loads(v)
        return v

    @validator('generated_answers', pre=True)
    def parse_generated_answers(cls, v):
        if isinstance(v, str):
            return json.loads(v)
        return v

    class Config:
        orm_mode = True


class AnswerGenerationResponse(BaseModel):
    message: str


class AnswerProgressResponse(BaseModel):
    status: str
    progress: float
    error_message: Optional[str]


class MetadataCreate(BaseModel):
    key: str
    value: str


class MetadataResponse(BaseModel):
    id: int
    key: str
    value: str


@router.post("/upload", response_model=InterviewResponse)
async def upload_audio(
        files: List[UploadFile] = File(...),
        interviewee_name: str = Form(...),
        date: str = Form(...),
        location: str = Form(...),
        questionnaire_id: int = Form(...),
        db: Session = Depends(get_db)
):
    try:
        parsed_date = parser.isoparse(date)

        questionnaire = db.query(Questionnaire).filter(Questionnaire.id == questionnaire_id).first()
        if not questionnaire:
            raise HTTPException(status_code=404, detail="Questionnaire not found")

        new_interview = Interview(
            interviewee_name=interviewee_name,
            date=parsed_date,
            location=location,
            status="uploaded",
            questionnaire=questionnaire
        )
        db.add(new_interview)
        db.commit()
        db.refresh(new_interview)

        filenames = []
        for file in files:
            unique_filename = f"{uuid.uuid4()}_{basename(file.filename)}"
            file_path = os.path.join(audio_settings.UPLOAD_DIRECTORY, unique_filename)
            with open(file_path, "wb") as buffer:
                buffer.write(await file.read())
            filenames.append(unique_filename)

        new_interview.original_filenames = json.dumps(filenames)
        db.commit()

        # Fetch the associated questionnaire
        questionnaire = db.query(Questionnaire).filter(Questionnaire.id == questionnaire_id).first()
        if not questionnaire:
            raise HTTPException(status_code=404, detail="Questionnaire not found")

        new_interview.questionnaire = questionnaire

        db.commit()
        db.refresh(new_interview)

        return new_interview
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=400, detail=str(e))

@router.post("/{interview_id}/add-audio")
async def add_audio_file(interview_id: int, file: UploadFile = File(...), db: Session = Depends(get_db)):
    interview = db.query(Interview).filter(Interview.id == interview_id).first()
    if not interview:
        raise HTTPException(status_code=404, detail="Interview not found")

    # Generate a unique filename
    unique_filename = f"{uuid.uuid4()}_{basename(file.filename)}"
    file_path = os.path.join(audio_settings.UPLOAD_DIRECTORY, unique_filename)

    # Save the new audio file
    with open(file_path, "wb") as buffer:
        buffer.write(await file.read())

    # Update the interview record with just the filename
    current_filenames = json.loads(interview.original_filenames or '[]')
    current_filenames.append(unique_filename)
    interview.original_filenames = json.dumps(current_filenames)
    db.commit()

    return {"message": "Audio file added successfully", "filename": unique_filename}

@router.post("/{interview_id}/remove-audio")
async def remove_audio_file(interview_id: int, filename: str = Body(..., embed=True), db: Session = Depends(get_db)):
    interview = db.query(Interview).filter(Interview.id == interview_id).first()
    if not interview:
        raise HTTPException(status_code=404, detail="Interview not found")

    current_filenames = json.loads(interview.original_filenames or '[]')
    if filename not in current_filenames:
        raise HTTPException(status_code=400, detail="File not found in interview")

    file_path = os.path.join(audio_settings.UPLOAD_DIRECTORY, filename)
    if os.path.exists(file_path):
        os.remove(file_path)

    current_filenames.remove(filename)
    interview.original_filenames = json.dumps(current_filenames)
    db.commit()

    return {"message": "Audio file removed successfully"}

# Modify the existing process_audio function to handle multiple files
@router.post("/process/{interview_id}", response_model=InterviewResponse)
async def process_audio(interview_id: int, background_tasks: BackgroundTasks, db: Session = Depends(get_db)):
    interview = db.query(Interview).filter(Interview.id == interview_id).first()
    if not interview:
        raise HTTPException(status_code=404, detail="Interview not found")

    if not interview.original_filenames:
        raise HTTPException(status_code=400, detail="No original audio files found. Please upload audio files first.")

    def process_task(interview_id: int):
        try:
            db = next(get_db())
            interview = db.query(Interview).filter(Interview.id == interview_id).first()

            interview.status = "processing"
            db.commit()

            pipeline = AudioProcessingPipeline()
            processed_filenames = []
            file_infos = []
            for filename in json.loads(interview.original_filenames or '[]'):
                input_path = os.path.join(audio_settings.UPLOAD_DIRECTORY, filename)
                processed_waveform, file_info = pipeline.process(input_path)

                base_filename = os.path.splitext(filename)[0]
                processed_filename = f"processed_{base_filename}.wav"
                output_path = os.path.join(audio_settings.UPLOAD_DIRECTORY, processed_filename)
                pipeline.save_processed_audio(processed_waveform, output_path)
                processed_filenames.append(processed_filename)
                file_infos.append(file_info)

            interview.processed_filenames = json.dumps(processed_filenames)
            interview.status = "processed"
            interview.duration = sum(file_info['processed_duration'] for file_info in file_infos)
            db.commit()

            logger.info(f"Audio processing completed for interview {interview_id}")

        except Exception as e:
            logger.error(f"Error processing audio for interview {interview_id}: {str(e)}")
            interview.status = "error"
            interview.error_message = str(e)
            db.commit()

    background_tasks.add_task(process_task, interview_id)
    return interview

@router.get("/audio/{filename}")
async def get_audio(filename: str):
    logger.info(f"Retrieving audio file: {filename}")
    file_path = os.path.join(audio_settings.UPLOAD_DIRECTORY, filename)

    if not os.path.exists(file_path):
        raise HTTPException(status_code=404, detail="Audio file not found")

    # Dynamically determine MIME type based on file extension
    mime_type, _ = mimetypes.guess_type(file_path)

    # Default to "audio/mpeg" if MIME type couldn't be determined
    if mime_type is None:
        mime_type = "audio/mpeg"

    return FileResponse(file_path, media_type=mime_type)

# In audio_endpoints.py

@router.post("/transcribe/{interview_id}", response_model=InterviewResponse)
async def transcribe_audio(
        interview_id: int,
        background_tasks: BackgroundTasks,
        min_speakers: Optional[int] = Body(None),
        max_speakers: Optional[int] = Body(None),
        language: Optional[str] = Body(None),  # Add language parameter
        db: Session = Depends(get_db)
):
    interview = db.query(Interview).filter(Interview.id == interview_id).first()
    if not interview:
        raise HTTPException(status_code=404, detail="Interview not found")

    if not interview.processed_filenames:
        raise HTTPException(status_code=400, detail="No processed audio files found. Please process the audio first.")

    # Update interview with transcription settings
    interview.min_speakers = min_speakers if min_speakers is not None else interview.min_speakers
    interview.max_speakers = max_speakers if max_speakers is not None else interview.max_speakers
    interview.language = language  # Add this field to your Interview model
    db.commit()

    def transcribe_task(interview_id: int):
        logger.info(f"Starting transcription task for interview {interview_id}")
        try:
            db = next(get_db())
            interview = db.query(Interview).filter(Interview.id == interview_id).first()

            if not interview:
                logger.error(f"Interview {interview_id} not found")
                return

            interview.status = "transcribing"
            db.commit()

            transcription_module = TranscriptionModule()
            all_transcriptions = []

            processed_files = json.loads(interview.processed_filenames or '[]')
            logger.info(f"Processing {len(processed_files)} audio files for interview {interview_id}")

            for idx, filename in enumerate(processed_files, 1):
                logger.info(f"Processing file {idx}/{len(processed_files)}: {filename}")

                audio_path = os.path.join(audio_settings.UPLOAD_DIRECTORY, filename)
                if not os.path.exists(audio_path):
                    raise FileNotFoundError(f"Processed audio file not found: {audio_path}")

                try:
                    results = transcription_module.transcribe_and_diarize(
                        audio_path,
                        min_speakers=interview.min_speakers,
                        max_speakers=interview.max_speakers,
                        language=interview.language  # Pass language to transcription module
                    )
                    all_transcriptions.extend(results)
                    logger.info(f"Successfully transcribed file {idx}/{len(processed_files)}")
                except Exception as e:
                    error_msg = f"Error transcribing file {filename}: {str(e)}"
                    logger.error(error_msg, exc_info=True)
                    raise RuntimeError(error_msg)

            if not all_transcriptions:
                raise ValueError("No transcriptions were generated")

            logger.info("Merging all transcriptions")
            merged_transcriptions = transcription_module._merge_segments(all_transcriptions)
            formatted_transcription = transcription_module.format_as_transcription(merged_transcriptions)

            interview.transcriptions = json.dumps(all_transcriptions)
            interview.merged_transcription = formatted_transcription
            interview.status = "transcribed"
            db.commit()

        except Exception as e:
            logger.error(f"Error in transcribe_task: {str(e)}")
            interview.status = "error"
            interview.error_message = str(e)
            db.commit()
        finally:
            try:
                if torch.cuda.is_available():
                    torch.cuda.empty_cache()
                gc.collect()
            except Exception as cleanup_error:
                logger.error(f"Error during cleanup: {str(cleanup_error)}")

    background_tasks.add_task(transcribe_task, interview_id)
    return interview

@router.post("/generate-answers/{interview_id}", response_model=AnswerGenerationResponse)
async def generate_answers(interview_id: int, background_tasks: BackgroundTasks, db: Session = Depends(get_db)):
    interview = db.query(Interview).filter(Interview.id == interview_id).first()
    if not interview:
        raise HTTPException(status_code=404, detail="Interview not found")

    if not interview.merged_transcription:
        raise HTTPException(status_code=400, detail="No transcription found. Please transcribe the audio first.")

    questionnaire = questionnaire_crud.get_questionnaire(db, interview.questionnaire_id)
    if not questionnaire:
        raise HTTPException(status_code=404, detail="Associated questionnaire not found")

    async def generate_answers_task(interview_id: int):
        try:
            db = next(get_db())
            interview = db.query(Interview).filter(Interview.id == interview_id).first()
            questionnaire = questionnaire_crud.get_questionnaire(db, interview.questionnaire_id)
            if not questionnaire:
                raise HTTPException(status_code=404, detail="Associated questionnaire not found")

            interview.status = "answering"
            interview.progress = 0
            db.commit()

            context = interview.merged_transcription
            if not context:
                raise Exception("No merged transcription available for the interview.")

            generated_answers = {}
            total_questions = len(questionnaire.questions)
            for i, question in enumerate(questionnaire.questions, 1):
                try:
                    answer = await question_answerer.answer_question(question, context)
                    generated_answers[question] = answer

                    interview.progress = (i / total_questions) * 100
                    db.commit()
                except Exception as e:
                    generated_answers[question] = f"Error: {str(e)}"

            interview.generated_answers = json.dumps(generated_answers)
            interview.status = "answered"
            interview.progress = 100
            db.commit()

        except SQLAlchemyError as e:
            interview.status = "error"
            interview.error_message = f"Database error: {str(e)}"
            db.commit()
        except Exception as e:
            interview.status = "error"
            interview.error_message = str(e)
            db.commit()
        finally:
            question_answerer.unload_model()

    background_tasks.add_task(generate_answers_task, interview_id)
    return {"message": "Answer generation started"}


@router.get("/answer-progress/{interview_id}", response_model=AnswerProgressResponse)
async def get_answer_progress(interview_id: int, db: Session = Depends(get_db)):
    """
    Get the progress of the answer generation process for a specific interview.

    - **interview_id**: The ID of the interview to check progress for.
    - Returns the current status, progress percentage, and any error message.
    - Raises a 404 error if the interview is not found.
    """
    interview = db.query(Interview).filter(Interview.id == interview_id).first()
    if not interview:
        raise HTTPException(status_code=404, detail="Interview not found")

    return {
        "status": interview.status,
        "progress": interview.progress,
        "error_message": interview.error_message
    }


@router.post("/metadata/{interview_id}", response_model=MetadataResponse)
async def add_metadata(interview_id: int, metadata: MetadataCreate, db: Session = Depends(get_db)):
    """
    Add metadata to a specific interview.

    - **interview_id**: The ID of the interview to add metadata to.
    - **metadata**: The key-value pair to add as metadata.
    - Returns the created metadata object.
    - Raises a 404 error if the interview is not found.
    """
    interview = db.query(Interview).filter(Interview.id == interview_id).first()
    if not interview:
        raise HTTPException(status_code=404, detail="Interview not found")

    new_metadata = InterviewMetadata(interview_id=interview_id, key=metadata.key, value=metadata.value)
    db.add(new_metadata)
    db.commit()
    db.refresh(new_metadata)

    return new_metadata


@router.get("/metadata/{interview_id}", response_model=List[MetadataResponse])
async def get_metadata(interview_id: int, db: Session = Depends(get_db)):
    """
    Get all metadata for a specific interview.

    - **interview_id**: The ID of the interview to get metadata for.
    - Returns a list of metadata objects.
    - Raises a 404 error if the interview is not found.
    """
    interview = db.query(Interview).filter(Interview.id == interview_id).first()
    if not interview:
        raise HTTPException(status_code=404, detail="Interview not found")

    metadata = db.query(InterviewMetadata).filter(InterviewMetadata.interview_id == interview_id).all()
    return metadata


@router.get("/", response_model=List[InterviewResponse])
async def get_interviews(skip: int = 0, limit: int = 10, db: Session = Depends(get_db)):
    """
    Get a list of interviews.

    - **skip**: Number of interviews to skip (for pagination).
    - **limit**: Maximum number of interviews to return.
    - Returns a list of interview objects.
    """
    interviews = db.query(Interview).offset(skip).limit(limit).all()
    return interviews


@router.get("/{interview_id}", response_model=InterviewResponse)
async def get_interview(interview_id: int, db: Session = Depends(get_db)):
    """
    Get details of a specific interview.

    - **interview_id**: The ID of the interview to retrieve.
    - Returns the interview object.
    - Raises a 404 error if the interview is not found.
    """
    interview = db.query(Interview).filter(Interview.id == interview_id).first()
    if not interview:
        raise HTTPException(status_code=404, detail="Interview not found")
    return interview


@router.delete("/{interview_id}")
async def delete_interview(interview_id: int, db: Session = Depends(get_db)):
    interview = db.query(Interview).filter(Interview.id == interview_id).first()
    if not interview:
        raise HTTPException(status_code=404, detail="Interview not found")

    # Delete associated audio files
    if interview.original_filenames:
        filenames = json.loads(interview.original_filenames)
        for filename in filenames:
            file_path = os.path.join(audio_settings.UPLOAD_DIRECTORY, filename)
            if os.path.exists(file_path):
                os.remove(file_path)

    db.delete(interview)
    db.commit()
    return {"message": "Interview deleted successfully"}

@router.post("/{interview_id}/remove-processed-audio")
async def remove_processed_audio_file(
        interview_id: int,
        filename: str = Body(..., embed=True),
        db: Session = Depends(get_db)
):
    """
    Remove a processed audio file from an interview.

    - **interview_id**: The ID of the interview.
    - **filename**: The name of the processed audio file to remove.
    - Returns a message indicating success.
    - Raises a 404 error if the interview is not found.
    - Raises a 400 error if the file is not found in the interview's processed files.
    """
    interview = db.query(Interview).filter(Interview.id == interview_id).first()
    if not interview:
        raise HTTPException(status_code=404, detail="Interview not found")

    # Load the list of processed filenames
    current_filenames = json.loads(interview.processed_filenames or '[]')
    if filename not in current_filenames:
        raise HTTPException(status_code=400, detail="Processed file not found in interview")

    # Remove the file from the filesystem
    file_path = os.path.join(audio_settings.UPLOAD_DIRECTORY, filename)
    if os.path.exists(file_path):
        os.remove(file_path)
    else:
        raise HTTPException(status_code=404, detail="Processed audio file not found on the server")

    # Remove the filename from the list and update the interview
    current_filenames.remove(filename)
    interview.processed_filenames = json.dumps(current_filenames)

    # Reset status to 'uploaded' if no processed files remain
    if len(current_filenames) == 0:
        interview.status = 'uploaded'
        interview.duration = None
        interview.error_message = None

        # Clear fields related to transcriptions and answers
        interview.transcriptions = None
        interview.merged_transcription = None
        interview.generated_answers = None
        interview.progress = None

    db.commit()

    return {"message": "Processed audio file removed successfully"}

# Add this new endpoint to the existing audio_endpoints.py file

@router.put("/{interview_id}/update-questionnaire", response_model=InterviewResponse)
async def update_interview_questionnaire(
        interview_id: int,
        questionnaire_id: int = Body(..., embed=True),
        db: Session = Depends(get_db)
):
    interview = db.query(Interview).filter(Interview.id == interview_id).first()
    if not interview:
        raise HTTPException(status_code=404, detail="Interview not found")

    questionnaire = db.query(Questionnaire).filter(Questionnaire.id == questionnaire_id).first()
    if not questionnaire:
        raise HTTPException(status_code=404, detail="Questionnaire not found")

    interview.questionnaire_id = questionnaire_id
    interview.questionnaire = questionnaire
    db.commit()
    db.refresh(interview)

    return interview

@router.put("/{interview_id}/update-transcription")
async def update_transcription(
        interview_id: int,
        update: TranscriptionUpdate,
        db: Session = Depends(get_db)
):
    interview = db.query(Interview).filter(Interview.id == interview_id).first()
    if not interview:
        raise HTTPException(status_code=404, detail="Interview not found")

    interview.merged_transcription = update.transcription
    db.commit()
    db.refresh(interview)
    return {"message": "Transcription updated successfully"}