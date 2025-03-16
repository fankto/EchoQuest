from loguru import logger
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.crud.crud_user import user_crud
from app.db.session import AsyncSessionLocal
from app.models.models import User, UserRole
from app.schemas.user import UserCreate


async def init_db() -> None:
    """
    Initialize database with default data.
    """
    try:
        async with AsyncSessionLocal() as db:
            await create_default_admin(db)
    except Exception as e:
        logger.error(f"Error initializing database: {e}")
        raise


async def create_default_admin(db: AsyncSession) -> None:
    """
    Create default admin user if it doesn't exist.
    """
    if settings.ENVIRONMENT != "production":
        # Check if admin user exists
        admin_email = "admin@example.com"
        admin = await user_crud.get_by_email(db, email=admin_email)
        
        if not admin:
            logger.info("Creating default admin user")
            admin_data = UserCreate(
                email=admin_email,
                password="password123",  # Insecure, but this is just for development
                full_name="Admin User",
            )
            admin = await user_crud.create(db, obj_in=admin_data, role=UserRole.ADMIN)
            admin.available_interview_credits = 10
            admin.available_chat_tokens = 100000
            await db.commit()
            logger.info(f"Default admin created: {admin_email}")
        else:
            logger.info("Default admin already exists")