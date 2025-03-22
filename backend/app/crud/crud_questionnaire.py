from typing import List, Optional, Union, Dict, Any
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import joinedload

from app.crud.base import CRUDBase
from app.models.models import Questionnaire, Interview
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
        return questionnaire
    
    async def get_with_interview_count(
        self, db: AsyncSession, id: UUID
    ) -> Optional[tuple[Questionnaire, int]]:
        """Get questionnaire with interview count"""
        result = await db.execute(
            select(Questionnaire, func.count(Interview.id))
            .outerjoin(Interview, Questionnaire.id == Interview.questionnaire_id)
            .where(Questionnaire.id == id)
            .group_by(Questionnaire.id)
        )
        return result.first()
    
    def get_multi_by_creator_query(
        self, creator_id: UUID, organization_id: Optional[UUID] = None
    ):
        """Get query for questionnaires by creator or organization"""
        from sqlalchemy import or_
        
        query = select(Questionnaire).where(Questionnaire.creator_id == creator_id)
        
        if organization_id:
            query = query.where(
                or_(
                    Questionnaire.creator_id == creator_id,
                    Questionnaire.organization_id == organization_id,
                )
            )
        
        return query.order_by(Questionnaire.created_at.desc())
    
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
        query = self.get_multi_by_creator_query(creator_id, organization_id)
        query = query.offset(skip).limit(limit)
        
        result = await db.execute(query)
        return result.scalars().all()
    
    async def get_with_interviews(
        self, db: AsyncSession, id: UUID
    ) -> Optional[Questionnaire]:
        """Get questionnaire with interviews relationship loaded"""
        result = await db.execute(
            select(Questionnaire)
            .options(joinedload(Questionnaire.interviews))
            .where(Questionnaire.id == id)
        )
        return result.scalars().first()


questionnaire_crud = CRUDQuestionnaire(Questionnaire)