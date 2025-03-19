import os
import uuid
from typing import List, Set, Tuple
import mimetypes
import hashlib

import aiofiles
from fastapi import UploadFile, HTTPException, status
from loguru import logger

from app.core.config import settings


class FileService:
    """Service for handling file operations"""

    ALLOWED_AUDIO_TYPES: Set[str] = {
        'audio/mpeg',
        'audio/mp3',
        'audio/wav',
        'audio/x-wav',
        'audio/ogg',
        'audio/flac',
        'audio/mp4',
        'audio/x-m4a',
        'audio/webm',
    }

    async def save_file(
            self,
            file: UploadFile,
            directory: str,
            allowed_types: Set[str] = None,
            max_size: int = None
    ) -> str:
        """
        Save an uploaded file to the specified directory

        Args:
            file: Uploaded file
            directory: Directory to save the file to
            allowed_types: Set of allowed MIME types (optional)
            max_size: Maximum file size in bytes (optional)

        Returns:
            Filename of the saved file
        """
        try:
            # Create directory if it doesn't exist
            os.makedirs(directory, exist_ok=True)

            # Validate file content type if allowed_types is provided
            content_type = file.content_type or ""
            if allowed_types and content_type not in allowed_types:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Unsupported file type: {content_type}. Allowed types: {', '.join(allowed_types)}"
                )

            # Generate unique filename while preserving extension
            original_filename = file.filename
            extension = os.path.splitext(original_filename)[1] if original_filename else ""
            if not extension and content_type:
                # Try to get extension from content type
                ext = mimetypes.guess_extension(content_type)
                if ext:
                    extension = ext

            unique_filename = f"{uuid.uuid4()}{extension}"
            file_path = os.path.join(directory, unique_filename)

            # Save file
            file_size = 0
            async with aiofiles.open(file_path, "wb") as buffer:
                # Read file in chunks to avoid memory issues with large files
                chunk_size = 1024 * 1024  # 1MB
                while chunk := await file.read(chunk_size):
                    file_size += len(chunk)
                    if max_size and file_size > max_size:
                        # Close and delete the partial file
                        await buffer.close()
                        os.remove(file_path)
                        raise HTTPException(
                            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
                            detail=f"File size exceeds the limit of {max_size / 1024 / 1024:.1f}MB"
                        )
                    await buffer.write(chunk)

            # Generate and store file hash for integrity verification
            file_hash = await self._get_file_hash(file_path)

            logger.info(f"File saved: {file_path} (size: {file_size / 1024 / 1024:.2f}MB, hash: {file_hash})")

            return unique_filename
        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"Error saving file: {e}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Error saving file: {str(e)}"
            )

    async def delete_file(self, filename: str, directory: str) -> bool:
        """
        Delete a file from the specified directory

        Args:
            filename: Filename to delete
            directory: Directory where the file is located

        Returns:
            True if the file was deleted, False otherwise
        """
        try:
            file_path = os.path.join(directory, filename)

            # Check if file exists
            if not os.path.exists(file_path):
                logger.warning(f"File not found: {file_path}")
                return False

            # Delete file
            os.remove(file_path)
            logger.info(f"File deleted: {file_path}")

            return True
        except Exception as e:
            logger.error(f"Error deleting file: {e}")
            return False

    async def list_files(self, directory: str) -> List[Tuple[str, int]]:
        """
        List all files in the specified directory with their sizes

        Args:
            directory: Directory to list files from

        Returns:
            List of tuples containing (filename, size in bytes)
        """
        try:
            # Create directory if it doesn't exist
            os.makedirs(directory, exist_ok=True)

            # List files
            files = []
            for filename in os.listdir(directory):
                file_path = os.path.join(directory, filename)
                if os.path.isfile(file_path):
                    file_size = os.path.getsize(file_path)
                    files.append((filename, file_size))

            return files
        except Exception as e:
            logger.error(f"Error listing files: {e}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Error listing files: {str(e)}"
            )

    async def _get_file_hash(self, file_path: str) -> str:
        """
        Get SHA-256 hash of a file

        Args:
            file_path: Path to the file

        Returns:
            SHA-256 hash as a hexadecimal string
        """
        try:
            hash_sha256 = hashlib.sha256()
            async with aiofiles.open(file_path, "rb") as f:
                chunk_size = 4096  # 4KB
                while chunk := await f.read(chunk_size):
                    hash_sha256.update(chunk)
            return hash_sha256.hexdigest()
        except Exception as e:
            logger.error(f"Error calculating file hash: {e}")
            return ""


# Create singleton instance
file_service = FileService()