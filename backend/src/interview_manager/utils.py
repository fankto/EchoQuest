import os
import shutil
from datetime import datetime
import aiofiles

async def save_to_permanent_storage(file_content: bytes, unique_filename: str):
    # Create a directory for permanent storage if it doesn't exist
    permanent_storage_dir = os.path.join(os.path.dirname(__file__), "permanent_storage")
    os.makedirs(permanent_storage_dir, exist_ok=True)

    # Use the provided unique filename
    permanent_file_path = os.path.join(permanent_storage_dir, unique_filename)

    # Asynchronously write the file content to permanent storage
    async with aiofiles.open(permanent_file_path, 'wb') as dest_file:
        await dest_file.write(file_content)

    # Return the path to the permanently stored file
    return permanent_file_path