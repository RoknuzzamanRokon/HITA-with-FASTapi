"""
Memory profiling tests for user management system
Tests memory usage patterns and identifies memory leaks
"""

import pytest
import gc
import psutil
import os
import time
from typing import Dict, Any, List
from memory_profiler import profile
import tracemalloc

from repositories.user_repository import UserRepository, UserFilters, SortConfig
from services.cached_user_service import CachedUserService
from tests.test_performance import PerformanceTestData


class MemoryProfiler:
    """Memory profiling utility"""
    
    def __init__(self):
        self.process = psutil.Process(os.getpid())
        self.baseline_memory = None
        self.peak_memory = 0
        self.memory_snapshots = []
    
    def start_profiling(self):
        """Start memory profiling"""
        gc.collect()  # Clean up before starting
        self.baseline_memory = self.process.memory_info().rss / 1024 / 1024  # MB
        self.peak_memory = self.baseline_memory
        self.memory_snapshots = []
        tracemalloc.start()
    
    def take_snapshot(self, label: str = ""):
        """Take a memory snapshot"""
        current_memory = self.process.memory_info().rss / 1024 / 1024  # MB
        self.peak_memory = max(self.peak_memory, current_memory)
        
        snapshot = {
            'label': label,
            'memory_mb': current_memory,
            'memory_delta': current_memory - self.baseline_memory,
            'timestamp': time.time()
        }
        
        self.memory_snapshots.append(snapshot)
        return snapshot
    
    def stop_profiling(self) -> Dict[str, Any]:
        """Stop profiling and return results"""
        final_memory = self.process.memory_info().rss / 1024 / 1024  # MB
        
        # Get tracemalloc statistics
        current, peak = tracemalloc.get_traced_memory()
        tracemalloc.stop()
        
        return {
            'baseline_memory_mb': self.baseline_memory,
            'final_memory_mb': final_memory,
            'peak_memory_mb': self.peak_memory,
            'memory_delta_mb': final_memory - self.baseline_memory,
            'tracemalloc_current_mb': current / 1024 / 1024,
            'tracemalloc_peak_mb': peak / 1024 / 1024,
            'snapshots': self.memory_snapshots
        }
    
    def get_memory_growth_rate(self) -> float:
        """Calculate memory growth rate MB/second"""
        if len(self.memory_snapshots) < 2:
            return 0.0
        
        first_snapshot = self.memory_snapshots[0]
        last_snapshot = self.memory_snapshots[-1]
        
        time_delta = last_snapshot['timestamp'] - first_snapshot['timestamp']
        memory_delta = last_snapshot['memory_mb'] - first_snapshot['memory_mb']
        
        return memory_delta / time_delta if time_delta > 0 else 0.0


class TestMemoryProfiling:
    """Memory profiling tests"""
    
    def test_user_repository_memory_usage(self, large_dataset_db):
        """Test memory usage of user repository operations"""
        profiler = MemoryProfiler()
        profiler.start_profiling()
        
        repository = UserRepository(large_dataset_db)
        filters = UserFilters()
        sort_config = SortConfig()
        
        # Test pagination memory usage
        profiler.take_snapshot("baseline")
        
        for page in range(1, 21):  # 20 pages
            users, total = repository.get_users_with_pagination(page, 50, filters, sort_config)
            
            if page % 5 == 0:
                profiler.take_snapshot(f"after_page_{page}")
        
        # Test search memory usage
        search_terms = ["perfuser_1", "example.com", "admin", "general"]
        for term in search_terms:
            results = repository.search_users(term, limit=100)
            profiler.take_snapshot(f"after_search_{term}")
        
        # Test statistics memory usage
        for i in range(10):
            stats = repository.get_user_statistics()
            if i % 3 == 0:
                profiler.take_snapshot(f"after_stats_{i}")
        
        # Test user details memory usage
        users, _ = repository.get_users_with_pagination(1, 10, filters, sort_config)
        for i, user in enumerate(users):
            details = repository.get_user_with_details(user.id)
            if i % 3 == 0:
                profiler.take_snapshot(f"after_details_{i}")
        
        results = profiler.stop_profiling()
        
        print(f"\nUser Repository Memory Usage:")
        print(f"Baseline memory: {results['baseline_memory_mb']:.2f} MB")
        print(f"Final memory: {results['final_memory_mb']:.2f} MB")
        print(f"Peak memory: {results['peak_memory_mb']:.2f} MB")
        print(f"Memory delta: {results['memory_delta_mb']:.2f} MB")
        print(f"Tracemalloc peak: {results['tracemalloc_peak_mb']:.2f} MB")
        
        # Print memory snapshots
        for snapshot in results['snapshots']:
            print(f"  {snapshot['label']}: {snapshot['memory_mb']:.2f} MB "
                  f"(+{snapshot['memory_delta']:.2f} MB)")
        
        # Memory usage should be reasonable
        assert results['peak_memory_mb'] < 200, f"Peak memory too high: {results['peak_memory_mb']:.2f} MB"
        assert results['memory_delta_mb'] < 50, f"Memory growth too high: {results['memory_delta_mb']:.2f} MB"
        
        # Check for memory leaks (growth rate)
        growth_rate = profiler.get_memory_growth_rate()
        print(f"Memory growth rate: {growth_rate:.3f} MB/s")
        
        # Growth rate should be minimal for read operations
        assert abs(growth_rate) < 1.0, f"Potential memory leak detected: {growth_rate:.3f} MB/s"
    
    def test_cached_service_memory_usage(self, large_dataset_db):
        """Test memory usage of cached service operations"""
        profiler = MemoryProfiler()
        profiler.start_profiling()
        
        service = CachedUserService(large_dataset_db)
        
        profiler.take_snapshot("baseline")
        
        # Test cached operations memory usage
        operations = [
            ("user_list_1", lambda: service.get_users_paginated(page=1, limit=25)),
            ("user_list_2", lambda: service.get_users_paginated(page=2, limit=25)),
            ("user_stats", lambda: service.get_user_statistics()),
            ("dashboard_stats", lambda: service.get_dashboard_statistics()),
        ]
        
        # First round - cache misses
        for op_name, operation in operations:
            operation()
            profiler.take_snapshot(f"first_{op_name}")
        
        # Second round - cache hits
        for op_name, operation in operations:
            operation()
            profiler.take_snapshot(f"second_{op_name}")
        
        # Third round - more cache hits
        for op_name, operation in operations:
            operation()
            profiler.take_snapshot(f"third_{op_name}")
        
        # Test user details caching
        repository = UserRepository(large_dataset_db)
        users, _ = repository.get_users_with_pagination(1, 5, UserFilters(), SortConfig())
        
        for user in users:
            service.get_user_details(user.id)  # Cache miss
            service.get_user_details(user.id)  # Cache hit
            profiler.take_snapshot(f"user_details_{user.id}")
        
        results = profiler.stop_profiling()
        
        print(f"\nCached Service Memory Usage:")
        print(f"Baseline memory: {results['baseline_memory_mb']:.2f} MB")
        print(f"Final memory: {results['final_memory_mb']:.2f} MB")
        print(f"Peak memory: {results['peak_memory_mb']:.2f} MB")
        print(f"Memory delta: {results['memory_delta_mb']:.2f} MB")
        print(f"Tracemalloc peak: {results['tracemalloc_peak_mb']:.2f} MB")
        
        # Print key snapshots
        key_snapshots = [s for s in results['snapshots'] if 'baseline' in s['label'] or 'third_' in s['label']]
        for snapshot in key_snapshots:
            print(f"  {snapshot['label']}: {snapshot['memory_mb']:.2f} MB "
                  f"(+{snapshot['memory_delta']:.2f} MB)")
        
        # Memory usage should be reasonable with caching
        assert results['peak_memory_mb'] < 300, f"Peak memory too high with caching: {results['peak_memory_mb']:.2f} MB"
        assert results['memory_delta_mb'] < 100, f"Memory growth too high with caching: {results['memory_delta_mb']:.2f} MB"
        
        # Check for memory leaks
        growth_rate = profiler.get_memory_growth_rate()
        print(f"Memory growth rate: {growth_rate:.3f} MB/s")
        
        # Some growth is expected due to caching, but should be bounded
        assert growth_rate < 2.0, f"Memory growth rate too high: {growth_rate:.3f} MB/s"
    
    def test_concurrent_operations_memory_usage(self, large_dataset_db):
        """Test memory usage under concurrent operations"""
        from concurrent.futures import ThreadPoolExecutor, as_completed
        
        profiler = MemoryProfiler()
        profiler.start_profiling()
        
        service = CachedUserService(large_dataset_db)
        
        def memory_intensive_operation(thread_id: int) -> Dict[str, Any]:
            """Perform memory-intensive operations"""
            try:
                # Mix of operations
                results = []
                
                # User list operations
                for page in range(1, 6):
                    result = service.get_users_paginated(page=page, limit=50)
                    results.append(len(result.get('users', [])))
                
                # Statistics operations
                for _ in range(3):
                    stats = service.get_user_statistics()
                    results.append(len(stats) if isinstance(stats, dict) else 1)
                
                # User details operations
                repository = UserRepository(large_dataset_db)
                users, _ = repository.get_users_with_pagination(1, 5, UserFilters(), SortConfig())
                for user in users:
                    details = service.get_user_details(user.id)
                    results.append(1 if details else 0)
                
                return {
                    'thread_id': thread_id,
                    'success': True,
                    'operations_count': len(results),
                    'total_results': sum(results)
                }
                
            except Exception as e:
                return {
                    'thread_id': thread_id,
                    'success': False,
                    'error': str(e)
                }
        
        profiler.take_snapshot("before_concurrent")
        
        # Run concurrent operations
        num_threads = 10
        
        with ThreadPoolExecutor(max_workers=5) as executor:
            futures = [executor.submit(memory_intensive_operation, i) for i in range(num_threads)]
            
            # Take snapshots during execution
            completed_count = 0
            for future in as_completed(futures):
                result = future.result()
                completed_count += 1
                
                if completed_count % 3 == 0:
                    profiler.take_snapshot(f"completed_{completed_count}")
        
        profiler.take_snapshot("after_concurrent")
        
        results = profiler.stop_profiling()
        
        print(f"\nConcurrent Operations Memory Usage:")
        print(f"Baseline memory: {results['baseline_memory_mb']:.2f} MB")
        print(f"Final memory: {results['final_memory_mb']:.2f} MB")
        print(f"Peak memory: {results['peak_memory_mb']:.2f} MB")
        print(f"Memory delta: {results['memory_delta_mb']:.2f} MB")
        print(f"Tracemalloc peak: {results['tracemalloc_peak_mb']:.2f} MB")
        
        # Print key snapshots
        key_snapshots = [s for s in results['snapshots'] 
                        if any(keyword in s['label'] for keyword in ['before_', 'after_', 'completed_'])]
        for snapshot in key_snapshots:
            print(f"  {snapshot['label']}: {snapshot['memory_mb']:.2f} MB "
                  f"(+{snapshot['memory_delta']:.2f} MB)")
        
        # Memory usage should be reasonable under concurrency
        assert results['peak_memory_mb'] < 500, f"Peak memory too high under concurrency: {results['peak_memory_mb']:.2f} MB"
        assert results['memory_delta_mb'] < 200, f"Memory growth too high under concurrency: {results['memory_delta_mb']:.2f} MB"
        
        # Check for memory leaks
        growth_rate = profiler.get_memory_growth_rate()
        print(f"Memory growth rate: {growth_rate:.3f} MB/s")
        
        # Some growth is expected, but should be bounded
        assert growth_rate < 5.0, f"Memory growth rate too high under concurrency: {growth_rate:.3f} MB/s"
    
    def test_large_dataset_memory_scaling(self, large_dataset_db):
        """Test memory usage scaling with large datasets"""
        profiler = MemoryProfiler()
        profiler.start_profiling()
        
        repository = UserRepository(large_dataset_db)
        
        # Test different page sizes and their memory impact
        page_sizes = [10, 25, 50, 100]
        
        profiler.take_snapshot("baseline")
        
        for page_size in page_sizes:
            # Test multiple pages with this page size
            for page in range(1, 6):
                users, total = repository.get_users_with_pagination(
                    page, page_size, UserFilters(), SortConfig()
                )
                
                # Force garbage collection to see actual memory usage
                gc.collect()
                
            profiler.take_snapshot(f"page_size_{page_size}")
        
        # Test large single queries
        large_queries = [
            ("large_page", lambda: repository.get_users_with_pagination(1, 200, UserFilters(), SortConfig())),
            ("search_all", lambda: repository.search_users("perf", limit=500)),
            ("statistics", lambda: repository.get_user_statistics()),
        ]
        
        for query_name, query_func in large_queries:
            query_func()
            gc.collect()
            profiler.take_snapshot(f"after_{query_name}")
        
        results = profiler.stop_profiling()
        
        print(f"\nLarge Dataset Memory Scaling:")
        print(f"Baseline memory: {results['baseline_memory_mb']:.2f} MB")
        print(f"Final memory: {results['final_memory_mb']:.2f} MB")
        print(f"Peak memory: {results['peak_memory_mb']:.2f} MB")
        print(f"Memory delta: {results['memory_delta_mb']:.2f} MB")
        
        # Analyze memory scaling by page size
        page_size_snapshots = [s for s in results['snapshots'] if 'page_size_' in s['label']]
        
        print("\nMemory usage by page size:")
        for snapshot in page_size_snapshots:
            page_size = snapshot['label'].split('_')[-1]
            print(f"  Page size {page_size}: {snapshot['memory_mb']:.2f} MB "
                  f"(+{snapshot['memory_delta']:.2f} MB)")
        
        # Memory should scale reasonably with page size
        if len(page_size_snapshots) >= 2:
            first_snapshot = page_size_snapshots[0]
            last_snapshot = page_size_snapshots[-1]
            
            memory_scaling = last_snapshot['memory_mb'] - first_snapshot['memory_mb']
            print(f"Memory scaling across page sizes: {memory_scaling:.2f} MB")
            
            # Memory scaling should be reasonable (not exponential)
            assert memory_scaling < 100, f"Memory scaling too high: {memory_scaling:.2f} MB"
        
        # Overall memory usage should be bounded
        assert results['peak_memory_mb'] < 400, f"Peak memory too high for large datasets: {results['peak_memory_mb']:.2f} MB"
    
    @profile
    def test_memory_profile_decorated_function(self, large_dataset_db):
        """Test function with memory_profiler decorator"""
        # This test uses the @profile decorator from memory_profiler
        # Run with: python -m memory_profiler test_memory_profiling.py::TestMemoryProfiling::test_memory_profile_decorated_function
        
        service = CachedUserService(large_dataset_db)
        
        # Perform various operations
        for i in range(10):
            service.get_users_paginated(page=1, limit=25)
            service.get_user_statistics()
            
            if i % 3 == 0:
                service.get_dashboard_statistics()
        
        # Test user details
        repository = UserRepository(large_dataset_db)
        users, _ = repository.get_users_with_pagination(1, 5, UserFilters(), SortConfig())
        
        for user in users:
            service.get_user_details(user.id)
        
        print("Memory profiling completed (see @profile output)")


def run_memory_analysis():
    """Run comprehensive memory analysis"""
    print("Running comprehensive memory analysis...")
    
    # This would be called from the performance test runner
    # to generate memory usage reports
    
    import subprocess
    import sys
    
    # Run memory profiling tests
    cmd = [
        sys.executable, "-m", "pytest", 
        "tests/test_memory_profiling.py", 
        "-v", "-s", "--tb=short"
    ]
    
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=300)
        
        print("Memory Analysis Results:")
        print("=" * 50)
        print(result.stdout)
        
        if result.stderr:
            print("Errors/Warnings:")
            print(result.stderr)
        
        return result.returncode == 0
        
    except subprocess.TimeoutExpired:
        print("Memory analysis timed out")
        return False
    except Exception as e:
        print(f"Error running memory analysis: {e}")
        return False


if __name__ == "__main__":
    # Run memory analysis
    success = run_memory_analysis()
    exit(0 if success else 1)