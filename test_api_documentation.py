"""
Comprehensive API Documentation Tests

This module provides automated testing for API documentation accuracy,
example validation, and endpoint documentation completeness.
"""

import pytest
import requests
import json
from typing import Dict, Any, List, Optional
from datetime import datetime
import jsonschema
from jsonschema import validate, ValidationError
from testing_utilities import APITestClient


class APIDocumentationTester:
    """
    Comprehensive API documentation testing class.
    
    This class validates:
    - OpenAPI schema accuracy
    - Example request/response correctness
    - Documentation completeness
    - Health check endpoint documentation
    - Error response documentation
    """
    
    def __init__(self, base_url: str = "http://localhost:8000"):
        """
        Initialize the documentation tester.
        
        Args:
            base_url: Base URL of the API server
        """
        self.base_url = base_url.rstrip('/')
        self.client = APITestClient(base_url)
        self.openapi_schema = None
        self.test_results = []
    
    def fetch_openapi_schema(self) -> Dict[str, Any]:
        """
        Fetch the OpenAPI schema from the API server.
        
        Returns:
            Dict[str, Any]: OpenAPI schema
        """
        try:
            response = requests.get(f"{self.base_url}/openapi.json")
            response.raise_for_status()
            self.openapi_schema = response.json()
            return self.openapi_schema
        except Exception as e:
            raise Exception(f"Failed to fetch OpenAPI schema: {str(e)}")
    
    def test_openapi_schema_structure(self) -> Dict[str, Any]:
        """
        Test the basic structure of the OpenAPI schema.
        
        Returns:
            Dict[str, Any]: Test results
        """
        if not self.openapi_schema:
            self.fetch_openapi_schema()
        
        required_fields = [
            "openapi", "info", "paths", "components"
        ]
        
        missing_fields = []
        for field in required_fields:
            if field not in self.openapi_schema:
                missing_fields.append(field)
        
        # Check info section
        info_required = ["title", "version", "description"]
        info_missing = []
        if "info" in self.openapi_schema:
            for field in info_required:
                if field not in self.openapi_schema["info"]:
                    info_missing.append(field)
        
        # Check components section
        components_expected = ["schemas", "securitySchemes"]
        components_missing = []
        if "components" in self.openapi_schema:
            for field in components_expected:
                if field not in self.openapi_schema["components"]:
                    components_missing.append(field)
        
        success = not missing_fields and not info_missing and not components_missing
        
        return {
            "test_name": "OpenAPI Schema Structure",
            "success": success,
            "missing_root_fields": missing_fields,
            "missing_info_fields": info_missing,
            "missing_component_fields": components_missing,
            "total_paths": len(self.openapi_schema.get("paths", {})),
            "total_schemas": len(self.openapi_schema.get("components", {}).get("schemas", {}))
        }
    
    def test_endpoint_documentation_completeness(self) -> Dict[str, Any]:
        """
        Test that all endpoints have complete documentation.
        
        Returns:
            Dict[str, Any]: Test results
        """
        if not self.openapi_schema:
            self.fetch_openapi_schema()
        
        paths = self.openapi_schema.get("paths", {})
        incomplete_endpoints = []
        
        required_fields = ["summary", "description", "responses"]
        optional_but_recommended = ["tags", "parameters"]
        
        for path, methods in paths.items():
            for method, spec in methods.items():
                if method.upper() in ["GET", "POST", "PUT", "DELETE", "PATCH"]:
                    missing_required = []
                    missing_recommended = []
                    
                    # Check required fields
                    for field in required_fields:
                        if field not in spec:
                            missing_required.append(field)
                    
                    # Check recommended fields
                    for field in optional_but_recommended:
                        if field not in spec:
                            missing_recommended.append(field)
                    
                    if missing_required or missing_recommended:
                        incomplete_endpoints.append({
                            "endpoint": f"{method.upper()} {path}",
                            "missing_required": missing_required,
                            "missing_recommended": missing_recommended
                        })
        
        success = len(incomplete_endpoints) == 0
        
        return {
            "test_name": "Endpoint Documentation Completeness",
            "success": success,
            "total_endpoints": sum(len([m for m in methods.keys() if m.upper() in ["GET", "POST", "PUT", "DELETE", "PATCH"]]) 
                                 for methods in paths.values()),
            "incomplete_endpoints": len(incomplete_endpoints),
            "incomplete_details": incomplete_endpoints[:10]  # Show first 10
        }
    
    def test_response_schema_definitions(self) -> Dict[str, Any]:
        """
        Test that response schemas are properly defined.
        
        Returns:
            Dict[str, Any]: Test results
        """
        if not self.openapi_schema:
            self.fetch_openapi_schema()
        
        paths = self.openapi_schema.get("paths", {})
        schemas = self.openapi_schema.get("components", {}).get("schemas", {})
        
        missing_schemas = []
        invalid_references = []
        
        for path, methods in paths.items():
            for method, spec in methods.items():
                if method.upper() in ["GET", "POST", "PUT", "DELETE", "PATCH"]:
                    responses = spec.get("responses", {})
                    
                    for status_code, response_spec in responses.items():
                        content = response_spec.get("content", {})
                        
                        for media_type, media_spec in content.items():
                            schema = media_spec.get("schema", {})
                            
                            # Check for $ref references
                            if "$ref" in schema:
                                ref_path = schema["$ref"]
                                if ref_path.startswith("#/components/schemas/"):
                                    schema_name = ref_path.split("/")[-1]
                                    if schema_name not in schemas:
                                        missing_schemas.append({
                                            "endpoint": f"{method.upper()} {path}",
                                            "status_code": status_code,
                                            "missing_schema": schema_name
                                        })
                            
                            # Check for inline schemas without proper structure
                            elif "type" not in schema and "properties" not in schema and "$ref" not in schema:
                                if schema:  # Not empty
                                    invalid_references.append({
                                        "endpoint": f"{method.upper()} {path}",
                                        "status_code": status_code,
                                        "issue": "Invalid schema structure"
                                    })
        
        success = len(missing_schemas) == 0 and len(invalid_references) == 0
        
        return {
            "test_name": "Response Schema Definitions",
            "success": success,
            "missing_schemas": missing_schemas,
            "invalid_references": invalid_references,
            "total_schemas_defined": len(schemas)
        }
    
    def test_example_requests_responses(self, admin_email: str = None, admin_password: str = None) -> Dict[str, Any]:
        """
        Test that example requests and responses in documentation are accurate.
        
        Args:
            admin_email: Admin email for authentication
            admin_password: Admin password for authentication
            
        Returns:
            Dict[str, Any]: Test results
        """
        if not self.openapi_schema:
            self.fetch_openapi_schema()
        
        # Authenticate if credentials provided
        authenticated = False
        if admin_email and admin_password:
            authenticated = self.client.authenticate(admin_email, admin_password)
        
        paths = self.openapi_schema.get("paths", {})
        example_test_results = []
        
        # Test specific endpoints with examples
        test_endpoints = [
            {
                "path": "/v1.0/health/",
                "method": "GET",
                "requires_auth": False,
                "expected_fields": ["status", "service", "timestamp"]
            },
            {
                "path": "/v1.0/health/detailed",
                "method": "GET", 
                "requires_auth": False,
                "expected_fields": ["status", "checks", "response_time_ms"]
            },
            {
                "path": "/v1.0/user/me",
                "method": "GET",
                "requires_auth": True,
                "expected_fields": ["id", "username", "email", "user_status"]
            }
        ]
        
        for endpoint in test_endpoints:
            if endpoint["requires_auth"] and not authenticated:
                example_test_results.append({
                    "endpoint": f"{endpoint['method']} {endpoint['path']}",
                    "status": "skipped",
                    "reason": "Authentication required but not available"
                })
                continue
            
            try:
                # Make actual request
                if endpoint["method"] == "GET":
                    response = self.client.session.get(f"{self.base_url}{endpoint['path']}")
                else:
                    response = self.client.session.request(endpoint["method"], f"{self.base_url}{endpoint['path']}")
                
                # Parse response
                try:
                    response_data = response.json()
                except json.JSONDecodeError:
                    response_data = {}
                
                # Check if expected fields are present
                missing_fields = []
                for field in endpoint.get("expected_fields", []):
                    if field not in response_data:
                        missing_fields.append(field)
                
                # Check if response matches documented examples
                endpoint_spec = paths.get(endpoint["path"], {}).get(endpoint["method"].lower(), {})
                documented_examples = self._extract_examples_from_spec(endpoint_spec)
                
                example_match = self._compare_response_with_examples(response_data, documented_examples)
                
                success = response.status_code == 200 and not missing_fields
                
                example_test_results.append({
                    "endpoint": f"{endpoint['method']} {endpoint['path']}",
                    "status": "success" if success else "failed",
                    "status_code": response.status_code,
                    "missing_fields": missing_fields,
                    "example_match": example_match,
                    "has_documented_examples": len(documented_examples) > 0
                })
                
            except Exception as e:
                example_test_results.append({
                    "endpoint": f"{endpoint['method']} {endpoint['path']}",
                    "status": "error",
                    "error": str(e)
                })
        
        successful_tests = sum(1 for r in example_test_results if r["status"] == "success")
        total_tests = len(example_test_results)
        
        return {
            "test_name": "Example Requests and Responses",
            "success": successful_tests == total_tests,
            "total_tests": total_tests,
            "successful_tests": successful_tests,
            "failed_tests": total_tests - successful_tests,
            "results": example_test_results
        }
    
    def test_health_check_documentation(self) -> Dict[str, Any]:
        """
        Test that health check endpoints are properly documented.
        
        Returns:
            Dict[str, Any]: Test results
        """
        if not self.openapi_schema:
            self.fetch_openapi_schema()
        
        expected_health_endpoints = [
            "/v1.0/health/",
            "/v1.0/health/detailed",
            "/v1.0/health/database",
            "/v1.0/health/cache",
            "/v1.0/health/status",
            "/v1.0/health/readiness",
            "/v1.0/health/liveness"
        ]
        
        paths = self.openapi_schema.get("paths", {})
        
        documented_endpoints = []
        missing_endpoints = []
        
        for endpoint in expected_health_endpoints:
            if endpoint in paths and "get" in paths[endpoint]:
                documented_endpoints.append(endpoint)
                
                # Check if endpoint has proper documentation
                spec = paths[endpoint]["get"]
                required_fields = ["summary", "description", "responses"]
                
                for field in required_fields:
                    if field not in spec:
                        missing_endpoints.append(f"{endpoint} missing {field}")
            else:
                missing_endpoints.append(endpoint)
        
        # Test actual health endpoints
        health_test_results = []
        for endpoint in expected_health_endpoints:
            try:
                response = requests.get(f"{self.base_url}{endpoint}", timeout=5)
                health_test_results.append({
                    "endpoint": endpoint,
                    "status_code": response.status_code,
                    "documented": endpoint in documented_endpoints,
                    "working": response.status_code == 200
                })
            except Exception as e:
                health_test_results.append({
                    "endpoint": endpoint,
                    "status_code": 0,
                    "documented": endpoint in documented_endpoints,
                    "working": False,
                    "error": str(e)
                })
        
        success = len(missing_endpoints) == 0 and all(r["working"] for r in health_test_results)
        
        return {
            "test_name": "Health Check Documentation",
            "success": success,
            "total_expected_endpoints": len(expected_health_endpoints),
            "documented_endpoints": len(documented_endpoints),
            "missing_documentation": missing_endpoints,
            "endpoint_tests": health_test_results
        }
    
    def test_error_response_documentation(self) -> Dict[str, Any]:
        """
        Test that error responses are properly documented.
        
        Returns:
            Dict[str, Any]: Test results
        """
        if not self.openapi_schema:
            self.fetch_openapi_schema()
        
        paths = self.openapi_schema.get("paths", {})
        schemas = self.openapi_schema.get("components", {}).get("schemas", {})
        
        # Check for common error response schemas
        expected_error_schemas = [
            "APIError",
            "ValidationError"
        ]
        
        missing_error_schemas = []
        for schema in expected_error_schemas:
            if schema not in schemas:
                missing_error_schemas.append(schema)
        
        # Check endpoints for error response documentation
        endpoints_without_error_docs = []
        
        for path, methods in paths.items():
            for method, spec in methods.items():
                if method.upper() in ["GET", "POST", "PUT", "DELETE", "PATCH"]:
                    responses = spec.get("responses", {})
                    
                    # Check for common error status codes
                    expected_error_codes = ["400", "401", "403", "404", "422", "500"]
                    documented_error_codes = [code for code in expected_error_codes if code in responses]
                    
                    if len(documented_error_codes) == 0:
                        endpoints_without_error_docs.append(f"{method.upper()} {path}")
        
        success = len(missing_error_schemas) == 0 and len(endpoints_without_error_docs) < 5  # Allow some flexibility
        
        return {
            "test_name": "Error Response Documentation",
            "success": success,
            "missing_error_schemas": missing_error_schemas,
            "endpoints_without_error_docs": len(endpoints_without_error_docs),
            "sample_endpoints_without_errors": endpoints_without_error_docs[:5],
            "error_schemas_defined": [schema for schema in expected_error_schemas if schema in schemas]
        }
    
    def _extract_examples_from_spec(self, endpoint_spec: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Extract examples from endpoint specification"""
        examples = []
        
        responses = endpoint_spec.get("responses", {})
        for status_code, response_spec in responses.items():
            content = response_spec.get("content", {})
            for media_type, media_spec in content.items():
                # Check for examples in different formats
                if "examples" in media_spec:
                    for example_name, example_data in media_spec["examples"].items():
                        if "value" in example_data:
                            examples.append(example_data["value"])
                elif "example" in media_spec:
                    examples.append(media_spec["example"])
        
        return examples
    
    def _compare_response_with_examples(self, actual_response: Dict[str, Any], 
                                      documented_examples: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Compare actual response with documented examples"""
        if not documented_examples:
            return {"has_examples": False}
        
        # Simple field presence check
        example_fields = set()
        for example in documented_examples:
            if isinstance(example, dict):
                example_fields.update(example.keys())
        
        actual_fields = set(actual_response.keys()) if isinstance(actual_response, dict) else set()
        
        common_fields = example_fields.intersection(actual_fields)
        missing_fields = example_fields - actual_fields
        extra_fields = actual_fields - example_fields
        
        return {
            "has_examples": True,
            "total_example_fields": len(example_fields),
            "common_fields": len(common_fields),
            "missing_fields": list(missing_fields),
            "extra_fields": list(extra_fields),
            "field_match_rate": len(common_fields) / len(example_fields) if example_fields else 0
        }
    
    def run_all_documentation_tests(self, admin_email: str = None, admin_password: str = None) -> Dict[str, Any]:
        """
        Run all documentation tests and return comprehensive results.
        
        Args:
            admin_email: Admin email for authentication
            admin_password: Admin password for authentication
            
        Returns:
            Dict[str, Any]: Complete test results
        """
        print("📚 Running Comprehensive API Documentation Tests")
        print("=" * 60)
        
        # Fetch OpenAPI schema first
        try:
            self.fetch_openapi_schema()
            print("✅ OpenAPI schema fetched successfully")
        except Exception as e:
            print(f"❌ Failed to fetch OpenAPI schema: {e}")
            return {"error": "Could not fetch OpenAPI schema", "details": str(e)}
        
        test_results = {}
        
        # 1. Test OpenAPI schema structure
        print("\n1️⃣  Testing OpenAPI Schema Structure...")
        test_results["schema_structure"] = self.test_openapi_schema_structure()
        status = "✅" if test_results["schema_structure"]["success"] else "❌"
        print(f"   {status} Schema Structure Test")
        
        # 2. Test endpoint documentation completeness
        print("\n2️⃣  Testing Endpoint Documentation Completeness...")
        test_results["endpoint_completeness"] = self.test_endpoint_documentation_completeness()
        status = "✅" if test_results["endpoint_completeness"]["success"] else "❌"
        print(f"   {status} Endpoint Documentation Test")
        
        # 3. Test response schema definitions
        print("\n3️⃣  Testing Response Schema Definitions...")
        test_results["response_schemas"] = self.test_response_schema_definitions()
        status = "✅" if test_results["response_schemas"]["success"] else "❌"
        print(f"   {status} Response Schema Test")
        
        # 4. Test example requests and responses
        print("\n4️⃣  Testing Example Requests and Responses...")
        test_results["example_accuracy"] = self.test_example_requests_responses(admin_email, admin_password)
        status = "✅" if test_results["example_accuracy"]["success"] else "❌"
        print(f"   {status} Example Accuracy Test")
        
        # 5. Test health check documentation
        print("\n5️⃣  Testing Health Check Documentation...")
        test_results["health_check_docs"] = self.test_health_check_documentation()
        status = "✅" if test_results["health_check_docs"]["success"] else "❌"
        print(f"   {status} Health Check Documentation Test")
        
        # 6. Test error response documentation
        print("\n6️⃣  Testing Error Response Documentation...")
        test_results["error_response_docs"] = self.test_error_response_documentation()
        status = "✅" if test_results["error_response_docs"]["success"] else "❌"
        print(f"   {status} Error Response Documentation Test")
        
        # Calculate overall results
        successful_tests = sum(1 for test in test_results.values() if test.get("success", False))
        total_tests = len(test_results)
        success_rate = (successful_tests / total_tests * 100) if total_tests > 0 else 0
        
        overall_result = {
            "timestamp": datetime.utcnow().isoformat(),
            "summary": {
                "total_tests": total_tests,
                "successful_tests": successful_tests,
                "failed_tests": total_tests - successful_tests,
                "success_rate": round(success_rate, 2)
            },
            "test_results": test_results
        }
        
        # Print summary
        print("\n" + "=" * 60)
        print("📊 DOCUMENTATION TEST SUMMARY")
        print("=" * 60)
        print(f"Total Tests: {total_tests}")
        print(f"Successful: {successful_tests} ✅")
        print(f"Failed: {total_tests - successful_tests} ❌")
        print(f"Success Rate: {success_rate:.1f}%")
        
        overall_status = "✅ DOCUMENTATION HEALTHY" if success_rate >= 80 else "⚠️  DOCUMENTATION ISSUES"
        print(f"\nOverall Status: {overall_status}")
        
        return overall_result


def run_documentation_tests(base_url: str = "http://localhost:8000", 
                          admin_email: str = None, admin_password: str = None,
                          output_file: str = None) -> Dict[str, Any]:
    """
    Run comprehensive API documentation tests.
    
    Args:
        base_url: Base URL of the API server
        admin_email: Admin email for authentication
        admin_password: Admin password for authentication
        output_file: Optional output file for results
        
    Returns:
        Dict[str, Any]: Test results
    """
    tester = APIDocumentationTester(base_url)
    results = tester.run_all_documentation_tests(admin_email, admin_password)
    
    # Save results if output file specified
    if output_file:
        with open(output_file, 'w') as f:
            json.dump(results, f, indent=2)
        print(f"\n📄 Results saved to: {output_file}")
    
    return results


# Pytest test functions for automated testing
class TestAPIDocumentation:
    """Pytest test class for API documentation validation"""
    
    @pytest.fixture
    def tester(self):
        """Create API documentation tester instance"""
        return APIDocumentationTester()
    
    def test_openapi_schema_structure(self, tester):
        """Test OpenAPI schema has required structure"""
        result = tester.test_openapi_schema_structure()
        assert result["success"], f"Schema structure test failed: {result}"
    
    def test_endpoint_documentation_completeness(self, tester):
        """Test all endpoints have complete documentation"""
        result = tester.test_endpoint_documentation_completeness()
        assert result["success"], f"Endpoint documentation incomplete: {result}"
    
    def test_response_schema_definitions(self, tester):
        """Test response schemas are properly defined"""
        result = tester.test_response_schema_definitions()
        assert result["success"], f"Response schema issues: {result}"
    
    def test_health_check_documentation(self, tester):
        """Test health check endpoints are documented"""
        result = tester.test_health_check_documentation()
        assert result["success"], f"Health check documentation issues: {result}"
    
    def test_error_response_documentation(self, tester):
        """Test error responses are documented"""
        result = tester.test_error_response_documentation()
        # Allow some flexibility for error documentation
        assert result["success"] or result["endpoints_without_error_docs"] < 10, \
               f"Too many endpoints without error documentation: {result}"


if __name__ == "__main__":
    import sys
    
    # Command line usage
    if len(sys.argv) >= 2:
        base_url = sys.argv[1] if len(sys.argv) > 1 else "http://localhost:8000"
        admin_email = sys.argv[2] if len(sys.argv) > 2 else None
        admin_password = sys.argv[3] if len(sys.argv) > 3 else None
        output_file = sys.argv[4] if len(sys.argv) > 4 else None
        
        run_documentation_tests(base_url, admin_email, admin_password, output_file)
    else:
        print("Usage: python test_api_documentation.py [base_url] [admin_email] [admin_password] [output_file]")
        print("Example: python test_api_documentation.py http://localhost:8000 admin@example.com password123 doc_test_results.json")
        sys.exit(1)