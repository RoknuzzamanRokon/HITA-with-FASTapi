#!/usr/bin/env python3
"""
End-to-End Integration Test Runner

This script runs comprehensive end-to-end integration tests for the user management system.
It tests complete workflows, frontend-backend integration, and system resilience.

Requirements covered: 8.5, 10.1, 10.2
"""

import os
import sys
import subprocess
import time
import json
from datetime import datetime
from pathlib import Path

# Add the backend directory to the Python path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))


def run_command(command, description="", timeout=300):
    """Run a command and return the result"""
    print(f"\n{'='*60}")
    print(f"Running: {description or command}")
    print(f"{'='*60}")
    
    start_time = time.time()
    
    try:
        result = subprocess.run(
            command,
            shell=True,
            capture_output=True,
            text=True,
            timeout=timeout
        )
        
        execution_time = time.time() - start_time
        
        print(f"Exit code: {result.returncode}")
        print(f"Execution time: {execution_time:.2f} seconds")
        
        if result.stdout:
            print(f"\nSTDOUT:\n{result.stdout}")
        
        if result.stderr:
            print(f"\nSTDERR:\n{result.stderr}")
        
        return {
            "command": command,
            "description": description,
            "exit_code": result.returncode,
            "stdout": result.stdout,
            "stderr": result.stderr,
            "execution_time": execution_time,
            "success": result.returncode == 0
        }
    
    except subprocess.TimeoutExpired:
        print(f"Command timed out after {timeout} seconds")
        return {
            "command": command,
            "description": description,
            "exit_code": -1,
            "error": "Timeout",
            "execution_time": timeout,
            "success": False
        }
    
    except Exception as e:
        print(f"Error running command: {e}")
        return {
            "command": command,
            "description": description,
            "exit_code": -1,
            "error": str(e),
            "execution_time": time.time() - start_time,
            "success": False
        }


def check_dependencies():
    """Check if required dependencies are available"""
    print("Checking dependencies...")
    
    dependencies = [
        ("python", "python --version"),
        ("pytest", "python -m pytest --version"),
        ("fastapi", "python -c \"import fastapi; print(f'FastAPI {fastapi.__version__}')\""),
        ("sqlalchemy", "python -c \"import sqlalchemy; print(f'SQLAlchemy {sqlalchemy.__version__}')\""),
    ]
    
    missing_deps = []
    
    for dep_name, check_command in dependencies:
        result = run_command(check_command, f"Checking {dep_name}")
        if not result["success"]:
            missing_deps.append(dep_name)
    
    if missing_deps:
        print(f"\n❌ Missing dependencies: {', '.join(missing_deps)}")
        print("Please install missing dependencies before running tests.")
        return False
    
    print("\n✅ All dependencies are available")
    return True


def setup_test_environment():
    """Setup the test environment"""
    print("\nSetting up test environment...")
    
    # Create test directories if they don't exist
    test_dirs = [
        "tests",
        "test_reports",
        "test_logs"
    ]
    
    for test_dir in test_dirs:
        Path(test_dir).mkdir(exist_ok=True)
    
    # Set environment variables for testing
    os.environ["TESTING"] = "true"
    os.environ["DATABASE_URL"] = "sqlite:///test_integration.db"
    
    print("✅ Test environment setup complete")


def run_integration_test_suite():
    """Run the complete integration test suite"""
    print("\n" + "="*80)
    print("RUNNING END-TO-END INTEGRATION TEST SUITE")
    print("="*80)
    
    test_results = []
    
    # Test configurations
    test_configs = [
        {
            "name": "End-to-End Integration Tests",
            "command": "python -m pytest tests/test_end_to_end_integration.py -v -s --tb=short",
            "timeout": 600,  # 10 minutes
            "critical": True
        },
        {
            "name": "Frontend-Backend Integration Tests",
            "command": "python -m pytest tests/test_frontend_integration.py -v -s --tb=short",
            "timeout": 300,  # 5 minutes
            "critical": True
        },
        {
            "name": "Integration Test Fixtures Validation",
            "command": "python -c 'from tests.test_integration_fixtures import IntegrationTestHelper; print(\"Integration fixtures loaded successfully\")'",
            "timeout": 30,
            "critical": False
        }
    ]
    
    # Run each test configuration
    for config in test_configs:
        print(f"\n{'='*60}")
        print(f"Running: {config['name']}")
        print(f"{'='*60}")
        
        result = run_command(
            config["command"],
            config["name"],
            config["timeout"]
        )
        
        result["test_name"] = config["name"]
        result["critical"] = config["critical"]
        test_results.append(result)
        
        # If critical test fails, we might want to continue but note it
        if config["critical"] and not result["success"]:
            print(f"⚠️  Critical test failed: {config['name']}")
        elif result["success"]:
            print(f"✅ Test passed: {config['name']}")
        else:
            print(f"❌ Test failed: {config['name']}")
    
    return test_results


def run_performance_integration_tests():
    """Run performance-related integration tests"""
    print("\n" + "="*80)
    print("RUNNING PERFORMANCE INTEGRATION TESTS")
    print("="*80)
    
    performance_tests = [
        {
            "name": "Performance Integration Tests",
            "command": "python -m pytest tests/test_performance_integration.py -v -s --tb=short",
            "timeout": 900,  # 15 minutes
        }
    ]
    
    performance_results = []
    
    for test in performance_tests:
        result = run_command(
            test["command"],
            test["name"],
            test["timeout"]
        )
        
        result["test_name"] = test["name"]
        performance_results.append(result)
    
    return performance_results


def generate_test_report(test_results, performance_results=None):
    """Generate a comprehensive test report"""
    print("\n" + "="*80)
    print("GENERATING TEST REPORT")
    print("="*80)
    
    report_data = {
        "test_run_info": {
            "timestamp": datetime.now().isoformat(),
            "total_tests": len(test_results),
            "environment": "integration_testing"
        },
        "test_results": test_results,
        "performance_results": performance_results or [],
        "summary": {}
    }
    
    # Calculate summary statistics
    successful_tests = [r for r in test_results if r["success"]]
    failed_tests = [r for r in test_results if not r["success"]]
    critical_failures = [r for r in failed_tests if r.get("critical", False)]
    
    total_execution_time = sum(r["execution_time"] for r in test_results)
    
    report_data["summary"] = {
        "total_tests": len(test_results),
        "successful_tests": len(successful_tests),
        "failed_tests": len(failed_tests),
        "critical_failures": len(critical_failures),
        "success_rate": len(successful_tests) / len(test_results) if test_results else 0,
        "total_execution_time": total_execution_time,
        "overall_status": "PASS" if len(critical_failures) == 0 else "FAIL"
    }
    
    # Save JSON report
    report_file = f"test_reports/integration_test_report_{int(time.time())}.json"
    with open(report_file, 'w') as f:
        json.dump(report_data, f, indent=2)
    
    # Print summary
    print(f"\nTEST SUMMARY:")
    print(f"{'='*40}")
    print(f"Total Tests: {report_data['summary']['total_tests']}")
    print(f"Successful: {report_data['summary']['successful_tests']}")
    print(f"Failed: {report_data['summary']['failed_tests']}")
    print(f"Critical Failures: {report_data['summary']['critical_failures']}")
    print(f"Success Rate: {report_data['summary']['success_rate']:.1%}")
    print(f"Total Time: {report_data['summary']['total_execution_time']:.2f} seconds")
    print(f"Overall Status: {report_data['summary']['overall_status']}")
    
    if failed_tests:
        print(f"\nFAILED TESTS:")
        for test in failed_tests:
            print(f"  ❌ {test.get('test_name', test['command'])}")
            if test.get('error'):
                print(f"     Error: {test['error']}")
    
    if successful_tests:
        print(f"\nSUCCESSFUL TESTS:")
        for test in successful_tests:
            print(f"  ✅ {test.get('test_name', test['command'])}")
    
    print(f"\nDetailed report saved to: {report_file}")
    
    return report_data


def cleanup_test_environment():
    """Clean up test environment"""
    print("\nCleaning up test environment...")
    
    # Remove test database files
    test_db_files = [
        "test_integration.db",
        "test.db",
        "hita_test.db"
    ]
    
    for db_file in test_db_files:
        if os.path.exists(db_file):
            try:
                os.remove(db_file)
                print(f"  Removed: {db_file}")
            except Exception as e:
                print(f"  Warning: Could not remove {db_file}: {e}")
    
    # Clean up test cache directories
    cache_dirs = [
        "__pycache__",
        "tests/__pycache__",
        ".pytest_cache"
    ]
    
    for cache_dir in cache_dirs:
        if os.path.exists(cache_dir):
            try:
                import shutil
                shutil.rmtree(cache_dir)
                print(f"  Removed cache: {cache_dir}")
            except Exception as e:
                print(f"  Warning: Could not remove {cache_dir}: {e}")
    
    print("✅ Cleanup complete")


def main():
    """Main test runner function"""
    print("="*80)
    print("END-TO-END INTEGRATION TEST RUNNER")
    print("User Management System - Backend")
    print("="*80)
    
    start_time = time.time()
    
    try:
        # Step 1: Check dependencies
        if not check_dependencies():
            return 1
        
        # Step 2: Setup test environment
        setup_test_environment()
        
        # Step 3: Run integration tests
        test_results = run_integration_test_suite()
        
        # Step 4: Run performance tests (optional)
        performance_results = []
        try:
            performance_results = run_performance_integration_tests()
        except Exception as e:
            print(f"⚠️  Performance tests skipped due to error: {e}")
        
        # Step 5: Generate report
        report_data = generate_test_report(test_results, performance_results)
        
        # Step 6: Cleanup
        cleanup_test_environment()
        
        # Determine exit code
        total_time = time.time() - start_time
        print(f"\n{'='*80}")
        print(f"INTEGRATION TEST RUN COMPLETE")
        print(f"Total execution time: {total_time:.2f} seconds")
        print(f"Overall status: {report_data['summary']['overall_status']}")
        print(f"{'='*80}")
        
        # Return appropriate exit code
        if report_data['summary']['critical_failures'] > 0:
            print("❌ Integration tests failed with critical failures")
            return 1
        elif report_data['summary']['failed_tests'] > 0:
            print("⚠️  Integration tests completed with some failures")
            return 2
        else:
            print("✅ All integration tests passed successfully")
            return 0
    
    except KeyboardInterrupt:
        print("\n\n⚠️  Test run interrupted by user")
        cleanup_test_environment()
        return 130
    
    except Exception as e:
        print(f"\n\n❌ Test run failed with error: {e}")
        cleanup_test_environment()
        return 1


if __name__ == "__main__":
    exit_code = main()
    sys.exit(exit_code)