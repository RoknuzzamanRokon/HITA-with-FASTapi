"""
Comprehensive Error Handling System

This module provides custom exception classes and error handlers for
structured error responses throughout the user management system.
"""

from fastapi import HTTPException, Request, status
from fastapi.responses import JSONResponse
from fastapi.exceptions import RequestValidationError
from pydantic import ValidationError as PydanticValidationError
from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from typing import Dict, Any, List, Optional
from datetime import datetime
import logging

from user_schemas import (
    APIError, 
    ValidationError as ValidationErrorSchema,
    BusinessLogicError,
    AuthorizationError,
    NotFoundError,
    ConflictError
)

# Configure logging
logger = logging.getLogger(__name__)


# ===== CUSTOM EXCEPTION CLASSES =====

class UserManagementException(Exception):
    """Base exception for user management operations."""
    
    def __init__(self, message: str, error_code: str = None, details: Dict[str, Any] = None):
        self.message = message
        self.error_code = error_code or "USER_MANAGEMENT_ERROR"
        self.details = details or {}
        super().__init__(self.message)


class UserNotFoundError(UserManagementException):
    """Exception raised when a user is not found."""
    
    def __init__(self, user_id: str = None, email: str = None):
        if user_id:
            message = f"User with ID '{user_id}' not found"
            details = {"user_id": user_id}
        elif email:
            message = f"User with email '{email}' not found"
            details = {"email": email}
        else:
            message = "User not found"
            details = {}
        
        super().__init__(
            message=message,
            error_code="USER_NOT_FOUND",
            details=details
        )


class UserAlreadyExistsError(UserManagementException):
    """Exception raised when trying to create a user that already exists."""
    
    def __init__(self, field: str, value: str):
        message = f"User with {field} '{value}' already exists"
        super().__init__(
            message=message,
            error_code="USER_ALREADY_EXISTS",
            details={field: value}
        )


class InsufficientPermissionsError(UserManagementException):
    """Exception raised when user lacks required permissions."""
    
    def __init__(self, required_role: str, current_role: str = None, operation: str = None):
        if operation:
            message = f"Operation '{operation}' requires {required_role} role or higher"
        else:
            message = f"This operation requires {required_role} role or higher"
        
        super().__init__(
            message=message,
            error_code="INSUFFICIENT_PERMISSIONS",
            details={
                "required_role": required_role,
                "current_role": current_role,
                "operation": operation
            }
        )


class InsufficientPointsError(UserManagementException):
    """Exception raised when user has insufficient points."""
    
    def __init__(self, required_points: int, available_points: int):
        message = f"Insufficient points. Required: {required_points}, Available: {available_points}"
        super().__init__(
            message=message,
            error_code="INSUFFICIENT_POINTS",
            details={
                "required_points": required_points,
                "available_points": available_points
            }
        )


class InvalidOperationError(UserManagementException):
    """Exception raised when an operation is invalid in the current context."""
    
    def __init__(self, operation: str, reason: str):
        message = f"Invalid operation '{operation}': {reason}"
        super().__init__(
            message=message,
            error_code="INVALID_OPERATION",
            details={"operation": operation, "reason": reason}
        )


class RateLimitExceededError(UserManagementException):
    """Exception raised when rate limit is exceeded."""
    
    def __init__(self, limit: int, window_minutes: int, retry_after: int = None):
        message = f"Rate limit exceeded. Maximum {limit} requests per {window_minutes} minutes"
        details = {"limit": limit, "window_minutes": window_minutes}
        
        if retry_after:
            message += f". Try again in {retry_after} seconds"
            details["retry_after"] = retry_after
        
        super().__init__(
            message=message,
            error_code="RATE_LIMIT_EXCEEDED",
            details=details
        )


class DataValidationError(UserManagementException):
    """Exception raised for data validation errors."""
    
    def __init__(self, field: str, value: Any, reason: str):
        message = f"Invalid value for field '{field}': {reason}"
        super().__init__(
            message=message,
            error_code="DATA_VALIDATION_ERROR",
            details={"field": field, "value": str(value), "reason": reason}
        )


class BusinessRuleViolationError(UserManagementException):
    """Exception raised when business rules are violated."""
    
    def __init__(self, rule: str, details: Dict[str, Any] = None):
        message = f"Business rule violation: {rule}"
        super().__init__(
            message=message,
            error_code="BUSINESS_RULE_VIOLATION",
            details=details or {}
        )


# ===== ERROR HANDLER FUNCTIONS =====

async def user_not_found_handler(request: Request, exc: UserNotFoundError) -> JSONResponse:
    """Handle UserNotFoundError exceptions."""
    logger.warning(f"User not found: {exc.message}")
    
    error_response = NotFoundError(
        message=exc.message,
        error_code=exc.error_code,
        details=exc.details,
        resource_type="user",
        resource_id=exc.details.get("user_id") or exc.details.get("email")
    )
    
    return JSONResponse(
        status_code=status.HTTP_404_NOT_FOUND,
        content=error_response.model_dump()
    )


async def user_already_exists_handler(request: Request, exc: UserAlreadyExistsError) -> JSONResponse:
    """Handle UserAlreadyExistsError exceptions."""
    logger.warning(f"User already exists: {exc.message}")
    
    error_response = ConflictError(
        message=exc.message,
        error_code=exc.error_code,
        details=exc.details,
        conflicting_field=list(exc.details.keys())[0] if exc.details else None,
        conflicting_value=list(exc.details.values())[0] if exc.details else None
    )
    
    return JSONResponse(
        status_code=status.HTTP_409_CONFLICT,
        content=error_response.model_dump()
    )


async def insufficient_permissions_handler(request: Request, exc: InsufficientPermissionsError) -> JSONResponse:
    """Handle InsufficientPermissionsError exceptions."""
    logger.warning(f"Insufficient permissions: {exc.message}")
    
    error_response = AuthorizationError(
        message=exc.message,
        error_code=exc.error_code,
        details=exc.details,
        required_role=exc.details.get("required_role"),
        current_role=exc.details.get("current_role")
    )
    
    return JSONResponse(
        status_code=status.HTTP_403_FORBIDDEN,
        content=error_response.model_dump()
    )


async def insufficient_points_handler(request: Request, exc: InsufficientPointsError) -> JSONResponse:
    """Handle InsufficientPointsError exceptions."""
    logger.warning(f"Insufficient points: {exc.message}")
    
    error_response = BusinessLogicError(
        message=exc.message,
        error_code=exc.error_code,
        details=exc.details,
        suggested_action="Please purchase more points or contact your administrator"
    )
    
    return JSONResponse(
        status_code=status.HTTP_400_BAD_REQUEST,
        content=error_response.model_dump()
    )


async def invalid_operation_handler(request: Request, exc: InvalidOperationError) -> JSONResponse:
    """Handle InvalidOperationError exceptions."""
    logger.warning(f"Invalid operation: {exc.message}")
    
    error_response = BusinessLogicError(
        message=exc.message,
        error_code=exc.error_code,
        details=exc.details,
        suggested_action="Please check the operation parameters and try again"
    )
    
    return JSONResponse(
        status_code=status.HTTP_400_BAD_REQUEST,
        content=error_response.model_dump()
    )


async def rate_limit_exceeded_handler(request: Request, exc: RateLimitExceededError) -> JSONResponse:
    """Handle RateLimitExceededError exceptions."""
    logger.warning(f"Rate limit exceeded: {exc.message}")
    
    error_response = APIError(
        message=exc.message,
        error_code=exc.error_code,
        details=exc.details
    )
    
    headers = {}
    if "retry_after" in exc.details:
        headers["Retry-After"] = str(exc.details["retry_after"])
    
    return JSONResponse(
        status_code=status.HTTP_429_TOO_MANY_REQUESTS,
        content=error_response.model_dump(),
        headers=headers
    )


async def data_validation_handler(request: Request, exc: DataValidationError) -> JSONResponse:
    """Handle DataValidationError exceptions."""
    logger.warning(f"Data validation error: {exc.message}")
    
    error_response = ValidationErrorSchema(
        message="Data validation failed",
        error_code=exc.error_code,
        details=exc.details,
        field_errors={exc.details["field"]: [exc.details["reason"]]}
    )
    
    return JSONResponse(
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        content=error_response.model_dump()
    )


async def business_rule_violation_handler(request: Request, exc: BusinessRuleViolationError) -> JSONResponse:
    """Handle BusinessRuleViolationError exceptions."""
    logger.warning(f"Business rule violation: {exc.message}")
    
    error_response = BusinessLogicError(
        message=exc.message,
        error_code=exc.error_code,
        details=exc.details,
        suggested_action="Please review the business rules and adjust your request"
    )
    
    return JSONResponse(
        status_code=status.HTTP_400_BAD_REQUEST,
        content=error_response.model_dump()
    )


async def pydantic_validation_handler(request: Request, exc: RequestValidationError) -> JSONResponse:
    """Handle Pydantic validation errors from FastAPI."""
    logger.warning(f"Pydantic validation error: {exc.errors()}")
    
    # Convert Pydantic errors to our format
    field_errors = {}
    for error in exc.errors():
        field_path = ".".join(str(loc) for loc in error["loc"])
        error_msg = error["msg"]
        
        if field_path not in field_errors:
            field_errors[field_path] = []
        field_errors[field_path].append(error_msg)
    
    error_response = ValidationErrorSchema(
        message="Request validation failed",
        error_code="REQUEST_VALIDATION_ERROR",
        field_errors=field_errors,
        details={"raw_errors": exc.errors()}
    )
    
    return JSONResponse(
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        content=error_response.model_dump()
    )


async def sqlalchemy_integrity_handler(request: Request, exc: IntegrityError) -> JSONResponse:
    """Handle SQLAlchemy integrity constraint violations."""
    logger.error(f"Database integrity error: {str(exc)}")
    
    # Try to extract meaningful information from the error
    error_msg = str(exc.orig) if hasattr(exc, 'orig') else str(exc)
    
    # Common integrity constraint patterns
    if "UNIQUE constraint failed" in error_msg or "Duplicate entry" in error_msg:
        if "email" in error_msg.lower():
            field = "email"
            message = "A user with this email address already exists"
        elif "username" in error_msg.lower():
            field = "username"
            message = "A user with this username already exists"
        else:
            field = "unknown"
            message = "A record with these values already exists"
        
        error_response = ConflictError(
            message=message,
            error_code="DUPLICATE_RECORD",
            conflicting_field=field
        )
        status_code = status.HTTP_409_CONFLICT
    
    elif "FOREIGN KEY constraint failed" in error_msg:
        error_response = BusinessLogicError(
            message="Referenced record does not exist",
            error_code="FOREIGN_KEY_VIOLATION",
            suggested_action="Please ensure all referenced records exist"
        )
        status_code = status.HTTP_400_BAD_REQUEST
    
    else:
        error_response = APIError(
            message="Database constraint violation",
            error_code="DATABASE_CONSTRAINT_ERROR",
            details={"constraint_type": "unknown"}
        )
        status_code = status.HTTP_400_BAD_REQUEST
    
    return JSONResponse(
        status_code=status_code,
        content=error_response.model_dump()
    )


async def sqlalchemy_error_handler(request: Request, exc: SQLAlchemyError) -> JSONResponse:
    """Handle general SQLAlchemy errors."""
    logger.error(f"Database error: {str(exc)}", exc_info=True)
    
    error_response = APIError(
        message="A database error occurred",
        error_code="DATABASE_ERROR",
        details={"error_type": type(exc).__name__}
    )
    
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content=error_response.model_dump()
    )


async def http_exception_handler(request: Request, exc: HTTPException) -> JSONResponse:
    """Handle FastAPI HTTPException with our error format."""
    logger.warning(f"HTTP exception: {exc.status_code} - {exc.detail}")
    
    # If detail is already a dict (from our validation), use it directly
    if isinstance(exc.detail, dict):
        return JSONResponse(
            status_code=exc.status_code,
            content=exc.detail
        )
    
    # Use a simple error format without datetime objects
    error_response = {
        "error": True,
        "message": str(exc.detail),
        "error_code": f"HTTP_{exc.status_code}",
        "details": {"status_code": exc.status_code},
        "timestamp": datetime.utcnow().isoformat()
    }
    
    return JSONResponse(
        status_code=exc.status_code,
        content=error_response
    )


async def generic_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    """Handle any unhandled exceptions."""
    logger.error(f"Unhandled exception: {type(exc).__name__}: {str(exc)}", exc_info=True)
    
    error_response = {
        "error": True,
        "message": "An internal server error occurred",
        "error_code": "INTERNAL_SERVER_ERROR",
        "details": {"exception_type": type(exc).__name__},
        "timestamp": datetime.utcnow().isoformat()
    }
    
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content=error_response
    )


# ===== ERROR HANDLER REGISTRY =====

def register_error_handlers(app):
    """Register all error handlers with the FastAPI application."""
    
    # Custom exception handlers
    app.add_exception_handler(UserNotFoundError, user_not_found_handler)
    app.add_exception_handler(UserAlreadyExistsError, user_already_exists_handler)
    app.add_exception_handler(InsufficientPermissionsError, insufficient_permissions_handler)
    app.add_exception_handler(InsufficientPointsError, insufficient_points_handler)
    app.add_exception_handler(InvalidOperationError, invalid_operation_handler)
    app.add_exception_handler(RateLimitExceededError, rate_limit_exceeded_handler)
    app.add_exception_handler(DataValidationError, data_validation_handler)
    app.add_exception_handler(BusinessRuleViolationError, business_rule_violation_handler)
    
    # Framework exception handlers
    app.add_exception_handler(RequestValidationError, pydantic_validation_handler)
    app.add_exception_handler(HTTPException, http_exception_handler)
    
    # Database exception handlers
    app.add_exception_handler(IntegrityError, sqlalchemy_integrity_handler)
    app.add_exception_handler(SQLAlchemyError, sqlalchemy_error_handler)
    
    # Generic exception handler (catch-all)
    app.add_exception_handler(Exception, generic_exception_handler)


# ===== UTILITY FUNCTIONS =====

def create_error_response(
    message: str,
    error_code: str = "GENERIC_ERROR",
    status_code: int = status.HTTP_400_BAD_REQUEST,
    details: Dict[str, Any] = None,
    field_errors: Dict[str, List[str]] = None
) -> JSONResponse:
    """
    Create a standardized error response.
    
    Args:
        message: Error message
        error_code: Machine-readable error code
        status_code: HTTP status code
        details: Additional error details
        field_errors: Field-specific validation errors
        
    Returns:
        JSONResponse with standardized error format
    """
    if field_errors:
        error_response = ValidationErrorSchema(
            message=message,
            error_code=error_code,
            details=details or {},
            field_errors=field_errors
        )
    else:
        error_response = APIError(
            message=message,
            error_code=error_code,
            details=details or {}
        )
    
    return JSONResponse(
        status_code=status_code,
        content=error_response.model_dump()
    )


def log_error_context(request: Request, exc: Exception, additional_context: Dict[str, Any] = None):
    """
    Log error with request context for debugging.
    
    Args:
        request: FastAPI request object
        exc: Exception that occurred
        additional_context: Additional context to log
    """
    context = {
        "method": request.method,
        "url": str(request.url),
        "client_ip": request.client.host if request.client else "unknown",
        "user_agent": request.headers.get("user-agent", "unknown"),
        "exception_type": type(exc).__name__,
        "exception_message": str(exc)
    }
    
    if additional_context:
        context.update(additional_context)
    
    logger.error(f"Error context: {context}", exc_info=True)