# Implementation Plan

- [x] 1. Create helper functions for data retrieval and processing

  - [x] 1.1 Implement `get_user_account_info()` function

    - Write function to retrieve user account details from database
    - Calculate days since registration using datetime operations
    - Determine account status based on supplier and point allocation
    - Return structured dictionary with account information
    - _Requirements: 1.1, 1.2, 1.3, 1.4, 1.5_

  - [x] 1.2 Implement `calculate_onboarding_progress()` function

    - Check completion status of each onboarding step (account created, suppliers assigned, points allocated)
    - Calculate completion percentage based on completed steps
    - Generate list of pending actions with descriptions
    - Return onboarding progress dictionary
    - _Requirements: 1.5_

  - [x] 1.3 Implement `get_available_suppliers()` function

    - Query SupplierSummary table for all available suppliers
    - Extract supplier names, hotel counts, and last update timestamps
    - Format supplier information for response
    - Return list of supplier dictionaries
    - _Requirements: 2.1, 2.2_

  - [x] 1.4 Implement `get_available_packages()` function

    - Define static information for all point package types (admin, yearly, monthly, per-request, guest)
    - Include example point allocations for each package type
    - Return list of package dictionaries with descriptions
    - _Requirements: 2.3, 2.4_

  - [x] 1.5 Implement `get_user_login_time_series()` function

    - Query UserActivityLog table for login events filtered by user_id and date range
    - Group login events by date and count occurrences
    - Fill missing dates with zero values using helper function
    - Sort time-series data chronologically
    - Return list of date-value dictionaries
    - _Requirements: 4.1, 4.2, 4.4, 6.1, 6.2, 6.3, 6.4_

  - [x] 1.6 Implement `get_platform_registration_trends()` function

    - Query User table for registration dates within last 30 days
    - Group registrations by date and count new users per day
    - Fill missing dates with zero values
    - Sort time-series data chronologically
    - Return list of date-value dictionaries with metadata
    - _Requirements: 3.4, 6.1, 6.2, 6.3, 6.4, 6.5_

  - [x] 1.7 Implement `get_hotel_update_trends()` function

    - Query Hotel table for update timestamps within last 30 days
    - Group updates by date and count hotel updates per day
    - Fill missing dates with zero values
    - Sort time-series data chronologically
    - Return list of date-value dictionaries with metadata
    - _Requirements: 3.5, 6.1, 6.2, 6.3, 6.4, 6.5_

  - [x] 1.8 Implement `generate_recommendations()` function

    - Analyze user's current state (suppliers, points, activity)
    - Generate prioritized list of next steps based on missing resources
    - Include contact information for administrator support
    - Estimate time to complete each action
    - Return recommendations dictionary
    - _Requirements: 5.1, 5.2, 5.3, 5.4, 5.5_

  - [x] 1.9 Implement `fill_time_series_gaps()` utility function

    - Accept time-series data and target number of days
    - Generate complete date range for specified period
    - Fill missing dates with zero values
    - Ensure consistent date format (YYYY-MM-DD)
    - Sort data chronologically and return complete series
    - _Requirements: 6.3, 6.4_

- [x] 2. Implement main dashboard endpoint

  - [x] 2.1 Create `/new-user` GET endpoint in dashboard.py

    - Add route decorator with path `/new-user` and tag "Dashboard"
    - Add authentication dependency using `get_current_active_user`
    - Define async function `get_new_user_dashboard()`
    - Add function parameters for current_user and db session
    - Add comprehensive docstring describing endpoint functionality
    - _Requirements: 1.1, 1.2, 1.3, 1.4, 1.5, 7.4_

  - [x] 2.2 Implement user authentication and validation

    - Validate current_user object is not None
    - Log dashboard access attempt with user details
    - Handle authentication errors with 401 status code
    - _Requirements: 7.4, 7.5_

  - [x] 2.3 Gather user account information

    - Call `get_user_account_info()` with db session and current user
    - Call `calculate_onboarding_progress()` for progress metrics
    - Combine results into account_info response section
    - _Requirements: 1.1, 1.2, 1.3, 1.4, 1.5_

  - [x] 2.4 Gather user resource information

    - Query UserProviderPermission table to count active suppliers for user
    - Query UserPoint table to get current point balance
    - Determine if supplier assignment is pending (count == 0)
    - Determine if point allocation is pending (balance == 0)
    - Format into user_resources response section
    - _Requirements: 2.1, 2.2, 2.5_

  - [x] 2.5 Gather platform overview statistics

    - Query User table for total user count
    - Query Hotel table for total hotel count
    - Query ProviderMapping table for total mapping count
    - Call `get_available_suppliers()` for supplier list
    - Call `get_available_packages()` for package information
    - Format into platform_overview response section
    - _Requirements: 3.1, 3.2, 3.3, 2.1, 2.2, 2.3, 2.4_

  - [x] 2.6 Gather user activity metrics

    - Call `get_user_login_time_series()` for login history
    - Query UserActivityLog for total login count
    - Get last login timestamp from UserSession table
    - Create API request time-series with zero values (new users have no API usage)
    - Format into activity_metrics response section
    - _Requirements: 4.1, 4.2, 4.3, 4.4, 4.5_

  - [x] 2.7 Gather platform trend data

    - Call `get_platform_registration_trends()` for user registration time-series
    - Call `get_hotel_update_trends()` for hotel update time-series
    - Add metadata (title, unit, data_type) to each time-series
    - Format into platform_trends response section
    - _Requirements: 3.4, 3.5, 6.5_

  - [x] 2.8 Generate recommendations

    - Call `generate_recommendations()` with user and db session
    - Format recommendations into response section
    - _Requirements: 5.1, 5.2, 5.3, 5.4, 5.5_

  - [x] 2.9 Add response metadata

    - Add current timestamp in ISO 8601 format
    - Add cache status indicator
    - Add data freshness timestamps for each component
    - _Requirements: 6.5_

  - [x] 2.10 Implement error handling

    - Wrap main logic in try-except block
    - Handle HTTPException by re-raising without modification
    - Handle database errors with 500 status code
    - Handle unexpected errors with logging and 500 status code
    - Ensure graceful degradation for missing tables
    - _Requirements: 7.1, 7.2, 7.3_

- [x] 3. Implement caching for performance optimization

  - [x] 3.1 Add caching decorator to system metrics functions

    - Import cache decorator from fastapi_cache
    - Apply 5-minute cache to `get_available_suppliers()`
    - Apply 5-minute cache to `get_platform_registration_trends()`
    - Apply 5-minute cache to `get_hotel_update_trends()`
    - _Requirements: 7.2, 7.3_

  - [x] 3.2 Add caching decorator to user-specific functions

    - Apply 1-minute cache to user account info retrieval
    - Apply 1-minute cache to user activity time-series
    - Include user_id in cache key for proper isolation
    - _Requirements: 7.3_

  - [x] 3.3 Implement cache fallback handling

    - Add try-except blocks around cached function calls
    - Fall back to direct database queries if cache unavailable
    - Log cache failures as warnings
    - Set cache_status in response metadata
    - _Requirements: 7.2, 7.3_

- [x] 4. Add comprehensive error handling and logging

  - [x] 4.1 Implement graceful degradation for missing tables

    - Wrap UserActivityLog queries in try-except blocks
    - Return empty time-series with zeros if table missing
    - Log warnings for missing tables
    - Set data_available flags in response
    - _Requirements: 7.1, 7.2_

  - [x] 4.2 Add audit logging for dashboard access

    - Log all dashboard access attempts with user details
    - Include timestamp, user_id, username, and IP address
    - Use existing dashboard_logger instance
    - _Requirements: 7.5_

  - [x] 4.3 Implement query timeout handling

    - Set query timeout to 30 seconds
    - Handle timeout exceptions with 504 status code
    - Log timeout events for monitoring
    - _Requirements: 7.1_

- [x] 5. Validate endpoint functionality and performance

  - [x] 5.1 Test endpoint with new user (0 suppliers, 0 points)

    - Create test user with no supplier permissions
    - Create test user with no point allocations
    - Call endpoint and verify response structure
    - Verify all time-series data contains zeros or empty arrays
    - Verify recommendations include supplier and point assignment actions
    - _Requirements: 1.1, 1.2, 1.3, 1.4, 1.5, 2.5, 4.5, 5.1, 5.2_

  - [x] 5.2 Test endpoint with authenticated user

    - Test with valid JWT token
    - Verify 200 OK response
    - Verify all required response fields present
    - _Requirements: 7.4_

  - [x] 5.3 Test endpoint error scenarios

    - Test with invalid/missing JWT token (expect 401)
    - Test with database connection failure (expect 500)
    - Test with missing UserActivityLog table (expect graceful degradation)
    - _Requirements: 7.1, 7.4_

  - [x] 5.4 Verify response time performance

    - Measure response time with cold cache
    - Measure response time with warm cache
    - Verify 95% of requests complete within 500ms
    - _Requirements: 7.1_

  - [x] 5.5 Verify time-series data format

    - Check all time-series data has consistent structure (date, value)
    - Verify dates are in YYYY-MM-DD format
    - Verify data is sorted chronologically
    - Verify missing dates are filled with zeros
    - Verify 30-day period is complete
    - _Requirements: 6.1, 6.2, 6.3, 6.4_

  - [x] 5.6 Verify caching behavior

    - Test cache hit scenario (second request faster)
    - Test cache expiration (data refreshes after TTL)
    - Test cache unavailable scenario (falls back to database)
    - _Requirements: 7.2, 7.3_

- [x] 6. Update API documentation

  - [x] 6.1 Add endpoint to OpenAPI schema

    - Ensure endpoint appears in /docs Swagger UI
    - Verify request/response examples are clear
    - Add description of endpoint purpose and usage
    - _Requirements: All_

  - [x] 6.2 Document response schema

    - Document all response fields with descriptions
    - Provide example response JSON
    - Document time-series data format
    - _Requirements: 6.5_
