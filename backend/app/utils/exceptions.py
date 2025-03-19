from app.core.exceptions import BaseAPIException


class AudioProcessingError(Exception):
    """Error processing audio files"""
    pass


class TranscriptionError(Exception):
    """Error transcribing audio"""
    pass


class ExternalAPIError(Exception):
    """Error communicating with external API"""
    pass


class RateLimitError(BaseAPIException):
    """Rate limit exceeded"""

    def __init__(self, detail: str = "Rate limit exceeded", retry_after: int = 60):
        super().__init__(
            status_code=429,
            detail=detail,
            code="rate_limit_exceeded",
            headers={"Retry-After": str(retry_after)},
        )