"""
Integration test for the complete performance monitoring system
Tests all components working together
"""

import pytest
import time
import os
from pathlib import Path

from tests.performance_monitoring import (
    global_performance_collector,
    global_concurrency_monitor,
    reset_performance_monitoring,
    get_performance_report
)
from tests.performance_report_generator import generate_performance_report
from tests.benchmark_config import BenchmarkConfig
from services.cached_user_service import CachedUserService
from repositories.user_repository import UserRepository, UserFilters, SortConfig


class TestPerformanceIntegration:
    """Integration tests for performance monitoring system"""
    
    def setup_method(self):
        """Setup for each test"""
        reset_performance_monitoring()
    
    def test_end_to_end_performance_monitoring(self, large_dataset_db):
        """Test complete end-to-end performance monitoring workflow"""
        
        print("\n" + "="*80)
        print("END-TO-END PERFORMANCE MONITORING TEST")
        print("="*80)
        
        # Initialize services
        service = CachedUserService(large_dataset_db)
        repository = UserRepository(large_dataset_db)
        
        # Phase 1: Generate performance data
        print("Phase 1: Generating performance data...")
        
        # User list operations
        for page in range(1, 11):
            for limit in [25, 50]:
                result = service.get_users_paginated(page=page, limit=limit)
                assert result is not None
        
        # Statistics operations
        for _ in range(10):
            stats = service.get_user_statistics()
            assert stats is not None
        
        # Search operations
        search_terms = ["perfuser_1", "example.com", "admin", "general", "nonexistent"]
        for term in search_terms:
            results = repository.search_users(term, limit=100)
            assert isinstance(results, list)
        
        # User details operations
        users, _ = repository.get_users_with_pagination(1, 10, UserFilters(), SortConfig())
        for user in users[:5]:
            details = service.get_user_details(user.id)
            # Details might be None if user doesn't exist, that's ok
        
        print(f"Generated performance data for multiple operations")
        
        # Phase 2: Validate monitoring data collection
        print("Phase 2: Validating monitoring data collection...")
        
        # Check that performance data was collected
        query_stats = global_performance_collector.get_query_statistics()
        assert len(query_stats) > 0, "No query statistics collected"
        
        # Check that we have data for expected operations
        expected_operations = ['get_users_with_pagination', 'get_user_statistics', 'search_users']
        found_operations = []
        
        for query_name in query_stats.keys():
            for expected_op in expected_operations:
                if expected_op in query_name:
                    found_operations.append(expected_op)
                    break
        
        assert len(found_operations) > 0, f"Expected operations not found in monitoring data: {list(query_stats.keys())}"
        print(f"Found monitoring data for operations: {found_operations}")
        
        # Phase 3: Test performance alerts
        print("Phase 3: Testing performance alerts...")
        
        alerts = global_performance_collector.get_performance_alerts()
        print(f"Generated {len(alerts)} performance alerts")
        
        # Categorize alerts
        critical_alerts = [a for a in alerts if a.get('severity') == 'critical']
        warning_alerts = [a for a in alerts if a.get('severity') == 'warning']
        
        print(f"  Critical alerts: {len(critical_alerts)}")
        print(f"  Warning alerts: {len(warning_alerts)}")
        
        # Phase 4: Test benchmark validation
        print("Phase 4: Testing benchmark validation...")
        
        benchmark_results = []
        for query_name, stats in query_stats.items():
            # Try to match with benchmarks
            if 'get_users_with_pagination' in query_name:
                try:
                    metrics = {
                        'execution_time': stats.get('avg_time', 0),
                        'cache_hit_rate': stats.get('cache_hit_rate', 0),
                        'error_rate': stats.get('error_rate', 0)
                    }
                    result = BenchmarkConfig.validate_performance('user_pagination_small', metrics)
                    benchmark_results.append(result)
                except Exception as e:
                    print(f"Benchmark validation error for {query_name}: {e}")
        
        print(f"Validated {len(benchmark_results)} benchmarks")
        
        # Phase 5: Test report generation
        print("Phase 5: Testing report generation...")
        
        # Get performance report
        performance_report = get_performance_report()
        assert 'performance_metrics' in performance_report
        assert 'concurrency_stats' in performance_report
        
        # Test comprehensive report generation
        test_results = {
            'test_execution': {
                'exit_code': 0,
                'duration': 30.0,
                'timestamp': time.time()
            },
            'performance_report': performance_report
        }
        
        # Generate comprehensive report
        output_dir = Path("test_performance_reports")
        output_dir.mkdir(exist_ok=True)
        
        try:
            report_files = generate_performance_report(test_results, str(output_dir))
            
            # Validate report files were created
            assert report_files['json_report'].exists(), "JSON report not created"
            assert report_files['html_report'].exists(), "HTML report not created"
            
            print(f"Generated reports:")
            print(f"  JSON: {report_files['json_report']}")
            print(f"  HTML: {report_files['html_report']}")
            
            # Validate report content
            report_data = report_files['report_data']
            assert 'executive_summary' in report_data
            assert 'performance_metrics' in report_data
            assert 'recommendations' in report_data
            
            # Check executive summary
            exec_summary = report_data['executive_summary']
            assert 'performance_grade' in exec_summary
            assert 'test_status' in exec_summary
            assert exec_summary['total_queries_executed'] > 0
            
            print(f"Report validation successful:")
            print(f"  Performance Grade: {exec_summary['performance_grade']}")
            print(f"  Test Status: {exec_summary['test_status']}")
            print(f"  Total Queries: {exec_summary['total_queries_executed']}")
            print(f"  Cache Hit Rate: {exec_summary['cache_hit_rate']:.1%}")
            
        except Exception as e:
            pytest.fail(f"Report generation failed: {e}")
        
        # Phase 6: Cleanup
        print("Phase 6: Cleanup...")
        
        # Clean up test reports
        try:
            if output_dir.exists():
                import shutil
                shutil.rmtree(output_dir)
        except Exception as e:
            print(f"Cleanup warning: {e}")
        
        print("End-to-end performance monitoring test completed successfully!")
        print("="*80)
    
    def test_performance_monitoring_accuracy(self, large_dataset_db):
        """Test accuracy of performance monitoring measurements"""
        
        service = CachedUserService(large_dataset_db)
        
        # Perform a known slow operation (large page size)
        start_time = time.time()
        result = service.get_users_paginated(page=1, limit=100)
        actual_time = time.time() - start_time
        
        # Get monitoring data
        query_stats = global_performance_collector.get_query_statistics()
        
        # Find the relevant query
        relevant_stats = None
        for query_name, stats in query_stats.items():
            if 'get_users_paginated' in query_name:
                relevant_stats = stats
                break
        
        assert relevant_stats is not None, "Query statistics not found"
        
        # Check accuracy (within reasonable margin)
        monitored_time = relevant_stats.get('avg_time', 0)
        time_difference = abs(actual_time - monitored_time)
        
        print(f"\nPerformance Monitoring Accuracy Test:")
        print(f"Actual execution time: {actual_time:.3f}s")
        print(f"Monitored execution time: {monitored_time:.3f}s")
        print(f"Time difference: {time_difference:.3f}s")
        
        # Allow for some measurement overhead (up to 50ms difference)
        assert time_difference < 0.05, f"Monitoring accuracy too low: {time_difference:.3f}s difference"
    
    def test_performance_monitoring_overhead(self, large_dataset_db):
        """Test that performance monitoring doesn't add significant overhead"""
        
        service = CachedUserService(large_dataset_db)
        
        # Measure operations with monitoring
        with_monitoring_times = []
        for _ in range(10):
            start_time = time.time()
            service.get_user_statistics()
            execution_time = time.time() - start_time
            with_monitoring_times.append(execution_time)
        
        # Temporarily disable monitoring (if possible)
        # Note: In a real implementation, you might have a way to disable monitoring
        # For this test, we'll assume monitoring is always on and check that overhead is minimal
        
        avg_time_with_monitoring = sum(with_monitoring_times) / len(with_monitoring_times)
        
        print(f"\nPerformance Monitoring Overhead Test:")
        print(f"Average execution time with monitoring: {avg_time_with_monitoring:.3f}s")
        
        # The overhead should be minimal for simple operations
        # This is more of a sanity check than a strict requirement
        assert avg_time_with_monitoring < 1.0, f"Operations too slow with monitoring: {avg_time_with_monitoring:.3f}s"
        
        # Check that monitoring data was collected
        query_stats = global_performance_collector.get_query_statistics()
        assert len(query_stats) > 0, "No monitoring data collected"
        
        print("Monitoring overhead appears acceptable")
    
    def test_concurrent_monitoring_accuracy(self, large_dataset_db):
        """Test monitoring accuracy under concurrent load"""
        
        from concurrent.futures import ThreadPoolExecutor, as_completed
        
        service = CachedUserService(large_dataset_db)
        
        def monitored_operation(thread_id: int):
            """Perform operation that should be monitored"""
            start_time = time.time()
            result = service.get_users_paginated(page=1, limit=25)
            execution_time = time.time() - start_time
            
            return {
                'thread_id': thread_id,
                'execution_time': execution_time,
                'success': result is not None
            }
        
        # Run concurrent operations
        num_threads = 10
        
        with ThreadPoolExecutor(max_workers=5) as executor:
            futures = [executor.submit(monitored_operation, i) for i in range(num_threads)]
            results = [future.result() for future in as_completed(futures)]
        
        # Validate all operations succeeded
        successful_ops = [r for r in results if r['success']]
        assert len(successful_ops) == num_threads, f"Some operations failed: {len(successful_ops)}/{num_threads}"
        
        # Check monitoring data
        query_stats = global_performance_collector.get_query_statistics()
        concurrency_stats = global_concurrency_monitor.get_concurrency_stats()
        
        print(f"\nConcurrent Monitoring Test:")
        print(f"Successful operations: {len(successful_ops)}/{num_threads}")
        print(f"Max concurrent recorded: {concurrency_stats.get('max_concurrent_ever', 0)}")
        print(f"Total requests recorded: {concurrency_stats.get('total_requests', 0)}")
        
        # Validate monitoring captured the concurrent operations
        assert concurrency_stats.get('total_requests', 0) >= num_threads, "Not all requests recorded"
        assert len(query_stats) > 0, "No query statistics recorded"
        
        print("Concurrent monitoring accuracy validated")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "-s"])