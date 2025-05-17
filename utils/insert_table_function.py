import os
import json
import requests
from sqlalchemy import create_engine, MetaData, Table, select
from sqlalchemy.orm import sessionmaker
from dotenv import load_dotenv

def get_auth_token():
    url = "http://127.0.0.1:8000/v1.0/auth/token/"
    payload = 'username=ursamroko&password=ursamroko123'
    headers = {'Content-Type': 'application/x-www-form-urlencoded'}
    r = requests.post(url, headers=headers, data=payload)
    r.raise_for_status()
    return r.json()['access_token']

load_dotenv()
db_uri = f"mysql+pymysql://{os.getenv('DB_USER')}:{os.getenv('DB_PASSWORD')}@{os.getenv('DB_HOST')}/{os.getenv('DB_NAME')}"
engine = create_engine(db_uri)
Session = sessionmaker(bind=engine)

metadata = MetaData()
hotel_table = Table('hotel_itt_test', metadata, autoload_with=engine)


token = get_auth_token()
headers = {
    'Content-Type': 'application/json',
    'Authorization': f'Bearer {token}'
}
url = "http://127.0.0.1:8000/v1.0/hotels/mapping/input_hotel_all_details"  # no trailing slash

def parse_contacts(data_str, contact_type):
    if not data_str:
        return []
    return [{"contact_type": contact_type, "value": v.strip()} 
            for v in data_str.split(",") if v.strip()]

with engine.connect() as conn:
    for row in conn.execute(select(hotel_table)):
        payload = {
            "ittid": row.ittid,
            "name": row.Name,
            "latitude": str(row.Latitude) if row.Latitude is not None else "",
              "longitude": str(row.Longitude) if row.Longitude is not None else "",
              "address_line1": str(row.AddressLine1) if row.AddressLine1 else "",
              "address_line2": str(row.AddressLine2) if row.AddressLine2 else "",
              "postal_code": str(row.PostalCode) if row.PostalCode else "",
              "rating": str(row.Rating) if row.Rating is not None else "",
              "property_type": str(row.PropertyType) if row.PropertyType else "",
              "map_status": "pending",
              "content_update_status": str(row.contentUpdateStatus) if row.contentUpdateStatus else "",
              
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

        response = requests.post(url, headers=headers, json=payload)
        if response.status_code >= 200 and response.status_code < 300:
            print(f"[OK]   {row.ittid} -> {response.status_code}")
        else:
            print(f"[ERR]  {row.ittid} -> {response.status_code}")
            # This will show you exactly which field is wrong or missing:
            try:
                print(json.dumps(response.json(), indent=2))
            except ValueError:
                print(response.text)
