from fastapi import HTTPException, status
from typing import Optional, Dict, Any


class BaseAPIException(HTTPException):
    """Base API exception with status code and detail"""

    def __init__(
            self,
            status_code: int,
            detail: str,
            code: str = "error",
            headers: Optional[Dict[str, Any]] = None,
    ):
        super().__init__(status_code=status_code, detail=detail, headers=headers)
        self.code = code


class AuthenticationError(BaseAPIException):
    """Exception for authentication errors"""

    def __init__(self, detail: str = "Authentication failed"):
        super().__init__(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=detail,
            code="authentication_error",
            headers={"WWW-Authenticate": "Bearer"},
        )


class AuthorizationError(BaseAPIException):
    """Exception for authorization errors"""

    def __init__(self, detail: str = "Not authorized to perform this action"):
        super().__init__(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=detail,
            code="authorization_error",
        )


class ResourceNotFoundError(BaseAPIException):
    """Exception for resource not found"""

    def __init__(self, resource_type: str, resource_id: Optional[str] = None):
        detail = f"{resource_type} not found"
        if resource_id:
            detail = f"{resource_type} with ID {resource_id} not found"

        super().__init__(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=detail,
            code="resource_not_found",
        )


class ValidationError(BaseAPIException):
    """Exception for validation errors"""

    def __init__(self, detail: str = "Validation error"):
        super().__init__(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=detail,
            code="validation_error",
        )


class BusinessLogicError(BaseAPIException):
    """Exception for business logic errors"""

    def __init__(self, detail: str):
        super().__init__(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=detail,
            code="business_logic_error",
        )


class ExternalServiceError(BaseAPIException):
    """Exception for external service errors"""

    def __init__(self, service_name: str, detail: str):
        super().__init__(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=f"Error from {service_name} service: {detail}",
            code="external_service_error",
        )


class DatabaseError(BaseAPIException):
    """Exception for database errors"""

    def __init__(self, detail: str = "Database operation failed"):
        super().__init__(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=detail,
            code="database_error",
        )


class CredentialsException(BaseAPIException):
    """Exception for invalid credentials"""

    def __init__(self, detail: str = "Could not validate credentials"):
        super().__init__(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=detail,
            code="invalid_credentials",
            headers={"WWW-Authenticate": "Bearer"},
        )


class PermissionDeniedException(BaseAPIException):
    """Exception for permission denied"""

    def __init__(self, detail: str = "Permission denied"):
        super().__init__(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=detail,
            code="permission_denied",
        )


class NotFoundException(BaseAPIException):
    """Exception for resource not found"""

    def __init__(self, detail: str = "Resource not found"):
        super().__init__(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=detail,
            code="not_found",
        )


class InsufficientCreditsError(BaseAPIException):
    """Exception for insufficient credits"""

    def __init__(self, detail: str = "Insufficient credits"):
        super().__init__(
            status_code=status.HTTP_402_PAYMENT_REQUIRED,
            detail=detail,
            code="insufficient_credits",
        )


class RateLimitExceeded(BaseAPIException):
    """Exception for rate limit exceeded"""

    def __init__(self, detail: str = "Rate limit exceeded", retry_after: int = 60):
        super().__init__(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail=detail,
            code="rate_limit_exceeded",
            headers={"Retry-After": str(retry_after)},
        )


class FileUploadError(BaseAPIException):
    """Exception for file upload errors"""

    def __init__(self, detail: str = "Error uploading file"):
        super().__init__(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=detail,
            code="file_upload_error",
        )


class AudioProcessingError(BaseAPIException):
    """Error processing audio files"""

    def __init__(self, detail: str = "Error processing audio file"):
        super().__init__(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=detail,
            code="audio_processing_error"
        )


class TranscriptionError(BaseAPIException):
    """Error transcribing audio"""

    def __init__(self, detail: str = "Error transcribing audio"):
        super().__init__(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=detail,
            code="transcription_error"
        )