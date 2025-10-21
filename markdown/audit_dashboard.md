# Audit Dashboard Documentation

## Overview

The Audit Dashboard provides comprehensive monitoring and tracking capabilities for the ITT Hotel API (HITA). It offers detailed insights into user activities, security events, and system operations through a robust audit logging system.

## Architecture

### Core Components

- **Audit Dashboard Router**: `/v1.0/audit` prefix
- **Audit Logger**: Comprehensive activity tracking system
- **Session Manager**: User session monitoring and management
- **Security Event Tracking**: Real-time security monitoring
- **Activity Analytics**: Statistical analysis and reporting

### Security Levels

```python
class SecurityLevel(str, Enum):
    LOW = "low"           # Regular activities
    MEDIUM = "medium"     # Important operations
    HIGH = "high"         # Security-sensitive actions
    CRITICAL = "critical" # Critical security events
```

## Activity Types

### Authentication Activities

- `LOGIN_SUCCESS` - Successful user login
- `LOGIN_FAILED` - Failed login attempt
- `LOGOUT` - User logout
- `PASSWORD_RESET_REQUEST` - Password reset requested
- `PASSWORD_RESET_SUCCESS` - Password successfully reset
- `PASSWORD_CHANGE` - Password changed

### User Management Activities

- `USER_CREATED` - New user account created
- `USER_UPDATED` - User account modified
- `USER_DELETED` - User account deleted
- `USER_ACTIVATED` - User account activated
- `USER_DEACTIVATED` - User account deactivated
- `USER_ROLE_CHANGED` - User role modified

### Point Management Activities

- `POINTS_GIVEN` - Points awarded to user
- `POINTS_USED` - Points consumed by user
- `POINTS_RESET` - Points balance reset
- `POINTS_TRANSFERRED` - Points transferred between users

### Security Events

- `UNAUTHORIZED_ACCESS_ATTEMPT` - Unauthorized access attempt
- `RATE_LIMIT_EXCEEDED` - Rate limit violations
- `SUSPICIOUS_ACTIVITY` - Suspicious behavior detected
- `ACCOUNT_LOCKED` - Account locked due to security
- `ACCOUNT_UNLOCKED` - Account unlocked

### System Activities

- `BULK_OPERATION` - Bulk data operations
- `DATA_EXPORT` - Data export operations
- `SYSTEM_CONFIGURATION_CHANGE` - System settings modified
- `API_ACCESS` - API endpoint access
- `API_ERROR` - API errors
- `SEARCH_PERFORMED` - Search operations

## Dashboard Endpoints

### Personal Activity Tracking

#### Get My Activity

```http
GET /v1.0/audit/my-activity?days=30&limit=50
Authorization: Bearer <token>
```

**Parameters:**

- `days` (optional): Number of days to look back (default: 30)
- `limit` (optional): Maximum number of records (default: 50)

**Response:**

```json
{
  "user_id": "5779356081",
  "username": "roman",
  "period_days": 30,
  "total_activities": 25,
  "activities": [
    {
      "id": "12345",
      "action": "login_success",
      "details": {
        "security_level": "low",
        "success": true,
        "timestamp": "2024-12-17T10:30:00Z"
      },
      "ip_address": "192.168.1.100",
      "created_at": "2024-12-17T10:30:00Z"
    }
  ]
}
```

#### Get Activity Summary

```http
GET /v1.0/audit/activity-summary?days=30
Authorization: Bearer <token>
```

**Response:**

```json
{
  "period_days": 30,
  "total_activities": 150,
  "security_events": 3,
  "activity_by_type": {
    "login_success": 45,
    "api_access": 89,
    "search_performed": 16
  },
  "daily_activity": [
    {
      "date": "2024-12-17",
      "count": 12
    }
  ]
}
```

### Administrative Monitoring

#### Get Security Events (Admin Only)

```http
GET /v1.0/audit/security-events?days=7&security_level=high&limit=100
Authorization: Bearer <admin_token>
```

**Parameters:**

- `days` (optional): Number of days to look back (default: 7)
- `security_level` (optional): Filter by security level
- `limit` (optional): Maximum number of records (default: 100)

**Response:**

```json
{
  "period_days": 7,
  "security_level_filter": "high",
  "total_events": 5,
  "events": [
    {
      "id": "67890",
      "action": "unauthorized_access_attempt",
      "user_id": null,
      "details": {
        "security_event": true,
        "requires_investigation": true,
        "failure_reason": "Invalid API key"
      },
      "ip_address": "203.0.113.45",
      "user_agent": "curl/7.68.0",
      "created_at": "2024-12-17T14:22:00Z"
    }
  ]
}
```

#### Get System Activity Summary (Admin Only)

```http
GET /v1.0/audit/system-summary?days=30
Authorization: Bearer <admin_token>
```

**Response:**

```json
{
  "period_days": 30,
  "total_activities": 2450,
  "security_events": 15,
  "activity_by_type": {
    "login_success": 234,
    "api_access": 1890,
    "user_created": 12,
    "search_performed": 314
  },
  "daily_activity": [
    {
      "date": "2024-12-17",
      "count": 89
    }
  ]
}
```

#### Get User Activity (Admin Only)

```http
GET /v1.0/audit/user/5779356081/activity?days=30&activity_types=login_success,logout&limit=100
Authorization: Bearer <admin_token>
```

**Parameters:**

- `user_id` (path): Target user ID
- `days` (optional): Number of days to look back (default: 30)
- `activity_types` (optional): Filter by specific activity types
- `limit` (optional): Maximum number of records (default: 100)

### Utility Endpoints

#### Get Available Activity Types

```http
GET /v1.0/audit/activity-types
```

**Response:**

```json
{
  "activity_types": [
    "login_success",
    "login_failed",
    "logout",
    "user_created",
    "user_updated",
    "points_given",
    "unauthorized_access_attempt"
  ],
  "security_levels": ["low", "medium", "high", "critical"]
}
```

## Audit Logging Features

### Comprehensive Activity Tracking

- **User Actions**: All user-initiated activities
- **System Events**: Automated system operations
- **Security Events**: Security-related incidents
- **API Access**: Endpoint usage tracking
- **Data Changes**: Modification tracking

### Security Monitoring

- **Failed Login Attempts**: Brute force detection
- **Unauthorized Access**: Invalid token/API key usage
- **Rate Limiting**: Abuse prevention
- **Suspicious Patterns**: Anomaly detection
- **Account Security**: Lock/unlock events

### Data Integrity

- **Immutable Logs**: Audit entries cannot be modified
- **Comprehensive Details**: Full context capture
- **IP Address Tracking**: Request origin monitoring
- **User Agent Logging**: Client identification
- **Timestamp Precision**: Exact timing information

## Session Management

### Session Tracking

```python
class SessionManager:
    def create_session(user_id, session_id, request, expires_at)
    def update_session_activity(session_id)
    def end_session(session_id, user_id, request)
    def cleanup_expired_sessions()
    def get_active_sessions(user_id)
    def revoke_all_sessions(user_id, except_session_id)
```

### Session Features

- **Active Session Monitoring**: Real-time session tracking
- **Automatic Cleanup**: Expired session removal
- **Multi-Device Support**: Multiple concurrent sessions
- **Session Revocation**: Force logout capabilities
- **Activity Updates**: Last activity timestamps

## Data Models

### User Activity Log

```python
class UserActivityLog:
    id: str                    # Unique log entry ID
    user_id: Optional[str]     # Acting user ID
    action: str               # Activity type
    details: Dict[str, Any]   # Activity details (JSON)
    ip_address: Optional[str] # Request IP address
    user_agent: Optional[str] # Client user agent
    created_at: datetime      # Timestamp
```

### User Session

```python
class UserSession:
    id: str              # Session ID
    user_id: str         # User ID
    created_at: datetime # Session start time
    last_activity: datetime # Last activity time
    expires_at: datetime # Session expiration
    is_active: bool      # Session status
```

## Security Features

### IP Address Validation

- **Proxy Support**: X-Forwarded-For header handling
- **Load Balancer Support**: X-Real-IP header processing
- **Validation**: IP address format verification
- **Privacy**: Sensitive data redaction

### Data Sanitization

- **Password Redaction**: Automatic password hiding
- **User Agent Sanitization**: Malicious content removal
- **Input Validation**: Safe data storage
- **JSON Serialization**: Structured data storage

### Access Control

- **Role-Based Access**: Different access levels
- **Personal Data**: Users can view own activities
- **Administrative Access**: Admins can view all activities
- **Security Events**: Admin-only security monitoring

## Analytics and Reporting

### Activity Statistics

- **Daily Activity Counts**: Trend analysis
- **Activity Type Distribution**: Usage patterns
- **Security Event Tracking**: Threat monitoring
- **User Behavior Analysis**: Pattern recognition

### Time-Based Analysis

- **Configurable Periods**: Flexible time ranges
- **Historical Data**: Long-term trend analysis
- **Real-Time Monitoring**: Current activity tracking
- **Comparative Analysis**: Period-over-period comparison

## Implementation Details

### Audit Logger Usage

```python
# Initialize audit logger
audit_logger = AuditLogger(db)

# Log authentication event
audit_logger.log_authentication_event(
    activity_type=ActivityType.LOGIN_SUCCESS,
    user_id=user.id,
    email=user.email,
    request=request,
    success=True
)

# Log user management event
audit_logger.log_user_management_event(
    activity_type=ActivityType.USER_CREATED,
    acting_user_id=admin.id,
    target_user_id=new_user.id,
    changes={"role": "general_user"},
    request=request
)

# Log security event
audit_logger.log_security_event(
    activity_type=ActivityType.UNAUTHORIZED_ACCESS_ATTEMPT,
    user_id=None,
    request=request,
    details={"reason": "Invalid API key"},
    security_level=SecurityLevel.HIGH
)
```

### Middleware Integration

```python
# Automatic audit logging middleware
audit_middleware = create_audit_middleware()
app.add_middleware(audit_middleware)
```

## Best Practices

### Logging Strategy

1. **Log All Security Events**: Never miss security incidents
2. **Sanitize Sensitive Data**: Protect user privacy
3. **Use Appropriate Security Levels**: Proper event classification
4. **Include Context**: Comprehensive event details
5. **Monitor Performance**: Efficient logging operations

### Data Retention

1. **Regular Cleanup**: Remove old audit logs
2. **Archive Important Events**: Preserve critical data
3. **Compliance Requirements**: Meet regulatory needs
4. **Storage Optimization**: Efficient data storage

### Security Monitoring

1. **Real-Time Alerts**: Immediate threat notification
2. **Pattern Recognition**: Identify suspicious behavior
3. **Automated Response**: Trigger security measures
4. **Investigation Support**: Detailed forensic data

## Error Handling

### Common Scenarios

- **Database Failures**: Graceful degradation
- **Invalid Parameters**: Input validation
- **Permission Denied**: Access control enforcement
- **Rate Limiting**: Abuse prevention

### Error Responses

```json
{
  "detail": "Access denied. Admin privileges required."
}
```

```json
{
  "detail": "Invalid activity type specified."
}
```

## Monitoring and Alerts

### Key Metrics

- **Failed Login Attempts**: Security monitoring
- **API Error Rates**: System health
- **User Activity Patterns**: Behavior analysis
- **Security Event Frequency**: Threat assessment

### Alert Conditions

- **Multiple Failed Logins**: Brute force attempts
- **Unusual Activity Patterns**: Anomaly detection
- **Critical Security Events**: Immediate attention required
- **System Performance Issues**: Operational monitoring

## Integration

### External Systems

- **SIEM Integration**: Security information systems
- **Log Aggregation**: Centralized logging
- **Monitoring Tools**: System monitoring
- **Alerting Systems**: Notification services

### API Integration

- **Webhook Support**: Real-time notifications
- **Export Capabilities**: Data extraction
- **Query APIs**: Programmatic access
- **Reporting Tools**: Dashboard integration
