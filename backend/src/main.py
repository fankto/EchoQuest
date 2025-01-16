# backend/src/api.py
from fastapi import FastAPI
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

from .database import engine, Base
from .interview_manager.audio_endpoints import router as interview_manager_router
from .questionnaire_manager.api import router as questionnaire_manager_router

import logging

logging.basicConfig(level=logging.INFO)

app = FastAPI()

# CORS middleware setup
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://frontend:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# Add these exception handlers
@app.exception_handler(StarletteHTTPException)
async def http_exception_handler(request, exc):
    return JSONResponse(
        status_code=exc.status_code,
        content={"detail": str(exc.detail)},
    )


@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request, exc):
    return JSONResponse(
        status_code=400,
        content={"detail": str(exc)},
    )


# Include the routers
app.include_router(questionnaire_manager_router, prefix="/api/questionnaires", tags=["questionnaires"])
app.include_router(interview_manager_router, prefix="/api/interviews", tags=["interviews"])

# Create tables
Base.metadata.create_all(bind=engine)

# Add a test route
@app.get("/api/test")
async def test_route():
    return {"message": "API is working"}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
