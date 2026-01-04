"""
Cleanup Notifications Script

This script should be run periodically (e.g., via cron job) to clean up
old read notifications and prevent database growth.

Usage:
    python utils/cleanup_notifications.py [--retention-days DAYS] [--dry-run]

Examples:
    # Clean up notifications older than 90 days (default)
    python utils/cleanup_notifications.py

    # Clean up notifications older than 30 days
    python utils/cleanup_notifications.py --retention-days 30

    # Dry run to see what would be deleted
    python utils/cleanup_notifications.py --dry-run

Cron Job Setup:
    # Run daily at 2:00 AM
    0 2 * * * cd /path/to/hita && /path/to/python utils/cleanup_notifications.py >> /var/log/notification_cleanup.log 2>&1

    # Run weekly on Sunday at 3:00 AM with 60-day retention
    0 3 * * 0 cd /path/to/hita && /path/to/python utils/cleanup_notifications.py --retention-days 60 >> /var/log/notification_cleanup.log 2>&1

Windows Scheduled Task:
    1. Open Task Scheduler
    2. Create Basic Task
    3. Set trigger (e.g., Daily at 2:00 AM)
    4. Action: Start a program
       - Program: C:\\path\\to\\python.exe
       - Arguments: utils/cleanup_notifications.py
       - Start in: C:\\path\\to\\hita
"""

import os
import sys
import argparse
import logging
from datetime import datetime

# Add parent directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from database import SessionLocal
from services.notification_service import NotificationService
from models import Notification, NotificationStatus

# Configure logging
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


def get_notification_stats(db):
    """Get statistics about notifications in the database"""
    total_count = db.query(Notification).count()
    read_count = (
        db.query(Notification)
        .filter(Notification.status == NotificationStatus.READ)
        .count()
    )
    unread_count = (
        db.query(Notification)
        .filter(Notification.status == NotificationStatus.UNREAD)
        .count()
    )

    # Get oldest notification
    oldest = db.query(Notification).order_by(Notification.created_at.asc()).first()
    oldest_date = oldest.created_at if oldest else None

    # Get newest notification
    newest = db.query(Notification).order_by(Notification.created_at.desc()).first()
    newest_date = newest.created_at if newest else None

    return {
        "total": total_count,
        "read": read_count,
        "unread": unread_count,
        "oldest": oldest_date,
        "newest": newest_date,
    }


def get_retention_days_from_env():
    """Get retention days from environment variable"""
    try:
        return int(os.getenv("NOTIFICATION_RETENTION_DAYS", "90"))
    except ValueError:
        logger.warning("Invalid NOTIFICATION_RETENTION_DAYS value, using default: 90")
        return 90


def main():
    """Main cleanup function"""
    parser = argparse.ArgumentParser(description="Clean up old read notifications")
    parser.add_argument(
        "--retention-days",
        type=int,
        default=None,
        help="Number of days to retain notifications (default: from env or 90)",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Show what would be deleted without actually deleting",
    )

    args = parser.parse_args()

    # Get retention days from args, env, or default
    if args.retention_days is not None:
        retention_days = args.retention_days
    else:
        retention_days = get_retention_days_from_env()

    logger.info("=" * 60)
    logger.info("Notification Cleanup Script")
    logger.info("=" * 60)
    logger.info(f"Retention period: {retention_days} days")
    logger.info(f"Dry run: {args.dry_run}")
    logger.info(f"Started at: {datetime.utcnow().isoformat()}")
    logger.info("=" * 60)

    # Create database session
    db = SessionLocal()

    try:
        # Get statistics before cleanup
        logger.info("\nNotification statistics BEFORE cleanup:")
        stats_before = get_notification_stats(db)
        logger.info(f"  Total notifications: {stats_before['total']}")
        logger.info(f"  Read notifications: {stats_before['read']}")
        logger.info(f"  Unread notifications: {stats_before['unread']}")
        if stats_before["oldest"]:
            logger.info(f"  Oldest notification: {stats_before['oldest'].isoformat()}")
        if stats_before["newest"]:
            logger.info(f"  Newest notification: {stats_before['newest'].isoformat()}")

        if args.dry_run:
            logger.info("\n*** DRY RUN MODE - No notifications will be deleted ***")
            logger.info(
                f"\nWould delete read notifications older than {retention_days} days"
            )
            logger.info("(Unread notifications are preserved regardless of age)")
            logger.info("\n" + "=" * 60)
            logger.info("Dry run completed")
            logger.info("=" * 60)
            return

        # Perform cleanup
        logger.info(
            f"\nCleaning up read notifications older than {retention_days} days..."
        )
        logger.info("(Unread notifications will be preserved regardless of age)")

        service = NotificationService(db)
        deleted_count = service.cleanup_old_notifications(retention_days)

        logger.info(f"  Deleted: {deleted_count} notifications")

        # Get statistics after cleanup
        logger.info("\nNotification statistics AFTER cleanup:")
        stats_after = get_notification_stats(db)
        logger.info(f"  Total notifications: {stats_after['total']}")
        logger.info(f"  Read notifications: {stats_after['read']}")
        logger.info(f"  Unread notifications: {stats_after['unread']}")

        # Calculate reduction
        reduction = stats_before["total"] - stats_after["total"]
        if stats_before["total"] > 0:
            reduction_pct = (reduction / stats_before["total"]) * 100
            logger.info(
                f"\nReduction: {reduction} notifications ({reduction_pct:.1f}%)"
            )

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
