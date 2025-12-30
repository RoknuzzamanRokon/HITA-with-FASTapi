"""
Cleanup Export Files Script

This script should be run periodically (e.g., via cron job) to clean up
expired export files and free up storage space.

Usage:
    python utils/cleanup_export_files.py [--retention-hours HOURS] [--dry-run]

Examples:
    # Clean up files older than 24 hours (default)
    python utils/cleanup_export_files.py

    # Clean up files older than 48 hours
    python utils/cleanup_export_files.py --retention-hours 48

    # Dry run to see what would be deleted
    python utils/cleanup_export_files.py --dry-run
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
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def main():
    """Main cleanup function"""
    parser = argparse.ArgumentParser(
        description='Clean up expired export files'
    )
    parser.add_argument(
        '--retention-hours',
        type=int,
        default=24,
        help='Number of hours to retain export files (default: 24)'
    )
    parser.add_argument(
        '--dry-run',
        action='store_true',
        help='Show what would be deleted without actually deleting'
    )
    parser.add_argument(
        '--storage-path',
        type=str,
        default=None,
        help='Custom storage path for export files'
    )
    
    args = parser.parse_args()
    
    logger.info("=" * 60)
    logger.info("Export File Cleanup Script")
    logger.info("=" * 60)
    logger.info(f"Retention period: {args.retention_hours} hours")
    logger.info(f"Dry run: {args.dry_run}")
    logger.info(f"Started at: {datetime.utcnow().isoformat()}")
    logger.info("=" * 60)
    
    # Initialize storage handler
    storage = ExportFileStorage(base_storage_path=args.storage_path)
    
    # Get storage statistics before cleanup
    logger.info("\nStorage statistics BEFORE cleanup:")
    stats_before = storage.get_storage_stats()
    logger.info(f"  Total files: {stats_before['total_files']}")
    logger.info(f"  Total size: {stats_before['total_size_mb']} MB")
    if stats_before['oldest_file']:
        logger.info(f"  Oldest file: {stats_before['oldest_file'].isoformat()}")
    if stats_before['newest_file']:
        logger.info(f"  Newest file: {stats_before['newest_file'].isoformat()}")
    
    if args.dry_run:
        logger.info("\n*** DRY RUN MODE - No files will be deleted ***\n")
        return
    
    # Create database session
    db = SessionLocal()
    
    try:
        # Clean up expired completed exports
        logger.info(f"\nCleaning up completed exports older than {args.retention_hours} hours...")
        deleted, failed = storage.cleanup_expired_files(
            db=db,
            retention_hours=args.retention_hours
        )
        logger.info(f"  Deleted: {deleted} files")
        logger.info(f"  Failed: {failed} files")
        
        # Clean up failed exports older than 1 hour
        logger.info("\nCleaning up failed exports older than 1 hour...")
        failed_deleted = storage.cleanup_failed_exports(db=db, age_hours=1)
        logger.info(f"  Deleted: {failed_deleted} files")
        
        # Get storage statistics after cleanup
        logger.info("\nStorage statistics AFTER cleanup:")
        stats_after = storage.get_storage_stats()
        logger.info(f"  Total files: {stats_after['total_files']}")
        logger.info(f"  Total size: {stats_after['total_size_mb']} MB")
        
        # Calculate space freed
        space_freed_mb = stats_before['total_size_mb'] - stats_after['total_size_mb']
        logger.info(f"\nSpace freed: {space_freed_mb:.2f} MB")
        
        logger.info("\n" + "=" * 60)
        logger.info("Cleanup completed successfully")
        logger.info(f"Finished at: {datetime.utcnow().isoformat()}")
        logger.info("=" * 60)
        
    except Exception as e:
        logger.error(f"\nError during cleanup: {str(e)}", exc_info=True)
        sys.exit(1)
    finally:
        db.close()


if __name__ == "__main__":
    main()
