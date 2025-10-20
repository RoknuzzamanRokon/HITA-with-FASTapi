#!/usr/bin/env python3
"""
Simple script to run API documentation tests

This script provides an easy way to run comprehensive API documentation tests
and validate that the OpenAPI documentation is accurate and complete.
"""

import sys
import json
from datetime import datetime
from test_api_documentation import run_documentation_tests


def main():
    """Main function to run documentation tests"""
    print("🚀 API Documentation Test Runner")
    print("=" * 50)
    
    # Default values
    base_url = "http://localhost:8000"
    admin_email = None
    admin_password = None
    
    # Parse command line arguments
    if len(sys.argv) > 1:
        base_url = sys.argv[1]
    if len(sys.argv) > 2:
        admin_email = sys.argv[2]
    if len(sys.argv) > 3:
        admin_password = sys.argv[3]
    
    print(f"Testing API at: {base_url}")
    if admin_email:
        print(f"Using authentication: {admin_email}")
    else:
        print("Running without authentication (limited tests)")
    
    print("\nStarting documentation tests...")
    
    try:
        # Run the tests
        results = run_documentation_tests(
            base_url=base_url,
            admin_email=admin_email,
            admin_password=admin_password
        )
        
        # Generate output filename
        timestamp = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
        output_file = f"documentation_test_results_{timestamp}.json"
        
        # Save results
        with open(output_file, 'w') as f:
            json.dump(results, f, indent=2)
        
        print(f"\n📄 Detailed results saved to: {output_file}")
        
        # Exit with appropriate code
        success_rate = results.get("summary", {}).get("success_rate", 0)
        if success_rate >= 80:
            print("\n✅ Documentation tests completed successfully!")
            sys.exit(0)
        else:
            print(f"\n⚠️  Documentation tests completed with issues (success rate: {success_rate}%)")
            sys.exit(1)
            
    except Exception as e:
        print(f"\n❌ Error running documentation tests: {str(e)}")
        sys.exit(1)


if __name__ == "__main__":
    if len(sys.argv) == 1 or sys.argv[1] in ["-h", "--help"]:
        print("Usage: python run_doc_tests.py [base_url] [admin_email] [admin_password]")
        print("\nExamples:")
        print("  python run_doc_tests.py")
        print("  python run_doc_tests.py http://localhost:8000")
        print("  python run_doc_tests.py http://localhost:8000 admin@example.com password123")
        print("\nThis script will:")
        print("  - Test OpenAPI schema structure")
        print("  - Validate endpoint documentation completeness")
        print("  - Check response schema definitions")
        print("  - Test example accuracy")
        print("  - Validate health check documentation")
        print("  - Check error response documentation")
        sys.exit(0)
    
    main()