import sys
import os
sys.path.append('.')

from routes.ml_mapping import get_hotel_ids_from_folder, get_hotel_ids_from_database

print("Testing the difference logic...")

# Get the actual data
print("Getting folder IDs...")
folder_ids = get_hotel_ids_from_folder("agoda")
print(f"Folder has {len(folder_ids)} hotel IDs")

print("Getting database IDs...")
db_ids = get_hotel_ids_from_database("agoda")
print(f"Database has {len(db_ids)} hotel IDs")

# Calculate the difference
folder_set = set(folder_ids)
db_set = set(db_ids)

# Hotel IDs in folder but NOT in database
not_mapped_ids = sorted(list(folder_set - db_set))
print(f"Hotel IDs in folder but NOT in database: {len(not_mapped_ids)}")

# Hotel IDs in database but NOT in folder (just for comparison)
extra_in_db = sorted(list(db_set - folder_set))
print(f"Hotel IDs in database but NOT in folder: {len(extra_in_db)}")

# Show some examples
print(f"\nFirst 10 hotel IDs in folder but NOT in database: {not_mapped_ids[:10]}")
print(f"First 10 hotel IDs in database but NOT in folder: {extra_in_db[:10]}")

# Verify our logic
print(f"\nVerification:")
print(f"Folder IDs: {len(folder_ids)}")
print(f"Database IDs: {len(db_ids)}")
print(f"In folder but not in DB: {len(not_mapped_ids)}")
print(f"In DB but not in folder: {len(extra_in_db)}")
print(f"Common IDs: {len(folder_set & db_set)}")

# The endpoint should return not_mapped_ids (folder - database)
print(f"\nThe endpoint will return {len(not_mapped_ids)} hotel IDs that are in folder but not in database")