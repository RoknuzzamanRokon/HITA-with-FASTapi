import requests
import json

url = "http://127.0.0.1:8001/v1.0/content/get-all-ittid"

headers = {
    'Content-Type': 'application/json',
    'Authorization': 'Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOiJ1cnNhbXJva28iLCJ1c2VyX2lkIjoiMWEyMDNjY2RhNCIsInJvbGUiOiJzdXBlcl91c2VyIiwiZXhwIjoxNzY1MDAwMTI5LCJ0eXBlIjoiYWNjZXNzIiwiaWF0IjoxNzYzMjAwMTI5fQ.Xuw8m2zhJ98bX5U8QzMfEU9qdVkLtOvyjx06IpPc9Pw'
}

# Call API
response = requests.get(url, headers=headers)

# Convert to Python dict
data = response.json()

# Extract only ittid_list
ittid_list = data.get("ittid_list", [])

# Save output to JSON file
file_name = "ittid_mapping_id.json"
with open(file_name, "w") as json_file:
    json.dump(ittid_list, json_file, indent=4)

print(f"Saved {len(ittid_list)} ITTIDs to {file_name}")
