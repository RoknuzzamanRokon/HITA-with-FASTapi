# Notification Cleanup Job Guide

## Overview

The notification cleanup script (`cleanup_notifications.py`) is designed to automatically remove old read notifications from the database to prevent unbounded growth. This script should be run periodically using a cron job (Linux/Mac) or Windows Task Scheduler.

## Features

- **Selective Deletion**: Only deletes READ notifications older than the retention period
- **Unread Preservation**: Unread notifications are NEVER deleted, regardless of age
- **Configurable Retention**: Retention period can be set via environment variable, command-line argument, or defaults to 90 days
- **Dry Run Mode**: Test what would be deleted without actually deleting anything
- **Detailed Logging**: Provides statistics before and after cleanup
- **Safe Execution**: Handles errors gracefully and logs all operations

## Usage

### Basic Usage

```bash
# Clean up notifications older than 90 days (default)
python utils/cleanup_notifications.py

# Clean up notifications older than 30 days
python utils/cleanup_notifications.py --retention-days 30

# Dry run to see what would be deleted
python utils/cleanup_notifications.py --dry-run

# Dry run with custom retention period
python utils/cleanup_notifications.py --retention-days 60 --dry-run
```

### Command-Line Options

- `--retention-days DAYS`: Number of days to retain notifications (default: from env or 90)
- `--dry-run`: Show what would be deleted without actually deleting
- `--help`: Show help message

## Configuration

### Environment Variable

Add to your `.env` file:

```bash
# Number of days to retain read notifications (default: 90)
# Unread notifications are preserved regardless of age
NOTIFICATION_RETENTION_DAYS=90
```

### Priority Order

The script determines retention period in this order:

1. Command-line argument (`--retention-days`)
2. Environment variable (`NOTIFICATION_RETENTION_DAYS`)
3. Default value (90 days)

## Scheduling

### Linux/Mac - Cron Job

Edit your crontab:

```bash
crontab -e
```

Add one of these entries:

```bash
# Run daily at 2:00 AM with default retention (90 days)
0 2 * * * cd /path/to/hita && /path/to/python utils/cleanup_notifications.py >> /var/log/notification_cleanup.log 2>&1

# Run daily at 3:00 AM with 60-day retention
0 3 * * * cd /path/to/hita && /path/to/python utils/cleanup_notifications.py --retention-days 60 >> /var/log/notification_cleanup.log 2>&1

# Run weekly on Sunday at 2:00 AM
0 2 * * 0 cd /path/to/hita && /path/to/python utils/cleanup_notifications.py >> /var/log/notification_cleanup.log 2>&1

# Run monthly on the 1st at 2:00 AM
0 2 1 * * cd /path/to/hita && /path/to/python utils/cleanup_notifications.py >> /var/log/notification_cleanup.log 2>&1
```

#### Cron Schedule Format

```
* * * * *
│ │ │ │ │
│ │ │ │ └─── Day of week (0-7, Sunday = 0 or 7)
│ │ │ └───── Month (1-12)
│ │ └─────── Day of month (1-31)
│ └───────── Hour (0-23)
└─────────── Minute (0-59)
```

### Windows - Task Scheduler

#### Using GUI:

1. Open **Task Scheduler** (search in Start menu)
2. Click **Create Basic Task** in the right panel
3. **Name**: "Notification Cleanup"
4. **Description**: "Clean up old read notifications"
5. **Trigger**: Choose frequency (Daily, Weekly, Monthly)
6. **Action**: Start a program
   - **Program/script**: `C:\path\to\python.exe`
   - **Add arguments**: `utils/cleanup_notifications.py`
   - **Start in**: `C:\path\to\hita\backend`
7. Click **Finish**

#### Using Command Line:

```cmd
REM Daily at 2:00 AM
schtasks /create /tn "NotificationCleanup" /tr "C:\path\to\python.exe utils/cleanup_notifications.py" /sc daily /st 02:00 /sd 01/01/2025

REM Weekly on Sunday at 2:00 AM
schtasks /create /tn "NotificationCleanup" /tr "C:\path\to\python.exe utils/cleanup_notifications.py" /sc weekly /d SUN /st 02:00
```

#### Using PowerShell:

```powershell
# Create a scheduled task that runs daily at 2:00 AM
$action = New-ScheduledTaskAction -Execute "C:\path\to\python.exe" -Argument "utils/cleanup_notifications.py" -WorkingDirectory "C:\path\to\hita\backend"
$trigger = New-ScheduledTaskTrigger -Daily -At 2am
Register-ScheduledTask -Action $action -Trigger $trigger -TaskName "NotificationCleanup" -Description "Clean up old read notifications"
```

## Logging

### View Logs (Linux/Mac)

```bash
# View recent cleanup logs
tail -f /var/log/notification_cleanup.log

# View last 100 lines
tail -n 100 /var/log/notification_cleanup.log

# Search for errors
grep -i error /var/log/notification_cleanup.log
```

### View Logs (Windows)

Check the Task Scheduler history:

1. Open Task Scheduler
2. Find "NotificationCleanup" task
3. Click on the **History** tab

Or redirect output to a file:

```cmd
python utils/cleanup_notifications.py >> C:\logs\notification_cleanup.log 2>&1
```

## Example Output

### Dry Run

```
============================================================
Notification Cleanup Script
============================================================
Retention period: 90 days
Dry run: True
Started at: 2025-11-26T06:31:30.730579
============================================================

Notification statistics BEFORE cleanup:
  Total notifications: 1523
  Read notifications: 1245
  Unread notifications: 278
  Oldest notification: 2024-08-15T10:23:45.123456
  Newest notification: 2025-11-26T05:12:33.987654

*** DRY RUN MODE - No notifications will be deleted ***

Would delete read notifications older than 90 days
(Unread notifications are preserved regardless of age)

============================================================
Dry run completed
============================================================
```

### Actual Cleanup

```
============================================================
Notification Cleanup Script
============================================================
Retention period: 90 days
Dry run: False
Started at: 2025-11-26T06:35:00.123456
============================================================

Notification statistics BEFORE cleanup:
  Total notifications: 1523
  Read notifications: 1245
  Unread notifications: 278
  Oldest notification: 2024-08-15T10:23:45.123456
  Newest notification: 2025-11-26T05:12:33.987654

Cleaning up read notifications older than 90 days...
(Unread notifications will be preserved regardless of age)
  Deleted: 856 notifications

Notification statistics AFTER cleanup:
  Total notifications: 667
  Read notifications: 389
  Unread notifications: 278

Reduction: 856 notifications (56.2%)

============================================================
Cleanup completed successfully
Finished at: 2025-11-26T06:35:02.456789
============================================================
```

## Best Practices

1. **Test First**: Always run with `--dry-run` before scheduling
2. **Monitor Logs**: Check logs regularly to ensure cleanup is working
3. **Adjust Retention**: Start with longer retention (90+ days) and adjust based on usage
4. **Schedule Off-Peak**: Run during low-traffic hours (e.g., 2-4 AM)
5. **Backup Database**: Ensure regular database backups before cleanup
6. **Alert on Failures**: Set up monitoring to alert on cleanup failures

## Recommended Schedules

| User Base               | Notification Volume | Recommended Schedule | Retention Period |
| ----------------------- | ------------------- | -------------------- | ---------------- |
| Small (<100 users)      | Low                 | Weekly               | 90 days          |
| Medium (100-1000 users) | Medium              | Daily                | 60-90 days       |
| Large (1000+ users)     | High                | Daily                | 30-60 days       |
| Enterprise              | Very High           | Daily or Twice Daily | 30 days          |

## Troubleshooting

### Script Fails to Run

**Problem**: Script exits with error
**Solution**: Check database connection and permissions

```bash
# Test database connection
python -c "from database import SessionLocal; db = SessionLocal(); print('Connected'); db.close()"
```

### No Notifications Deleted

**Problem**: Script runs but deletes 0 notifications
**Possible Causes**:

- All notifications are unread (preserved by design)
- All notifications are newer than retention period
- Retention period is too long

**Solution**: Run with `--dry-run` to see statistics

### Permission Denied

**Problem**: Cannot write to log file
**Solution**: Ensure log directory exists and has write permissions

```bash
# Linux/Mac
mkdir -p /var/log
chmod 755 /var/log

# Windows
mkdir C:\logs
```

### Cron Job Not Running

**Problem**: Cron job doesn't execute
**Solution**: Check cron service and syntax

```bash
# Check if cron is running
sudo systemctl status cron

# View cron logs
grep CRON /var/log/syslog

# Test cron entry syntax
crontab -l
```

## Monitoring

### Key Metrics to Track

1. **Deletion Count**: Number of notifications deleted per run
2. **Execution Time**: How long cleanup takes
3. **Database Size**: Monitor database growth over time
4. **Error Rate**: Track failed cleanup attempts

### Sample Monitoring Script

```bash
#!/bin/bash
# monitor_cleanup.sh

LOG_FILE="/var/log/notification_cleanup.log"
ALERT_EMAIL="admin@example.com"

# Check if cleanup ran today
if ! grep -q "$(date +%Y-%m-%d)" "$LOG_FILE"; then
    echo "Notification cleanup did not run today!" | mail -s "Cleanup Alert" "$ALERT_EMAIL"
fi

# Check for errors
if grep -q "Error during cleanup" "$LOG_FILE"; then
    echo "Notification cleanup encountered errors!" | mail -s "Cleanup Error" "$ALERT_EMAIL"
fi
```

## Related Documentation

- [Notification System Design](../.kiro/specs/notification-system/design.md)
- [Notification API Documentation](../docs/admin/NOTIFICATIONS_API_ADMIN.md)
- [Database Maintenance Guide](../docs/admin/DATABASE_MAINTENANCE.md)

## Support

For issues or questions:

1. Check the logs for error messages
2. Run with `--dry-run` to diagnose issues
3. Review the notification service logs
4. Contact system administrator
