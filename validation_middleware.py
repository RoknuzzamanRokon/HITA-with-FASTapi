"""
Validation Middleware for FastAPI

This module provides middleware and dependency injection functions for
comprehensive request validation and sanitization in FastAPI applications.
"""

from fastapi import Request, HTTPException, status, Depends
from fastapi.responses import JSONResponse
from typing import Optional, Dict, Any, Callable
import time
import logging
from datetime import datetime

from validation_utils import (
    InputSanitizer, 
    PasswordValidator, 
    ValidationError, 
    rate_limiter
)
from user_schemas import APIError, ValidationError as ValidationErrorSchema

# Configure logging
logger = logging.getLogger(__name__)


class ValidationMiddleware:
    """Middleware for request validation and sanitization."""
    
    def __init__(self, app):
        self.app = app
    
    async def __call__(self, scope, receive, send):
        if scope["type"] == "http":
            request = Request(scope, receive)
            
            # Skip validation for certain paths
            if self._should_skip_validation(request.url.path):
                await self.app(scope, receive, send)
                return
            
            # Apply rate limiting
            client_ip = self._get_client_ip(request)
            if rate_limiter.is_rate_limited(client_ip, max_attempts=100, window_minutes=1):
                error_response = ValidationErrorSchema(
                    message="Too many requests. Please try again later.",
                    error_code="RATE_LIMITED",
                    field_errors={}
                )
                response = JSONResponse(
                    status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                    content=error_response.dict()
                )
                await response(scope, receive, send)
                return
            
            # Record the attempt
            rate_limiter.record_attempt(client_ip)
        
        await self.app(scope, receive, send)
    
    def _should_skip_validation(self, path: str) -> bool:
        """Determine if validation should be skipped for this path."""
        skip_paths = [
            "/docs",
            "/redoc",
            "/openapi.json",
            "/health",
            "/favicon.ico"
        ]
        return any(path.startswith(skip_path) for skip_path in skip_paths)
    
    def _get_client_ip(self, request: Request) -> str:
        """Extract client IP address from request."""
        # Check for forwarded headers first
        forwarded_for = request.headers.get("X-Forwarded-For")
        if forwarded_for:
            return forwarded_for.split(",")[0].strip()
        
        real_ip = request.headers.get("X-Real-IP")
        if real_ip:
            return real_ip
        
        # Fall back to direct client IP
        return request.client.host if request.client else "unknown"


# Dependency injection functions for validation

async def validate_user_creation_request(request: Request) -> Dict[str, Any]:
    """
    Validate and sanitize user creation request data.
    
    Args:
        request: FastAPI request object
        
    Returns:
        Validated and sanitized request data
        
    Raises:
        HTTPException: If validation fails
    """
    try:
        # Get request body
        body = await request.json()
        
        # Validate required fields
        required_fields = ['username', 'email', 'password']
        missing_fields = [field for field in required_fields if field not in body]
        if missing_fields:
            raise ValidationError(
                f"Missing required fields: {', '.join(missing_fields)}",
                code="MISSING_FIELDS"
            )
        
        # Sanitize and validate username
        username = InputSanitizer.sanitize_string(body['username'], max_length=50)
        if not username:
            raise ValidationError("Username cannot be empty", field="username")
        
        # Validate email
        email = body['email'].strip().lower()
        is_valid_email, normalized_email = InputSanitizer.validate_email_format(email)
        if not is_valid_email:
            raise ValidationError("Invalid email format", field="email")
        
        # Validate password
        password = body['password']
        password_validation = PasswordValidator.validate_password_strength(password)
        if not password_validation['is_valid']:
            raise ValidationError(
                "; ".join(password_validation['errors']),
                field="password"
            )
        
        # Return sanitized data
        return {
            'username': username,
            'email': normalized_email,
            'password': password,
            'role': body.get('role', 'general_user'),
            'is_active': body.get('is_active', True)
        }
        
    except ValidationError as e:
        logger.warning(f"Validation error in user creation: {e.message}")
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail={
                "error": True,
                "message": e.message,
                "field_errors": {e.field: [e.message]} if e.field else {},
                "error_code": e.code or "VALIDATION_ERROR"
            }
        )
    except Exception as e:
        logger.error(f"Unexpected error in user creation validation: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={
                "error": True,
                "message": "Invalid request data",
                "error_code": "INVALID_REQUEST"
            }
        )


async def validate_user_update_request(request: Request) -> Dict[str, Any]:
    """
    Validate and sanitize user update request data.
    
    Args:
        request: FastAPI request object
        
    Returns:
        Validated and sanitized request data
        
    Raises:
        HTTPException: If validation fails
    """
    try:
        # Get request body
        body = await request.json()
        
        if not body:
            raise ValidationError("No update data provided")
        
        validated_data = {}
        
        # Validate username if provided
        if 'username' in body:
            username = InputSanitizer.sanitize_string(body['username'], max_length=50)
            if not username:
                raise ValidationError("Username cannot be empty", field="username")
            validated_data['username'] = username
        
        # Validate email if provided
        if 'email' in body:
            email = body['email'].strip().lower()
            is_valid_email, normalized_email = InputSanitizer.validate_email_format(email)
            if not is_valid_email:
                raise ValidationError("Invalid email format", field="email")
            validated_data['email'] = normalized_email
        
        # Validate password if provided
        if 'password' in body:
            password = body['password']
            password_validation = PasswordValidator.validate_password_strength(password)
            if not password_validation['is_valid']:
                raise ValidationError(
                    "; ".join(password_validation['errors']),
                    field="password"
                )
            validated_data['password'] = password
        
        # Validate role if provided
        if 'role' in body:
            role = body['role']
            valid_roles = ['super_user', 'admin_user', 'general_user']
            if role not in valid_roles:
                raise ValidationError(f"Invalid role. Must be one of: {', '.join(valid_roles)}", field="role")
            validated_data['role'] = role
        
        # Validate is_active if provided
        if 'is_active' in body:
            is_active = body['is_active']
            if not isinstance(is_active, bool):
                raise ValidationError("is_active must be a boolean value", field="is_active")
            validated_data['is_active'] = is_active
        
        return validated_data
        
    except ValidationError as e:
        logger.warning(f"Validation error in user update: {e.message}")
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail={
                "error": True,
                "message": e.message,
                "field_errors": {e.field: [e.message]} if e.field else {},
                "error_code": e.code or "VALIDATION_ERROR"
            }
        )
    except Exception as e:
        logger.error(f"Unexpected error in user update validation: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={
                "error": True,
                "message": "Invalid request data",
                "error_code": "INVALID_REQUEST"
            }
        )


def validate_search_params(
    page: int = 1,
    limit: int = 25,
    search: Optional[str] = None,
    role: Optional[str] = None,
    is_active: Optional[bool] = None,
    sort_by: str = "created_at",
    sort_order: str = "desc"
) -> Dict[str, Any]:
    """
    Validate and sanitize search parameters.
    
    Args:
        page: Page number
        limit: Items per page
        search: Search query
        role: Role filter
        is_active: Active status filter
        sort_by: Sort field
        sort_order: Sort order
        
    Returns:
        Validated search parameters
        
    Raises:
        HTTPException: If validation fails
    """
    try:
        # Validate pagination parameters
        if page < 1:
            raise ValidationError("Page number must be greater than 0", field="page")
        
        if limit < 1 or limit > 100:
            raise ValidationError("Limit must be between 1 and 100", field="limit")
        
        # Sanitize search query
        sanitized_search = None
        if search:
            sanitized_search = InputSanitizer.sanitize_search_query(search)
            if not sanitized_search:
                sanitized_search = None
        
        # Validate role filter
        if role:
            valid_roles = ['super_user', 'admin_user', 'general_user']
            if role not in valid_roles:
                raise ValidationError(f"Invalid role filter. Must be one of: {', '.join(valid_roles)}", field="role")
        
        # Validate sort parameters
        from validation_utils import sanitize_sort_parameters
        validated_sort_by, validated_sort_order = sanitize_sort_parameters(sort_by, sort_order)
        
        return {
            'page': page,
            'limit': limit,
            'search': sanitized_search,
            'role': role,
            'is_active': is_active,
            'sort_by': validated_sort_by,
            'sort_order': validated_sort_order
        }
        
    except ValidationError as e:
        logger.warning(f"Validation error in search parameters: {e.message}")
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail={
                "error": True,
                "message": e.message,
                "field_errors": {e.field: [e.message]} if e.field else {},
                "error_code": e.code or "VALIDATION_ERROR"
            }
        )


async def validate_point_allocation_request(request: Request) -> Dict[str, Any]:
    """
    Validate and sanitize point allocation request data.
    
    Args:
        request: FastAPI request object
        
    Returns:
        Validated and sanitized request data
        
    Raises:
        HTTPException: If validation fails
    """
    try:
        # Get request body
        body = await request.json()
        
        # Validate required fields
        required_fields = ['receiver_email', 'receiver_id', 'allocation_type']
        missing_fields = [field for field in required_fields if field not in body]
        if missing_fields:
            raise ValidationError(
                f"Missing required fields: {', '.join(missing_fields)}",
                code="MISSING_FIELDS"
            )
        
        # Validate receiver email
        email = body['receiver_email'].strip().lower()
        is_valid_email, normalized_email = InputSanitizer.validate_email_format(email)
        if not is_valid_email:
            raise ValidationError("Invalid receiver email format", field="receiver_email")
        
        # Validate receiver ID
        receiver_id = body['receiver_id']
        if not InputSanitizer.validate_user_id(receiver_id):
            raise ValidationError("Invalid receiver ID format", field="receiver_id")
        
        # Validate allocation type
        allocation_type = body['allocation_type']
        valid_types = [
            'admin_user_package', 'one_year_package', 'one_month_package',
            'per_request_point', 'guest_point'
        ]
        if allocation_type not in valid_types:
            raise ValidationError(
                f"Invalid allocation type. Must be one of: {', '.join(valid_types)}",
                field="allocation_type"
            )
        
        # Validate custom points if provided
        custom_points = body.get('custom_points')
        if custom_points is not None:
            if not isinstance(custom_points, int) or custom_points < 1 or custom_points > 10000000:
                raise ValidationError(
                    "Custom points must be an integer between 1 and 10,000,000",
                    field="custom_points"
                )
        
        # Sanitize reason if provided
        reason = body.get('reason')
        if reason:
            reason = InputSanitizer.sanitize_string(reason, max_length=500)
        
        return {
            'receiver_email': normalized_email,
            'receiver_id': receiver_id,
            'allocation_type': allocation_type,
            'custom_points': custom_points,
            'reason': reason
        }
        
    except ValidationError as e:
        logger.warning(f"Validation error in point allocation: {e.message}")
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail={
                "error": True,
                "message": e.message,
                "field_errors": {e.field: [e.message]} if e.field else {},
                "error_code": e.code or "VALIDATION_ERROR"
            }
        )
    except Exception as e:
        logger.error(f"Unexpected error in point allocation validation: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={
                "error": True,
                "message": "Invalid request data",
                "error_code": "INVALID_REQUEST"
            }
        )


async def validate_bulk_operation_request(request: Request) -> Dict[str, Any]:
    """
    Validate and sanitize bulk operation request data.
    
    Args:
        request: FastAPI request object
        
    Returns:
        Validated and sanitized request data
        
    Raises:
        HTTPException: If validation fails
    """
    try:
        # Get request body
        body = await request.json()
        
        if not isinstance(body, dict) or 'operations' not in body:
            raise ValidationError("Request must contain 'operations' field")
        
        operations = body['operations']
        if not isinstance(operations, list):
            raise ValidationError("Operations must be a list")
        
        # Validate operations using utility function
        from validation_utils import validate_bulk_operation_data
        validated_operations = validate_bulk_operation_data(operations)
        
        return {
            'operations': validated_operations
        }
        
    except ValidationError as e:
        logger.warning(f"Validation error in bulk operation: {e.message}")
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail={
                "error": True,
                "message": e.message,
                "field_errors": {},
                "error_code": e.code or "VALIDATION_ERROR"
            }
        )
    except Exception as e:
        logger.error(f"Unexpected error in bulk operation validation: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={
                "error": True,
                "message": "Invalid request data",
                "error_code": "INVALID_REQUEST"
            }
        )


# Exception handlers for validation errors

async def validation_exception_handler(request: Request, exc: ValidationError):
    """Handle validation exceptions and return structured error responses."""
    return JSONResponse(
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        content={
            "error": True,
            "message": exc.message,
            "field_errors": {exc.field: [exc.message]} if exc.field else {},
            "error_code": exc.code or "VALIDATION_ERROR",
            "timestamp": datetime.utcnow().isoformat()
        }
    )


async def generic_exception_handler(request: Request, exc: Exception):
    """Handle generic exceptions and return safe error responses."""
    logger.error(f"Unhandled exception: {str(exc)}", exc_info=True)
    
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={
            "error": True,
            "message": "An internal server error occurred",
            "error_code": "INTERNAL_SERVER_ERROR",
            "timestamp": datetime.utcnow().isoformat()
        }
    )


# Security headers middleware

class SecurityHeadersMiddleware:
    """Middleware to add security headers to responses."""
    
    def __init__(self, app):
        self.app = app
    
    async def __call__(self, scope, receive, send):
        if scope["type"] == "http":
            async def send_wrapper(message):
                if message["type"] == "http.response.start":
                    headers = dict(message.get("headers", []))
                    
                    # Add security headers
                    security_headers = {
                        b"x-content-type-options": b"nosniff",
                        b"x-frame-options": b"DENY",
                        b"x-xss-protection": b"1; mode=block",
                        b"strict-transport-security": b"max-age=31536000; includeSubDomains",
                        b"content-security-policy": b"default-src 'self'",
                        b"referrer-policy": b"strict-origin-when-cross-origin"
                    }
                    
                    headers.update(security_headers)
                    message["headers"] = list(headers.items())
                
                await send(message)
            
            await self.app(scope, receive, send_wrapper)
        else:
            await self.app(scope, receive, send)


# Logging middleware for request/response tracking

class RequestLoggingMiddleware:
    """Middleware for logging requests and responses for audit purposes."""
    
    def __init__(self, app):
        self.app = app
    
    async def __call__(self, scope, receive, send):
        if scope["type"] == "http":
            request = Request(scope, receive)
            start_time = time.time()
            
            # Log request
            logger.info(
                f"Request: {request.method} {request.url.path} "
                f"from {self._get_client_ip(request)}"
            )
            
            async def send_wrapper(message):
                if message["type"] == "http.response.start":
                    process_time = time.time() - start_time
                    status_code = message["status"]
                    
                    # Log response
                    logger.info(
                        f"Response: {status_code} for {request.method} {request.url.path} "
                        f"in {process_time:.3f}s"
                    )
                
                await send(message)
            
            await self.app(scope, receive, send_wrapper)
        else:
            await self.app(scope, receive, send)
    
    def _get_client_ip(self, request: Request) -> str:
        """Extract client IP address from request."""
        forwarded_for = request.headers.get("X-Forwarded-For")
        if forwarded_for:
            return forwarded_for.split(",")[0].strip()
        
        real_ip = request.headers.get("X-Real-IP")
        if real_ip:
            return real_ip
        
        return request.client.host if request.client else "unknown"