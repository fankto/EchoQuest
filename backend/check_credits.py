from app.db.session import AsyncSessionLocal
from app.crud.crud_user import user_crud
import asyncio

async def get_admin_credits():
    async with AsyncSessionLocal() as db:
        user = await user_crud.get_by_email(db, email="admin@example.com")
        print(f"Admin user credits: {user.available_interview_credits}")

if __name__ == "__main__":
    asyncio.run(get_admin_credits())
