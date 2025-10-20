# Dashboard API Documentation

## Overview

The Dashboard API provides comprehensive statistics and analytics for admin and superuser roles. It includes user metrics, activity tracking, and points distribution data.

## Base URL

```
http://localhost:3000/v1.0/dashboard
```

## Authentication

All dashboard endpoints require authentication and admin/superuser privileges:

- **Required Role**: `admin_user` or `super_user`
- **Authentication**: Bearer token in Authorization header
- **Header**: `Authorization: Bearer <access_token>`

## Endpoints

### 1. Main Dashboard Statistics

**GET** `/stats`

Returns comprehensive dashboard statistics including all requested metrics.

#### Response Format

```json
{
  "total_users": 150,
  "active_users": 45,
  "admin_users": 5,
  "general_users": 140,
  "points_distributed": 50000,
  "current_balance": 25000,
  "recent_signups": 12,
  "inactive_users": 105,
  "additional_stats": {
    "super_users": 2,
    "admin_users_only": 3,
    "total_transactions": 1250,
    "recent_activity_count": 89,
    "users_with_api_keys": 8,
    "points_used": 25000
  },
  "timestamp": "2024-10-16T10:30:00.000Z",
  "requested_by": {
    "user_id": "abc123",
    "username": "admin_user",
    "role": "super_user"
  }
}
```

#### Field Descriptions

- **total_users**: Total number of registered users
- **active_users**: Users with activity in the last 7 days
- **admin_users**: Combined count of admin and super users
- **general_users**: Count of general users
- **points_distributed**: Total points ever distributed to users
- **current_balance**: Current total points balance across all users
- **recent_signups**: New user registrations in the last 30 days
- **inactive_users**: Users with no activity in the last 30 days

### 2. User Activity Statistics

**GET** `/user-activity?days=30`

Returns detailed user activity analytics.

#### Query Parameters

- `days` (optional): Number of days to look back (default: 30)

#### Response Format

```json
{
  "period_days": 30,
  "daily_activity": [
    {
      "date": "2024-10-15",
      "activity_count": 45,
      "unique_users": 12
    }
  ],
  "most_active_users": [
    {
      "user_id": "user123",
      "username": "john_doe",
      "email": "john@example.com",
      "role": "general_user",
      "activity_count": 89
    }
  ],
  "timestamp": "2024-10-16T10:30:00.000Z"
}
```

### 3. Points Summary

**GET** `/points-summary`

Returns detailed points and transaction statistics.

#### Response Format

```json
{
  "points_by_role": [
    {
      "role": "general_user",
      "user_count": 140,
      "total_points": 45000,
      "current_points": 22000,
      "avg_points": 157.14
    }
  ],
  "recent_transactions_30d": 156,
  "transaction_types": [
    {
      "type": "allocation",
      "count": 89,
      "total_points": 25000
    }
  ],
  "top_point_holders": [
    {
      "user_id": "user456",
      "username": "power_user",
      "role": "admin_user",
      "current_points": 5000,
      "total_points": 8000
    }
  ],
  "timestamp": "2024-10-16T10:30:00.000Z"
}
```

## Usage Examples

### Frontend Integration (React/Next.js)

```javascript
// Dashboard component example
const Dashboard = () => {
  const [stats, setStats] = useState(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    const fetchDashboardStats = async () => {
      try {
        const token = localStorage.getItem("access_token");
        const response = await fetch(
          "http://localhost:8000/v1.0/dashboard/stats",
          {
            headers: {
              Authorization: `Bearer ${token}`,
              "Content-Type": "application/json",
            },
          }
        );

        if (response.ok) {
          const data = await response.json();
          setStats(data);
        } else {
          console.error("Failed to fetch dashboard stats");
        }
      } catch (error) {
        console.error("Error:", error);
      } finally {
        setLoading(false);
      }
    };

    fetchDashboardStats();
  }, []);

  if (loading) return <div>Loading...</div>;

  return (
    <div className="dashboard">
      <div className="stats-grid">
        <div className="stat-card">
          <h3>Total Users</h3>
          <p>{stats?.total_users}</p>
        </div>
        <div className="stat-card">
          <h3>Active Users</h3>
          <p>{stats?.active_users}</p>
        </div>
        <div className="stat-card">
          <h3>Admin Users</h3>
          <p>{stats?.admin_users}</p>
        </div>
        <div className="stat-card">
          <h3>General Users</h3>
          <p>{stats?.general_users}</p>
        </div>
        <div className="stat-card">
          <h3>Points Distributed</h3>
          <p>{stats?.points_distributed?.toLocaleString()}</p>
        </div>
        <div className="stat-card">
          <h3>Current Balance</h3>
          <p>{stats?.current_balance?.toLocaleString()}</p>
        </div>
        <div className="stat-card">
          <h3>Recent Signups</h3>
          <p>{stats?.recent_signups}</p>
        </div>
        <div className="stat-card">
          <h3>Inactive Users</h3>
          <p>{stats?.inactive_users}</p>
        </div>
      </div>
    </div>
  );
};
```

### cURL Examples

```bash
# Get access token
curl -X POST "http://localhost:8000/v1.0/auth/token" \
  -H "Content-Type: application/x-www-form-urlencoded" \
  -d "username=admin&password=your_password"

# Get dashboard stats
curl -X GET "http://localhost:8000/v1.0/dashboard/stats" \
  -H "Authorization: Bearer YOUR_ACCESS_TOKEN"

# Get user activity (last 7 days)
curl -X GET "http://localhost:8000/v1.0/dashboard/user-activity?days=7" \
  -H "Authorization: Bearer YOUR_ACCESS_TOKEN"

# Get points summary
curl -X GET "http://localhost:8000/v1.0/dashboard/points-summary" \
  -H "Authorization: Bearer YOUR_ACCESS_TOKEN"
```

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
  "detail": "Access denied. Only admin and super admin users can access dashboard."
}
```

### 422 Validation Error

```json
{
  "detail": [
    {
      "loc": ["query", "days"],
      "msg": "ensure this value is greater than 0",
      "type": "value_error.number.not_gt"
    }
  ]
}
```

## Security Notes

- All endpoints require valid authentication tokens
- Only users with `admin_user` or `super_user` roles can access dashboard data
- Sensitive user information (like passwords) is never exposed in responses
- All requests are logged for audit purposes

## Performance Considerations

- Dashboard queries are optimized with proper database indexing
- Consider implementing caching for frequently accessed statistics
- Large datasets may benefit from pagination in future versions
- Activity data is limited to prevent excessive memory usage

## Future Enhancements

- Real-time dashboard updates via WebSocket
- Exportable reports (CSV, PDF)
- Custom date range filtering
- Advanced analytics and charts
- Role-based data filtering
