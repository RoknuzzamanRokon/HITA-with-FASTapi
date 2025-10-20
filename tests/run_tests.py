#!/usr/bin/env python3
"""
Test runner script for user management backend tests.

This script runs the unit tests for data models and validation components.
"""

import subprocess
import sys
import os

def run_tests():
    """Run all unit tests for data models and validation."""
    
    # Change to the backend directory
    os.chdir(os.path.dirname(os.path.abspath(__file__)))
    
    print("Running unit tests for data models and validation...")
    print("=" * 60)
    
    # Run the tests using pipenv
    try:
        result = subprocess.run([
            "pipenv", "run", "python", "-m", "pytest", 
            "tests/test_models.py", "tests/test_validation.py", 
            "-v", "--tb=short"
        ], check=True, capture_output=False)
        
        print("\n" + "=" * 60)
        print("✅ All tests completed successfully!")
        return True
        
    except subprocess.CalledProcessError as e:
        print(f"\n❌ Tests failed with exit code: {e.returncode}")
        return False
    except FileNotFoundError:
        print("❌ Error: pipenv not found. Please install pipenv first.")
        return False

if __name__ == "__main__":
    success = run_tests()
    sys.exit(0 if success else 1)