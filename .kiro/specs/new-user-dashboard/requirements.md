# Requirements Document

## Introduction

This feature provides a comprehensive dashboard for newly registered users in the HITA system who have not yet been assigned supplier permissions or point allocations. The dashboard displays meaningful metrics, onboarding guidance, and system information to help new users understand the platform and take next steps toward activation.

## Glossary

- **HITA_System**: The Hotel Integration Technology API platform that aggregates hotel data from multiple suppliers
- **New_User**: A registered user account with no active supplier permissions and zero point allocation
- **Dashboard_Service**: The backend service that provides dashboard data and metrics via API endpoints
- **Supplier_Permission**: Authorization to access hotel data from a specific supplier (e.g., Agoda, Booking, EAN)
- **Point_Allocation**: Credit-based system that controls API usage limits for users
- **Account_Status**: The current state of a user account (pending, active, suspended)
- **Onboarding_Metric**: Data points that track user progress through initial setup steps
- **System_Metric**: Platform-wide statistics visible to all users
- **Time_Series_Data**: Historical data points suitable for graph visualization over time periods

## Requirements

### Requirement 1

**User Story:** As a newly registered user with no suppliers or points, I want to see my account status and onboarding progress, so that I understand what steps I need to take to start using the platform

#### Acceptance Criteria

1. WHEN a new user accesses the dashboard endpoint, THE Dashboard_Service SHALL return the user's account creation date
2. WHEN a new user accesses the dashboard endpoint, THE Dashboard_Service SHALL return the current Account_Status value
3. WHEN a new user accesses the dashboard endpoint, THE Dashboard_Service SHALL return a count of zero for active Supplier_Permission entries
4. WHEN a new user accesses the dashboard endpoint, THE Dashboard_Service SHALL return a Point_Allocation balance of zero
5. WHEN a new user accesses the dashboard endpoint, THE Dashboard_Service SHALL return an onboarding completion percentage calculated from completed setup steps

### Requirement 2

**User Story:** As a newly registered user, I want to see available suppliers and point packages in the system, so that I understand what options are available when my account is activated

#### Acceptance Criteria

1. THE Dashboard_Service SHALL return a list of all available supplier names in the HITA_System
2. THE Dashboard_Service SHALL return a count of total available suppliers
3. THE Dashboard_Service SHALL return available point package types (admin, yearly, monthly, per-request, guest)
4. THE Dashboard_Service SHALL return example point allocation amounts for each package type
5. WHERE the user has zero Supplier_Permission entries, THE Dashboard_Service SHALL include a flag indicating pending supplier assignment

### Requirement 3

**User Story:** As a newly registered user, I want to see platform activity metrics and trends, so that I understand the scale and activity level of the platform I'm joining

#### Acceptance Criteria

1. THE Dashboard_Service SHALL return the total count of registered users in the HITA_System
2. THE Dashboard_Service SHALL return the total count of hotels available across all suppliers
3. THE Dashboard_Service SHALL return the total count of active provider mappings
4. THE Dashboard_Service SHALL return Time_Series_Data showing new user registrations over the last 30 days
5. THE Dashboard_Service SHALL return Time_Series_Data showing hotel data updates over the last 30 days

### Requirement 4

**User Story:** As a newly registered user, I want to see my account activity timeline, so that I can track my interactions with the platform even before activation

#### Acceptance Criteria

1. THE Dashboard_Service SHALL return Time_Series_Data of the user's login attempts over the last 30 days
2. THE Dashboard_Service SHALL return a count of total login sessions for the user account
3. THE Dashboard_Service SHALL return the timestamp of the user's last login
4. THE Dashboard_Service SHALL return a count of API requests made by the user (expected to be zero for new users)
5. WHERE the user has made zero API requests, THE Dashboard_Service SHALL return Time_Series_Data with zero values suitable for empty state graph rendering

### Requirement 5

**User Story:** As a newly registered user, I want to see next steps and recommendations, so that I know how to proceed with activating my account

#### Acceptance Criteria

1. WHERE the user has zero Supplier_Permission entries, THE Dashboard_Service SHALL return a recommendation to contact an administrator for supplier access
2. WHERE the user has zero Point_Allocation, THE Dashboard_Service SHALL return a recommendation to request point package assignment
3. THE Dashboard_Service SHALL return a list of pending actions required for full account activation
4. THE Dashboard_Service SHALL return estimated time to complete each pending action
5. THE Dashboard_Service SHALL return contact information for administrator support

### Requirement 6

**User Story:** As a developer integrating the dashboard, I want all time-series data in a consistent format, so that I can easily render graphs and charts

#### Acceptance Criteria

1. THE Dashboard_Service SHALL return all Time_Series_Data in a consistent JSON structure with date and value pairs
2. THE Dashboard_Service SHALL return Time_Series_Data with daily granularity for 30-day periods
3. THE Dashboard_Service SHALL fill missing dates in Time_Series_Data with zero values to ensure continuous data series
4. THE Dashboard_Service SHALL return Time_Series_Data sorted chronologically from oldest to newest
5. THE Dashboard_Service SHALL return metadata for each Time_Series_Data set including title, unit of measurement, and data type

### Requirement 7

**User Story:** As a system administrator, I want the dashboard endpoint to be performant and cached, so that new users have a fast experience even with limited permissions

#### Acceptance Criteria

1. THE Dashboard_Service SHALL complete dashboard data retrieval within 500 milliseconds for 95% of requests
2. THE Dashboard_Service SHALL cache system-wide metrics for 5 minutes to reduce database load
3. THE Dashboard_Service SHALL cache user-specific data for 1 minute to balance freshness and performance
4. THE Dashboard_Service SHALL require valid JWT authentication for all dashboard endpoints
5. THE Dashboard_Service SHALL log dashboard access attempts for security audit purposes
