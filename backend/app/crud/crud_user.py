from typing import Optional, Union

from passlib.context import CryptContext
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.crud.base import CRUDBase
from app.models.models import User, UserRole
from app.schemas.user import UserCreate, UserUpdate


pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


class CRUDUser(CRUDBase[User, UserCreate, UserUpdate]):
    """CRUD operations for user model"""
    
    async def get_by_email(self, db: AsyncSession, *, email: str) -> Optional[User]:
        """Get user by email"""
        result = await db.execute(select(User).where(User.email == email))
        return result.scalars().first()
    
    async def create(
        self, db: AsyncSession, *, obj_in: UserCreate, role: UserRole = UserRole.USER
    ) -> User:
        """Create a new user"""
        hashed_password = self.get_password_hash(obj_in.password)
        db_obj = User(
            email=obj_in.email,
            hashed_password=hashed_password,
            full_name=obj_in.full_name,
            role=role,
        )
        db.add(db_obj)
        await db.commit()
        await db.refresh(db_obj)
        return db_obj
    
    async def update(
        self, db: AsyncSession, *, db_obj: User, obj_in: Union[UserUpdate, dict]
    ) -> User:
        """Update a user"""
        if isinstance(obj_in, dict):
            update_data = obj_in
        else:
            update_data = obj_in.model_dump(exclude_unset=True)
        
        if "password" in update_data:
            hashed_password = self.get_password_hash(update_data["password"])
            del update_data["password"]
            update_data["hashed_password"] = hashed_password
        
        return await super().update(db, db_obj=db_obj, obj_in=update_data)
    
    async def authenticate(
        self, db: AsyncSession, *, email: str, password: str
    ) -> Optional[User]:
        """Authenticate user"""
        user = await self.get_by_email(db, email=email)
        if not user:
            return None
        if not self.verify_password(password, user.hashed_password):
            return None
        return user
    
    def verify_password(self, plain_password: str, hashed_password: str) -> bool:
        """Verify password"""
        return pwd_context.verify(plain_password, hashed_password)
    
    def get_password_hash(self, password: str) -> str:
        """Get password hash"""
        return pwd_context.hash(password)
    
    async def add_credits(
        self, db: AsyncSession, user_id: str, credits: int
    ) -> User:
        """Add interview credits to user"""
        user = await self.get(db, id=user_id)
        if not user:
            raise ValueError(f"User {user_id} not found")
        
        user.available_interview_credits += credits
        await db.commit()
        await db.refresh(user)
        return user
    
    async def add_chat_tokens(
        self, db: AsyncSession, user_id: str, tokens: int
    ) -> User:
        """Add chat tokens to user"""
        user = await self.get(db, id=user_id)
        if not user:
            raise ValueError(f"User {user_id} not found")
        
        user.available_chat_tokens += tokens
        await db.commit()
        await db.refresh(user)
        return user


user_crud = CRUDUser(User)