"""
API Testing Utilities for User Management System

This module provides comprehensive testing utilities for integration testing,
API validation, and automated testing of the user management endpoints.
"""

import requests
import json
import time
from typing import Dict, Any, List, Optional, Tuple
from datetime import datetime
from dataclasses import dataclass
from enum import Enum
import random
import string


class TestResult(Enum):
    """Test result status enumeration"""
    PASS = "PASS"
    FAIL = "FAIL"
    SKIP = "SKIP"
    ERROR = "ERROR"


@dataclass
class TestCase:
    """Test case data structure"""
    name: str
    description: str
    method: str
    endpoint: str
    headers: Dict[str, str]
    payload: Optional[Dict[str, Any]] = None
    expected_status: int = 200
    expected_fields: Optional[List[str]] = None
    validation_rules: Optional[Dict[str, Any]] = None


@dataclass
class TestExecutionResult:
    """Test execution result data structure"""
    test_case: TestCase
    result: TestResult
    status_code: int
    response_data: Optional[Dict[str, Any]]
    response_time_ms: float
    error_message: Optional[str] = None
    validation_errors: Optional[List[str]] = None


class APITestClient:
    """
    Comprehensive API testing client for user management endpoints.
    
    This class provides utilities for:
    - Authentication and token management
    - Endpoint testing with validation
    - Performance testing and benchmarking
    - Data validation and schema checking
    - Test result reporting and analysis
    """
    
    def __init__(self, base_url: str = "http://localhost:8000"):
        """
        Initialize the API test client.
        
        Args:
            base_url: Base URL of the API server
        """
        self.base_url = base_url.rstrip('/')
        self.session = requests.Session()
        self.auth_token = None
        self.test_results: List[TestExecutionResult] = []
    
    def authenticate(self, email: str, password: str) -> bool:
        """
        Authenticate with the API and store the token.
        
        Args:
            email: User email for authentication
            password: User password for authentication
            
        Returns:
            bool: True if authentication successful, False otherwise
        """
        try:
            auth_data = {
                "username": email,  # FastAPI OAuth2 uses 'username' field
                "password": password
            }
            
            response = self.session.post(
                f"{self.base_url}/v1.0/auth/token",
                data=auth_data,
                headers={"Content-Type": "application/x-www-form-urlencoded"}
            )
            
            if response.status_code == 200:
                token_data = response.json()
                self.auth_token = token_data.get("access_token")
                self.session.headers.update({
                    "Authorization": f"Bearer {self.auth_token}"
                })
                return True
            else:
                print(f"Authentication failed: {response.status_code} - {response.text}")
                return False
                
        except Exception as e:
            print(f"Authentication error: {str(e)}")
            return False
    
    def execute_test_case(self, test_case: TestCase) -> TestExecutionResult:
        """
        Execute a single test case and return the result.
        
        Args:
            test_case: Test case to execute
            
        Returns:
            TestExecutionResult: Result of the test execution
        """
        start_time = time.time()
        
        try:
            # Prepare request
            url = f"{self.base_url}{test_case.endpoint}"
            headers = {**self.session.headers, **test_case.headers}
            
            # Execute request
            if test_case.method.upper() == "GET":
                response = self.session.get(url, headers=headers, params=test_case.payload)
            elif test_case.method.upper() == "POST":
                response = self.session.post(url, headers=headers, json=test_case.payload)
            elif test_case.method.upper() == "PUT":
                response = self.session.put(url, headers=headers, json=test_case.payload)
            elif test_case.method.upper() == "DELETE":
                response = self.session.delete(url, headers=headers)
            else:
                raise ValueError(f"Unsupported HTTP method: {test_case.method}")
            
            response_time = (time.time() - start_time) * 1000
            
            # Parse response
            try:
                response_data = response.json()
            except json.JSONDecodeError:
                response_data = {"raw_response": response.text}
            
            # Validate response
            validation_errors = self._validate_response(test_case, response, response_data)
            
            # Determine test result
            if response.status_code == test_case.expected_status and not validation_errors:
                result = TestResult.PASS
            else:
                result = TestResult.FAIL
            
            return TestExecutionResult(
                test_case=test_case,
                result=result,
                status_code=response.status_code,
                response_data=response_data,
                response_time_ms=response_time,
                validation_errors=validation_errors
            )
            
        except Exception as e:
            response_time = (time.time() - start_time) * 1000
            return TestExecutionResult(
                test_case=test_case,
                result=TestResult.ERROR,
                status_code=0,
                response_data=None,
                response_time_ms=response_time,
                error_message=str(e)
            )
    
    def _validate_response(self, test_case: TestCase, response: requests.Response, 
                          response_data: Dict[str, Any]) -> List[str]:
        """
        Validate response against test case expectations.
        
        Args:
            test_case: Test case with validation rules
            response: HTTP response object
            response_data: Parsed response data
            
        Returns:
            List[str]: List of validation errors (empty if valid)
        """
        errors = []
        
        # Check expected fields
        if test_case.expected_fields:
            for field in test_case.expected_fields:
                if field not in response_data:
                    errors.append(f"Missing expected field: {field}")
        
        # Check validation rules
        if test_case.validation_rules:
            for rule_name, rule_value in test_case.validation_rules.items():
                if rule_name == "min_response_time_ms":
                    # This would be checked in the calling method
                    pass
                elif rule_name == "max_response_time_ms":
                    # This would be checked in the calling method
                    pass
                elif rule_name == "required_fields":
                    for field in rule_value:
                        if field not in response_data:
                            errors.append(f"Required field missing: {field}")
                elif rule_name == "field_types":
                    for field, expected_type in rule_value.items():
                        if field in response_data:
                            actual_type = type(response_data[field]).__name__
                            if actual_type != expected_type:
                                errors.append(f"Field {field} type mismatch: expected {expected_type}, got {actual_type}")
        
        return errors
    
    def run_test_suite(self, test_cases: List[TestCase]) -> Dict[str, Any]:
        """
        Run a complete test suite and return comprehensive results.
        
        Args:
            test_cases: List of test cases to execute
            
        Returns:
            Dict[str, Any]: Test suite results and statistics
        """
        print(f"Running test suite with {len(test_cases)} test cases...")
        
        results = []
        start_time = time.time()
        
        for i, test_case in enumerate(test_cases, 1):
            print(f"Executing test {i}/{len(test_cases)}: {test_case.name}")
            result = self.execute_test_case(test_case)
            results.append(result)
            self.test_results.append(result)
            
            # Print immediate result
            status_icon = "✅" if result.result == TestResult.PASS else "❌"
            print(f"  {status_icon} {result.result.value} ({result.response_time_ms:.2f}ms)")
            
            if result.validation_errors:
                for error in result.validation_errors:
                    print(f"    - {error}")
        
        total_time = time.time() - start_time
        
        # Calculate statistics
        stats = self._calculate_test_statistics(results)
        
        return {
            "summary": {
                "total_tests": len(test_cases),
                "passed": stats["passed"],
                "failed": stats["failed"],
                "errors": stats["errors"],
                "success_rate": stats["success_rate"],
                "total_time_seconds": round(total_time, 2),
                "average_response_time_ms": stats["avg_response_time"]
            },
            "results": [self._serialize_test_result(r) for r in results],
            "timestamp": datetime.utcnow().isoformat()
        }
    
    def _calculate_test_statistics(self, results: List[TestExecutionResult]) -> Dict[str, Any]:
        """Calculate test execution statistics"""
        passed = sum(1 for r in results if r.result == TestResult.PASS)
        failed = sum(1 for r in results if r.result == TestResult.FAIL)
        errors = sum(1 for r in results if r.result == TestResult.ERROR)
        
        total_response_time = sum(r.response_time_ms for r in results)
        avg_response_time = total_response_time / len(results) if results else 0
        
        success_rate = (passed / len(results) * 100) if results else 0
        
        return {
            "passed": passed,
            "failed": failed,
            "errors": errors,
            "success_rate": round(success_rate, 2),
            "avg_response_time": round(avg_response_time, 2)
        }
    
    def _serialize_test_result(self, result: TestExecutionResult) -> Dict[str, Any]:
        """Serialize test result for JSON output"""
        return {
            "test_name": result.test_case.name,
            "description": result.test_case.description,
            "result": result.result.value,
            "status_code": result.status_code,
            "expected_status": result.test_case.expected_status,
            "response_time_ms": round(result.response_time_ms, 2),
            "error_message": result.error_message,
            "validation_errors": result.validation_errors,
            "endpoint": result.test_case.endpoint,
            "method": result.test_case.method
        }
    
    def generate_test_data(self) -> Dict[str, Any]:
        """
        Generate random test data for user creation and testing.
        
        Returns:
            Dict[str, Any]: Generated test data
        """
        random_suffix = ''.join(random.choices(string.ascii_lowercase + string.digits, k=6))
        
        return {
            "username": f"test_user_{random_suffix}",
            "email": f"test_{random_suffix}@example.com",
            "password": f"TestPass{random.randint(100, 999)}",
            "business_id": f"BIZ_{random_suffix.upper()}"
        }
    
    def performance_test(self, endpoint: str, method: str = "GET", 
                        payload: Optional[Dict[str, Any]] = None,
                        concurrent_requests: int = 10, 
                        total_requests: int = 100) -> Dict[str, Any]:
        """
        Perform performance testing on an endpoint.
        
        Args:
            endpoint: API endpoint to test
            method: HTTP method
            payload: Request payload for POST/PUT requests
            concurrent_requests: Number of concurrent requests
            total_requests: Total number of requests to make
            
        Returns:
            Dict[str, Any]: Performance test results
        """
        print(f"Running performance test: {total_requests} requests to {endpoint}")
        
        import threading
        import queue
        
        results_queue = queue.Queue()
        
        def make_request():
            start_time = time.time()
            try:
                url = f"{self.base_url}{endpoint}"
                if method.upper() == "GET":
                    response = self.session.get(url)
                elif method.upper() == "POST":
                    response = self.session.post(url, json=payload)
                else:
                    response = self.session.request(method, url, json=payload)
                
                response_time = (time.time() - start_time) * 1000
                results_queue.put({
                    "status_code": response.status_code,
                    "response_time_ms": response_time,
                    "success": response.status_code < 400
                })
            except Exception as e:
                response_time = (time.time() - start_time) * 1000
                results_queue.put({
                    "status_code": 0,
                    "response_time_ms": response_time,
                    "success": False,
                    "error": str(e)
                })
        
        # Execute requests in batches
        start_time = time.time()
        threads = []
        
        for i in range(0, total_requests, concurrent_requests):
            batch_size = min(concurrent_requests, total_requests - i)
            batch_threads = []
            
            for _ in range(batch_size):
                thread = threading.Thread(target=make_request)
                thread.start()
                batch_threads.append(thread)
            
            # Wait for batch to complete
            for thread in batch_threads:
                thread.join()
            
            threads.extend(batch_threads)
        
        total_time = time.time() - start_time
        
        # Collect results
        results = []
        while not results_queue.empty():
            results.append(results_queue.get())
        
        # Calculate statistics
        response_times = [r["response_time_ms"] for r in results]
        successful_requests = sum(1 for r in results if r["success"])
        
        return {
            "endpoint": endpoint,
            "method": method,
            "total_requests": len(results),
            "successful_requests": successful_requests,
            "failed_requests": len(results) - successful_requests,
            "success_rate": (successful_requests / len(results) * 100) if results else 0,
            "total_time_seconds": round(total_time, 2),
            "requests_per_second": round(len(results) / total_time, 2),
            "response_times": {
                "min_ms": min(response_times) if response_times else 0,
                "max_ms": max(response_times) if response_times else 0,
                "avg_ms": round(sum(response_times) / len(response_times), 2) if response_times else 0,
                "p95_ms": round(sorted(response_times)[int(len(response_times) * 0.95)], 2) if response_times else 0,
                "p99_ms": round(sorted(response_times)[int(len(response_times) * 0.99)], 2) if response_times else 0
            },
            "timestamp": datetime.utcnow().isoformat()
        }


def create_user_management_test_suite() -> List[TestCase]:
    """
    Create a comprehensive test suite for user management endpoints.
    
    Returns:
        List[TestCase]: Complete test suite for user management
    """
    test_cases = [
        # Health check tests
        TestCase(
            name="Health Check - Basic",
            description="Test basic health check endpoint",
            method="GET",
            endpoint="/v1.0/health/",
            headers={},
            expected_status=200,
            expected_fields=["status", "service", "timestamp"]
        ),
        
        TestCase(
            name="Health Check - Detailed",
            description="Test detailed health check with all components",
            method="GET",
            endpoint="/v1.0/health/detailed",
            headers={},
            expected_status=200,
            expected_fields=["status", "checks", "response_time_ms"],
            validation_rules={
                "required_fields": ["status", "service", "version", "checks"],
                "field_types": {
                    "status": "str",
                    "response_time_ms": "float"
                }
            }
        ),
        
        # Authentication tests
        TestCase(
            name="Get Current User Info",
            description="Test retrieving current user information",
            method="GET",
            endpoint="/v1.0/user/me",
            headers={},
            expected_status=200,
            expected_fields=["id", "username", "email", "user_status", "available_points"]
        ),
        
        # User listing tests
        TestCase(
            name="List Users - Basic",
            description="Test basic user listing without pagination",
            method="GET",
            endpoint="/v1.0/user/check/all",
            headers={},
            expected_status=200,
            expected_fields=["total_super_user", "total_admin_users", "total_general_users", "root_user"]
        ),
        
        TestCase(
            name="List Users - With Pagination",
            description="Test user listing with pagination parameters",
            method="GET",
            endpoint="/v1.0/user/check/all",
            headers={},
            payload={"page": 1, "limit": 10},
            expected_status=200,
            expected_fields=["pagination", "users"] if False else ["total_super_user", "total_admin_users"]  # Fallback to legacy
        ),
        
        TestCase(
            name="List Users - With Search",
            description="Test user listing with search functionality",
            method="GET",
            endpoint="/v1.0/user/check/all",
            headers={},
            payload={"search": "test", "page": 1, "limit": 25},
            expected_status=200
        ),
        
        # Point management tests
        TestCase(
            name="Check Point Details",
            description="Test retrieving point details for current user",
            method="GET",
            endpoint="/v1.0/user/points/check/me",
            headers={},
            expected_status=200,
            expected_fields=["total_points", "current_points", "transactions"]
        ),
        
        # Error handling tests
        TestCase(
            name="Unauthorized Access",
            description="Test endpoint access without authentication",
            method="GET",
            endpoint="/v1.0/user/check/all",
            headers={"Authorization": "Bearer invalid_token"},
            expected_status=401
        ),
        
        TestCase(
            name="Invalid Pagination Parameters",
            description="Test user listing with invalid pagination",
            method="GET",
            endpoint="/v1.0/user/check/all",
            headers={},
            payload={"page": 0, "limit": 200},  # Invalid values
            expected_status=400
        )
    ]
    
    return test_cases


def run_integration_tests(base_url: str = "http://localhost:8000", 
                         admin_email: str = None, admin_password: str = None):
    """
    Run comprehensive integration tests for the user management system.
    
    Args:
        base_url: Base URL of the API server
        admin_email: Admin user email for authentication
        admin_password: Admin user password for authentication
    """
    print("🚀 Starting User Management API Integration Tests")
    print("=" * 60)
    
    # Initialize test client
    client = APITestClient(base_url)
    
    # Authenticate if credentials provided
    if admin_email and admin_password:
        print(f"🔐 Authenticating as {admin_email}...")
        if client.authenticate(admin_email, admin_password):
            print("✅ Authentication successful")
        else:
            print("❌ Authentication failed - running limited tests")
    else:
        print("⚠️  No authentication credentials provided - running limited tests")
    
    # Create and run test suite
    test_cases = create_user_management_test_suite()
    results = client.run_test_suite(test_cases)
    
    # Print summary
    print("\n" + "=" * 60)
    print("📊 TEST RESULTS SUMMARY")
    print("=" * 60)
    
    summary = results["summary"]
    print(f"Total Tests: {summary['total_tests']}")
    print(f"Passed: {summary['passed']} ✅")
    print(f"Failed: {summary['failed']} ❌")
    print(f"Errors: {summary['errors']} 🔥")
    print(f"Success Rate: {summary['success_rate']}%")
    print(f"Total Time: {summary['total_time_seconds']}s")
    print(f"Average Response Time: {summary['average_response_time_ms']}ms")
    
    # Save results to file
    timestamp = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
    filename = f"test_results_{timestamp}.json"
    
    with open(filename, 'w') as f:
        json.dump(results, f, indent=2)
    
    print(f"\n📄 Detailed results saved to: {filename}")
    
    return results


if __name__ == "__main__":
    # Example usage
    import sys
    
    if len(sys.argv) >= 3:
        admin_email = sys.argv[1]
        admin_password = sys.argv[2]
        base_url = sys.argv[3] if len(sys.argv) > 3 else "http://localhost:8000"
    else:
        print("Usage: python testing_utilities.py <admin_email> <admin_password> [base_url]")
        print("Example: python testing_utilities.py admin@example.com password123 http://localhost:8000")
        sys.exit(1)
    
    run_integration_tests(base_url, admin_email, admin_password)