# Dashboard Documentation

## Overview

The Dashboard system provides comprehensive analytics and statistics for administrators and super users of the ITT Hotel API (HITA). It offers real-time insights into user activity, point distribution, transaction patterns, and system usage through a robust set of analytical endpoints.

## Architecture

### Core Components

- **Dashboard Router**: `/v1.0/dashboard` prefix
- **Statistics Engine**: Real-time data aggregation
- **Role-Based Access**: Admin and super user only access
- **Error Resilience**: Graceful handling of missing tables
- **Multi-Dimensional Analytics**: User, activity, and points analysis

### Security Model

- **Super User**: Full access to all dashboard statistics
- **Admin User**: Full access to all dashboard statistics
- **General User**: No access to dashboard endpoints

### Route Prefix

```
/v1.0/dashboard
```

## Dashboard Endpoints

### Get Dashboard Statistics

#### Endpoint

```http
GET /v1.0/dashboard/stats
Authorization: Bearer <admin_token>
```

#### Response

```json
{
  "total_users": 150,
  "active_users": 89,
  "admin_users": 7,
  "general_users": 143,
  "points_distributed": 45000,
  "current_balance": 12500,
  "recent_signups": 8,
  "inactive_users": 61,
  "additional_stats": {
    "super_users": 2,
    "admin_users_only": 5,
    "total_transactions": 1250,
    "recent_activity_count": 456,
    "users_with_api_keys": 25,
    "points_used": 32500
  },
  "timestamp": "2024-12-17T15:30:00Z",
  "requested_by": {
    "user_id": "admin_001",
    "username": "admin_user",
    "role": "admin_user"
  }
}
```

#### Key Metrics Explained

- **total_users**: Total registered users in the system
- **active_users**: Users with activity in the last 7 days
- **admin_users**: Combined count of admin and super users
- **general_users**: Regular users with limited permissions
- **points_distributed**: Total points ever distributed
- **current_balance**: Current total points balance across all users
- **recent_signups**: New users registered in the last 30 days
- **inactive_users**: Users with no activity in the last 30 days

### Get User Activity Statistics

#### Endpoint

```http
GET /v1.0/dashboard/user-activity?days=30
Authorization: Bearer <admin_token>
```

#### Parameters

| Parameter | Type | Default | Description               |
| --------- | ---- | ------- | ------------------------- |
| `days`    | int  | 30      | Number of days to analyze |

#### Response

```json
{
  "period_days": 30,
  "daily_activity": [
    {
      "date": "2024-12-17",
      "activity_count": 145,
      "unique_users": 23
    },
    {
      "date": "2024-12-16",
      "activity_count": 132,
      "unique_users": 19
    }
  ],
  "most_active_users": [
    {
      "user_id": "5779356081",
      "username": "john_doe",
      "email": "john@example.com",
      "role": "general_user",
      "activity_count": 45
    },
    {
      "user_id": "admin_001",
      "username": "admin_user",
      "email": "admin@example.com",
      "role": "admin_user",
      "activity_count": 38
    }
  ],
  "timestamp": "2024-12-17T15:30:00Z"
}
```

#### Activity Metrics

- **daily_activity**: Day-by-day activity breakdown
- **activity_count**: Total activities per day
- **unique_users**: Number of unique active users per day
- **most_active_users**: Top 10 users by activity count

### Get Points Summary

#### Endpoint

```http
GET /v1.0/dashboard/points-summary
Authorization: Bearer <admin_token>
```

#### Response

```json
{
  "points_by_role": [
    {
      "role": "super_user",
      "user_count": 2,
      "total_points": 5000,
      "current_points": 4500,
      "avg_points": 2250.0
    },
    {
      "role": "admin_user",
      "user_count": 5,
      "total_points": 15000,
      "current_points": 12000,
      "avg_points": 2400.0
    },
    {
      "role": "general_user",
      "user_count": 143,
      "total_points": 25000,
      "current_points": 8500,
      "avg_points": 59.44
    }
  ],
  "recent_transactions_30d": 234,
  "transaction_types": [
    {
      "type": "transfer",
      "count": 156,
      "total_points": 15600
    },
    {
      "type": "reward",
      "count": 78,
      "total_points": 7800
    },
    {
      "type": "deduction",
      "count": 45,
      "total_points": 2250
    }
  ],
  "top_point_holders": [
    {
      "user_id": "super_001",
      "username": "super_admin",
      "role": "super_user",
      "current_points": 2500,
      "total_points": 3000
    },
    {
      "user_id": "admin_002",
      "username": "admin_manager",
      "role": "admin_user",
      "current_points": 2200,
      "total_points": 2800
    }
  ],
  "timestamp": "2024-12-17T15:30:00Z"
}
```

#### Points Metrics

- **points_by_role**: Point distribution across user roles
- **recent_transactions_30d**: Transaction count in last 30 days
- **transaction_types**: Breakdown by transaction type
- **top_point_holders**: Users with highest current point balances

## Data Analysis Features

### User Statistics

- **Total User Count**: Complete user registration metrics
- **Role Distribution**: Breakdown by user roles (super, admin, general)
- **Activity Tracking**: Active vs inactive user identification
- **Registration Trends**: New user signup patterns
- **API Key Usage**: Users with API key access

### Activity Analytics

- **Daily Activity Patterns**: Day-by-day activity trends
- **User Engagement**: Unique active users per day
- **Activity Volume**: Total activities and interactions
- **Most Active Users**: Top performers by activity count
- **Engagement Trends**: Activity patterns over time

### Points and Transaction Analysis

- **Point Distribution**: Points allocated across user roles
- **Transaction Volume**: Recent transaction activity
- **Transaction Types**: Breakdown by transaction categories
- **Point Utilization**: Used vs available points
- **Top Point Holders**: Users with highest balances

## Error Resilience

### Graceful Degradation

The dashboard system is designed to handle missing database tables gracefully:

```python
# Example error handling for missing tables
try:
    total_points_distributed = db.query(func.sum(models.UserPoint.total_points)).scalar() or 0
    current_balance = db.query(func.sum(models.UserPoint.current_points)).scalar() or 0
except Exception as e:
    print(f"Error fetching points stats (UserPoint may not exist): {e}")
    # Continue with default values
```

### Fallback Behavior

- **Missing UserActivityLog**: Returns empty activity data
- **Missing UserPoint**: Returns zero point statistics
- **Missing PointTransaction**: Returns zero transaction data
- **Database Errors**: Returns partial data with error logging

## Security and Access Control

### Authentication Requirements

- All endpoints require valid JWT tokens
- Role-based access control enforcement
- Admin or super user privileges required

### Permission Validation

```python
def require_admin_or_superuser(current_user: models.User) -> models.User:
    """Check if user is admin or superuser"""
    if current_user.role not in [UserRole.SUPER_USER, UserRole.ADMIN_USER]:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access denied. Only admin and super admin users can access dashboard."
        )
    return current_user
```

### Access Control Features

- **Role Verification**: Explicit role checking on each endpoint
- **Request Tracking**: Log who requested dashboard data
- **Error Handling**: Secure error responses without data leakage

## Performance Considerations

### Database Optimization

- **Efficient Aggregations**: Use database-level aggregation functions
- **Indexed Queries**: Optimized queries for large datasets
- **Date Range Filtering**: Efficient time-based filtering
- **Selective Loading**: Load only required data fields

### Query Patterns

```python
# Efficient user count by role
admin_users = db.query(func.count(models.User.id)).filter(
    models.User.role == UserRole.ADMIN_USER
).scalar() or 0

# Optimized activity aggregation
daily_activity = db.query(
    func.date(models.UserActivityLog.created_at).label('date'),
    func.count(models.UserActivityLog.id).label('activity_count'),
    func.count(func.distinct(models.UserActivityLog.user_id)).label('unique_users')
).filter(
    models.UserActivityLog.created_at >= start_date
).group_by(
    func.date(models.UserActivityLog.created_at)
).all()
```

### Caching Strategy

- **Real-time Data**: No caching for dashboard statistics
- **Expensive Queries**: Consider caching for complex aggregations
- **Refresh Patterns**: Regular data refresh for accuracy

## Error Handling

### Common Error Scenarios

#### Access Denied

```json
{
  "detail": "Access denied. Only admin and super admin users can access dashboard."
}
```

#### Database Error

```json
{
  "detail": "Failed to fetch dashboard statistics: Database connection error"
}
```

#### Missing Data

```json
{
  "detail": "Failed to fetch user activity statistics: UserActivityLog table not found"
}
```

### Error Response Format

```json
{
  "detail": "Error message describing the issue"
}
```

## Integration Examples

### Basic Dashboard Data Retrieval

```python
import requests

# Get dashboard statistics
response = requests.get(
    f"{base_url}/v1.0/dashboard/stats",
    headers={"Authorization": f"Bearer {admin_token}"}
)

dashboard_data = response.json()
print(f"Total Users: {dashboard_data['total_users']}")
print(f"Active Users: {dashboard_data['active_users']}")
```

### Activity Analysis

```python
# Get user activity for last 7 days
response = requests.get(
    f"{base_url}/v1.0/dashboard/user-activity?days=7",
    headers={"Authorization": f"Bearer {admin_token}"}
)

activity_data = response.json()
for day in activity_data['daily_activity']:
    print(f"Date: {day['date']}, Activities: {day['activity_count']}")
```

### Points Analysis

```python
# Get points summary
response = requests.get(
    f"{base_url}/v1.0/dashboard/points-summary",
    headers={"Authorization": f"Bearer {admin_token}"}
)

points_data = response.json()
for role_data in points_data['points_by_role']:
    print(f"Role: {role_data['role']}, Avg Points: {role_data['avg_points']}")
```

## Monitoring and Alerting

### Key Metrics to Monitor

- **User Growth**: Track total_users and recent_signups
- **User Engagement**: Monitor active_users vs total_users ratio
- **System Usage**: Track activity_count and unique_users
- **Point Economy**: Monitor points_distributed vs current_balance
- **Transaction Volume**: Track recent_transactions_30d

### Alert Conditions

- **Low Activity**: Active users below threshold
- **High Inactivity**: Inactive users above threshold
- **Point Imbalance**: Unusual point distribution patterns
- **System Errors**: Database connection or query failures

## Best Practices

### Dashboard Usage

1. **Regular Monitoring**: Check dashboard statistics regularly
2. **Trend Analysis**: Compare metrics over time periods
3. **User Engagement**: Monitor active vs inactive user ratios
4. **Point Management**: Track point distribution and usage
5. **Performance Monitoring**: Watch for system performance issues

### Development Guidelines

1. **Error Handling**: Always handle database errors gracefully
2. **Performance**: Use efficient database queries
3. **Security**: Validate permissions on all endpoints
4. **Logging**: Log errors and important events
5. **Testing**: Test with missing tables and edge cases

### Operational Guidelines

1. **Data Accuracy**: Ensure data consistency across metrics
2. **Performance Tuning**: Optimize slow queries
3. **Capacity Planning**: Monitor database performance
4. **Security Auditing**: Regular access control reviews
5. **Documentation**: Keep metrics documentation updated

## Future Enhancements

### Potential Improvements

- **Real-time Updates**: WebSocket-based live dashboard updates
- **Custom Date Ranges**: Flexible date range selection
- **Export Functionality**: CSV/PDF export of dashboard data
- **Visualization**: Built-in charts and graphs
- **Alerting System**: Automated alerts for threshold breaches

### Advanced Analytics

- **Predictive Analytics**: User behavior prediction
- **Cohort Analysis**: User retention and engagement analysis
- **Geographic Analytics**: Location-based user statistics
- **Performance Metrics**: API usage and response time analytics
- **Business Intelligence**: Advanced reporting and insights
