from app.db.session import get_db
from app.models.models import Interview
from sqlalchemy import select
from sqlalchemy.orm import selectinload
import asyncio

async def get_interview_data():
    async for db in get_db():
        result = await db.execute(select(Interview))
        interviews = result.scalars().all()
        
        for interview in interviews:
            print(f"Interview {interview.id}")
            print(f"  Title: {interview.title}")
            print(f"  Status: {interview.status}")
            print(f"  Questionnaire ID: {interview.questionnaire_id}")
            
            # Try to load relationship
            if interview.questionnaire_id:
                result = await db.execute(
                    select(Interview).where(Interview.id == interview.id).options(
                        selectinload(Interview.questionnaire)
                    )
                )
                interview_with_rel = result.scalars().first()
                print(f"  Has questionnaire object: {interview_with_rel.questionnaire is not None}")
                if interview_with_rel.questionnaire:
                    print(f"  Questionnaire title: {interview_with_rel.questionnaire.title}")

if __name__ == "__main__":
    asyncio.run(get_interview_data()) 