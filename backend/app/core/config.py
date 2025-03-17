import os
from typing import Any, Dict, List, Optional, Union

from pydantic import AnyHttpUrl, EmailStr, PostgresDsn, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings"""
    
    model_config = SettingsConfigDict(env_file=".env", case_sensitive=True, extra="ignore")
    
    # Base settings
    ENVIRONMENT: str = "development"
    API_V1_STR: str = "/api/v1"
    
    # CORS
    CORS_ORIGINS: List[AnyHttpUrl] = ["http://localhost:3000", "http://localhost:3001", "http://frontend:3000"]
    
    # Authentication
    JWT_SECRET: str
    JWT_ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 30
    REFRESH_TOKEN_EXPIRE_DAYS: int = 7
    
    # Database
    DATABASE_URL: PostgresDsn
    
    @field_validator("DATABASE_URL")
    def assemble_db_connection(cls, v: Optional[str], info: Dict[str, Any]) -> Any:
        if isinstance(v, str):
            return v
        
        return PostgresDsn.build(
            scheme="postgresql",
            username=os.getenv("POSTGRES_USER", "echoquest"),
            password=os.getenv("POSTGRES_PASSWORD", "echoquest"),
            host=os.getenv("POSTGRES_HOST", "postgres"),
            port=5432,
            path=os.getenv('POSTGRES_DB', 'echoquest'),
        )
    
    # Redis
    REDIS_URL: str = "redis://redis:6379/0"
    
    # File storage
    UPLOAD_DIR: str = "/app/data/uploads"
    PROCESSED_DIR: str = "/app/data/processed"
    MAX_UPLOAD_SIZE: int = 100 * 1024 * 1024  # 100 MB
    
    # OpenAI
    OPENAI_API_KEY: str
    OPENAI_EMBEDDING_MODEL: str = "text-embedding-3-small"
    OPENAI_CHAT_MODEL: str = "gpt-4-turbo-preview"
    
    # Optional AssemblyAI for transcription
    ASSEMBLYAI_API_KEY: Optional[str] = None
    
    # Qdrant
    QDRANT_URL: str = "http://qdrant:6333"
    QDRANT_COLLECTION_NAME: str = "transcripts"
    
    # Credit system
    DEFAULT_CHAT_TOKENS_PER_INTERVIEW: int = 50000
    CHAT_TOKEN_PACKAGES: Dict[str, Dict[str, Union[int, float]]] = {
        "small": {"tokens": 100000, "price": 5.0},
        "medium": {"tokens": 500000, "price": 20.0},
        "large": {"tokens": 1000000, "price": 35.0},
    }
    
    # Email
    SMTP_TLS: bool = True
    SMTP_PORT: Optional[int] = 587
    SMTP_HOST: Optional[str] = None
    SMTP_USER: Optional[str] = None
    SMTP_PASSWORD: Optional[str] = None
    EMAILS_FROM_EMAIL: Optional[EmailStr] = None
    EMAILS_FROM_NAME: Optional[str] = None
    
    # Auth0 Configuration
    AUTH0_DOMAIN: str = "your-auth0-domain.auth0.com"
    AUTH0_CLIENT_ID: str = "your-auth0-client-id"
    AUTH0_CLIENT_SECRET: str = "your-auth0-client-secret"
    AUTH0_AUDIENCE: str = "https://api.echoquest.com"
    AUTH0_CALLBACK_URL: str = "http://localhost:3001/auth/callback"


settings = Settings()