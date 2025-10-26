# Hotel ID List APIs

## Overview

These endpoints help identify hotel IDs that need mapping or content updates by comparing JSON files with database records.

## Endpoints

### 1. Get Not Mapped Hotel ID List

Returns hotel IDs that exist in JSON files but are not yet mapped in the database.

```
POST /v1.0/ml_mapping/get_not_mapped_hotel_id_list
```

### 2. Get Not Update Content Hotel ID List

Returns hotel IDs that exist in database but don't have corresponding JSON files.

```
POST /v1.0/ml_mapping/get_not_update_content_hotel_id_list
```

## Request Body

```json
{
  "supplier_name": "agoda"
}
```

## Response

```json
{
  "supplier_name": "agoda",
  "total_hotel_id": 455,
  "hotel_id": [1, 2, 3, 4]
}
```

## How it works

### Step 1: Get Hotel IDs from Supplier Folder

- Reads JSON files from: `D:\content_for_hotel_json\cdn_row_collection\{supplier_name}\`
- Extracts hotel IDs from filenames (e.g., `1.json` → `1`, `2.json` → `2`)
- Creates list `a = [1, 2, 3, ...]`

### Step 2: Get Hotel IDs from Database

- Uses the existing utility function `create_txt_file_follow_a_supplier.py`
- Queries the database for existing hotel IDs for the supplier
- Creates list `b = [2, 4, 5, ...]`

### Step 3: Calculate Difference

- Computes `c = a - b` (hotel IDs in folder but not in database)
- Returns the unmapped hotel IDs

## Example Usage

### Using curl:

```bash
curl -X POST "http://localhost:8000/v1.0/ml_mapping/get_not_mapped_hotel_id_list" \
     -H "Content-Type: application/json" \
     -d '{"supplier_name": "agoda"}'
```

### Using Python requests:

```python
import requests

url = "http://localhost:8000/v1.0/ml_mapping/get_not_mapped_hotel_id_list"
payload = {"supplier_name": "agoda"}

response = requests.post(url, json=payload)
result = response.json()

print(f"Total unmapped hotels: {result['total_hotel_id']}")
print(f"Hotel IDs: {result['hotel_id']}")
```

## Configuration

### Folder Path

The base directory for supplier JSON files is configured in the code:

```python
RAW_BASE_DIR = r"D:\content_for_hotel_json\cdn_row_collection"
```

### Database Configuration

Database connection is configured via environment variables in `.env`:

- `DB_HOST`
- `DB_USER`
- `DB_PASSWORD`
- `DB_NAME`

## Error Handling

The endpoint handles various error scenarios:

- Supplier folder not found
- Database connection issues
- Invalid supplier names
- File system access errors

## Supported Suppliers

Currently supported suppliers (as defined in `provider_mappings`):

- agoda
- hotelbeds
- ean
- mgholiday
- restel
- stuba
- hyperguestdirect
- tbohotel
- goglobal
- ratehawkhotel
- adivahahotel
- grnconnect
- juniper
- mikihotel
- paximumhotel
- adonishotel
- w2mhotel
- oryxhotel
- dotw
- hotelston
- letsflyhotel
- illusionshotel
- innstanttravel
- roomerang

## Testing

Run the test script to verify the endpoint:

```bash
python test_not_mapped_endpoint.py
```

Make sure your FastAPI server is running before testing.

## Response Format (Both Endpoints)

```json
{
  "supplier_name": "agoda",
  "total_hotel_id": 25457,
  "hotel_id": [1, 2, 3, 4]
}
```

## Endpoint Differences

### get_not_mapped_hotel_id_list

- **Logic**: folder_ids - database_ids
- **Purpose**: Find hotels that need to be mapped
- **Use case**: Hotels exist in JSON files but not in database
- **Expected result**: ~25,457 hotel IDs for agoda

### get_not_update_content_hotel_id_list

- **Logic**: database_ids - folder_ids
- **Purpose**: Find hotels that need content updates
- **Use case**: Hotels exist in database but no JSON content files
- **Expected result**: ~344,755 hotel IDs for agoda

## Example Usage

### Test both endpoints:

```python
import requests

base_url = "http://127.0.0.1:8002/v1.0/ml_mapping"
payload = {"supplier_name": "agoda"}
headers = {'Content-Type': 'application/json'}

# Test endpoint 1: Hotels needing mapping
response1 = requests.post(f"{base_url}/get_not_mapped_hotel_id_list",
                         headers=headers, json=payload)
print("Need mapping:", response1.json()['total_hotel_id'])

# Test endpoint 2: Hotels needing content update
response2 = requests.post(f"{base_url}/get_not_update_content_hotel_id_list",
                         headers=headers, json=payload)
print("Need content update:", response2.json()['total_hotel_id'])
```
