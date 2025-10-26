import sys
import os
sys.path.append('.')

from routes.ml_mapping import get_hotel_ids_from_folder, get_hotel_ids_from_database

print("Testing both endpoints logic...")

# Get the actual data
print("Getting folder IDs...")
folder_ids = get_hotel_ids_from_folder("agoda")
print(f"Folder has {len(folder_ids)} hotel IDs")

print("Getting database IDs...")
db_ids = get_hotel_ids_from_database("agoda")
print(f"Database has {len(db_ids)} hotel IDs")

# Calculate both differences
folder_set = set(folder_ids)
db_set = set(db_ids)

# Endpoint 1: get_not_mapped_hotel_id_list
# Hotel IDs in folder but NOT in database (folder - database)
not_mapped_ids = sorted(list(folder_set - db_set))
print(f"\n=== get_not_mapped_hotel_id_list ===")
print(f"Hotel IDs in folder but NOT in database: {len(not_mapped_ids)}")
print(f"First 10 IDs: {not_mapped_ids[:10]}")

# Endpoint 2: get_not_update_content_hotel_id_list  
# Hotel IDs in database but NOT in folder (database - folder)
not_update_content_ids = sorted(list(db_set - folder_set))
print(f"\n=== get_not_update_content_hotel_id_list ===")
print(f"Hotel IDs in database but NOT in folder: {len(not_update_content_ids)}")
print(f"First 10 IDs: {not_update_content_ids[:10]}")

print(f"\n=== Summary ===")
print(f"Total folder IDs: {len(folder_ids)}")
print(f"Total database IDs: {len(db_ids)}")
print(f"Common IDs: {len(folder_set & db_set)}")
print(f"Need mapping (folder - db): {len(not_mapped_ids)}")
print(f"Need content update (db - folder): {len(not_update_content_ids)}")
print(f"Verification: {len(folder_ids)} + {len(not_update_content_ids)} - {len(not_mapped_ids)} = {len(db_ids)}")