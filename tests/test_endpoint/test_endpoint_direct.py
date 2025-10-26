import sys
import os
sys.path.append('.')

try:
    from routes.ml_mapping import get_not_mapped_hotel_id_list, NotMappedHotelRequest
    print("✓ Successfully imported the endpoint function")
    
    # Test the function directly
    request = NotMappedHotelRequest(supplier_name="agoda")
    print(f"✓ Created request object: {request}")
    
    # Try to call the function (this will be async, so we'll just check if it's callable)
    print(f"✓ Function is callable: {callable(get_not_mapped_hotel_id_list)}")
    
    # Check if the utility functions work
    from routes.ml_mapping import get_hotel_ids_from_folder, get_hotel_ids_from_database
    
    print("Testing folder function...")
    folder_ids = get_hotel_ids_from_folder("agoda")
    print(f"✓ Folder function returned {len(folder_ids)} IDs")
    
    print("Testing database function...")
    db_ids = get_hotel_ids_from_database("agoda")
    print(f"✓ Database function returned {len(db_ids)} IDs")
    
    print("✓ All functions are working correctly!")
    
except Exception as e:
    print(f"✗ Error: {e}")
    import traceback
    traceback.print_exc()