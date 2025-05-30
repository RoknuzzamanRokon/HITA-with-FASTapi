import os
import json
import requests
from sqlalchemy import create_engine, MetaData, Table, select
from sqlalchemy.orm import sessionmaker
from dotenv import load_dotenv
from concurrent.futures import ThreadPoolExecutor, as_completed

# Load environment variables
load_dotenv()

# --- CONFIGURATION --- #
def get_database_engine():
    db_uri = f"mysql+pymysql://{os.getenv('DB_USER')}:{os.getenv('DB_PASSWORD')}@{os.getenv('DB_HOST')}/{os.getenv('DB_NAME')}"
    return create_engine(db_uri)

def get_headers():
    token = get_auth_token()
    return {
        'Content-Type': 'application/json',
        'Authorization': f'Bearer {token}'
    }

# --- AUTHENTICATION --- #
def get_auth_token():
    url = "http://127.0.0.1:8000/v1.0/auth/token/"
    payload = 'username=ursamroko&password=ursamroko123'
    headers = {'Content-Type': 'application/x-www-form-urlencoded'}
    r = requests.post(url, headers=headers, data=payload)
    r.raise_for_status()
    return r.json()['access_token']

# --- CHECK EXISTENCE --- #
def check_if_ittid_exists(ittid, headers):
    check_url = f"http://127.0.0.1:8000/v1.0/content/get_hotel_with_ittid/{ittid}"
    r = requests.get(check_url, headers=headers)
    if r.status_code == 200:
        return r.json().get("hotel", False)
    return False

# --- HELPER FUNCTION --- #
def parse_contacts(data_str, contact_type):
    if not data_str:
        return []
    return [{"contact_type": contact_type, "value": v.strip()}
            for v in data_str.split(",") if v.strip()]

def build_payload(row):
    return {
        "ittid": row.ittid,
        "name": row.Name,
        "latitude": str(row.Latitude) if row.Latitude is not None else "",
        "longitude": str(row.Longitude) if row.Longitude is not None else "",
        "address_line1": str(row.AddressLine1) if row.AddressLine1 else "",
        "address_line2": str(row.AddressLine2) if row.AddressLine2 else "",
        "postal_code": str(row.PostalCode) if row.PostalCode else "",
        "rating": str(row.Rating) if row.Rating is not None else "",
        "property_type": str(row.PropertyType) if row.PropertyType else "",
        "primary_photo": str(row.PrimaryPhoto) if row.PrimaryPhoto else "",
        "map_status": "pending",
        "content_update_status": "Done",
        "locations": [{
            "city_name": str(row.CityName) if row.CityName else "",
            "state_name": str(row.StateName) if row.StateName else "",
            "state_code": str(row.StateCode) if row.StateCode else "",
            "country_name": str(row.CountryName) if row.CountryName else "",
            "country_code": str(row.CountryCode) if row.CountryCode else "",
            "master_city_name": str(row.MasterCityName if row.MasterCityName else row.CityName) if (row.MasterCityName or row.CityName) else "",
            "city_code": str(row.CityCode) if row.CityCode else "",
            "city_location_id": str(row.CityLocationId) if row.CityLocationId is not None else ""
        }],
        "provider_mappings": [{
            "provider_name": "itt",
            "provider_id": row.ittid,
            "system_type": 'a',
            "vervotech_id": str(row.VervotechId) if row.VervotechId else "",
            "giata_code": str(row.GiataCode) if row.GiataCode else ""
        }],
        "contacts": parse_contacts(row.Phones, "phone") + parse_contacts(row.Emails, "email"),
        "chains": [{
            "chain_name": str(row.ChainName) if row.ChainName else "",
            "chain_code": str(row.ChainCode) if row.ChainCode else "",
            "brand_name": str(row.BrandName) if row.BrandName else ""
        }]
    }

# --- TASK FUNCTION --- #
def process_hotel(row, headers, url):
    if check_if_ittid_exists(row.ittid, headers):
        print(f"[SKIP] {row.ittid} already exists")
        return

    payload = build_payload(row)
    try:
        response = requests.post(url, headers=headers, json=payload)
        if 200 <= response.status_code < 300:
            print(f"[OK]   {row.ittid} -> {response.status_code}")
        else:
            print(f"[ERR]  {row.ittid} -> {response.status_code}")
            try:
                print(json.dumps(response.json(), indent=2))
            except ValueError:
                print(response.text)
    except Exception as e:
        print(f"[EXCEPTION] {row.ittid} -> {e}")

# --- MAIN PROCESS --- #
def upload_hotels():
    engine = get_database_engine()
    headers = get_headers()
    url = "http://127.0.0.1:8000/v1.0/hotels/mapping/input_hotel_all_details"

    metadata = MetaData()
    hotel_table = Table('hotel_itt_test', metadata, autoload_with=engine)

    # Load all rows before starting threads
    with engine.connect() as conn:
        rows = list(conn.execute(select(hotel_table)))

    # Use ThreadPoolExecutor for concurrency
    with ThreadPoolExecutor(max_workers=30) as executor:
        futures = [executor.submit(process_hotel, row, headers, url) for row in rows]
        for future in as_completed(futures):
            pass  # Optional: handle future.result() if needed

# --- EXECUTION --- #
if __name__ == "__main__":
    upload_hotels()
