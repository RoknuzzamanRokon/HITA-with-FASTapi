"""
Performance tests for user management system
Tests query performance, caching effectiveness, and concurrent request handling
"""

import pytest
import time
import asyncio
import threading
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import List, Dict, Any
from datetime import datetime, timedelta
import statistics
import random
import string

from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from models import User, UserRole, UserPoint, PointTransaction, UserProviderPermission
from repositories.user_repository import UserRepository, UserFilters, SortConfig
from services.cached_user_service import CachedUserService
from cache_config import cache, CacheKeys
from repositories.repository_config import performance_monitor, repository_metrics, query_cache


class PerformanceTestData:
    """Helper class for generating test data"""
    
    @staticmethod
    def generate_random_string(length: int = 10) -> str:
        """Generate random string for test data"""
        return ''.join(random.choices(string.ascii_lowercase + string.digits, k=length))
    
    @staticmethod
    def create_test_users(db_session, count: int) -> List[User]:
        """Create multiple test users for performance testing"""
        users = []
        roles = [UserRole.GENERAL_USER, UserRole.ADMIN_USER, UserRole.SUPER_USER]
        
        for i in range(count):
            user = User(
                id=f"perf_user_{i:06d}",
                username=f"perfuser_{i}",
                email=f"perfuser_{i}@example.com",
                hashed_password=f"hashed_password_{i}",
                role=random.choice(roles),
                is_active=random.choice([True, False]),
                created_by="performance_test",
                created_at=datetime.utcnow() - timedelta(days=random.randint(0, 365)),
                updated_at=datetime.utcnow()
            )
            users.append(user)
        
        # Batch insert for better performance
        db_session.add_all(users)
        db_session.commit()
        
        return users
    
    @staticmethod
    def create_test_user_points(db_session, users: List[User]) -> List[UserPoint]:
        """Create user points for test users"""
        user_points = []
        
        for user in users:
            if random.random() > 0.3:  # 70% of users have points
                points = UserPoint(
                    user_id=user.id,
                    user_email=user.email,
                    total_points=random.randint(100, 10000),
                    current_points=random.randint(0, 5000),
                    total_used_points=random.randint(0, 5000)
                )
                user_points.append(points)
        
        db_session.add_all(user_points)
        db_session.commit()
        
        return user_points
    
    @staticmethod
    def create_test_transactions(db_session, users: List[User], count: int) -> List[PointTransaction]:
        """Create point transactions for activity testing"""
        transactions = []
        
        for i in range(count):
            giver = random.choice(users)
            receiver = random.choice(users)
            
            if giver.id != receiver.id:
                transaction = PointTransaction(
                    giver_id=giver.id,
                    giver_email=giver.email,
                    receiver_id=receiver.id,
                    receiver_email=receiver.email,
                    points=random.randint(1, 100),
                    transaction_type="transfer",
                    created_at=datetime.utcnow() - timedelta(days=random.randint(0, 30))
                )
                transactions.append(transaction)
        
        db_session.add_all(transactions)
        db_session.commit()
        
        return transactions


@pytest.fixture(scope="module")
def large_dataset_db():
    """Create database with large dataset for performance testing"""
    # Use in-memory SQLite database for testing
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    
    # Create all tables
    from database import Base
    Base.metadata.create_all(bind=engine)
    
    # Create session
    TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    session = TestingSessionLocal()
    
    # Create large dataset
    print("Creating large test dataset...")
    users = PerformanceTestData.create_test_users(session, 5000)
    user_points = PerformanceTestData.create_test_user_points(session, users)
    transactions = PerformanceTestData.create_test_transactions(session, users, 10000)
    
    # Create indexes for better performance (simulate production environment)
    session.execute(text("CREATE INDEX IF NOT EXISTS idx_users_email ON users(email)"))
    session.execute(text("CREATE INDEX IF NOT EXISTS idx_users_role ON users(role)"))
    session.execute(text("CREATE INDEX IF NOT EXISTS idx_users_is_active ON users(is_active)"))
    session.execute(text("CREATE INDEX IF NOT EXISTS idx_users_created_at ON users(created_at)"))
    session.execute(text("CREATE INDEX IF NOT EXISTS idx_user_points_user_id ON user_points(user_id)"))
    session.execute(text("CREATE INDEX IF NOT EXISTS idx_point_transactions_giver_receiver ON point_transactions(giver_id, receiver_id)"))
    session.execute(text("CREATE INDEX IF NOT EXISTS idx_point_transactions_created_at ON point_transactions(created_at)"))
    session.commit()
    
    print(f"Created {len(users)} users, {len(user_points)} user points, {len(transactions)} transactions")
    
    yield session
    
    session.close()


class TestQueryPerformance:
    """Test query performance with large datasets"""
    
    def test_user_pagination_performance(self, large_dataset_db):
        """Test pagination performance with large datasets"""
        repository = UserRepository(large_dataset_db)
        
        # Test different page sizes and positions
        test_cases = [
            (1, 25),    # First page, small size
            (1, 100),   # First page, large size
            (10, 25),   # Middle page
            (50, 25),   # Deep pagination
            (100, 25),  # Very deep pagination
        ]
        
        performance_results = []
        
        for page, limit in test_cases:
            filters = UserFilters()
            sort_config = SortConfig()
            
            start_time = time.time()
            users, total = repository.get_users_with_pagination(page, limit, filters, sort_config)
            execution_time = time.time() - start_time
            
            performance_results.append({
                'page': page,
                'limit': limit,
                'execution_time': execution_time,
                'result_count': len(users),
                'total_count': total
            })
            
            # Assert reasonable performance (adjust thresholds as needed)
            assert execution_time < 2.0, f"Pagination query too slow: {execution_time:.3f}s for page {page}"
            assert len(users) <= limit, f"Returned more results than limit: {len(users)} > {limit}"
        
        # Log performance results
        print("\nPagination Performance Results:")
        for result in performance_results:
            print(f"Page {result['page']}, Limit {result['limit']}: "
                  f"{result['execution_time']:.3f}s, {result['result_count']} results")
        
        # Test performance degradation with deep pagination
        shallow_time = performance_results[0]['execution_time']  # Page 1
        deep_time = performance_results[-1]['execution_time']    # Page 100
        
        # Deep pagination shouldn't be more than 3x slower than shallow
        assert deep_time < shallow_time * 3, f"Deep pagination too slow: {deep_time:.3f}s vs {shallow_time:.3f}s"
    
    def test_search_performance(self, large_dataset_db):
        """Test search query performance"""
        repository = UserRepository(large_dataset_db)
        
        # Test different search scenarios
        search_terms = [
            "perfuser_1",      # Exact match
            "perfuser_",       # Prefix match
            "example.com",     # Email domain search
            "nonexistent",     # No results
            "perf",           # Short term, many results
        ]
        
        performance_results = []
        
        for search_term in search_terms:
            start_time = time.time()
            results = repository.search_users(search_term, limit=100)
            execution_time = time.time() - start_time
            
            performance_results.append({
                'search_term': search_term,
                'execution_time': execution_time,
                'result_count': len(results)
            })
            
            # Assert reasonable performance
            assert execution_time < 1.0, f"Search query too slow: {execution_time:.3f}s for '{search_term}'"
        
        print("\nSearch Performance Results:")
        for result in performance_results:
            print(f"Search '{result['search_term']}': "
                  f"{result['execution_time']:.3f}s, {result['result_count']} results")
    
    def test_statistics_query_performance(self, large_dataset_db):
        """Test user statistics aggregation performance"""
        repository = UserRepository(large_dataset_db)
        
        # Test statistics query multiple times
        execution_times = []
        
        for i in range(5):
            start_time = time.time()
            stats = repository.get_user_statistics()
            execution_time = time.time() - start_time
            execution_times.append(execution_time)
            
            # Verify statistics are reasonable
            assert stats['total_users'] > 0
            assert stats['total_users'] == (stats['super_users'] + stats['admin_users'] + stats['general_users'])
            assert stats['total_users'] == (stats['active_users'] + stats['inactive_users'])
        
        avg_time = statistics.mean(execution_times)
        max_time = max(execution_times)
        
        print(f"\nStatistics Query Performance: avg={avg_time:.3f}s, max={max_time:.3f}s")
        
        # Statistics should be fast due to database aggregation
        assert avg_time < 0.5, f"Statistics query too slow: {avg_time:.3f}s average"
        assert max_time < 1.0, f"Statistics query max time too slow: {max_time:.3f}s"
    
    def test_filtered_query_performance(self, large_dataset_db):
        """Test performance of queries with various filters"""
        repository = UserRepository(large_dataset_db)
        
        # Test different filter combinations
        filter_scenarios = [
            UserFilters(role=UserRole.GENERAL_USER),
            UserFilters(is_active=True),
            UserFilters(search="perfuser_1"),
            UserFilters(role=UserRole.ADMIN_USER, is_active=True),
            UserFilters(has_points=True),
            UserFilters(activity_status="Active"),
            UserFilters(
                role=UserRole.GENERAL_USER,
                is_active=True,
                has_points=True,
                created_after=datetime.utcnow() - timedelta(days=30)
            )
        ]
        
        performance_results = []
        
        for i, filters in enumerate(filter_scenarios):
            sort_config = SortConfig()
            
            start_time = time.time()
            users, total = repository.get_users_with_pagination(1, 25, filters, sort_config)
            execution_time = time.time() - start_time
            
            performance_results.append({
                'scenario': i + 1,
                'execution_time': execution_time,
                'result_count': len(users),
                'total_count': total
            })
            
            # Assert reasonable performance
            assert execution_time < 1.5, f"Filtered query too slow: {execution_time:.3f}s for scenario {i+1}"
        
        print("\nFiltered Query Performance Results:")
        for result in performance_results:
            print(f"Scenario {result['scenario']}: "
                  f"{result['execution_time']:.3f}s, {result['result_count']}/{result['total_count']} results")
    
    def test_sorting_performance(self, large_dataset_db):
        """Test performance of different sorting options"""
        repository = UserRepository(large_dataset_db)
        filters = UserFilters()
        
        # Test different sorting configurations
        sort_scenarios = [
            SortConfig("created_at", "desc"),
            SortConfig("created_at", "asc"),
            SortConfig("username", "asc"),
            SortConfig("email", "asc"),
            SortConfig("role", "asc"),
            SortConfig("points", "desc"),  # Requires join
        ]
        
        performance_results = []
        
        for sort_config in sort_scenarios:
            start_time = time.time()
            users, total = repository.get_users_with_pagination(1, 50, filters, sort_config)
            execution_time = time.time() - start_time
            
            performance_results.append({
                'sort_by': sort_config.sort_by,
                'sort_order': sort_config.sort_order,
                'execution_time': execution_time,
                'result_count': len(users)
            })
            
            # Assert reasonable performance
            assert execution_time < 1.0, f"Sorting query too slow: {execution_time:.3f}s for {sort_config.sort_by}"
        
        print("\nSorting Performance Results:")
        for result in performance_results:
            print(f"Sort by {result['sort_by']} {result['sort_order']}: "
                  f"{result['execution_time']:.3f}s, {result['result_count']} results")


class TestCachingEffectiveness:
    """Test caching effectiveness and cache hit rates"""
    
    def setup_method(self):
        """Clear cache before each test"""
        cache.delete_pattern("*")
        query_cache.clear()
        repository_metrics.metrics = {
            'total_queries': 0,
            'cached_queries': 0,
            'cache_hits': 0,
            'cache_misses': 0,
            'avg_query_time': 0.0,
            'slow_queries': 0
        }
    
    def test_user_list_caching(self, large_dataset_db):
        """Test user list caching effectiveness"""
        service = CachedUserService(large_dataset_db)
        
        # First request - should be cache miss
        start_time = time.time()
        result1 = service.get_users_paginated(page=1, limit=25)
        first_request_time = time.time() - start_time
        
        # Second request - should be cache hit
        start_time = time.time()
        result2 = service.get_users_paginated(page=1, limit=25)
        second_request_time = time.time() - start_time
        
        # Third request with different parameters - should be cache miss
        start_time = time.time()
        result3 = service.get_users_paginated(page=2, limit=25)
        third_request_time = time.time() - start_time
        
        # Fourth request - repeat of first - should be cache hit
        start_time = time.time()
        result4 = service.get_users_paginated(page=1, limit=25)
        fourth_request_time = time.time() - start_time
        
        print(f"\nUser List Caching Performance:")
        print(f"First request (cache miss): {first_request_time:.3f}s")
        print(f"Second request (cache hit): {second_request_time:.3f}s")
        print(f"Third request (different params): {third_request_time:.3f}s")
        print(f"Fourth request (cache hit): {fourth_request_time:.3f}s")
        
        # Cache hits should be significantly faster
        assert second_request_time < first_request_time * 0.5, "Cache hit not significantly faster"
        assert fourth_request_time < first_request_time * 0.5, "Cache hit not significantly faster"
        
        # Results should be identical for cached requests
        assert result1 == result2, "Cached result differs from original"
        assert result1 == result4, "Cached result differs from original"
        assert result1 != result3, "Different parameters should return different results"
    
    def test_user_statistics_caching(self, large_dataset_db):
        """Test user statistics caching"""
        service = CachedUserService(large_dataset_db)
        
        # Multiple requests for statistics
        execution_times = []
        results = []
        
        for i in range(5):
            start_time = time.time()
            stats = service.get_user_statistics()
            execution_time = time.time() - start_time
            execution_times.append(execution_time)
            results.append(stats)
        
        print(f"\nStatistics Caching Performance:")
        for i, time_taken in enumerate(execution_times):
            print(f"Request {i+1}: {time_taken:.3f}s")
        
        # First request should be slower (cache miss)
        # Subsequent requests should be faster (cache hits)
        first_time = execution_times[0]
        subsequent_times = execution_times[1:]
        avg_subsequent_time = statistics.mean(subsequent_times)
        
        assert avg_subsequent_time < first_time * 0.3, "Cache hits not significantly faster for statistics"
        
        # All results should be identical
        for result in results[1:]:
            assert result == results[0], "Cached statistics result differs from original"
    
    def test_user_details_caching(self, large_dataset_db):
        """Test user details caching"""
        service = CachedUserService(large_dataset_db)
        
        # Get a user ID from the database
        repository = UserRepository(large_dataset_db)
        users, _ = repository.get_users_with_pagination(1, 1, UserFilters(), SortConfig())
        test_user_id = users[0].id
        
        # Test caching for user details
        execution_times = []
        results = []
        
        for i in range(3):
            start_time = time.time()
            details = service.get_user_details(test_user_id)
            execution_time = time.time() - start_time
            execution_times.append(execution_time)
            results.append(details)
        
        print(f"\nUser Details Caching Performance:")
        for i, time_taken in enumerate(execution_times):
            print(f"Request {i+1}: {time_taken:.3f}s")
        
        # Cache hits should be faster
        first_time = execution_times[0]
        subsequent_times = execution_times[1:]
        avg_subsequent_time = statistics.mean(subsequent_times)
        
        assert avg_subsequent_time < first_time * 0.5, "Cache hits not significantly faster for user details"
        
        # All results should be identical
        for result in results[1:]:
            assert result == results[0], "Cached user details result differs from original"
    
    def test_cache_invalidation(self, large_dataset_db):
        """Test cache invalidation functionality"""
        service = CachedUserService(large_dataset_db)
        
        # Get initial statistics (cache miss)
        stats1 = service.get_user_statistics()
        
        # Get statistics again (cache hit)
        start_time = time.time()
        stats2 = service.get_user_statistics()
        cached_time = time.time() - start_time
        
        # Invalidate cache
        service.invalidate_user_caches()
        
        # Get statistics after invalidation (cache miss)
        start_time = time.time()
        stats3 = service.get_user_statistics()
        post_invalidation_time = time.time() - start_time
        
        print(f"\nCache Invalidation Test:")
        print(f"Cached request time: {cached_time:.3f}s")
        print(f"Post-invalidation time: {post_invalidation_time:.3f}s")
        
        # Post-invalidation should be slower than cached request
        assert post_invalidation_time > cached_time * 2, "Cache invalidation not effective"
        
        # Results should still be the same (data hasn't changed)
        assert stats1 == stats2 == stats3, "Statistics results should be consistent"
    
    def test_cache_hit_rate_monitoring(self, large_dataset_db):
        """Test cache hit rate monitoring"""
        service = CachedUserService(large_dataset_db)
        
        # Make multiple requests to build up cache metrics
        for i in range(10):
            service.get_user_statistics()
            service.get_users_paginated(page=1, limit=25)
            service.get_users_paginated(page=2, limit=25)
        
        # Get cache metrics
        metrics = repository_metrics.get_metrics_summary()
        cache_hit_rate = repository_metrics.get_cache_hit_rate()
        
        print(f"\nCache Metrics:")
        print(f"Total queries: {metrics['total_queries']}")
        print(f"Cache hits: {metrics['cache_hits']}")
        print(f"Cache misses: {metrics['cache_misses']}")
        print(f"Cache hit rate: {cache_hit_rate:.2%}")
        
        # Should have a reasonable cache hit rate
        assert cache_hit_rate > 0.5, f"Cache hit rate too low: {cache_hit_rate:.2%}"
        assert metrics['cache_hits'] > 0, "No cache hits recorded"
        assert metrics['cache_misses'] > 0, "No cache misses recorded"


class TestConcurrentRequestHandling:
    """Test concurrent request handling and response times"""
    
    def test_concurrent_user_list_requests(self, large_dataset_db):
        """Test handling multiple concurrent user list requests"""
        service = CachedUserService(large_dataset_db)
        
        def make_request(request_id: int) -> Dict[str, Any]:
            """Make a single request and return timing info"""
            start_time = time.time()
            result = service.get_users_paginated(
                page=random.randint(1, 10),
                limit=random.randint(10, 50)
            )
            execution_time = time.time() - start_time
            
            return {
                'request_id': request_id,
                'execution_time': execution_time,
                'result_count': len(result.get('users', [])),
                'success': True
            }
        
        # Test with different numbers of concurrent requests
        concurrency_levels = [5, 10, 20, 50]
        
        for num_concurrent in concurrency_levels:
            print(f"\nTesting {num_concurrent} concurrent requests...")
            
            start_time = time.time()
            
            with ThreadPoolExecutor(max_workers=num_concurrent) as executor:
                futures = [executor.submit(make_request, i) for i in range(num_concurrent)]
                results = [future.result() for future in as_completed(futures)]
            
            total_time = time.time() - start_time
            
            # Analyze results
            execution_times = [r['execution_time'] for r in results]
            avg_time = statistics.mean(execution_times)
            max_time = max(execution_times)
            min_time = min(execution_times)
            
            print(f"Concurrent requests: {num_concurrent}")
            print(f"Total time: {total_time:.3f}s")
            print(f"Average request time: {avg_time:.3f}s")
            print(f"Max request time: {max_time:.3f}s")
            print(f"Min request time: {min_time:.3f}s")
            print(f"Requests per second: {num_concurrent / total_time:.1f}")
            
            # All requests should succeed
            assert all(r['success'] for r in results), "Some concurrent requests failed"
            
            # No request should take too long
            assert max_time < 5.0, f"Some requests too slow under concurrency: {max_time:.3f}s"
            
            # System should handle reasonable concurrency
            if num_concurrent <= 20:
                assert avg_time < 2.0, f"Average response time too slow: {avg_time:.3f}s"
    
    def test_concurrent_mixed_operations(self, large_dataset_db):
        """Test concurrent mixed read operations"""
        service = CachedUserService(large_dataset_db)
        repository = UserRepository(large_dataset_db)
        
        # Get some user IDs for testing
        users, _ = repository.get_users_with_pagination(1, 10, UserFilters(), SortConfig())
        user_ids = [user.id for user in users]
        
        def mixed_operation(operation_id: int) -> Dict[str, Any]:
            """Perform a random operation"""
            operation_type = random.choice(['list', 'stats', 'details', 'search'])
            start_time = time.time()
            
            try:
                if operation_type == 'list':
                    result = service.get_users_paginated(
                        page=random.randint(1, 5),
                        limit=random.randint(10, 30)
                    )
                elif operation_type == 'stats':
                    result = service.get_user_statistics()
                elif operation_type == 'details':
                    user_id = random.choice(user_ids)
                    result = service.get_user_details(user_id)
                elif operation_type == 'search':
                    search_term = f"perfuser_{random.randint(1, 100)}"
                    result = repository.search_users(search_term)
                
                execution_time = time.time() - start_time
                
                return {
                    'operation_id': operation_id,
                    'operation_type': operation_type,
                    'execution_time': execution_time,
                    'success': True,
                    'result_size': len(result) if isinstance(result, list) else 1
                }
                
            except Exception as e:
                execution_time = time.time() - start_time
                return {
                    'operation_id': operation_id,
                    'operation_type': operation_type,
                    'execution_time': execution_time,
                    'success': False,
                    'error': str(e)
                }
        
        # Test mixed concurrent operations
        num_operations = 30
        
        print(f"\nTesting {num_operations} concurrent mixed operations...")
        
        start_time = time.time()
        
        with ThreadPoolExecutor(max_workers=15) as executor:
            futures = [executor.submit(mixed_operation, i) for i in range(num_operations)]
            results = [future.result() for future in as_completed(futures)]
        
        total_time = time.time() - start_time
        
        # Analyze results by operation type
        operation_stats = {}
        successful_results = [r for r in results if r['success']]
        failed_results = [r for r in results if not r['success']]
        
        for result in successful_results:
            op_type = result['operation_type']
            if op_type not in operation_stats:
                operation_stats[op_type] = []
            operation_stats[op_type].append(result['execution_time'])
        
        print(f"Mixed Operations Results:")
        print(f"Total time: {total_time:.3f}s")
        print(f"Successful operations: {len(successful_results)}/{num_operations}")
        print(f"Failed operations: {len(failed_results)}")
        
        for op_type, times in operation_stats.items():
            avg_time = statistics.mean(times)
            max_time = max(times)
            count = len(times)
            print(f"{op_type}: {count} ops, avg={avg_time:.3f}s, max={max_time:.3f}s")
        
        # Most operations should succeed
        success_rate = len(successful_results) / num_operations
        assert success_rate > 0.9, f"Success rate too low: {success_rate:.2%}"
        
        # No operation should take too long
        if successful_results:
            max_execution_time = max(r['execution_time'] for r in successful_results)
            assert max_execution_time < 3.0, f"Some operations too slow: {max_execution_time:.3f}s"
        
        # Print any failures for debugging
        if failed_results:
            print("Failed operations:")
            for failure in failed_results:
                print(f"  {failure['operation_type']}: {failure['error']}")
    
    def test_database_connection_handling(self, large_dataset_db):
        """Test database connection handling under concurrent load"""
        def database_operation(op_id: int) -> Dict[str, Any]:
            """Perform database operation with new repository instance"""
            try:
                repository = UserRepository(large_dataset_db)
                
                start_time = time.time()
                users, total = repository.get_users_with_pagination(
                    1, 10, UserFilters(), SortConfig()
                )
                execution_time = time.time() - start_time
                
                return {
                    'op_id': op_id,
                    'execution_time': execution_time,
                    'result_count': len(users),
                    'success': True
                }
                
            except Exception as e:
                return {
                    'op_id': op_id,
                    'execution_time': 0,
                    'result_count': 0,
                    'success': False,
                    'error': str(e)
                }
        
        # Test database connection handling
        num_operations = 25
        
        print(f"\nTesting database connection handling with {num_operations} operations...")
        
        with ThreadPoolExecutor(max_workers=10) as executor:
            futures = [executor.submit(database_operation, i) for i in range(num_operations)]
            results = [future.result() for future in as_completed(futures)]
        
        successful_ops = [r for r in results if r['success']]
        failed_ops = [r for r in results if not r['success']]
        
        print(f"Database Connection Test Results:")
        print(f"Successful operations: {len(successful_ops)}/{num_operations}")
        print(f"Failed operations: {len(failed_ops)}")
        
        if successful_ops:
            avg_time = statistics.mean(r['execution_time'] for r in successful_ops)
            max_time = max(r['execution_time'] for r in successful_ops)
            print(f"Average execution time: {avg_time:.3f}s")
            print(f"Max execution time: {max_time:.3f}s")
        
        # Most operations should succeed
        success_rate = len(successful_ops) / num_operations
        assert success_rate > 0.95, f"Database connection success rate too low: {success_rate:.2%}"
        
        # Print any failures for debugging
        if failed_ops:
            print("Failed operations:")
            for failure in failed_ops:
                print(f"  Operation {failure['op_id']}: {failure['error']}")


class TestPerformanceMonitoring:
    """Test performance monitoring and metrics collection"""
    
    def test_query_performance_monitoring(self, large_dataset_db):
        """Test query performance monitoring functionality"""
        repository = UserRepository(large_dataset_db)
        
        # Clear previous performance data
        performance_monitor.query_stats.clear()
        
        # Perform various operations to generate performance data
        filters = UserFilters()
        sort_config = SortConfig()
        
        # Multiple pagination requests
        for page in range(1, 6):
            repository.get_users_with_pagination(page, 25, filters, sort_config)
        
        # Statistics requests
        for _ in range(3):
            repository.get_user_statistics()
        
        # Search requests
        search_terms = ["perfuser_1", "example.com", "nonexistent"]
        for term in search_terms:
            repository.search_users(term)
        
        # Get performance statistics
        query_stats = performance_monitor.query_stats
        slow_queries = performance_monitor.get_slow_queries(threshold_seconds=0.1)
        optimization_suggestions = performance_monitor.get_optimization_suggestions()
        
        print(f"\nPerformance Monitoring Results:")
        print(f"Monitored queries: {len(query_stats)}")
        
        for query_name, stats in query_stats.items():
            print(f"{query_name}:")
            print(f"  Executions: {stats['total_executions']}")
            print(f"  Avg time: {stats['avg_time']:.3f}s")
            print(f"  Max time: {stats['max_time']:.3f}s")
            print(f"  Min time: {stats['min_time']:.3f}s")
            print(f"  Avg results: {stats['avg_results']:.1f}")
        
        if slow_queries:
            print(f"\nSlow queries detected: {len(slow_queries)}")
            for query_name, stats in slow_queries.items():
                print(f"  {query_name}: {stats['avg_time']:.3f}s average")
        
        if optimization_suggestions:
            print(f"\nOptimization suggestions:")
            for suggestion in optimization_suggestions:
                print(f"  - {suggestion}")
        
        # Verify monitoring is working
        assert len(query_stats) > 0, "No query statistics collected"
        assert all(stats['total_executions'] > 0 for stats in query_stats.values()), "Invalid execution counts"
        assert all(stats['avg_time'] > 0 for stats in query_stats.values()), "Invalid timing data"
    
    def test_repository_metrics_collection(self, large_dataset_db):
        """Test repository metrics collection"""
        service = CachedUserService(large_dataset_db)
        
        # Clear previous metrics
        repository_metrics.metrics = {
            'total_queries': 0,
            'cached_queries': 0,
            'cache_hits': 0,
            'cache_misses': 0,
            'avg_query_time': 0.0,
            'slow_queries': 0
        }
        
        # Perform operations to generate metrics
        for i in range(10):
            service.get_users_paginated(page=1, limit=25)  # Should hit cache after first
            service.get_user_statistics()  # Should hit cache after first
        
        # Get comprehensive metrics
        metrics_summary = repository_metrics.get_metrics_summary()
        
        print(f"\nRepository Metrics Summary:")
        print(f"Total queries: {metrics_summary['total_queries']}")
        print(f"Cache hits: {metrics_summary['cache_hits']}")
        print(f"Cache misses: {metrics_summary['cache_misses']}")
        print(f"Cache hit rate: {metrics_summary['cache_hit_rate']:.2%}")
        
        if metrics_summary['performance_stats']:
            print(f"Performance stats available for {len(metrics_summary['performance_stats'])} queries")
        
        if metrics_summary['optimization_suggestions']:
            print("Optimization suggestions:")
            for suggestion in metrics_summary['optimization_suggestions']:
                print(f"  - {suggestion}")
        
        # Verify metrics collection
        assert metrics_summary['total_queries'] > 0, "No queries recorded in metrics"
        assert metrics_summary['cache_hit_rate'] >= 0, "Invalid cache hit rate"
        assert isinstance(metrics_summary['performance_stats'], dict), "Performance stats not collected"
    
    def test_cache_performance_monitoring(self, large_dataset_db):
        """Test cache performance monitoring"""
        service = CachedUserService(large_dataset_db)
        
        # Test cache performance with repeated requests
        cache_test_scenarios = [
            {'page': 1, 'limit': 25, 'iterations': 5},
            {'page': 2, 'limit': 25, 'iterations': 3},
            {'page': 1, 'limit': 50, 'iterations': 4},
        ]
        
        cache_performance_data = []
        
        for scenario in cache_test_scenarios:
            scenario_times = []
            
            for i in range(scenario['iterations']):
                start_time = time.time()
                result = service.get_users_paginated(
                    page=scenario['page'],
                    limit=scenario['limit']
                )
                execution_time = time.time() - start_time
                scenario_times.append(execution_time)
            
            cache_performance_data.append({
                'scenario': f"page_{scenario['page']}_limit_{scenario['limit']}",
                'times': scenario_times,
                'first_request': scenario_times[0],
                'avg_cached_requests': statistics.mean(scenario_times[1:]) if len(scenario_times) > 1 else 0,
                'cache_speedup': scenario_times[0] / statistics.mean(scenario_times[1:]) if len(scenario_times) > 1 else 1
            })
        
        print(f"\nCache Performance Monitoring:")
        for data in cache_performance_data:
            print(f"Scenario {data['scenario']}:")
            print(f"  First request (cache miss): {data['first_request']:.3f}s")
            if data['avg_cached_requests'] > 0:
                print(f"  Avg cached requests: {data['avg_cached_requests']:.3f}s")
                print(f"  Cache speedup: {data['cache_speedup']:.1f}x")
        
        # Verify cache is providing performance benefits
        for data in cache_performance_data:
            if data['cache_speedup'] > 1:
                assert data['cache_speedup'] > 2, f"Cache speedup too low: {data['cache_speedup']:.1f}x"


if __name__ == "__main__":
    # Run performance tests with verbose output
    pytest.main([__file__, "-v", "-s", "--tb=short"])