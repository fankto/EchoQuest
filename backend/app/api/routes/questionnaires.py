import uuid
from typing import Any, List, Optional
import json

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile, status
from fastapi_pagination import Page
from fastapi_pagination.ext.sqlalchemy import paginate
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_active_user
from app.crud.crud_questionnaire import questionnaire_crud
from app.db.session import get_db
from app.models.models import User
from app.schemas.questionnaire import (
    QuestionExtractionRequest,
    QuestionExtractionResponse,
    QuestionnaireCreate,
    QuestionnaireOut,
    QuestionnairePatch,
)
from app.services.questionnaire_service import questionnaire_service
import logging

router = APIRouter()

logger = logging.getLogger(__name__)


@router.post("/", response_model=QuestionnaireOut)
async def create_questionnaire(
    title: str = Form(...),
    content: str = Form(...),
    description: Optional[str] = Form(None),
    file: Optional[UploadFile] = File(None),
    questions: Optional[str] = Form(None),
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
) -> Any:
    """
    Create a new questionnaire.
    """
    # If file is provided, extract content
    if file:
        # Extract content from file (implementation depends on file type)
        file_content = await questionnaire_service.extract_content_from_file(file)
        content = file_content
    
    # Create questionnaire data
    questionnaire_in = QuestionnaireCreate(
        title=title,
        description=description,
        content=content,
    )
    
    # Parse questions if provided
    parsed_questions = None
    if questions:
        try:
            parsed_questions = json.loads(questions)
        except json.JSONDecodeError:
            logger.error(f"Failed to parse questions JSON: {questions}")
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="Invalid questions format",
            )
    
    # If questions are not provided or parsing failed, extract them
    if not parsed_questions:
        parsed_questions = await questionnaire_service.extract_questions(content)
    
    # Create questionnaire
    questionnaire = await questionnaire_crud.create(
        db=db,
        obj_in=questionnaire_in,
        creator_id=current_user.id,
        questions=parsed_questions,
    )
    
    await db.commit()
    await db.refresh(questionnaire)
    
    # Get interview count for the new questionnaire
    interview_count = 0
    
    # Return with interview count
    return {
        **questionnaire.__dict__,
        "interview_count": interview_count,
    }


@router.get("/", response_model=List[QuestionnaireOut])
async def read_questionnaires(
    skip: int = 0,
    limit: int = 100,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
) -> Any:
    """
    Retrieve questionnaires for current user.
    """
    # Get organization ID if user belongs to an organization
    # This is a simplified version - in a real app, you'd get the user's organizations
    organization_id = None
    
    logger.debug(f"Fetching questionnaires for user {current_user.id}")
    questionnaires = await questionnaire_crud.get_multi_by_creator(
        db, creator_id=current_user.id, organization_id=organization_id, skip=skip, limit=limit
    )
    logger.debug(f"Found {len(questionnaires)} questionnaires")
    
    # Add interview count for each questionnaire
    result = []
    for q in questionnaires:
        q_with_count, count = await questionnaire_crud.get_with_interview_count(db, id=q.id)
        result.append({
            **q.__dict__,
            "interview_count": count,
        })
    
    logger.debug(f"Returning {len(result)} questionnaires")
    return result


@router.get("/{questionnaire_id}", response_model=QuestionnaireOut)
async def read_questionnaire(
    questionnaire_id: uuid.UUID,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
) -> Any:
    """
    Get questionnaire by ID.
    """
    questionnaire = await questionnaire_crud.get(db, id=questionnaire_id)
    if not questionnaire:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Questionnaire not found",
        )
    
    # Check if user has access
    if questionnaire.creator_id != current_user.id:
        # Check if questionnaire belongs to user's organization
        # This is a simplified version - in a real app, you'd check organization membership
        if not questionnaire.organization_id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Not enough permissions",
            )
    
    # Get interview count
    _, count = await questionnaire_crud.get_with_interview_count(db, id=questionnaire_id)
    
    # Return with interview count
    return {
        **questionnaire.__dict__,
        "interview_count": count,
    }


@router.patch("/{questionnaire_id}", response_model=QuestionnaireOut)
async def update_questionnaire(
    questionnaire_id: uuid.UUID,
    title: Optional[str] = Form(None),
    content: Optional[str] = Form(None),
    description: Optional[str] = Form(None),
    questions: Optional[str] = Form(None),
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
) -> Any:
    """
    Update questionnaire.
    """
    questionnaire = await questionnaire_crud.get(db, id=questionnaire_id)
    if not questionnaire:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Questionnaire not found",
        )
    
    # Check if user has access
    if questionnaire.creator_id != current_user.id:
        # Check if questionnaire belongs to user's organization and user is admin
        # This is a simplified version - in a real app, you'd check organization membership and role
        if not questionnaire.organization_id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Not enough permissions",
            )
    
    # Parse questions if provided
    parsed_questions = None
    if questions:
        try:
            parsed_questions = json.loads(questions)
        except json.JSONDecodeError:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="Invalid questions format. Expected JSON string.",
            )
    
    # Create update data
    update_data = QuestionnairePatch(
        title=title,
        content=content,
        description=description,
        questions=parsed_questions,
    )
    
    # Always extract questions if content is updated
    if content:
        questions = await questionnaire_service.extract_questions(content)
        update_data.questions = questions
    
    # Update questionnaire
    questionnaire = await questionnaire_crud.update(
        db, db_obj=questionnaire, obj_in=update_data
    )
    
    await db.commit()
    await db.refresh(questionnaire)
    
    # Get interview count
    _, count = await questionnaire_crud.get_with_interview_count(db, id=questionnaire_id)
    
    # Return with interview count
    return {
        **questionnaire.__dict__,
        "interview_count": count,
    }


@router.delete("/{questionnaire_id}", response_model=dict)
async def delete_questionnaire(
    questionnaire_id: uuid.UUID,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
) -> Any:
    """
    Delete questionnaire.
    """
    questionnaire = await questionnaire_crud.get(db, id=questionnaire_id)
    if not questionnaire:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Questionnaire not found",
        )
    
    # Check if user has access
    if questionnaire.creator_id != current_user.id:
        # Check if questionnaire belongs to user's organization and user is admin
        # This is a simplified version - in a real app, you'd check organization membership and role
        if not questionnaire.organization_id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Not enough permissions",
            )
    
    # Get number of interviews using this questionnaire
    _, count = await questionnaire_crud.get_with_interview_count(db, id=questionnaire_id)
    
    # Optionally, prevent deletion if there are associated interviews
    if count > 0:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Cannot delete questionnaire with {count} associated interviews",
        )
    
    # Delete questionnaire
    await questionnaire_crud.remove(db, id=questionnaire_id)
    
    return {"message": "Questionnaire deleted successfully"}


@router.post("/extract-questions", response_model=QuestionExtractionResponse)
async def extract_questions(
    request: QuestionExtractionRequest,
    current_user: User = Depends(get_current_active_user),
) -> Any:
    """
    Extract questions from content.
    """
    # Extract questions
    questions = await questionnaire_service.extract_questions(request.content)
    
    return QuestionExtractionResponse(questions=questions)