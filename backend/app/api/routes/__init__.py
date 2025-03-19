from fastapi import APIRouter

from app.api.routes import (
    auth, interviews, questionnaires, users, chat, credits, organizations
)

# Create main API router
api_router = APIRouter()

# Include all route modules
api_router.include_router(auth.router, prefix="/auth", tags=["auth"])
api_router.include_router(users.router, prefix="/users", tags=["users"])
api_router.include_router(organizations.router, prefix="/organizations", tags=["organizations"])
api_router.include_router(questionnaires.router, prefix="/questionnaires", tags=["questionnaires"])
api_router.include_router(interviews.router, prefix="/interviews", tags=["interviews"])
api_router.include_router(chat.router, prefix="/chat", tags=["chat"])
api_router.include_router(credits.router, prefix="/credits", tags=["credits"])