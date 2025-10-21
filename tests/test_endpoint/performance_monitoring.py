"""
Performance monitoring utilities for user management system
Provides tools for monitoring query performance, cache effectiveness, and system metrics
"""

import time
import threading
import statistics
from typing import Dict, List, Any, Optional, Callable
from datetime import datetime, timedelta
from dataclasses import dataclass, field
from collections import defaultdict, deque
import json
import logging

logger = logging.getLogger(__name__)


@dataclass
class QueryMetrics:
    """Metrics for a single query execution"""
    query_name: str
    execution_time: float
    result_count: int
    timestamp: datetime
    parameters: Dict[str, Any] = field(default_factory=dict)
    cache_hit: bool = False
    error: Optional[str] = None


@dataclass
class PerformanceThresholds:
    """Performance thresholds for monitoring"""
    slow_query_threshold: float = 1.0  # seconds
    very_slow_query_threshold: float = 3.0  # seconds
    large_result_threshold: int = 1000  # number of results
    cache_hit_rate_threshold: float = 0.7  # 70%
    concurrent_request_threshold: int = 50  # max concurrent requests


class PerformanceCollector:
    """Collects and analyzes performance metrics"""
    
    def __init__(self, max_metrics: int = 10000):
        self.metrics: deque = deque(maxlen=max_metrics)
        self.query_stats: Dict[str, Dict[str, Any]] = defaultdict(lambda: {
            'count': 0,
            'total_time': 0.0,
            'min_time': float('inf'),
            'max_time': 0.0,
            'total_results': 0,
            'cache_hits': 0,
            'errors': 0,
            'recent_times': deque(maxlen=100)
        })
        self.thresholds = PerformanceThresholds()
        self._lock = threading.Lock()
    
    def record_query(self, metrics: QueryMetrics):
        """Record query execution metrics"""
        with self._lock:
            self.metrics.append(metrics)
            
            stats = self.query_stats[metrics.query_name]
            stats['count'] += 1
            stats['total_time'] += metrics.execution_time
            stats['min_time'] = min(stats['min_time'], metrics.execution_time)
            stats['max_time'] = max(stats['max_time'], metrics.execution_time)
            stats['total_results'] += metrics.result_count
            stats['recent_times'].append(metrics.execution_time)
            
            if metrics.cache_hit:
                stats['cache_hits'] += 1
            
            if metrics.error:
                stats['errors'] += 1
    
    def get_query_statistics(self, query_name: Optional[str] = None) -> Dict[str, Any]:
        """Get statistics for a specific query or all queries"""
        with self._lock:
            if query_name:
                if query_name not in self.query_stats:
                    return {}
                
                stats = self.query_stats[query_name].copy()
                stats['avg_time'] = stats['total_time'] / stats['count'] if stats['count'] > 0 else 0
                stats['avg_results'] = stats['total_results'] / stats['count'] if stats['count'] > 0 else 0
                stats['cache_hit_rate'] = stats['cache_hits'] / stats['count'] if stats['count'] > 0 else 0
                stats['error_rate'] = stats['errors'] / stats['count'] if stats['count'] > 0 else 0
                
                # Calculate recent performance trend
                if stats['recent_times']:
                    recent_avg = statistics.mean(stats['recent_times'])
                    stats['recent_avg_time'] = recent_avg
                    
                    if len(stats['recent_times']) > 10:
                        first_half = list(stats['recent_times'])[:len(stats['recent_times'])//2]
                        second_half = list(stats['recent_times'])[len(stats['recent_times'])//2:]
                        
                        if first_half and second_half:
                            trend = statistics.mean(second_half) - statistics.mean(first_half)
                            stats['performance_trend'] = 'improving' if trend < 0 else 'degrading' if trend > 0 else 'stable'
                        else:
                            stats['performance_trend'] = 'stable'
                    else:
                        stats['performance_trend'] = 'insufficient_data'
                
                return stats
            else:
                # Return statistics for all queries
                all_stats = {}
                for name, raw_stats in self.query_stats.items():
                    all_stats[name] = self.get_query_statistics(name)
                return all_stats
    
    def get_slow_queries(self, threshold: Optional[float] = None) -> Dict[str, Dict[str, Any]]:
        """Get queries that exceed performance thresholds"""
        threshold = threshold or self.thresholds.slow_query_threshold
        
        slow_queries = {}
        all_stats = self.get_query_statistics()
        
        for query_name, stats in all_stats.items():
            if stats.get('avg_time', 0) > threshold:
                slow_queries[query_name] = stats
        
        return slow_queries
    
    def get_performance_alerts(self) -> List[Dict[str, Any]]:
        """Get performance alerts based on thresholds"""
        alerts = []
        all_stats = self.get_query_statistics()
        
        for query_name, stats in all_stats.items():
            # Slow query alert
            if stats.get('avg_time', 0) > self.thresholds.slow_query_threshold:
                severity = 'critical' if stats['avg_time'] > self.thresholds.very_slow_query_threshold else 'warning'
                alerts.append({
                    'type': 'slow_query',
                    'severity': severity,
                    'query_name': query_name,
                    'avg_time': stats['avg_time'],
                    'threshold': self.thresholds.slow_query_threshold,
                    'message': f"Query '{query_name}' averaging {stats['avg_time']:.3f}s (threshold: {self.thresholds.slow_query_threshold}s)"
                })
            
            # Large result set alert
            if stats.get('avg_results', 0) > self.thresholds.large_result_threshold:
                alerts.append({
                    'type': 'large_result_set',
                    'severity': 'warning',
                    'query_name': query_name,
                    'avg_results': stats['avg_results'],
                    'threshold': self.thresholds.large_result_threshold,
                    'message': f"Query '{query_name}' returning large result sets (avg: {stats['avg_results']:.0f})"
                })
            
            # Low cache hit rate alert
            if stats.get('cache_hit_rate', 0) < self.thresholds.cache_hit_rate_threshold and stats.get('count', 0) > 10:
                alerts.append({
                    'type': 'low_cache_hit_rate',
                    'severity': 'warning',
                    'query_name': query_name,
                    'cache_hit_rate': stats['cache_hit_rate'],
                    'threshold': self.thresholds.cache_hit_rate_threshold,
                    'message': f"Query '{query_name}' has low cache hit rate: {stats['cache_hit_rate']:.1%}"
                })
            
            # High error rate alert
            if stats.get('error_rate', 0) > 0.1 and stats.get('count', 0) > 5:  # 10% error rate
                alerts.append({
                    'type': 'high_error_rate',
                    'severity': 'critical',
                    'query_name': query_name,
                    'error_rate': stats['error_rate'],
                    'message': f"Query '{query_name}' has high error rate: {stats['error_rate']:.1%}"
                })
            
            # Performance degradation alert
            if stats.get('performance_trend') == 'degrading' and stats.get('count', 0) > 20:
                alerts.append({
                    'type': 'performance_degradation',
                    'severity': 'warning',
                    'query_name': query_name,
                    'recent_avg_time': stats.get('recent_avg_time', 0),
                    'message': f"Query '{query_name}' performance is degrading"
                })
        
        return sorted(alerts, key=lambda x: {'critical': 0, 'warning': 1}.get(x['severity'], 2))
    
    def get_performance_summary(self) -> Dict[str, Any]:
        """Get comprehensive performance summary"""
        with self._lock:
            total_queries = sum(stats['count'] for stats in self.query_stats.values())
            total_cache_hits = sum(stats['cache_hits'] for stats in self.query_stats.values())
            total_errors = sum(stats['errors'] for stats in self.query_stats.values())
            
            # Calculate overall metrics
            overall_cache_hit_rate = total_cache_hits / total_queries if total_queries > 0 else 0
            overall_error_rate = total_errors / total_queries if total_queries > 0 else 0
            
            # Get recent metrics (last hour)
            recent_cutoff = datetime.utcnow() - timedelta(hours=1)
            recent_metrics = [m for m in self.metrics if m.timestamp >= recent_cutoff]
            
            recent_avg_time = statistics.mean([m.execution_time for m in recent_metrics]) if recent_metrics else 0
            recent_query_rate = len(recent_metrics) / 60 if recent_metrics else 0  # queries per minute
            
            # Identify top queries by various metrics
            all_stats = self.get_query_statistics()
            
            top_by_frequency = sorted(all_stats.items(), key=lambda x: x[1].get('count', 0), reverse=True)[:5]
            top_by_avg_time = sorted(all_stats.items(), key=lambda x: x[1].get('avg_time', 0), reverse=True)[:5]
            top_by_total_time = sorted(all_stats.items(), key=lambda x: x[1].get('total_time', 0), reverse=True)[:5]
            
            return {
                'overview': {
                    'total_queries': total_queries,
                    'unique_queries': len(self.query_stats),
                    'overall_cache_hit_rate': overall_cache_hit_rate,
                    'overall_error_rate': overall_error_rate,
                    'recent_avg_time': recent_avg_time,
                    'recent_query_rate': recent_query_rate
                },
                'top_queries': {
                    'by_frequency': [(name, stats['count']) for name, stats in top_by_frequency],
                    'by_avg_time': [(name, stats['avg_time']) for name, stats in top_by_avg_time],
                    'by_total_time': [(name, stats['total_time']) for name, stats in top_by_total_time]
                },
                'alerts': self.get_performance_alerts(),
                'slow_queries': self.get_slow_queries(),
                'thresholds': {
                    'slow_query_threshold': self.thresholds.slow_query_threshold,
                    'cache_hit_rate_threshold': self.thresholds.cache_hit_rate_threshold,
                    'large_result_threshold': self.thresholds.large_result_threshold
                }
            }
    
    def export_metrics(self, format: str = 'json') -> str:
        """Export metrics in specified format"""
        summary = self.get_performance_summary()
        
        if format.lower() == 'json':
            return json.dumps(summary, indent=2, default=str)
        elif format.lower() == 'csv':
            # Simple CSV export of query statistics
            lines = ['query_name,count,avg_time,max_time,cache_hit_rate,error_rate']
            all_stats = self.get_query_statistics()
            
            for query_name, stats in all_stats.items():
                lines.append(f"{query_name},{stats['count']},{stats['avg_time']:.3f},"
                           f"{stats['max_time']:.3f},{stats['cache_hit_rate']:.3f},{stats['error_rate']:.3f}")
            
            return '\n'.join(lines)
        else:
            raise ValueError(f"Unsupported export format: {format}")
    
    def clear_metrics(self, older_than: Optional[timedelta] = None):
        """Clear metrics, optionally only those older than specified time"""
        with self._lock:
            if older_than:
                cutoff = datetime.utcnow() - older_than
                # Remove old metrics
                self.metrics = deque([m for m in self.metrics if m.timestamp >= cutoff], maxlen=self.metrics.maxlen)
                
                # Recalculate query stats from remaining metrics
                self.query_stats.clear()
                for metric in self.metrics:
                    # Simplified recalculation - in production, you might want more sophisticated logic
                    stats = self.query_stats[metric.query_name]
                    stats['count'] += 1
                    stats['total_time'] += metric.execution_time
                    stats['total_results'] += metric.result_count
                    if metric.cache_hit:
                        stats['cache_hits'] += 1
                    if metric.error:
                        stats['errors'] += 1
            else:
                self.metrics.clear()
                self.query_stats.clear()


class ConcurrencyMonitor:
    """Monitor concurrent request handling"""
    
    def __init__(self):
        self.active_requests: Dict[str, datetime] = {}
        self.request_history: deque = deque(maxlen=1000)
        self.max_concurrent = 0
        self.total_requests = 0
        self._lock = threading.Lock()
    
    def start_request(self, request_id: str):
        """Mark start of a request"""
        with self._lock:
            self.active_requests[request_id] = datetime.utcnow()
            self.total_requests += 1
            current_concurrent = len(self.active_requests)
            self.max_concurrent = max(self.max_concurrent, current_concurrent)
    
    def end_request(self, request_id: str):
        """Mark end of a request"""
        with self._lock:
            if request_id in self.active_requests:
                start_time = self.active_requests.pop(request_id)
                duration = (datetime.utcnow() - start_time).total_seconds()
                
                self.request_history.append({
                    'request_id': request_id,
                    'start_time': start_time,
                    'duration': duration,
                    'concurrent_count': len(self.active_requests) + 1  # +1 because we just removed this one
                })
    
    def get_concurrency_stats(self) -> Dict[str, Any]:
        """Get concurrency statistics"""
        with self._lock:
            current_concurrent = len(self.active_requests)
            
            if self.request_history:
                recent_requests = [r for r in self.request_history 
                                 if r['start_time'] >= datetime.utcnow() - timedelta(minutes=5)]
                
                avg_duration = statistics.mean([r['duration'] for r in recent_requests]) if recent_requests else 0
                avg_concurrent = statistics.mean([r['concurrent_count'] for r in recent_requests]) if recent_requests else 0
                max_recent_concurrent = max([r['concurrent_count'] for r in recent_requests]) if recent_requests else 0
                
                return {
                    'current_concurrent': current_concurrent,
                    'max_concurrent_ever': self.max_concurrent,
                    'max_concurrent_recent': max_recent_concurrent,
                    'avg_concurrent_recent': avg_concurrent,
                    'total_requests': self.total_requests,
                    'avg_duration_recent': avg_duration,
                    'recent_request_count': len(recent_requests)
                }
            else:
                return {
                    'current_concurrent': current_concurrent,
                    'max_concurrent_ever': self.max_concurrent,
                    'total_requests': self.total_requests,
                    'avg_duration_recent': 0,
                    'recent_request_count': 0
                }


def performance_monitor_decorator(collector: PerformanceCollector, query_name: str = None):
    """Decorator to monitor function performance"""
    def decorator(func: Callable) -> Callable:
        def wrapper(*args, **kwargs):
            name = query_name or f"{func.__module__}.{func.__name__}"
            start_time = time.time()
            error = None
            result = None
            result_count = 0
            
            try:
                result = func(*args, **kwargs)
                
                # Determine result count
                if isinstance(result, (list, tuple)):
                    result_count = len(result)
                elif isinstance(result, dict) and 'users' in result:
                    result_count = len(result.get('users', []))
                elif hasattr(result, '__len__'):
                    result_count = len(result)
                
            except Exception as e:
                error = str(e)
                raise
            finally:
                execution_time = time.time() - start_time
                
                metrics = QueryMetrics(
                    query_name=name,
                    execution_time=execution_time,
                    result_count=result_count,
                    timestamp=datetime.utcnow(),
                    parameters=kwargs,
                    error=error
                )
                
                collector.record_query(metrics)
            
            return result
        return wrapper
    return decorator


# Global instances
global_performance_collector = PerformanceCollector()
global_concurrency_monitor = ConcurrencyMonitor()


def get_performance_report() -> Dict[str, Any]:
    """Get comprehensive performance report"""
    return {
        'performance_metrics': global_performance_collector.get_performance_summary(),
        'concurrency_stats': global_concurrency_monitor.get_concurrency_stats(),
        'timestamp': datetime.utcnow().isoformat()
    }


def reset_performance_monitoring():
    """Reset all performance monitoring data"""
    global_performance_collector.clear_metrics()
    global_concurrency_monitor.active_requests.clear()
    global_concurrency_monitor.request_history.clear()
    global_concurrency_monitor.max_concurrent = 0
    global_concurrency_monitor.total_requests = 0