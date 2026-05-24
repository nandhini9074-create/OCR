import os
import hashlib
import logging
import shutil
from fastapi import UploadFile, HTTPException, status
from pathlib import Path

logger = logging.getLogger("certificate_intelligence.file_handler")

ALLOWED_EXTENSIONS = {".png", ".jpg", ".jpeg", ".webp", ".pdf"}

class FileHandler:
    def __init__(self, upload_dir: str = "./uploads"):
        self.upload_dir = Path(upload_dir)
        # Ensure uploads directory exists
        self.upload_dir.mkdir(parents=True, exist_ok=True)

    def calculate_hash(self, file_content: bytes) -> str:
        """Calculate SHA-256 hash of a file's binary content."""
        sha256_hash = hashlib.sha256()
        sha256_hash.update(file_content)
        return sha256_hash.hexdigest()

    async def save_file(self, upload_file: UploadFile) -> tuple[Path, str]:
        """
        Validate and save an uploaded certificate file to the uploads directory.
        Returns:
            Tuple of (Saved File Path, File Hash)
        """
        filename = upload_file.filename
        if not filename:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Filename cannot be empty."
            )

        file_ext = Path(filename).suffix.lower()
        if file_ext not in ALLOWED_EXTENSIONS:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Unsupported file format '{file_ext}'. Allowed formats: {', '.join(ALLOWED_EXTENSIONS)}"
            )

        try:
            # Read file bytes to calculate hash
            file_content = await upload_file.read()
            file_hash = self.calculate_hash(file_content)
            
            # Reset file pointer so it can be read/written
            await upload_file.seek(0)
            
            # Create a unique filename based on the hash to avoid collisions
            safe_filename = f"{file_hash}{file_ext}"
            file_path = self.upload_dir / safe_filename
            
            # Save the file locally (if it doesn't already exist)
            if not file_path.exists():
                with open(file_path, "wb") as buffer:
                    shutil.copyfileobj(upload_file.file, buffer)
                logger.info(f"Saved new certificate: {safe_filename} to {file_path}")
            else:
                logger.info(f"Certificate already exists on disk (hash match): {safe_filename}")
                
            return file_path, file_hash

        except Exception as e:
            logger.error(f"Error saving uploaded file: {e}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Failed to process and save the uploaded certificate file: {str(e)}"
            )

    def cleanup_file(self, file_path: Path):
        """Clean up a file if necessary (optional utility)."""
        try:
            if file_path.exists():
                os.remove(file_path)
                logger.info(f"Cleaned up file from disk: {file_path}")
        except Exception as e:
            logger.error(f"Error cleaning up file {file_path}: {e}")
