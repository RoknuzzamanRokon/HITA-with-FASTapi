import requests
import json
import pandas as pd
from difflib import SequenceMatcher

def find_best_match(api_name, csv_file_path):
    """
    Find the best matching hotel name in CSV file and return the ID and ittid
    """
    try:
        # Read the CSV file
        df = pd.read_csv(csv_file_path)
        
        # Split and clean the API name
        api_name_clean = api_name.split(',')[0].strip().lower()
        
        best_match = None
        best_score = 0
        best_row = None
        
        # Iterate through CSV rows to find best match
        for index, row in df.iterrows():
            csv_name = str(row['Name']).strip().lower()
            
            # Calculate similarity score
            score = SequenceMatcher(None, api_name_clean, csv_name).ratio()
            
            # Update best match if this score is higher
            if score > best_score:
                best_score = score
                best_match = csv_name
                best_row = row
        
        # If we found a reasonable match (threshold can be adjusted)
        if best_score > 0.7:  # 70% similarity threshold
            return {
                "Id": int(best_row['Id']),
                "ittid": int(best_row['ittid'])
            }
        else:
            return None
            
    except Exception as e:
        print(f"Error in CSV matching: {e}")
        return None

def main():
    supplier_name = "agoda"
    hotel_id = "31563646"
    
    # Step 1: Call pushhotel API
    try:
        url1 = "https://mappingapi.innsightmap.com/hotel/pushhotel"
        payload1 = json.dumps({
            "supplier_code": supplier_name,
            "hotel_id": [hotel_id]
        })
        headers = {'Content-Type': 'application/json'}
        
        response1 = requests.request("POST", url1, headers=headers, data=payload1)
        
    except Exception as e:
        print(f"Error in Step 1: {e}")
        return
    
    # Step 2: Call details API to get hotel name
    try:
        url2 = "https://mappingapi.innsightmap.com/hotel/details"
        payload2 = json.dumps({
            "supplier_code": supplier_name,
            "hotel_id": hotel_id
        })
        
        response2 = requests.request("POST", url2, headers=headers, data=payload2)
        
        # Parse the response to get hotel name
        details_data = response2.json()
        hotel_name = details_data.get('name')
        
        if not hotel_name:
            print("Could not find hotel name in response")
            return
            
        print(f"Extracted Hotel Name: {hotel_name}")
        
    except Exception as e:
        print(f"Error in Step 2: {e}")
        return
    
    # Step 3: Match with CSV file
    try:
        csv_file_path = "D:/Rokon/ofc_git/HITA_full/backend/static/hotelcontent/itt_hotel_basic_info.csv"
        match_result = find_best_match(hotel_name, csv_file_path)
        
        if match_result:
            # Add supplier_name and hotel_id to result
            match_result["supplier_name"] = supplier_name
            match_result["hotel_id"] = hotel_id

            result = {
                "find_hotel": match_result
            }
            print("\nFinal Result:")
            print(json.dumps(result, indent=2))
        else:
            print("No matching hotel found in CSV file")
            
    except Exception as e:
        print(f"Error in Step 3: {e}")

if __name__ == "__main__":
    main()
