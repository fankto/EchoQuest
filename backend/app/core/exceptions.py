from fastapi import HTTPException, status


class BaseAPIException(HTTPException):
    """Base API exception with status code and detail"""
    
    def __init__(
        self,
        status_code: int,
        detail: str,
        code: str = "error",
        headers: dict = None,
    ):
        super().__init__(status_code=status_code, detail=detail, headers=headers)
        self.code = code


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
    
    def __init__(self, detail: str = "Rate limit exceeded"):
        super().__init__(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail=detail,
            code="rate_limit_exceeded",
        )


class ValidationError(BaseAPIException):
    """Exception for validation errors"""
    
    def __init__(self, detail: str = "Validation error"):
        super().__init__(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=detail,
            code="validation_error",
        )


class FileUploadError(BaseAPIException):
    """Exception for file upload errors"""
    
    def __init__(self, detail: str = "Error uploading file"):
        super().__init__(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=detail,
            code="file_upload_error",
        )