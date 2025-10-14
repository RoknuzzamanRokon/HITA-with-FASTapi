#!/usr/bin/env python3
"""
Test script for caching functionality
"""

import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from cache_config import cache, CacheConfig, cached, CacheKeys
from services.cached_user_service import CachedUserService
from database import SessionLocal
import time
import logging

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def test_basic_cache_operations():
    """Test basic cache operations"""
    print("\n=== Testing Basic Cache Operations ===")
    
    # Test cache availability
    print(f"Cache available: {cache.is_available}")
    
    if not cache.is_available:
        print("Redis cache is not available. Please ensure Redis is running.")
        return False
    
    # Test basic operations
    test_key = "test_key"
    test_value = {"message": "Hello, Cache!", "timestamp": time.time()}
    
    # Test set
    set_result = cache.set(test_key, test_value, 60)
    print(f"Set operation: {set_result}")
    
    # Test get
    get_result = cache.get(test_key)
    print(f"Get operation: {get_result}")
    print(f"Values match: {get_result == test_value}")
    
    # Test exists
    exists_result = cache.exists(test_key)
    print(f"Exists operation: {exists_result}")
    
    # Test delete
    delete_result = cache.delete(test_key)
    print(f"Delete operation: {delete_result}")
    
    # Test get after delete
    get_after_delete = cache.get(test_key)
    print(f"Get after delete: {get_after_delete}")
    
    return True

def test_cached_decorator():
    """Test the cached decorator"""
    print("\n=== Testing Cached Decorator ===")
    
    @cached(ttl=30, key_prefix="test")
    def expensive_function(x, y):
        """Simulate an expensive function"""
        print(f"Executing expensive function with {x}, {y}")
        time.sleep(0.1)  # Simulate work
        return x + y
    
    # First call - should execute function
    start_time = time.time()
    result1 = expensive_function(5, 3)
    time1 = time.time() - start_time
    print(f"First call result: {result1}, time: {time1:.3f}s")
    
    # Second call - should use cache
    start_time = time.time()
    result2 = expensive_function(5, 3)
    time2 = time.time() - start_time
    print(f"Second call result: {result2}, time: {time2:.3f}s")
    
    print(f"Results match: {result1 == result2}")
    print(f"Second call faster: {time2 < time1}")

def test_user_service_caching():
    """Test user service caching"""
    print("\n=== Testing User Service Caching ===")
    print("Skipping user service tests - requires schema updates")
    # TODO: Implement after schema updates

def test_cache_warming():
    """Test cache warming functionality"""
    print("\n=== Testing Cache Warming ===")
    print("Skipping cache warming tests - requires schema updates")
    # TODO: Implement after schema updates

def main():
    """Run all cache tests"""
    print("Starting Cache Tests...")
    
    # Test basic operations
    if not test_basic_cache_operations():
        print("Basic cache operations failed. Exiting.")
        return
    
    # Test decorator
    test_cached_decorator()
    
    # Test user service caching
    test_user_service_caching()
    
    # Test cache warming
    test_cache_warming()
    
    print("\n=== Cache Tests Completed ===")

if __name__ == "__main__":
    main()