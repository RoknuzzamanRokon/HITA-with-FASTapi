"""
Validation Middleware for User Management

This module provides middleware functions for request validation and
error handling in FastAPI routes.
"""

from functools import wraps
from typing import Callable, Any, Dict, List
from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from validation_utils import (
    validate_user_data_comprehensive,
    ValidationResult,
    ConflictResolver
)
from error_handlers import (
    UserNotFoundError,
    UserAlreadyExistsError,
    InsufficientPermissionsError,
    DataValidationError,
    BusinessRuleViolationError
)
from user_schemas import ValidationError as ValidationErrorSchema, APIError
import models


def validate_user_creation(db: Session, user_data: Dict[str, Any], current_user: models.User) -> ValidationResult:
    """
    Validate user creation data with comprehensive checks
    
    Args:
        db: Database session
        user_data: User data dictionary
        current_user: Current authenticated user
        
    Returns:
        ValidationResult with validation status and errors
    """
    return validate_user_data_comprehensive(
        db=db,
        username=user_data.get("username"),
        email=user_data.get("email"),
        password=user_data.get("password"),
        role=user_data.get("role"),
        current_user=current_user
    )


def validate_user_update(db: Session, user_id: str, update_data: Dict[str, Any], current_user: models.User) -> ValidationResult:
    """
    Validate user update data with comprehensive checks
    
    Args:
        db: Database session
        user_id: ID of user being updated
        update_data: Update data dictionary
        current_user: Current authenticated user
        
    Returns:
        ValidationResult with validation status and errors
    """
    return validate_user_data_comprehensive(
        db=db,
        username=update_data.get("username"),
        email=update_data.get("email"),
        password=update_data.get("password"),
        role=update_data.get("role"),
        current_user=current_user,
        target_user_id=user_id
    )


def handle_validation_result(validation_result: ValidationResult) -> None:
    """
    Handle validation result by raising appropriate HTTP exceptions
    
    Args:
        validation_result: Result from validation
        
    Raises:
        HTTPException: With appropriate status code and error details
    """
    if not validation_result.is_valid:
        if validation_result.field_errors:
            # Create ValidationError response
            error_response = ValidationErrorSchema(
                message="Validation failed",
                error_code="VALIDATION_ERROR",
                field_errors=validation_result.field_errors,
                details={"business_errors": validation_result.business_errors}
            )
            
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail=error_response.dict()
            )
        
        elif validation_result.business_errors:
            # Create business logic error response
            error_response = APIError(
                message=validation_result.business_errors[0],
                error_code="BUSINESS_RULE_VIOLATION",
                details={
                    "all_business_errors": validation_result.business_errors,
                    "warnings": validation_result.warnings
                }
            )
            
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=error_response.dict()
            )


def provide_conflict_resolution(db: Session, field: str, value: str) -> Dict[str, Any]:
    """
    Provide conflict resolution suggestions for duplicate data
    
    Args:
        db: Database session
        field: Field name that has conflict
        value: Conflicting value
        
    Returns:
        Dictionary with conflict resolution information
    """
    resolver = ConflictResolver(db)
    
    if field == "username":
        return resolver.resolve_username_conflict(value)
    elif field == "email":
        return resolver.resolve_email_conflict(value)
    else:
        return {
            "conflict_type": f"{field}_conflict",
            "original_value": value,
            "resolution_message": f"The {field} '{value}' is already in use. Please choose a different value."
        }


def validate_request_data(required_fields: List[str], optional_fields: List[str] = None) -> Callable:
    """
    Decorator to validate request data for required and optional fields
    
    Args:
        required_fields: List of required field names
        optional_fields: List of optional field names
        
    Returns:
        Decorator function
    """
    def decorator(func: Callable) -> Callable:
        @wraps(func)
        async def wrapper(*args, **kwargs):
            # Extract request data from kwargs
            request_data = None
            for key, value in kwargs.items():
                if isinstance(value, dict) and any(field in value for field in required_fields):
                    request_data = value
                    break
            
            if request_data is None:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail={
                        "error": True,
                        "message": "Invalid request data format",
                        "error_code": "INVALID_REQUEST_FORMAT"
                    }
                )
            
            # Check required fields
            missing_fields = []
            for field in required_fields:
                if field not in request_data or not request_data[field]:
                    missing_fields.append(field)
            
            if missing_fields:
                error_response = ValidationErrorSchema(
                    message="Required fields are missing",
                    error_code="MISSING_REQUIRED_FIELDS",
                    field_errors={field: ["This field is required"] for field in missing_fields}
                )
                
                raise HTTPException(
                    status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                    detail=error_response.dict()
                )
            
            # Validate field types and basic format
            validation_errors = {}
            
            # Email validation
            if "email" in request_data:
                email = request_data["email"]
                if not isinstance(email, str) or "@" not in email:
                    validation_errors["email"] = ["Invalid email format"]
            
            # Username validation
            if "username" in request_data:
                username = request_data["username"]
                if not isinstance(username, str) or len(username) < 3:
                    validation_errors["username"] = ["Username must be at least 3 characters long"]
            
            # Password validation
            if "password" in request_data:
                password = request_data["password"]
                if not isinstance(password, str) or len(password) < 8:
                    validation_errors["password"] = ["Password must be at least 8 characters long"]
            
            if validation_errors:
                error_response = ValidationErrorSchema(
                    message="Field validation failed",
                    error_code="FIELD_VALIDATION_ERROR",
                    field_errors=validation_errors
                )
                
                raise HTTPException(
                    status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                    detail=error_response.dict()
                )
            
            return await func(*args, **kwargs)
        
        return wrapper
    return decorator


def validate_user_permissions(required_roles: List[models.UserRole]) -> Callable:
    """
    Decorator to validate user permissions for specific operations
    
    Args:
        required_roles: List of roles that can perform the operation
        
    Returns:
        Decorator function
    """
    def decorator(func: Callable) -> Callable:
        @wraps(func)
        async def wrapper(*args, **kwargs):
            # Extract current_user from kwargs
            current_user = None
            for key, value in kwargs.items():
                if isinstance(value, models.User):
                    current_user = value
                    break
            
            if current_user is None:
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail={
                        "error": True,
                        "message": "Authentication required",
                        "error_code": "AUTHENTICATION_REQUIRED"
                    }
                )
            
            if current_user.role not in required_roles:
                required_role_names = [role.value for role in required_roles]
                error_response = APIError(
                    message=f"This operation requires one of the following roles: {', '.join(required_role_names)}",
                    error_code="INSUFFICIENT_PERMISSIONS",
                    details={
                        "required_roles": required_role_names,
                        "current_role": current_user.role.value
                    }
                )
                
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail=error_response.dict()
                )
            
            return await func(*args, **kwargs)
        
        return wrapper
    return decorator


def handle_database_errors(func: Callable) -> Callable:
    """
    Decorator to handle database errors and provide meaningful error messages
    
    Args:
        func: Function to wrap
        
    Returns:
        Wrapped function with error handling
    """
    @wraps(func)
    async def wrapper(*args, **kwargs):
        try:
            return await func(*args, **kwargs)
        except Exception as e:
            # Handle specific database errors
            error_message = str(e)
            
            if "UNIQUE constraint failed" in error_message or "Duplicate entry" in error_message:
                if "email" in error_message.lower():
                    field = "email"
                    message = "A user with this email address already exists"
                elif "username" in error_message.lower():
                    field = "username"
                    message = "A user with this username already exists"
                else:
                    field = "unknown"
                    message = "A record with these values already exists"
                
                error_response = APIError(
                    message=message,
                    error_code="DUPLICATE_RECORD",
                    details={"conflicting_field": field}
                )
                
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail=error_response.dict()
                )
            
            elif "FOREIGN KEY constraint failed" in error_message:
                error_response = APIError(
                    message="Referenced record does not exist",
                    error_code="FOREIGN_KEY_VIOLATION",
                    details={"suggestion": "Please ensure all referenced records exist"}
                )
                
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=error_response.dict()
                )
            
            else:
                # Generic database error
                error_response = APIError(
                    message="A database error occurred",
                    error_code="DATABASE_ERROR",
                    details={"error_type": type(e).__name__}
                )
                
                raise HTTPException(
                    status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                    detail=error_response.dict()
                )
    
    return wrapper


# Utility functions for common validation patterns

def validate_pagination_params(page: int, limit: int) -> None:
    """
    Validate pagination parameters
    
    Args:
        page: Page number
        limit: Items per page
        
    Raises:
        HTTPException: If parameters are invalid
    """
    errors = {}
    
    if page < 1:
        errors["page"] = ["Page number must be greater than 0"]
    
    if limit < 1:
        errors["limit"] = ["Limit must be greater than 0"]
    elif limit > 100:
        errors["limit"] = ["Limit cannot exceed 100 items per page"]
    
    if errors:
        error_response = ValidationErrorSchema(
            message="Invalid pagination parameters",
            error_code="INVALID_PAGINATION",
            field_errors=errors
        )
        
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=error_response.dict()
        )


def validate_search_params(search: str = None, max_length: int = 100) -> None:
    """
    Validate search parameters
    
    Args:
        search: Search query string
        max_length: Maximum allowed length
        
    Raises:
        HTTPException: If search parameters are invalid
    """
    if search is not None:
        if len(search) > max_length:
            error_response = ValidationErrorSchema(
                message="Search query too long",
                error_code="SEARCH_QUERY_TOO_LONG",
                field_errors={"search": [f"Search query must not exceed {max_length} characters"]}
            )
            
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail=error_response.dict()
            )
        
        # Check for potentially dangerous characters
        dangerous_chars = ['<', '>', '"', "'", '&', ';', '(', ')', '|', '`']
        if any(char in search for char in dangerous_chars):
            error_response = ValidationErrorSchema(
                message="Search query contains invalid characters",
                error_code="INVALID_SEARCH_CHARACTERS",
                field_errors={"search": ["Search query contains potentially dangerous characters"]}
            )
            
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail=error_response.dict()
            )