# Enhanced Security Features for User Management

This document describes the comprehensive security enhancements implemented for the user management system, including advanced input validation, rate limiting, and audit logging.

## Overview

The security module provides:

1. **Advanced Input Validation and Sanitization**

   - Enhanced password strength validation
   - Comprehensive input sanitization
   - SQL injection and XSS protection

2. **Rate Limiting**

   - Configurable rate limits for sensitive operations
   - IP-based and user-based limiting
   - Automatic blocking for repeated violations

3. **Comprehensive Audit Logging**

   - Activity tracking for all user operations
   - Security event logging
   - Session management and tracking

4. **Security Middleware**
   - Automatic security checks
   - Request/response monitoring
   - Security header injection

## Installation and Setup

### 1. Database Migration

First, run the database migration to create the necessary security tables:

```bash
cd backend
python migrations/add_security_tables.py
```

This will create:

- `user_activity_logs` - For audit logging
- `user_sessions` - For session management
- `blacklisted_tokens` - For token revocation

### 2. Install Dependencies

Ensure you have the required dependencies:

```bash
pip install bleach email-validator redis
```

### 3. Configure Redis (Optional)

For production environments, configure Redis for rate limiting:

```python
import redis
from security.rate_limiting import RateLimitManager

redis_client = redis.Redis(host='localhost', port=6379, db=0)
rate_limit_manager = RateLimitManager(redis_client)
```

### 4. Add Security Middleware

Add the security middleware to your FastAPI application:

```python
from fastapi import FastAPI
from security.middleware import create_security_middleware_stack

app = FastAPI()
app = create_security_middleware_stack(app)
```

## Usage Examples

### Input Validation and Sanitization

```python
from security import SecurityValidator, InputSanitizer

# Initialize components
validator = SecurityValidator()
sanitizer = InputSanitizer()

# Validate user creation data
user_data = {
    'username': 'john_doe',
    'email': 'john@example.com',
    'password': 'SecurePass123!'
}

result = validator.validate_user_creation_data(user_data)
if result['is_valid']:
    sanitized_data = result['sanitized_data']
    # Use sanitized_data for user creation
else:
    # Handle validation errors
    errors = result['errors']
```

### Rate Limiting

#### Using Decorators

```python
from security import rate_limit

@router.post("/create_user")
@rate_limit("user_creation", use_user_id=True)
async def create_user(request: Request, ...):
    # Your endpoint logic here
    pass
```

#### Manual Rate Limiting

```python
from security import check_rate_limit_manual

@router.post("/sensitive_operation")
async def sensitive_operation(request: Request, current_user: User, ...):
    # Check rate limit manually
    check_rate_limit_manual(request, "sensitive_operation", current_user.id)

    # Your operation logic here
    pass
```

### Audit Logging

```python
from security import AuditLogger, ActivityType, SecurityLevel

# Initialize audit logger
audit_logger = AuditLogger(db)

# Log user activity
audit_logger.log_activity(
    activity_type=ActivityType.USER_CREATED,
    user_id=current_user.id,
    target_user_id=new_user.id,
    details={'username': new_user.username},
    request=request,
    security_level=SecurityLevel.MEDIUM
)

# Log security events
audit_logger.log_security_event(
    activity_type=ActivityType.UNAUTHORIZED_ACCESS_ATTEMPT,
    user_id=None,
    request=request,
    details={'reason': 'invalid_token'},
    security_level=SecurityLevel.HIGH
)
```

### Session Management

```python
from security import SessionManager

session_manager = SessionManager(db)

# Create session
session = session_manager.create_session(
    user_id=user.id,
    session_id=token,
    request=request,
    expires_at=datetime.utcnow() + timedelta(hours=24)
)

# Update session activity
session_manager.update_session_activity(session_id)

# End session
session_manager.end_session(session_id, user.id, request)
```

## Configuration

### Security Configuration

Modify `SecurityConfig` in `security/input_validation.py`:

```python
class SecurityConfig:
    # Password requirements
    MIN_PASSWORD_LENGTH = 12
    REQUIRE_SPECIAL_CHARS = True
    MIN_SPECIAL_CHARS = 2

    # Rate limiting (requests per minute)
    USER_CREATION_RATE_LIMIT = 5
    LOGIN_ATTEMPT_RATE_LIMIT = 10

    # Blocked email domains
    BLOCKED_EMAIL_DOMAINS = [
        'tempmail.com',
        '10minutemail.com'
    ]
```

### Rate Limit Configuration

Modify rate limits in `security/rate_limiting.py`:

```python
self.limits = {
    'user_creation': {'limit': 5, 'window': 300},      # 5 per 5 minutes
    'password_reset': {'limit': 3, 'window': 300},     # 3 per 5 minutes
    'login_attempt': {'limit': 10, 'window': 300},     # 10 per 5 minutes
}
```

## Security Features

### Password Validation

The enhanced password validator checks for:

- Minimum length (configurable, default 12 characters)
- Character requirements (uppercase, lowercase, digits, special characters)
- Common password detection
- Keyboard pattern detection
- Sequential character detection
- Password strength scoring

### Input Sanitization

All user inputs are sanitized to prevent:

- SQL injection attacks
- Cross-site scripting (XSS)
- HTML injection
- Control character injection
- Path traversal attacks

### Rate Limiting

Rate limiting is applied to:

- User creation operations
- Password reset requests
- Login attempts
- Bulk operations
- Search queries

### Audit Logging

All activities are logged including:

- User management operations (create, update, delete)
- Authentication events (login, logout, failed attempts)
- Point transactions
- Permission changes
- Security events
- API access

## Monitoring and Alerts

### Security Event Monitoring

```python
# Get security events from the last 7 days
security_events = audit_logger.get_security_events(days=7)

# Get activity summary
summary = audit_logger.get_activity_summary(days=30)
```

### Rate Limit Monitoring

```python
# Check rate limit status
from security import get_rate_limit_status

status = get_rate_limit_status("user_creation", "ip:192.168.1.1")
```

## Best Practices

### 1. Always Use Validation

```python
# Good
validation_result = validator.validate_user_creation_data(data)
if validation_result['is_valid']:
    # Process with sanitized data
    process_user(validation_result['sanitized_data'])

# Bad
# Process raw user input directly
process_user(raw_data)
```

### 2. Log Security-Relevant Actions

```python
# Log all user management operations
audit_logger.log_activity(
    activity_type=ActivityType.USER_UPDATED,
    user_id=current_user.id,
    target_user_id=target_user.id,
    details={'changes': changes},
    request=request
)
```

### 3. Apply Rate Limiting to Sensitive Endpoints

```python
@rate_limit("sensitive_operation")
async def sensitive_endpoint(...):
    pass
```

### 4. Validate Permissions

```python
validate_user_permissions(
    current_user,
    [UserRole.SUPER_USER, UserRole.ADMIN_USER],
    target_user
)
```

## Troubleshooting

### Common Issues

1. **Rate Limit Errors**

   - Check if Redis is running (for production)
   - Verify rate limit configuration
   - Check client IP extraction

2. **Validation Errors**

   - Review password requirements
   - Check email domain restrictions
   - Verify input sanitization rules

3. **Audit Log Issues**
   - Ensure database tables exist
   - Check database permissions
   - Verify foreign key constraints

### Debug Mode

Enable debug logging:

```python
import logging
logging.getLogger("audit").setLevel(logging.DEBUG)
logging.getLogger("security").setLevel(logging.DEBUG)
```

## Security Considerations

1. **Database Security**

   - Use parameterized queries
   - Implement proper access controls
   - Regular security updates

2. **Network Security**

   - Use HTTPS in production
   - Implement proper firewall rules
   - Monitor network traffic

3. **Application Security**

   - Regular security audits
   - Dependency vulnerability scanning
   - Secure configuration management

4. **Monitoring**
   - Set up alerts for security events
   - Regular log analysis
   - Anomaly detection

## Performance Considerations

1. **Rate Limiting**

   - Use Redis for production environments
   - Monitor memory usage
   - Configure appropriate cleanup intervals

2. **Audit Logging**

   - Implement log rotation
   - Consider archiving old logs
   - Monitor database growth

3. **Input Validation**
   - Cache validation results where appropriate
   - Optimize regex patterns
   - Consider async validation for heavy operations

## Migration from Legacy System

To migrate from the existing system:

1. Run the database migration
2. Update existing endpoints to use new security features
3. Configure rate limiting
4. Set up monitoring and alerting
5. Test thoroughly in staging environment

## Support

For questions or issues:

1. Check the troubleshooting section
2. Review the audit logs for security events
3. Monitor rate limiting metrics
4. Consult the security configuration
