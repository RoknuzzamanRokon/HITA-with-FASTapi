# Notifications API - User Guide

## Overview

The Notifications API allows you to stay informed about important events and updates in the HITA platform. You'll receive notifications about permission changes, export completions, point transactions, and other activities relevant to your account.

## Table of Contents

- [Getting Started](#getting-started)
- [Understanding Notifications](#understanding-notifications)
- [Using the API](#using-the-api)
- [Common Use Cases](#common-use-cases)
- [FAQ](#faq)

## Getting Started

### Authentication

All notification endpoints require authentication. Include your JWT token in the request header:

```
Authorization: Bearer <your_jwt_token>
```

You receive this token when you log in to the HITA platform.

### Base URL

All notification endpoints start with:

```
/v1.0/notifications
```

## Understanding Notifications

### Notification Types

You'll receive different types of notifications based on your activities:

| Type            | What It Means                  | Example                           |
| --------------- | ------------------------------ | --------------------------------- |
| **System**      | General platform announcements | "New feature available"           |
| **Permission**  | Changes to your access rights  | "Access to Agoda granted"         |
| **Export**      | Your export jobs are complete  | "Hotel export ready for download" |
| **Mapping**     | Mapping operations finished    | "Mapping update completed"        |
| **Point**       | Changes to your point balance  | "100 points received"             |
| **API Key**     | API key created or expiring    | "API key expires in 7 days"       |
| **Maintenance** | Scheduled system maintenance   | "Maintenance on Dec 1st"          |

### Priority Levels

Notifications have priority levels to help you identify what needs attention:

- 🔴 **Critical**: Requires immediate action (security alerts, system issues)
- 🟠 **High**: Important but not urgent (permission changes, key expiration)
- 🟡 **Medium**: Standard updates (export completions, point changes)
- 🟢 **Low**: Informational only (tips, general updates)

### Notification Status

- **Unread**: New notifications you haven't reviewed yet
- **Read**: Notifications you've already seen

## Using the API

### 1. View Your Notifications

Get a list of your notifications with pagination and filtering.

**Request:**

```bash
GET /v1.0/notifications?page=1&limit=25&status=unread
```

**Parameters:**

- `page` (optional): Page number, default is 1
- `limit` (optional): Items per page (1-100), default is 25
- `status` (optional): Filter by `read` or `unread`
- `type` (optional): Filter by notification type
- `priority` (optional): Filter by priority level

**Example:**

```bash
curl -X GET "https://api.hita.com/v1.0/notifications?page=1&limit=10&status=unread" \
  -H "Authorization: Bearer your_token_here"
```

**Response:**

```json
{
  "notifications": [
    {
      "id": 123,
      "type": "export",
      "priority": "medium",
      "title": "Export Complete",
      "message": "Your hotel export for Agoda is ready for download.",
      "status": "unread",
      "created_at": "2025-11-26T10:30:00Z",
      "read_at": null
    },
    {
      "id": 122,
      "type": "point",
      "priority": "medium",
      "title": "Points Received",
      "message": "You received 100 points from admin_user.",
      "status": "unread",
      "created_at": "2025-11-26T09:15:00Z",
      "read_at": null
    }
  ],
  "total": 15,
  "page": 1,
  "limit": 10,
  "total_pages": 2,
  "unread_count": 8
}
```

---

### 2. Check Unread Count

Quickly see how many unread notifications you have.

**Request:**

```bash
GET /v1.0/notifications/unread-count
```

**Example:**

```bash
curl -X GET "https://api.hita.com/v1.0/notifications/unread-count" \
  -H "Authorization: Bearer your_token_here"
```

**Response:**

```json
{
  "unread_count": 8,
  "last_notification_at": "2025-11-26T10:30:00Z"
}
```

---

### 3. Mark a Notification as Read

Mark a specific notification as read after you've reviewed it.

**Request:**

```bash
PUT /v1.0/notifications/{notification_id}/read
```

**Example:**

```bash
curl -X PUT "https://api.hita.com/v1.0/notifications/123/read" \
  -H "Authorization: Bearer your_token_here"
```

**Response:**

```json
{
  "id": 123,
  "type": "export",
  "priority": "medium",
  "title": "Export Complete",
  "message": "Your hotel export for Agoda is ready for download.",
  "status": "read",
  "created_at": "2025-11-26T10:30:00Z",
  "read_at": "2025-11-26T11:00:00Z"
}
```

---

### 4. Mark All as Read

Clear all your unread notifications at once.

**Request:**

```bash
PUT /v1.0/notifications/mark-all-read
```

**Example:**

```bash
curl -X PUT "https://api.hita.com/v1.0/notifications/mark-all-read" \
  -H "Authorization: Bearer your_token_here"
```

**Response:**

```json
{
  "updated_count": 8,
  "message": "Successfully marked 8 notifications as read"
}
```

---

### 5. Delete a Notification

Remove a notification you no longer need.

**Request:**

```bash
DELETE /v1.0/notifications/{notification_id}
```

**Example:**

```bash
curl -X DELETE "https://api.hita.com/v1.0/notifications/123" \
  -H "Authorization: Bearer your_token_here"
```

**Response:**

```json
{
  "message": "Notification deleted successfully"
}
```

---

## Common Use Cases

### Use Case 1: Check for New Notifications

Check if you have any new unread notifications:

```bash
# Get unread count
curl -X GET "https://api.hita.com/v1.0/notifications/unread-count" \
  -H "Authorization: Bearer your_token_here"

# If count > 0, fetch unread notifications
curl -X GET "https://api.hita.com/v1.0/notifications?status=unread&limit=10" \
  -H "Authorization: Bearer your_token_here"
```

---

### Use Case 2: Review Export Notifications

Check if your export jobs are complete:

```bash
curl -X GET "https://api.hita.com/v1.0/notifications?type=export&status=unread" \
  -H "Authorization: Bearer your_token_here"
```

---

### Use Case 3: Monitor Permission Changes

See if your access permissions have been updated:

```bash
curl -X GET "https://api.hita.com/v1.0/notifications?type=permission&priority=high" \
  -H "Authorization: Bearer your_token_here"
```

---

### Use Case 4: Clear Old Notifications

Mark all notifications as read and delete old ones:

```bash
# Mark all as read
curl -X PUT "https://api.hita.com/v1.0/notifications/mark-all-read" \
  -H "Authorization: Bearer your_token_here"

# Delete specific notifications
curl -X DELETE "https://api.hita.com/v1.0/notifications/123" \
  -H "Authorization: Bearer your_token_here"
```

---

### Use Case 5: Check Critical Alerts

View only critical priority notifications:

```bash
curl -X GET "https://api.hita.com/v1.0/notifications?priority=critical&status=unread" \
  -H "Authorization: Bearer your_token_here"
```

---

## Error Messages

### 401 Unauthorized

**Cause**: Your authentication token is missing or invalid.

**Solution**: Log in again to get a new token.

```json
{
  "detail": "Could not validate credentials"
}
```

---

### 403 Forbidden

**Cause**: You're trying to access a notification that doesn't belong to you.

**Solution**: Only access your own notifications.

```json
{
  "detail": "You do not have permission to access this notification"
}
```

---

### 404 Not Found

**Cause**: The notification ID doesn't exist or has been deleted.

**Solution**: Verify the notification ID is correct.

```json
{
  "detail": "Notification not found"
}
```

---

### 422 Validation Error

**Cause**: Invalid parameter values in your request.

**Solution**: Check that filter values match allowed options.

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

## FAQ

### How long are notifications stored?

Read notifications are automatically deleted after 90 days. Unread notifications are kept indefinitely until you mark them as read or delete them manually.

### Can I get notifications via email?

Currently, notifications are only available through the API. Email notifications may be added in a future update.

### Why didn't I receive a notification?

Notifications are created automatically for specific events:

- Permission changes by admins
- Export job completions
- Point balance changes
- API key events
- System maintenance announcements

If you expected a notification but didn't receive one, contact your administrator.

### Can I customize which notifications I receive?

Currently, all users receive notifications for events related to their account. Notification preferences may be added in a future update.

### What happens to notifications when I delete them?

Deleted notifications are permanently removed and cannot be recovered. Consider marking them as read instead if you might need to reference them later.

### How do I know if a notification is important?

Check the `priority` field:

- `critical` and `high` priority notifications typically require action
- `medium` and `low` priority are informational

### Can I access another user's notifications?

No. You can only access notifications that belong to your account. Attempting to access another user's notifications will result in a 403 Forbidden error.

### How many notifications can I retrieve at once?

You can retrieve up to 100 notifications per request using the `limit` parameter. Use pagination to access more notifications.

### Do notifications affect my point balance?

No. Viewing, marking as read, or deleting notifications does not consume any points. Notifications are a free feature to keep you informed.

---

## Tips for Managing Notifications

1. **Check Regularly**: Review your notifications daily to stay informed
2. **Use Filters**: Filter by type or priority to focus on what matters
3. **Mark as Read**: Keep your notification list organized by marking items as read
4. **Delete Old Ones**: Remove notifications you no longer need
5. **Watch for Critical**: Always check critical priority notifications immediately
6. **Monitor Exports**: Use export notifications to know when your data is ready
7. **Track Permissions**: Permission notifications help you understand your access rights

---

## Integration Examples

### Python Example

```python
import requests

# Configuration
BASE_URL = "https://api.hita.com/v1.0"
TOKEN = "your_jwt_token_here"
HEADERS = {"Authorization": f"Bearer {TOKEN}"}

# Get unread notifications
response = requests.get(
    f"{BASE_URL}/notifications",
    params={"status": "unread", "limit": 10},
    headers=HEADERS
)

notifications = response.json()
print(f"You have {notifications['unread_count']} unread notifications")

# Mark all as read
response = requests.put(
    f"{BASE_URL}/notifications/mark-all-read",
    headers=HEADERS
)

result = response.json()
print(result['message'])
```

### JavaScript Example

```javascript
const BASE_URL = "https://api.hita.com/v1.0";
const TOKEN = "your_jwt_token_here";

// Get unread count
async function getUnreadCount() {
  const response = await fetch(`${BASE_URL}/notifications/unread-count`, {
    headers: {
      Authorization: `Bearer ${TOKEN}`,
    },
  });

  const data = await response.json();
  console.log(`Unread notifications: ${data.unread_count}`);
}

// Mark notification as read
async function markAsRead(notificationId) {
  const response = await fetch(
    `${BASE_URL}/notifications/${notificationId}/read`,
    {
      method: "PUT",
      headers: {
        Authorization: `Bearer ${TOKEN}`,
      },
    }
  );

  const data = await response.json();
  console.log("Notification marked as read:", data);
}

getUnreadCount();
```

---

## Support

If you have questions or need help:

1. Check this documentation first
2. Review the error message for guidance
3. Contact your system administrator
4. Email support: support@hita.com

---

## What's Next?

- Explore the [API Documentation](/docs) for more endpoints
- Learn about [Export Management](CONTENT_API_GENERAL_USER.md)
- Understand [Point System](ANALYTICS_API_GENERAL_USER.md)
