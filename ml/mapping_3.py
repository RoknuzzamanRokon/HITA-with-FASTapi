import requests
import json
import pandas as pd
from difflib import SequenceMatcher
import re
from typing import Optional, Dict, Any, Tuple
import logging

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def clean_text(text: Any) -> str:
    """Clean and normalize text for better matching"""
    if not text or pd.isna(text):
        return ""
    # Remove extra whitespace, special characters, and normalize
    cleaned = re.sub(r'[^\w\s]', ' ', str(text))
    return ' '.join(cleaned.lower().split())

def extract_city_country_from_api(api_data: Dict[str, Any]) -> Tuple[str, str]:
    """Extract city and country from API response with comprehensive fallbacks"""
    city = None
    country = None
    
    # Enhanced extraction with multiple fallback options
    city_fields = [
        'city',
        ('address', 'city'),
        ('location', 'city'),
        ('geo', 'city'),
        'city_name'
    ]
    
    country_fields = [
        'country',
        ('address', 'country'),
        ('location', 'country'),
        ('geo', 'country'),
        'country_name',
        'country_code'
    ]
    
    # Extract city
    for field in city_fields:
        if isinstance(field, tuple):
            if field[0] in api_data and isinstance(api_data[field[0]], dict) and field[1] in api_data[field[0]]:
                city = api_data[field[0]][field[1]]
                break
        elif field in api_data:
            city = api_data[field]
            break
    
    # Extract country
    for field in country_fields:
        if isinstance(field, tuple):
            if field[0] in api_data and isinstance(api_data[field[0]], dict) and field[1] in api_data[field[0]]:
                country = api_data[field[0]][field[1]]
                break
        elif field in api_data:
            country = api_data[field]
            break
    
    return clean_text(city), clean_text(country)

def calculate_fuzzy_score(text1: str, text2: str) -> float:
    """Calculate fuzzy matching score with multiple algorithms"""
    if not text1 or not text2:
        return 0.0
    
    # Use SequenceMatcher for basic similarity
    basic_score = SequenceMatcher(None, text1, text2).ratio()
    
    # Check for exact substring matches (boost score)
    if text1 in text2 or text2 in text1:
        basic_score = min(1.0, basic_score + 0.2)
    
    # Check for word-level matches
    words1 = set(text1.split())
    words2 = set(text2.split())
    if words1 and words2:
        word_overlap = len(words1.intersection(words2)) / len(words1.union(words2))
        basic_score = max(basic_score, word_overlap)
    
    return basic_score

def find_best_match(api_name: str, api_city: str, api_country: str, csv_file_path: str) -> Optional[Dict[str, Any]]:
    """
    Find the best matching hotel in CSV file using enhanced matching algorithm
    """
    try:
        logger.info(f"Loading CSV file: {csv_file_path}")
        df = pd.read_csv(csv_file_path)
        logger.info(f"Loaded {len(df)} hotels from CSV")
        
        # Clean and prepare API data
        api_name_clean = clean_text(api_name.split(',')[0] if api_name else "")
        api_city_clean = clean_text(api_city)
        api_country_clean = clean_text(api_country)
        
        if not api_name_clean:
            logger.warning("No valid hotel name provided for matching")
            return None
        
        best_match = None
        best_score = 0
        best_row = None
        matches_found = []
        
        # Pre-filter by country if available (performance optimization)
        if api_country_clean:
            country_mask = df['CountryName'].str.lower().str.contains(api_country_clean, na=False, regex=False)
            filtered_df = df[country_mask]
            if len(filtered_df) > 0:
                logger.info(f"Pre-filtered to {len(filtered_df)} hotels by country")
                df = filtered_df
        
        # Iterate through CSV rows to find best match
        for index, row in df.iterrows():
            csv_name = clean_text(row['Name'])
            csv_city = clean_text(row['CityName'])
            csv_country = clean_text(row['CountryName'])
            
            # Skip if essential data is missing
            if not csv_name:
                continue
            
            # Calculate name similarity score with enhanced algorithm
            name_score = calculate_fuzzy_score(api_name_clean, csv_name)
            
            # Calculate location score with weighted components
            location_score = 0
            location_weight = 0
            
            if api_city_clean and csv_city:
                city_score = calculate_fuzzy_score(api_city_clean, csv_city)
                location_score += city_score * 0.6
                location_weight += 0.6
            
            if api_country_clean and csv_country:
                country_score = calculate_fuzzy_score(api_country_clean, csv_country)
                location_score += country_score * 0.4
                location_weight += 0.4
            
            # Normalize location score
            if location_weight > 0:
                location_score = location_score / location_weight
            
            # Dynamic weighting based on available data
            if location_weight > 0:
                # Both name and location available
                final_score = (name_score * 0.75) + (location_score * 0.25)
            else:
                # Only name available
                final_score = name_score
            
            # Store potential matches for debugging
            if final_score > 0.4:  # Lower threshold for tracking
                matches_found.append({
                    'name': csv_name,
                    'city': csv_city,
                    'country': csv_country,
                    'score': final_score,
                    'name_score': name_score,
                    'location_score': location_score
                })
            
            # Update best match if this score is higher
            if final_score > best_score:
                best_score = final_score
                best_match = {
                    'name': csv_name,
                    'city': csv_city,
                    'country': csv_country
                }
                best_row = row
        
        # Log top matches for debugging
        matches_found.sort(key=lambda x: x['score'], reverse=True)
        logger.info(f"Top 3 matches found:")
        for i, match in enumerate(matches_found[:3]):
            logger.info(f"  {i+1}. {match['name']} (Score: {match['score']:.3f})")
        
        logger.info(f"Best match score: {best_score:.3f}")
        
        # Adaptive threshold based on data quality
        threshold = 0.6 if (api_city_clean and api_country_clean) else 0.7
        
        if best_score > threshold:
            return {
                "Id": int(best_row['Id']),
                "ittid": int(best_row['ittid']),
                "matched_name": best_row['Name'],
                "matched_city": best_row['CityName'],
                "matched_country": best_row['CountryName'],
                "confidence_score": round(best_score, 3),
                "threshold_used": threshold,
                "total_candidates": len(df)
            }
        else:
            logger.warning(f"No match found above threshold {threshold}")
            return None
            
    except FileNotFoundError:
        logger.error(f"CSV file not found: {csv_file_path}")
        return None
    except Exception as e:
        logger.error(f"Error in CSV matching: {e}")
        return None

class HotelMapper:
    """Enhanced hotel mapping class with better error handling and configuration"""
    
    def __init__(self, csv_file_path: str = "../../static/hotelcontent/itt_hotel_basic_info.csv"):
        self.csv_file_path = csv_file_path
        self.base_url = "https://mappingapi.innsightmap.com"
        self.headers = {'Content-Type': 'application/json'}
        self.timeout = 30
    
    def push_hotel(self, supplier_code: str, hotel_id: str) -> bool:
        """Push hotel to the mapping API"""
        try:
            logger.info(f"Pushing hotel {hotel_id} for supplier {supplier_code}")
            url = f"{self.base_url}/hotel/pushhotel"
            payload = {
                "supplier_code": supplier_code,
                "hotel_id": [hotel_id]
            }
            
            response = requests.post(
                url, 
                headers=self.headers, 
                data=json.dumps(payload),
                timeout=self.timeout
            )
            
            if response.status_code == 200:
                logger.info("Hotel pushed successfully")
                return True
            else:
                logger.warning(f"Push hotel returned status code: {response.status_code}")
                return False
                
        except requests.exceptions.Timeout:
            logger.error("Timeout occurred while pushing hotel")
            return False
        except Exception as e:
            logger.error(f"Error pushing hotel: {e}")
            return False
    
    def get_hotel_details(self, supplier_code: str, hotel_id: str) -> Optional[Dict[str, Any]]:
        """Get hotel details from the mapping API"""
        try:
            logger.info(f"Getting details for hotel {hotel_id}")
            url = f"{self.base_url}/hotel/details"
            payload = {
                "supplier_code": supplier_code,
                "hotel_id": hotel_id
            }
            
            response = requests.post(
                url,
                headers=self.headers,
                data=json.dumps(payload),
                timeout=self.timeout
            )
            
            if response.status_code != 200:
                logger.error(f"API returned status code {response.status_code}")
                logger.error(f"Response: {response.text}")
                return None
            
            return response.json()
            
        except requests.exceptions.Timeout:
            logger.error("Timeout occurred while getting hotel details")
            return None
        except Exception as e:
            logger.error(f"Error getting hotel details: {e}")
            return None
    
    def map_hotel(self, supplier_code: str, hotel_id: str) -> Optional[Dict[str, Any]]:
        """Complete hotel mapping process"""
        logger.info(f"Starting hotel mapping for {supplier_code}:{hotel_id}")
        
        # Step 1: Push hotel
        if not self.push_hotel(supplier_code, hotel_id):
            logger.error("Failed to push hotel, continuing anyway...")
        
        # Step 2: Get hotel details
        details_data = self.get_hotel_details(supplier_code, hotel_id)
        if not details_data:
            logger.error("Failed to get hotel details")
            return None
        
        # Extract hotel information
        hotel_name = details_data.get('name')
        if not hotel_name:
            logger.error("No hotel name found in API response")
            return None
        
        hotel_city, hotel_country = extract_city_country_from_api(details_data)
        
        logger.info(f"Extracted from API:")
        logger.info(f"  Name: {hotel_name}")
        logger.info(f"  City: {hotel_city}")
        logger.info(f"  Country: {hotel_country}")
        
        # Step 3: Find match in CSV
        match_result = find_best_match(hotel_name, hotel_city, hotel_country, self.csv_file_path)
        
        if match_result:
            result = {
                "find_hotel": {
                    "Id": match_result["Id"],
                    "ittid": match_result["ittid"],
                    "supplier_name": supplier_code,
                    "hotel_id": hotel_id,
                    "api_data": {
                        "name": hotel_name,
                        "city": hotel_city.title() if hotel_city else None,
                        "country": hotel_country.title() if hotel_country else None
                    },
                    "matched_data": {
                        "name": match_result["matched_name"],
                        "city": match_result["matched_city"],
                        "country": match_result["matched_country"]
                    },
                    "matching_info": {
                        "confidence_score": match_result["confidence_score"],
                        "threshold_used": match_result["threshold_used"],
                        "total_candidates": match_result["total_candidates"]
                    }
                }
            }
            logger.info("Hotel mapping completed successfully")
            return result
        else:
            logger.warning("No matching hotel found in CSV file")
            return None

def main():
    """Main function with configurable parameters"""
    # Configuration
    supplier_name = "agoda"
    hotel_id = "297844"
    
    # Initialize mapper
    mapper = HotelMapper()
    
    # Perform mapping
    result = mapper.map_hotel(supplier_name, hotel_id)
    
    if result:
        print("\n" + "="*50)
        print("HOTEL MAPPING RESULT")
        print("="*50)
        print(json.dumps(result, indent=2))
    else:
        print("\n" + "="*50)
        print("NO MATCH FOUND")
        print("="*50)

def batch_map_hotels(supplier_code: str, hotel_ids: list, csv_file_path: str = None) -> Dict[str, Any]:
    """Map multiple hotels in batch for better efficiency"""
    mapper = HotelMapper(csv_file_path) if csv_file_path else HotelMapper()
    results = {
        "successful_mappings": [],
        "failed_mappings": [],
        "summary": {
            "total_hotels": len(hotel_ids),
            "successful": 0,
            "failed": 0
        }
    }
    
    logger.info(f"Starting batch mapping for {len(hotel_ids)} hotels")
    
    for i, hotel_id in enumerate(hotel_ids, 1):
        logger.info(f"Processing hotel {i}/{len(hotel_ids)}: {hotel_id}")
        
        try:
            result = mapper.map_hotel(supplier_code, hotel_id)
            if result:
                results["successful_mappings"].append(result)
                results["summary"]["successful"] += 1
            else:
                results["failed_mappings"].append({
                    "hotel_id": hotel_id,
                    "reason": "No match found"
                })
                results["summary"]["failed"] += 1
        except Exception as e:
            logger.error(f"Error processing hotel {hotel_id}: {e}")
            results["failed_mappings"].append({
                "hotel_id": hotel_id,
                "reason": str(e)
            })
            results["summary"]["failed"] += 1
    
    logger.info(f"Batch mapping completed: {results['summary']['successful']}/{len(hotel_ids)} successful")
    return results

# def test_different_suppliers():
#     """Test mapping with different suppliers and hotel IDs"""
#     test_cases = [
#         {"supplier": "agoda", "hotel_id": "297844"},
#         # {"supplier": "agoda", "hotel_id": "31563646"},
#         # Add more test cases as needed
#     ]
    
#     mapper = HotelMapper()
    
#     for case in test_cases:
#         print(f"\n{'='*60}")
#         print(f"Testing: {case['supplier']} - {case['hotel_id']}")
#         print('='*60)
        
#         result = mapper.map_hotel(case['supplier'], case['hotel_id'])
#         if result:
#             print("SUCCESS:")
#             print(json.dumps(result, indent=2))
#         else:
#             print("FAILED: No match found")

if __name__ == "__main__":
    main()