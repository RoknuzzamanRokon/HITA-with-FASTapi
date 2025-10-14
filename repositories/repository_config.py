"""
Repository configuration and caching utilities
"""

from typing import Dict, Any, Optional, Callable, List
from functools import wraps
from datetime import datetime, timedelta
import hashlib
import json


class RepositoryConfig:
    """Configuration settings for repository layer"""
    
    # Default pagination settings
    DEFAULT_PAGE_SIZE = 25
    MAX_PAGE_SIZE = 100
    
    # Query optimization settings
    ENABLE_QUERY_CACHE = True
    CACHE_TTL_SECONDS = 300  # 5 minutes
    MAX_CACHE_SIZE = 1000
    
    # Performance settings
    LARGE_DATASET_THRESHOLD = 10000
    DEEP_PAGINATION_THRESHOLD = 100
    ENABLE_CURSOR_PAGINATION = True
    
    # Search settings
    MAX_SEARCH_RESULTS = 500
    MIN_SEARCH_LENGTH = 2
    
    # Bulk operation settings
    MAX_BULK_SIZE = 1000
    BULK_BATCH_SIZE = 100


class QueryCache:
    """Simple in-memory cache for query results"""
    
    def __init__(self, max_size: int = 1000, ttl_seconds: int = 300):
        self.cache: Dict[str, Dict[str, Any]] = {}
        self.max_size = max_size
        self.ttl_seconds = ttl_seconds
    
    def _generate_key(self, query_params: Dict[str, Any]) -> str:
        """Generate cache key from query parameters"""
        # Sort parameters for consistent key generation
        sorted_params = json.dumps(query_params, sort_keys=True, default=str)
        return hashlib.md5(sorted_params.encode()).hexdigest()
    
    def get(self, query_params: Dict[str, Any]) -> Optional[Any]:
        """Get cached result if available and not expired"""
        if not RepositoryConfig.ENABLE_QUERY_CACHE:
            return None
            
        key = self._generate_key(query_params)
        
        if key in self.cache:
            cache_entry = self.cache[key]
            if datetime.utcnow() < cache_entry['expires_at']:
                return cache_entry['data']
            else:
                # Remove expired entry
                del self.cache[key]
        
        return None
    
    def set(self, query_params: Dict[str, Any], data: Any) -> None:
        """Cache query result"""
        if not RepositoryConfig.ENABLE_QUERY_CACHE:
            return
            
        key = self._generate_key(query_params)
        
        # Remove oldest entries if cache is full
        if len(self.cache) >= self.max_size:
            oldest_key = min(self.cache.keys(), 
                           key=lambda k: self.cache[k]['created_at'])
            del self.cache[oldest_key]
        
        self.cache[key] = {
            'data': data,
            'created_at': datetime.utcnow(),
            'expires_at': datetime.utcnow() + timedelta(seconds=self.ttl_seconds)
        }
    
    def clear(self) -> None:
        """Clear all cached entries"""
        self.cache.clear()
    
    def clear_expired(self) -> int:
        """Remove expired entries and return count of removed entries"""
        now = datetime.utcnow()
        expired_keys = [
            key for key, entry in self.cache.items()
            if now >= entry['expires_at']
        ]
        
        for key in expired_keys:
            del self.cache[key]
        
        return len(expired_keys)


# Global cache instance
query_cache = QueryCache(
    max_size=RepositoryConfig.MAX_CACHE_SIZE,
    ttl_seconds=RepositoryConfig.CACHE_TTL_SECONDS
)


def cached_query(cache_key_params: list = None):
    """
    Decorator for caching query results
    
    Args:
        cache_key_params: List of parameter names to include in cache key
    """
    def decorator(func: Callable) -> Callable:
        @wraps(func)
        def wrapper(*args, **kwargs):
            if not RepositoryConfig.ENABLE_QUERY_CACHE:
                return func(*args, **kwargs)
            
            # Build cache key from specified parameters
            cache_params = {}
            if cache_key_params:
                for param in cache_key_params:
                    if param in kwargs:
                        cache_params[param] = kwargs[param]
            else:
                # Use all kwargs as cache key
                cache_params = kwargs.copy()
            
            # Add function name to cache key for uniqueness
            cache_params['_func'] = func.__name__
            
            # Try to get from cache
            cached_result = query_cache.get(cache_params)
            if cached_result is not None:
                return cached_result
            
            # Execute function and cache result
            result = func(*args, **kwargs)
            query_cache.set(cache_params, result)
            
            return result
        
        return wrapper
    return decorator


class PerformanceMonitor:
    """Monitor query performance and provide optimization suggestions"""
    
    def __init__(self):
        self.query_stats: Dict[str, Dict[str, Any]] = {}
    
    def record_query(
        self,
        query_name: str,
        execution_time: float,
        result_count: int,
        parameters: Dict[str, Any] = None
    ):
        """Record query execution statistics"""
        if query_name not in self.query_stats:
            self.query_stats[query_name] = {
                'total_executions': 0,
                'total_time': 0.0,
                'avg_time': 0.0,
                'max_time': 0.0,
                'min_time': float('inf'),
                'total_results': 0,
                'avg_results': 0.0
            }
        
        stats = self.query_stats[query_name]
        stats['total_executions'] += 1
        stats['total_time'] += execution_time
        stats['avg_time'] = stats['total_time'] / stats['total_executions']
        stats['max_time'] = max(stats['max_time'], execution_time)
        stats['min_time'] = min(stats['min_time'], execution_time)
        stats['total_results'] += result_count
        stats['avg_results'] = stats['total_results'] / stats['total_executions']
    
    def get_slow_queries(self, threshold_seconds: float = 1.0) -> Dict[str, Dict[str, Any]]:
        """Get queries that exceed the performance threshold"""
        return {
            name: stats for name, stats in self.query_stats.items()
            if stats['avg_time'] > threshold_seconds
        }
    
    def get_optimization_suggestions(self) -> List[str]:
        """Get optimization suggestions based on query patterns"""
        suggestions = []
        
        slow_queries = self.get_slow_queries()
        if slow_queries:
            suggestions.append(
                f"Consider optimizing {len(slow_queries)} slow queries: "
                f"{', '.join(slow_queries.keys())}"
            )
        
        # Check for queries with large result sets
        large_result_queries = {
            name: stats for name, stats in self.query_stats.items()
            if stats['avg_results'] > 1000
        }
        
        if large_result_queries:
            suggestions.append(
                "Consider adding pagination or filtering to queries with large result sets: "
                f"{', '.join(large_result_queries.keys())}"
            )
        
        return suggestions


# Global performance monitor
performance_monitor = PerformanceMonitor()


def monitor_performance(query_name: str = None):
    """Decorator for monitoring query performance"""
    def decorator(func: Callable) -> Callable:
        @wraps(func)
        def wrapper(*args, **kwargs):
            import time
            
            start_time = time.time()
            result = func(*args, **kwargs)
            execution_time = time.time() - start_time
            
            # Determine result count
            result_count = 0
            if isinstance(result, (list, tuple)):
                result_count = len(result)
            elif isinstance(result, tuple) and len(result) >= 2:
                # Assume (results, count) tuple
                if isinstance(result[1], int):
                    result_count = result[1]
                elif isinstance(result[0], (list, tuple)):
                    result_count = len(result[0])
            
            # Record performance
            name = query_name or func.__name__
            performance_monitor.record_query(
                name, execution_time, result_count, kwargs
            )
            
            return result
        
        return wrapper
    return decorator


class RepositoryMetrics:
    """Collect and provide repository usage metrics"""
    
    def __init__(self):
        self.metrics = {
            'total_queries': 0,
            'cached_queries': 0,
            'cache_hits': 0,
            'cache_misses': 0,
            'avg_query_time': 0.0,
            'slow_queries': 0
        }
    
    def increment_query_count(self):
        """Increment total query count"""
        self.metrics['total_queries'] += 1
    
    def record_cache_hit(self):
        """Record cache hit"""
        self.metrics['cache_hits'] += 1
        self.metrics['cached_queries'] += 1
    
    def record_cache_miss(self):
        """Record cache miss"""
        self.metrics['cache_misses'] += 1
    
    def get_cache_hit_rate(self) -> float:
        """Calculate cache hit rate"""
        total_cache_attempts = self.metrics['cache_hits'] + self.metrics['cache_misses']
        if total_cache_attempts == 0:
            return 0.0
        return self.metrics['cache_hits'] / total_cache_attempts
    
    def get_metrics_summary(self) -> Dict[str, Any]:
        """Get comprehensive metrics summary"""
        return {
            **self.metrics,
            'cache_hit_rate': self.get_cache_hit_rate(),
            'performance_stats': performance_monitor.query_stats,
            'optimization_suggestions': performance_monitor.get_optimization_suggestions()
        }


# Global metrics instance
repository_metrics = RepositoryMetrics()