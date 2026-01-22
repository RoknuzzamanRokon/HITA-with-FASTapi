# Notifications API - Admin Guide

## Overview

The Notifications API provides a comprehensive system for managing user notifications in the HITA platform. As an admin, you have access to all notification features and can configure system-wide notification settings.

## Table of Contents

- [Notification Types](#notification-types)
- [Priority Levels](#priority-levels)
- [API Endpoints](#api-endpoints)
- [Cleanup Job Configuration](#cleanup-job-configuration)
- [Best Practices](#best-practices)

## Notification Types

The system supports the following notification types:

| Type          | Description                  | Trigger Event                     |
| ------------- | ---------------------------- | --------------------------------- |
| `system`      | General system announcements | Manual or scheduled system events |
| `permission`  | Permission changes           | User permission granted/revoked   |
| `export`      | Export job completion        | Export job finishes processing    |
| `mapping`     | Mapping-related updates      | Mapping operations complete       |
| `point`       | Point balance changes        | Points allocated/transferred      |
| `api_key`     | API key events               | API key created/expired           |
| `maintenance` | Scheduled maintenance        | System maintenance scheduled      |

## Priority Levels

Notifications are assigned priority levels to help users identify critical messages:

| Priority   | Description                  | Use Case                               |
| ---------- | ---------------------------- | -------------------------------------- |
| `critical` | Requires immediate attention | Security alerts, system failures       |
| `high`     | Important but not urgent     | Permission changes, API key expiration |
| `medium`   | Standard notifications       | Export completions, point transactions |
| `low`      | Informational only           | General updates, tips                  |

## API Endpoints

### Authentication

All endpoints require JWT authentication via the `Authorization` header:

```
Authorization: Bearer <your_jwt_token>
```

### Base URL

```
/v1.0/notifications
```

---

### 1. Get Notifications

Retrieve a paginated list of notifications with optional filtering.

**Endpoint:** `GET /v1.0/notifications`

**Query Parameters:**

| Parameter  | Type    | Required | Default | Description                               |
| ---------- | ------- | -------- | ------- | ----------------------------------------- |
| `page`     | integer | No       | 1       | Page number (≥1)                          |
| `limit`    | integer | No       | 25      | Items per page (1-100)                    |
| `status`   | string  | No       | -       | Filter by status: `read`, `unread`        |
| `type`     | string  | No       | -       | Filter by type (see types above)          |
| `priority` | string  | No       | -       | Filter by priority (see priorities above) |

**Example Request:**

```bash
curl -X GET "https://api.hita.com/v1.0/notifications?page=1&limit=25&status=unread&priority=high" \
  -H "Authorization: Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9..."
```

**Example Response:**

```json
{
  "notifications": [
    {
      "id": 123,
      "user_id": "1234567890",
      "type": "permission",
      "priority": "high",
      "title": "Permission Updated",
      "message": "Your access to Agoda supplier has been granted by admin_user.",
      "status": "unread",
      "metadata": {
        "supplier_name": "Agoda",
        "action": "granted",
        "admin_username": "admin_user"
      },
      "created_at": "2025-11-26T10:30:00Z",
      "read_at": null
    }
  ],
  "total": 45,
  "page": 1,
  "limit": 25,
  "total_pages": 2,
  "unread_count": 12
}
```

---

### 2. Get Unread Count

Get the count of unread notifications for the current user.

**Endpoint:** `GET /v1.0/notifications/unread-count`

**Example Request:**

```bash
curl -X GET "https://api.hita.com/v1.0/notifications/unread-count" \
  -H "Authorization: Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9..."
```

**Example Response:**

```json
{
  "unread_count": 12,
  "last_notification_at": "2025-11-26T10:30:00Z"
}
```

---

### 3. Mark Notification as Read

Mark a specific notification as read.

**Endpoint:** `PUT /v1.0/notifications/{notification_id}/read`

**Path Parameters:**

| Parameter         | Type    | Required | Description            |
| ----------------- | ------- | -------- | ---------------------- |
| `notification_id` | integer | Yes      | ID of the notification |

**Example Request:**

```bash
curl -X PUT "https://api.hita.com/v1.0/notifications/123/read" \
  -H "Authorization: Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9..."
```

**Example Response:**

```json
{
  "id": 123,
  "user_id": "1234567890",
  "type": "permission",
  "priority": "high",
  "title": "Permission Updated",
  "message": "Your access to Agoda supplier has been granted by admin_user.",
  "status": "read",
  "metadata": {
    "supplier_name": "Agoda",
    "action": "granted",
    "admin_username": "admin_user"
  },
  "created_at": "2025-11-26T10:30:00Z",
  "read_at": "2025-11-26T11:15:00Z"
}
```

---

### 4. Mark All Notifications as Read

Mark all unread notifications as read for the current user.

**Endpoint:** `PUT /v1.0/notifications/mark-all-read`

**Example Request:**

```bash
curl -X PUT "https://api.hita.com/v1.0/notifications/mark-all-read" \
  -H "Authorization: Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9..."
```

**Example Response:**

```json
{
  "updated_count": 12,
  "message": "Successfully marked 12 notifications as read"
}
```

---

### 5. Delete Notification

Delete a specific notification.

**Endpoint:** `DELETE /v1.0/notifications/{notification_id}`

**Path Parameters:**

| Parameter         | Type    | Required | Description            |
| ----------------- | ------- | -------- | ---------------------- |
| `notification_id` | integer | Yes      | ID of the notification |

**Example Request:**

```bash
curl -X DELETE "https://api.hita.com/v1.0/notifications/123" \
  -H "Authorization: Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9..."
```

**Example Response:**

```json
{
  "message": "Notification deleted successfully"
}
```

---

## Error Responses

### 401 Unauthorized

```json
{
  "detail": "Could not validate credentials"
}
```

### 403 Forbidden

```json
{
  "detail": "You do not have permission to access this notification"
}
```

### 404 Not Found

```json
{
  "detail": "Notification not found"
}
```

### 422 Validation Error

```json
{
  "detail": [
    {
      "loc": ["query", "status"],
      "msg": "value is not a valid enumeration member; permitted: 'read', 'unread'",
      "type": "type_error.enum"
    }
  ]
}
```

---

## Cleanup Job Configuration

The notification system includes an automated cleanup job to prevent database growth.

### Configuration

Add the following environment variables to your `.env` file:

```bash
# Retention period in days (default: 90)
NOTIFICATION_RETENTION_DAYS=90

# Maximum page size for API requests (default: 100)
NOTIFICATION_MAX_PAGE_SIZE=100

# Cleanup schedule (cron format, default: daily at 2 AM)
NOTIFICATION_CLEANUP_SCHEDULE="0 2 * * *"
```

### Running the Cleanup Job

#### Manual Execution

```bash
python utils/cleanup_notifications.py
```

#### Scheduled Execution (Linux/Mac)

Add to crontab:

```bash
# Run daily at 2 AM
0 2 * * * cd /path/to/hita && /path/to/venv/bin/python utils/cleanup_notifications.py >> /var/log/notification_cleanup.log 2>&1
```

#### Scheduled Execution (Windows)

Use Task Scheduler to run:

```bash
python utils/cleanup_notifications.py
```

### Cleanup Behavior

- **Deletes**: Read notifications older than retention period
- **Preserves**: All unread notifications regardless of age
- **Logs**: Number of notifications deleted
- **Performance**: Processes in batches of 1000 for efficiency

### Monitoring Cleanup

Check logs for cleanup execution:

```bash
tail -f /var/log/notification_cleanup.log
```

Expected output:

```
2025-11-26 02:00:01 - INFO - Starting notification cleanup (retention: 90 days)
2025-11-26 02:00:05 - INFO - Cleaned up 1,234 old notifications
2025-11-26 02:00:05 - INFO - Cleanup completed successfully
```

---

## Best Practices

### For Admins

1. **Monitor Notification Volume**

   - Track notification creation rates
   - Alert on unusual spikes
   - Review unread counts per user

2. **Configure Appropriate Retention**

   - Balance storage vs. audit requirements
   - Consider compliance needs
   - Adjust based on user feedback

3. **Use Priority Appropriately**

   - Reserve `critical` for true emergencies
   - Use `high` for time-sensitive actions
   - Default to `medium` for routine updates

4. **Test Notification Triggers**

   - Verify permission change notifications
   - Test export completion notifications
   - Validate system maintenance broadcasts

5. **Schedule Cleanup During Low Traffic**
   - Run during off-peak hours
   - Monitor database performance
   - Adjust batch size if needed

### Triggering System Notifications

As an admin, you can trigger system-wide notifications programmatically:

```python
from services.notification_service import NotificationService
from database import SessionLocal

db = SessionLocal()
service = NotificationService(db)

# Broadcast maintenance notification to all active users
service.notify_system_maintenance(
    scheduled_at=datetime(2025, 12, 1, 2, 0, 0),
    duration="2 hours",
    description="Database upgrade and performance optimization"
)

db.close()
```

### Integration with Other Systems

The notification system automatically integrates with:

- **Permission Management**: Notifications sent when permissions change
- **Export System**: Notifications sent when exports complete
- **Point System**: Notifications sent on significant point changes
- **API Key Management**: Notifications sent on key creation/expiration

No additional configuration required - these triggers are built into the system.

---

## Troubleshooting

### High Unread Counts

If users report high unread counts:

1. Check if cleanup job is running
2. Verify retention period is appropriate
3. Consider implementing notification preferences

### Missing Notifications

If notifications aren't being created:

1. Check trigger integration points
2. Verify database connectivity
3. Review application logs for errors

### Performance Issues

If notification queries are slow:

1. Verify database indexes exist
2. Check pagination limits
3. Monitor concurrent user load
4. Consider caching strategies

---

## Support

For technical support or questions:

- Review application logs: `/var/log/hita/`
- Check database: `notifications` table
- Contact: support@hita.com
