# backend/src/questionnaire_manager/crud.py
from typing import List, Dict

from sqlalchemy.orm import Session

from . import models, schemas


def create_questionnaire(db: Session, questionnaire: schemas.QuestionnaireCreate, questions: Dict[str, list]):
    db_questionnaire = models.Questionnaire(
        title=questionnaire.title,
        content=questionnaire.content,
        file_type=questionnaire.file_type,
        questions=questions['items']
    )
    db.add(db_questionnaire)
    db.commit()
    db.refresh(db_questionnaire)
    return db_questionnaire


def get_questionnaire(db: Session, questionnaire_id: int):
    return db.query(models.Questionnaire).filter(models.Questionnaire.id == questionnaire_id).first()


def get_questionnaires(db: Session, skip: int = 0, limit: int = 100):
    questionnaires = db.query(models.Questionnaire).offset(skip).limit(limit).all()
    for questionnaire in questionnaires:
        if isinstance(questionnaire.questions, dict) and 'items' in questionnaire.questions:
            questionnaire.questions = questionnaire.questions['items']
        if questionnaire.updated_at is None:
            questionnaire.updated_at = questionnaire.created_at
    db.commit()
    return questionnaires


def update_questionnaire(db: Session, questionnaire_id: int, questionnaire: schemas.QuestionnaireCreate,
                         questions: List[str] = None):
    db_questionnaire = db.query(models.Questionnaire).filter(models.Questionnaire.id == questionnaire_id).first()
    if db_questionnaire:
        db_questionnaire.title = questionnaire.title
        db_questionnaire.content = questionnaire.content
        db_questionnaire.file_type = questionnaire.file_type
        if questions is not None:
            db_questionnaire.questions = questions
        db.commit()
        db.refresh(db_questionnaire)
    return db_questionnaire


def delete_questionnaire(db: Session, questionnaire_id: int):
    db_questionnaire = db.query(models.Questionnaire).filter(models.Questionnaire.id == questionnaire_id).first()
    if db_questionnaire:
        db.delete(db_questionnaire)
        db.commit()
        return True
    return False