import os
from contextlib import asynccontextmanager
import time
from pathlib import Path

from fastapi import FastAPI, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi_pagination import add_pagination
from loguru import logger
from starlette.middleware.base import BaseHTTPMiddleware

from app.api.routes import api_router
from app.core.config import settings
from app.core.exceptions import BaseAPIException, RateLimitExceeded
from app.db.init_db import init_db
from app.db.session import engine
from app.services.qdrant_service import QdrantService
from app.utils.redis import get_redis_client, close_redis_connection


class RequestLoggingMiddleware(BaseHTTPMiddleware):
    """Middleware for logging all requests"""

    async def dispatch(self, request: Request, call_next):
        start_time = time.time()

        # Generate a unique request ID
        request_id = str(time.time())

        # Add request ID to request state
        request.state.request_id = request_id

        # Log the request
        logger.info(f"Request {request_id}: {request.method} {request.url.path}")

        try:
            # Process the request
            response = await call_next(request)

            # Log the response
            process_time = time.time() - start_time
            status_code = response.status_code
            logger.info(f"Response {request_id}: {status_code} completed in {process_time:.3f}s")

            # Add custom headers
            response.headers["X-Process-Time"] = f"{process_time:.3f}"
            response.headers["X-Request-ID"] = request_id

            return response
        except Exception as e:
            # Log the error
            process_time = time.time() - start_time
            logger.error(f"Error {request_id}: {str(e)} after {process_time:.3f}s")

            # Re-raise the exception
            raise


@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Lifespan context manager for FastAPI application.
    Handles startup and shutdown events.
    """
    # Create upload directories if they don't exist
    Path(settings.UPLOAD_DIR).mkdir(parents=True, exist_ok=True)
    Path(settings.PROCESSED_DIR).mkdir(parents=True, exist_ok=True)

    # Initialize database
    await init_db()

    # Initialize Redis
    redis_client = await get_redis_client()

    # Initialize Qdrant collections
    qdrant_service = QdrantService()
    await qdrant_service.init_collections()

    logger.info(f"Application startup complete in {settings.ENVIRONMENT} environment")
    yield

    # Close Redis connection
    await close_redis_connection()

    logger.info("Application shutdown")


app = FastAPI(
    title=settings.PROJECT_NAME,
    description="API for interview transcription and analysis",
    version=settings.VERSION,
    lifespan=lifespan,
    docs_url=settings.DOCS_URL,
    redoc_url=settings.REDOC_URL,
    openapi_url=settings.OPENAPI_URL,
)

# Configure CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
    expose_headers=["Content-Type", "Content-Length", "Authorization", "X-Process-Time", "X-Request-ID"],
    max_age=600,
)

# Add request logging middleware
app.add_middleware(RequestLoggingMiddleware)

# Add pagination to the API
add_pagination(app)

# Mount static directories for media files
app.mount("/api/media/uploads", StaticFiles(directory=settings.UPLOAD_DIR, html=True), name="uploads")
app.mount("/api/media/processed", StaticFiles(directory=settings.PROCESSED_DIR, html=True), name="processed")

# Include API routes
app.include_router(api_router, prefix=settings.API_V1_STR)


# Exception handlers
@app.exception_handler(BaseAPIException)
async def api_exception_handler(request: Request, exc: BaseAPIException):
    """Handle custom API exceptions"""
    return JSONResponse(
        status_code=exc.status_code,
        content={"detail": exc.detail, "code": exc.code},
        headers=exc.headers or {},
    )


@app.exception_handler(RateLimitExceeded)
async def rate_limit_exception_handler(request: Request, exc: RateLimitExceeded):
    """Handle rate limit exceptions"""
    return JSONResponse(
        status_code=exc.status_code,
        content={"detail": exc.detail, "code": exc.code},
        headers=exc.headers or {},
    )


@app.get("/health")
async def health_check():
    """Health check endpoint"""
    return {
        "status": "healthy",
        "version": settings.VERSION,
        "environment": settings.ENVIRONMENT,
        "timestamp": time.time()
    }


if __name__ == "__main__":
    import uvicorn

    uvicorn.run("app.main:app", host="0.0.0.0", port=8000, reload=settings.DEBUG)