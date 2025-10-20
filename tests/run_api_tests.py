#!/usr/bin/env python3
"""
Comprehensive API Testing Script for User Management System

This script provides automated testing capabilities for the user management API,
including health checks, endpoint validation, performance testing, and integration tests.

Usage:
    python run_api_tests.py --help
    python run_api_tests.py --health-check
    python run_api_tests.py --integration-tests --admin-email admin@example.com --admin-password password123
    python run_api_tests.py --performance-test --endpoint /v1.0/user/check/all
    python run_api_tests.py --full-suite --admin-email admin@example.com --admin-password password123
"""

import argparse
import sys
import json
import time
from datetime import datetime
from typing import Dict, Any, List
import requests
from testing_utilities import APITestClient, create_user_management_test_suite, run_integration_tests


def run_health_checks(base_url: str) -> Dict[str, Any]:
    """
    Run comprehensive health checks on the API.
    
    Args:
        base_url: Base URL of the API server
        
    Returns:
        Dict[str, Any]: Health check results
    """
    print("🏥 Running Health Checks")
    print("=" * 40)
    
    health_endpoints = [
        "/v1.0/health/",
        "/v1.0/health/detailed",
        "/v1.0/health/database",
        "/v1.0/health/cache",
        "/v1.0/health/status",
        "/v1.0/health/readiness",
        "/v1.0/health/liveness"
    ]
    
    results = {}
    
    for endpoint in health_endpoints:
        print(f"Testing {endpoint}...")
        try:
            start_time = time.time()
            response = requests.get(f"{base_url}{endpoint}", timeout=10)
            response_time = (time.time() - start_time) * 1000
            
            status = "✅ PASS" if response.status_code == 200 else "❌ FAIL"
            print(f"  {status} ({response.status_code}) - {response_time:.2f}ms")
            
            try:
                response_data = response.json()
            except json.JSONDecodeError:
                response_data = {"raw_response": response.text}
            
            results[endpoint] = {
                "status_code": response.status_code,
                "response_time_ms": response_time,
                "success": response.status_code == 200,
                "data": response_data
            }
            
        except requests.exceptions.RequestException as e:
            print(f"  ❌ ERROR - {str(e)}")
            results[endpoint] = {
                "status_code": 0,
                "response_time_ms": 0,
                "success": False,
                "error": str(e)
            }
    
    # Summary
    successful = sum(1 for r in results.values() if r["success"])
    total = len(results)
    
    print(f"\n📊 Health Check Summary: {successful}/{total} endpoints healthy")
    
    return {
        "timestamp": datetime.utcnow().isoformat(),
        "summary": {
            "total_endpoints": total,
            "healthy_endpoints": successful,
            "unhealthy_endpoints": total - successful,
            "success_rate": (successful / total * 100) if total > 0 else 0
        },
        "results": results
    }


def run_performance_test(base_url: str, endpoint: str, method: str = "GET",
                        concurrent_requests: int = 10, total_requests: int = 100,
                        admin_email: str = None, admin_password: str = None) -> Dict[str, Any]:
    """
    Run performance tests on a specific endpoint.
    
    Args:
        base_url: Base URL of the API server
        endpoint: Endpoint to test
        method: HTTP method
        concurrent_requests: Number of concurrent requests
        total_requests: Total number of requests
        admin_email: Admin email for authentication
        admin_password: Admin password for authentication
        
    Returns:
        Dict[str, Any]: Performance test results
    """
    print(f"🚀 Running Performance Test")
    print(f"Endpoint: {method} {endpoint}")
    print(f"Requests: {total_requests} ({concurrent_requests} concurrent)")
    print("=" * 50)
    
    client = APITestClient(base_url)
    
    # Authenticate if credentials provided
    if admin_email and admin_password:
        if not client.authenticate(admin_email, admin_password):
            print("❌ Authentication failed - cannot run performance test")
            return {"error": "Authentication failed"}
    
    # Run performance test
    results = client.performance_test(
        endpoint=endpoint,
        method=method,
        concurrent_requests=concurrent_requests,
        total_requests=total_requests
    )
    
    # Print results
    print(f"✅ Performance Test Complete")
    print(f"Total Requests: {results['total_requests']}")
    print(f"Successful: {results['successful_requests']}")
    print(f"Failed: {results['failed_requests']}")
    print(f"Success Rate: {results['success_rate']:.2f}%")
    print(f"Total Time: {results['total_time_seconds']}s")
    print(f"Requests/Second: {results['requests_per_second']:.2f}")
    print(f"Average Response Time: {results['response_times']['avg_ms']:.2f}ms")
    print(f"95th Percentile: {results['response_times']['p95_ms']:.2f}ms")
    print(f"99th Percentile: {results['response_times']['p99_ms']:.2f}ms")
    
    return results


def run_endpoint_validation(base_url: str, admin_email: str = None, admin_password: str = None) -> Dict[str, Any]:
    """
    Run endpoint validation tests to ensure all endpoints are working correctly.
    
    Args:
        base_url: Base URL of the API server
        admin_email: Admin email for authentication
        admin_password: Admin password for authentication
        
    Returns:
        Dict[str, Any]: Validation test results
    """
    print("🔍 Running Endpoint Validation")
    print("=" * 40)
    
    client = APITestClient(base_url)
    
    # Authenticate if credentials provided
    authenticated = False
    if admin_email and admin_password:
        authenticated = client.authenticate(admin_email, admin_password)
        if authenticated:
            print("✅ Authentication successful")
        else:
            print("❌ Authentication failed - running limited tests")
    
    # Define validation tests
    validation_tests = [
        {
            "name": "Health Check",
            "endpoint": "/v1.0/health/",
            "method": "GET",
            "requires_auth": False,
            "expected_fields": ["status", "service"]
        },
        {
            "name": "Detailed Health Check",
            "endpoint": "/v1.0/health/detailed",
            "method": "GET",
            "requires_auth": False,
            "expected_fields": ["status", "checks"]
        },
        {
            "name": "Current User Info",
            "endpoint": "/v1.0/user/me",
            "method": "GET",
            "requires_auth": True,
            "expected_fields": ["id", "username", "email"]
        },
        {
            "name": "User List",
            "endpoint": "/v1.0/user/check/all",
            "method": "GET",
            "requires_auth": True,
            "expected_fields": ["total_super_user", "total_admin_users", "total_general_users"]
        },
        {
            "name": "Point Details",
            "endpoint": "/v1.0/user/points/check/me",
            "method": "GET",
            "requires_auth": True,
            "expected_fields": ["total_points", "current_points"]
        }
    ]
    
    results = []
    
    for test in validation_tests:
        if test["requires_auth"] and not authenticated:
            print(f"⏭️  Skipping {test['name']} (requires authentication)")
            continue
        
        print(f"Testing {test['name']}...")
        
        try:
            start_time = time.time()
            
            if test["method"] == "GET":
                response = client.session.get(f"{base_url}{test['endpoint']}")
            else:
                response = client.session.request(test["method"], f"{base_url}{test['endpoint']}")
            
            response_time = (time.time() - start_time) * 1000
            
            try:
                response_data = response.json()
            except json.JSONDecodeError:
                response_data = {}
            
            # Check expected fields
            missing_fields = []
            for field in test.get("expected_fields", []):
                if field not in response_data:
                    missing_fields.append(field)
            
            success = response.status_code == 200 and not missing_fields
            status = "✅ PASS" if success else "❌ FAIL"
            
            print(f"  {status} ({response.status_code}) - {response_time:.2f}ms")
            
            if missing_fields:
                print(f"    Missing fields: {', '.join(missing_fields)}")
            
            results.append({
                "test_name": test["name"],
                "endpoint": test["endpoint"],
                "method": test["method"],
                "status_code": response.status_code,
                "response_time_ms": response_time,
                "success": success,
                "missing_fields": missing_fields,
                "requires_auth": test["requires_auth"]
            })
            
        except Exception as e:
            print(f"  ❌ ERROR - {str(e)}")
            results.append({
                "test_name": test["name"],
                "endpoint": test["endpoint"],
                "method": test["method"],
                "status_code": 0,
                "response_time_ms": 0,
                "success": False,
                "error": str(e),
                "requires_auth": test["requires_auth"]
            })
    
    # Summary
    successful = sum(1 for r in results if r["success"])
    total = len(results)
    
    print(f"\n📊 Validation Summary: {successful}/{total} tests passed")
    
    return {
        "timestamp": datetime.utcnow().isoformat(),
        "summary": {
            "total_tests": total,
            "passed_tests": successful,
            "failed_tests": total - successful,
            "success_rate": (successful / total * 100) if total > 0 else 0
        },
        "results": results
    }


def run_full_test_suite(base_url: str, admin_email: str = None, admin_password: str = None) -> Dict[str, Any]:
    """
    Run the complete test suite including all test types.
    
    Args:
        base_url: Base URL of the API server
        admin_email: Admin email for authentication
        admin_password: Admin password for authentication
        
    Returns:
        Dict[str, Any]: Complete test suite results
    """
    print("🎯 Running Full Test Suite")
    print("=" * 50)
    
    suite_results = {
        "timestamp": datetime.utcnow().isoformat(),
        "base_url": base_url,
        "authenticated": bool(admin_email and admin_password)
    }
    
    # 1. Health Checks
    print("\n1️⃣  Health Checks")
    suite_results["health_checks"] = run_health_checks(base_url)
    
    # 2. Endpoint Validation
    print("\n2️⃣  Endpoint Validation")
    suite_results["endpoint_validation"] = run_endpoint_validation(base_url, admin_email, admin_password)
    
    # 3. Integration Tests
    if admin_email and admin_password:
        print("\n3️⃣  Integration Tests")
        suite_results["integration_tests"] = run_integration_tests(base_url, admin_email, admin_password)
        
        # 4. Performance Tests
        print("\n4️⃣  Performance Tests")
        suite_results["performance_tests"] = {
            "health_check": run_performance_test(base_url, "/v1.0/health/", "GET", 5, 50),
            "user_list": run_performance_test(base_url, "/v1.0/user/check/all", "GET", 3, 30, admin_email, admin_password)
        }
    else:
        print("\n⚠️  Skipping Integration and Performance Tests (no authentication)")
    
    # Overall Summary
    print("\n" + "=" * 50)
    print("📊 FULL TEST SUITE SUMMARY")
    print("=" * 50)
    
    health_success = suite_results["health_checks"]["summary"]["success_rate"]
    validation_success = suite_results["endpoint_validation"]["summary"]["success_rate"]
    
    print(f"Health Checks: {health_success:.1f}% success rate")
    print(f"Endpoint Validation: {validation_success:.1f}% success rate")
    
    if "integration_tests" in suite_results:
        integration_success = suite_results["integration_tests"]["summary"]["success_rate"]
        print(f"Integration Tests: {integration_success:.1f}% success rate")
    
    overall_health = "✅ HEALTHY" if health_success >= 90 and validation_success >= 90 else "⚠️  ISSUES DETECTED"
    print(f"\nOverall System Health: {overall_health}")
    
    return suite_results


def save_results(results: Dict[str, Any], output_file: str = None):
    """
    Save test results to a JSON file.
    
    Args:
        results: Test results to save
        output_file: Output file path (auto-generated if not provided)
    """
    if not output_file:
        timestamp = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
        output_file = f"api_test_results_{timestamp}.json"
    
    with open(output_file, 'w') as f:
        json.dump(results, f, indent=2)
    
    print(f"📄 Results saved to: {output_file}")


def main():
    """Main function to handle command line arguments and run tests"""
    parser = argparse.ArgumentParser(
        description="Comprehensive API Testing for User Management System",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python run_api_tests.py --health-check
  python run_api_tests.py --integration-tests --admin-email admin@example.com --admin-password password123
  python run_api_tests.py --performance-test --endpoint /v1.0/user/check/all --requests 100
  python run_api_tests.py --full-suite --admin-email admin@example.com --admin-password password123
        """
    )
    
    parser.add_argument("--base-url", default="http://localhost:8000", 
                       help="Base URL of the API server (default: http://localhost:8000)")
    parser.add_argument("--admin-email", help="Admin email for authentication")
    parser.add_argument("--admin-password", help="Admin password for authentication")
    parser.add_argument("--output-file", help="Output file for test results")
    
    # Test type options
    parser.add_argument("--health-check", action="store_true", 
                       help="Run health check tests")
    parser.add_argument("--endpoint-validation", action="store_true",
                       help="Run endpoint validation tests")
    parser.add_argument("--integration-tests", action="store_true",
                       help="Run integration tests (requires authentication)")
    parser.add_argument("--performance-test", action="store_true",
                       help="Run performance tests")
    parser.add_argument("--full-suite", action="store_true",
                       help="Run complete test suite")
    
    # Performance test options
    parser.add_argument("--endpoint", default="/v1.0/health/",
                       help="Endpoint for performance testing")
    parser.add_argument("--method", default="GET",
                       help="HTTP method for performance testing")
    parser.add_argument("--requests", type=int, default=100,
                       help="Total requests for performance testing")
    parser.add_argument("--concurrent", type=int, default=10,
                       help="Concurrent requests for performance testing")
    
    args = parser.parse_args()
    
    # Validate arguments
    if not any([args.health_check, args.endpoint_validation, args.integration_tests, 
               args.performance_test, args.full_suite]):
        parser.print_help()
        sys.exit(1)
    
    if (args.integration_tests or args.full_suite) and not (args.admin_email and args.admin_password):
        print("❌ Integration tests require --admin-email and --admin-password")
        sys.exit(1)
    
    # Run selected tests
    results = None
    
    if args.health_check:
        results = run_health_checks(args.base_url)
    
    elif args.endpoint_validation:
        results = run_endpoint_validation(args.base_url, args.admin_email, args.admin_password)
    
    elif args.integration_tests:
        results = run_integration_tests(args.base_url, args.admin_email, args.admin_password)
    
    elif args.performance_test:
        results = run_performance_test(
            args.base_url, args.endpoint, args.method,
            args.concurrent, args.requests,
            args.admin_email, args.admin_password
        )
    
    elif args.full_suite:
        results = run_full_test_suite(args.base_url, args.admin_email, args.admin_password)
    
    # Save results if requested
    if results and args.output_file:
        save_results(results, args.output_file)
    elif results:
        # Auto-save for full suite
        if args.full_suite:
            save_results(results)


if __name__ == "__main__":
    main()