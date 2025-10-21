# Health Check and Monitoring Documentation

## Overview

The Health Check and Monitoring system provides comprehensive health monitoring, service status verification, and system metrics for the ITT Hotel API (HITA). It includes multiple health check endpoints designed for different monitoring needs, from basic service availability to detailed system diagnostics.

## Architecture

### Core Components

- **Health Router**: `/v1.0/health` prefix
- **Multi-Level Health Checks**: Basic to comprehensive monitoring
- **System Resource Monitoring**: CPU, memory, and disk usage
- **Database Health Verification**: Connection and performance testing
- **Cache Health Monitoring**: Redis connectivity and performance
- **Service Metrics**: Detailed analytics and statistics
- **Container Orchestration Support**: Kubernetes-style probes

### Route Prefix

```
/v1.0/health
```

## Health Check Endpoints

### Basic Health Check

#### Endpoint

```http
GET /v1.0/health/
```

#### Response

```json
{
  "status": "healthy",
  "service": "User Management API",
  "version": "1.0.0",
  "timestamp": "2024-12-17T15:30:00Z",
  "uptime": "Service is running"
}
```

#### Use Cases

- **Load Balancer Health Checks**: Quick service availability verification
- **Basic Monitoring**: Simple up/down status checking
- **Lightweight Probes**: Minimal resource usage health verification

### Detailed Health Check

#### Endpoint

```http
GET /v1.0/health/detailed
```

#### Response

```json
{
  "status": "healthy",
  "service": "User Management API",
  "version": "1.0.0",
  "timestamp": "2024-12-17T15:30:00Z",
  "response_time_ms": 145.67,
  "checks": {
    "database": {
      "status": "healthy",
      "response_time_ms": 23.45,
      "user_count": 150,
      "point_records": 145,
      "details": "Database connectivity and basic queries successful"
    },
    "cache": {
      "status": "healthy",
      "response_time_ms": 12.34,
      "backend": "Redis",
      "details": "Cache backend is initialized and accessible"
    },
    "system_resources": {
      "status": "healthy",
      "cpu_percent": 45.2,
      "memory_percent": 67.8,
      "memory_available_gb": 2.45,
      "disk_percent": 34.5,
      "disk_free_gb": 15.67,
      "details": "System resources at healthy levels"
    },
    "service_metrics": {
      "status": "healthy",
      "recent_user_registrations": 8,
      "recent_point_transactions": 234,
      "details": "Service activity metrics within normal ranges"
    }
  }
}
```

#### Health Status Levels

- **healthy**: All systems operating normally
- **warning**: Some components showing elevated metrics
- **critical**: Critical thresholds exceeded
- **unhealthy**: System failures detected

### Database Health Check

#### Endpoint

```http
GET /v1.0/health/database
```

#### Response

```json
{
  "status": "healthy",
  "response_time_ms": 45.23,
  "complex_query_time_ms": 78.9,
  "table_counts": {
    "users": 150,
    "user_points": 145,
    "point_transactions": 1250,
    "user_permissions": 89
  },
  "performance_metrics": {
    "recent_active_users": 23,
    "query_performance": "good"
  },
  "timestamp": "2024-12-17T15:30:00Z"
}
```

#### Database Checks

- **Connection Pool Status**: Database connectivity verification
- **Query Performance**: Response time measurement
- **Table Accessibility**: Core table access verification
- **Index Performance**: Complex query performance testing

### Cache Health Check

#### Endpoint

```http
GET /v1.0/health/cache
```

#### Response

```json
{
  "status": "healthy",
  "response_time_ms": 15.67,
  "cache_test_time_ms": 8.45,
  "backend_type": "RedisBackend",
  "details": "Cache backend is accessible and responding",
  "timestamp": "2024-12-17T15:30:00Z"
}
```

#### Cache Checks

- **Redis Connection**: Backend connectivity verification
- **Cache Operations**: Read/write operation testing
- **Performance Metrics**: Response time measurement
- **Memory Usage**: Cache memory statistics

### Service Metrics (Admin Only)

#### Endpoint

```http
GET /v1.0/health/metrics
Authorization: Bearer <admin_token>
```

#### Response

```json
{
  "timestamp": "2024-12-17T15:30:00Z",
  "service": "User Management API",
  "user_metrics": {
    "total_users": 150,
    "new_users_24h": 3,
    "new_users_7d": 12,
    "new_users_30d": 45,
    "active_users_7d": 89,
    "role_distribution": {
      "super_user": 2,
      "admin_user": 5,
      "general_user": 143
    }
  },
  "transaction_metrics": {
    "total_transactions": 1250,
    "transactions_24h": 45,
    "transactions_7d": 234,
    "total_points_distributed": 45000,
    "current_points_available": 12500,
    "points_utilization_rate": 72.22
  },
  "performance_metrics": {
    "avg_response_time_ms": 50,
    "error_rate_percent": 0.1,
    "uptime_status": "healthy"
  },
  "system_health": {
    "database_status": "healthy",
    "cache_status": "healthy",
    "overall_status": "healthy"
  }
}
```

#### Metrics Categories

- **User Metrics**: Registration trends and role distribution
- **Transaction Metrics**: Point transaction volumes and utilization
- **Performance Metrics**: Response times and error rates
- **System Health**: Overall component status

### Service Status Summary

#### Endpoint

```http
GET /v1.0/health/status
```

#### Response

```json
{
  "service": "User Management API",
  "status": "operational",
  "version": "1.0.0",
  "environment": "production",
  "last_updated": "2024-12-17T15:30:00Z",
  "components": {
    "api": "operational",
    "database": "operational",
    "cache": "operational",
    "authentication": "operational"
  },
  "performance": {
    "response_time": "normal",
    "error_rate": "low",
    "throughput": "normal"
  }
}
```

## Container Orchestration Support

### Readiness Probe

#### Endpoint

```http
GET /v1.0/health/readiness
```

#### Response (Ready)

```json
{
  "status": "ready",
  "timestamp": "2024-12-17T15:30:00Z",
  "checks": {
    "database": "ready",
    "cache": "ready"
  }
}
```

#### Response (Not Ready)

```http
HTTP/1.1 503 Service Unavailable
```

```json
{
  "status": "not_ready",
  "error": "Database connection failed",
  "timestamp": "2024-12-17T15:30:00Z"
}
```

#### Kubernetes Configuration

```yaml
readinessProbe:
  httpGet:
    path: /v1.0/health/readiness
    port: 8000
  initialDelaySeconds: 10
  periodSeconds: 5
  timeoutSeconds: 3
  failureThreshold: 3
```

### Liveness Probe

#### Endpoint

```http
GET /v1.0/health/liveness
```

#### Response

```json
{
  "status": "alive",
  "timestamp": "2024-12-17T15:30:00Z",
  "service": "User Management API"
}
```

#### Kubernetes Configuration

```yaml
livenessProbe:
  httpGet:
    path: /v1.0/health/liveness
    port: 8000
  initialDelaySeconds: 30
  periodSeconds: 10
  timeoutSeconds: 5
  failureThreshold: 3
```

## System Resource Monitoring

### Resource Thresholds

| Resource     | Healthy | Warning | Critical |
| ------------ | ------- | ------- | -------- |
| CPU Usage    | < 80%   | 80-95%  | > 95%    |
| Memory Usage | < 85%   | 85-95%  | > 95%    |
| Disk Usage   | < 90%   | 90-95%  | > 95%    |

### Resource Monitoring Features

- **Real-time Metrics**: Current CPU, memory, and disk usage
- **Threshold Alerting**: Automatic status changes based on thresholds
- **Historical Tracking**: Resource usage trends over time
- **Performance Impact**: Resource usage impact on service performance

## Health Check Implementation

### Database Health Verification

```python
# Test basic connectivity
db.execute(text("SELECT 1"))

# Test table access and get counts
user_count = db.query(models.User).count()
point_count = db.query(models.UserPoint).count()

# Test complex query performance
complex_query_start = time.time()
recent_active_users = db.query(models.User).join(
    models.PointTransaction,
    models.User.id == models.PointTransaction.giver_id
).filter(
    models.PointTransaction.created_at >= datetime.utcnow() - timedelta(days=7)
).distinct().count()
complex_query_time = (time.time() - complex_query_start) * 1000
```

### Cache Health Verification

```python
# Check if cache backend is available
if FastAPICache.get_backend():
    backend = FastAPICache.get_backend()
    cache_status = "healthy"
else:
    cache_status = "warning"
```

### System Resource Monitoring

```python
# Get system resource usage
cpu_percent = psutil.cpu_percent(interval=1)
memory = psutil.virtual_memory()
disk = psutil.disk_usage('/')

# Determine system health based on resource usage
system_status = "healthy"
if cpu_percent > 80 or memory.percent > 85 or disk.percent > 90:
    system_status = "warning"
if cpu_percent > 95 or memory.percent > 95 or disk.percent > 95:
    system_status = "critical"
```

## Monitoring Integration

### Prometheus Metrics

```python
# Example Prometheus metrics integration
from prometheus_client import Counter, Histogram, Gauge

# Request counters
health_check_requests = Counter('health_check_requests_total', 'Total health check requests')
health_check_failures = Counter('health_check_failures_total', 'Total health check failures')

# Response time histogram
health_check_duration = Histogram('health_check_duration_seconds', 'Health check response time')

# System resource gauges
cpu_usage_gauge = Gauge('system_cpu_usage_percent', 'Current CPU usage percentage')
memory_usage_gauge = Gauge('system_memory_usage_percent', 'Current memory usage percentage')
```

### Alerting Rules

```yaml
# Example Prometheus alerting rules
groups:
  - name: health_checks
    rules:
      - alert: ServiceUnhealthy
        expr: health_check_status != 1
        for: 2m
        labels:
          severity: critical
        annotations:
          summary: "Service health check failing"

      - alert: HighCPUUsage
        expr: system_cpu_usage_percent > 80
        for: 5m
        labels:
          severity: warning
        annotations:
          summary: "High CPU usage detected"
```

## Error Handling and Resilience

### Graceful Degradation

- **Partial Failures**: Continue operation with reduced functionality
- **Component Isolation**: Isolate failing components
- **Fallback Responses**: Provide meaningful error responses
- **Recovery Procedures**: Automatic recovery mechanisms

### Error Response Format

```json
{
  "status": "unhealthy",
  "error": "Database connection timeout",
  "response_time_ms": 5000.0,
  "timestamp": "2024-12-17T15:30:00Z",
  "details": "Database connectivity failed after 5 second timeout"
}
```

## Security Considerations

### Access Control

- **Public Endpoints**: Basic health checks available to all
- **Protected Endpoints**: Detailed metrics require authentication
- **Admin Only**: Comprehensive metrics restricted to admin users
- **Rate Limiting**: Prevent health check endpoint abuse

### Information Disclosure

- **Sensitive Data**: Avoid exposing sensitive system information
- **Error Details**: Limit error information in public endpoints
- **Internal Metrics**: Restrict detailed internal metrics
- **Security Headers**: Implement appropriate security headers

## Performance Optimization

### Caching Strategy

- **Health Check Caching**: Cache health check results for short periods
- **Resource Monitoring**: Efficient resource usage monitoring
- **Database Queries**: Optimized health check queries
- **Response Compression**: Compress large health check responses

### Monitoring Overhead

- **Lightweight Checks**: Minimize resource usage for basic checks
- **Sampling**: Use sampling for expensive metrics collection
- **Async Operations**: Use asynchronous operations where possible
- **Connection Pooling**: Efficient database connection management

## Best Practices

### Health Check Design

1. **Layered Approach**: Multiple levels of health checks
2. **Fast Response**: Keep basic health checks lightweight
3. **Comprehensive Coverage**: Test all critical dependencies
4. **Clear Status**: Provide clear and actionable status information
5. **Consistent Format**: Use consistent response formats

### Monitoring Strategy

1. **Regular Monitoring**: Implement continuous health monitoring
2. **Alerting Thresholds**: Set appropriate alerting thresholds
3. **Trend Analysis**: Monitor health trends over time
4. **Capacity Planning**: Use health metrics for capacity planning
5. **Documentation**: Document health check procedures

### Operational Guidelines

1. **Response Time**: Monitor health check response times
2. **Availability**: Track health check endpoint availability
3. **False Positives**: Minimize false positive alerts
4. **Recovery Time**: Measure and optimize recovery times
5. **Incident Response**: Have clear incident response procedures

## Integration Examples

### Basic Health Check

```python
import requests

# Basic health check
response = requests.get(f"{base_url}/v1.0/health/")
if response.status_code == 200:
    health_data = response.json()
    print(f"Service Status: {health_data['status']}")
```

### Detailed Health Monitoring

```python
# Detailed health check with error handling
try:
    response = requests.get(f"{base_url}/v1.0/health/detailed", timeout=10)
    health_data = response.json()

    if health_data['status'] == 'healthy':
        print("All systems operational")
    else:
        print(f"System issues detected: {health_data['status']}")
        for check_name, check_data in health_data['checks'].items():
            if check_data['status'] != 'healthy':
                print(f"  {check_name}: {check_data['status']}")

except requests.exceptions.Timeout:
    print("Health check timeout - service may be overloaded")
except requests.exceptions.ConnectionError:
    print("Cannot connect to service - service may be down")
```

### Kubernetes Health Checks

```yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: user-management-api
spec:
  template:
    spec:
      containers:
        - name: api
          image: user-management-api:latest
          ports:
            - containerPort: 8000
          livenessProbe:
            httpGet:
              path: /v1.0/health/liveness
              port: 8000
            initialDelaySeconds: 30
            periodSeconds: 10
            timeoutSeconds: 5
            failureThreshold: 3
          readinessProbe:
            httpGet:
              path: /v1.0/health/readiness
              port: 8000
            initialDelaySeconds: 10
            periodSeconds: 5
            timeoutSeconds: 3
            failureThreshold: 3
```

## Troubleshooting

### Common Issues

#### Database Connection Failures

- **Symptoms**: Database health check failing
- **Causes**: Connection pool exhaustion, database downtime
- **Solutions**: Check connection strings, restart database, scale connection pool

#### Cache Connectivity Issues

- **Symptoms**: Cache health check warnings
- **Causes**: Redis downtime, network issues
- **Solutions**: Verify Redis status, check network connectivity, restart cache

#### High Resource Usage

- **Symptoms**: System resource warnings/critical status
- **Causes**: Memory leaks, CPU-intensive operations, disk space issues
- **Solutions**: Investigate resource usage, optimize queries, clean up disk space

### Diagnostic Commands

```bash
# Check service health
curl -s http://localhost:8000/v1.0/health/ | jq

# Detailed health check
curl -s http://localhost:8000/v1.0/health/detailed | jq

# Database specific check
curl -s http://localhost:8000/v1.0/health/database | jq

# System resource monitoring
curl -s http://localhost:8000/v1.0/health/detailed | jq '.checks.system_resources'
```

## Future Enhancements

### Potential Improvements

- **Custom Health Checks**: User-defined health check endpoints
- **Health Check Scheduling**: Automated health check scheduling
- **Historical Data**: Long-term health trend storage
- **Predictive Monitoring**: AI-based health prediction
- **Integration APIs**: Third-party monitoring tool integration

### Advanced Features

- **Circuit Breakers**: Automatic service protection
- **Health Dashboards**: Real-time health visualization
- **Automated Recovery**: Self-healing capabilities
- **Performance Profiling**: Detailed performance analysis
- **Distributed Tracing**: Request tracing across services
