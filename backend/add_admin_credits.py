from app.db.session import AsyncSessionLocal
from app.crud.crud_user import user_crud
import asyncio

async def add_admin_credits():
    async with AsyncSessionLocal() as db:
        # Get the admin user
        user = await user_crud.get_by_email(db, email="admin@example.com")
        
        if not user:
            print("Admin user not found!")
            return
            
        # Add 100 more credits
        old_credits = user.available_interview_credits
        user.available_interview_credits += 100
        await db.commit()
        
        print(f"Admin user credits updated from {old_credits} to {user.available_interview_credits}")

if __name__ == "__main__":
    asyncio.run(add_admin_credits()) 