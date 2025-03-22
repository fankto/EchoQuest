from typing import List, Optional, Tuple, Dict, Any
from uuid import UUID

from sqlalchemy import select, func, or_
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import joinedload

from app.crud.base import CRUDBase
from app.models.models import Questionnaire, Interview, interview_questionnaire
from app.schemas.questionnaire import QuestionnaireCreate, QuestionnairePatch


class CRUDQuestionnaire(CRUDBase[Questionnaire, QuestionnaireCreate, QuestionnairePatch]):
    """CRUD operations for Questionnaire model"""

    async def create(
            self,
            db: AsyncSession,
            *,
            obj_in: QuestionnaireCreate,
            creator_id: UUID,
            organization_id: Optional[UUID] = None,
            questions: Optional[List[str]] = None,
    ) -> Questionnaire:
        """Create a new questionnaire"""
        questionnaire = Questionnaire(
            title=obj_in.title,
            description=obj_in.description,
            content=obj_in.content,
            creator_id=creator_id,
            organization_id=organization_id,
            questions=questions or [],
        )

        db.add(questionnaire)
        await db.flush()
        await db.refresh(questionnaire)
        return questionnaire

    async def get_with_interview_count(
            self, db: AsyncSession, id: UUID
    ) -> Optional[Tuple[Questionnaire, int]]:
        """Get questionnaire with interview count"""
        # First get the questionnaire
        result = await db.execute(
            select(Questionnaire).where(Questionnaire.id == id)
        )
        questionnaire = result.scalars().first()

        if not questionnaire:
            return None

        # Count interviews through the many-to-many relationship
        result = await db.execute(
            select(func.count())
            .select_from(interview_questionnaire)
            .where(interview_questionnaire.c.questionnaire_id == id)
        )
        count = result.scalar_one()

        return (questionnaire, count)

    async def get_multi_by_creator(
            self,
            db: AsyncSession,
            *,
            creator_id: UUID,
            organization_id: Optional[UUID] = None,
            skip: int = 0,
            limit: int = 100,
    ) -> List[Questionnaire]:
        """Get questionnaires by creator or organization"""
        query = select(Questionnaire)

        if organization_id:
            # Get questionnaires created by user or owned by their organization
            query = query.where(
                or_(
                    Questionnaire.creator_id == creator_id,
                    Questionnaire.organization_id == organization_id,
                )
            )
        else:
            # Get only personally created questionnaires
            query = query.where(Questionnaire.creator_id == creator_id)

        query = query.order_by(Questionnaire.created_at.desc()).offset(skip).limit(limit)

        result = await db.execute(query)
        return result.scalars().all()

    async def get_multi_with_counts(
            self,
            db: AsyncSession,
            *,
            creator_id: UUID,
            organization_id: Optional[UUID] = None,
            skip: int = 0,
            limit: int = 100,
    ) -> List[Dict[str, Any]]:
        """Get questionnaires with interview counts"""
        # First get the questionnaires
        questionnaires = await self.get_multi_by_creator(
            db,
            creator_id=creator_id,
            organization_id=organization_id,
            skip=skip,
            limit=limit
        )

        if not questionnaires:
            return []

        # Get interview counts for each questionnaire
        result_list = []
        for q in questionnaires:
            query = select(func.count()) \
                .select_from(interview_questionnaire) \
                .where(interview_questionnaire.c.questionnaire_id == q.id)

            result = await db.execute(query)
            count = result.scalar_one()

            # Convert to dict and add count
            q_dict = {
                **q.__dict__,
                "interview_count": count,
            }

            # Remove SQLAlchemy state attributes
            q_dict.pop('_sa_instance_state', None)

            result_list.append(q_dict)

        return result_list

    async def get_questions(
            self, db: AsyncSession, questionnaire_id: UUID
    ) -> List[str]:
        """Get questions for a questionnaire"""
        questionnaire = await self.get(db, id=questionnaire_id)
        if not questionnaire:
            return []
        return questionnaire.questions or []


questionnaire_crud = CRUDQuestionnaire(Questionnaire)