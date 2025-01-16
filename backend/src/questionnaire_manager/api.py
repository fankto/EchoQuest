# backend/src/questionnaire_manager/api.py
import io
from typing import List

import PyPDF2
import docx2txt
from fastapi import APIRouter, File, UploadFile, Depends, HTTPException, Form
from sqlalchemy.orm import Session

from . import crud, models, schemas
from .database import SessionLocal, engine
from .llm_question_extractor import extract_and_verify_questions

router = APIRouter()

models.Base.metadata.create_all(bind=engine)

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

@router.post("/", response_model=schemas.Questionnaire)
async def create_questionnaire(
        title: str = Form(...),
        file: UploadFile = File(None),
        content: str = Form(None),
        db: Session = Depends(get_db)
):
    if not file and not content:
        raise HTTPException(status_code=400, detail="Either file or content must be provided")

    if file:
        file_content = await file.read()
        file_type = file.filename.split(".")[-1].lower()

        try:
            if file_type == "docx":
                content = docx2txt.process(io.BytesIO(file_content))
            elif file_type == "pdf":
                pdf_reader = PyPDF2.PdfReader(io.BytesIO(file_content))
                content = ""
                for page in pdf_reader.pages:
                    content += page.extract_text()
            elif file_type == "txt":
                content = file_content.decode()
            else:
                raise HTTPException(status_code=400, detail=f"Unsupported file type: {file_type}")
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Error processing file: {str(e)}")

    try:
        # Extract questions and await the result
        extracted_questions = await extract_and_verify_questions(content)

        questionnaire = schemas.QuestionnaireCreate(
            title=title,
            content=content,
            file_type=file.filename if file else "manual"
        )

        db_questionnaire = crud.create_questionnaire(db, questionnaire, extracted_questions)

        if db_questionnaire.updated_at is None:
            db_questionnaire.updated_at = db_questionnaire.created_at
            db.commit()

        return db_questionnaire
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error creating questionnaire: {str(e)}")

@router.get("/", response_model=List[schemas.Questionnaire])
def read_questionnaires(skip: int = 0, limit: int = 100, db: Session = Depends(get_db)):
    questionnaires = crud.get_questionnaires(db, skip=skip, limit=limit)
    return [schemas.Questionnaire(
        id=q.id,
        title=q.title,
        content=q.content,
        file_type=q.file_type,
        questions=q.questions,
        created_at=q.created_at,
        updated_at=q.updated_at,
        interviews=[schemas.InterviewBrief(
            id=i.id,
            interviewee_name=i.interviewee_name,
            date=i.date,
            status=i.status
        ) for i in q.interviews]
    ) for q in questionnaires]

@router.get("/{questionnaire_id}", response_model=schemas.Questionnaire)
def read_questionnaire(questionnaire_id: int, db: Session = Depends(get_db)):
    db_questionnaire = crud.get_questionnaire(db, questionnaire_id=questionnaire_id)
    if db_questionnaire is None:
        raise HTTPException(status_code=404, detail="Questionnaire not found")
    return db_questionnaire

@router.put("/{questionnaire_id}", response_model=schemas.Questionnaire)
async def update_questionnaire(
        questionnaire_id: int,
        title: str = Form(...),
        content: str = Form(...),
        db: Session = Depends(get_db)
):
    db_questionnaire = crud.get_questionnaire(db, questionnaire_id=questionnaire_id)
    if db_questionnaire is None:
        raise HTTPException(status_code=404, detail="Questionnaire not found")

    # Extract questions and await the result
    extracted_questions = await extract_and_verify_questions(content)
    questions = extracted_questions['items'] if isinstance(extracted_questions, dict) else extracted_questions

    questionnaire_data = schemas.QuestionnaireCreate(
        title=title,
        content=content,
        file_type="manual"  # Since we're updating manually, we'll set this to "manual"
    )

    updated_questionnaire = crud.update_questionnaire(db, questionnaire_id, questionnaire_data, questions)
    return updated_questionnaire

@router.delete("/{questionnaire_id}")
async def delete_questionnaire(questionnaire_id: int, db: Session = Depends(get_db)):
    questionnaire = db.query(models.Questionnaire).filter(models.Questionnaire.id == questionnaire_id).first()
    if not questionnaire:
        raise HTTPException(status_code=404, detail="Questionnaire not found")
    db.delete(questionnaire)
    db.commit()
    return {"message": "Questionnaire deleted successfully"}