from typing import Any, Dict, List, Optional, Union

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.crud.base import CRUDBase
from app.models.models import Interview
from app.schemas.interview import InterviewCreate, InterviewPatch


class CRUDInterview(CRUDBase[Interview, InterviewCreate, InterviewPatch]):
    """CRUD operations for Interview model"""
    
    async def create(
        self,
        db: AsyncSession,
        *,
        obj_in: InterviewCreate,
        owner_id: str,
        organization_id: Optional[str] = None,
    ) -> Interview:
        """Create a new interview"""
        interview = Interview(
            title=obj_in.title,
            interviewee_name=obj_in.interviewee_name,
            date=obj_in.date,
            location=obj_in.location,
            notes=obj_in.notes,
            owner_id=owner_id,
            organization_id=organization_id,
        )
        
        db.add(interview)
        await db.flush()
        return interview
    
    def get_multi_by_owner_query(
        self, db: AsyncSession, owner_id: str, **filters
    ):
        """Get query for interviews by owner"""
        query = select(Interview).filter(Interview.owner_id == owner_id)
        
        # Apply additional filters
        for key, value in filters.items():
            if hasattr(Interview, key) and value is not None:
                query = query.filter(getattr(Interview, key) == value)
        
        return query.order_by(Interview.created_at.desc())
    
    async def get_multi_by_owner(
        self,
        db: AsyncSession,
        *,
        owner_id: str,
        skip: int = 0,
        limit: int = 100,
        **filters
    ) -> List[Interview]:
        """Get interviews by owner"""
        query = self.get_multi_by_owner_query(db, owner_id, **filters)
        query = query.offset(skip).limit(limit)
        
        result = await db.execute(query)
        return result.scalars().all()


interview_crud = CRUDInterview(Interview)