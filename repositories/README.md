# Enhanced User Repository Layer

This directory contains the enhanced user repository layer implementation for the user management backend update.

## Files Created

### Core Repository

- **`user_repository.py`** - Main repository class with optimized database queries
- **`query_builders.py`** - Advanced query building utilities
- **`repository_config.py`** - Configuration, caching, and performance monitoring

### Database Migration

- **`../migrations/add_user_indexes.py`** - Database indexes for query optimization

### Testing

- **`../test_repository.py`** - Test script for repository functionality

## Features Implemented

### 3.1 Optimized Database Queries ✅

- **UserRepository class** with efficient pagination queries
- **Database-level aggregation** for user statistics using `func.sum()` and `case()` statements
- **Eager loading** with `selectinload()` for related data (user_points, provider_permissions)
- **Optimized joins** to avoid N+1 query problems
- **Database indexes** created for frequently queried fields:
  - User table: email, role, is_active, created_at, created_by
  - Composite indexes: role+is_active, is_active+created_at
  - UserPoint table: user_id, current_points, total_points
  - PointTransaction table: giver_id, receiver_id, created_at with composite indexes
  - UserProviderPermission table: user_id, provider_name

### 3.2 Filtering and Sorting Capabilities ✅

- **Dynamic query building** with `UserFilters` dataclass supporting:

  - Text search across username, email, and ID fields
  - Role filtering (super_user, admin_user, general_user)
  - Active status filtering
  - Date range filtering (created_after, created_before)
  - Point balance filtering (has_points, min_points, max_points)
  - Activity status filtering (Active/Inactive based on recent transactions)

- **Multi-field sorting** with `SortConfig` dataclass supporting:

  - Sort by: username, email, role, created_at, updated_at, is_active, points
  - Sort order: ascending or descending
  - Optimized sorting with proper database indexes

- **Advanced query optimization** for large datasets:
  - Cursor-based pagination for better performance on large datasets
  - Deep pagination optimization (page > 100)
  - Query performance monitoring and caching
  - Bulk operations support

## Key Methods

### Core Repository Methods

- `get_users_with_pagination()` - Basic pagination with filtering and sorting
- `get_user_statistics()` - Efficient database-level aggregation for statistics
- `search_users()` - Text search with database indexes
- `get_user_with_details()` - Single user with all related data
- `get_users_by_creator()` - Users created by specific creator (role-based access)

### Advanced Methods

- `get_users_with_advanced_filters()` - Advanced filtering with metadata
- `get_users_by_role_hierarchy()` - Role-based access control
- `build_dynamic_query()` - Dynamic query building from parameters
- `get_user_statistics_by_filters()` - Statistics for filtered user sets
- `optimize_query_for_large_datasets()` - Performance optimization for large datasets

### Utility Methods

- `get_active_users_in_period()` - Users active in specified time period
- `get_user_activity_summary()` - Activity summary for individual users
- `bulk_update_users()` - Bulk operations for better performance

## Performance Features

### Caching

- **Query result caching** with configurable TTL (5 minutes default)
- **Cache key generation** based on query parameters
- **Automatic cache invalidation** for expired entries

### Monitoring

- **Performance monitoring** with execution time tracking
- **Query statistics** collection and analysis
- **Optimization suggestions** based on query patterns
- **Slow query detection** with configurable thresholds

### Configuration

- **Configurable pagination** limits (default: 25, max: 100)
- **Large dataset thresholds** for optimization strategies
- **Cache settings** (TTL, max size)
- **Performance thresholds** for monitoring

## Database Indexes Created

The migration script created the following indexes for optimal query performance:

```sql
-- User table indexes
CREATE INDEX idx_users_email ON users(email);
CREATE INDEX idx_users_role ON users(role);
CREATE INDEX idx_users_is_active ON users(is_active);
CREATE INDEX idx_users_created_at ON users(created_at);
CREATE INDEX idx_users_created_by ON users(created_by);

-- Composite indexes
CREATE INDEX idx_users_role_active ON users(role, is_active);
CREATE INDEX idx_users_active_created ON users(is_active, created_at);

-- Related table indexes
CREATE INDEX idx_user_points_user_id ON user_points(user_id);
CREATE INDEX idx_user_points_current_points ON user_points(current_points);
CREATE INDEX idx_point_transactions_giver_id ON point_transactions(giver_id);
CREATE INDEX idx_point_transactions_receiver_id ON point_transactions(receiver_id);
CREATE INDEX idx_point_transactions_created_at ON point_transactions(created_at);
-- ... and more composite indexes for optimal query performance
```

## Test Results

All repository functionality has been tested and verified:

✅ Repository initialization  
✅ User statistics retrieval (23 total users: 2 super, 5 admin, 16 general)  
✅ Basic pagination (5 users per page)  
✅ Search functionality (text search across username/email)  
✅ Role filtering (16 general users found)  
✅ Advanced filtering with metadata  
✅ Detailed user retrieval with related data

## Usage Example

```python
from repositories.user_repository import UserRepository, UserFilters, SortConfig
from database import get_db

# Initialize repository
db = next(get_db())
repo = UserRepository(db)

# Get paginated users with filtering
filters = UserFilters(
    role=UserRole.GENERAL_USER,
    is_active=True,
    search="john"
)
sort_config = SortConfig(sort_by="created_at", sort_order="desc")

users, total = repo.get_users_with_pagination(
    page=1,
    limit=10,
    filters=filters,
    sort_config=sort_config
)

# Get user statistics
stats = repo.get_user_statistics()
print(f"Total users: {stats['total_users']}")
```

## Requirements Satisfied

This implementation satisfies the following requirements from the specification:

- **2.1**: Pagination with configurable page size ✅
- **2.2**: Search by username, email, and role ✅
- **2.3**: Filtering by role, active status, and creation date ✅
- **6.1**: Optimized database queries with proper joins ✅
- **6.2**: Efficient pagination for large datasets ✅

The repository layer is now ready to support the enhanced user service layer and API endpoints.
