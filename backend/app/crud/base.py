from typing import Any, Dict, Generic, List, Optional, Type, TypeVar, Union
import uuid

from fastapi.encoders import jsonable_encoder
from pydantic import BaseModel
from sqlalchemy import select, func, update, delete
from sqlalchemy.ext.asyncio import AsyncSession
from loguru import logger

from app.db.base_class import Base
from app.core.exceptions import DatabaseError, ResourceNotFoundError

ModelType = TypeVar("ModelType", bound=Base)
CreateSchemaType = TypeVar("CreateSchemaType", bound=BaseModel)
UpdateSchemaType = TypeVar("UpdateSchemaType", bound=BaseModel)


class CRUDBase(Generic[ModelType, CreateSchemaType, UpdateSchemaType]):
    """
    Base class for CRUD operations with improved error handling
    """

    def __init__(self, model: Type[ModelType]):
        """
        Initialize with model class

        Args:
            model: SQLAlchemy model class
        """
        self.model = model

    async def get(self, db: AsyncSession, id: Any) -> Optional[ModelType]:
        """
        Get a record by ID

        Args:
            db: Database session
            id: Record ID

        Returns:
            Model instance if found, None otherwise
        """
        try:
            result = await db.execute(select(self.model).filter(self.model.id == id))
            return result.scalars().first()
        except Exception as e:
            logger.error(f"Error retrieving {self.model.__name__} with ID {id}: {e}")
            raise DatabaseError(f"Error retrieving {self.model.__name__}")

    async def get_or_404(self, db: AsyncSession, id: Any) -> ModelType:
        """
        Get a record by ID or raise 404 error if not found

        Args:
            db: Database session
            id: Record ID

        Returns:
            Model instance

        Raises:
            ResourceNotFoundError: If record doesn't exist
        """
        model = await self.get(db, id=id)
        if model is None:
            raise ResourceNotFoundError(self.model.__name__, str(id))
        return model

    async def get_multi(
            self, db: AsyncSession, *, skip: int = 0, limit: int = 100
    ) -> List[ModelType]:
        """
        Get multiple records

        Args:
            db: Database session
            skip: Number of records to skip
            limit: Maximum number of records to return

        Returns:
            List of model instances
        """
        try:
            result = await db.execute(
                select(self.model)
                .order_by(self.model.created_at.desc())
                .offset(skip)
                .limit(limit)
            )
            return result.scalars().all()
        except Exception as e:
            logger.error(f"Error retrieving multiple {self.model.__name__}: {e}")
            raise DatabaseError(f"Error retrieving {self.model.__name__} records")

    async def get_by_condition(
            self, db: AsyncSession, *, condition, skip: int = 0, limit: int = 100
    ) -> List[ModelType]:
        """
        Get records by condition

        Args:
            db: Database session
            condition: SQLAlchemy filter condition
            skip: Number of records to skip
            limit: Maximum number of records to return

        Returns:
            List of model instances
        """
        try:
            result = await db.execute(
                select(self.model)
                .filter(condition)
                .order_by(self.model.created_at.desc())
                .offset(skip)
                .limit(limit)
            )
            return result.scalars().all()
        except Exception as e:
            logger.error(f"Error retrieving {self.model.__name__} by condition: {e}")
            raise DatabaseError(f"Error retrieving {self.model.__name__} records")

    async def count(self, db: AsyncSession, condition=None) -> int:
        """
        Count total records, optionally with a condition

        Args:
            db: Database session
            condition: Optional SQLAlchemy filter condition

        Returns:
            Count of records
        """
        try:
            query = select(func.count()).select_from(self.model)
            if condition is not None:
                query = query.filter(condition)

            result = await db.execute(query)
            return result.scalar_one()
        except Exception as e:
            logger.error(f"Error counting {self.model.__name__}: {e}")
            raise DatabaseError(f"Error counting {self.model.__name__} records")

    async def create(self, db: AsyncSession, *, obj_in: CreateSchemaType, **kwargs) -> ModelType:
        """
        Create a new record

        Args:
            db: Database session
            obj_in: Input schema for creation
            **kwargs: Additional model fields

        Returns:
            Created model instance
        """
        try:
            obj_in_data = obj_in.model_dump() if hasattr(obj_in, "model_dump") else jsonable_encoder(obj_in)
            db_obj = self.model(**obj_in_data, **kwargs)
            db.add(db_obj)
            await db.flush()
            await db.refresh(db_obj)
            return db_obj
        except Exception as e:
            logger.error(f"Error creating {self.model.__name__}: {e}")
            await db.rollback()
            raise DatabaseError(f"Error creating {self.model.__name__}")

    async def update(
            self,
            db: AsyncSession,
            *,
            db_obj: ModelType,
            obj_in: Union[UpdateSchemaType, Dict[str, Any]]
    ) -> ModelType:
        """
        Update a record

        Args:
            db: Database session
            db_obj: Existing model instance
            obj_in: Update schema or dictionary of fields to update

        Returns:
            Updated model instance
        """
        try:
            obj_data = jsonable_encoder(db_obj)

            if isinstance(obj_in, dict):
                update_data = obj_in
            else:
                update_data = obj_in.model_dump(exclude_unset=True) if hasattr(obj_in, "model_dump") else obj_in.dict(
                    exclude_unset=True)

            # Only update fields that are provided and different from current values
            for field in obj_data:
                if field in update_data and update_data[field] != obj_data[field]:
                    setattr(db_obj, field, update_data[field])

            db.add(db_obj)
            await db.flush()
            await db.refresh(db_obj)
            return db_obj
        except Exception as e:
            logger.error(f"Error updating {self.model.__name__} {db_obj.id}: {e}")
            await db.rollback()
            raise DatabaseError(f"Error updating {self.model.__name__}")

    async def update_by_id(
            self,
            db: AsyncSession,
            *,
            id: Any,
            obj_in: Union[UpdateSchemaType, Dict[str, Any]]
    ) -> Optional[ModelType]:
        """
        Update a record by ID

        Args:
            db: Database session
            id: Record ID
            obj_in: Update schema or dictionary of fields to update

        Returns:
            Updated model instance if found, None otherwise
        """
        try:
            db_obj = await self.get(db, id=id)
            if db_obj is None:
                return None

            return await self.update(db, db_obj=db_obj, obj_in=obj_in)
        except Exception as e:
            logger.error(f"Error updating {self.model.__name__} {id}: {e}")
            await db.rollback()
            raise DatabaseError(f"Error updating {self.model.__name__}")

    async def remove(self, db: AsyncSession, *, id: Any) -> Optional[ModelType]:
        """
        Remove a record by ID

        Args:
            db: Database session
            id: Record ID

        Returns:
            Removed model instance if found, None otherwise
        """
        try:
            obj = await self.get(db, id=id)
            if obj is None:
                return None

            await db.delete(obj)
            await db.flush()
            return obj
        except Exception as e:
            logger.error(f"Error removing {self.model.__name__} {id}: {e}")
            await db.rollback()
            raise DatabaseError(f"Error removing {self.model.__name__}")

    async def remove_by_condition(
            self, db: AsyncSession, *, condition
    ) -> int:
        """
        Remove records by condition

        Args:
            db: Database session
            condition: SQLAlchemy filter condition

        Returns:
            Number of records deleted
        """
        try:
            result = await db.execute(
                delete(self.model).where(condition)
            )
            await db.flush()
            return result.rowcount
        except Exception as e:
            logger.error(f"Error removing {self.model.__name__} by condition: {e}")
            await db.rollback()
            raise DatabaseError(f"Error removing {self.model.__name__} records")