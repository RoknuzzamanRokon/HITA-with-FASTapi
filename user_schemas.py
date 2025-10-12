"""
Enhanced User Data Transfer Objects and Validation Models

This module contains comprehensive Pydantic models for user management operations,
including response models, request validation, and error handling schemas.
"""

from pydantic import BaseModel, EmailStr, Field, field_validator, model_validator, ConfigDict
from typing import Optional, List, Dict, Any, Union
from datetime import datetime
from enum import Enum
import re
from models import UserRole, PointAllocationType


# ===== ENUMS AND CONSTANTS =====

class SortOrder(str, Enum):
    ASC = "asc"
    DESC = "desc"


class UserSortField(str, Enum):
    USERNAME = "username"
    EMAIL = "email"
    CREATED_AT = "created_at"
    UPDATED_AT = "updated_at"
    ROLE = "role"
    POINTS = "points"


class ActivityStatus(str, Enum):
    ACTIVE = "Active"
    INACTIVE = "Inactive"
    UNKNOWN = "Unknown"


class PaidStatus(str, Enum):
    PAID = "Paid"
    USED = "Used"
    UNPAID = "Unpaid"
    UNLIMITED = "I am super user, I have unlimited points."


# ===== CORE RESPONSE MODELS =====

class UserListResponse(BaseModel):
    """Enhanced user response model for list operations with comprehensive user data."""
    
    id: str = Field(..., description="Unique user identifier")
    username: str = Field(..., description="User's username")
    email: EmailStr = Field(..., description="User's email address")
    role: UserRole = Field(..., description="User's role in the system")
    is_active: bool = Field(default=True, description="Whether the user account is active")
    created_at: datetime = Field(..., description="User creation timestamp")
    updated_at: Optional[datetime] = Field(None, description="Last update timestamp")
    created_by: Optional[str] = Field(None, description="Who created this user")
    
    # Enhanced fields with point and activity information
    point_balance: int = Field(default=0, description="Current available points")
    total_points: int = Field(default=0, description="Total points ever received")
    total_used_points: int = Field(default=0, description="Total points used")
    paid_status: PaidStatus = Field(default=PaidStatus.UNPAID, description="Payment/points status")
    total_requests: int = Field(default=0, description="Total number of requests made")
    activity_status: ActivityStatus = Field(default=ActivityStatus.INACTIVE, description="Recent activity status")
    active_suppliers: List[str] = Field(default_factory=list, description="List of active supplier permissions")
    last_login: Optional[datetime] = Field(None, description="Last login timestamp")

    model_config = ConfigDict(
        from_attributes=True,
        json_encoders={
            datetime: lambda v: v.isoformat() if v else None
        }
    )


class UserDetailResponse(UserListResponse):
    """Extended user response with additional detailed information."""
    
    # Additional detailed fields
    api_key: Optional[str] = Field(None, description="User's API key (if applicable)")
    session_count: int = Field(default=0, description="Number of active sessions")
    recent_activity_count: int = Field(default=0, description="Recent activity count (last 7 days)")
    point_transaction_history: List[Dict[str, Any]] = Field(default_factory=list, description="Recent point transactions")
    supplier_permissions: List[Dict[str, str]] = Field(default_factory=list, description="Detailed supplier permissions")


class UserStatistics(BaseModel):
    """User statistics for dashboard and analytics."""
    
    total_users: int = Field(default=0, description="Total number of users")
    super_users: int = Field(default=0, description="Number of super users")
    admin_users: int = Field(default=0, description="Number of admin users")
    general_users: int = Field(default=0, description="Number of general users")
    active_users: int = Field(default=0, description="Number of active users")
    inactive_users: int = Field(default=0, description="Number of inactive users")
    total_points_distributed: int = Field(default=0, description="Total points distributed across all users")
    recent_signups: int = Field(default=0, description="New user signups in the last 30 days")
    users_with_points: int = Field(default=0, description="Users with current point balance > 0")
    average_points_per_user: float = Field(default=0.0, description="Average points per user")


class PaginationMetadata(BaseModel):
    """Pagination metadata for list responses."""
    
    page: int = Field(..., ge=1, description="Current page number")
    limit: int = Field(..., ge=1, le=100, description="Items per page")
    total: int = Field(..., ge=0, description="Total number of items")
    total_pages: int = Field(..., ge=0, description="Total number of pages")
    has_next: bool = Field(..., description="Whether there is a next page")
    has_prev: bool = Field(..., description="Whether there is a previous page")


class PaginatedUserResponse(BaseModel):
    """Paginated response for user list operations."""
    
    users: List[UserListResponse] = Field(..., description="List of users for current page")
    pagination: PaginationMetadata = Field(..., description="Pagination information")
    statistics: UserStatistics = Field(..., description="User statistics summary")
    filters_applied: Dict[str, Any] = Field(default_factory=dict, description="Applied filters summary")


# ===== REQUEST VALIDATION MODELS =====

class UserCreateRequest(BaseModel):
    """Comprehensive user creation request with validation."""
    
    username: str = Field(
        ..., 
        min_length=3, 
        max_length=50, 
        pattern=r'^[a-zA-Z0-9_]+$',
        description="Username (alphanumeric and underscore only)"
    )
    email: EmailStr = Field(..., description="Valid email address")
    password: str = Field(
        ..., 
        min_length=8, 
        max_length=128,
        description="Password (minimum 8 characters)"
    )
    role: Optional[UserRole] = Field(
        default=UserRole.GENERAL_USER,
        description="User role (defaults to general_user)"
    )
    is_active: Optional[bool] = Field(
        default=True,
        description="Whether the user account should be active"
    )

    @field_validator('password')
    @classmethod
    def validate_password_strength(cls, v):
        """Validate password strength requirements."""
        if not re.search(r'[A-Z]', v):
            raise ValueError('Password must contain at least one uppercase letter')
        if not re.search(r'[a-z]', v):
            raise ValueError('Password must contain at least one lowercase letter')
        if not re.search(r'\d', v):
            raise ValueError('Password must contain at least one digit')
        if not re.search(r'[!@#$%^&*(),.?":{}|<>]', v):
            raise ValueError('Password must contain at least one special character')
        return v

    @field_validator('username')
    @classmethod
    def validate_username_format(cls, v):
        """Validate username format and restrictions."""
        if v.lower() in ['admin', 'root', 'system', 'api', 'test']:
            raise ValueError('Username cannot be a reserved word')
        return v.lower()


class UserUpdateRequest(BaseModel):
    """User update request with partial update support."""
    
    username: Optional[str] = Field(
        None, 
        min_length=3, 
        max_length=50, 
        pattern=r'^[a-zA-Z0-9_]+$',
        description="New username"
    )
    email: Optional[EmailStr] = Field(None, description="New email address")
    password: Optional[str] = Field(
        None, 
        min_length=8, 
        max_length=128,
        description="New password"
    )
    role: Optional[UserRole] = Field(None, description="New user role")
    is_active: Optional[bool] = Field(None, description="Active status")

    @field_validator('password')
    @classmethod
    def validate_password_strength(cls, v):
        """Validate password strength if provided."""
        if v is not None:
            if not re.search(r'[A-Z]', v):
                raise ValueError('Password must contain at least one uppercase letter')
            if not re.search(r'[a-z]', v):
                raise ValueError('Password must contain at least one lowercase letter')
            if not re.search(r'\d', v):
                raise ValueError('Password must contain at least one digit')
            if not re.search(r'[!@#$%^&*(),.?":{}|<>]', v):
                raise ValueError('Password must contain at least one special character')
        return v

    @field_validator('username')
    @classmethod
    def validate_username_format(cls, v):
        """Validate username format if provided."""
        if v is not None:
            if v.lower() in ['admin', 'root', 'system', 'api', 'test']:
                raise ValueError('Username cannot be a reserved word')
            return v.lower()
        return v


class UserSearchParams(BaseModel):
    """Search and filter parameters for user queries."""
    
    page: int = Field(default=1, ge=1, description="Page number")
    limit: int = Field(default=25, ge=1, le=100, description="Items per page")
    search: Optional[str] = Field(
        None, 
        min_length=1, 
        max_length=100,
        description="Search term for username or email"
    )
    role: Optional[UserRole] = Field(None, description="Filter by user role")
    is_active: Optional[bool] = Field(None, description="Filter by active status")
    created_after: Optional[datetime] = Field(None, description="Filter users created after this date")
    created_before: Optional[datetime] = Field(None, description="Filter users created before this date")
    has_points: Optional[bool] = Field(None, description="Filter users with/without points")
    sort_by: UserSortField = Field(default=UserSortField.CREATED_AT, description="Sort field")
    sort_order: SortOrder = Field(default=SortOrder.DESC, description="Sort order")

    @field_validator('search')
    @classmethod
    def sanitize_search_query(cls, v):
        """Sanitize search query to prevent injection attacks."""
        if v is not None:
            # Remove potentially dangerous characters
            v = re.sub(r'[<>"\';\\]', '', v.strip())
            if len(v) == 0:
                return None
        return v

    @model_validator(mode='after')
    def validate_date_range(self):
        """Validate that created_after is before created_before."""
        if self.created_after and self.created_before and self.created_after >= self.created_before:
            raise ValueError('created_after must be before created_before')
        return self


class BulkUserOperation(BaseModel):
    """Model for bulk user operations."""
    
    operation: str = Field(..., pattern=r'^(activate|deactivate|delete|update_role)$')
    user_ids: List[str] = Field(..., min_items=1, max_items=100)
    parameters: Optional[Dict[str, Any]] = Field(default_factory=dict)

    @field_validator('user_ids')
    @classmethod
    def validate_user_ids(cls, v):
        """Validate user IDs format."""
        for user_id in v:
            if not re.match(r'^[a-zA-Z0-9]{10}$', user_id):
                raise ValueError(f'Invalid user ID format: {user_id}')
        return v


class PointAllocationRequest(BaseModel):
    """Enhanced point allocation request with validation."""
    
    receiver_email: EmailStr = Field(..., description="Recipient's email address")
    receiver_id: str = Field(..., pattern=r'^[a-zA-Z0-9]{10}$', description="Recipient's user ID")
    allocation_type: PointAllocationType = Field(..., description="Type of point allocation")
    custom_points: Optional[int] = Field(
        None, 
        ge=1, 
        le=10000000,
        description="Custom point amount (if allocation_type supports it)"
    )
    reason: Optional[str] = Field(
        None, 
        max_length=500,
        description="Reason for point allocation"
    )

    @field_validator('reason')
    @classmethod
    def sanitize_reason(cls, v):
        """Sanitize reason text."""
        if v is not None:
            v = re.sub(r'[<>"\';\\]', '', v.strip())
        return v


# ===== ERROR RESPONSE MODELS =====

class APIError(BaseModel):
    """Standard API error response format."""
    
    error: bool = Field(default=True, description="Indicates this is an error response")
    message: str = Field(..., description="Human-readable error message")
    details: Optional[Dict[str, Any]] = Field(None, description="Additional error details")
    error_code: Optional[str] = Field(None, description="Machine-readable error code")
    timestamp: datetime = Field(default_factory=datetime.utcnow, description="Error timestamp")

    model_config = ConfigDict(
        json_encoders={
            datetime: lambda v: v.isoformat()
        }
    )


class ValidationError(APIError):
    """Validation error response with field-specific errors."""
    
    field_errors: Dict[str, List[str]] = Field(..., description="Field-specific validation errors")
    error_code: str = Field(default="VALIDATION_ERROR", description="Error code")


class BusinessLogicError(APIError):
    """Business logic error response."""
    
    error_code: str = Field(default="BUSINESS_LOGIC_ERROR", description="Error code")
    suggested_action: Optional[str] = Field(None, description="Suggested action to resolve the error")


class AuthorizationError(APIError):
    """Authorization error response."""
    
    error_code: str = Field(default="AUTHORIZATION_ERROR", description="Error code")
    required_role: Optional[str] = Field(None, description="Required role for this operation")
    current_role: Optional[str] = Field(None, description="Current user's role")


class NotFoundError(APIError):
    """Resource not found error response."""
    
    error_code: str = Field(default="NOT_FOUND", description="Error code")
    resource_type: Optional[str] = Field(None, description="Type of resource that was not found")
    resource_id: Optional[str] = Field(None, description="ID of resource that was not found")


class ConflictError(APIError):
    """Resource conflict error response."""
    
    error_code: str = Field(default="CONFLICT", description="Error code")
    conflicting_field: Optional[str] = Field(None, description="Field that caused the conflict")
    conflicting_value: Optional[str] = Field(None, description="Value that caused the conflict")


# ===== SUCCESS RESPONSE MODELS =====

class SuccessResponse(BaseModel):
    """Standard success response format."""
    
    success: bool = Field(default=True, description="Indicates successful operation")
    message: str = Field(..., description="Success message")
    data: Optional[Dict[str, Any]] = Field(None, description="Additional response data")
    timestamp: datetime = Field(default_factory=datetime.utcnow, description="Response timestamp")

    model_config = ConfigDict(
        json_encoders={
            datetime: lambda v: v.isoformat()
        }
    )


class BulkOperationResponse(SuccessResponse):
    """Response for bulk operations."""
    
    total_processed: int = Field(..., description="Total number of items processed")
    successful: int = Field(..., description="Number of successful operations")
    failed: int = Field(..., description="Number of failed operations")
    errors: List[Dict[str, Any]] = Field(default_factory=list, description="Details of failed operations")


# ===== ACTIVITY AND AUDIT MODELS =====

class UserActivityResponse(BaseModel):
    """User activity information response."""
    
    user_id: str = Field(..., description="User ID")
    total_logins: int = Field(default=0, description="Total number of logins")
    last_login: Optional[datetime] = Field(None, description="Last login timestamp")
    recent_transactions: int = Field(default=0, description="Recent transactions count")
    active_sessions: int = Field(default=0, description="Number of active sessions")
    point_transactions: List[Dict[str, Any]] = Field(default_factory=list, description="Recent point transactions")
    activity_timeline: List[Dict[str, Any]] = Field(default_factory=list, description="Recent activity timeline")

    model_config = ConfigDict(
        json_encoders={
            datetime: lambda v: v.isoformat() if v else None
        }
    )


# ===== HEALTH CHECK AND MONITORING =====

class HealthCheckResponse(BaseModel):
    """Health check response for monitoring."""
    
    status: str = Field(..., description="Service status")
    timestamp: datetime = Field(default_factory=datetime.utcnow, description="Health check timestamp")
    version: str = Field(default="1.0.0", description="API version")
    database_status: str = Field(..., description="Database connection status")
    active_users: int = Field(default=0, description="Number of currently active users")
    total_users: int = Field(default=0, description="Total number of users")

    model_config = ConfigDict(
        json_encoders={
            datetime: lambda v: v.isoformat()
        }
    )