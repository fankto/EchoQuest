import os
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi_pagination import add_pagination
from loguru import logger

from app.api.routes import api_router
from app.core.config import settings
from app.core.exceptions import BaseAPIException
from app.db.init_db import init_db
from app.db.session import engine
from app.services.qdrant_service import QdrantService


@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Lifespan context manager for FastAPI application.
    Handles startup and shutdown events.
    """
    # Create upload directories if they don't exist
    os.makedirs(settings.UPLOAD_DIR, exist_ok=True)
    os.makedirs(settings.PROCESSED_DIR, exist_ok=True)
    
    # Initialize database
    await init_db()
    
    # Initialize Qdrant collections
    qdrant_service = QdrantService()
    await qdrant_service.init_collections()
    
    logger.info("Application startup complete")
    yield
    logger.info("Application shutdown")


app = FastAPI(
    title="EchoQuest API",
    description="API for interview transcription and analysis",
    version="1.0.0",
    lifespan=lifespan,
)

# Configure CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
    expose_headers=["Content-Type", "Content-Length", "Authorization"],
    max_age=600,
)

# Add pagination to the API
add_pagination(app)

# Mount static directories for media files
app.mount("/api/media/uploads", StaticFiles(directory=settings.UPLOAD_DIR), name="uploads")
app.mount("/api/media/processed", StaticFiles(directory=settings.PROCESSED_DIR), name="processed")

# Include API routes
app.include_router(api_router, prefix="/api")


# Exception handlers
@app.exception_handler(BaseAPIException)
async def api_exception_handler(request: Request, exc: BaseAPIException):
    """Handle custom API exceptions"""
    return JSONResponse(
        status_code=exc.status_code,
        content={"detail": exc.detail, "code": exc.code},
    )


@app.get("/health")
async def health_check():
    """Health check endpoint"""
    return {"status": "healthy"}


if __name__ == "__main__":
    import uvicorn
    
    uvicorn.run("app.main:app", host="0.0.0.0", port=8000, reload=True)