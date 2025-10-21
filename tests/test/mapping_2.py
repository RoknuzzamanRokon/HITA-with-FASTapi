import requests
import json
import pandas as pd
from difflib import SequenceMatcher
import re

def clean_text(text):
    """Clean and normalize text for better matching"""
    if not text or pd.isna(text):
        return ""
    return str(text).lower().strip()

def extract_city_country_from_api(api_data):
    """Extract city and country from API response"""
    city = None
    country = None
    
    # Try to get city and country from different possible fields in API
    if 'city' in api_data:
        city = api_data['city']
    elif 'address' in api_data and 'city' in api_data['address']:
        city = api_data['address']['city']
    
    if 'country' in api_data:
        country = api_data['country']
    elif 'address' in api_data and 'country' in api_data['address']:
        country = api_data['address']['country']
    elif 'country_code' in api_data and api_data['country_code']:
        # You might need a mapping from country_code to country name
        country = api_data['country_code']
    
    return clean_text(city), clean_text(country)

def find_best_match(api_name, api_city, api_country, csv_file_path):
    """
    Find the best matching hotel in CSV file using name, city, and country
    """
    try:
        # Read the CSV file
        df = pd.read_csv(csv_file_path)
        
        # Clean API data
        api_name_clean = clean_text(api_name.split(',')[0] if api_name else "")
        
        best_match = None
        best_score = 0
        best_row = None
        
        # Iterate through CSV rows to find best match
        for index, row in df.iterrows():
            csv_name = clean_text(row['Name'])
            csv_city = clean_text(row['CityName'])
            csv_country = clean_text(row['CountryName'])
            
            # Calculate name similarity score
            name_score = SequenceMatcher(None, api_name_clean, csv_name).ratio()
            
            # Calculate location score
            location_score = 0
            if api_city and csv_city:
                city_score = SequenceMatcher(None, api_city, csv_city).ratio()
                location_score += city_score * 0.5
            if api_country and csv_country:
                country_score = SequenceMatcher(None, api_country, csv_country).ratio()
                location_score += country_score * 0.5
            
            # Combine scores (70% name, 30% location)
            final_score = (name_score * 0.7) + (location_score * 0.3)
            
            # Update best match if this score is higher
            if final_score > best_score:
                best_score = final_score
                best_match = {
                    'name': csv_name,
                    'city': csv_city,
                    'country': csv_country
                }
                best_row = row
        
        print(f"Best match score: {best_score:.2f}")
        
        # Return result if above threshold
        if best_score > 0.6:  # 60% similarity threshold
            return {
                "Id": int(best_row['Id']),
                "ittid": int(best_row['ittid']),
                "matched_name": best_row['Name'],
                "matched_city": best_row['CityName'],
                "matched_country": best_row['CountryName'],
                "confidence_score": round(best_score, 2)
            }
        else:
            return None
            
    except Exception as e:
        print(f"Error in CSV matching: {e}")
        return None

def main():
    supplier_name = "agoda"
    hotel_id = "64845042"
    
    # Step 1: Call pushhotel API
    try:
        print("Step 1: Calling pushhotel API...")
        url1 = "https://mappingapi.innsightmap.com/hotel/pushhotel"
        payload1 = json.dumps({
            "supplier_code": supplier_name,
            "hotel_id": [hotel_id]
        })
        headers = {'Content-Type': 'application/json'}
        
        response1 = requests.request("POST", url1, headers=headers, data=payload1)
        # print(f"Push Hotel Response: {response1.status_code}")
        
    except Exception as e:
        print(f"Error in Step 1: {e}")
        return
    
    # Step 2: Call details API to get hotel information
    try:
        print("\nStep 2: Calling details API...")
        url2 = "https://mappingapi.innsightmap.com/hotel/details"
        payload2 = json.dumps({
            "supplier_code": supplier_name,
            "hotel_id": hotel_id
        })
        
        response2 = requests.request("POST", url2, headers=headers, data=payload2)
        # print(f"Details API Response: {response2.status_code}")
        
        if response2.status_code != 200:
            print(f"Error: API returned status code {response2.status_code}")
            return
            
        # Parse the response
        details_data = response2.json()
        # print(f"Raw API response: {json.dumps(details_data, indent=2)}")
        
        # Extract required information
        hotel_name = details_data.get('name')
        hotel_city, hotel_country = extract_city_country_from_api(details_data)
        
        if not hotel_name:
            print("Could not find hotel name in response")
            return
            
        print(f"Extracted from API:")
        print(f"  Name: {hotel_name}")
        print(f"  City: {hotel_city}")
        print(f"  Country: {hotel_country}")
        
    except Exception as e:
        print(f"Error in Step 2: {e}")
        return
    
    # Step 3: Match with CSV file
    try:
        print("\nStep 3: Matching with CSV file...")
        csv_file_path = "../../static/hotelcontent/itt_hotel_basic_info.csv"
        
        match_result = find_best_match(hotel_name, hotel_city, hotel_country, csv_file_path)
        
        if match_result:
            result = {
                "find_hotel": {
                    "Id": match_result["Id"],
                    "ittid": match_result["ittid"],
                    "supplier_name": supplier_name,
                    "hotel_id": hotel_id,
                    "name": hotel_name,
                    "city": hotel_city.title() if hotel_city else None,
                    "country": hotel_country.title() if hotel_country else None,
                    "confidence_score": match_result["confidence_score"],
                    "matched_csv_name": match_result["matched_name"],
                    "matched_csv_city": match_result["matched_city"],
                    "matched_csv_country": match_result["matched_country"]
                }
            }
            print("\nFinal Result:")
            print(json.dumps(result, indent=2))
        else:
            print("No matching hotel found in CSV file")
            
    except Exception as e:
        print(f"Error in Step 3: {e}")

# Alternative function if the API structure is different
def alternative_main():
    """
    Alternative version if the API response structure is different
    """
    supplier_name = "agoda"
    hotel_id = "31563646"
    
    # Step 1: Push hotel
    try:
        url1 = "https://mappingapi.innsightmap.com/hotel/pushhotel"
        payload1 = json.dumps({"supplier_code": supplier_name, "hotel_id": [hotel_id]})
        headers = {'Content-Type': 'application/json'}
        response1 = requests.post(url1, headers=headers, data=payload1)
        print(f"Step 1 completed: {response1.status_code}")
    except Exception as e:
        print(f"Step 1 error: {e}")
        return

    # Step 2: Get details
    try:
        url2 = "https://mappingapi.innsightmap.com/hotel/details"
        payload2 = json.dumps({"supplier_code": supplier_name, "hotel_id": hotel_id})
        response2 = requests.post(url2, headers=headers, data=payload2)
        api_data = response2.json()
        
        # Extract data with fallbacks
        hotel_name = api_data.get('name', '')
        
        # For city and country, you might need to adjust these based on actual API response
        hotel_city = api_data.get('city') or (api_data.get('address', {}).get('city') if api_data.get('address') else None)
        hotel_country = api_data.get('country') or (api_data.get('address', {}).get('country') if api_data.get('address') else None)
        
        print(f"API Data - Name: {hotel_name}, City: {hotel_city}, Country: {hotel_country}")
        
    except Exception as e:
        print(f"Step 2 error: {e}")
        return

    # Step 3: CSV matching (same as above)
    # ... rest of the matching logic

if __name__ == "__main__":
    main()