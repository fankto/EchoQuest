import asyncio
from sqlalchemy import text
from app.db.session import AsyncSessionLocal


async def update_test_user_credits():
    """Update the test user's credits"""
    async with AsyncSessionLocal() as db:
        # First get the test user
        result = await db.execute(
            text("SELECT * FROM users WHERE email = :email"),
            {"email": "test@example.com"}
        )
        user = result.fetchone()
        
        if not user:
            print("Test user not found")
            return
        
        # Update the user's credits
        current_credits = user.available_interview_credits
        new_credits = 20
        
        await db.execute(
            text("UPDATE users SET available_interview_credits = :credits WHERE email = :email"),
            {"credits": new_credits, "email": "test@example.com"}
        )
        await db.commit()
        
        print(f"Test user credits updated from {current_credits} to {new_credits}")


if __name__ == "__main__":
    asyncio.run(update_test_user_credits()) 