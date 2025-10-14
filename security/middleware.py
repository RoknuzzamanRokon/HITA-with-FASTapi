"""
Security Middleware for User Management

This module provides comprehensive security middleware that integrates
input validation, rate limiting, and audit logging.
"""

import time
import json
from typing import Optional, Dict, Any
from fastapi import Request, HTTPException, status
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware
from sqlalchemy.orm import Session
from database import get_db
from security.input_validation import SecurityValidator, InputSanitizer
from security.rate_limiting import RateLimitManager, rate_limit_manager
from security.audit_logging import AuditLogger, ActivityType, SecurityLevel
import logging

logger = logging.getLogger(__name__)


class SecurityMiddleware(BaseHTTPMiddleware):
    """Comprehensive security middleware"""
    
    def __init__(self, app, enable_rate_limiting: bool = True, enable_audit_logging: bool = True):
        super().__init__(app)
        self.enable_rate_limiting = enable_rate_limiting
        self.enable_audit_logging = enable_audit_logging
        self.security_validator = SecurityValidator()
        self.input_sanitizer = InputSanitizer()
        
        # Endpoints that require special security handling
        self.sensitive_endpoints = {
            '/v1.0/user/create_super_user': 'user_creation',
            '/v1.0/user/create_admin_user': 'user_creation',
            '/v1.0/user/create_general_user': 'user_creation',
            '/v1.0/auth/login': 'login_attempt',
            '/v1.0/auth/reset-password': 'password_reset',
            '/v1.0/user/bulk': 'bulk_operations'
        }
        
        # Endpoints that should be logged
        self.logged_endpoints = [
            '/v1.0/user/',
            '/v1.0/auth/',
            '/v1.0/admin/'
        ]
    
    async def dispatch(self, request: Request, call_next):
        """Main middleware dispatch method"""
        start_time = time.time()
        
        # Get database session
        db = next(get_db())
        
        try:
            # Initialize audit logger
            audit_logger = AuditLogger(db) if self.enable_audit_logging else None
            
            # Check for blocked IPs or suspicious activity
            if await self._check_security_blocks(request, audit_logger):
                return JSONResponse(
                    status_code=status.HTTP_403_FORBIDDEN,
                    content={
                        "error": True,
                        "message": "Access denied due to security policy",
                        "error_code": "ACCESS_DENIED"
                    }
                )
            
            # Apply rate limiting for sensitive endpoints
            if self.enable_rate_limiting:
                rate_limit_response = await self._apply_rate_limiting(request, audit_logger)
                if rate_limit_response:
                    return rate_limit_response
            
            # Validate and sanitize request data
            await self._validate_request_data(request)
            
            # Process the request
            response = await call_next(request)
            
            # Log successful API access
            if audit_logger and self._should_log_endpoint(request.url.path):
                await self._log_api_access(request, response, audit_logger, time.time() - start_time)
            
            # Add security headers
            self._add_security_headers(response)
            
            return response
            
        except HTTPException as e:
            # Log security-related HTTP exceptions
            if audit_logger and e.status_code in [401, 403, 429]:
                await self._log_security_event(request, e, audit_logger)
            raise e
            
        except Exception as e:
            # Log unexpected errors
            if audit_logger:
                audit_logger.log_activity(
                    activity_type=ActivityType.API_ERROR,
                    details={
                        'error': str(e),
                        'endpoint': request.url.path,
                        'method': request.method
                    },
                    request=request,
                    security_level=SecurityLevel.HIGH,
                    success=False
                )
            
            logger.error(f"Security middleware error: {e}")
            raise e
            
        finally:
            db.close()
    
    async def _check_security_blocks(self, request: Request, audit_logger: Optional[AuditLogger]) -> bool:
        """Check for security blocks and suspicious activity"""
        client_ip = self._get_client_ip(request)
        
        # Check for blocked IPs (this would typically be stored in database or cache)
        # For now, we'll implement basic checks
        
        # Check for suspicious user agents
        user_agent = request.headers.get('user-agent', '').lower()
        suspicious_agents = ['bot', 'crawler', 'scanner', 'hack', 'exploit']
        
        if any(agent in user_agent for agent in suspicious_agents):
            if audit_logger:
                audit_logger.log_security_event(
                    activity_type=ActivityType.SUSPICIOUS_ACTIVITY,
                    user_id=None,
                    request=request,
                    details={'reason': 'suspicious_user_agent', 'user_agent': user_agent},
                    security_level=SecurityLevel.MEDIUM
                )
            return True
        
        # Check for malicious request patterns
        if self._detect_malicious_patterns(request):
            if audit_logger:
                audit_logger.log_security_event(
                    activity_type=ActivityType.SUSPICIOUS_ACTIVITY,
                    user_id=None,
                    request=request,
                    details={'reason': 'malicious_patterns'},
                    security_level=SecurityLevel.HIGH
                )
            return True
        
        return False
    
    async def _apply_rate_limiting(self, request: Request, audit_logger: Optional[AuditLogger]) -> Optional[JSONResponse]:
        """Apply rate limiting to sensitive endpoints"""
        endpoint = request.url.path
        operation = self.sensitive_endpoints.get(endpoint)
        
        if not operation:
            return None
        
        # Get client identifier
        identifier = rate_limit_manager.get_client_identifier(request)
        
        # Check rate limit
        is_allowed, rate_info = rate_limit_manager.check_rate_limit(operation, identifier)
        
        if not is_allowed:
            # Log rate limit violation
            if audit_logger:
                audit_logger.log_security_event(
                    activity_type=ActivityType.RATE_LIMIT_EXCEEDED,
                    user_id=None,
                    request=request,
                    details={
                        'operation': operation,
                        'rate_limit_info': rate_info
                    },
                    security_level=SecurityLevel.MEDIUM
                )
            
            return JSONResponse(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                content={
                    "error": True,
                    "message": f"Rate limit exceeded for {operation}",
                    "error_code": "RATE_LIMIT_EXCEEDED",
                    "rate_limit_info": rate_info
                },
                headers={
                    "X-RateLimit-Limit": str(rate_info.get('limit', 0)),
                    "X-RateLimit-Remaining": str(rate_info.get('remaining', 0)),
                    "X-RateLimit-Reset": str(rate_info.get('reset_time', 0)),
                    "Retry-After": str(rate_info.get('retry_after', 300))
                }
            )
        
        return None
    
    async def _validate_request_data(self, request: Request):
        """Validate and sanitize request data"""
        # Only validate POST/PUT/PATCH requests with JSON data
        if request.method not in ['POST', 'PUT', 'PATCH']:
            return
        
        content_type = request.headers.get('content-type', '')
        if 'application/json' not in content_type:
            return
        
        try:
            # Get request body
            body = await request.body()
            if not body:
                return
            
            # Parse JSON
            try:
                data = json.loads(body)
            except json.JSONDecodeError:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail={
                        "error": True,
                        "message": "Invalid JSON format",
                        "error_code": "INVALID_JSON"
                    }
                )
            
            # Validate based on endpoint
            endpoint = request.url.path
            if any(endpoint.startswith(prefix) for prefix in ['/v1.0/user/create', '/v1.0/user/update']):
                validation_result = self.security_validator.validate_user_creation_data(data)
                
                if not validation_result['is_valid']:
                    raise HTTPException(
                        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                        detail={
                            "error": True,
                            "message": "Validation failed",
                            "error_code": "VALIDATION_ERROR",
                            "field_errors": validation_result['errors'],
                            "warnings": validation_result.get('warnings', [])
                        }
                    )
                
                # Replace request data with sanitized version
                # Note: This is a simplified approach. In practice, you might want to
                # store sanitized data in request state for the endpoint to use
                
        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"Request validation error: {e}")
            # Don't block the request for validation errors, just log them
    
    async def _log_api_access(self, request: Request, response, audit_logger: AuditLogger, duration: float):
        """Log API access"""
        # Extract user ID if available (this would typically come from JWT token)
        user_id = getattr(request.state, 'user_id', None)
        
        audit_logger.log_activity(
            activity_type=ActivityType.API_ACCESS,
            user_id=user_id,
            details={
                'endpoint': request.url.path,
                'method': request.method,
                'status_code': response.status_code,
                'duration_ms': round(duration * 1000, 2),
                'query_params': dict(request.query_params) if request.query_params else None
            },
            request=request,
            security_level=SecurityLevel.LOW,
            success=response.status_code < 400
        )
    
    async def _log_security_event(self, request: Request, exception: HTTPException, audit_logger: AuditLogger):
        """Log security-related events"""
        activity_type = ActivityType.UNAUTHORIZED_ACCESS_ATTEMPT
        
        if exception.status_code == 429:
            activity_type = ActivityType.RATE_LIMIT_EXCEEDED
        elif exception.status_code == 401:
            activity_type = ActivityType.UNAUTHORIZED_ACCESS_ATTEMPT
        elif exception.status_code == 403:
            activity_type = ActivityType.UNAUTHORIZED_ACCESS_ATTEMPT
        
        audit_logger.log_security_event(
            activity_type=activity_type,
            user_id=getattr(request.state, 'user_id', None),
            request=request,
            details={
                'status_code': exception.status_code,
                'detail': str(exception.detail),
                'endpoint': request.url.path,
                'method': request.method
            },
            security_level=SecurityLevel.HIGH
        )
    
    def _should_log_endpoint(self, path: str) -> bool:
        """Check if endpoint should be logged"""
        return any(path.startswith(prefix) for prefix in self.logged_endpoints)
    
    def _detect_malicious_patterns(self, request: Request) -> bool:
        """Detect malicious request patterns"""
        # Check URL for SQL injection patterns
        url_path = request.url.path.lower()
        query_string = str(request.query_params).lower()
        
        malicious_patterns = [
            'union select', 'drop table', 'insert into', 'delete from',
            '<script', 'javascript:', 'onload=', 'onerror=',
            '../', '..\\', '/etc/passwd', '/proc/self',
            'cmd.exe', 'powershell', '/bin/bash'
        ]
        
        full_url = f"{url_path}?{query_string}"
        return any(pattern in full_url for pattern in malicious_patterns)
    
    def _get_client_ip(self, request: Request) -> str:
        """Extract client IP address"""
        # Check for forwarded headers
        forwarded_for = request.headers.get('X-Forwarded-For')
        if forwarded_for:
            return forwarded_for.split(',')[0].strip()
        
        real_ip = request.headers.get('X-Real-IP')
        if real_ip:
            return real_ip
        
        return request.client.host if request.client else 'unknown'
    
    def _add_security_headers(self, response):
        """Add security headers to response"""
        security_headers = {
            'X-Content-Type-Options': 'nosniff',
            'X-Frame-Options': 'DENY',
            'X-XSS-Protection': '1; mode=block',
            'Strict-Transport-Security': 'max-age=31536000; includeSubDomains',
            'Referrer-Policy': 'strict-origin-when-cross-origin',
            'Content-Security-Policy': "default-src 'self'; script-src 'self'; style-src 'self' 'unsafe-inline';"
        }
        
        for header, value in security_headers.items():
            response.headers[header] = value


class AuthenticationMiddleware(BaseHTTPMiddleware):
    """Authentication middleware for extracting user information"""
    
    def __init__(self, app):
        super().__init__(app)
    
    async def dispatch(self, request: Request, call_next):
        """Extract user information from JWT token"""
        # This is a simplified implementation
        # In practice, you would decode JWT tokens and extract user information
        
        authorization = request.headers.get('Authorization')
        if authorization and authorization.startswith('Bearer '):
            token = authorization.split(' ')[1]
            # Decode token and extract user_id
            # For now, we'll just set a placeholder
            request.state.user_id = None  # Would be extracted from token
        
        response = await call_next(request)
        return response


def create_security_middleware_stack(app):
    """Create the complete security middleware stack"""
    # Add middlewares in reverse order (they wrap around each other)
    app.add_middleware(SecurityMiddleware, enable_rate_limiting=True, enable_audit_logging=True)
    app.add_middleware(AuthenticationMiddleware)
    
    return app


# Utility functions for manual security checks

def validate_user_permissions(current_user, required_roles: list, target_user=None):
    """Validate user permissions for operations"""
    if not current_user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication required"
        )
    
    if current_user.role not in required_roles:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"Insufficient permissions. Required roles: {required_roles}"
        )
    
    # Additional checks for user management operations
    if target_user and current_user.role == 'admin_user':
        # Admin users can only manage users they created
        if target_user.created_by != f"admin_user: {current_user.email}":
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Admin users can only manage users they created"
            )


def log_user_action(db: Session, user_id: str, action: str, details: dict, request: Request):
    """Manually log user actions"""
    audit_logger = AuditLogger(db)
    
    # Map action strings to ActivityType enum
    action_mapping = {
        'create_user': ActivityType.USER_CREATED,
        'update_user': ActivityType.USER_UPDATED,
        'delete_user': ActivityType.USER_DELETED,
        'give_points': ActivityType.POINTS_GIVEN,
        'reset_points': ActivityType.POINTS_RESET
    }
    
    activity_type = action_mapping.get(action, ActivityType.API_ACCESS)
    
    audit_logger.log_activity(
        activity_type=activity_type,
        user_id=user_id,
        details=details,
        request=request,
        security_level=SecurityLevel.MEDIUM
    )


def check_rate_limit_manual(request: Request, operation: str, user_id: Optional[str] = None):
    """Manually check rate limits"""
    identifier = rate_limit_manager.get_client_identifier(request, user_id)
    is_allowed, rate_info = rate_limit_manager.check_rate_limit(operation, identifier)
    
    if not is_allowed:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail={
                "error": True,
                "message": f"Rate limit exceeded for {operation}",
                "error_code": "RATE_LIMIT_EXCEEDED",
                "rate_limit_info": rate_info
            }
        )
    
    return rate_info