from pydantic import BaseModel, EmailStr, Field, validator
from typing import Optional, List, Dict, Any
from datetime import datetime
from enum import Enum
from models import UserRole, PointAllocationType


# Enhanced User Response Models
class UserListResponse(BaseModel):
    id: str
    username: str
    email: str
    role: UserRole
    is_active: bool
    created_at: datetime
    updated_at: Optional[datetime]
    created_by: Optional[str]

    # Enhanced fields
    point_balance: int = 0
    total_points: int = 0
    paid_status: str = "Unknown"
    total_requests: int = 0
    activity_status: str = "Inactive"
    active_suppliers: List[str] = []
    last_login: Optional[datetime] = None

    class Config:
        from_attributes = True


class PaginationMetadata(BaseModel):
    page: int
    limit: int
    total: int
    total_pages: int
    has_next: bool
    has_prev: bool


class UserStatistics(BaseModel):
    total_users: int
    super_users: int
    admin_users: int
    general_users: int
    active_users: int
    inactive_users: int
    total_points_distributed: int
    recent_signups: int


class PaginatedUserResponse(BaseModel):
    users: List[UserListResponse]
    pagination: PaginationMetadata
    statistics: UserStatistics


# User Detail Response
class UserDetailResponse(BaseModel):
    id: str
    username: str
    email: str
    role: UserRole
    is_active: bool
    created_at: datetime
    updated_at: Optional[datetime]
    created_by: Optional[str]

    # Point information
    point_balance: int = 0
    total_points: int = 0
    total_used_points: int = 0
    paid_status: str = "Unknown"

    # Activity information
    activity_status: str = "Inactive"
    total_requests: int = 0
    last_login: Optional[datetime] = None

    # Supplier information
    active_suppliers: List[str] = []

    # Recent transactions (last 10)
    recent_transactions: List[Dict[str, Any]] = []

    class Config:
        from_attributes = True


# Request Models
class UserSearchParams(BaseModel):
    page: int = Field(default=1, ge=1)
    limit: int = Field(default=25, ge=1, le=100)
    search: Optional[str] = None
    role: Optional[UserRole] = None
    is_active: Optional[bool] = None
    sort_by: Optional[str] = Field(default="created_at")
    sort_order: Optional[str] = Field(default="desc")

    @validator('sort_by')
    def validate_sort_by(cls, v):
        allowed_fields = ['username', 'email', 'created_at', 'updated_at', 'point_balance', 'total_points']
        if v not in allowed_fields:
            raise ValueError(f'sort_by must be one of: {", ".join(allowed_fields)}')
        return v

    @validator('sort_order')
    def validate_sort_order(cls, v):
        if v.lower() not in ['asc', 'desc']:
            raise ValueError('sort_order must be either "asc" or "desc"')
        return v.lower()


class UserCreateRequest(BaseModel):
    username: str = Field(..., min_length=3, max_length=50)
    email: EmailStr
    password: str
    role: Optional[UserRole] = UserRole.GENERAL_USER

    @validator('username')
    def validate_username(cls, v):
        if not v.replace('_', '').isalnum():
            raise ValueError('Username must contain only alphanumeric characters and underscores')
        return v


class UserUpdateRequest(BaseModel):
    username: Optional[str] = Field(None, min_length=3, max_length=50)
    email: Optional[EmailStr] = None
    password: Optional[str] = None
    role: Optional[UserRole] = None
    is_active: Optional[bool] = None

    @validator('username')
    def validate_username(cls, v):
        if v is not None and not v.replace('_', '').isalnum():
            raise ValueError('Username must contain only alphanumeric characters and underscores')
        return v


# Bulk Operations
class BulkUserOperation(BaseModel):
    operation: str  # 'create', 'update', 'delete'
    user_id: Optional[str] = None
    user_data: Optional[Dict[str, Any]] = None


class BulkUserOperationRequest(BaseModel):
    operations: List[BulkUserOperation]


# User Activity Response
class UserActivityResponse(BaseModel):
    user_id: str
    activities: List[Dict[str, Any]]
    summary: Dict[str, Any]


# Error Response Models
class APIError(BaseModel):
    error: bool = True
    message: str
    details: Optional[Dict[str, Any]] = None
    error_code: Optional[str] = None
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    
    class Config:
        json_encoders = {
            datetime: lambda v: v.isoformat()
        }


class ValidationError(APIError):
    field_errors: Dict[str, List[str]]


class BusinessLogicError(APIError):
    suggested_action: Optional[str] = None


class AuthorizationError(APIError):
    required_role: Optional[str] = None
    current_role: Optional[str] = None


class NotFoundError(APIError):
    resource_type: Optional[str] = None
    resource_id: Optional[str] = None


class ConflictError(APIError):
    conflicting_field: Optional[str] = None
    conflicting_value: Optional[str] = None