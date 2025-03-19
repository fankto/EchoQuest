import os
from datetime import datetime, timedelta
from typing import Optional, Dict, Any, Union
import uuid
import hashlib

from jose import jwt
from passlib.context import CryptContext

from app.core.config import settings

# Password hashing context
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


def get_password_hash(password: str) -> str:
    """
    Hash a password
    """
    return pwd_context.hash(password)


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """
    Verify a password against a hash
    """
    return pwd_context.verify(plain_password, hashed_password)


def create_password_reset_token(user_id: Union[str, uuid.UUID]) -> str:
    """
    Create a password reset token
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

    Returns:
        User ID if valid, None otherwise
    """
    try:
        payload = jwt.decode(token, settings.JWT_SECRET, algorithms=[settings.JWT_ALGORITHM])
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
    except Exception:
        return None


def create_invitation_token(data: Dict[str, Any]) -> str:
    """
    Create an organization invitation token

    Args:
        data: Dictionary with invitation data (organization_id, email, role, inviter_id)
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

    Returns:
        Invitation data if valid, None otherwise
    """
    try:
        payload = jwt.decode(token, settings.JWT_SECRET, algorithms=[settings.JWT_ALGORITHM])
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
    except Exception:
        return None


def generate_file_hash(file_content: bytes) -> str:
    """
    Generate a SHA-256 hash of file content
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
    # Get file extension
    _, ext = os.path.splitext(original_filename)

    # Generate UUID-based name
    unique_id = uuid.uuid4()

    # Create a secure filename
    secure_name = f"{unique_id}{ext.lower()}"

    return secure_name