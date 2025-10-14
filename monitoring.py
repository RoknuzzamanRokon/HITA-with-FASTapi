"""
Service Monitoring and Metrics Collection for User Management System

This module provides comprehensive monitoring capabilities including:
- Performance metrics collection
- Error tracking and alerting
- System health monitoring
- Usage analytics and reporting
- Custom metrics and dashboards
"""

import time
import logging
from typing import Dict, Any, List, Optional, Callable
from datetime import datetime, timedelta
from dataclasses import dataclass, field
from collections import defaultdict, deque
from threading import Lock
import json
import os
from functools import wraps
from contextlib import contextmanager


# Configure logging for monitoring
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


@dataclass
class MetricPoint:
    """Individual metric data point"""
    timestamp: datetime
    value: float
    tags: Dict[str, str] = field(default_factory=dict)
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class PerformanceMetric:
    """Performance metric tracking"""
    name: str
    count: int = 0
    total_time: float = 0.0
    min_time: float = float('inf')
    max_time: float = 0.0
    errors: int = 0
    last_updated: datetime = field(default_factory=datetime.utcnow)
    
    @property
    def average_time(self) -> float:
        return self.total_time / self.count if self.count > 0 else 0.0
    
    @property
    def error_rate(self) -> float:
        return (self.errors / self.count * 100) if self.count > 0 else 0.0


class MetricsCollector:
    """
    Comprehensive metrics collection system for API monitoring.
    
    This class provides:
    - Real-time performance metrics
    - Error tracking and analysis
    - Custom metric collection
    - Historical data storage
    - Alert threshold monitoring
    """
    
    def __init__(self, max_history_size: int = 10000):
        """
        Initialize the metrics collector.
        
        Args:
            max_history_size: Maximum number of historical data points to keep
        """
        self.max_history_size = max_history_size
        self.metrics: Dict[str, PerformanceMetric] = {}
        self.custom_metrics: Dict[str, deque] = defaultdict(lambda: deque(maxlen=max_history_size))
        self.error_log: deque = deque(maxlen=max_history_size)
        self.request_log: deque = deque(maxlen=max_history_size)
        self.lock = Lock()
        
        # Alert thresholds
        self.alert_thresholds = {
            "response_time_ms": 1000,  # Alert if response time > 1s
            "error_rate_percent": 5.0,  # Alert if error rate > 5%
            "requests_per_minute": 1000  # Alert if requests > 1000/min
        }
        
        # System start time
        self.start_time = datetime.utcnow()
    
    def record_request(self, endpoint: str, method: str, status_code: int, 
                      response_time: float, user_id: Optional[str] = None,
                      error_message: Optional[str] = None):
        """
        Record an API request with performance and error tracking.
        
        Args:
            endpoint: API endpoint path
            method: HTTP method
            status_code: HTTP status code
            response_time: Response time in milliseconds
            user_id: User ID making the request (if available)
            error_message: Error message if request failed
        """
        with self.lock:
            # Create metric key
            metric_key = f"{method}:{endpoint}"
            
            # Initialize metric if not exists
            if metric_key not in self.metrics:
                self.metrics[metric_key] = PerformanceMetric(name=metric_key)
            
            metric = self.metrics[metric_key]
            
            # Update performance metrics
            metric.count += 1
            metric.total_time += response_time
            metric.min_time = min(metric.min_time, response_time)
            metric.max_time = max(metric.max_time, response_time)
            metric.last_updated = datetime.utcnow()
            
            # Track errors
            if status_code >= 400:
                metric.errors += 1
                
                # Log error details
                self.error_log.append({
                    "timestamp": datetime.utcnow().isoformat(),
                    "endpoint": endpoint,
                    "method": method,
                    "status_code": status_code,
                    "response_time_ms": response_time,
                    "user_id": user_id,
                    "error_message": error_message
                })
            
            # Log request details
            self.request_log.append({
                "timestamp": datetime.utcnow().isoformat(),
                "endpoint": endpoint,
                "method": method,
                "status_code": status_code,
                "response_time_ms": response_time,
                "user_id": user_id,
                "success": status_code < 400
            })
            
            # Check alert thresholds
            self._check_alerts(metric_key, metric, response_time)
    
    def record_custom_metric(self, name: str, value: float, 
                           tags: Optional[Dict[str, str]] = None,
                           metadata: Optional[Dict[str, Any]] = None):
        """
        Record a custom metric value.
        
        Args:
            name: Metric name
            value: Metric value
            tags: Optional tags for categorization
            metadata: Optional additional metadata
        """
        with self.lock:
            metric_point = MetricPoint(
                timestamp=datetime.utcnow(),
                value=value,
                tags=tags or {},
                metadata=metadata or {}
            )
            self.custom_metrics[name].append(metric_point)
    
    def get_performance_summary(self, time_window_minutes: int = 60) -> Dict[str, Any]:
        """
        Get performance summary for the specified time window.
        
        Args:
            time_window_minutes: Time window in minutes for analysis
            
        Returns:
            Dict[str, Any]: Performance summary statistics
        """
        with self.lock:
            cutoff_time = datetime.utcnow() - timedelta(minutes=time_window_minutes)
            
            # Filter recent requests
            recent_requests = [
                req for req in self.request_log 
                if datetime.fromisoformat(req["timestamp"]) >= cutoff_time
            ]
            
            # Filter recent errors
            recent_errors = [
                err for err in self.error_log
                if datetime.fromisoformat(err["timestamp"]) >= cutoff_time
            ]
            
            # Calculate summary statistics
            total_requests = len(recent_requests)
            total_errors = len(recent_errors)
            
            if total_requests > 0:
                response_times = [req["response_time_ms"] for req in recent_requests]
                avg_response_time = sum(response_times) / len(response_times)
                p95_response_time = sorted(response_times)[int(len(response_times) * 0.95)]
                p99_response_time = sorted(response_times)[int(len(response_times) * 0.99)]
                error_rate = (total_errors / total_requests) * 100
                requests_per_minute = total_requests / time_window_minutes
            else:
                avg_response_time = 0
                p95_response_time = 0
                p99_response_time = 0
                error_rate = 0
                requests_per_minute = 0
            
            # Endpoint breakdown
            endpoint_stats = defaultdict(lambda: {"count": 0, "errors": 0, "total_time": 0})
            for req in recent_requests:
                key = f"{req['method']}:{req['endpoint']}"
                endpoint_stats[key]["count"] += 1
                endpoint_stats[key]["total_time"] += req["response_time_ms"]
                if not req["success"]:
                    endpoint_stats[key]["errors"] += 1
            
            # Convert to summary format
            endpoint_summary = {}
            for endpoint, stats in endpoint_stats.items():
                endpoint_summary[endpoint] = {
                    "requests": stats["count"],
                    "errors": stats["errors"],
                    "error_rate": (stats["errors"] / stats["count"] * 100) if stats["count"] > 0 else 0,
                    "avg_response_time_ms": stats["total_time"] / stats["count"] if stats["count"] > 0 else 0
                }
            
            return {
                "time_window_minutes": time_window_minutes,
                "summary": {
                    "total_requests": total_requests,
                    "total_errors": total_errors,
                    "error_rate_percent": round(error_rate, 2),
                    "requests_per_minute": round(requests_per_minute, 2),
                    "avg_response_time_ms": round(avg_response_time, 2),
                    "p95_response_time_ms": round(p95_response_time, 2),
                    "p99_response_time_ms": round(p99_response_time, 2)
                },
                "endpoints": endpoint_summary,
                "recent_errors": list(recent_errors)[-10:],  # Last 10 errors
                "timestamp": datetime.utcnow().isoformat()
            }
    
    def get_system_health(self) -> Dict[str, Any]:
        """
        Get overall system health status.
        
        Returns:
            Dict[str, Any]: System health information
        """
        summary = self.get_performance_summary(60)  # Last hour
        
        # Determine health status
        health_status = "healthy"
        issues = []
        
        if summary["summary"]["error_rate_percent"] > self.alert_thresholds["error_rate_percent"]:
            health_status = "warning"
            issues.append(f"High error rate: {summary['summary']['error_rate_percent']}%")
        
        if summary["summary"]["avg_response_time_ms"] > self.alert_thresholds["response_time_ms"]:
            health_status = "warning"
            issues.append(f"High response time: {summary['summary']['avg_response_time_ms']}ms")
        
        if summary["summary"]["requests_per_minute"] > self.alert_thresholds["requests_per_minute"]:
            health_status = "warning"
            issues.append(f"High request rate: {summary['summary']['requests_per_minute']}/min")
        
        # System uptime
        uptime = datetime.utcnow() - self.start_time
        uptime_hours = uptime.total_seconds() / 3600
        
        return {
            "status": health_status,
            "uptime_hours": round(uptime_hours, 2),
            "issues": issues,
            "performance": summary["summary"],
            "alert_thresholds": self.alert_thresholds,
            "timestamp": datetime.utcnow().isoformat()
        }
    
    def get_custom_metrics_summary(self, metric_name: str, 
                                 time_window_minutes: int = 60) -> Dict[str, Any]:
        """
        Get summary of custom metrics for the specified time window.
        
        Args:
            metric_name: Name of the custom metric
            time_window_minutes: Time window in minutes
            
        Returns:
            Dict[str, Any]: Custom metric summary
        """
        with self.lock:
            if metric_name not in self.custom_metrics:
                return {"error": f"Metric '{metric_name}' not found"}
            
            cutoff_time = datetime.utcnow() - timedelta(minutes=time_window_minutes)
            recent_points = [
                point for point in self.custom_metrics[metric_name]
                if point.timestamp >= cutoff_time
            ]
            
            if not recent_points:
                return {
                    "metric_name": metric_name,
                    "time_window_minutes": time_window_minutes,
                    "data_points": 0,
                    "summary": {}
                }
            
            values = [point.value for point in recent_points]
            
            return {
                "metric_name": metric_name,
                "time_window_minutes": time_window_minutes,
                "data_points": len(recent_points),
                "summary": {
                    "min": min(values),
                    "max": max(values),
                    "avg": sum(values) / len(values),
                    "latest": values[-1] if values else None
                },
                "recent_values": values[-10:],  # Last 10 values
                "timestamp": datetime.utcnow().isoformat()
            }
    
    def _check_alerts(self, metric_key: str, metric: PerformanceMetric, response_time: float):
        """Check if any alert thresholds are exceeded"""
        alerts = []
        
        # Response time alert
        if response_time > self.alert_thresholds["response_time_ms"]:
            alerts.append(f"High response time for {metric_key}: {response_time}ms")
        
        # Error rate alert
        if metric.error_rate > self.alert_thresholds["error_rate_percent"]:
            alerts.append(f"High error rate for {metric_key}: {metric.error_rate}%")
        
        # Log alerts
        for alert in alerts:
            logger.warning(f"ALERT: {alert}")
    
    def export_metrics(self, filepath: str):
        """
        Export all metrics to a JSON file.
        
        Args:
            filepath: Path to save the metrics file
        """
        with self.lock:
            export_data = {
                "export_timestamp": datetime.utcnow().isoformat(),
                "system_start_time": self.start_time.isoformat(),
                "performance_metrics": {
                    name: {
                        "count": metric.count,
                        "total_time": metric.total_time,
                        "average_time": metric.average_time,
                        "min_time": metric.min_time,
                        "max_time": metric.max_time,
                        "errors": metric.errors,
                        "error_rate": metric.error_rate,
                        "last_updated": metric.last_updated.isoformat()
                    }
                    for name, metric in self.metrics.items()
                },
                "custom_metrics": {
                    name: [
                        {
                            "timestamp": point.timestamp.isoformat(),
                            "value": point.value,
                            "tags": point.tags,
                            "metadata": point.metadata
                        }
                        for point in points
                    ]
                    for name, points in self.custom_metrics.items()
                },
                "recent_errors": list(self.error_log),
                "system_health": self.get_system_health()
            }
        
        with open(filepath, 'w') as f:
            json.dump(export_data, f, indent=2)
        
        logger.info(f"Metrics exported to {filepath}")


# Global metrics collector instance
metrics_collector = MetricsCollector()


def monitor_endpoint(endpoint_name: Optional[str] = None):
    """
    Decorator to automatically monitor endpoint performance.
    
    Args:
        endpoint_name: Custom endpoint name (defaults to function name)
        
    Returns:
        Decorated function with monitoring
    """
    def decorator(func: Callable) -> Callable:
        @wraps(func)
        async def async_wrapper(*args, **kwargs):
            start_time = time.time()
            endpoint = endpoint_name or func.__name__
            method = "ASYNC"
            status_code = 200
            error_message = None
            
            try:
                result = await func(*args, **kwargs)
                return result
            except Exception as e:
                status_code = 500
                error_message = str(e)
                raise
            finally:
                response_time = (time.time() - start_time) * 1000
                metrics_collector.record_request(
                    endpoint=endpoint,
                    method=method,
                    status_code=status_code,
                    response_time=response_time,
                    error_message=error_message
                )
        
        @wraps(func)
        def sync_wrapper(*args, **kwargs):
            start_time = time.time()
            endpoint = endpoint_name or func.__name__
            method = "SYNC"
            status_code = 200
            error_message = None
            
            try:
                result = func(*args, **kwargs)
                return result
            except Exception as e:
                status_code = 500
                error_message = str(e)
                raise
            finally:
                response_time = (time.time() - start_time) * 1000
                metrics_collector.record_request(
                    endpoint=endpoint,
                    method=method,
                    status_code=status_code,
                    response_time=response_time,
                    error_message=error_message
                )
        
        # Return appropriate wrapper based on function type
        import asyncio
        if asyncio.iscoroutinefunction(func):
            return async_wrapper
        else:
            return sync_wrapper
    
    return decorator


@contextmanager
def monitor_operation(operation_name: str, tags: Optional[Dict[str, str]] = None):
    """
    Context manager to monitor custom operations.
    
    Args:
        operation_name: Name of the operation to monitor
        tags: Optional tags for categorization
        
    Yields:
        None
    """
    start_time = time.time()
    success = True
    error_message = None
    
    try:
        yield
    except Exception as e:
        success = False
        error_message = str(e)
        raise
    finally:
        duration = (time.time() - start_time) * 1000
        
        # Record custom metrics
        metrics_collector.record_custom_metric(
            f"{operation_name}_duration_ms",
            duration,
            tags=tags,
            metadata={"success": success, "error": error_message}
        )
        
        metrics_collector.record_custom_metric(
            f"{operation_name}_success_rate",
            1.0 if success else 0.0,
            tags=tags
        )


class AlertManager:
    """
    Alert management system for monitoring thresholds and notifications.
    """
    
    def __init__(self, metrics_collector: MetricsCollector):
        self.metrics_collector = metrics_collector
        self.alert_handlers: List[Callable] = []
    
    def add_alert_handler(self, handler: Callable[[str, Dict[str, Any]], None]):
        """
        Add an alert handler function.
        
        Args:
            handler: Function to call when alerts are triggered
        """
        self.alert_handlers.append(handler)
    
    def check_alerts(self) -> List[Dict[str, Any]]:
        """
        Check all alert conditions and return active alerts.
        
        Returns:
            List[Dict[str, Any]]: List of active alerts
        """
        alerts = []
        health = self.metrics_collector.get_system_health()
        
        if health["status"] != "healthy":
            alerts.append({
                "type": "system_health",
                "severity": "warning" if health["status"] == "warning" else "critical",
                "message": f"System health is {health['status']}",
                "details": health["issues"],
                "timestamp": datetime.utcnow().isoformat()
            })
        
        # Trigger alert handlers
        for alert in alerts:
            for handler in self.alert_handlers:
                try:
                    handler(alert["message"], alert)
                except Exception as e:
                    logger.error(f"Alert handler failed: {e}")
        
        return alerts


# Example alert handlers
def log_alert_handler(message: str, alert_data: Dict[str, Any]):
    """Log alert to file"""
    logger.warning(f"ALERT: {message} - {alert_data}")


def email_alert_handler(message: str, alert_data: Dict[str, Any]):
    """Send email alert (placeholder implementation)"""
    # In a real implementation, this would send an email
    logger.info(f"EMAIL ALERT: {message}")


# Initialize alert manager
alert_manager = AlertManager(metrics_collector)
alert_manager.add_alert_handler(log_alert_handler)


# Utility functions for easy metric recording
def record_user_action(action: str, user_id: str, success: bool = True, 
                      metadata: Optional[Dict[str, Any]] = None):
    """Record user action metrics"""
    metrics_collector.record_custom_metric(
        "user_actions",
        1.0,
        tags={"action": action, "user_id": user_id, "success": str(success)},
        metadata=metadata or {}
    )


def record_database_query(query_type: str, duration_ms: float, success: bool = True):
    """Record database query metrics"""
    metrics_collector.record_custom_metric(
        "database_query_duration_ms",
        duration_ms,
        tags={"query_type": query_type, "success": str(success)}
    )


def record_cache_operation(operation: str, hit: bool, duration_ms: float):
    """Record cache operation metrics"""
    metrics_collector.record_custom_metric(
        "cache_operations",
        1.0,
        tags={"operation": operation, "hit": str(hit)},
        metadata={"duration_ms": duration_ms}
    )


# Export the main collector for use in other modules
__all__ = [
    'metrics_collector',
    'monitor_endpoint',
    'monitor_operation',
    'alert_manager',
    'record_user_action',
    'record_database_query',
    'record_cache_operation'
]