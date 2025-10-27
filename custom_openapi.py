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
    
    # Enhanced documentation for analytics endpoints
    enhance_analytics_endpoints_documentation(paths)


def enhance_analytics_endpoints_documentation(paths):
    """Enhance documentation for analytics endpoints"""
    
    # Analytics test health endpoint
    if "/v1.0/analytics/test/health" in paths:
        paths["/v1.0/analytics/test/health"]["get"]["summary"] = "Analytics Router Health Check"
        paths["/v1.0/analytics/test/health"]["get"]["description"] = """
        Simple test endpoint to verify analytics router is working and test IP extraction.
        
        **Returns:**
        - Router status confirmation
        - IP address information from various sources
        - Headers information for debugging
        
        **Use Cases:**
        - System health monitoring
        - IP middleware testing
        - Router connectivity verification
        """
        paths["/v1.0/analytics/test/health"]["get"]["tags"] = ["Analytics Health"]
    
    # Dashboard analytics endpoint
    if "/v1.0/analytics/dashboard" in paths:
        paths["/v1.0/analytics/dashboard"]["get"]["summary"] = "Get Dashboard Analytics"
        paths["/v1.0/analytics/dashboard"]["get"]["description"] = """
        Get comprehensive analytics for dashboard display including user statistics, activity trends, and point distribution.
        
        **Returns:**
        - User statistics (total users by role, active/inactive counts)
        - User creation trend (last 30 days)
        - Point distribution by role with averages
        - Activity summary (active users, recent transactions)
        
        **Features:**
        - Real-time data aggregation
        - Role-based data filtering
        - 30-day trend analysis
        - Point distribution analytics
        
        **Access Control:**
        - SUPER_USER: Can view all system analytics
        - ADMIN_USER: Can view analytics for users they created
        - GENERAL_USER: Can view their own analytics only
        """
        paths["/v1.0/analytics/dashboard"]["get"]["tags"] = ["Dashboard Analytics"]
    
    # User points analytics endpoint
    if "/v1.0/analytics/user_points" in paths:
        paths["/v1.0/analytics/user_points"]["get"]["summary"] = "Get Point Analytics"
        paths["/v1.0/analytics/user_points"]["get"]["description"] = """
        Get detailed point analytics and distribution metrics for administrative users.
        
        **Returns:**
        - Point allocation statistics by transaction type
        - Top users by current and total points
        - Point usage trends over last 30 days
        - Transaction count and average metrics
        
        **Analytics Features:**
        - Allocation type breakdown (allocation, deduction, etc.)
        - Top 10 users ranking by points
        - Daily usage trend analysis
        - Average points per transaction
        
        **Access Control:**
        - SUPER_USER: Can view all point analytics
        - ADMIN_USER: Can view analytics for users they created
        """
        paths["/v1.0/analytics/user_points"]["get"]["tags"] = ["Point Analytics"]
    
    # User activity analytics endpoint
    if "/v1.0/analytics/user_activity" in paths:
        paths["/v1.0/analytics/user_activity"]["get"]["summary"] = "Get User Activity Analytics"
        paths["/v1.0/analytics/user_activity"]["get"]["description"] = """
        Get comprehensive user activity analytics for a specified date range with detailed user behavior insights.
        
        **Parameters:**
        - start_date: Start date in YYYY-MM-DD format
        - end_date: End date in YYYY-MM-DD format
        - user_role: Optional filter by user role
        
        **Returns:**
        - Summary statistics (active users, new users, API requests)
        - Individual user activity details (up to 50 users)
        - Daily active users trend
        - Peak usage hours analysis
        
        **User Activity Details:**
        - Total API requests per user
        - Points used during the period
        - Active days count
        - Favorite endpoints accessed
        
        **Access Control:**
        - SUPER_USER: Can view all user activity
        - ADMIN_USER: Can view activity for users they created
        """
        paths["/v1.0/analytics/user_activity"]["get"]["tags"] = ["User Activity Analytics"]
    
    # User engagement analytics endpoint
    if "/v1.0/analytics/user_engagement" in paths:
        paths["/v1.0/analytics/user_engagement"]["get"]["summary"] = "Get User Engagement Metrics"
        paths["/v1.0/analytics/user_engagement"]["get"]["description"] = """
        Get comprehensive user engagement metrics including DAU/WAU/MAU, feature adoption, and user segmentation.
        
        **Engagement Metrics:**
        - Daily Active Users (DAU) - users active in last 24 hours
        - Weekly Active Users (WAU) - users active in last 7 days
        - Monthly Active Users (MAU) - users active in last 30 days
        - User retention rate (month-over-month)
        - Average session duration
        
        **Feature Adoption:**
        - Hotel search feature usage and adoption rate
        - Booking management feature usage and adoption rate
        - Unique users per feature
        - Feature usage counts
        
        **User Segmentation:**
        - Power users (high transaction frequency)
        - Casual users (low transaction frequency)
        - Average requests per day by segment
        - Points consumption patterns
        
        **Access Control:**
        - SUPER_USER: Can view all engagement metrics
        - ADMIN_USER: Can view metrics for users they created
        """
        paths["/v1.0/analytics/user_engagement"]["get"]["tags"] = ["User Engagement Analytics"]
    
    # System health analytics endpoint
    if "/v1.0/analytics/system_health" in paths:
        paths["/v1.0/analytics/system_health"]["get"]["summary"] = "Get System Health Metrics"
        paths["/v1.0/analytics/system_health"]["get"]["description"] = """
        Get comprehensive system health metrics including performance indicators, API statistics, and database health.
        
        **System Status:**
        - Overall system health status (healthy/degraded)
        - System uptime percentage
        - Last updated timestamp
        
        **Performance Metrics:**
        - Average response time across all endpoints
        - Requests per second capacity
        - Error rate percentage
        - CPU, memory, and disk usage
        
        **API Endpoints Statistics:**
        - Individual endpoint performance metrics
        - Success rates and error counts
        - Response time per endpoint
        - Request volume per endpoint
        
        **Database Metrics:**
        - Connection pool usage
        - Average query execution time
        - Slow queries count
        - Active database connections
        
        **Access Control:**
        - SUPER_USER: Can view all system health metrics
        - ADMIN_USER: Can view system health metrics
        """
        paths["/v1.0/analytics/system_health"]["get"]["tags"] = ["System Health Analytics"]
    
    # Dashboard user activity endpoint
    if "/v1.0/dashboard/user_activity" in paths:
        paths["/v1.0/dashboard/user_activity"]["get"]["summary"] = "Get Dashboard User Activity"
        paths["/v1.0/dashboard/user_activity"]["get"]["description"] = """
        Get user activity analytics specifically formatted for dashboard display over a configurable time period.
        
        **Parameters:**
        - days: Number of days to analyze (1-365, default: 30)
        
        **Returns:**
        - Daily activity trends with activity counts and unique users
        - Most active users (top 10) with activity counts
        - Activity breakdown by type (hotel operations, user logins)
        
        **Daily Activity Trends:**
        - Date-wise activity counts
        - Unique active users per day
        - Transaction and activity log aggregation
        
        **Most Active Users:**
        - User identification and role information
        - Total activity count in the period
        - Ranked by activity volume
        
        **Activity Types:**
        - Hotel created, updated, deleted operations
        - User login activities
        - System interactions
        
        **Access Control:**
        - SUPER_USER: Can view all user activity
        - ADMIN_USER: Can view activity for users they created
        """
        paths["/v1.0/dashboard/user_activity"]["get"]["tags"] = ["Dashboard Analytics"]


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
    
    # Analytics Response Schemas
    schemas["DashboardAnalytics"] = {
        "type": "object",
        "properties": {
            "statistics": {"$ref": "#/components/schemas/UserStatistics"},
            "user_creation_trend": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "date": {"type": "string", "format": "date"},
                        "count": {"type": "integer"}
                    }
                }
            },
            "point_distribution": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "role": {"type": "string"},
                        "total_points": {"type": "integer"},
                        "user_count": {"type": "integer"},
                        "average_points": {"type": "number"}
                    }
                }
            },
            "activity_summary": {
                "type": "object",
                "properties": {
                    "active_users_last_7_days": {"type": "integer"},
                    "total_transactions_last_30_days": {"type": "integer"}
                }
            },
            "generated_at": {"type": "string", "format": "date-time"}
        }
    }
    
    schemas["PointAnalytics"] = {
        "type": "object",
        "properties": {
            "allocation_statistics": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "allocation_type": {"type": "string"},
                        "total_points": {"type": "integer"},
                        "transaction_count": {"type": "integer"},
                        "average_per_transaction": {"type": "number"}
                    }
                }
            },
            "top_users": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "username": {"type": "string"},
                        "email": {"type": "string"},
                        "current_points": {"type": "integer"},
                        "total_points": {"type": "integer"}
                    }
                }
            },
            "usage_trend": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "date": {"type": "string", "format": "date"},
                        "points_used": {"type": "integer"}
                    }
                }
            },
            "generated_at": {"type": "string", "format": "date-time"}
        }
    }
    
    schemas["UserActivityAnalytics"] = {
        "type": "object",
        "properties": {
            "summary": {
                "type": "object",
                "properties": {
                    "total_active_users": {"type": "integer"},
                    "new_users_this_period": {"type": "integer"},
                    "total_api_requests": {"type": "integer"},
                    "average_requests_per_user": {"type": "number"}
                }
            },
            "user_activity": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "user_id": {"type": "string"},
                        "username": {"type": "string"},
                        "email": {"type": "string"},
                        "role": {"type": "string"},
                        "last_login": {"type": "string", "format": "date-time"},
                        "total_requests": {"type": "integer"},
                        "points_used": {"type": "integer"},
                        "active_days": {"type": "integer"},
                        "favorite_endpoints": {
                            "type": "array",
                            "items": {"type": "string"}
                        }
                    }
                }
            },
            "activity_trends": {
                "type": "object",
                "properties": {
                    "daily_active_users": {
                        "type": "array",
                        "items": {
                            "type": "object",
                            "properties": {
                                "date": {"type": "string", "format": "date"},
                                "count": {"type": "integer"}
                            }
                        }
                    },
                    "peak_usage_hours": {
                        "type": "array",
                        "items": {
                            "type": "object",
                            "properties": {
                                "hour": {"type": "integer"},
                                "requests": {"type": "integer"}
                            }
                        }
                    }
                }
            }
        }
    }
    
    schemas["UserEngagementMetrics"] = {
        "type": "object",
        "properties": {
            "engagement_metrics": {
                "type": "object",
                "properties": {
                    "daily_active_users": {"type": "integer"},
                    "weekly_active_users": {"type": "integer"},
                    "monthly_active_users": {"type": "integer"},
                    "user_retention_rate": {"type": "number"},
                    "average_session_duration": {"type": "string"}
                }
            },
            "feature_adoption": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "feature": {"type": "string"},
                        "usage_count": {"type": "integer"},
                        "unique_users": {"type": "integer"},
                        "adoption_rate": {"type": "number"}
                    }
                }
            },
            "user_segments": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "segment": {"type": "string"},
                        "count": {"type": "integer"},
                        "avg_requests_per_day": {"type": "integer"},
                        "points_consumption": {"type": "string"}
                    }
                }
            }
        }
    }
    
    schemas["SystemHealthMetrics"] = {
        "type": "object",
        "properties": {
            "system_status": {"type": "string", "enum": ["healthy", "degraded", "critical"]},
            "uptime": {"type": "string"},
            "last_updated": {"type": "string", "format": "date-time"},
            "performance_metrics": {
                "type": "object",
                "properties": {
                    "avg_response_time": {"type": "integer"},
                    "requests_per_second": {"type": "integer"},
                    "error_rate": {"type": "number"},
                    "cpu_usage": {"type": "number"},
                    "memory_usage": {"type": "number"},
                    "disk_usage": {"type": "number"}
                }
            },
            "api_endpoints": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "endpoint": {"type": "string"},
                        "avg_response_time": {"type": "integer"},
                        "success_rate": {"type": "number"},
                        "requests_count": {"type": "integer"},
                        "error_count": {"type": "integer"}
                    }
                }
            },
            "database_metrics": {
                "type": "object",
                "properties": {
                    "connection_pool_usage": {"type": "integer"},
                    "query_avg_time": {"type": "integer"},
                    "slow_queries_count": {"type": "integer"},
                    "active_connections": {"type": "integer"}
                }
            }
        }
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


def add_analytics_examples(paths):
    """Add example responses for analytics endpoints"""
    
    # Dashboard analytics examples
    if "/v1.0/analytics/dashboard" in paths and "get" in paths["/v1.0/analytics/dashboard"]:
        endpoint = paths["/v1.0/analytics/dashboard"]["get"]
        endpoint["responses"] = {
            "200": {
                "description": "Dashboard analytics data",
                "content": {
                    "application/json": {
                        "schema": {"$ref": "#/components/schemas/DashboardAnalytics"},
                        "example": {
                            "statistics": {
                                "total_users": 150,
                                "super_users": 2,
                                "admin_users": 8,
                                "general_users": 140,
                                "active_users": 95,
                                "inactive_users": 55,
                                "total_points_distributed": 500000,
                                "recent_signups": 12
                            },
                            "user_creation_trend": [
                                {"date": "2024-01-01", "count": 5},
                                {"date": "2024-01-02", "count": 3}
                            ],
                            "point_distribution": [
                                {
                                    "role": "GENERAL_USER",
                                    "total_points": 450000,
                                    "user_count": 140,
                                    "average_points": 3214.3
                                }
                            ],
                            "activity_summary": {
                                "active_users_last_7_days": 45,
                                "total_transactions_last_30_days": 1250
                            },
                            "generated_at": "2024-01-15T10:30:00Z"
                        }
                    }
                }
            }
        }
    
    # User activity analytics examples
    if "/v1.0/analytics/user_activity" in paths and "get" in paths["/v1.0/analytics/user_activity"]:
        endpoint = paths["/v1.0/analytics/user_activity"]["get"]
        endpoint["responses"] = {
            "200": {
                "description": "User activity analytics data",
                "content": {
                    "application/json": {
                        "schema": {"$ref": "#/components/schemas/UserActivityAnalytics"},
                        "example": {
                            "summary": {
                                "total_active_users": 45,
                                "new_users_this_period": 8,
                                "total_api_requests": 1250,
                                "average_requests_per_user": 27.78
                            },
                            "user_activity": [
                                {
                                    "user_id": "user_123",
                                    "username": "john_doe",
                                    "email": "john@example.com",
                                    "role": "GENERAL_USER",
                                    "last_login": "2024-01-14T15:30:00Z",
                                    "total_requests": 45,
                                    "points_used": 450,
                                    "active_days": 12,
                                    "favorite_endpoints": ["/v1.0/hotel/details", "/v1.0/content/get_all_hotel_info"]
                                }
                            ],
                            "activity_trends": {
                                "daily_active_users": [
                                    {"date": "2024-01-01", "count": 25},
                                    {"date": "2024-01-02", "count": 30}
                                ],
                                "peak_usage_hours": [
                                    {"hour": 9, "requests": 100},
                                    {"hour": 14, "requests": 150}
                                ]
                            }
                        }
                    }
                }
            }
        }
    
    # System health examples
    if "/v1.0/analytics/system_health" in paths and "get" in paths["/v1.0/analytics/system_health"]:
        endpoint = paths["/v1.0/analytics/system_health"]["get"]
        endpoint["responses"] = {
            "200": {
                "description": "System health metrics",
                "content": {
                    "application/json": {
                        "schema": {"$ref": "#/components/schemas/SystemHealthMetrics"},
                        "example": {
                            "system_status": "healthy",
                            "uptime": "99.97%",
                            "last_updated": "2024-01-15T10:30:00Z",
                            "performance_metrics": {
                                "avg_response_time": 245,
                                "requests_per_second": 125,
                                "error_rate": 0.02,
                                "cpu_usage": 45.5,
                                "memory_usage": 67.2,
                                "disk_usage": 38.1
                            },
                            "api_endpoints": [
                                {
                                    "endpoint": "/v1.0/hotels/search",
                                    "avg_response_time": 180,
                                    "success_rate": 99.8,
                                    "requests_count": 850,
                                    "error_count": 2
                                }
                            ],
                            "database_metrics": {
                                "connection_pool_usage": 75,
                                "query_avg_time": 45,
                                "slow_queries_count": 12,
                                "active_connections": 150
                            }
                        }
                    }
                }
            }
        }


# Remove this line - it causes circular reference and breaks docs
# The openapi method is properly set in main.py 