# Dashboard API Endpoints Guide

## Overview

The dashboard system has been enhanced with comprehensive new endpoints that provide detailed analytics and insights for better system understanding and management. All endpoints require Admin or Super User privileges.

## New Endpoints Added

### 1. `/v1.0/dashboard/system_health` (GET)

**Purpose**: System health monitoring and performance overview
**Features**:

- Database health and performance metrics
- User engagement and activity analysis
- API usage and performance statistics
- Security status monitoring
- Data quality assessment
- System recommendations

**Key Metrics**:

- Overall system status (healthy/warning/critical)
- User engagement rates
- API performance indicators
- Security threat levels
- Data completeness scores

### 2. `/v1.0/dashboard/hotel_analytics` (GET)

**Purpose**: Hotel inventory and location analytics
**Features**:

- Hotel distribution analysis
- Geographic coverage metrics
- Provider mapping statistics
- Content quality assessment
- Chain analysis
- Data integrity insights

**Key Metrics**:

- Total hotels and locations
- Geographic distribution by country/city
- Provider mapping coverage
- Data completeness scores
- Chain vs independent hotel ratios

### 3. `/v1.0/dashboard/user_management` (GET)

**Purpose**: User administration and management insights
**Features**:

- Role distribution analysis
- Account status monitoring
- API integration statistics
- User lifecycle tracking
- Administrative insights
- Security overview

**Key Metrics**:

- User counts by role
- API adoption rates
- User growth and activation rates
- Account security scores
- Administrative recommendations

### 4. `/v1.0/dashboard/performance_metrics` (GET)

**Purpose**: System performance and usage analysis
**Parameters**: `days` (1-30, default: 7)
**Features**:

- API performance monitoring
- System load analysis
- Error rate tracking
- Database performance metrics
- User activity patterns
- Capacity utilization

**Key Metrics**:

- Request throughput and response times
- Success rates and error analysis
- Peak usage identification
- User engagement scores
- Performance benchmarks

### 5. `/v1.0/dashboard/export_data` (GET)

**Purpose**: Comprehensive data export for reporting
**Parameters**: `format` ("json" or "csv_structure")
**Features**:

- Multi-format data export
- Complete dashboard data aggregation
- Business intelligence ready structure
- Audit trail logging
- Data privacy compliance

**Export Includes**:

- User analytics and statistics
- System health metrics
- Hotel and location data
- Performance analytics
- Points system data (if available)

## Existing Endpoints (Enhanced)

### 1. `/v1.0/dashboard/stats` (GET)

**Enhanced Features**:

- Comprehensive user statistics
- Points system analytics
- Activity tracking metrics
- System health indicators
- Graceful error handling

### 2. `/v1.0/dashboard/user_activity` (GET)

**Enhanced Features**:

- Daily activity trends
- Most active users identification
- Configurable time periods
- User engagement analysis
- Activity pattern insights

### 3. `/v1.0/dashboard/points_summary` (GET)

**Enhanced Features**:

- Points distribution by role
- Transaction analytics
- Top point holders
- Financial insights
- Points economy health

## Security and Access Control

All dashboard endpoints implement:

- Role-based access control (Admin/Super User only)
- Comprehensive audit logging
- Unauthorized access monitoring
- Security incident tracking
- Data privacy protection

## Error Handling and Resilience

The dashboard system includes:

- Graceful degradation when tables are missing
- Comprehensive error logging
- Default values for missing data
- Database connection resilience
- User-friendly error messages

## Usage Examples

### Get System Health

```bash
GET /v1.0/dashboard/system_health
Authorization: Bearer <admin_token>
```

### Get Hotel Analytics

```bash
GET /v1.0/dashboard/hotel_analytics
Authorization: Bearer <admin_token>
```

### Get Performance Metrics (Last 14 days)

```bash
GET /v1.0/dashboard/performance_metrics?days=14
Authorization: Bearer <admin_token>
```

### Export Dashboard Data as JSON

```bash
GET /v1.0/dashboard/export_data?format=json
Authorization: Bearer <admin_token>
```

## Benefits of the Enhanced Dashboard

1. **Comprehensive Monitoring**: Complete system oversight with health, performance, and usage metrics
2. **Business Intelligence**: Rich analytics for data-driven decision making
3. **Proactive Management**: Early warning systems and recommendations
4. **Scalability Insights**: Capacity planning and resource optimization data
5. **Security Monitoring**: User activity and security threat detection
6. **Data Quality Assurance**: Content completeness and integrity monitoring

## Integration with Frontend

The enhanced endpoints provide structured JSON responses that can be easily integrated with:

- Admin dashboards and control panels
- Business intelligence tools
- Monitoring and alerting systems
- Reporting and analytics platforms
- Executive summary dashboards

## Monitoring and Alerting

The dashboard system supports:

- Real-time system health monitoring
- Performance threshold alerting
- User activity anomaly detection
- Data quality degradation warnings
- Security incident notifications

This enhanced dashboard system provides administrators with comprehensive insights into system performance, user behavior, data quality, and business metrics, enabling proactive management and data-driven decision making.
