"""
Enhanced API Documentation for User Management Endpoints

This module provides comprehensive documentation, examples, and validation rules
for all user management endpoints in the Hotel API system.
"""

from typing import Dict, Any, List
from fastapi import FastAPI
from fastapi.openapi.utils import get_openapi


class UserEndpointDocumentation:
    """Documentation for user management endpoints"""
    
    @staticmethod
    def get_user_list_documentation() -> Dict[str, Any]:
        """Documentation for the enhanced user listing endpoint"""
        return {
            "summary": "List Users with Advanced Features",
            "description": """
            Retrieve a comprehensive list of users with advanced filtering, searching, and pagination capabilities.
            
            ## Enhanced Features
            
            ### Pagination
            - Navigate through large user datasets efficiently
            - Configurable page size (1-100 items per page)
            - Metadata includes total count, page info, and navigation flags
            
            ### Search and Filtering
            - **Search**: Find users by username, email, or other text fields
            - **Role Filter**: Filter by specific user roles (SUPER_USER, ADMIN_USER, GENERAL_USER)
            - **Status Filter**: Filter by active/inactive status
            - **Date Range**: Filter by creation date ranges
            
            ### Sorting
            - Sort by multiple fields: username, email, created_at, point_balance
            - Configurable sort order: ascending or descending
            - Default sort: created_at descending (newest first)
            
            ### Performance Optimizations
            - Optimized database queries with proper indexing
            - Efficient joins for related data (points, permissions, transactions)
            - Caching for frequently accessed data
            - Query result streaming for large datasets
            
            ## Access Control
            - **SUPER_USER**: Can view all users in the system
            - **ADMIN_USER**: Can view users they created and manage
            - **GENERAL_USER**: Cannot access this endpoint
            
            ## Response Formats
            
            ### Legacy Format (Backward Compatibility)
            When no pagination parameters are provided, returns the original format:
            ```json
            {
                "total_super_user": 1,
                "total_admin_users": 5,
                "total_general_users": 100,
                "root_user": {...},
                "super_users": [...],
                "admin_users": [...],
                "general_users": [...]
            }
            ```
            
            ### Enhanced Format (With Pagination)
            When pagination parameters are provided, returns enhanced format:
            ```json
            {
                "users": [...],
                "pagination": {
                    "page": 1,
                    "limit": 25,
                    "total": 106,
                    "total_pages": 5,
                    "has_next": true,
                    "has_prev": false
                },
                "statistics": {
                    "total_users": 106,
                    "super_users": 1,
                    "admin_users": 5,
                    "general_users": 100,
                    "active_users": 95,
                    "inactive_users": 11
                }
            }
            ```
            
            ## Use Cases
            - Dashboard user management interface
            - User search and discovery
            - Administrative user oversight
            - System analytics and reporting
            - Bulk user operations preparation
            """,
            "parameters": [
                {
                    "name": "page",
                    "in": "query",
                    "description": "Page number for pagination (starts from 1)",
                    "required": False,
                    "schema": {
                        "type": "integer",
                        "minimum": 1,
                        "default": 1,
                        "example": 1
                    }
                },
                {
                    "name": "limit",
                    "in": "query",
                    "description": "Number of items per page (1-100)",
                    "required": False,
                    "schema": {
                        "type": "integer",
                        "minimum": 1,
                        "maximum": 100,
                        "default": 25,
                        "example": 25
                    }
                },
                {
                    "name": "search",
                    "in": "query",
                    "description": "Search term to filter users by username, email, or other text fields",
                    "required": False,
                    "schema": {
                        "type": "string",
                        "minLength": 1,
                        "maxLength": 100,
                        "example": "john"
                    }
                },
                {
                    "name": "role",
                    "in": "query",
                    "description": "Filter users by role",
                    "required": False,
                    "schema": {
                        "type": "string",
                        "enum": ["SUPER_USER", "ADMIN_USER", "GENERAL_USER"],
                        "example": "GENERAL_USER"
                    }
                },
                {
                    "name": "is_active",
                    "in": "query",
                    "description": "Filter users by active status",
                    "required": False,
                    "schema": {
                        "type": "boolean",
                        "example": True
                    }
                },
                {
                    "name": "sort_by",
                    "in": "query",
                    "description": "Field to sort by",
                    "required": False,
                    "schema": {
                        "type": "string",
                        "enum": ["username", "email", "created_at", "updated_at", "point_balance", "total_points"],
                        "default": "created_at",
                        "example": "created_at"
                    }
                },
                {
                    "name": "sort_order",
                    "in": "query",
                    "description": "Sort order direction",
                    "required": False,
                    "schema": {
                        "type": "string",
                        "enum": ["asc", "desc"],
                        "default": "desc",
                        "example": "desc"
                    }
                }
            ],
            "responses": {
                "200": {
                    "description": "Successful response with user list",
                    "content": {
                        "application/json": {
                            "examples": {
                                "legacy_format": {
                                    "summary": "Legacy format (no pagination parameters)",
                                    "value": {
                                        "total_super_user": 1,
                                        "total_admin_users": 2,
                                        "total_general_users": 10,
                                        "root_user": {
                                            "id": "abc123",
                                            "username": "admin",
                                            "email": "admin@example.com",
                                            "role": "SUPER_USER",
                                            "points_info": {
                                                "total_points": 1000000,
                                                "current_points": 950000,
                                                "paid_status": "I am super user, I have unlimited points.",
                                                "total_rq": 50
                                            },
                                            "using_rq_status": "Active",
                                            "active_supplier": ["hotel_api", "booking_system"],
                                            "created_at": "2024-01-01T00:00:00Z",
                                            "updated_at": "2024-01-15T10:30:00Z"
                                        },
                                        "super_users": [],
                                        "admin_users": [
                                            {
                                                "id": "def456",
                                                "username": "admin_user",
                                                "email": "admin@company.com",
                                                "role": "ADMIN_USER",
                                                "points_info": {
                                                    "total_points": 100000,
                                                    "current_points": 85000,
                                                    "paid_status": "Paid",
                                                    "total_rq": 15
                                                },
                                                "using_rq_status": "Active",
                                                "active_supplier": ["hotel_api"],
                                                "created_at": "2024-01-05T00:00:00Z",
                                                "updated_at": "2024-01-15T08:00:00Z"
                                            }
                                        ],
                                        "general_users": [
                                            {
                                                "id": "ghi789",
                                                "username": "john_doe",
                                                "email": "john@example.com",
                                                "role": "GENERAL_USER",
                                                "points_info": {
                                                    "total_points": 5000,
                                                    "current_points": 3000,
                                                    "paid_status": "Paid",
                                                    "total_rq": 20
                                                },
                                                "using_rq_status": "Inactive",
                                                "active_supplier": [],
                                                "created_at": "2024-01-10T00:00:00Z",
                                                "updated_at": "2024-01-12T15:30:00Z"
                                            }
                                        ]
                                    }
                                },
                                "enhanced_format": {
                                    "summary": "Enhanced format (with pagination)",
                                    "value": {
                                        "users": [
                                            {
                                                "id": "ghi789",
                                                "username": "john_doe",
                                                "email": "john@example.com",
                                                "role": "GENERAL_USER",
                                                "is_active": True,
                                                "created_at": "2024-01-10T00:00:00Z",
                                                "updated_at": "2024-01-12T15:30:00Z",
                                                "created_by": "admin_user: admin@company.com",
                                                "point_balance": 3000,
                                                "total_points": 5000,
                                                "paid_status": "Paid",
                                                "total_requests": 20,
                                                "activity_status": "Inactive",
                                                "active_suppliers": [],
                                                "last_login": "2024-01-12T15:30:00Z"
                                            }
                                        ],
                                        "pagination": {
                                            "page": 1,
                                            "limit": 25,
                                            "total": 13,
                                            "total_pages": 1,
                                            "has_next": False,
                                            "has_prev": False
                                        },
                                        "statistics": {
                                            "total_users": 13,
                                            "super_users": 1,
                                            "admin_users": 2,
                                            "general_users": 10,
                                            "active_users": 11,
                                            "inactive_users": 2,
                                            "total_points_distributed": 1105000,
                                            "recent_signups": 3
                                        }
                                    }
                                }
                            }
                        }
                    }
                },
                "400": {
                    "description": "Bad Request - Invalid parameters",
                    "content": {
                        "application/json": {
                            "schema": {"$ref": "#/components/schemas/ValidationError"},
                            "examples": {
                                "invalid_pagination": {
                                    "summary": "Invalid pagination parameters",
                                    "value": {
                                        "error": True,
                                        "message": "Validation failed",
                                        "field_errors": {
                                            "page": ["Page must be greater than 0"],
                                            "limit": ["Limit must be between 1 and 100"]
                                        },
                                        "timestamp": "2024-01-15T10:30:00Z"
                                    }
                                },
                                "invalid_sort": {
                                    "summary": "Invalid sort parameters",
                                    "value": {
                                        "error": True,
                                        "message": "Validation failed",
                                        "field_errors": {
                                            "sort_by": ["sort_by must be one of: username, email, created_at, updated_at, point_balance, total_points"],
                                            "sort_order": ["sort_order must be either 'asc' or 'desc'"]
                                        },
                                        "timestamp": "2024-01-15T10:30:00Z"
                                    }
                                }
                            }
                        }
                    }
                },
                "401": {
                    "description": "Unauthorized - Invalid or missing authentication",
                    "content": {
                        "application/json": {
                            "schema": {"$ref": "#/components/schemas/APIError"},
                            "example": {
                                "error": True,
                                "message": "Could not validate credentials",
                                "error_code": "INVALID_TOKEN",
                                "timestamp": "2024-01-15T10:30:00Z"
                            }
                        }
                    }
                },
                "403": {
                    "description": "Forbidden - Insufficient permissions",
                    "content": {
                        "application/json": {
                            "schema": {"$ref": "#/components/schemas/APIError"},
                            "example": {
                                "error": True,
                                "message": "Only super_user or admin_user can access this endpoint.",
                                "error_code": "INSUFFICIENT_PERMISSIONS",
                                "details": {
                                    "required_role": "ADMIN_USER or SUPER_USER",
                                    "current_role": "GENERAL_USER"
                                },
                                "timestamp": "2024-01-15T10:30:00Z"
                            }
                        }
                    }
                },
                "500": {
                    "description": "Internal Server Error",
                    "content": {
                        "application/json": {
                            "schema": {"$ref": "#/components/schemas/APIError"},
                            "example": {
                                "error": True,
                                "message": "An internal server error occurred",
                                "error_code": "INTERNAL_ERROR",
                                "timestamp": "2024-01-15T10:30:00Z"
                            }
                        }
                    }
                }
            }
        }
    
    @staticmethod
    def get_user_creation_documentation() -> Dict[str, Any]:
        """Documentation for user creation endpoints"""
        return {
            "summary": "Create New User",
            "description": """
            Create a new user with comprehensive validation and role-based access control.
            
            ## Validation Rules
            
            ### Username Requirements
            - Length: 3-50 characters
            - Characters: Alphanumeric and underscores only
            - Must be unique across the system
            
            ### Email Requirements
            - Must be a valid email format
            - Must be unique across the system
            - Used for authentication and notifications
            
            ### Password Requirements
            - Minimum length: 8 characters
            - Must contain at least one uppercase letter
            - Must contain at least one lowercase letter
            - Must contain at least one digit
            - Stored securely using bcrypt hashing
            
            ## Role-Based Creation Rules
            
            ### SUPER_USER Creation
            - Only SUPER_USER can create other SUPER_USER accounts
            - No restrictions on user creation
            - Can create users of any role
            
            ### ADMIN_USER Creation
            - Only SUPER_USER can create ADMIN_USER accounts
            - ADMIN_USER can create GENERAL_USER accounts
            - Cannot create other ADMIN_USER or SUPER_USER accounts
            
            ### GENERAL_USER Creation
            - SUPER_USER and ADMIN_USER can create GENERAL_USER accounts
            - GENERAL_USER cannot create any accounts
            
            ## Security Features
            - Rate limiting: 5 user creations per minute
            - Input sanitization and validation
            - Audit logging of all user creation activities
            - Automatic password hashing with bcrypt
            
            ## Response Format
            Returns the created user information in a standardized format with:
            - User ID and basic information
            - Role assignment confirmation
            - Creator information for audit trail
            - Creation timestamp
            """,
            "requestBody": {
                "required": True,
                "content": {
                    "application/json": {
                        "schema": {
                            "type": "object",
                            "properties": {
                                "username": {
                                    "type": "string",
                                    "minLength": 3,
                                    "maxLength": 50,
                                    "pattern": "^[a-zA-Z0-9_]+$",
                                    "description": "Unique username (alphanumeric and underscores only)"
                                },
                                "email": {
                                    "type": "string",
                                    "format": "email",
                                    "description": "Valid email address (must be unique)"
                                },
                                "password": {
                                    "type": "string",
                                    "minLength": 8,
                                    "description": "Strong password (min 8 chars, uppercase, lowercase, digit)"
                                }
                            },
                            "required": ["username", "email", "password"]
                        },
                        "examples": {
                            "general_user": {
                                "summary": "Create General User",
                                "value": {
                                    "username": "john_doe",
                                    "email": "john@example.com",
                                    "password": "SecurePass123"
                                }
                            },
                            "admin_user": {
                                "summary": "Create Admin User",
                                "value": {
                                    "username": "admin_user",
                                    "email": "admin@company.com",
                                    "password": "AdminPass456",
                                    "business_id": "COMP001"
                                }
                            }
                        }
                    }
                }
            },
            "responses": {
                "201": {
                    "description": "User created successfully",
                    "content": {
                        "application/json": {
                            "examples": {
                                "general_user_created": {
                                    "summary": "General user created",
                                    "value": {
                                        "id": "abc123",
                                        "username": "john_doe",
                                        "email": "john@example.com",
                                        "role": "GENERAL_USER",
                                        "created_by": [
                                            {
                                                "title": "ADMIN_USER",
                                                "email": "admin@company.com"
                                            }
                                        ]
                                    }
                                },
                                "admin_user_created": {
                                    "summary": "Admin user created",
                                    "value": {
                                        "id": "def456",
                                        "username": "admin_user",
                                        "email": "admin@company.com",
                                        "role": "ADMIN_USER",
                                        "created_by": [
                                            {
                                                "title": "SUPER_USER",
                                                "email": "super@system.com"
                                            }
                                        ]
                                    }
                                }
                            }
                        }
                    }
                },
                "400": {
                    "description": "Bad Request - Validation failed or duplicate data",
                    "content": {
                        "application/json": {
                            "examples": {
                                "validation_error": {
                                    "summary": "Validation errors",
                                    "value": {
                                        "error": True,
                                        "message": "Validation failed",
                                        "field_errors": {
                                            "username": ["Username must contain only alphanumeric characters and underscores"],
                                            "email": ["Must need valid email"],
                                            "password": ["Password must contain at least one uppercase letter"]
                                        },
                                        "timestamp": "2024-01-15T10:30:00Z"
                                    }
                                },
                                "duplicate_email": {
                                    "summary": "Email already exists",
                                    "value": {
                                        "error": True,
                                        "message": "User with this email already exists.",
                                        "error_code": "DUPLICATE_EMAIL",
                                        "details": {
                                            "conflicting_field": "email",
                                            "conflicting_value": "john@example.com"
                                        },
                                        "timestamp": "2024-01-15T10:30:00Z"
                                    }
                                },
                                "duplicate_username": {
                                    "summary": "Username already exists",
                                    "value": {
                                        "error": True,
                                        "message": "Username already exists.",
                                        "error_code": "DUPLICATE_USERNAME",
                                        "details": {
                                            "conflicting_field": "username",
                                            "conflicting_value": "john_doe"
                                        },
                                        "timestamp": "2024-01-15T10:30:00Z"
                                    }
                                }
                            }
                        }
                    }
                },
                "403": {
                    "description": "Forbidden - Insufficient permissions",
                    "content": {
                        "application/json": {
                            "examples": {
                                "insufficient_permissions": {
                                    "summary": "Cannot create user of this role",
                                    "value": {
                                        "error": True,
                                        "message": "Only super_user can create another super_user.",
                                        "error_code": "INSUFFICIENT_PERMISSIONS",
                                        "details": {
                                            "required_role": "SUPER_USER",
                                            "current_role": "ADMIN_USER",
                                            "attempted_action": "create_super_user"
                                        },
                                        "timestamp": "2024-01-15T10:30:00Z"
                                    }
                                }
                            }
                        }
                    }
                },
                "429": {
                    "description": "Too Many Requests - Rate limit exceeded",
                    "content": {
                        "application/json": {
                            "example": {
                                "error": True,
                                "message": "Rate limit exceeded. Maximum 5 user creations per minute.",
                                "error_code": "RATE_LIMIT_EXCEEDED",
                                "details": {
                                    "limit": 5,
                                    "window": "1 minute",
                                    "retry_after": 45
                                },
                                "timestamp": "2024-01-15T10:30:00Z"
                            }
                        }
                    }
                }
            }
        }
    
    @staticmethod
    def get_point_management_documentation() -> Dict[str, Any]:
        """Documentation for point management endpoints"""
        return {
            "summary": "Get Detailed Point Information",
            "description": """
            Retrieve comprehensive point information for the current user including detailed transaction history.
            
            ## Point System Overview
            
            The point system manages user credits for API usage and services:
            - **Total Points**: Lifetime points allocated to the user
            - **Current Points**: Available points for spending
            - **Used Points**: Points consumed through API requests or services
            
            ## Point Allocation Types
            
            ### Package Types
            - **ADMIN_USER_PACKAGE**: 4,000,000 points (for admin users)
            - **ONE_YEAR_PACKAGE**: 1,000,000 points (annual subscription)
            - **ONE_MONTH_PACKAGE**: 80,000 points (monthly subscription)
            - **PER_REQUEST_POINT**: 10,000 points (pay-per-use)
            - **GUEST_POINT**: 1,000 points (trial/guest access)
            
            ## Transaction History
            
            ### Received Points (Credit Transactions)
            - Points allocated by administrators
            - Package purchases and upgrades
            - Promotional credits and bonuses
            - Refunds and adjustments
            
            ### Used Points (Debit Transactions)
            - API request consumption
            - Service usage charges
            - Administrative deductions
            - Point transfers to other users
            
            ## Response Data Structure
            
            The response includes:
            1. **User Point Summary**: Current balance, total earned, total used
            2. **Transaction History**: Detailed log of all point movements
            3. **Usage Analytics**: Request counts, usage patterns
            4. **Account Status**: Payment status, activity level
            
            ## Use Cases
            - Point balance dashboard display
            - Transaction history review and audit
            - Usage analytics and reporting
            - Billing and payment verification
            - Account status monitoring
            """,
            "responses": {
                "200": {
                    "description": "Detailed point information with transaction history",
                    "content": {
                        "application/json": {
                            "example": {
                                "user_mail": "john@example.com",
                                "total_points": 10000,
                                "current_points": 7500,
                                "total_points_used": 2500,
                                "transactions": [
                                    {
                                        "user_name": "john_doe",
                                        "user_id": "abc123",
                                        "total_used_point": 10000,
                                        "get_point_history": [
                                            {
                                                "id": 1,
                                                "giver_id": "admin001",
                                                "giver_email": "admin@company.com",
                                                "receiver_id": "abc123",
                                                "receiver_email": "john@example.com",
                                                "points": 10000,
                                                "transaction_type": "ONE_MONTH_PACKAGE",
                                                "created_at": "2024-01-01T00:00:00Z"
                                            }
                                        ]
                                    },
                                    {
                                        "uses_request_history": [
                                            {
                                                "id": 2,
                                                "user_id": "abc123",
                                                "user_email": "john@example.com",
                                                "point_used": 2500,
                                                "total_request": 250,
                                                "transaction_type": "deduction",
                                                "created_at": "2024-01-15T10:30:00Z"
                                            }
                                        ]
                                    }
                                ]
                            }
                        }
                    }
                },
                "401": {
                    "description": "Unauthorized - Invalid or missing authentication",
                    "content": {
                        "application/json": {
                            "schema": {"$ref": "#/components/schemas/APIError"},
                            "example": {
                                "error": True,
                                "message": "Could not validate credentials",
                                "error_code": "INVALID_TOKEN",
                                "timestamp": "2024-01-15T10:30:00Z"
                            }
                        }
                    }
                }
            }
        }


def apply_enhanced_documentation(app: FastAPI):
    """Apply enhanced documentation to the FastAPI app"""
    
    # Get the documentation helper
    doc_helper = UserEndpointDocumentation()
    
    # Apply documentation to specific endpoints
    if hasattr(app, 'openapi_schema') and app.openapi_schema:
        paths = app.openapi_schema.get("paths", {})
        
        # Enhance user listing endpoint
        if "/v1.0/user/check/all" in paths and "get" in paths["/v1.0/user/check/all"]:
            user_list_doc = doc_helper.get_user_list_documentation()
            paths["/v1.0/user/check/all"]["get"].update(user_list_doc)
        
        # Enhance user creation endpoints
        creation_endpoints = [
            "/v1.0/user/create_general_user",
            "/v1.0/user/create_admin_user", 
            "/v1.0/user/create_super_user"
        ]
        
        for endpoint in creation_endpoints:
            if endpoint in paths and "post" in paths[endpoint]:
                creation_doc = doc_helper.get_user_creation_documentation()
                paths[endpoint]["post"].update(creation_doc)
        
        # Enhance point management endpoint
        if "/v1.0/user/points-check" in paths and "get" in paths["/v1.0/user/points-check"]:
            point_doc = doc_helper.get_point_management_documentation()
            paths["/v1.0/user/points-check"]["get"].update(point_doc)


# Validation rules documentation
VALIDATION_RULES = {
    "username": {
        "min_length": 3,
        "max_length": 50,
        "pattern": "^[a-zA-Z0-9_]+$",
        "description": "Must contain only alphanumeric characters and underscores",
        "examples": ["john_doe", "admin_user", "user123"]
    },
    "email": {
        "format": "email",
        "description": "Must be a valid email address format",
        "examples": ["user@example.com", "admin@company.org", "test@domain.co.uk"]
    },
    "password": {
        "min_length": 8,
        "requirements": [
            "At least one uppercase letter",
            "At least one lowercase letter", 
            "At least one digit"
        ],
        "description": "Strong password meeting security requirements",
        "examples": ["SecurePass123", "MyPassword1", "StrongPwd9"]
    },
    "pagination": {
        "page": {
            "minimum": 1,
            "description": "Page number starting from 1"
        },
        "limit": {
            "minimum": 1,
            "maximum": 100,
            "description": "Items per page, maximum 100"
        }
    },
    "search": {
        "min_length": 1,
        "max_length": 100,
        "description": "Search term for filtering users"
    },
    "sort_by": {
        "allowed_values": ["username", "email", "created_at", "updated_at", "point_balance", "total_points"],
        "description": "Field to sort results by"
    },
    "sort_order": {
        "allowed_values": ["asc", "desc"],
        "description": "Sort direction: ascending or descending"
    }
}

# Error response examples
ERROR_EXAMPLES = {
    "validation_error": {
        "error": True,
        "message": "Validation failed",
        "field_errors": {
            "username": ["Username must contain only alphanumeric characters and underscores"],
            "email": ["Must need valid email"],
            "password": ["Password must contain at least one uppercase letter"]
        },
        "timestamp": "2024-01-15T10:30:00Z"
    },
    "unauthorized": {
        "error": True,
        "message": "Could not validate credentials",
        "error_code": "INVALID_TOKEN",
        "timestamp": "2024-01-15T10:30:00Z"
    },
    "forbidden": {
        "error": True,
        "message": "Only super_user or admin_user can access this endpoint.",
        "error_code": "INSUFFICIENT_PERMISSIONS",
        "details": {
            "required_role": "ADMIN_USER or SUPER_USER",
            "current_role": "GENERAL_USER"
        },
        "timestamp": "2024-01-15T10:30:00Z"
    },
    "not_found": {
        "error": True,
        "message": "User not found",
        "error_code": "USER_NOT_FOUND",
        "details": {
            "resource_type": "user",
            "resource_id": "abc123"
        },
        "timestamp": "2024-01-15T10:30:00Z"
    },
    "conflict": {
        "error": True,
        "message": "User with this email already exists.",
        "error_code": "DUPLICATE_EMAIL",
        "details": {
            "conflicting_field": "email",
            "conflicting_value": "john@example.com"
        },
        "timestamp": "2024-01-15T10:30:00Z"
    },
    "rate_limit": {
        "error": True,
        "message": "Rate limit exceeded. Maximum 5 user creations per minute.",
        "error_code": "RATE_LIMIT_EXCEEDED",
        "details": {
            "limit": 5,
            "window": "1 minute",
            "retry_after": 45
        },
        "timestamp": "2024-01-15T10:30:00Z"
    }
}