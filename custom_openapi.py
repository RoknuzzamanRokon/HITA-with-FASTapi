from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.openapi.utils import get_openapi


def custom_openapi(app: FastAPI):
    if app.openapi_schema:
        return app.openapi_schema
    
    # Generate base schema
    openapi_schema = get_openapi(
        title="Hotel API - User Management System",
        version="V1.0",
        description="""
        ## Hotel API - Enhanced User Management System
        
        A comprehensive API for managing hotels, users, and point systems with enhanced features for dashboard integration.
        
        ### Key Features
        - **User Management**: Create, update, delete, and manage users with role-based access control
        - **Point System**: Comprehensive point allocation and transaction management
        - **Enhanced Search**: Advanced filtering, sorting, and pagination capabilities
        - **Statistics & Analytics**: Real-time user statistics and activity tracking
        - **Security**: Role-based permissions, input validation, and audit logging
        - **Performance**: Optimized queries, caching, and database indexing
        
        ### Authentication
        All endpoints require authentication via JWT tokens. Include the token in the Authorization header:
        ```
        Authorization: Bearer <your-jwt-token>
        ```
        
        ### User Roles
        - **SUPER_USER**: Full system access, can create any user type
        - **ADMIN_USER**: Can create and manage general users, limited point operations
        - **GENERAL_USER**: Basic access to personal information and point checking
        
        ### Error Handling
        The API returns structured error responses with detailed information:
        - **400**: Bad Request - Invalid input data
        - **401**: Unauthorized - Missing or invalid authentication
        - **403**: Forbidden - Insufficient permissions
        - **404**: Not Found - Resource doesn't exist
        - **422**: Validation Error - Input validation failed
        - **500**: Internal Server Error - System error
        
        ### Rate Limiting
        Some endpoints have rate limiting to prevent abuse:
        - User creation: 5 requests per minute
        - Point operations: 10 requests per minute
        
        ### Pagination
        List endpoints support pagination with the following parameters:
        - `page`: Page number (default: 1)
        - `limit`: Items per page (default: 25, max: 100)
        - `search`: Search term for filtering
        - `sort_by`: Field to sort by
        - `sort_order`: Sort direction (asc/desc)
        """,
        routes=app.routes,
    )

    # Add logo configuration
    openapi_schema["info"]["x-logo"] = {
        "url": "/static/images/ittapilogo_1.png",
        "altText": "Hotel API Logo",
        "backgroundColor": "#FFFFFF",
        "href": "https://example.com"
    }
    
    # Add contact information
    openapi_schema["info"]["contact"] = {
        "name": "API Support",
        "email": "support@hotelapi.com",
        "url": "https://hotelapi.com/support"
    }
    
    # Add license information
    openapi_schema["info"]["license"] = {
        "name": "MIT License",
        "url": "https://opensource.org/licenses/MIT"
    }
    
    # Add server information
    openapi_schema["servers"] = [
        {
            "url": "http://localhost:8000",
            "description": "Development server"
        },
        {
            "url": "https://api.hotelapi.com",
            "description": "Production server"
        }
    ]
    
    # Add security schemes
    if "components" not in openapi_schema:
        openapi_schema["components"] = {}
    if "securitySchemes" not in openapi_schema["components"]:
        openapi_schema["components"]["securitySchemes"] = {}
    
    openapi_schema["components"]["securitySchemes"]["BearerAuth"] = {
        "type": "http",
        "scheme": "bearer",
        "bearerFormat": "JWT",
        "description": "JWT token obtained from the authentication endpoint"
    }
    
    # Add global security requirement
    openapi_schema["security"] = [{"BearerAuth": []}]
    
    # Enhance user management endpoint documentation
    enhance_user_endpoints_documentation(openapi_schema)
    
    # Add common response schemas
    add_common_response_schemas(openapi_schema)
    
    # Add example responses
    add_example_responses(openapi_schema)

    app.openapi_schema = openapi_schema
    return app.openapi_schema


def enhance_user_endpoints_documentation(openapi_schema):
    """Enhance documentation for user management endpoints"""
    paths = openapi_schema.get("paths", {})
    
    # Enhanced documentation for /v1.0/user/me endpoint
    if "/v1.0/user/me" in paths:
        paths["/v1.0/user/me"]["get"]["summary"] = "Get Current User Information"
        paths["/v1.0/user/me"]["get"]["description"] = """
        Retrieve detailed information about the currently authenticated user.
        
        **Returns:**
        - User profile information
        - Current point balance and total points
        - Active supplier relationships
        - Account status and activity information
        
        **Use Cases:**
        - Dashboard user profile display
        - Account settings page
        - Point balance checking
        """
        paths["/v1.0/user/me"]["get"]["tags"] = ["User Profile"]
    
    # Enhanced documentation for /v1.0/user/check/all endpoint
    if "/v1.0/user/check/all" in paths:
        paths["/v1.0/user/check/all"]["get"]["summary"] = "List All Users with Enhanced Features"
        paths["/v1.0/user/check/all"]["get"]["description"] = """
        Retrieve a comprehensive list of users with advanced filtering, searching, and pagination capabilities.
        
        **Enhanced Features:**
        - **Pagination**: Navigate through large user datasets efficiently
        - **Search**: Find users by username, email, or other criteria
        - **Filtering**: Filter by role, active status, creation date
        - **Sorting**: Sort by multiple fields with configurable order
        - **Statistics**: Get real-time user statistics and metrics
        
        **Access Control:**
        - SUPER_USER: Can view all users in the system
        - ADMIN_USER: Can view users they created
        
        **Response Format:**
        - Legacy format for backward compatibility
        - Enhanced pagination metadata when using pagination parameters
        - User statistics and analytics data
        
        **Performance:**
        - Optimized database queries with proper indexing
        - Efficient joins for related data (points, permissions)
        - Caching for frequently accessed data
        """
        paths["/v1.0/user/check/all"]["get"]["tags"] = ["User Management"]
    
    # Enhanced documentation for point checking endpoint
    if "/v1.0/user/points/check/me" in paths:
        paths["/v1.0/user/points/check/me"]["get"]["summary"] = "Get Detailed Point Information"
        paths["/v1.0/user/points/check/me"]["get"]["description"] = """
        Retrieve comprehensive point information for the current user including transaction history.
        
        **Returns:**
        - Current point balance and total points earned
        - Detailed transaction history (received vs used)
        - Point usage analytics and patterns
        - Transaction categorization and summaries
        
        **Transaction Types:**
        - **Received Points**: Points allocated by administrators
        - **Used Points**: Points spent on API requests or services
        - **Deductions**: Administrative point adjustments
        
        **Use Cases:**
        - Point balance dashboard
        - Transaction history review
        - Usage analytics and reporting
        """
        paths["/v1.0/user/points/check/me"]["get"]["tags"] = ["Point Management"]


def add_common_response_schemas(openapi_schema):
    """Add common response schemas to the OpenAPI specification"""
    components = openapi_schema.setdefault("components", {})
    schemas = components.setdefault("schemas", {})
    
    # API Error Response Schema
    schemas["APIError"] = {
        "type": "object",
        "properties": {
            "error": {
                "type": "boolean",
                "default": True,
                "description": "Indicates that an error occurred"
            },
            "message": {
                "type": "string",
                "description": "Human-readable error message"
            },
            "details": {
                "type": "object",
                "description": "Additional error details",
                "additionalProperties": True
            },
            "error_code": {
                "type": "string",
                "description": "Machine-readable error code"
            },
            "timestamp": {
                "type": "string",
                "format": "date-time",
                "description": "When the error occurred"
            }
        },
        "required": ["error", "message", "timestamp"]
    }
    
    # Validation Error Response Schema
    schemas["ValidationError"] = {
        "allOf": [
            {"$ref": "#/components/schemas/APIError"},
            {
                "type": "object",
                "properties": {
                    "field_errors": {
                        "type": "object",
                        "description": "Field-specific validation errors",
                        "additionalProperties": {
                            "type": "array",
                            "items": {"type": "string"}
                        }
                    }
                },
                "required": ["field_errors"]
            }
        ]
    }
    
    # Pagination Metadata Schema
    schemas["PaginationMetadata"] = {
        "type": "object",
        "properties": {
            "page": {
                "type": "integer",
                "description": "Current page number"
            },
            "limit": {
                "type": "integer",
                "description": "Items per page"
            },
            "total": {
                "type": "integer",
                "description": "Total number of items"
            },
            "total_pages": {
                "type": "integer",
                "description": "Total number of pages"
            },
            "has_next": {
                "type": "boolean",
                "description": "Whether there is a next page"
            },
            "has_prev": {
                "type": "boolean",
                "description": "Whether there is a previous page"
            }
        },
        "required": ["page", "limit", "total", "total_pages", "has_next", "has_prev"]
    }
    
    # User Statistics Schema
    schemas["UserStatistics"] = {
        "type": "object",
        "properties": {
            "total_users": {
                "type": "integer",
                "description": "Total number of users in the system"
            },
            "super_users": {
                "type": "integer",
                "description": "Number of super users"
            },
            "admin_users": {
                "type": "integer",
                "description": "Number of admin users"
            },
            "general_users": {
                "type": "integer",
                "description": "Number of general users"
            },
            "active_users": {
                "type": "integer",
                "description": "Number of active users"
            },
            "inactive_users": {
                "type": "integer",
                "description": "Number of inactive users"
            },
            "total_points_distributed": {
                "type": "integer",
                "description": "Total points distributed across all users"
            },
            "recent_signups": {
                "type": "integer",
                "description": "Number of users created in the last 7 days"
            }
        },
        "required": ["total_users", "super_users", "admin_users", "general_users", "active_users", "inactive_users"]
    }


def add_example_responses(openapi_schema):
    """Add example responses to endpoints"""
    paths = openapi_schema.get("paths", {})
    
    # Add examples for user listing endpoint
    if "/v1.0/user/check/all" in paths and "get" in paths["/v1.0/user/check/all"]:
        endpoint = paths["/v1.0/user/check/all"]["get"]
        endpoint["responses"] = {
            "200": {
                "description": "Successful response with user list",
                "content": {
                    "application/json": {
                        "examples": {
                            "legacy_format": {
                                "summary": "Legacy format (no pagination)",
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
                                            "paid_status": "I am super user, I have unlimited points."
                                        }
                                    },
                                    "super_users": [],
                                    "admin_users": [],
                                    "general_users": []
                                }
                            },
                            "enhanced_format": {
                                "summary": "Enhanced format (with pagination)",
                                "value": {
                                    "total_super_user": 1,
                                    "total_admin_users": 2,
                                    "total_general_users": 10,
                                    "pagination": {
                                        "page": 1,
                                        "limit": 25,
                                        "total": 13,
                                        "total_pages": 1,
                                        "has_next": False,
                                        "has_prev": False
                                    },
                                    "root_user": {},
                                    "super_users": [],
                                    "admin_users": [],
                                    "general_users": []
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
                        "example": {
                            "error": True,
                            "message": "Validation failed",
                            "field_errors": {
                                "page": ["Page must be greater than 0"],
                                "limit": ["Limit must be between 1 and 100"]
                            },
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
                            "timestamp": "2024-01-15T10:30:00Z"
                        }
                    }
                }
            }
        }
    
    # Add examples for current user endpoint
    if "/v1.0/user/me" in paths and "get" in paths["/v1.0/user/me"]:
        endpoint = paths["/v1.0/user/me"]["get"]
        endpoint["responses"] = {
            "200": {
                "description": "Current user information",
                "content": {
                    "application/json": {
                        "example": {
                            "id": "abc123",
                            "username": "john_doe",
                            "email": "john@example.com",
                            "user_status": "GENERAL_USER",
                            "available_points": 5000,
                            "total_points": 10000,
                            "active_supplier": ["hotel_api", "booking_system"],
                            "created_at": "2024-01-01T00:00:00Z",
                            "updated_at": "2024-01-15T10:30:00Z",
                            "need_to_next_upgrade": "It function is not implemented yet"
                        }
                    }
                }
            },
            "401": {
                "description": "Unauthorized - Invalid or missing token",
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


# Remove this line - it causes circular reference and breaks docs
# The openapi method is properly set in main.py 