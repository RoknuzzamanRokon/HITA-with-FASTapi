# routes/hotel_raw.py
import logging
import os
import time
import hashlib
import json
from typing import List, Union, Dict, Any
from dotenv import load_dotenv
from io import StringIO
import pandas as pd

import requests
import xmltodict
import urllib.parse

import uuid
import base64
import datetime
import random
import xml.etree.ElementTree as ET


from fastapi import HTTPException, APIRouter, status, Depends, Request
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session
from typing import Annotated

# import your path constants
from routes.path import RAW_BASE_DIR
from database import get_db
from routes.auth import get_current_user
import models
from security.audit_logging import AuditLogger, ActivityType, SecurityLevel

load_dotenv()

organization = "NMC-SAUDI"
user_id = os.getenv("AMADEUSE_USER_ID")
password = "psC6Gh=q3qPb"
office_id = "DMMS228XU"
duty_code = "SU"
requestor_type = "U"
soap_action = "http://webservices.amadeus.com/OTA_HotelDescriptiveInfoRQ_07.1_1A2007A"
wsap = "1ASIWAAAAAK"
url = os.getenv("AMADEUSE_LIVE_URL")


router = APIRouter(
    prefix="/v1.0/hotel",
    tags=["Raw Hotel Content"],
    responses={404: {"description": "Not found"}},
)


class ConvertRequest(BaseModel):
    supplier_code: str
    # Accept either a single id or list of ids (client sends "hotel_id": ["1622759", ...])
    hotel_id: Union[str, List[str]] = Field(
        ..., description="String or list of hotel ids"
    )


def _ensure_dir(path: str) -> None:
    os.makedirs(path, exist_ok=True)


def generate_uuid():
    return str(uuid.uuid4())


def get_timestamp():
    now = datetime.datetime.utcnow()
    micro = f"{now.microsecond // 1000:03d}"
    return now.strftime("%Y-%m-%dT%H:%M:%S") + micro + "Z"


def generate_nonce():
    return base64.b64encode(str(random.randint(10000000, 99999999)).encode()).decode()


def generate_password_digest(nonce_b64, created, password):
    nonce_bytes = base64.b64decode(nonce_b64)
    sha1_password = hashlib.sha1(password.encode("utf-8")).digest()
    digest = hashlib.sha1(nonce_bytes + created.encode() + sha1_password).digest()
    return base64.b64encode(digest).decode()


def remove_namespace(obj):
    if isinstance(obj, dict):
        return {
            k.split("}", 1)[-1] if "}" in k else k: remove_namespace(v)
            for k, v in obj.items()
        }
    elif isinstance(obj, list):
        return [remove_namespace(item) for item in obj]
    return obj


def xml_to_dict(element):
    result = {}

    # Process element attributes
    if element.attrib:
        result.update(element.attrib)

    # Process element text
    text = (element.text or "").strip()
    if text:
        if result:
            result["text"] = text
        else:
            result = text

    # Process children
    for child in element:
        child_data = xml_to_dict(child)
        child_tag = child.tag

        if child_tag in result:
            if isinstance(result[child_tag], list):
                result[child_tag].append(child_data)
            else:
                result[child_tag] = [result[child_tag], child_data]
        else:
            result[child_tag] = child_data

    return result


def save_json_file(
    dir_path: str, hotel_id: str, json_text: Union[str, dict, list]
) -> bool:

    try:
        _ensure_dir(dir_path)
        file_path = os.path.join(dir_path, f"{hotel_id}.json")

        # Ensure we have a string to write
        if isinstance(json_text, (dict, list)):
            content = json.dumps(json_text, ensure_ascii=False)
        elif json_text is None:
            content = "{}"
        else:
            # assume string (maybe JSON already)
            content = str(json_text)

        with open(file_path, "w", encoding="utf-8") as f:
            f.write(content)

        logging.info(f"Saved raw JSON for hotel {hotel_id} to {file_path}")
        return True
    except Exception:
        logging.exception(f"Failed to save JSON for hotel {hotel_id}")
        return False


def fetch_hotelbeds_raw(hotel_id: str) -> Union[dict, None]:
    api_key = os.getenv("HOTELBEDS_API_KEY")
    api_secret = os.getenv("HOTELBEDS_API_SECRET")

    if not api_key or not api_secret:
        logging.error("Hotelbeds API credentials are missing in environment variables.")
        return None

    timestamp = str(int(time.time()))
    signature_data = f"{api_key}{api_secret}{timestamp}"
    signature = hashlib.sha256(signature_data.encode("utf-8")).hexdigest()

    url = f"https://api.hotelbeds.com/hotel-content-api/1.0/hotels/{hotel_id}/details?language=ENG&useSecondaryLanguage=False"

    headers = {
        "Api-key": api_key,
        "X-Signature": signature,
        "Accept-Encoding": "gzip",
        "Content-Type": "application/json",
    }

    try:
        resp = requests.get(url, headers=headers, timeout=30)
        if resp.status_code == 200:
            try:
                data = resp.json()
                # Check if the response contains actual hotel content
                if "hotel" not in data and "hotels" not in data:
                    logging.warning(
                        f"No hotel data found for Hotelbeds hotel {hotel_id}"
                    )
                    return {"status": "no_data_found"}
                return data
            except Exception:
                logging.exception(
                    f"Failed to parse JSON for Hotelbeds hotel {hotel_id}"
                )
                return None
        else:
            logging.error(
                f"Hotelbeds fetch failed for {hotel_id}: {resp.status_code} - {resp.text}"
            )
            return None
    except Exception:
        logging.exception(f"Exception while fetching Hotelbeds data for {hotel_id}")
        return None


def fetch_agoda_raw(hotel_id: str) -> Union[dict, None]:
    api_key = os.getenv("AGODA_API_KEY")
    site_id = os.getenv("AGODA_SITEID")

    if not api_key or not site_id:
        logging.error(
            "Agoda credentials (AGODA_API_KEY or AGODA_SITEID) missing in environment."
        )
        return None

    url = (
        f"http://affiliatefeed.agoda.com/datafeeds/feed/getfeed?feed_id=19"
        f"&apikey={api_key}&site_id={site_id}&mhotel_id={hotel_id}"
    )

    try:
        response = requests.get(url, timeout=20)
        if response.status_code == 200 and response.content:
            try:
                data_dict = xmltodict.parse(response.content)
                hotel_feed = data_dict.get("Hotel_feed_full", {})

                # Only check relevant fields, ignore namespace attributes
                content_fields = [
                    "addresses",
                    "hotel_descriptions",
                    "facilities",
                    "pictures",
                    "roomtypes",
                ]

                if all(hotel_feed.get(f) in (None, {}, []) for f in content_fields):
                    logging.warning(
                        f"No hotel data found in Agoda response for {hotel_id}"
                    )
                    return {"status": "no_data_found"}

                return data_dict
            except Exception:
                logging.exception(f"Failed to parse XML for Agoda hotel {hotel_id}")
                return None
        else:
            logging.error(
                f"Failed to fetch Agoda data for hotel {hotel_id}. Status code: {response.status_code}"
            )
            return None
    except Exception:
        logging.exception(f"Error fetching data for Agoda hotel {hotel_id}")
        return None


def fetch_tbohotel_raw(hotel_id: str) -> Union[dict, None]:
    TBO_AUTHENTICATION = os.getenv("TBO_AUTHENTICATION")
    url = "https://api.tbotechnology.in/TBOHolidays_HotelAPI/Hoteldetails"
    payload = {"Hotelcodes": hotel_id, "Language": "en"}
    headers = {"Authorization": TBO_AUTHENTICATION, "Content-Type": "application/json"}

    try:
        response = requests.post(url, headers=headers, json=payload, timeout=10)
        response.raise_for_status()
        data = response.json()
        status_code = data.get("Status", {}).get("Code", -1)
        if status_code == 200:
            return data
        else:
            error_desc = data.get("Status", {}).get(
                "Description", "No description provided"
            )
            print(f"API Error for hotel {hotel_id}: {error_desc} (Code: {status_code})")
            return None
    except requests.exceptions.HTTPError as http_err:
        print(f"HTTP error for hotel {hotel_id}: {http_err}")
    except json.JSONDecodeError as json_err:
        print(f"Failed to decode JSON for hotel {hotel_id}: {json_err}")
    except Exception as e:
        print(f"General error fetching hotel {hotel_id}: {e}")
    return None


def fetch_ean_raw(hotel_id: str) -> Union[dict, None]:
    EAN_API_KEY = os.getenv("EAN_API_KEY")
    EAN_API_SECRET = os.getenv("EAN_API_SECRET")
    BASE_URL = os.getenv("EAN_BASE_URL")

    if not EAN_API_KEY or not EAN_API_SECRET or not BASE_URL:
        logging.error(
            "EAN API credentials or BASE_URL are missing in environment variables."
        )
        return None

    timestamp = str(int(time.time()))
    signature_data = f"{EAN_API_KEY}{EAN_API_SECRET}{timestamp}"
    signature = hashlib.sha512(signature_data.encode("utf-8")).hexdigest()

    url = f"{BASE_URL}/v3/properties/content?language=en-US&supply_source=expedia&property_id={hotel_id}"

    headers = {
        "Accept": "application/json",
        "Authorization": f"EAN APIKey={EAN_API_KEY},Signature={signature},timestamp={timestamp}",
        "Content-Type": "application/json",
    }

    try:
        resp = requests.get(url, headers=headers, timeout=30)
        print(resp.text)
        if resp.status_code == 200:
            try:
                data = resp.json()

                # Case 1: Empty dict "{}"
                if not data or data == {}:
                    logging.warning(f"No hotel data found for EAN hotel {hotel_id}")
                    return {"status": "no_data_found"}

                return data

            except Exception:
                logging.exception(f"Failed to parse JSON for EAN hotel {hotel_id}")
                return None
        else:
            logging.error(f"EAN fetch failed for {hotel_id}: {resp.status_code}")
            return None

    except Exception:
        logging.exception(f"Exception while fetching EAN data for {hotel_id}")
        return None


def fetch_grnconnect_raw(hotel_id: str) -> Union[dict, None]:
    """
    Fetch hotel, country, city, and image info for the given GRNConnect hotel_id.
    Saves JSON to BASE_PATH/hotel_id.json and returns the combined dict.
    """
    # API key and headers
    API_KEY = os.getenv("GRNCONNECT_API_KEY")
    HEADERS = {
        "Content-Type": "application/json",
        "Accept": "application/json",
        "Accept-Encoding": "application/gzip",
        "api-key": API_KEY,
    }
    CITY_HEADERS = {
        "Content-Type": "application/json",
        "Accept": "application/json",
        "API-key": API_KEY,
    }

    try:
        # 1) hotel info
        hotel_url = f"https://api-sandbox.grnconnect.com/api/v3/hotels?hcode={hotel_id}&version=2.0"
        resp = requests.get(hotel_url, headers=HEADERS, timeout=30)
        resp.raise_for_status()
        hotel_payload = resp.json()
        hotel = hotel_payload["hotels"][0]

        # 2) country info
        country_code = hotel.get("country")
        country = {}
        if country_code:
            country_url = (
                f"https://api-sandbox.grnconnect.com/api/v3/countries/{country_code}"
            )
            resp = requests.get(country_url, headers=HEADERS, timeout=30)
            resp.raise_for_status()
            country = resp.json().get("country", {})

        # 3) city info
        city_code = hotel.get("city_code")
        city = {}
        if city_code:
            city_url = f"https://api-sandbox.grnconnect.com/api/v3/cities/{city_code}?version=2.0"
            resp = requests.get(city_url, headers=CITY_HEADERS, timeout=30)
            resp.raise_for_status()
            city = resp.json().get("city", {})

        # 4) images
        images_url = f"https://api-sandbox.grnconnect.com/api/v3/hotels/{hotel_id}/images?version=2.0"
        resp = requests.get(images_url, headers=HEADERS, timeout=30)
        resp.raise_for_status()
        images = resp.json().get("images", {}).get("regular", [])

        # combine into single dict
        data = {
            "hotel_code": hotel_id,
            "hotel": hotel,
            "country": country,
            "city": city,
            "images": images,
        }
        return data

    except Exception:
        logging.exception(f"Exception while fetching GRNConnect data for {hotel_id}")
        return {"status": "no_data_found"}


def fetch_restel_raw(hotel_id: str) -> Union[dict, None]:
    restel_cookie = os.getenv("RESTEL_COOKIE")
    xml_data = f"""<?xml version="1.0" encoding="UTF-8"?>
    <peticion>
    <tipo>15</tipo>
    <nombre>Servicio de información de hotel</nombre>
    <agencia>Agencia prueba</agencia>
    <parametros>
        <codigo>{hotel_id}</codigo>
        <idioma>2</idioma>
    </parametros>
    </peticion>"""

    encoded_xml = urllib.parse.quote(xml_data)
    url = f"http://xml.hotelresb2b.com/xml/listen_xml.jsp?codigousu=ZVYE&clausu=xml514142&afiliacio=RS&secacc=151003&xml={encoded_xml}"

    headers = {"Cookie": f"{restel_cookie}"}

    try:
        response = requests.get(url, headers=headers, timeout=10)
        if response.status_code == 200:
            try:
                data = xmltodict.parse(response.text)

                # Check if response contains an error message
                if (
                    "respuesta" in data
                    and "parametros" in data["respuesta"]
                    and "error" in data["respuesta"]["parametros"]
                ):
                    return {"status": "no_data_found"}

                return data
            except Exception:
                logging.exception(f"Exception while parsing Restel data for {hotel_id}")
                return {"status": "no_data_found"}
        else:
            print(
                f"Failed to fetch data for hotel ID {hotel_id}. "
                f"Status code: {response.status_code}, Response: {response.text}"
            )
            return None
    except requests.RequestException as e:
        logging.exception(f"Request error for hotel ID {hotel_id}: {e}")
        return None


def authentication_paximum():
    paximum_token = os.getenv("PAXIMUM_TOKEN")
    paximum_agency = os.getenv("PAXIMUM_AGENCY")
    paximum_user = os.getenv("PAXIMUM_USER")
    paximum_password = os.getenv("PAXIMUM_PASSWORD")

    url = "http://service.stage.paximum.com/v2/api/authenticationservice/login"

    payload = json.dumps(
        {"Agency": paximum_agency, "User": paximum_user, "Password": paximum_password}
    )

    headers = {"Content-Type": "application/json", "Authorization": paximum_token}

    response = requests.request("POST", url, headers=headers, data=payload)

    if response.status_code == 200:
        try:
            df = pd.read_json(StringIO(response.text))
            token = df.get("body").get("token")
            return token
        except Exception as e:
            print("Error parsing token:", e)
            return None
    else:
        print(
            f"Failed to authenticate. Status code: {response.status_code}, Response: {response.text}"
        )
        return None


def fetch_paximum_raw(hotel_id: str) -> Union[dict, None]:
    token = authentication_paximum()
    if not token:
        print(f"Authentication failed for hotel ID {hotel_id}.")
        return None

    url = "http://service.stage.paximum.com/v2/api/productservice/getproductInfo"

    payload = {
        "productType": 2,
        "ownerProvider": 2,
        "product": hotel_id,
        "culture": "en-US",
    }

    headers = {"Content-Type": "application/json", "Authorization": f"Bearer {token}"}

    try:
        response = requests.post(url, headers=headers, json=payload, timeout=10)
        if response.status_code == 200:
            try:
                data = response.json()

                # Check for failure or "Hotel room detail not found"
                if "header" in data and (
                    not data["header"].get("success", True)
                    or any(
                        msg.get("code") == "RoomDetailNotFound"
                        for msg in data["header"].get("messages", [])
                    )
                ):
                    return {"status": "no_data_found"}

                return data
            except Exception as e:
                print(f"Error parsing JSON for hotel ID {hotel_id}: {e}")
                return {"status": "no_data_found"}
        else:
            print(
                f"Failed to fetch data for hotel ID {hotel_id}. "
                f"Status code: {response.status_code}, Response: {response.text}"
            )
            return None
    except requests.RequestException as e:
        print(f"Request failed for hotel ID {hotel_id}: {e}")
        return None


def fetch_juniperhotel_raw(hotel_id: str) -> Union[dict, None]:
    JUNIPER_USER = os.getenv("JUNIPER_EMAIL")
    JUNIPER_PASSWORD = os.getenv("JUNIPER_PASS")

    url = "https://xml-uat.bookingengine.es/WebService/jp/operations/staticdatatransactions.asmx"

    # # For live environment
    # JUNIPER_USER = os.getenv("JUNIPER_USER")
    # JUNIPER_PASSWORD = os.getenv("JUNIPER_PASSWORD")
    ## This url for live url
    # url = "http://juniper-xmlcredit.roibos.com/webservice/jp/operations/staticdatatransactions.asmx"

    payload = f"""
    <soapenv:Envelope xmlns:soapenv="http://schemas.xmlsoap.org/soap/envelope/" xmlns="http://www.juniper.es/webservice/2007/">
        <soapenv:Header/>
        <soapenv:Body>
            <HotelContent>
                <HotelContentRQ Version="1" Language="en">
                    <Login Password="{JUNIPER_PASSWORD}" Email="{JUNIPER_USER}"/>
                    <HotelContentList>
                        <Hotel Code="{hotel_id}"/>
                    </HotelContentList>
                </HotelContentRQ>
            </HotelContent>
        </soapenv:Body>
    </soapenv:Envelope>
    """

    headers = {
        "Content-Type": "text/xml;charset=UTF-8",
        "SOAPAction": '"http://www.juniper.es/webservice/2007/HotelContent"',
    }

    try:
        response = requests.post(url, headers=headers, data=payload, timeout=20)

        if response.status_code == 200:
            try:
                data = xmltodict.parse(response.text)
                return data
            except Exception as e:
                print(f"Error parsing XML for hotel ID {hotel_id}: {e}")
                return None
        else:
            print(
                f"Failed to fetch data for hotel ID {hotel_id}. Status code: {response.status_code}, Response: {response.text}"
            )
            return None
    except requests.exceptions.RequestException as e:
        print(f"Request error for hotel ID {hotel_id}: {e}")
        return None


def fetch_oryxhotel_raw(hotel_id: str) -> Union[dict, None]:
    GILL_API_KEY = os.getenv("GILL_API_KEY")

    url = "https://api.giinfotech.ae/api/Hotel/HotelInfo"

    payload = json.dumps({"hotelCode": f"{hotel_id}"})

    headers = {"ApiKey": GILL_API_KEY, "Content-Type": "application/json"}
    try:
        response = requests.post(url, headers=headers, data=payload, timeout=20)

        if response.status_code == 200:
            try:
                data = response.json()
                return data
            except Exception as e:
                print(f"Error parsing for hotel ID {hotel_id}: {e}")
                return None
        else:
            print(
                f"Failed to fetch data for hotel ID {hotel_id}. Status code: {response.status_code}, Response: {response.text}"
            )
            return None
    except requests.exceptions.RequestException as e:
        print(f"Request error for hotel ID {hotel_id}: {e}")
        return None


def fetch_hyperguestdirect_raw(hotel_id: str) -> Union[dict, str, None]:
    hyperguestdirect_token = os.getenv("HYPERGUEST_TOKEN")
    url = f"https://hg-static.hyperguest.com/{hotel_id}/property-static.json"
    headers = {"Authorization": f"Bearer {hyperguestdirect_token}"}

    try:
        response = requests.get(url, headers=headers, timeout=10)
        if response.status_code == 200:
            data = response.json()
            if not data:
                return "no_data_found"
            return data
        else:
            print(f"Error: Received status code {response.status_code}")
            return None
    except requests.RequestException as e:
        print(f"Request failed: {e}")
        return None


def fetch_innstant_raw(hotel_id):
    INNESTENT_HOTEL_KEY = os.getenv("INNESTENT_HOTEL_KEY")
    INNESTENT_HOTEL_TOKEN = os.getenv("INNESTENT_HOTEL_TOKEN")
    url = f"https://static-data.innstant-servers.com/hotels/{hotel_id}"
    headers = {
        "aether-application-key": f"{INNESTENT_HOTEL_KEY}",
        "aether-access-token": f"{INNESTENT_HOTEL_TOKEN}",
    }
    try:
        response = requests.get(url, headers=headers, timeout=10)

        if response.status_code == 200:
            data = response.json()
            if not data:
                return "no_data_found"
            return data
        else:
            print(
                f"Failed to fetch data for hotel ID {hotel_id}. Status code: {response.status_code}"
            )
            return None
    except requests.RequestException as e:
        print(f"Request error for hotel ID {hotel_id}: {e}")
        return None


def fetch_ratehawk_raw(hotel_id: str) -> Union[Dict[str, Any], str, None]:
    RATEHAWK_AUTHORIZATION = os.getenv("RATEHAWK_AUTHORIZATION")

    url = "https://api.worldota.net/api/b2b/v3/hotel/info/"
    payload = json.dumps({"id": hotel_id, "language": "en"})
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Basic {RATEHAWK_AUTHORIZATION}",
    }

    try:
        response = requests.post(url, headers=headers, data=payload, timeout=15)
        response.raise_for_status()
        result = response.json()

        # Check if the API explicitly says hotel not found
        if result.get("status") == "error" and result.get("error") == "hotel_not_found":
            # print("Hotel not found")
            return "no_data_found"
        return result

    except Exception as e:
        print(f"Error fetching data for hotel {hotel_id}: {e}")
        return None


def fetch_amadeushotel_raw(hotel_id: str) -> Union[Dict[str, Any], str, None]:
    try:
        uuid_val = generate_uuid()
        timestamp = get_timestamp()
        nonce = generate_nonce()
        password_digest = generate_password_digest(nonce, timestamp, password)

        soap_payload = f"""<?xml version="1.0" encoding="UTF-8"?>
            <soap:Envelope xmlns:soap="http://schemas.xmlsoap.org/soap/envelope/">
            <soap:Header>
                <add:MessageID xmlns:add="http://www.w3.org/2005/08/addressing">{uuid_val}</add:MessageID>
                <add:Action xmlns:add="http://www.w3.org/2005/08/addressing">{soap_action}</add:Action>
                <add:To xmlns:add="http://www.w3.org/2005/08/addressing">{url}/{wsap}</add:To>
                <oas:Security xmlns:oas="http://docs.oasis-open.org/wss/2004/01/oasis-200401-wss-wssecurity-secext-1.0.xsd">
                <oas:UsernameToken xmlns:oas1="http://docs.oasis-open.org/wss/2004/01/oasis-200401-wss-wssecurity-utility-1.0.xsd" oas1:Id="UsernameToken-1">
                    <oas:Username>{user_id}</oas:Username>
                    <oas:Nonce EncodingType="http://docs.oasis-open.org/wss/2004/01/oasis-200401-wss-soap-message-security-1.0#Base64Binary">{nonce}</oas:Nonce>
                    <oas:Password Type="http://docs.oasis-open.org/wss/2004/01/oasis-200401-wss-username-token-profile-1.0#PasswordDigest">{password_digest}</oas:Password>
                    <oas1:Created>{timestamp}</oas1:Created>
                </oas:UsernameToken>
                </oas:Security>
                <AMA_SecurityHostedUser xmlns="http://xml.amadeus.com/2010/06/Security_v1">
                <UserID POS_Type="1" PseudoCityCode="{office_id}" AgentDutyCode="{duty_code}" RequestorType="{requestor_type}"/>
                </AMA_SecurityHostedUser>
            </soap:Header>
            <soap:Body>
                <OTA_HotelDescriptiveInfoRQ EchoToken="withParsing" Version="6.001" PrimaryLangID="en">
                <HotelDescriptiveInfos>
                    <HotelDescriptiveInfo HotelCode="{hotel_id}">
                    <HotelInfo SendData="true"/>
                    <FacilityInfo SendGuestRooms="true" SendMeetingRooms="true" SendRestaurants="true"/>
                    <Policies SendPolicies="true"/>
                    <AreaInfo SendAttractions="true" SendRefPoints="true" SendRecreations="true"/>
                    <AffiliationInfo SendAwards="true" SendLoyalPrograms="false"/>
                    <ContactInfo SendData="true"/>
                    <MultimediaObjects SendData="true"/>
                    <ContentInfos>
                        <ContentInfo Name="SecureMultimediaURLs"/>
                    </ContentInfos>
                    </HotelDescriptiveInfo>
                </HotelDescriptiveInfos>
                </OTA_HotelDescriptiveInfoRQ>
            </soap:Body>
            </soap:Envelope>"""

        headers = {
            "Content-Type": "text/xml",
            "SOAPAction": soap_action,
        }

        response = requests.post(
            url, data=soap_payload.strip(), headers=headers, timeout=60
        )

        if response.status_code == 200:
            root = ET.fromstring(response.content)
            response_dict = remove_namespace(xml_to_dict(root))

            if (
                response_dict.get("status") == "error"
                and response_dict.get("error") == "hotel_not_found"
            ):
                return "no_data_found"
            return response_dict
    except Exception as e:
        print(f"Exception {hotel_id}: {e}")
        return None


def fetch_kiwi_hotel_raw(hotel_id: str) -> Union[Dict[str, Any], str, None]:
    USER_NAME = os.getenv("KIWI_USER_NAME")
    PASSWORD = os.getenv("KIWI_USER_PASSWORD")
    url = "https://api.uat.kiwicollection.net/v1/propertyDetails"

    payload = f"""<?xml version="1.0" encoding="UTF-8"?>
    <PropertyDetailsRequest PropertyCode="{hotel_id}" DetailLevel="full" />"""

    headers = {
        "Accept-Encoding": "gzip,deflate",
        "Content-Type": "text/xml",
        "username": USER_NAME,
        "password": PASSWORD,
    }

    try:
        response = requests.post(url, headers=headers, data=payload, timeout=20)
        if response.status_code == 200:
            try:
                data_dict = xmltodict.parse(response.content)
                print(f"Data fetched successfully for {hotel_id}")
                return data_dict
            except Exception as parse_error:
                print(f"XML parse error for hotel {hotel_id}: {parse_error}")
                return None
        else:
            print(
                f"Failed to fetch data for {hotel_id}. Status code: {response.status_code}"
            )
            return None

    except Exception as e:
        print(f"Error fetching data for {hotel_id}: {e}")
        return None


@router.post("/pushhotel", status_code=status.HTTP_200_OK)
async def raw_data_push_our_system(
    request_body: ConvertRequest,
    request: Request,
    current_user: Annotated[models.User, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
):
    """Push hotel raw data to system (Super User and Admin User only)"""

    # 🔒 SECURITY CHECK: Only super users and admin users can push hotel data
    if current_user.role not in [
        models.UserRole.SUPER_USER,
        models.UserRole.ADMIN_USER,
    ]:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access denied. Only super users and admin users can push hotel data.",
        )

    # 📝 AUDIT LOG: Record hotel data push attempt
    audit_logger = AuditLogger(db)
    audit_logger.log_activity(
        activity_type=ActivityType.API_ACCESS,
        user_id=current_user.id,
        details={
            "endpoint": "/v1.0/hotel/pushhotel",
            "action": "push_hotel_data",
            "supplier_code": request_body.supplier_code,
            "hotel_ids": (
                request_body.hotel_id
                if isinstance(request_body.hotel_id, list)
                else [request_body.hotel_id]
            ),
        },
        request=request,
        security_level=SecurityLevel.HIGH,
        success=True,
    )
    # normalize supplier (accept Hotelbeds, HotelBeds, hotelbeds, etc.)
    supplier = request_body.supplier_code.strip().lower()

    # Normalize hotel ids to a list of strings
    if isinstance(request_body.hotel_id, list):
        hotel_ids = [str(h).strip() for h in request_body.hotel_id if h is not None]
    else:
        hotel_ids = [str(request_body.hotel_id).strip()]

    # Directory where we'll save raw JSONs: RAW_BASE_DIR/<supplier>/
    base_dir = os.path.join(RAW_BASE_DIR, supplier)
    _ensure_dir(base_dir)

    results: List[Dict[str, Any]] = []

    if supplier == "hotelbeds":
        for hid in hotel_ids:
            item_result: Dict[str, Any] = {"hotel_id": hid}
            raw_data = fetch_hotelbeds_raw(hid)
            if raw_data is None:
                item_result["status"] = "failed"
                item_result["reason"] = "fetch_failed_or_missing_credentials"
                logging.warning(f"Fetch failed for hotel {hid} (hotelbeds)")

            elif (
                isinstance(raw_data, dict) and raw_data.get("status") == "no_data_found"
            ):
                item_result["status"] = "failed"
                item_result["reason"] = "no_data_found"
                logging.info(f"No data found for hotel {hid} (hotelbeds)")

            else:
                saved = save_json_file(
                    base_dir, hid, json.dumps(raw_data, indent=2, ensure_ascii=False)
                )
                if saved:
                    item_result["status"] = "saved"
                    item_result["path"] = os.path.join(base_dir, f"{hid}.json")

                else:
                    item_result["status"] = "failed"
                    item_result["reason"] = "save_failed"
            results.append(item_result)

        return {"supplier": supplier, "results": results}

    elif supplier == "agoda":
        for hid in hotel_ids:
            item_result: dict = {"hotel_id": hid}
            raw_data = fetch_agoda_raw(hid)

            if raw_data is None:
                item_result["status"] = "failed"
                item_result["reason"] = "fetch_failed_or_missing_credentials"
                logging.warning(f"Fetch failed for hotel {hid} (agoda)")

            elif (
                isinstance(raw_data, dict) and raw_data.get("status") == "no_data_found"
            ):
                item_result["status"] = "failed"
                item_result["reason"] = "no_data_found"
                logging.info(f"No data found for hotel {hid} (agoda)")

            else:
                saved = save_json_file(
                    base_dir, hid, json.dumps(raw_data, indent=2, ensure_ascii=False)
                )
                if saved:
                    item_result["status"] = "saved"
                    item_result["path"] = os.path.join(base_dir, f"{hid}.json")
                else:
                    item_result["status"] = "failed"
                    item_result["reason"] = "save_failed"

            results.append(item_result)

        return {"supplier": supplier, "results": results}

    elif supplier == "tbohotel":
        for hid in hotel_ids:
            item_result: dict = {"hotel_id": hid}
            raw_data = fetch_tbohotel_raw(hid)

            if raw_data is None:
                item_result["status"] = "failed"
                item_result["reason"] = "fetch_failed_or_missing_credentials"
                logging.warning(f"Fetch failed for hotel {hid} (tbohotel)")

            elif (
                isinstance(raw_data, dict) and raw_data.get("status") == "no_data_found"
            ):
                item_result["status"] = "failed"
                item_result["reason"] = "no_data_found"
                logging.info(f"No data found for hotel {hid} (tbohotel)")

            else:
                saved = save_json_file(
                    base_dir, hid, json.dumps(raw_data, indent=2, ensure_ascii=False)
                )
                if saved:
                    item_result["status"] = "saved"
                    item_result["path"] = os.path.join(base_dir, f"{hid}.json")
                else:
                    item_result["status"] = "failed"
                    item_result["reason"] = "save_failed"

            results.append(item_result)

        return {"supplier": supplier, "results": results}

    elif supplier == "ean":
        for hid in hotel_ids:
            item_result: dict = {"hotel_id": hid}
            raw_data = fetch_ean_raw(hid)
            print(raw_data)

            if raw_data is None:
                item_result["status"] = "failed"
                item_result["reason"] = "fetch_failed_or_missing_credentials"
                logging.warning(f"Fetch failed for hotel {hid} (ean)")

            elif isinstance(raw_data, dict) and (
                raw_data.get("status") == "no_data_found"
                or raw_data.get("status") == "invalid_response"
            ):
                item_result["status"] = "failed"
                item_result["reason"] = raw_data.get("status")
                logging.info(f"No data found for hotel {hid} (ean)")

            else:
                # ✅ unwrap if supplier wraps like {"10000003": {...}}
                if (
                    isinstance(raw_data, dict)
                    and len(raw_data) == 1
                    and hid in raw_data
                ):
                    raw_data = raw_data[hid]

                saved = save_json_file(
                    base_dir, hid, json.dumps(raw_data, indent=2, ensure_ascii=False)
                )
                if saved:
                    item_result["status"] = "saved"
                    item_result["path"] = os.path.join(base_dir, f"{hid}.json")
                else:
                    item_result["status"] = "failed"
                    item_result["reason"] = "save_failed"

            results.append(item_result)

        return {"supplier": supplier, "results": results}

    elif supplier == "grnconnect":
        for hid in hotel_ids:
            item_result: dict = {"hotel_id": hid}
            raw_data = fetch_grnconnect_raw(hid)

            if raw_data is None:
                item_result["status"] = "failed"
                item_result["reason"] = "fetch_failed_or_missing_credentials"
                logging.warning(f"Fetch failed for hotel {hid} (grnconnect)")

            elif (
                isinstance(raw_data, dict) and raw_data.get("status") == "no_data_found"
            ):
                item_result["status"] = "failed"
                item_result["reason"] = "no_data_found"
                logging.info(f"No data found for hotel {hid} (grnconnect)")

            else:
                saved = save_json_file(
                    base_dir, hid, json.dumps(raw_data, indent=2, ensure_ascii=False)
                )
                if saved:
                    item_result["status"] = "saved"
                    item_result["path"] = os.path.join(base_dir, f"{hid}.json")
                else:
                    item_result["status"] = "failed"
                    item_result["reason"] = "save_failed"

            results.append(item_result)

        return {"supplier": supplier, "results": results}

    elif supplier == "restel":
        for hid in hotel_ids:
            item_result: dict = {"hotel_id": hid}
            raw_data = fetch_restel_raw(hid)

            if raw_data is None:
                item_result["status"] = "failed"
                item_result["reason"] = "fetch_failed_or_missing_credentials"
                logging.warning(f"Fetch failed for hotel {hid} (restel)")

            elif (
                isinstance(raw_data, dict) and raw_data.get("status") == "no_data_found"
            ):
                item_result["status"] = "failed"
                item_result["reason"] = "no_data_found"
                logging.info(f"No data found for hotel {hid} (restel)")

            else:
                saved = save_json_file(
                    base_dir, hid, json.dumps(raw_data, indent=2, ensure_ascii=False)
                )
                if saved:
                    item_result["status"] = "saved"
                    item_result["path"] = os.path.join(base_dir, f"{hid}.json")
                else:
                    item_result["status"] = "failed"
                    item_result["reason"] = "save_failed"

            results.append(item_result)

        return {"supplier": supplier, "results": results}

    elif supplier == "paximum":
        for hid in hotel_ids:
            item_result: dict = {"hotel_id": hid}
            raw_data = fetch_paximum_raw(hid)

            if raw_data is None:
                item_result["status"] = "failed"
                item_result["reason"] = "fetch_failed_or_missing_credentials"
                logging.warning(f"Fetch failed for hotel {hid} (paximum)")

            elif (
                isinstance(raw_data, dict) and raw_data.get("status") == "no_data_found"
            ):
                item_result["status"] = "failed"
                item_result["reason"] = "no_data_found"
                logging.info(f"No data found for hotel {hid} (paximum)")

            else:
                saved = save_json_file(
                    base_dir, hid, json.dumps(raw_data, indent=2, ensure_ascii=False)
                )
                if saved:
                    item_result["status"] = "saved"
                    item_result["path"] = os.path.join(base_dir, f"{hid}.json")
                else:
                    item_result["status"] = "failed"
                    item_result["reason"] = "save_failed"

            results.append(item_result)

        return {"supplier": supplier, "results": results}

    elif supplier == "juniperhoteltest":
        for hid in hotel_ids:
            item_result: dict = {"hotel_id": hid}
            raw_data = fetch_juniperhotel_raw(hid)

            if raw_data is None:
                item_result["status"] = "failed"
                item_result["reason"] = "fetch_failed_or_missing_credentials"
                logging.warning(f"Fetch failed for hotel {hid} (juniperhotel)")

            elif (
                isinstance(raw_data, dict) and raw_data.get("status") == "no_data_found"
            ):
                item_result["status"] = "failed"
                item_result["reason"] = "no_data_found"
                logging.info(f"No data found for hotel {hid} (juniperhotel)")

            else:
                saved = save_json_file(
                    base_dir, hid, json.dumps(raw_data, indent=2, ensure_ascii=False)
                )
                if saved:
                    item_result["status"] = "saved"
                    item_result["path"] = os.path.join(base_dir, f"{hid}.json")
                else:
                    item_result["status"] = "failed"
                    item_result["reason"] = "save_failed"

            results.append(item_result)

        return {"supplier": supplier, "results": results}

    elif supplier == "oryxhotel":
        for hid in hotel_ids:
            item_result: dict = {"hotel_id": hid}
            raw_data = fetch_oryxhotel_raw(hid)

            if raw_data is None:
                item_result["statusCode"] = "failed"
                item_result["reason"] = "fetch_failed_or_missing_credentials"
                logging.warning(f"Fetch failed for hotel {hid} (oryxhotel)")

            elif (
                isinstance(raw_data, dict)
                and raw_data.get("exceptionMessage") == "Hotels not available"
            ):
                item_result["statusCode"] = "failed"
                item_result["reason"] = "Hotels not available"
                logging.info(f"No data found for hotel {hid} (oryxhotel)")

            else:
                saved = save_json_file(
                    base_dir, hid, json.dumps(raw_data, indent=4, ensure_ascii=False)
                )
                if saved:
                    item_result["statusCode"] = "saved"
                    item_result["path"] = os.path.join(base_dir, f"{hid}.json")
                else:
                    item_result["statusCode"] = "failed"
                    item_result["reason"] = "save_failed"

            results.append(item_result)

        return {"supplier": supplier, "results": results}

    elif supplier == "hyperguestdirect":
        for hid in hotel_ids:
            item_result: dict = {"hotel_id": hid}
            raw_data = fetch_hyperguestdirect_raw(hid)

            if raw_data is None:
                item_result["status"] = "failed"
                item_result["reason"] = "fetch_failed_or_missing_credentials"
                logging.warning(f"Fetch failed for hotel {hid} (hyperguestdirect)")

            elif (
                isinstance(raw_data, dict) and raw_data.get("status") == "no_data_found"
            ):
                item_result["status"] = "failed"
                item_result["reason"] = "no_data_found"
                logging.info(f"No data found for hotel {hid} (hyperguestdirect)")

            else:
                saved = save_json_file(
                    base_dir, hid, json.dumps(raw_data, indent=2, ensure_ascii=False)
                )
                if saved:
                    item_result["status"] = "saved"
                    item_result["path"] = os.path.join(base_dir, f"{hid}.json")
                else:
                    item_result["status"] = "failed"
                    item_result["reason"] = "save_failed"

            results.append(item_result)

        return {"supplier": supplier, "results": results}

    elif supplier == "innstant":
        for hid in hotel_ids:
            item_result: dict = {"hotel_id": hid}
            raw_data = fetch_innstant_raw(hid)
            print(raw_data)

            if raw_data is None:
                item_result["status"] = "failed"
                item_result["reason"] = "fetch_failed_or_missing_credentials"
                logging.warning(f"Fetch failed for hotel {hid} (innstant)")

            elif (
                isinstance(raw_data, dict) and raw_data.get("status") == "no_data_found"
            ) or raw_data == "no_data_found":
                item_result["status"] = "failed"
                item_result["reason"] = "no_data_found"
                logging.info(f"No data found for hotel {hid} (innstant)")

            else:
                saved = save_json_file(
                    base_dir, hid, json.dumps(raw_data, indent=2, ensure_ascii=False)
                )
                if saved:
                    item_result["status"] = "saved"
                    item_result["path"] = os.path.join(base_dir, f"{hid}.json")
                else:
                    item_result["status"] = "failed"
                    item_result["reason"] = "save_failed"

            results.append(item_result)

        return {"supplier": supplier, "results": results}

    elif supplier == "ratehawk_new":
        for hid in hotel_ids:
            item_result: dict = {"hotel_id": hid}
            raw_data = fetch_ratehawk_raw(hid)

            if raw_data is None:
                item_result["status"] = "error"
                logging.info(f"No data found for hotel {hid} (ratehawk_new)")

            elif (
                isinstance(raw_data, dict) and raw_data.get("reason") == "no_data_found"
            ):
                item_result["status"] = "failed"
                item_result["reason"] = "no_data_found"
                logging.info(f"No data found for hotel {hid} (ratehawk_new)")

            elif isinstance(raw_data, dict):
                saved = save_json_file(
                    base_dir, hid, json.dumps(raw_data, indent=2, ensure_ascii=False)
                )
                if saved:
                    item_result["status"] = "saved"
                    item_result["path"] = os.path.join(base_dir, f"{hid}.json")
                else:
                    item_result["status"] = "failed"
                    item_result["reason"] = "save_failed"

            else:
                item_result["status"] = "failed"
                item_result["reason"] = "invalid_response"
                logging.warning(
                    f"Invalid response for hotel '{hid}' (ratehawk_new): {raw_data}"
                )

            results.append(item_result)

        return {"supplier": supplier, "results": results}

    elif supplier == "amadeushotel":
        for hid in hotel_ids:
            item_result: dict = {"hotel_id": hid}
            raw_data = fetch_amadeushotel_raw(hid)

            if raw_data is None:
                item_result["status"] = "error"
                logging.info(f"No data found for hotel {hid} (amadeushotel)")

            elif (
                isinstance(raw_data, dict) and raw_data.get("reason") == "no_data_found"
            ):
                item_result["status"] = "failed"
                item_result["reason"] = "no_data_found"
                logging.info(f"No data found for hotel {hid} (amadeushotel)")

            elif isinstance(raw_data, dict):
                saved = save_json_file(
                    base_dir, hid, json.dumps(raw_data, indent=2, ensure_ascii=False)
                )
                if saved:
                    item_result["status"] = "saved"
                    item_result["path"] = os.path.join(base_dir, f"{hid}.json")
                else:
                    item_result["status"] = "failed"
                    item_result["reason"] = "save_failed"

            else:
                item_result["status"] = "failed"
                item_result["reason"] = "invalid_response"
                logging.warning(
                    f"Invalid response for hotel '{hid}' (ratehawk_new): {raw_data}"
                )

            results.append(item_result)

        return {"supplier": supplier, "results": results}

    elif supplier == "kiwihotel":
        for hid in hotel_ids:
            item_result: dict = {"hotel_id": hid}
            raw_data = fetch_kiwi_hotel_raw(hid)

            if raw_data is None:
                item_result["status"] = "error"
                item_result["reason"] = "no_response"
                logging.info(f"No data found for hotel {hid} (kiwihotel)")

            elif (
                isinstance(raw_data, dict) and raw_data.get("reason") == "no_data_found"
            ):
                item_result["status"] = "failed"
                item_result["reason"] = "no_data_found"
                logging.info(f"No data found for hotel {hid} (kiwihotel)")

            elif isinstance(raw_data, dict):
                property_response = raw_data.get("PropertyDetailResponse")
                if property_response and "Errors" in property_response:
                    errors = property_response["Errors"]
                    error_items = errors.get("Error", [])

                    if isinstance(error_items, dict):
                        error_items = [error_items]

                    error_messages = []
                    for err in error_items:
                        code = err.get("@Code", "UNKNOWN")
                        msg = err.get("#text", "No message")
                        error_messages.append(f"{code}: {msg}")

                    item_result["status"] = "failed"
                    item_result["reason"] = "api_error"
                    item_result["errors"] = error_messages
                    logging.warning(
                        f"Skipping hotel {hid} (kiwihotel) due to API error(s): {error_messages}"
                    )
                    results.append(item_result)
                    continue

                saved = save_json_file(
                    base_dir, hid, json.dumps(raw_data, indent=2, ensure_ascii=False)
                )
                if saved:
                    item_result["status"] = "saved"
                    item_result["path"] = os.path.join(base_dir, f"{hid}.json")
                else:
                    item_result["status"] = "failed"
                    item_result["reason"] = "save_failed"

            else:
                item_result["status"] = "failed"
                item_result["reason"] = "invalid_response"
                logging.warning(
                    f"Invalid response for hotel '{hid}' (kiwihotel): {raw_data}"
                )

            results.append(item_result)

        return {"supplier": supplier, "results": results}

    else:
        raise HTTPException(
            status_code=400, detail=f"Unknown supplier_code: {supplier}"
        )
