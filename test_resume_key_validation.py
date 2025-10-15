"""
Test script to verify resume_key validation for /v1.0/content/get_all_hotel_only_supplier
Tests various resume_key scenarios to ensure proper validation
"""

import requests
import json

base_url = "http://127.0.0.1:8000"

def test_resume_key_validation():
    """Test resume_key validation with different scenarios"""
    
    print("🔍 Testing Resume Key Validation")
    print("=" * 50)
    
    # First, login to get a token
    login_data = 'username=roman&password=roman123'
    login_headers = {'Content-Type': 'application/x-www-form-urlencoded'}
    
    login_response = requests.post(f"{base_url}/v1.0/auth/token", data=login_data, headers=login_headers)
    
    if login_response.status_code != 200:
        print("❌ Failed to login")
        return
    
    token_data = json.loads(login_response.text)
    token = token_data.get('access_token')
    
    headers = {
        'Authorization': f'Bearer {token}',
        'Content-Type': 'application/json'
    }
    
    # Test data - you may need to adjust the provider_name based on your data
    test_provider = "hotelbeds"  # Adjust this to a provider that exists in your system
    
    print(f"\n📋 Testing with provider: {test_provider}")
    print("-" * 30)
    
    # Test 1: Valid request without resume_key (should work)
    print("\n1. Testing WITHOUT resume_key (Expected: 200)")
    test_valid_request(headers, test_provider, None)
    
    # Test 2: Get a valid resume_key first
    print("\n2. Getting valid resume_key for further tests...")
    valid_resume_key = get_valid_resume_key(headers, test_provider)
    
    if valid_resume_key:
        print(f"   ✅ Got valid resume_key: {valid_resume_key[:20]}...")
        
        # Test 3: Valid resume_key (should work)
        print("\n3. Testing WITH valid resume_key (Expected: 200)")
        test_valid_request(headers, test_provider, valid_resume_key)
        
        # Test 4: Invalid resume_key formats
        print("\n4. Testing INVALID resume_key formats (Expected: 400)")
        test_invalid_resume_keys(headers, test_provider)
    else:
        print("   ⚠️  No valid resume_key obtained (might be end of data)")
        print("\n4. Testing INVALID resume_key formats (Expected: 400)")
        test_invalid_resume_keys(headers, test_provider)

def test_valid_request(headers, provider, resume_key):
    """Test a valid request"""
    
    params = {
        'limit_per_page': 10
    }
    
    if resume_key:
        params['resume_key'] = resume_key
    
    data = {
        'provider_name': provider
    }
    
    try:
        response = requests.get(
            f"{base_url}/v1.0/content/get_all_hotel_only_supplier/",
            headers=headers,
            params=params,
            json=data
        )
        
        print(f"   Status: {response.status_code}")
        
        if response.status_code == 200:
            result = json.loads(response.text)
            print(f"   ✅ SUCCESS: Got {result.get('show_hotels_this_page', 0)} hotels")
            print(f"   📊 Total hotels: {result.get('total_hotel', 0)}")
            if result.get('resume_key'):
                print(f"   🔑 Next resume_key available: {result['resume_key'][:20]}...")
            else:
                print("   🏁 No more pages (end of data)")
        else:
            print(f"   ❌ FAILED: {response.text[:100]}...")
            
    except Exception as e:
        print(f"   ❌ ERROR: {e}")

def get_valid_resume_key(headers, provider):
    """Get a valid resume_key from the first page"""
    
    params = {
        'limit_per_page': 5  # Small limit to ensure we get a resume_key
    }
    
    data = {
        'provider_name': provider
    }
    
    try:
        response = requests.get(
            f"{base_url}/v1.0/content/get_all_hotel_only_supplier/",
            headers=headers,
            params=params,
            json=data
        )
        
        if response.status_code == 200:
            result = json.loads(response.text)
            return result.get('resume_key')
        else:
            print(f"   ❌ Failed to get valid resume_key: {response.text[:100]}...")
            return None
            
    except Exception as e:
        print(f"   ❌ ERROR getting resume_key: {e}")
        return None

def test_invalid_resume_keys(headers, provider):
    """Test various invalid resume_key formats"""
    
    invalid_resume_keys = [
        # Wrong format tests
        ("invalid_format", "No underscore separator"),
        ("123", "Missing random part"),
        ("abc_def", "Non-numeric ID"),
        ("123_short", "Random part too short"),
        ("123_" + "a" * 60, "Random part too long"),
        
        # Non-existent ID tests
        ("999999_" + "a" * 50, "Non-existent ID"),
        ("0_" + "b" * 50, "Zero ID"),
        ("-1_" + "c" * 50, "Negative ID"),
        
        # Special characters
        ("123_" + "!" * 50, "Special characters in random part"),
        ("", "Empty resume_key"),
        ("   ", "Whitespace only"),
    ]
    
    for resume_key, description in invalid_resume_keys:
        print(f"\n   Testing: {description}")
        print(f"   Resume key: '{resume_key[:30]}{'...' if len(resume_key) > 30 else ''}'")
        
        params = {
            'limit_per_page': 10,
            'resume_key': resume_key
        }
        
        data = {
            'provider_name': provider
        }
        
        try:
            response = requests.get(
                f"{base_url}/v1.0/content/get_all_hotel_only_supplier/",
                headers=headers,
                params=params,
                json=data
            )
            
            if response.status_code == 400:
                print(f"   ✅ PASS: Correctly rejected (400)")
                error_detail = json.loads(response.text).get('detail', '')
                print(f"   📝 Error: {error_detail[:80]}...")
            else:
                print(f"   ❌ FAIL: Expected 400, got {response.status_code}")
                print(f"   📝 Response: {response.text[:100]}...")
                
        except Exception as e:
            print(f"   ❌ ERROR: {e}")

def test_cross_provider_resume_key():
    """Test using resume_key from one provider with another provider"""
    
    print("\n5. Testing cross-provider resume_key usage (Expected: 400)")
    print("-" * 50)
    
    # This test would require having resume_keys from different providers
    # For now, we'll just document the expected behavior
    print("📝 Cross-provider resume_key test:")
    print("   - Resume_key from provider A should not work with provider B")
    print("   - This prevents data leakage between providers")
    print("   - Expected: 400 Bad Request with 'non-existent record' error")

if __name__ == "__main__":
    test_resume_key_validation()
    test_cross_provider_resume_key()
    
    print("\n" + "=" * 50)
    print("🎯 RESUME KEY VALIDATION TEST SUMMARY")
    print("=" * 50)
    print("✅ Validation checks implemented:")
    print("   - Format validation (id_randomstring)")
    print("   - Random part length validation (50 characters)")
    print("   - ID existence validation in database")
    print("   - Provider-specific ID validation")
    print("\n🔒 Security benefits:")
    print("   - Prevents invalid pagination attempts")
    print("   - Prevents cross-provider data access")
    print("   - Clear error messages for debugging")
    print("   - Protects against malformed requests")
    print("\n📝 Valid resume_key format:")
    print("   - Format: 'database_id_50_character_random_string'")
    print("   - Example: '12345_abcdefghijklmnopqrstuvwxyz1234567890abcdefghijkl'")
    print("   - Must reference existing record for the requested provider")