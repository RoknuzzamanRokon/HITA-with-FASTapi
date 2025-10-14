"""
Benchmark configuration for performance testing
Defines performance benchmarks and thresholds for user management system
"""

from typing import Dict, Any
from dataclasses import dataclass


@dataclass
class PerformanceBenchmark:
    """Performance benchmark definition"""
    name: str
    max_execution_time: float  # seconds
    max_memory_usage: int      # MB
    min_cache_hit_rate: float  # percentage (0.0 to 1.0)
    max_error_rate: float      # percentage (0.0 to 1.0)
    description: str


class BenchmarkConfig:
    """Configuration for performance benchmarks"""
    
    # Database query benchmarks
    QUERY_BENCHMARKS = {
        'user_pagination_small': PerformanceBenchmark(
            name='User Pagination (Small)',
            max_execution_time=0.5,
            max_memory_usage=50,
            min_cache_hit_rate=0.8,
            max_error_rate=0.01,
            description='Pagination with 25 users per page, first 10 pages'
        ),
        
        'user_pagination_large': PerformanceBenchmark(
            name='User Pagination (Large)',
            max_execution_time=1.0,
            max_memory_usage=100,
            min_cache_hit_rate=0.7,
            max_error_rate=0.01,
            description='Pagination with 100 users per page, deep pagination'
        ),
        
        'user_search': PerformanceBenchmark(
            name='User Search',
            max_execution_time=0.3,
            max_memory_usage=30,
            min_cache_hit_rate=0.6,
            max_error_rate=0.02,
            description='Search users by username or email'
        ),
        
        'user_statistics': PerformanceBenchmark(
            name='User Statistics',
            max_execution_time=0.2,
            max_memory_usage=20,
            min_cache_hit_rate=0.9,
            max_error_rate=0.01,
            description='Aggregate user statistics calculation'
        ),
        
        'user_details': PerformanceBenchmark(
            name='User Details',
            max_execution_time=0.1,
            max_memory_usage=10,
            min_cache_hit_rate=0.8,
            max_error_rate=0.01,
            description='Fetch detailed user information with relationships'
        ),
        
        'filtered_queries': PerformanceBenchmark(
            name='Filtered Queries',
            max_execution_time=0.8,
            max_memory_usage=80,
            min_cache_hit_rate=0.5,
            max_error_rate=0.02,
            description='Complex queries with multiple filters'
        )
    }
    
    # Caching benchmarks
    CACHE_BENCHMARKS = {
        'cache_hit_performance': PerformanceBenchmark(
            name='Cache Hit Performance',
            max_execution_time=0.01,  # Cache hits should be very fast
            max_memory_usage=5,
            min_cache_hit_rate=0.95,
            max_error_rate=0.001,
            description='Performance of cache hit operations'
        ),
        
        'cache_miss_performance': PerformanceBenchmark(
            name='Cache Miss Performance',
            max_execution_time=1.0,
            max_memory_usage=50,
            min_cache_hit_rate=0.0,  # N/A for cache misses
            max_error_rate=0.01,
            description='Performance of cache miss operations'
        ),
        
        'cache_invalidation': PerformanceBenchmark(
            name='Cache Invalidation',
            max_execution_time=0.05,
            max_memory_usage=10,
            min_cache_hit_rate=0.0,  # N/A for invalidation
            max_error_rate=0.001,
            description='Cache invalidation operation performance'
        )
    }
    
    # Concurrency benchmarks
    CONCURRENCY_BENCHMARKS = {
        'low_concurrency': PerformanceBenchmark(
            name='Low Concurrency (5 requests)',
            max_execution_time=2.0,
            max_memory_usage=100,
            min_cache_hit_rate=0.7,
            max_error_rate=0.02,
            description='Performance under low concurrent load'
        ),
        
        'medium_concurrency': PerformanceBenchmark(
            name='Medium Concurrency (20 requests)',
            max_execution_time=5.0,
            max_memory_usage=200,
            min_cache_hit_rate=0.6,
            max_error_rate=0.05,
            description='Performance under medium concurrent load'
        ),
        
        'high_concurrency': PerformanceBenchmark(
            name='High Concurrency (50 requests)',
            max_execution_time=10.0,
            max_memory_usage=500,
            min_cache_hit_rate=0.5,
            max_error_rate=0.1,
            description='Performance under high concurrent load'
        )
    }
    
    # Dataset size benchmarks
    DATASET_BENCHMARKS = {
        'small_dataset': PerformanceBenchmark(
            name='Small Dataset (1K users)',
            max_execution_time=0.5,
            max_memory_usage=50,
            min_cache_hit_rate=0.8,
            max_error_rate=0.01,
            description='Performance with small dataset'
        ),
        
        'medium_dataset': PerformanceBenchmark(
            name='Medium Dataset (10K users)',
            max_execution_time=1.0,
            max_memory_usage=100,
            min_cache_hit_rate=0.7,
            max_error_rate=0.01,
            description='Performance with medium dataset'
        ),
        
        'large_dataset': PerformanceBenchmark(
            name='Large Dataset (100K users)',
            max_execution_time=2.0,
            max_memory_usage=200,
            min_cache_hit_rate=0.6,
            max_error_rate=0.02,
            description='Performance with large dataset'
        )
    }
    
    @classmethod
    def get_all_benchmarks(cls) -> Dict[str, PerformanceBenchmark]:
        """Get all defined benchmarks"""
        all_benchmarks = {}
        all_benchmarks.update(cls.QUERY_BENCHMARKS)
        all_benchmarks.update(cls.CACHE_BENCHMARKS)
        all_benchmarks.update(cls.CONCURRENCY_BENCHMARKS)
        all_benchmarks.update(cls.DATASET_BENCHMARKS)
        return all_benchmarks
    
    @classmethod
    def get_benchmark(cls, name: str) -> PerformanceBenchmark:
        """Get specific benchmark by name"""
        all_benchmarks = cls.get_all_benchmarks()
        if name not in all_benchmarks:
            raise ValueError(f"Benchmark '{name}' not found. Available: {list(all_benchmarks.keys())}")
        return all_benchmarks[name]
    
    @classmethod
    def validate_performance(cls, benchmark_name: str, metrics: Dict[str, Any]) -> Dict[str, Any]:
        """
        Validate performance metrics against benchmark
        
        Returns:
            Dictionary with validation results
        """
        benchmark = cls.get_benchmark(benchmark_name)
        
        results = {
            'benchmark_name': benchmark_name,
            'benchmark': benchmark,
            'metrics': metrics,
            'passed': True,
            'failures': [],
            'warnings': []
        }
        
        # Check execution time
        execution_time = metrics.get('execution_time', 0)
        if execution_time > benchmark.max_execution_time:
            results['passed'] = False
            results['failures'].append(
                f"Execution time {execution_time:.3f}s exceeds benchmark {benchmark.max_execution_time:.3f}s"
            )
        elif execution_time > benchmark.max_execution_time * 0.8:
            results['warnings'].append(
                f"Execution time {execution_time:.3f}s is close to benchmark limit {benchmark.max_execution_time:.3f}s"
            )
        
        # Check memory usage (if available)
        memory_usage = metrics.get('memory_usage_mb', 0)
        if memory_usage > benchmark.max_memory_usage:
            results['passed'] = False
            results['failures'].append(
                f"Memory usage {memory_usage}MB exceeds benchmark {benchmark.max_memory_usage}MB"
            )
        elif memory_usage > benchmark.max_memory_usage * 0.8:
            results['warnings'].append(
                f"Memory usage {memory_usage}MB is close to benchmark limit {benchmark.max_memory_usage}MB"
            )
        
        # Check cache hit rate (if applicable)
        cache_hit_rate = metrics.get('cache_hit_rate', 1.0)
        if cache_hit_rate < benchmark.min_cache_hit_rate:
            results['passed'] = False
            results['failures'].append(
                f"Cache hit rate {cache_hit_rate:.1%} below benchmark {benchmark.min_cache_hit_rate:.1%}"
            )
        elif cache_hit_rate < benchmark.min_cache_hit_rate * 1.1:
            results['warnings'].append(
                f"Cache hit rate {cache_hit_rate:.1%} is close to benchmark minimum {benchmark.min_cache_hit_rate:.1%}"
            )
        
        # Check error rate
        error_rate = metrics.get('error_rate', 0)
        if error_rate > benchmark.max_error_rate:
            results['passed'] = False
            results['failures'].append(
                f"Error rate {error_rate:.1%} exceeds benchmark {benchmark.max_error_rate:.1%}"
            )
        elif error_rate > benchmark.max_error_rate * 0.8:
            results['warnings'].append(
                f"Error rate {error_rate:.1%} is close to benchmark limit {benchmark.max_error_rate:.1%}"
            )
        
        return results


# Performance test scenarios
PERFORMANCE_TEST_SCENARIOS = {
    'basic_operations': {
        'description': 'Basic CRUD operations performance',
        'benchmarks': ['user_pagination_small', 'user_search', 'user_details'],
        'dataset_size': 1000,
        'iterations': 10
    },
    
    'heavy_load': {
        'description': 'Heavy load performance testing',
        'benchmarks': ['user_pagination_large', 'filtered_queries', 'medium_concurrency'],
        'dataset_size': 10000,
        'iterations': 5
    },
    
    'cache_effectiveness': {
        'description': 'Cache performance and effectiveness',
        'benchmarks': ['cache_hit_performance', 'cache_miss_performance', 'user_statistics'],
        'dataset_size': 5000,
        'iterations': 20
    },
    
    'scalability': {
        'description': 'System scalability under load',
        'benchmarks': ['high_concurrency', 'large_dataset', 'filtered_queries'],
        'dataset_size': 50000,
        'iterations': 3
    }
}


def get_performance_thresholds() -> Dict[str, float]:
    """Get performance thresholds for monitoring"""
    return {
        'slow_query_threshold': 1.0,      # seconds
        'very_slow_query_threshold': 3.0, # seconds
        'cache_hit_rate_threshold': 0.7,  # 70%
        'error_rate_threshold': 0.05,     # 5%
        'memory_usage_threshold': 500,    # MB
        'concurrent_request_threshold': 100
    }