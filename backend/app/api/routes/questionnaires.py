from typing import Any, List, Optional
import uuid
import json

from fastapi import APIRouter, Depends, File, Form, HTTPException, Path, Query, UploadFile, status
from sqlalchemy.ext.asyncio import AsyncSession
from fastapi.responses import JSONResponse

from app.api.deps import get_current_active_user
from app.crud.crud_questionnaire import questionnaire_crud
from app.crud.crud_organization import organization_crud
from app.db.session import get_db
from app.models.models import User, OrganizationRole
from app.schemas.questionnaire import (
    QuestionExtractionRequest,
    QuestionExtractionResponse,
    QuestionnaireCreate,
    QuestionnaireOut,
    QuestionnairePatch,
    QuestionnaireWithInterviews,
)
from app.services.questionnaire_service import questionnaire_service
from app.utils.pagination import get_pagination_params
from loguru import logger

router = APIRouter()


@router.post("/", response_model=QuestionnaireOut, status_code=status.HTTP_201_CREATED)
async def create_questionnaire(
        title: str = Form(..., description="Questionnaire title"),
        content: str = Form(..., description="Questionnaire content"),
        description: Optional[str] = Form(None, description="Optional description"),
        organization_id: Optional[uuid.UUID] = Form(None, description="Optional organization ID"),
        file: Optional[UploadFile] = File(None, description="Optional file with questionnaire content"),
        questions: Optional[str] = Form(None, description="Optional JSON string of questions"),
        current_user: User = Depends(get_current_active_user),
        db: AsyncSession = Depends(get_db),
) -> Any:
    """
    Create a new questionnaire.
    """
    # Check organization access if provided
    if organization_id:
        org_role = await organization_crud.get_member_role(db, organization_id=organization_id, user_id=current_user.id)
        if not org_role or org_role not in [OrganizationRole.ADMIN, OrganizationRole.OWNER]:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="You need admin or owner role to create organization questionnaires",
            )

    # If file is provided, extract content
    if file:
        try:
            # Extract content from file
            file_content = await questionnaire_service.extract_content_from_file(file)
            if file_content:
                content = file_content
        except Exception as e:
            logger.error(f"Error extracting content from file: {e}")
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail=f"Error extracting content from file: {str(e)}",
            )

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
            if not isinstance(parsed_questions, list):
                raise ValueError("Questions must be a list")
        except (json.JSONDecodeError, ValueError) as e:
            logger.error(f"Failed to parse questions JSON: {questions} - {e}")
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail=f"Invalid questions format: {str(e)}",
            )

    # If questions are not provided or parsing failed, extract them
    if not parsed_questions:
        parsed_questions = await questionnaire_service.extract_questions(content)

    # Create questionnaire
    questionnaire = await questionnaire_crud.create(
        db=db,
        obj_in=questionnaire_in,
        creator_id=current_user.id,
        organization_id=organization_id,
        questions=parsed_questions,
    )

    await db.commit()
    await db.refresh(questionnaire)

    # Return with interview count (0 for new questionnaire)
    return {
        **questionnaire.__dict__,
        "interview_count": 0,
    }


@router.get("/", response_model=List[QuestionnaireOut])
async def read_questionnaires(
        page: int = Query(1, ge=1, description="Page number"),
        size: int = Query(10, ge=1, le=100, description="Page size"),
        organization_id: Optional[uuid.UUID] = Query(None, description="Filter by organization ID"),
        current_user: User = Depends(get_current_active_user),
        db: AsyncSession = Depends(get_db),
) -> Any:
    """
    Retrieve questionnaires for current user.
    """
    # Get organization ID if provided and validate access
    if organization_id:
        org_role = await organization_crud.get_member_role(db, organization_id=organization_id, user_id=current_user.id)
        if not org_role:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Not a member of this organization",
            )

    # Calculate skip based on page and size
    skip = (page - 1) * size

    # Get questionnaires with interview counts
    questionnaires = await questionnaire_crud.get_multi_with_counts(
        db,
        creator_id=current_user.id,
        organization_id=organization_id,
        skip=skip,
        limit=size
    )

    return questionnaires


@router.get("/{questionnaire_id}", response_model=QuestionnaireOut)
async def read_questionnaire(
        questionnaire_id: uuid.UUID = Path(..., description="The ID of the questionnaire to retrieve"),
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
        if questionnaire.organization_id:
            org_role = await organization_crud.get_member_role(
                db,
                organization_id=questionnaire.organization_id,
                user_id=current_user.id
            )
            if not org_role:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="Not enough permissions",
                )
        else:
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
        questionnaire_id: uuid.UUID = Path(..., description="The ID of the questionnaire to update"),
        title: Optional[str] = Form(None, description="Updated title"),
        content: Optional[str] = Form(None, description="Updated content"),
        description: Optional[str] = Form(None, description="Updated description"),
        questions: Optional[str] = Form(None, description="Updated questions as JSON array"),
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
    has_permission = False
    if questionnaire.creator_id == current_user.id:
        has_permission = True
    elif questionnaire.organization_id:
        # Check if questionnaire belongs to user's organization and user is admin
        org_role = await organization_crud.get_member_role(
            db,
            organization_id=questionnaire.organization_id,
            user_id=current_user.id
        )
        if org_role in [OrganizationRole.ADMIN, OrganizationRole.OWNER]:
            has_permission = True

    if not has_permission:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not enough permissions",
        )

    # Parse questions if provided
    parsed_questions = None
    if questions:
        try:
            parsed_questions = json.loads(questions)
            if not isinstance(parsed_questions, list):
                raise ValueError("Questions must be a list")
        except (json.JSONDecodeError, ValueError) as e:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail=f"Invalid questions format: {str(e)}",
            )

    # Create update data
    update_data = QuestionnairePatch(
        title=title,
        content=content,
        description=description,
        questions=parsed_questions,
    )

    # If content is updated but questions aren't, extract questions from content
    if content and not parsed_questions:
        new_questions = await questionnaire_service.extract_questions(content)
        update_data.questions = new_questions

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


@router.delete("/{questionnaire_id}")
async def delete_questionnaire(
        questionnaire_id: uuid.UUID = Path(..., description="The ID of the questionnaire to delete"),
        force: bool = Query(False, description="Force deletion even if questionnaire is in use"),
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
    has_permission = False
    if questionnaire.creator_id == current_user.id:
        has_permission = True
    elif questionnaire.organization_id:
        # Check if questionnaire belongs to user's organization and user is admin/owner
        org_role = await organization_crud.get_member_role(
            db,
            organization_id=questionnaire.organization_id,
            user_id=current_user.id
        )
        if org_role in [OrganizationRole.ADMIN, OrganizationRole.OWNER]:
            has_permission = True

    if not has_permission:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not enough permissions",
        )

    # Get number of interviews using this questionnaire
    _, count = await questionnaire_crud.get_with_interview_count(db, id=questionnaire_id)

    # Prevent deletion if there are associated interviews, unless force=True
    if count > 0 and not force:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Cannot delete questionnaire with {count} associated interviews. Use force=true to override.",
        )

    # Delete questionnaire
    await questionnaire_crud.remove(db, id=questionnaire_id)

    return JSONResponse(
        status_code=status.HTTP_200_OK,
        content={"message": "Questionnaire deleted successfully"}
    )


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