import os
import secrets
import string
from datetime import datetime, timedelta
from typing import Optional, Dict, Any, Union
import uuid
import hashlib
import re
import base64

from jose import jwt
from passlib.context import CryptContext
from loguru import logger

from app.core.config import settings

# Password hashing context
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


def get_password_hash(password: str) -> str:
    """
    Hash a password

    Args:
        password: Plain text password

    Returns:
        Hashed password
    """
    return pwd_context.hash(password)


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """
    Verify a password against a hash

    Args:
        plain_password: Plain text password
        hashed_password: Hashed password

    Returns:
        True if password matches hash, False otherwise
    """
    return pwd_context.verify(plain_password, hashed_password)


def password_meets_requirements(password: str) -> tuple[bool, str]:
    """
    Check if a password meets security requirements

    Args:
        password: Password to check

    Returns:
        Tuple of (meets_requirements, error_message)
    """
    if len(password) < 8:
        return False, "Password must be at least 8 characters long"

    if not re.search(r'[A-Z]', password):
        return False, "Password must contain at least one uppercase letter"

    if not re.search(r'[a-z]', password):
        return False, "Password must contain at least one lowercase letter"

    if not re.search(r'[0-9]', password):
        return False, "Password must contain at least one number"

    if not re.search(r'[^A-Za-z0-9]', password):
        return False, "Password must contain at least one special character"

    return True, ""


def create_token(
        subject: Union[str, uuid.UUID, Dict],
        expires_delta: Optional[timedelta] = None,
        token_type: str = "access",
        additional_claims: Optional[Dict[str, Any]] = None
) -> str:
    """
    Create a JWT token

    Args:
        subject: Subject identifier (user ID)
        expires_delta: Optional expiration time override
        token_type: Token type (access or refresh)
        additional_claims: Optional additional claims to include

    Returns:
        JWT token string
    """
    if expires_delta:
        expire = datetime.utcnow() + expires_delta
    elif token_type == "refresh":
        expire = datetime.utcnow() + timedelta(days=settings.REFRESH_TOKEN_EXPIRE_DAYS)
    else:
        expire = datetime.utcnow() + timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)

    to_encode = {"exp": expire, "sub": str(subject), "type": token_type}

    # Add additional claims if provided
    if additional_claims:
        to_encode.update(additional_claims)

    encoded_jwt = jwt.encode(
        to_encode,
        settings.JWT_SECRET,
        algorithm=settings.JWT_ALGORITHM
    )
    return encoded_jwt


def create_password_reset_token(user_id: Union[str, uuid.UUID]) -> str:
    """
    Create a password reset token

    Args:
        user_id: User ID

    Returns:
        Password reset token
    """
    expire = datetime.utcnow() + timedelta(hours=24)
    payload = {
        "exp": expire.timestamp(),
        "sub": str(user_id),
        "type": "password_reset"
    }
    return jwt.encode(payload, settings.JWT_SECRET, algorithm=settings.JWT_ALGORITHM)


def verify_password_reset_token(token: str) -> Optional[str]:
    """
    Verify a password reset token

    Args:
        token: Password reset token

    Returns:
        User ID if valid, None otherwise
    """
    try:
        payload = jwt.decode(
            token,
            settings.JWT_SECRET,
            algorithms=[settings.JWT_ALGORITHM]
        )
        if payload.get("type") != "password_reset":
            return None
        user_id = payload.get("sub")
        if not user_id:
            return None

        # Check expiration
        exp = payload.get("exp")
        if not exp or datetime.utcnow().timestamp() > exp:
            return None

        return user_id
    except Exception as e:
        logger.error(f"Error decoding password reset token: {e}")
        return None


def create_invitation_token(data: Dict[str, Any]) -> str:
    """
    Create an organization invitation token

    Args:
        data: Dictionary with invitation data (organization_id, email, role, inviter_id)

    Returns:
        Invitation token
    """
    expire = datetime.utcnow() + timedelta(days=7)  # 7 days expiration
    payload = {
        "exp": expire.timestamp(),
        "type": "org_invitation",
        **data
    }
    return jwt.encode(payload, settings.JWT_SECRET, algorithm=settings.JWT_ALGORITHM)


def verify_invitation_token(token: str) -> Optional[Dict[str, Any]]:
    """
    Verify an organization invitation token

    Args:
        token: Invitation token

    Returns:
        Invitation data if valid, None otherwise
    """
    try:
        payload = jwt.decode(
            token,
            settings.JWT_SECRET,
            algorithms=[settings.JWT_ALGORITHM]
        )
        if payload.get("type") != "org_invitation":
            return None

        # Check required fields
        required_fields = ["organization_id", "email", "role", "inviter_id"]
        for field in required_fields:
            if field not in payload:
                return None

        # Check expiration
        exp = payload.get("exp")
        if not exp or datetime.utcnow().timestamp() > exp:
            return None

        return payload
    except Exception as e:
        logger.error(f"Error decoding invitation token: {e}")
        return None


def generate_file_hash(file_content: bytes) -> str:
    """
    Generate a SHA-256 hash of file content

    Args:
        file_content: File content bytes

    Returns:
        SHA-256 hash as hexadecimal string
    """
    return hashlib.sha256(file_content).hexdigest()


def generate_secure_filename(original_filename: str) -> str:
    """
    Generate a secure filename based on original name and UUID

    Args:
        original_filename: Original filename

    Returns:
        Secure filename
    """
    # Extract file extension
    _, ext = os.path.splitext(original_filename)

    # Generate UUID for filename
    unique_id = uuid.uuid4()

    # Create secure filename
    return f"{unique_id}{ext.lower()}"


def generate_random_password(length: int = 16) -> str:
    """
    Generate a secure random password

    Args:
        length: Password length

    Returns:
        Random password string
    """
    # Define character sets
    uppercase = string.ascii_uppercase
    lowercase = string.ascii_lowercase
    digits = string.digits
    special = "!@#$%^&*()-_=+[]{}|;:,.<>?"

    # Ensure at least one of each character type
    password = [
        secrets.choice(uppercase),
        secrets.choice(lowercase),
        secrets.choice(digits),
        secrets.choice(special)
    ]

    # Fill the rest with random characters from all sets
    all_chars = uppercase + lowercase + digits + special
    password += [secrets.choice(all_chars) for _ in range(length - 4)]

    # Shuffle the password
    secrets.SystemRandom().shuffle(password)

    return ''.join(password)


def sanitize_html(html: str) -> str:
    """
    Sanitize HTML input to prevent XSS attacks

    Args:
        html: HTML string to sanitize

    Returns:
        Sanitized HTML string
    """
    # This is a simple implementation for example purposes
    # In production, use a proper HTML sanitizer like bleach

    # Remove script tags and their content
    html = re.sub(r'<script.*?</script>', '', html, flags=re.DOTALL)

    # Remove event handlers
    html = re.sub(r' on\w+=".*?"', '', html)
    html = re.sub(r" on\w+='.*?'", '', html)
    html = re.sub(r' on\w+=.*?>', '>', html)

    # Remove javascript: URLs
    html = re.sub(r'javascript:', 'forbidden:', html, flags=re.IGNORECASE)

    return html


def generate_csrf_token() -> str:
    """
    Generate a CSRF token

    Returns:
        CSRF token string
    """
    return secrets.token_hex(32)


def hash_csrf_token(token: str, salt: Optional[str] = None) -> tuple[str, str]:
    """
    Hash a CSRF token with a salt

    Args:
        token: CSRF token
        salt: Optional salt (generated if not provided)

    Returns:
        Tuple of (hashed_token, salt)
    """
    if not salt:
        salt = secrets.token_hex(8)

    hasher = hashlib.sha256()
    hasher.update(f"{salt}:{token}".encode())

    return hasher.hexdigest(), salt


def verify_csrf_token(token: str, hashed_token: str, salt: str) -> bool:
    """
    Verify a CSRF token against a hash

    Args:
        token: CSRF token to verify
        hashed_token: Hashed token to verify against
        salt: Salt used for hashing

    Returns:
        True if token is valid, False otherwise
    """
    calculated_hash, _ = hash_csrf_token(token, salt)
    return secrets.compare_digest(calculated_hash, hashed_token)