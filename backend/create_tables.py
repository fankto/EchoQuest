import asyncio
import sys

from sqlalchemy.ext.asyncio import create_async_engine

from app.core.config import settings
from app.db.base_class import Base
from app.models.models import (
    User, Organization, OrganizationMember, Questionnaire,
    Interview, ChatMessage, Transaction
)


async def create_tables():
    """Create database tables."""
    print("Creating database tables...")
    
    # Create async engine
    engine = create_async_engine(
        str(settings.DATABASE_URL).replace("postgresql://", "postgresql+asyncpg://"),
        echo=True,
    )
    
    # Create tables
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    
    print("Database tables created successfully!")


if __name__ == "__main__":
    asyncio.run(create_tables()) 