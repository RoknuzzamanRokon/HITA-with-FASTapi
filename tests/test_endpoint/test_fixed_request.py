import requests
import json

# Correct URL without trailing slash
url = "http://127.0.0.1:8002/v1.0/ml_mapping/get_not_mapped_hotel_id_list"

# Correct payload
payload = {"supplier_name": "agoda"}

# Headers
headers = {
    'Content-Type': 'application/json',
    'Authorization': 'Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOiJ1cnNhbXJva28iLCJ1c2VyX2lkIjoiMWEyMDNjY2RhNCIsInJvbGUiOiJzdXBlcl91c2VyIiwiZXhwIjoxNzYyOTk0ODE2LCJ0eXBlIjoiYWNjZXNzIiwiaWF0IjoxNzYxMTk0ODE2fQ.XAE6ma_JFe7JDGPVahpbo80OLxHhe5lN2vjsvhgQA1s'
}

# Use POST method and json parameter
response = requests.post(url, headers=headers, json=payload)

print("Status Code:", response.status_code)
print("Response:", response.text)

# If successful, pretty print the JSON
if response.status_code == 200:
    result = response.json()
    print("\nFormatted Response:")
    print(json.dumps(result, indent=2))
else:
    print("Error occurred")