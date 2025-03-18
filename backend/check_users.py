import asyncio
from app.db.session import AsyncSessionLocal
from sqlalchemy import text


async def check_users():
    async with AsyncSessionLocal() as db:
        result = await db.execute(text('SELECT * FROM users'))
        users = result.fetchall()
        for user in users:
            print(f'User: {user}')


if __name__ == "__main__":
    asyncio.run(check_users()) 