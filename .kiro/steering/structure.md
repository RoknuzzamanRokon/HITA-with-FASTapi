---
inclusion: always
---

# Project Structure

## Core Application Files

- **main.py**: FastAPI application entry point, router registration, middleware configuration, startup events
- **database.py**: SQLAlchemy engine, session management, connection pooling, database dependency
- **models.py**: SQLAlchemy ORM models for all database tables (User, Hotel, Location, ProviderMapping, etc.)
- **schemas.py**: Pydantic models for request/response validation and serialization
- **utils.py**: General utility functions

## Directory Organization

### `/routes`

API endpoint definitions organized by feature domain:

- **auth.py**: Authentication (login, register, logout, password reset, API key management)
- **usersIntegrations.py**: User CRUD operations
- **hotelIntegration.py**: Hotel data management
- **locations.py**: Location-based hotel search
- **mapping.py**: Provider mapping operations
- **ml_mapping.py**: ML-assisted hotel mapping
- **permissions.py**: User permission management
- **cache_management.py**: Cache control endpoints
- **health.py**: Health check endpoints
- **analytics.py**: Analytics and reporting
- **dashboard.py**: Dashboard data endpoints

### `/repositories`

Data access layer with optimized queries:

- **user_repository.py**: User data access with pagination, filtering, sorting
- **query_builders.py**: Dynamic query construction utilities
- **repository_config.py**: Repository configuration, caching, performance monitoring
- **README.md**: Comprehensive documentation of repository patterns

### `/services`

Business logic layer:

- **user_service.py**: User management business logic
- **cached_user_service.py**: Cached user operations
- **permission_service.py**: Permission management logic
- **point_service.py**: Point allocation and transaction logic

### `/security`

Security features and middleware:

- **audit_logging.py**: Activity and security event logging
- **input_validation.py**: Input sanitization and validation
- **rate_limiting.py**: Rate limiting for API endpoints
- **middleware.py**: Security middleware stack
- **README.md**: Security implementation guide

### `/middleware`

Custom middleware components:

- **cache_invalidation.py**: Cache invalidation logic
- **ip_middleware.py**: IP address extraction and trusted proxy handling

### `/migrations`

Database migration scripts:

- **add_security_tables.py**: Security-related tables
- **add_user_indexes.py**: Performance indexes for user queries

### `/utils`

Utility scripts and helpers:

- **create_super_user.py**: Super user creation script
- **update_user_roles.py**: Bulk role updates
- **insert_mapping_data.py**: Mapping data import
- **api_documentation.py**: API documentation utilities

### `/static`

Static file storage:

- **/countryJson**: Country data JSON files
- **/countryJsonWithRate**: Country data with rate information
- **/hotelcontent**: Hotel content files
- **/read**: Read-only data files
- **/write**: Writable data files

### `/ml`

Machine learning components:

- **mapping_3.py**: ML mapping implementation
- **mapping_without_push.py**: ML mapping without database updates

### `/alembic`

Alembic migration management:

- **env.py**: Alembic environment configuration
- **/versions**: Migration version files

## Architecture Patterns

### Layered Architecture

```
Routes (API Layer)
    ↓
Services (Business Logic)
    ↓
Repositories (Data Access)
    ↓
Models (Database)
```

### Key Conventions

1. **Dependency Injection**: Use FastAPI's `Depends()` for database sessions and authentication
2. **Async/Await**: Prefer async endpoints for I/O operations
3. **Type Hints**: All functions use Python type hints
4. **Pydantic Validation**: Request/response validation via Pydantic schemas
5. **Error Handling**: Centralized error handlers in `error_handlers.py`
6. **Audit Logging**: Security-relevant actions logged via `AuditLogger`
7. **Rate Limiting**: Sensitive endpoints protected with `@rate_limit` decorator

### Database Conventions

- **Primary Keys**: String IDs for users (10 chars), Integer auto-increment for other entities
- **Timestamps**: `created_at` and `updated_at` on all major tables
- **Foreign Keys**: Enabled via PRAGMA for SQLite
- **Indexes**: Performance indexes on frequently queried fields
- **Enums**: SQLAlchemy Enum types for role, status fields

### API Conventions

- **Versioning**: All routes prefixed with `/v1.0/`
- **Authentication**: JWT Bearer tokens via `Authorization` header
- **API Keys**: Alternative auth via `api_key` for programmatic access
- **Response Format**: JSON with consistent error structure
- **Pagination**: Page-based with configurable limits
- **Filtering**: Query parameters for search and filter operations

### Naming Conventions

- **Files**: snake_case (e.g., `user_repository.py`)
- **Classes**: PascalCase (e.g., `UserRepository`)
- **Functions**: snake_case (e.g., `get_user_by_id`)
- **Constants**: UPPER_SNAKE_CASE (e.g., `ACCESS_TOKEN_EXPIRE_MINUTES`)
- **Database Tables**: snake_case plural (e.g., `users`, `hotels`)
- **Route Prefixes**: kebab-case (e.g., `/search-hotel-with-location`)
