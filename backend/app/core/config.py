import os
from typing import Any, Dict, List, Optional, Union
from functools import lru_cache

from pydantic import AnyHttpUrl, EmailStr, PostgresDsn, field_validator, SecretStr, validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings"""

    model_config = SettingsConfigDict(env_file=".env", case_sensitive=True, extra="ignore")

    # Environment
    ENVIRONMENT: str = "development"
    DEBUG: bool = False
    TESTING: bool = False

    # API
    API_V1_STR: str = "/api/v1"
    PROJECT_NAME: str = "EchoQuest"
    VERSION: str = "1.0.0"

    # CORS
    CORS_ORIGINS: List[str] = ["http://localhost:3000", "http://localhost:3001", "http://frontend:3000"]

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
    REDIS_ENABLED: bool = True

    # File storage
    UPLOAD_DIR: str = "/app/data/uploads"
    PROCESSED_DIR: str = "/app/data/processed"
    MAX_UPLOAD_SIZE: int = 100 * 1024 * 1024  # 100 MB
    ALLOWED_AUDIO_EXTENSIONS: List[str] = [".mp3", ".wav", ".ogg", ".flac", ".m4a", ".webm"]

    # OpenAI - Optional, used for chat functionality
    OPENAI_API_KEY: Optional[str] = None
    OPENAI_EMBEDDING_MODEL: str = "text-embedding-3-small"
    OPENAI_CHAT_MODEL: str = "gpt-4o-mini"
    OPENAI_MAX_RETRIES: int = 3
    OPENAI_RETRY_DELAY: float = 1.0  # Initial retry delay in seconds

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

    # Transcription settings
    AUDIO_CHUNK_SIZE: int = 20 * 1024 * 1024  # 20 MB in bytes
    AUDIO_CHUNK_DURATION: int = 180  # 3 minutes in seconds

    # Rate limiting
    RATE_LIMIT_ENABLED: bool = True
    RATE_LIMIT_DEFAULT_LIMIT: int = 100  # Number of requests
    RATE_LIMIT_DEFAULT_PERIOD: int = 60  # Period in seconds (1 minute)

    # API docs
    DOCS_URL: Optional[str] = "/docs"
    REDOC_URL: Optional[str] = "/redoc"
    OPENAPI_URL: Optional[str] = "/openapi.json"

    @validator("OPENAPI_URL", "DOCS_URL", "REDOC_URL")
    def disable_docs_in_production(cls, v: Optional[str], values: Dict[str, Any]) -> Optional[str]:
        if values.get("ENVIRONMENT") == "production" and v is not None:
            # Disable API docs in production unless explicitly enabled
            return None
        return v

    # Security
    SECURITY_PASSWORD_HASH: str = "bcrypt"
    SECURITY_PASSWORD_SALT: str = "changeme"  # Should be overridden in .env

    # Frontend URL for links in emails, etc.
    FRONTEND_URL: str = "http://localhost:3000"

    # Health check
    HEALTH_CHECK_ENABLED: bool = True

    def get_database_url_for_alembic(self) -> str:
        """Get database URL for Alembic migrations"""
        return str(self.DATABASE_URL).replace("+asyncpg", "")

    class Config:
        case_sensitive = True


@lru_cache()
def get_settings() -> Settings:
    """Get cached settings instance"""
    return Settings()


settings = get_settings()