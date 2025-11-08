from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.openapi.utils import get_openapi


def custom_openapi(app: FastAPI):
    # Force regeneration of schema for development (comment out for production)
    # if app.openapi_schema:
    #     return app.openapi_schema
    
    # Generate base schema
    openapi_schema = get_openapi(
        title=app.title,
        version=app.version,
        description=app.description,
        routes=app.routes,
    )
    
    # Manually add tags metadata - Define it here to ensure it's included
    tags_metadata = [
        {
            "name": "Authentication",
            "description": """
## 🔐 Authentication & Authorization API

**Comprehensive user authentication, authorization, and API key management system**

This API module provides complete user authentication, JWT token management, API key generation, and role-based access control for the hotel booking system. It ensures secure access to all system resources with comprehensive user management capabilities.

### 🔑 Key Features

**🔓 User Authentication:**
- JWT-based authentication with access and refresh tokens
- OAuth2 password flow implementation
- Secure password hashing and validation
- Multi-device session management
- Token refresh and automatic renewal

**🔑 API Key Management:**
- Personal API key generation and management
- Administrative API key management for users
- API key revocation and regeneration
- Secure API key authentication alongside JWT

**👥 User Registration & Management:**
- User registration with email validation
- User profile management and updates
- Account activation and deactivation
- Role-based user categorization

**🛡️ Security & Access Control:**
- Role-based access control (Super User, Admin, General User)
- Secure logout with token invalidation
- Multi-device logout functionality
- Comprehensive audit logging for security events

**⚙️ Administrative Functions:**
- Super user management capabilities
- User activation and deactivation controls
- Bulk user operations and management
- System health monitoring for authentication services

### 🎯 Available Operations

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/token` | POST | Login and obtain JWT access/refresh-token tokens |
| `/refresh-token` | POST | Refresh expired access tokens |
| `/register` | POST | Register new user accounts |
| `/logout` | POST | Logout from current device |
| `//logout-all` | POST | Logout from all devices |
| `/check-me` | GET | Get current user profile information |
| `/regenerate_api_key` | POST | Regenerate personal API key |
| `/generate_api_key/{user_id}` | POST | Generate API key for specific user (Admin) |
| `/revoke_api_key/{user_id}` | DELETE | Revoke API key for specific user (Admin) |
| `/health` | GET | Authentication service health check |
| `/super/users` | GET | Get all users (Super User only) |
| `/super/users/{user_id}/activate` | PUT | Activate/deactivate user accounts (Admin) |
| `/check-api-key` | GET | Get user profile using API key authentication |

### 🔄 Authentication Flow

1. **Registration** → Create new user account with email validation
2. **Login** → Authenticate with credentials and receive JWT tokens
3. **Access Resources** → Use access token for API requests
4. **Token Refresh** → Refresh expired tokens using refresh token
5. **API Key Usage** → Alternative authentication using personal API keys
6. **Logout** → Invalidate tokens and end session

### 🛡️ Security Features

**Token Security:**
- JWT tokens with configurable expiration times
- Secure token storage and validation
- Automatic token refresh mechanisms
- Token blacklisting for logout functionality

**Password Security:**
- Bcrypt password hashing with salt
- Password strength validation
- Secure password reset mechanisms
- Protection against brute force attacks

**API Key Security:**
- Cryptographically secure API key generation
- API key scoping and permissions
- Secure key storage and validation
- Key rotation and revocation capabilities

### 👤 User Roles & Permissions

**Super User:**
- Full system access and administrative privileges
- User management and activation controls
- API key management for all users
- System configuration and monitoring

**Admin User:**
- User management within their scope
- API key generation for managed users
- Access to administrative functions
- User activation and deactivation

**General User:**
- Personal profile management
- Personal API key management
- Access to assigned resources
- Basic authentication functions

### 🔒 Security Best Practices

- All passwords are hashed using bcrypt with salt
- JWT tokens include user role and permissions
- API keys are generated using cryptographically secure methods
- All authentication events are logged for audit purposes
- Rate limiting and brute force protection implemented
- Secure token storage and transmission protocols

### 📊 Authentication Analytics

- User login/logout tracking and analytics
- Failed authentication attempt monitoring
- API key usage statistics and monitoring
- Session duration and activity tracking
- Security event logging and alerting

### 🚨 Error Handling

Comprehensive error handling with standardized HTTP status codes:

- **400 Bad Request**: Invalid credentials or malformed requests
- **401 Unauthorized**: Missing or invalid authentication tokens
- **403 Forbidden**: Insufficient permissions for requested operation
- **404 Not Found**: User or resource not found
- **409 Conflict**: Duplicate user registration or conflicts
- **422 Unprocessable Entity**: Validation errors in request data
- **500 Internal Server Error**: System errors or authentication failures
            """,
        },
        {
            "name": "User Profile",
            "description": """
# 👤 User Profile & Account Management API

**Comprehensive user profile management and account information system**

This API module provides complete user profile management, account information retrieval, and personal data management capabilities. It enables users to manage their profiles, view account details, and access personalized information within the hotel booking system.

### 🔑 Key Features

**👤 Profile Management:**
- Complete user profile information retrieval
- Personal account details and settings
- User activity history and engagement metrics
- Role and permission information display

**📊 Account Information:**
- Current point balance and transaction history
- API key management and access credentials
- Account status and activity tracking
- Personal preferences and settings

**🔐 Security & Privacy:**
- Secure profile data access with authentication
- Personal information protection and validation
- Account security status and monitoring
- Privacy-compliant data handling

**📈 Activity & Analytics:**
- User activity history and patterns
- Engagement metrics and statistics
- Transaction history and point usage
- Account usage analytics and insights

### 🎯 Available Operations

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/v1.0/user/check-me` | GET | Get current user profile and account information |


### 🔄 Profile Access Flow

1. **Authentication** → Authenticate using JWT token or API key
2. **Profile Retrieval** → Access personal profile information
3. **Account Details** → View account status, points, and settings
4. **Activity History** → Review account activity and transactions
5. **Security Info** → Check account security and API key status

### 📋 Profile Information Included

**Basic Profile Data:**
- User ID, username, and email address
- Full name and contact information
- Account creation date and last login
- User role and permission level

**Account Status:**
- Account activation status (active/inactive)
- Email verification status
- Account security settings
- Login history and device information

**Points & Transactions:**
- Current point balance and total points earned
- Point transaction history (received vs used)
- Point allocation details and sources
- Payment status and point usage analytics

**API Access:**
- Personal API key information and status
- API usage statistics and limits
- Authentication method preferences
- Access token information and expiry

**Activity & Engagement:**
- Recent login activity and patterns
- API request history and usage
- Feature usage and engagement metrics
- Account interaction statistics

### 🛡️ Security & Access Control

**Authentication Methods:**
- JWT Bearer token authentication
- API key authentication
- Session-based authentication
- Multi-factor authentication support

**Access Levels:**
- **Personal Access**: Users can view their own profile information
- **Administrative Access**: Admins can view user details they manage
- **Super User Access**: Full access to all user profile information
- **Audit Access**: Read-only access for compliance and monitoring

**Data Protection:**
- Sensitive information masking and filtering
- Role-based data visibility controls
- Audit logging for profile access events
- GDPR-compliant data handling practices

### 📊 Profile Analytics

**User Engagement Metrics:**
- Login frequency and session duration
- Feature usage patterns and preferences
- API request patterns and frequency
- Account activity trends over time

**Account Health Indicators:**
- Account security score and status
- Profile completeness percentage
- Activity level classification
- Account risk assessment metrics

**Usage Statistics:**
- Total API requests and usage patterns
- Point earning and spending behavior
- Feature adoption and usage rates
- Account growth and engagement trends

### 🔧 Profile Management Features

**Self-Service Capabilities:**
- Profile information viewing and validation
- Account status monitoring and alerts
- Personal API key management
- Activity history review and analysis

**Administrative Functions:**
- User profile oversight and management
- Account status modification and control
- Bulk user information retrieval
- User activity monitoring and reporting

### 🚨 Error Handling

Comprehensive error handling with standardized HTTP status codes:

- **400 Bad Request**: Invalid profile request parameters
- **401 Unauthorized**: Missing or invalid authentication credentials
- **403 Forbidden**: Insufficient permissions to access profile data
- **404 Not Found**: User profile or requested information not found
- **429 Too Many Requests**: Rate limit exceeded for profile requests
- **500 Internal Server Error**: System errors during profile retrieval

### 🔍 Use Cases

**End User Applications:**
- User dashboard and profile display
- Account settings and preferences management
- Activity history and transaction review
- API key management and security monitoring

**Administrative Applications:**
- User management and oversight dashboards
- Account status monitoring and reporting
- User activity analysis and insights
- Compliance and audit reporting

**Integration Applications:**
- User information retrieval for external systems
- Profile data synchronization and updates
- Authentication and authorization validation
- User analytics and reporting integration
            """,
        },
        {
            "name": "Hotels Integrations & Mapping",
            "description": """
## 🏨 Hotel Integration & Mapping API

**Comprehensive hotel data management and supplier integration system**

This API module provides complete hotel data management, supplier integration, and provider mapping functionality for the hotel booking system. It enables seamless integration with multiple hotel suppliers and provides robust hotel data management capabilities.

### 🔑 Key Features

**🏨 Hotel Management:**
- Complete hotel record creation with all associated data (locations, contacts, chains)
- Transactional integrity with automatic rollback on errors
- Comprehensive validation and error handling
- Automatic ITTID generation and relationship management

**🔗 Provider Integration:**
- Multi-supplier hotel mapping and integration (Booking.com, Expedia, etc.)
- Duplicate detection and prevention
- Provider-specific hotel ID management
- System type classification (OTA, GDS, Direct) and metadata handling

**🔐 Access Control & Security:**
- Role-based access control (Super User, Admin, General User)
- User permission validation and tracking
- Comprehensive audit logging for all operations
- Secure authentication and authorization

**📊 Supplier Management:**
- Supplier information retrieval and analytics
- User-specific supplier access management
- Hotel count statistics and availability tracking
- System integration status monitoring

### 🎯 Available Operations

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/input_hotel_all_details` | POST | Create complete hotel records with all related data |
| `/add_provider_all_details_with_ittid` | POST | Add provider mappings to existing hotels |
| `/get-supplier-info` | GET | Retrieve supplier information and hotel counts |
| `/check-my-active-suppliers-info` | GET | Get user's accessible supplier list with analytics |

### 🔄 Integration Workflow

1. **Hotel Creation** → Create complete hotel records with all related data
2. **Provider Mapping** → Add supplier-specific hotel IDs and mappings  
3. **Access Management** → Configure user permissions for supplier access
4. **Data Validation** → Ensure data integrity and prevent duplicates
5. **Monitoring** → Track supplier availability and system health

### 🛡️ Security & Permissions

- **Super User**: Full access to all hotel and supplier operations
- **Admin User**: Full access to all hotel and supplier operations
- **General User**: Limited access based on explicit supplier permissions

All operations are logged for audit purposes and include comprehensive error handling with detailed error messages.
            """,
        },
        {
            "name": "Hotel mapping",
            "description": """
# 🗺️ Hotel Mapping & Rate Management API

**Advanced hotel mapping and rate type management system**

This API module provides specialized functionality for managing hotel provider mappings, rate types, and comprehensive hotel data retrieval with advanced filtering and pagination capabilities. It enables efficient management of hotel-provider relationships and rate information across multiple suppliers.

### 🔑 Key Features

**🗺️ Provider Mapping Management:**
- Add and update rate type information for hotel-provider combinations
- Comprehensive provider mapping validation and error handling
- Automatic creation or update of existing rate type records
- Transactional integrity with rollback on errors

**💰 Rate Type Management:**
- Room title and rate name management
- Sell per night pricing configuration
- Rate type information updates and modifications
- Historical tracking with created/updated timestamps

**📊 Advanced Data Retrieval:**
- Multi-supplier hotel mapping data with comprehensive filtering
- Country-based location filtering with ISO codes
- Pagination support with resume keys for large datasets
- Cached responses for improved performance (2-hour cache)

**🔍 Filtering & Search:**
- Filter by multiple supplier names simultaneously
- Country-based filtering using ISO country codes
- Configurable page limits (1-500 records per page)
- Resume key pagination for efficient large dataset navigation

### 🎯 Available Operations

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/add_rate_type_with_ittid_and_pid` | POST | Add or update rate type information for hotel-provider mapping |
| `/update_rate_type` | PUT | Update existing rate type information |
| `/get_basic_mapping_with_info` | GET | Retrieve comprehensive hotel mapping data with filtering |

### 🔄 Mapping Workflow

1. **Rate Type Creation** → Add rate information for hotel-provider combinations
2. **Rate Updates** → Modify existing rate type details and pricing
3. **Data Retrieval** → Query comprehensive mapping data with filters
4. **Pagination** → Navigate through large datasets efficiently
5. **Caching** → Leverage cached responses for improved performance

### 📋 Data Structure

**Rate Type Information:**
- Hotel ITTID (Internal Travel Technology ID)
- Provider mapping ID and relationship
- Room title and descriptive information
- Rate name and classification
- Sell per night pricing
- Creation and modification timestamps

**Mapping Response Data:**
- Provider-specific hotel IDs and mappings
- Hotel basic information (name, coordinates, rating)
- Location data (address, country, coordinates)
- Rate type details (room titles, rate names, pricing)
- External system IDs (Vervotech, Giata codes)
- Photo and media information

### 🔐 Access Control & Security

**Required Roles:**
- **Super User**: Full access to all mapping operations
- **Admin User**: Full access to all mapping operations
- **General User**: No access to mapping endpoints

**Security Features:**
- JWT token authentication required
- Role-based access validation
- Comprehensive audit logging
- Input validation and sanitization
- Error handling with detailed logging

### 📊 Performance & Caching

**Caching Strategy:**
- 2-hour cache expiration for mapping data retrieval
- Redis-based caching for improved response times
- Cache invalidation on data updates
- Optimized database queries with proper indexing

**Pagination Features:**
- Resume key-based pagination for consistent results
- Configurable page sizes (1-500 records)
- Total count information for UI pagination
- Efficient large dataset handling

### 🚨 Error Handling

Comprehensive error handling with standardized HTTP status codes:

- **400 Bad Request**: Invalid resume_key format or malformed requests
- **401 Unauthorized**: Missing or invalid authentication tokens
- **403 Forbidden**: Insufficient permissions (non-admin/super users)
- **404 Not Found**: Hotel, provider mapping, or rate type not found
- **422 Unprocessable Entity**: Validation errors in request parameters
- **500 Internal Server Error**: Database errors or system failures

### 🔍 Use Cases

**Rate Management:**
- Hotel rate configuration and updates
- Provider-specific pricing management
- Rate type categorization and organization
- Bulk rate updates and modifications

**Data Integration:**
- Multi-supplier data aggregation
- Hotel mapping data export and reporting
- Integration with external booking systems
- Data synchronization across platforms

**Analytics & Reporting:**
- Hotel availability and rate analysis
- Provider performance metrics
- Geographic distribution analysis
- Rate competitiveness reporting

### 📈 Response Formats

**JSON Response Structure:**
- Standardized response format with metadata
- File attachment headers for data export
- Comprehensive error messages with context
- Pagination metadata for navigation

**Data Export:**
- JSON file attachment format
- Comprehensive hotel mapping data
- Ready for integration with external systems
- Structured data for analytics and reporting
            """,
        },
        {
            "name": "Users Activity",
            "description": """
## 👥 User Management & Activity API

**Comprehensive user account management and activity tracking system**

This API module provides complete user lifecycle management, point allocation systems, supplier permissions, and detailed user activity tracking. It enables role-based user administration with comprehensive audit trails and flexible user management capabilities.

### 🔑 Key Features

**👤 User Account Management:**
- Complete user profile creation and management with role-based validation
- User authentication and profile information retrieval
- Role-based user creation (Super User, Admin User, General User)
- Account activation, deactivation, and comprehensive user lifecycle management

**💰 Point Management System:**
- Flexible point allocation with predefined package types
- Point balance tracking and transaction history
- Point reset capabilities for administrative control
- Comprehensive point usage analytics and reporting

**🔐 Role-Based Access Control:**
- Three-tier user role system (Super User, Admin User, General User)
- Hierarchical permission structure with role inheritance
- Role-specific operation permissions and access controls
- Administrative oversight and user management capabilities

**🏨 Supplier Permission Management:**
- User-specific supplier access permissions
- Role-based supplier access (unlimited for admins, specific for general users)
- Supplier permission validation and management
- Complete supplier catalog and availability tracking

### 🎯 Available Operations

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/check-me` | GET | Get current user profile and account information |
| `/` | POST | Create new user with role-based validation |
| `/create_super_user` | POST | Create super user accounts (super user only) |
| `/create_admin_user` | POST | Create admin user accounts (super user only) |
| `/create_general_user` | POST | Create general user accounts (admin/super user) |
| `/points/give` | POST | Allocate points to users with package types |
| `/reset_point/{user_id}/` | POST | Reset user points to zero (admin operation) |
| `/points-check` | GET | Get detailed point history and transactions |
| `/check/all` | GET | List all users with enhanced filtering and pagination |
| `/check-user-info/{user_id}` | GET | Get specific user information and details |
| `/active_my_supplier` | GET | Get user's accessible supplier permissions |
| `/check-available-suppliers` | GET | Get complete system supplier catalog |
| `/list` | GET | Enhanced paginated user listing with search |
| `/stats` | GET | Get comprehensive user statistics |
| `/{user_id}/details` | GET | Get detailed user information with analytics |
| `/{user_id}/activity` | GET | Get user activity and usage analytics |
| `/bulk` | POST | Perform bulk user operations (create/update/delete) |
| `/{user_id}` | PUT | Update user information with validation |
| `/{user_id}` | DELETE | Delete user with complete cleanup |
| `/enhanced/create` | POST | Enhanced user creation with comprehensive validation |
| `/health` | GET | User management service health check |

### 🔄 User Management Workflow

1. **User Creation** → Role-based user account creation with validation
2. **Point Allocation** → Assign points using predefined packages
3. **Permission Assignment** → Configure supplier access permissions
4. **Activity Monitoring** → Track user activity and usage patterns
5. **Account Management** → Update, deactivate, or delete user accounts

### 💰 Point Allocation Packages

**Package Types and Values:**
- **ADMIN_USER_PACKAGE**: 4,000,000 points (Administrative package)
- **ONE_YEAR_PACKAGE**: 1,000,000 points (Annual subscription)
- **ONE_MONTH_PACKAGE**: 80,000 points (Monthly subscription)
- **PER_REQUEST_POINT**: 10,000 points (Pay-per-request)
- **GUEST_POINT**: 1,000 points (Guest/trial access)

**Point Management Features:**
- Automatic point deduction for non-super users
- Unlimited points for super users
- Complete transaction logging and audit trail
- Point balance validation and insufficient funds handling

### 🔐 Role-Based Permissions

**Super User:**
- Create any user role (Super User, Admin User, General User)
- Unlimited point allocation capabilities
- Access to all suppliers and system functions
- Complete user management and administrative control

**Admin User:**
- Create General User accounts only
- Point allocation with balance deduction
- Access to all suppliers in the system
- User management for created accounts

**General User:**
- No user creation capabilities
- Limited to assigned supplier permissions
- Point consumption for API usage
- Personal profile and activity access only

### 📊 User Analytics & Reporting

**User Statistics:**
- Total user counts by role and status
- User creation trends and growth metrics
- Point distribution and usage analytics
- Activity patterns and engagement metrics

**Activity Tracking:**
- User login and session tracking
- API usage patterns and frequency
- Point transaction history and analysis
- Supplier access and usage monitoring

**Enhanced Features:**
- Pagination and search capabilities
- Advanced filtering by role, status, and activity
- Bulk operations for administrative efficiency
- Real-time statistics and health monitoring

### 🔍 Search & Filtering

**Advanced Search:**
- Username and email search capabilities
- Role-based filtering and sorting
- Activity status and date range filtering
- Pagination with configurable page sizes

**Bulk Operations:**
- Create multiple users simultaneously
- Update user information in batches
- Delete users with complete cleanup
- Administrative efficiency tools

### 🚨 Error Handling

Comprehensive error handling with standardized HTTP status codes:

- **400 Bad Request**: Invalid input data or validation failures
- **401 Unauthorized**: Missing or invalid authentication tokens
- **403 Forbidden**: Insufficient role permissions for operation
- **404 Not Found**: User, points, or supplier permissions not found
- **409 Conflict**: Duplicate user email or username conflicts
- **422 Unprocessable Entity**: Request validation errors
- **500 Internal Server Error**: Database errors or system failures

### 🔒 Security Features

**Authentication & Authorization:**
- JWT token-based authentication
- Role-based access control validation
- Session management and token validation
- Multi-device logout capabilities

**Data Protection:**
- Password hashing using bcrypt
- Sensitive data masking and filtering
- Audit logging for all user operations
- GDPR-compliant data handling

**Business Rules:**
- Role hierarchy enforcement
- Point allocation validation
- Supplier permission verification
- Account integrity maintenance

### 🔍 Use Cases

**Administrative Management:**
- User account provisioning and management
- Point allocation and balance management
- Supplier permission configuration
- System user analytics and reporting

**Self-Service Operations:**
- User profile management and updates
- Point balance checking and transaction history
- Supplier access verification
- Personal activity monitoring

**Integration Applications:**
- User data synchronization with external systems
- Automated user provisioning workflows
- Point system integration with billing
- Activity analytics for business intelligence

### 📈 Response Formats

**Standardized Responses:**
- Consistent JSON response structure
- Comprehensive error messages with context
- Pagination metadata for large datasets
- Activity and analytics data formatting

**Enhanced Features:**
- Real-time user statistics
- Activity trend analysis
- Point usage analytics
- Supplier access reporting
            """,
        },
    ]
    
    # Add tags to the schema
    openapi_schema["tags"] = tags_metadata
    
    # Also try to get tags from app if they exist and merge them
    if hasattr(app, 'tags_metadata') and app.tags_metadata:
        # Merge app tags with our defined tags, avoiding duplicates
        existing_tag_names = {tag["name"] for tag in tags_metadata}
        for app_tag in app.tags_metadata:
            if app_tag["name"] not in existing_tag_names:
                openapi_schema["tags"].append(app_tag)

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
    
    # Enhanced documentation for /v1.0/user/check-me endpoint
    if "/v1.0/user/check-me" in paths:
        paths["/v1.0/user/check-me"]["get"]["summary"] = "Get Current User Information"
        paths["/v1.0/user/check-me"]["get"]["description"] = """
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
        paths["/v1.0/user/check-me"]["get"]["tags"] = ["User Profile"]
    
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
    if "/v1.0/user/points-check" in paths:
        paths["/v1.0/user/points-check"]["get"]["summary"] = "Get Detailed Point Information"
        paths["/v1.0/user/points-check"]["get"]["description"] = """
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
        paths["/v1.0/user/points-check"]["get"]["tags"] = ["Point Management"]
    
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
    if "/v1.0/user/check-me" in paths and "get" in paths["/v1.0/user/check-me"]:
        endpoint = paths["/v1.0/user/check-me"]["get"]
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
                                    "favorite_endpoints": ["/v1.0/hotel/details", "/v1.0/content/get-all-basic-hotel-info"]
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


def get_swagger_ui_html(
    *,
    openapi_url: str,
    title: str,
    swagger_js_url: str = "https://cdn.jsdelivr.net/npm/swagger-ui-dist@5.9.0/swagger-ui-bundle.js",
    swagger_css_url: str = "https://cdn.jsdelivr.net/npm/swagger-ui-dist@5.9.0/swagger-ui.css",
    swagger_favicon_url: str = "https://fastapi.tiangolo.com/img/favicon.png",
    oauth2_redirect_url: str = None,
    init_oauth: dict = None,
    swagger_ui_parameters: dict = None,
) -> str:
    """
    Generate custom Swagger UI HTML with enhanced styling and features
    
    This function creates a customized Swagger UI interface with:
    - Professional Hotel API branding and styling
    - Enhanced user experience with loading screen
    - Custom CSS for better visual hierarchy
    - Interactive features and keyboard shortcuts
    - Responsive design for all devices
    """
    import json
    
    current_swagger_ui_parameters = {
        "dom_id": "#swagger-ui",
        "layout": "BaseLayout",
        "deepLinking": True,
        "showExtensions": True,
        "showCommonExtensions": True,
        "syntaxHighlight.theme": "arta",
        "defaultModelsExpandDepth": 2,
        "defaultModelExpandDepth": 2,
        "displayRequestDuration": True,
        "filter": True,
        "tryItOutEnabled": True,
        "supportedSubmitMethods": ["get", "post", "put", "delete", "patch"],
        "validatorUrl": None
    }
    if swagger_ui_parameters:
        current_swagger_ui_parameters.update(swagger_ui_parameters)

    oauth2_redirect_url_html = ""
    if oauth2_redirect_url:
        oauth2_redirect_url_html = f'"oauth2RedirectUrl": "{oauth2_redirect_url}",'

    init_oauth_html = ""
    if init_oauth:
        init_oauth_html = f"""
        ui.initOAuth({json.dumps(init_oauth)})
        """

    html = f"""
    <!DOCTYPE html>
    <html>
    <head>
        <title>{title}</title>
        <link rel="stylesheet" type="text/css" href="{swagger_css_url}" />
        <link rel="stylesheet" type="text/css" href="/static/css/swagger-ui-custom.css" />
        <link rel="icon" type="image/png" href="{swagger_favicon_url}" sizes="32x32" />
        <link rel="icon" type="image/png" href="{swagger_favicon_url}" sizes="16x16" />
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <style>
            body {{
                margin: 0;
                background: #fafafa;
                font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, "Helvetica Neue", Arial, sans-serif;
            }}
            
            /* Loading screen */
            .loading-screen {{
                position: fixed;
                top: 0;
                left: 0;
                width: 100%;
                height: 100%;
                background: linear-gradient(135deg, #2c5aa0 0%, #1e3a5f 100%);
                display: flex;
                justify-content: center;
                align-items: center;
                z-index: 9999;
                transition: opacity 0.5s ease-out;
            }}
            
            .loading-spinner {{
                width: 50px;
                height: 50px;
                border: 4px solid rgba(255,255,255,0.3);
                border-top: 4px solid white;
                border-radius: 50%;
                animation: spin 1s linear infinite;
            }}
            
            .loading-text {{
                color: white;
                font-size: 1.2em;
                margin-left: 20px;
                font-weight: 600;
            }}
            
            @keyframes spin {{
                0% {{ transform: rotate(0deg); }}
                100% {{ transform: rotate(360deg); }}
            }}
            
            /* Hide loading screen when content is ready */
            .loaded .loading-screen {{
                opacity: 0;
                pointer-events: none;
            }}
        </style>
    </head>
    <body>
        <!-- Loading Screen -->
        <div class="loading-screen" id="loading-screen">
            <div class="loading-spinner"></div>
            <div class="loading-text">Loading Hotel API Documentation...</div>
        </div>
        
        <!-- Swagger UI Container -->
        <div id="swagger-ui"></div>
        
        <script src="{swagger_js_url}"></script>
        <script>
            // Initialize Swagger UI
            const ui = SwaggerUIBundle({{
                url: '{openapi_url}',
                {oauth2_redirect_url_html}
                {json.dumps(current_swagger_ui_parameters)[1:-1]},
                presets: [
                    SwaggerUIBundle.presets.apis,
                    SwaggerUIStandalonePreset
                ],
                plugins: [
                    SwaggerUIBundle.plugins.DownloadUrl
                ],
                onComplete: function() {{
                    // Hide loading screen when Swagger UI is ready
                    setTimeout(function() {{
                        document.body.classList.add('loaded');
                        setTimeout(function() {{
                            document.getElementById('loading-screen').style.display = 'none';
                        }}, 500);
                    }}, 1000);
                    
                    // Add custom enhancements
                    addCustomEnhancements();
                }}
            }});
            
            {init_oauth_html}
            
            // Custom enhancements function
            function addCustomEnhancements() {{
                // Add API status indicator
                const topbar = document.querySelector('.topbar');
                if (topbar) {{
                    const statusIndicator = document.createElement('div');
                    statusIndicator.innerHTML = `
                        <div style="display: flex; align-items: center; margin-left: auto; margin-right: 20px;">
                            <div style="width: 8px; height: 8px; background: #28a745; border-radius: 50%; margin-right: 8px; animation: pulse 2s infinite;"></div>
                            <span style="color: white; font-size: 0.9em; font-weight: 500;">API Online</span>
                        </div>
                        <style>
                            @keyframes pulse {{
                                0% {{ opacity: 1; }}
                                50% {{ opacity: 0.5; }}
                                100% {{ opacity: 1; }}
                            }}
                        </style>
                    `;
                    topbar.appendChild(statusIndicator);
                }}
                
                // Add keyboard shortcuts info
                const infoSection = document.querySelector('.info');
                if (infoSection) {{
                    const shortcutsInfo = document.createElement('div');
                    shortcutsInfo.innerHTML = `
                        <div style="margin-top: 20px; padding: 15px; background: #e3f2fd; border-radius: 8px; border-left: 4px solid #2196f3;">
                            <h4 style="margin: 0 0 10px 0; color: #1976d2;">💡 Quick Tips</h4>
                            <ul style="margin: 0; padding-left: 20px; color: #424242;">
                                <li><strong>Ctrl + /</strong> - Focus search filter</li>
                                <li><strong>Expand All</strong> - Click any tag to expand/collapse all operations</li>
                                <li><strong>Try It Out</strong> - Test endpoints directly from the documentation</li>
                                <li><strong>Authentication</strong> - Use the 🔒 Authorize button to set your JWT token</li>
                            </ul>
                        </div>
                    `;
                    infoSection.appendChild(shortcutsInfo);
                }}
                
                // Add search functionality enhancement
                setTimeout(function() {{
                    const filterInput = document.querySelector('.filter input');
                    if (filterInput) {{
                        filterInput.placeholder = '🔍 Search endpoints, methods, or descriptions...';
                        filterInput.style.fontSize = '1em';
                        filterInput.style.padding = '10px 15px';
                        filterInput.style.borderRadius = '25px';
                        filterInput.style.border = '2px solid #e0e0e0';
                        filterInput.style.transition = 'all 0.3s ease';
                        
                        filterInput.addEventListener('focus', function() {{
                            this.style.borderColor = '#2c5aa0';
                            this.style.boxShadow = '0 0 0 3px rgba(44, 90, 160, 0.1)';
                        }});
                        
                        filterInput.addEventListener('blur', function() {{
                            this.style.borderColor = '#e0e0e0';
                            this.style.boxShadow = 'none';
                        }});
                    }}
                }}, 2000);
                
                // Add keyboard shortcut for search
                document.addEventListener('keydown', function(e) {{
                    if (e.ctrlKey && e.key === '/') {{
                        e.preventDefault();
                        const filterInput = document.querySelector('.filter input');
                        if (filterInput) {{
                            filterInput.focus();
                        }}
                    }}
                }});
            }}
            
            // Error handling
            window.addEventListener('error', function(e) {{
                console.error('Swagger UI Error:', e);
                document.body.classList.add('loaded');
                document.getElementById('loading-screen').style.display = 'none';
            }});
        </script>
    </body>
    </html>
    """
    
    return html


def create_custom_swagger_ui_response(app):
    """
    Create a custom Swagger UI HTML response with enhanced features
    
    This function generates the complete HTML response for the Swagger UI
    with all custom styling and interactive features applied.
    """
    from fastapi.responses import HTMLResponse
    
    return HTMLResponse(
        content=get_swagger_ui_html(
            openapi_url=app.openapi_url,
            title=f"{app.title} - Interactive API Documentation",
            swagger_ui_parameters=getattr(app, 'swagger_ui_parameters', {}),
            init_oauth=getattr(app, 'swagger_ui_init_oauth', {}),
        )
    ) 