import os
from pathlib import Path
import tempfile
from typing import List, Set, Tuple, Optional
import mimetypes
import hashlib
import uuid
import shutil

import aiofiles
from fastapi import UploadFile, HTTPException, status
from loguru import logger

from app.core.config import settings
from app.core.exceptions import FileUploadError, ResourceNotFoundError


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

    def __init__(self):
        # Ensure upload and processed directories exist
        os.makedirs(settings.UPLOAD_DIR, exist_ok=True)
        os.makedirs(settings.PROCESSED_DIR, exist_ok=True)

    async def save_file(
            self,
            file: UploadFile,
            directory: str,
            allowed_types: Optional[Set[str]] = None,
            max_size: Optional[int] = None
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

        Raises:
            FileUploadError: If there's an error uploading or validating the file
        """
        try:
            # Create directory if it doesn't exist
            Path(directory).mkdir(parents=True, exist_ok=True)

            # Validate file content type if allowed_types is provided
            content_type = file.content_type or ""
            if allowed_types and content_type not in allowed_types:
                raise FileUploadError(
                    f"Unsupported file type: {content_type}. Allowed types: {', '.join(allowed_types)}"
                )

            # Generate unique filename while preserving extension
            original_filename = file.filename or ""
            suffix = Path(original_filename).suffix
            if not suffix and content_type:
                # Try to get extension from content type
                ext = mimetypes.guess_extension(content_type)
                if ext:
                    suffix = ext

            unique_filename = f"{uuid.uuid4()}{suffix}"
            file_path = Path(directory) / unique_filename

            # Create a temporary file first to avoid partial writes
            with tempfile.NamedTemporaryFile(delete=False) as temp_file:
                temp_path = temp_file.name
                file_size = 0

                # Reset file position
                await file.seek(0)

                # Read file in chunks to avoid memory issues with large files
                chunk_size = 1024 * 1024  # 1MB
                while chunk := await file.read(chunk_size):
                    file_size += len(chunk)
                    if max_size and file_size > max_size:
                        # Close and delete the temp file
                        os.unlink(temp_path)
                        raise FileUploadError(
                            f"File size exceeds the limit of {max_size / 1024 / 1024:.1f}MB"
                        )
                    temp_file.write(chunk)

            # Move the temporary file to the final location
            shutil.move(temp_path, file_path)

            # Generate and store file hash for integrity verification
            file_hash = await self._get_file_hash(file_path)

            logger.info(f"File saved: {file_path} (size: {file_size / 1024 / 1024:.2f}MB, hash: {file_hash})")

            return unique_filename

        except FileUploadError:
            raise
        except Exception as e:
            logger.error(f"Error saving file: {e}")
            raise FileUploadError(f"Error saving file: {str(e)}")

    async def delete_file(self, filename: str, directory: str) -> bool:
        """
        Delete a file from the specified directory

        Args:
            filename: Filename to delete
            directory: Directory where the file is located

        Returns:
            True if the file was deleted, False if it didn't exist
        """
        try:
            file_path = Path(directory) / filename

            # Check if file exists
            if not file_path.exists():
                logger.warning(f"File not found: {file_path}")
                return False

            # Delete file
            file_path.unlink()
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

        Raises:
            FileUploadError: If there's an error listing files
        """
        try:
            dir_path = Path(directory)
            # Create directory if it doesn't exist
            dir_path.mkdir(parents=True, exist_ok=True)

            # List files
            files = []
            for file_path in dir_path.iterdir():
                if file_path.is_file():
                    file_size = file_path.stat().st_size
                    files.append((file_path.name, file_size))

            return files
        except Exception as e:
            logger.error(f"Error listing files: {e}")
            raise FileUploadError(f"Error listing files: {str(e)}")

    async def get_file_path(self, filename: str, directory: str) -> Path:
        """
        Get the full path to a file

        Args:
            filename: Filename
            directory: Directory where the file is located

        Returns:
            Path object for the file

        Raises:
            ResourceNotFoundError: If the file doesn't exist
        """
        file_path = Path(directory) / filename
        if not file_path.exists():
            raise ResourceNotFoundError("File", filename)
        return file_path

    async def _get_file_hash(self, file_path: Path) -> str:
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

    async def ensure_valid_audio_file(self, file: UploadFile) -> None:
        """
        Validate that a file is a valid audio file

        Args:
            file: File to validate

        Raises:
            FileUploadError: If the file is not a valid audio file
        """
        # Check MIME type
        content_type = file.content_type or ""
        if content_type not in self.ALLOWED_AUDIO_TYPES:
            raise FileUploadError(
                f"Unsupported audio format: {content_type}. Allowed types: {', '.join(self.ALLOWED_AUDIO_TYPES)}"
            )

        # Check file size (simple initial check)
        await file.seek(0)
        chunk = await file.read(1024)
        if not chunk:
            raise FileUploadError("Empty audio file")

        # Reset file position after checking
        await file.seek(0)


# Create singleton instance
file_service = FileService()