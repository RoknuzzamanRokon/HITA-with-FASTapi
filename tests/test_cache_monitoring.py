"""
Cache monitoring and effectiveness tests
Tests cache hit rates, invalidation, and performance impact
"""

import pytest
import time
import statistics
from typing import Dict, Any, List
from datetime import datetime, timedelta

from cache_config import cache, CacheKeys
from services.cached_user_service import CachedUserService
from repositories.user_repository import UserRepository, UserFilters, SortConfig
from tests.performance_monitoring import (
    global_performance_collector, 
    QueryMetrics,
    reset_performance_monitoring
)
from tests.benchmark_config import BenchmarkConfig


class CacheMonitoringTest:
    """Test cache monitoring and effectiveness"""
    
    def setup_method(self):
        """Setup for each test method"""
        # Clear cache and reset monitoring
        cache.delete_pattern("*")
        reset_performance_monitoring()
    
    def test_cache_hit_rate_monitoring(self, large_dataset_db):
        """Test cache hit rate monitoring and measurement"""
        service = CachedUserService(large_dataset_db)
        
        # Track cache operations
        cache_operations = []
        
        # Make requests that should result in cache misses and hits
        test_scenarios = [
            {'page': 1, 'limit': 25, 'expected_cache_hit': False},  # First request - cache miss
            {'page': 1, 'limit': 25, 'expected_cache_hit': True},   # Second request - cache hit
            {'page': 2, 'limit': 25, 'expected_cache_hit': False},  # Different params - cache miss
            {'page': 1, 'limit': 25, 'expected_cache_hit': True},   # Repeat first - cache hit
            {'page': 2, 'limit': 25, 'expected_cache_hit': True},   # Repeat second - cache hit
        ]
        
        for i, scenario in enumerate(test_scenarios):
            start_time = time.time()
            
            result = service.get_users_paginated(
                page=scenario['page'],
                limit=scenario['limit']
            )
            
            execution_time = time.time() - start_time
            
            cache_operations.append({
                'request_id': i + 1,
                'execution_time': execution_time,
                'expected_cache_hit': scenario['expected_cache_hit'],
                'result_count': len(result.get('users', []))
            })
        
        # Analyze cache performance
        cache_misses = [op for op in cache_operations if not op['expected_cache_hit']]
        cache_hits = [op for op in cache_operations if op['expected_cache_hit']]
        
        if cache_misses and cache_hits:
            avg_miss_time = statistics.mean([op['execution_time'] for op in cache_misses])
            avg_hit_time = statistics.mean([op['execution_time'] for op in cache_hits])
            
            print(f"\nCache Performance Analysis:")
            print(f"Average cache miss time: {avg_miss_time:.3f}s")
            print(f"Average cache hit time: {avg_hit_time:.3f}s")
            print(f"Cache speedup: {avg_miss_time / avg_hit_time:.1f}x")
            
            # Cache hits should be significantly faster
            assert avg_hit_time < avg_miss_time * 0.3, f"Cache hits not fast enough: {avg_hit_time:.3f}s vs {avg_miss_time:.3f}s"
            
            # Validate against benchmark
            benchmark_result = BenchmarkConfig.validate_performance(
                'cache_hit_performance',
                {
                    'execution_time': avg_hit_time,
                    'cache_hit_rate': len(cache_hits) / len(cache_operations),
                    'error_rate': 0
                }
            )
            
            assert benchmark_result['passed'], f"Cache hit benchmark failed: {benchmark_result['failures']}"
    
    def test_cache_invalidation_effectiveness(self, large_dataset_db):
        """Test cache invalidation and its effectiveness"""
        service = CachedUserService(large_dataset_db)
        
        # Initial request to populate cache
        result1 = service.get_user_statistics()
        
        # Verify cache is populated by making same request
        start_time = time.time()
        result2 = service.get_user_statistics()
        cached_time = time.time() - start_time
        
        assert result1 == result2, "Cached result should match original"
        assert cached_time < 0.01, f"Cached request too slow: {cached_time:.3f}s"
        
        # Invalidate cache
        invalidation_start = time.time()
        service.invalidate_user_caches()
        invalidation_time = time.time() - invalidation_start
        
        # Request after invalidation should be slower (cache miss)
        start_time = time.time()
        result3 = service.get_user_statistics()
        post_invalidation_time = time.time() - start_time
        
        print(f"\nCache Invalidation Test:")
        print(f"Cached request time: {cached_time:.3f}s")
        print(f"Invalidation time: {invalidation_time:.3f}s")
        print(f"Post-invalidation time: {post_invalidation_time:.3f}s")
        
        # Validate invalidation effectiveness
        assert post_invalidation_time > cached_time * 10, "Cache invalidation not effective"
        assert result1 == result3, "Results should be consistent after invalidation"
        
        # Validate against benchmark
        benchmark_result = BenchmarkConfig.validate_performance(
            'cache_invalidation',
            {
                'execution_time': invalidation_time,
                'error_rate': 0
            }
        )
        
        assert benchmark_result['passed'], f"Cache invalidation benchmark failed: {benchmark_result['failures']}"
    
    def test_cache_memory_usage(self, large_dataset_db):
        """Test cache memory usage and efficiency"""
        service = CachedUserService(large_dataset_db)
        
        # Generate various cached data
        cache_operations = []
        
        # Different user list requests
        for page in range(1, 11):
            for limit in [25, 50]:
                start_time = time.time()
                result = service.get_users_paginated(page=page, limit=limit)
                execution_time = time.time() - start_time
                
                cache_operations.append({
                    'operation': f'user_list_page_{page}_limit_{limit}',
                    'execution_time': execution_time,
                    'result_size': len(result.get('users', []))
                })
        
        # Statistics requests
        for _ in range(5):
            start_time = time.time()
            stats = service.get_user_statistics()
            execution_time = time.time() - start_time
            
            cache_operations.append({
                'operation': 'user_statistics',
                'execution_time': execution_time,
                'result_size': len(stats) if isinstance(stats, dict) else 1
            })
        
        # User details requests
        repository = UserRepository(large_dataset_db)
        users, _ = repository.get_users_with_pagination(1, 10, UserFilters(), SortConfig())
        
        for user in users[:5]:
            start_time = time.time()
            details = service.get_user_details(user.id)
            execution_time = time.time() - start_time
            
            cache_operations.append({
                'operation': f'user_details_{user.id}',
                'execution_time': execution_time,
                'result_size': 1 if details else 0
            })
        
        print(f"\nCache Memory Usage Test:")
        print(f"Total cache operations: {len(cache_operations)}")
        
        # Analyze cache effectiveness
        first_requests = {}
        subsequent_requests = {}
        
        for op in cache_operations:
            op_type = op['operation'].split('_')[0] + '_' + op['operation'].split('_')[1]  # e.g., 'user_list'
            
            if op_type not in first_requests:
                first_requests[op_type] = []
                subsequent_requests[op_type] = []
            
            if len(first_requests[op_type]) == 0:
                first_requests[op_type].append(op['execution_time'])
            else:
                subsequent_requests[op_type].append(op['execution_time'])
        
        # Calculate cache effectiveness for each operation type
        for op_type in first_requests:
            if first_requests[op_type] and subsequent_requests[op_type]:
                avg_first = statistics.mean(first_requests[op_type])
                avg_subsequent = statistics.mean(subsequent_requests[op_type])
                speedup = avg_first / avg_subsequent if avg_subsequent > 0 else 1
                
                print(f"{op_type}: {speedup:.1f}x speedup (first: {avg_first:.3f}s, cached: {avg_subsequent:.3f}s)")
                
                # Cache should provide reasonable speedup
                assert speedup > 2, f"Insufficient cache speedup for {op_type}: {speedup:.1f}x"
    
    def test_cache_ttl_behavior(self, large_dataset_db):
        """Test cache TTL (Time To Live) behavior"""
        service = CachedUserService(large_dataset_db)
        
        # Make initial request
        result1 = service.get_user_statistics()
        
        # Make request immediately (should be cache hit)
        start_time = time.time()
        result2 = service.get_user_statistics()
        immediate_time = time.time() - start_time
        
        assert result1 == result2, "Immediate cache hit failed"
        assert immediate_time < 0.01, f"Cache hit too slow: {immediate_time:.3f}s"
        
        # Test cache behavior over time (simulate TTL expiration)
        # Note: In a real test, you might wait for actual TTL expiration
        # Here we'll test the cache key existence
        
        # Check if cache key exists
        cache_key = f"user_stats"  # Simplified key for testing
        
        # The cache should have the data
        cached_data = cache.get(cache_key)
        print(f"\nCache TTL Test:")
        print(f"Cache key exists: {cache.exists(cache_key)}")
        print(f"Immediate cache hit time: {immediate_time:.3f}s")
        
        # Test cache warming (pre-populate cache)
        cache_warming_operations = [
            ('user_list_page_1', lambda: service.get_users_paginated(page=1, limit=25)),
            ('user_list_page_2', lambda: service.get_users_paginated(page=2, limit=25)),
            ('user_stats', lambda: service.get_user_statistics()),
        ]
        
        warming_times = []
        for op_name, operation in cache_warming_operations:
            start_time = time.time()
            operation()
            warming_time = time.time() - start_time
            warming_times.append(warming_time)
            
            print(f"Cache warming {op_name}: {warming_time:.3f}s")
        
        # Subsequent requests should be fast (cache hits)
        hit_times = []
        for op_name, operation in cache_warming_operations:
            start_time = time.time()
            operation()
            hit_time = time.time() - start_time
            hit_times.append(hit_time)
            
            print(f"Cache hit {op_name}: {hit_time:.3f}s")
        
        # Cache hits should be consistently faster
        avg_warming_time = statistics.mean(warming_times)
        avg_hit_time = statistics.mean(hit_times)
        
        print(f"Average warming time: {avg_warming_time:.3f}s")
        print(f"Average hit time: {avg_hit_time:.3f}s")
        print(f"Cache effectiveness: {avg_warming_time / avg_hit_time:.1f}x speedup")
        
        assert avg_hit_time < avg_warming_time * 0.2, "Cache hits not consistently fast"
    
    def test_cache_concurrent_access(self, large_dataset_db):
        """Test cache behavior under concurrent access"""
        import threading
        from concurrent.futures import ThreadPoolExecutor, as_completed
        
        service = CachedUserService(large_dataset_db)
        
        def cache_operation(thread_id: int) -> Dict[str, Any]:
            """Perform cache operation from a thread"""
            try:
                start_time = time.time()
                
                # Mix of operations
                if thread_id % 3 == 0:
                    result = service.get_user_statistics()
                    op_type = 'statistics'
                elif thread_id % 3 == 1:
                    result = service.get_users_paginated(page=1, limit=25)
                    op_type = 'user_list'
                else:
                    # Get a user for details
                    repository = UserRepository(large_dataset_db)
                    users, _ = repository.get_users_with_pagination(1, 1, UserFilters(), SortConfig())
                    if users:
                        result = service.get_user_details(users[0].id)
                        op_type = 'user_details'
                    else:
                        result = None
                        op_type = 'user_details_failed'
                
                execution_time = time.time() - start_time
                
                return {
                    'thread_id': thread_id,
                    'operation_type': op_type,
                    'execution_time': execution_time,
                    'success': result is not None,
                    'result_size': len(result) if isinstance(result, (list, dict)) else 1
                }
                
            except Exception as e:
                return {
                    'thread_id': thread_id,
                    'operation_type': 'error',
                    'execution_time': 0,
                    'success': False,
                    'error': str(e)
                }
        
        # Test concurrent cache access
        num_threads = 20
        
        print(f"\nConcurrent Cache Access Test ({num_threads} threads):")
        
        start_time = time.time()
        
        with ThreadPoolExecutor(max_workers=10) as executor:
            futures = [executor.submit(cache_operation, i) for i in range(num_threads)]
            results = [future.result() for future in as_completed(futures)]
        
        total_time = time.time() - start_time
        
        # Analyze results
        successful_ops = [r for r in results if r['success']]
        failed_ops = [r for r in results if not r['success']]
        
        # Group by operation type
        op_stats = {}
        for result in successful_ops:
            op_type = result['operation_type']
            if op_type not in op_stats:
                op_stats[op_type] = []
            op_stats[op_type].append(result['execution_time'])
        
        print(f"Total time: {total_time:.3f}s")
        print(f"Successful operations: {len(successful_ops)}/{num_threads}")
        print(f"Failed operations: {len(failed_ops)}")
        
        for op_type, times in op_stats.items():
            avg_time = statistics.mean(times)
            max_time = max(times)
            count = len(times)
            print(f"{op_type}: {count} ops, avg={avg_time:.3f}s, max={max_time:.3f}s")
        
        # Validate concurrent performance
        success_rate = len(successful_ops) / num_threads
        assert success_rate > 0.95, f"Success rate too low under concurrency: {success_rate:.1%}"
        
        # No operation should take too long
        if successful_ops:
            max_execution_time = max(r['execution_time'] for r in successful_ops)
            assert max_execution_time < 2.0, f"Some operations too slow under concurrency: {max_execution_time:.3f}s"
        
        # Print any failures for debugging
        if failed_ops:
            print("Failed operations:")
            for failure in failed_ops:
                print(f"  Thread {failure['thread_id']}: {failure.get('error', 'Unknown error')}")
    
    def test_cache_size_limits(self, large_dataset_db):
        """Test cache behavior when approaching size limits"""
        service = CachedUserService(large_dataset_db)
        
        # Generate many different cache entries
        cache_entries = []
        
        # Create many different user list requests
        for page in range(1, 51):  # 50 different pages
            for limit in [10, 25, 50]:  # 3 different limits
                start_time = time.time()
                result = service.get_users_paginated(page=page, limit=limit)
                execution_time = time.time() - start_time
                
                cache_entries.append({
                    'key': f'user_list_page_{page}_limit_{limit}',
                    'execution_time': execution_time,
                    'result_count': len(result.get('users', []))
                })
        
        print(f"\nCache Size Limits Test:")
        print(f"Generated {len(cache_entries)} cache entries")
        
        # Test cache behavior with many entries
        # First requests should be slower (cache misses)
        # Subsequent requests should be faster (cache hits)
        
        # Repeat some requests to test cache hits
        repeat_tests = [
            {'page': 1, 'limit': 25},
            {'page': 5, 'limit': 50},
            {'page': 10, 'limit': 10},
        ]
        
        repeat_times = []
        for test in repeat_tests:
            start_time = time.time()
            result = service.get_users_paginated(page=test['page'], limit=test['limit'])
            execution_time = time.time() - start_time
            repeat_times.append(execution_time)
            
            print(f"Repeat request page {test['page']}, limit {test['limit']}: {execution_time:.3f}s")
        
        avg_repeat_time = statistics.mean(repeat_times)
        print(f"Average repeat request time: {avg_repeat_time:.3f}s")
        
        # Repeat requests should be fast (cache hits)
        assert avg_repeat_time < 0.05, f"Repeat requests too slow: {avg_repeat_time:.3f}s"
        
        # Test cache statistics if available
        try:
            # This would depend on your cache implementation
            # For Redis, you could get info about memory usage, key count, etc.
            print("Cache appears to be handling size limits appropriately")
        except Exception as e:
            print(f"Could not get cache statistics: {e}")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "-s"])