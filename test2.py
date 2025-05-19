now i need to add update hotel info section,

where end point is like

http://127.0.0.1:8000/v1.0/content/update_info?limit=50&last_update_data=2025-04-10

then here  get all new and update data show, like

{"ittid": "87748639",
"provider_name" : "itt",
"provider_id:  "42345",
"system_type" "a",





now for above "hotel_test_mapping" table information inset into my another database using API endpoint. my API information is



import requests

import json



url = "http://127.0.0.1:8000/v1.0/hotels/mapping/add_provider_all_details_with_ittid/"



payload = json.dumps({

  "ittid": "Pf546fs345",

  "provider_name": "Adoda",

  "provider_id": "654998",

  "system_type": "g",

  "vervotech_id": "651",

  "giata_code": "5655"

})

headers = {

  'Content-Type': 'application/json',

  'Authorization': 'Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOiJyb21hbiIsImV4cCI6MTc0NzU5NDEyNX0.I8LFMvM7ZtvwuEN0eQShAJu9o5IoO7CvPs29hTjuUdc'

}



response = requests.request("POST", url, headers=headers, data=payload)



print(response.text)





inset all data in database. my database credential is

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





this is basic information that is need to help you.





i give you an example.



like



if get 

'ittid':'87748639'

"VervotechId": "16188944"

`GiataCode`:"1149042"

`hotelbeds`:123

`hotelbeds_a`:343



insert like

{

    "ittid": "ittid",

    "provider_name":VervotechId,

    "provider_id": 123,

    "system_type": g, 

    "vervotech_id": VervotechId

    "giata_code": GiataCode

   }

{

    "ittid": "ittid",

    "provider_name":VervotechId,

    "provider_id": 343,

    "system_type": c, 

    "vervotech_id": VervotechId

    "giata_code": GiataCode

   }

hotelbeds= "system_type": g,

hotelbeds_a  =  "system_type": b,

hotelbeds_b=  "system_type": c,

hotelbeds_c=  "system_type": d,

hotelbeds_d=  "system_type": e,

hotelbeds_e=  "system_type": f,

ean= "system_type": g,

ean_a=  "system_type": b,

ean_b=  "system_type": c,

ean_c=  "system_type": d,

ean_d=  "system_type": e,

ean_e=  "system_type": f,


