"""
Security Module for User Management

This module provides comprehensive security features including:
- Advanced input validation and sanitization
- Rate limiting for sensitive operations
- Comprehensive audit logging and activity tracking
- Security middleware and utilities
"""

from .input_validation import (
    SecurityConfig,
    AdvancedPasswordValidator,
    InputSanitizer,
    SecurityValidator,
    generate_secure_password,
    validate_ip_address,
    sanitize_user_agent
)

from .rate_limiting import (
    RateLimitManager,
    rate_limit_manager,
    rate_limit,
    RateLimitMiddleware,
    check_suspicious_activity,
    get_rate_limit_status
)

from .audit_logging import (
    ActivityType,
    SecurityLevel,
    AuditLogger,
    SessionManager,
    create_audit_middleware
)

from .middleware import (
    SecurityMiddleware,
    AuthenticationMiddleware,
    create_security_middleware_stack,
    validate_user_permissions,
    log_user_action,
    check_rate_limit_manual
)

__all__ = [
    # Input validation
    'SecurityConfig',
    'AdvancedPasswordValidator',
    'InputSanitizer',
    'SecurityValidator',
    'generate_secure_password',
    'validate_ip_address',
    'sanitize_user_agent',
    
    # Rate limiting
    'RateLimitManager',
    'rate_limit_manager',
    'rate_limit',
    'RateLimitMiddleware',
    'check_suspicious_activity',
    'get_rate_limit_status',
    
    # Audit logging
    'ActivityType',
    'SecurityLevel',
    'AuditLogger',
    'SessionManager',
    'create_audit_middleware',
    
    # Middleware
    'SecurityMiddleware',
    'AuthenticationMiddleware',
    'create_security_middleware_stack',
    'validate_user_permissions',
    'log_user_action',
    'check_rate_limit_manual'
]