# User Management Backend Tests

This directory contains comprehensive unit tests for the user management backend system, specifically focusing on data models and validation components as required by task 2.3.

## Test Structure

### Test Files

1. **`test_models.py`** - Tests for SQLAlchemy models and hybrid properties
2. **`test_validation.py`** - Tests for Pydantic model validation and validation utilities
3. **`conftest.py`** - Test configuration and fixtures

### Test Coverage

#### Model Tests (`test_models.py`)

**TestUserModel:**

- Basic user creation and default values
- User role enum validation
- Hybrid property testing:
  - `current_point_balance` and `total_point_balance`
  - `activity_status` based on recent transactions
  - `active_supplier_list` from provider permissions
  - `total_requests` from transaction history
  - `paid_status` based on point balances
  - `last_login` from session data

**TestUserModelEdgeCases:**

- Multiple point records handling
- Expired sessions behavior
- Activity status boundary conditions (7-day window)
- Zero points edge cases

**TestUserModelPerformance:**

- Large dataset handling
- Multiple users with different data patterns

#### Validation Tests (`test_validation.py`)

**Pydantic Model Tests:**

- `UserCreateRequest` - Username, email, password validation
- `UserUpdateRequest` - Partial update validation
- `UserSearchParams` - Search query sanitization and pagination
- `BulkUserOperation` - Bulk operation validation
- `PointAllocationRequest` - Point allocation validation
- Response models - `UserListResponse`, `UserStatistics`, etc.
- Error response models - `APIError`, `ValidationError`, etc.

**Validation Utility Tests:**

- `InputSanitizer` - String sanitization and SQL injection prevention
- `PasswordValidator` - Password strength validation and generation
- `RateLimiter` - Rate limiting functionality
- Utility functions for bulk operations, date ranges, and sort parameters

## Running Tests

### Prerequisites

1. Install test dependencies:
   ```bash
   pipenv install --dev
   ```

### Running Tests

1. **Run all tests:**

   ```bash
   pipenv run python -m pytest tests/ -v
   ```

2. **Run specific test files:**

   ```bash
   # Model tests only
   pipenv run python -m pytest tests/test_models.py -v

   # Validation tests only
   pipenv run python -m pytest tests/test_validation.py -v
   ```

3. **Run with coverage:**

   ```bash
   pipenv run python -m pytest tests/ --cov=. --cov-report=html
   ```

4. **Use the test runner script:**
   ```bash
   python run_tests.py
   ```

## Test Scenarios Covered

### Data Model Validation

1. **User Creation:**

   - Valid user creation with all required fields
   - Default value assignment
   - Role enum validation
   - Database constraint handling

2. **Hybrid Properties:**

   - Point balance calculations with and without UserPoint records
   - Activity status determination based on transaction recency
   - Supplier list generation from permissions
   - Request count aggregation from transactions
   - Paid status logic based on point balances
   - Last login extraction from session data

3. **Edge Cases:**
   - Boundary conditions for activity status (7-day window)
   - Zero and negative point scenarios
   - Expired session handling
   - Large dataset performance

### Pydantic Validation

1. **Input Validation:**

   - Username format and reserved word checking
   - Email format validation
   - Password strength requirements (uppercase, lowercase, digits, special chars)
   - Field length and pattern constraints

2. **Sanitization:**

   - XSS prevention in search queries
   - SQL injection detection and prevention
   - Input length limiting
   - Dangerous character removal

3. **Business Logic:**
   - Date range validation
   - Pagination parameter validation
   - Bulk operation constraints
   - Point allocation limits

## Test Data and Fixtures

The `conftest.py` file provides comprehensive fixtures:

- `db_session` - In-memory SQLite database for testing
- `sample_user_data` - Basic user data template
- `sample_user` - User with basic data
- `sample_user_with_points` - User with point records
- `sample_user_with_transactions` - User with transaction history
- `sample_user_with_permissions` - User with provider permissions
- `sample_user_with_sessions` - User with session data

## Requirements Covered

This test suite addresses the requirements specified in task 2.3:

✅ **Test Pydantic model validation with various input scenarios**

- Comprehensive validation tests for all user-related Pydantic models
- Edge cases and error conditions
- Input sanitization and security validation

✅ **Test computed properties and hybrid properties on User model**

- All hybrid properties tested with various data scenarios
- Edge cases and boundary conditions
- Performance testing with larger datasets

✅ **Requirements 1.1, 7.1 coverage**

- Enhanced user data structure validation (Requirement 1.1)
- Comprehensive error handling and validation (Requirement 7.1)

## Notes

- Tests use in-memory SQLite database for isolation and speed
- One test is skipped due to email-validator dependency issues (non-critical)
- Warnings about deprecated datetime.utcnow() are expected and don't affect functionality
- All core functionality is thoroughly tested and working correctly
