"""
Export File Cleanup Script

Scheduled job to clean up expired export files.
Should be run periodically (e.g., hourly via cron or task scheduler).

Usage:
    python utils/cleanup_export_files.py [--retention-hours 24] [--dry-run]
"""

import os
import sys
import argparse
import logging
from datetime import datetime

# Add parent directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from database import SessionLocal
from utils.export_file_storage import ExportFileStorage

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('export_cleanup.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)


def cleanup_exports(retention_hours: int = 24, dry_run: bool = False) -> None:
    """
    Clean up expired export files.
    
    Args:
        retention_hours: Number of hours to retain files (default: 24)
        dry_run: If True, only report what would be deleted without actually deleting
    """
    logger.info("=" * 80)
    logger.info(f"Export File Cleanup Job Started - {datetime.utcnow().isoformat()}")
    logger.info(f"Retention period: {retention_hours} hours")
    logger.info(f"Dry run mode: {dry_run}")
    logger.info("=" * 80)
    
    # Get storage path from environment or use default
    storage_path = os.getenv("EXPORT_STORAGE_PATH", os.path.join(os.getcwd(), "exports"))
    
    # Initialize storage manager
    storage = ExportFileStorage(storage_path)
    
    # Get storage statistics before cleanup
    logger.info("Storage statistics before cleanup:")
    stats_before = storage.get_storage_stats()
    logger.info(f"  Total files: {stats_before['total_files']}")
    logger.info(f"  Total size: {stats_before['total_size_mb']} MB")
    if stats_before['oldest_file']:
        logger.info(f"  Oldest file: {stats_before['oldest_file'].isoformat()}")
    if stats_before['newest_file']:
        logger.info(f"  Newest file: {stats_before['newest_file'].isoformat()}")
    
    if dry_run:
        logger.info("\n*** DRY RUN MODE - No files will be deleted ***\n")
        return
    
    # Create database session
    db = SessionLocal()
    
    try:
        # Clean up expired completed exports
        logger.info(f"\nCleaning up completed exports older than {retention_hours} hours...")
        files_deleted, files_failed = storage.cleanup_expired_files(db, retention_hours)
        logger.info(f"Completed exports cleanup: {files_deleted} deleted, {files_failed} failed")
        
        # Clean up failed exports (older than 1 hour)
        logger.info("\nCleaning up failed exports older than 1 hour...")
        failed_deleted = storage.cleanup_failed_exports(db, age_hours=1)
        logger.info(f"Failed exports cleanup: {failed_deleted} deleted")
        
        # Get storage statistics after cleanup
        logger.info("\nStorage statistics after cleanup:")
        stats_after = storage.get_storage_stats()
        logger.info(f"  Total files: {stats_after['total_files']}")
        logger.info(f"  Total size: {stats_after['total_size_mb']} MB")
        
        # Calculate space freed
        space_freed_mb = stats_before['total_size_mb'] - stats_after['total_size_mb']
        logger.info(f"\nSpace freed: {space_freed_mb} MB")
        
        logger.info("\n" + "=" * 80)
        logger.info("Export File Cleanup Job Completed Successfully")
        logger.info("=" * 80)
        
    except Exception as e:
        logger.error(f"Error during cleanup: {str(e)}", exc_info=True)
        raise
    finally:
        db.close()


def main():
    """Main entry point for the cleanup script."""
    parser = argparse.ArgumentParser(
        description="Clean up expired export files"
    )
    parser.add_argument(
        "--retention-hours",
        type=int,
        default=24,
        help="Number of hours to retain export files (default: 24)"
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Show what would be deleted without actually deleting"
    )
    
    args = parser.parse_args()
    
    try:
        cleanup_exports(
            retention_hours=args.retention_hours,
            dry_run=args.dry_run
        )
    except Exception as e:
        logger.error(f"Cleanup job failed: {str(e)}")
        sys.exit(1)


if __name__ == "__main__":
    main()
