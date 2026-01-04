#!/usr/bin/env python3
"""
Create Test Notifications Script
Adds sample notifications to the database for testing
"""

import sys
import os
from datetime import datetime

# Add the current directory to Python path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from database import get_db
from services.notification_service import NotificationService
from models import NotificationType, NotificationPriority
import models


def create_test_notifications():
    """Create test notifications for existing users"""

    # Get database session
    db = next(get_db())

    try:
        # Get all users
        users = db.query(models.User).filter(models.User.is_active == True).all()

        if not users:
            print("❌ No active users found in database")
            return False

        print(f"✅ Found {len(users)} active users")

        # Create notification service
        service = NotificationService(db)

        # Sample notifications to create
        test_notifications = [
            {
                "type": NotificationType.SYSTEM,
                "title": "Welcome to HITA",
                "message": "Welcome to the Hotel Integration Technology API! Your account is now active and ready to use.",
                "priority": NotificationPriority.MEDIUM,
                "metadata": {
                    "category": "welcome",
                    "created_by": "system",
                    "timestamp": datetime.utcnow().isoformat(),
                },
            },
            {
                "type": NotificationType.SYSTEM,
                "title": "System Maintenance Notice",
                "message": "Scheduled maintenance will occur on Sunday at 2:00 AM UTC. Expected downtime: 30 minutes.",
                "priority": NotificationPriority.HIGH,
                "metadata": {
                    "category": "maintenance",
                    "scheduled_time": "2026-01-05T02:00:00Z",
                    "duration": "30 minutes",
                },
            },
            {
                "type": NotificationType.POINT,
                "title": "Points Allocated",
                "message": "You have been allocated 1000 points for API usage. Use them wisely!",
                "priority": NotificationPriority.MEDIUM,
                "metadata": {
                    "points": 1000,
                    "transaction_type": "allocation",
                    "reason": "initial_allocation",
                },
            },
        ]

        created_count = 0

        # Create notifications for each user
        for user in users:
            print(f"\n📝 Creating notifications for user: {user.username} ({user.id})")

            for notif_data in test_notifications:
                try:
                    notification = service.create_notification(
                        user_id=user.id,
                        type=notif_data["type"],
                        title=notif_data["title"],
                        message=notif_data["message"],
                        priority=notif_data["priority"],
                        metadata=notif_data["metadata"],
                    )

                    print(
                        f"   ✅ Created: {notification.title} (ID: {notification.id})"
                    )
                    created_count += 1

                except Exception as e:
                    print(f"   ❌ Failed to create notification: {str(e)}")

        print(f"\n🎉 Successfully created {created_count} notifications!")

        # Show summary
        total_notifications = db.query(models.Notification).count()
        print(f"📊 Total notifications in database: {total_notifications}")

        return True

    except Exception as e:
        print(f"❌ Error creating test notifications: {str(e)}")
        return False

    finally:
        db.close()


def check_notifications_table():
    """Check if notifications table exists and show current data"""

    db = next(get_db())

    try:
        # Check if we can query the notifications table
        notifications = db.query(models.Notification).all()

        print(f"📋 Current notifications in database: {len(notifications)}")

        if notifications:
            print("\n📝 Recent notifications:")
            for notif in notifications[-5:]:  # Show last 5
                print(
                    f"   ID: {notif.id} | User: {notif.user_id} | Title: {notif.title}"
                )
                print(
                    f"      Type: {notif.type} | Status: {notif.status} | Created: {notif.created_at}"
                )
        else:
            print("   No notifications found")

        return True

    except Exception as e:
        print(f"❌ Error checking notifications table: {str(e)}")
        return False

    finally:
        db.close()


def main():
    """Main function"""
    print("🚀 HITA Notification System Test")
    print("=" * 50)

    # Check current state
    print("\n1️⃣ Checking notifications table...")
    if not check_notifications_table():
        return False

    # Create test notifications
    print("\n2️⃣ Creating test notifications...")
    if not create_test_notifications():
        return False

    # Check final state
    print("\n3️⃣ Final check...")
    check_notifications_table()

    print("\n✅ Test completed successfully!")
    print("\nYou can now:")
    print("- Test the notification endpoints with the test script")
    print("- View notifications in the API at /v1.0/notifications/")
    print("- Check unread count at /v1.0/notifications/unread-count")

    return True


if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
