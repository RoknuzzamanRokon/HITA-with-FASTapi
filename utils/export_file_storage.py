"""
Export File Storage Utility

Manages file storage for export operations including:
- Directory structure creation
- File naming conventions
- File permissions
- Cleanup of expired files
- Storage error handling
"""

import os
import logging
import stat
from pathlib import Path
from datetime import datetime, timedelta
from typing import Optional, Tuple
from sqlalchemy.orm import Session

from models import ExportJob

# Configure logging
logger = logging.getLogger(__name__)


class ExportFileStorage:
    """
    Manages file storage for export operations.
    
    Features:
    - Automatic directory creation with proper permissions
    - Standardized file naming convention
    - File permission management
    - Cleanup of expired export files
    - Storage error handling
    """
    
    def __init__(self, base_storage_path: str = None):
        """
        Initialize ExportFileStorage.
        
        Args:
            base_storage_path: Base directory for export file storage
                              (default: ./exports/)
        """
        if base_storage_path is None:
            base_storage_path = os.path.join(os.getcwd(), "exports")
        
        self.base_storage_path = base_storage_path
        self._ensure_storage_directory()
        
        logger.info(f"ExportFileStorage initialized with base path: {self.base_storage_path}")
    
    def _ensure_storage_directory(self) -> None:
        """
        Ensure the export storage directory exists with proper permissions.
        
        Creates the directory structure if it doesn't exist and sets
        appropriate permissions to restrict access.
        """
        try:
            # Create directory if it doesn't exist
            Path(self.base_storage_path).mkdir(parents=True, exist_ok=True)
            
            # Set directory permissions (owner: rwx, group: rx, others: none)
            # This is 0o750 in octal notation
            os.chmod(self.base_storage_path, stat.S_IRWXU | stat.S_IRGRP | stat.S_IXGRP)
            
            logger.info(f"Export storage directory ensured: {self.base_storage_path}")
            
        except PermissionError as e:
            logger.error(f"Permission denied creating storage directory: {str(e)}")
            raise
        except Exception as e:
            logger.error(f"Error creating storage directory: {str(e)}")
            raise
    
    def get_file_path(
        self,
        job_id: str,
        export_type: str,
        format: str,
        timestamp: datetime = None,
        user_id: str = None
    ) -> str:
        """
        Generate standardized file path for an export.
        
        Directory structure:
        /exports/{user_id}/{export_type}/filename
        
        File naming convention:
        {export_type}_{job_id}_{timestamp}.{extension}
        
        Example: /exports/5779356081/mapping/mappings_exp_a1b2c3d4e5f6_20231116_143022.csv
        
        Args:
            job_id: Unique export job ID
            export_type: Type of export (hotels, mappings, supplier_summary)
            format: Export format (csv, json, excel)
            timestamp: Timestamp for filename (default: current time)
            user_id: User ID for organizing files (optional)
            
        Returns:
            Full file path for the export file
        """
        if timestamp is None:
            timestamp = datetime.utcnow()
        
        # Get file extension based on format
        extension_map = {
            "csv": "csv",
            "json": "json",
            "excel": "xlsx"
        }
        extension = extension_map.get(format.lower(), format.lower())
        
        # Generate filename
        timestamp_str = timestamp.strftime("%Y%m%d_%H%M%S")
        filename = f"{export_type}_{job_id}_{timestamp_str}.{extension}"
        
        # Build directory structure: /exports/{user_id}/{export_type}/
        if user_id:
            # Normalize export_type for directory name (remove 's' if plural)
            dir_export_type = export_type.rstrip('s') if export_type.endswith('s') else export_type
            
            # Create user-specific directory structure
            user_dir = os.path.join(self.base_storage_path, user_id, dir_export_type)
            
            # Ensure directory exists
            Path(user_dir).mkdir(parents=True, exist_ok=True)
            
            # Set directory permissions
            try:
                os.chmod(user_dir, stat.S_IRWXU | stat.S_IRGRP | stat.S_IXGRP)
            except Exception as e:
                logger.warning(f"Could not set permissions on {user_dir}: {str(e)}")
            
            file_path = os.path.join(user_dir, filename)
        else:
            # Fallback to flat structure if no user_id provided
            file_path = os.path.join(self.base_storage_path, filename)
        
        logger.debug(f"Generated file path: {file_path}")
        
        return file_path
    
    def set_file_permissions(self, file_path: str) -> None:
        """
        Set restrictive permissions on an export file.
        
        Sets file permissions to owner read/write only (0o600).
        This prevents unauthorized access to export files.
        
        Args:
            file_path: Path to the export file
        """
        try:
            if not os.path.exists(file_path):
                logger.warning(f"File does not exist, cannot set permissions: {file_path}")
                return
            
            # Set file permissions (owner: rw, group: none, others: none)
            # This is 0o600 in octal notation
            os.chmod(file_path, stat.S_IRUSR | stat.S_IWUSR)
            
            logger.debug(f"Set restrictive permissions on file: {file_path}")
            
        except PermissionError as e:
            logger.error(f"Permission denied setting file permissions: {str(e)}")
            # Don't raise - this is not critical
        except Exception as e:
            logger.error(f"Error setting file permissions: {str(e)}")
            # Don't raise - this is not critical
    
    def get_file_size(self, file_path: str) -> Optional[int]:
        """
        Get the size of an export file in bytes.
        
        Args:
            file_path: Path to the export file
            
        Returns:
            File size in bytes, or None if file doesn't exist
        """
        try:
            if os.path.exists(file_path):
                size = os.path.getsize(file_path)
                logger.debug(f"File size for {file_path}: {size} bytes")
                return size
            else:
                logger.warning(f"File does not exist: {file_path}")
                return None
        except Exception as e:
            logger.error(f"Error getting file size: {str(e)}")
            return None
    
    def delete_file(self, file_path: str) -> bool:
        """
        Delete an export file.
        
        Args:
            file_path: Path to the export file
            
        Returns:
            True if file was deleted successfully, False otherwise
        """
        try:
            if os.path.exists(file_path):
                os.remove(file_path)
                logger.info(f"Deleted export file: {file_path}")
                return True
            else:
                logger.warning(f"File does not exist, cannot delete: {file_path}")
                return False
        except PermissionError as e:
            logger.error(f"Permission denied deleting file: {str(e)}")
            return False
        except Exception as e:
            logger.error(f"Error deleting file: {str(e)}")
            return False
    
    def cleanup_expired_files(
        self,
        db: Session,
        retention_hours: int = 24
    ) -> Tuple[int, int]:
        """
        Clean up export files older than the retention period.
        
        This method should be run periodically (e.g., hourly) to remove
        expired export files and free up storage space.
        
        Process:
        1. Query database for expired export jobs
        2. Delete associated files from storage
        3. Update database records (optional)
        
        Args:
            db: SQLAlchemy database session
            retention_hours: Number of hours to retain files (default: 24)
            
        Returns:
            Tuple of (files_deleted, files_failed)
        """
        logger.info(f"Starting cleanup of export files older than {retention_hours} hours")
        
        files_deleted = 0
        files_failed = 0
        
        try:
            # Calculate expiration threshold
            expiration_threshold = datetime.utcnow() - timedelta(hours=retention_hours)
            
            # Query expired export jobs
            expired_jobs = db.query(ExportJob).filter(
                ExportJob.status == "completed",
                ExportJob.completed_at < expiration_threshold,
                ExportJob.file_path.isnot(None)
            ).all()
            
            logger.info(f"Found {len(expired_jobs)} expired export jobs")
            
            # Delete files for expired jobs
            for job in expired_jobs:
                if job.file_path and os.path.exists(job.file_path):
                    if self.delete_file(job.file_path):
                        files_deleted += 1
                        
                        # Update job record to mark file as deleted
                        job.file_path = None
                        job.expires_at = datetime.utcnow()
                    else:
                        files_failed += 1
            
            # Commit database changes
            db.commit()
            
            logger.info(f"Cleanup completed: {files_deleted} files deleted, {files_failed} files failed")
            
        except Exception as e:
            logger.error(f"Error during cleanup: {str(e)}")
            db.rollback()
        
        return files_deleted, files_failed
    
    def cleanup_failed_exports(self, db: Session, age_hours: int = 1) -> int:
        """
        Clean up files from failed export jobs.
        
        Failed exports may leave partial files that should be cleaned up.
        
        Args:
            db: SQLAlchemy database session
            age_hours: Minimum age in hours for failed jobs to clean up
            
        Returns:
            Number of files deleted
        """
        logger.info(f"Starting cleanup of failed export files older than {age_hours} hours")
        
        files_deleted = 0
        
        try:
            # Calculate age threshold
            age_threshold = datetime.utcnow() - timedelta(hours=age_hours)
            
            # Query failed export jobs
            failed_jobs = db.query(ExportJob).filter(
                ExportJob.status == "failed",
                ExportJob.created_at < age_threshold,
                ExportJob.file_path.isnot(None)
            ).all()
            
            logger.info(f"Found {len(failed_jobs)} failed export jobs")
            
            # Delete files for failed jobs
            for job in failed_jobs:
                if job.file_path and os.path.exists(job.file_path):
                    if self.delete_file(job.file_path):
                        files_deleted += 1
                        
                        # Update job record
                        job.file_path = None
            
            # Commit database changes
            db.commit()
            
            logger.info(f"Failed export cleanup completed: {files_deleted} files deleted")
            
        except Exception as e:
            logger.error(f"Error during failed export cleanup: {str(e)}")
            db.rollback()
        
        return files_deleted
    
    def get_storage_stats(self) -> dict:
        """
        Get statistics about the export storage directory.
        
        Returns:
            Dictionary with storage statistics:
            - total_files: Number of files in storage
            - total_size_bytes: Total size of all files
            - oldest_file: Timestamp of oldest file
            - newest_file: Timestamp of newest file
        """
        try:
            files = []
            total_size = 0
            
            # Scan storage directory
            for filename in os.listdir(self.base_storage_path):
                file_path = os.path.join(self.base_storage_path, filename)
                
                if os.path.isfile(file_path):
                    file_stat = os.stat(file_path)
                    files.append({
                        "path": file_path,
                        "size": file_stat.st_size,
                        "modified": datetime.fromtimestamp(file_stat.st_mtime)
                    })
                    total_size += file_stat.st_size
            
            # Calculate statistics
            stats = {
                "total_files": len(files),
                "total_size_bytes": total_size,
                "total_size_mb": round(total_size / (1024 * 1024), 2),
                "oldest_file": min([f["modified"] for f in files]) if files else None,
                "newest_file": max([f["modified"] for f in files]) if files else None
            }
            
            logger.debug(f"Storage stats: {stats}")
            
            return stats
            
        except Exception as e:
            logger.error(f"Error getting storage stats: {str(e)}")
            return {
                "total_files": 0,
                "total_size_bytes": 0,
                "total_size_mb": 0,
                "oldest_file": None,
                "newest_file": None,
                "error": str(e)
            }
    
    def handle_storage_error(self, error: Exception, operation: str) -> None:
        """
        Handle storage-related errors gracefully.
        
        Logs the error with appropriate context and can be extended
        to send alerts or notifications.
        
        Args:
            error: The exception that occurred
            operation: Description of the operation that failed
        """
        error_type = type(error).__name__
        error_message = str(error)
        
        logger.error(
            f"Storage error during {operation}: {error_type} - {error_message}",
            exc_info=True
        )
        
        # Could be extended to:
        # - Send alerts to monitoring system
        # - Trigger fallback storage mechanisms
        # - Notify administrators
        # - Update system health metrics
