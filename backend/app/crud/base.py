from typing import Any, Dict, Generic, List, Optional, Type, TypeVar, Union

from fastapi.encoders import jsonable_encoder
from pydantic import BaseModel
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.base_class import Base

ModelType = TypeVar("ModelType", bound=Base)
CreateSchemaType = TypeVar("CreateSchemaType", bound=BaseModel)
UpdateSchemaType = TypeVar("UpdateSchemaType", bound=BaseModel)


class CRUDBase(Generic[ModelType, CreateSchemaType, UpdateSchemaType]):
    """
    Base class for CRUD operations
    """

    def __init__(self, model: Type[ModelType]):
        self.model = model

    async def get(self, db: AsyncSession, id: Any) -> Optional[ModelType]:
        """Get a record by ID"""
        result = await db.execute(select(self.model).filter(self.model.id == id))
        return result.scalars().first()

    async def get_multi(
            self, db: AsyncSession, *, skip: int = 0, limit: int = 100
    ) -> List[ModelType]:
        """Get multiple records"""
        result = await db.execute(
            select(self.model).order_by(self.model.created_at.desc()).offset(skip).limit(limit)
        )
        return result.scalars().all()

    async def count(self, db: AsyncSession) -> int:
        """Count total records"""
        result = await db.execute(select(func.count()).select_from(self.model))
        return result.scalar_one()

    async def create(self, db: AsyncSession, *, obj_in: CreateSchemaType, **kwargs) -> ModelType:
        """Create a new record"""
        obj_in_data = obj_in.model_dump() if hasattr(obj_in, "model_dump") else jsonable_encoder(obj_in)
        db_obj = self.model(**obj_in_data, **kwargs)
        db.add(db_obj)
        await db.flush()
        await db.refresh(db_obj)
        return db_obj

    async def update(
            self,
            db: AsyncSession,
            *,
            db_obj: ModelType,
            obj_in: Union[UpdateSchemaType, Dict[str, Any]]
    ) -> ModelType:
        """Update a record"""
        obj_data = jsonable_encoder(db_obj)

        if isinstance(obj_in, dict):
            update_data = obj_in
        else:
            update_data = obj_in.model_dump(exclude_unset=True) if hasattr(obj_in, "model_dump") else obj_in.dict(
                exclude_unset=True)

        for field in obj_data:
            if field in update_data:
                setattr(db_obj, field, update_data[field])

        db.add(db_obj)
        await db.flush()
        await db.refresh(db_obj)
        return db_obj

    async def remove(self, db: AsyncSession, *, id: Any) -> Optional[ModelType]:
        """Remove a record"""
        obj = await self.get(db, id=id)
        if obj:
            await db.delete(obj)
            await db.commit()
        return obj