import os
import uuid
from typing import List, Set

import aiofiles
from fastapi import UploadFile

from app.core.config import settings
from loguru import logger


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
    
    async def save_file(self, file: UploadFile, directory: str) -> str:
        """
        Save an uploaded file to the specified directory
        
        Args:
            file: Uploaded file
            directory: Directory to save the file to
            
        Returns:
            Filename of the saved file
        """
        try:
            # Create directory if it doesn't exist
            os.makedirs(directory, exist_ok=True)
            
            # Generate unique filename while preserving extension
            original_filename = file.filename
            extension = os.path.splitext(original_filename)[1] if original_filename else ""
            unique_filename = f"{uuid.uuid4()}{extension}"
            file_path = os.path.join(directory, unique_filename)
            
            # Save file
            async with aiofiles.open(file_path, "wb") as buffer:
                # Read file in chunks to avoid memory issues with large files
                chunk_size = 1024 * 1024  # 1MB
                while content := await file.read(chunk_size):
                    await buffer.write(content)
            
            logger.info(f"File saved: {file_path}")
            
            return unique_filename
        except Exception as e:
            logger.error(f"Error saving file: {e}")
            raise
    
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
    
    async def list_files(self, directory: str) -> List[str]:
        """
        List all files in the specified directory
        
        Args:
            directory: Directory to list files from
            
        Returns:
            List of filenames
        """
        try:
            # Create directory if it doesn't exist
            os.makedirs(directory, exist_ok=True)
            
            # List files
            files = os.listdir(directory)
            
            # Filter out directories
            files = [f for f in files if os.path.isfile(os.path.join(directory, f))]
            
            return files
        except Exception as e:
            logger.error(f"Error listing files: {e}")
            raise


# Create singleton instance
file_service = FileService()