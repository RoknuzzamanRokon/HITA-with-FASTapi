#!/usr/bin/env python3
"""
Test script to verify the improvements in mapping_3.py
"""

import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from mapping_3 import HotelMapper, clean_text, calculate_fuzzy_score, extract_city_country_from_api

def test_clean_text():
    """Test the enhanced clean_text function"""
    print("Testing clean_text function:")
    test_cases = [
        ("Hotel & Resort", "hotel resort"),
        ("Grand Hotel, Paris", "grand hotel paris"),
        ("  Multiple   Spaces  ", "multiple spaces"),
        ("Special@#$Characters!", "special characters"),
        (None, ""),
        ("", "")
    ]
    
    for input_text, expected in test_cases:
        result = clean_text(input_text)
        status = "✓" if result == expected else "✗"
        print(f"  {status} '{input_text}' -> '{result}' (expected: '{expected}')")

def test_fuzzy_score():
    """Test the enhanced fuzzy scoring"""
    print("\nTesting calculate_fuzzy_score function:")
    test_cases = [
        ("Grand Hotel", "Grand Hotel", 1.0),
        ("Grand Hotel", "grand hotel", 1.0),
        ("Grand Hotel Paris", "Grand Hotel", 0.8),  # Should be high due to substring match
        ("Hilton", "Hotel Hilton", 0.6),  # Should get boost for word match
        ("", "Grand Hotel", 0.0),
        ("Completely Different", "Another Hotel", 0.2)  # Should be low
    ]
    
    for text1, text2, min_expected in test_cases:
        result = calculate_fuzzy_score(text1, text2)
        status = "✓" if result >= min_expected else "✗"
        print(f"  {status} '{text1}' vs '{text2}' -> {result:.3f} (min expected: {min_expected})")

def test_api_extraction():
    """Test API data extraction"""
    print("\nTesting extract_city_country_from_api function:")
    
    test_api_responses = [
        {
            "name": "Grand Hotel",
            "city": "Paris",
            "country": "France"
        },
        {
            "name": "Hotel Example",
            "address": {
                "city": "London",
                "country": "UK"
            }
        },
        {
            "name": "Another Hotel",
            "location": {
                "city": "Tokyo"
            },
            "country_code": "JP"
        }
    ]
    
    for i, api_data in enumerate(test_api_responses, 1):
        city, country = extract_city_country_from_api(api_data)
        print(f"  Test {i}: City='{city}', Country='{country}'")

def test_hotel_mapper_init():
    """Test HotelMapper initialization"""
    print("\nTesting HotelMapper initialization:")
    try:
        mapper = HotelMapper()
        print("  ✓ HotelMapper initialized successfully")
        print(f"  ✓ CSV path: {mapper.csv_file_path}")
        print(f"  ✓ Base URL: {mapper.base_url}")
        print(f"  ✓ Timeout: {mapper.timeout}s")
    except Exception as e:
        print(f"  ✗ Error initializing HotelMapper: {e}")

if __name__ == "__main__":
    print("="*60)
    print("TESTING MAPPING_3.PY IMPROVEMENTS")
    print("="*60)
    
    test_clean_text()
    test_fuzzy_score()
    test_api_extraction()
    test_hotel_mapper_init()
    
    print("\n" + "="*60)
    print("TESTS COMPLETED")
    print("="*60)
    print("\nTo run the actual hotel mapping, use:")
    print("python mapping_3.py")
    print("\nOr import and use the HotelMapper class in your code.")