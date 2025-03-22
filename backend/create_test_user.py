from app.db.session import AsyncSessionLocal
from app.crud.crud_user import user_crud
from app.schemas.user import UserCreate
import asyncio

async def create_test_user():
    async with AsyncSessionLocal() as db:
        user = await user_crud.get_by_email(db, email='test@example.com')
        if not user:
            user_in = UserCreate(
                email='test@example.com',
                password='password123',
                full_name='Test User'
            )
            await user_crud.create(db, obj_in=user_in)
            print('Test user created successfully!')
        else:
            print('Test user already exists!')

if __name__ == "__main__":
    asyncio.run(create_test_user()) 