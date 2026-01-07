import os
import json
import requests
from sqlalchemy import create_engine, MetaData, Table, select, text
from dotenv import load_dotenv
from concurrent.futures import ThreadPoolExecutor, as_completed

# Load environment variables
load_dotenv()

# --- CONFIGURATION --- #
def get_database_engine():
    db_uri = (
        f"mysql+pymysql://{os.getenv('DB_USER')}:"
        f"{os.getenv('DB_PASSWORD')}@"
        f"{os.getenv('DB_HOST')}/"
        f"{os.getenv('DB_NAME')}"
    )
    return create_engine(db_uri, echo=False)

# --- AUTHENTICATION & API HELPERS --- #
def get_auth_token():
    url = "http://127.0.0.1:8028/v1.0/auth/token/"
    payload = {'username': 'ursamroko', 'password': 'ursamroko123'}
    r = requests.post(url, data=payload)
    r.raise_for_status()
    return r.json().get('access_token')


def get_headers():
    token = get_auth_token()
    return {
        'Content-Type': 'application/json',
        'Authorization': f'Bearer {token}'
    }

# --- EXISTENCE CHECK --- #
def check_if_ittid_exists(ittid, headers):
    url = f"http://127.0.0.1:8028/v1.0/content/get-hotel-with-ittid/{ittid}"
    r = requests.get(url, headers=headers)
    return (r.status_code == 200) and bool(r.json().get("hotel"))

# --- PAYLOAD BUILDER --- #
def parse_contacts(data_str, contact_type):
    if not data_str:
        return []
    return [
        {"contact_type": contact_type, "value": v.strip()}
        for v in data_str.split(",") if v.strip()
    ]


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
        "content_update_status": "NewAdd",
        "locations": [{
            "city_name": str(row.CityName) if row.CityName else "",
            "state_name": str(row.StateName) if row.StateName else "",
            "state_code": str(row.StateCode) if row.StateCode else "",
            "country_name": str(row.CountryName) if row.CountryName else "",
            "country_code": str(row.CountryCode) if row.CountryCode else "",
            "master_city_name": str(row.MasterCityName) if row.MasterCityName else str(row.CityName or ""),
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
        "contacts": (
            parse_contacts(row.Phones, "phone") +
            parse_contacts(row.Emails, "email") +
            parse_contacts(row.Fax, "fax") +
            parse_contacts(row.Website, "website")
        ),
        "chains": [{
            "chain_name": str(row.ChainName) if row.ChainName else "",
            "chain_code": str(row.ChainCode) if row.ChainCode else "",
            "brand_name": str(row.BrandName) if row.BrandName else ""
        }]
    }

# --- WORKER --- #
def process_hotel(row, headers, url):
    if check_if_ittid_exists(row.ittid, headers):
        print(f"[SKIP] {row.ittid} already exists")
        return

    payload = build_payload(row)
    try:
        resp = requests.post(url, headers=headers, json=payload)
        if 200 <= resp.status_code < 300:
            print(f"[OK]   {row.ittid} -> {resp.status_code}")
        else:
            print(f"[ERR]  {row.ittid} -> {resp.status_code}")
            print(resp.text)
    except Exception as e:
        print(f"[EXCEPTION] {row.ittid} -> {e}")


def upload_single_hotel(ittid):
    engine = get_database_engine()
    headers = get_headers()
    api_url = "http://127.0.0.1:8028/v1.0/hotels/input_hotel_all_details"

    metadata = MetaData()
    hotel_table = Table("global_hotel_mapping_copy_2", metadata, autoload_with=engine)

    with engine.connect() as conn:
        result = conn.execute(
            select(hotel_table).where(hotel_table.c.ittid == str(ittid)).limit(1)
        )

        row = result.fetchone()

        if not row:
            print(f"[NOT FOUND] Hotel Id {ittid} not found")
            return

        print(f"[PROCESSING] Hotel Id {ittid}, ITTID {row.ittid}")

        process_hotel(row, headers, api_url)


if __name__ == "__main__":
    upload_single_hotel(11688458)
