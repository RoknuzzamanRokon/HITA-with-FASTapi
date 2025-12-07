from fastapi import HTTPException, APIRouter, status, Depends, Request
from pydantic import BaseModel
from sqlalchemy.orm import Session
from typing import Annotated
import json, os, secrets
from datetime import datetime
import urllib.parse
import xml.etree.ElementTree as ET
import re
import ast
from routes.path import (
    RAW_BASE_DIR,
    IRIX_STATIC_DIR,
    DOTW_STATIC_DIR,
    INSTANTTRAVEL_STATIC_DIR,
)
import csv
from database import get_db
from routes.auth import get_current_user
import models
from models import UserIPWhitelist
from security.audit_logging import AuditLogger, ActivityType, SecurityLevel
from middleware.ip_middleware import get_client_ip

router = APIRouter()

router = APIRouter(
    prefix="/v1.0/hotel",
    tags=["Raw Hotel Content"],
    responses={404: {"description": "Not found"}},
)


def check_ip_whitelist(user_id: str, request: Request, db: Session) -> bool:
    """
    Check if the user's IP address is in the whitelist.
    
    Args:
        user_id (str): The user ID to check
        request (Request): The FastAPI request object
        db (Session): Database session
    
    Returns:
        bool: True if IP is whitelisted, False otherwise
    """
    try:
        # Get client IP using the middleware function
        client_ip = get_client_ip(request)
        
        if not client_ip:
            return False
        
        # Check if the user has any active IP whitelist entries for this IP
        whitelist_entry = db.query(UserIPWhitelist).filter(
            UserIPWhitelist.user_id == user_id,
            UserIPWhitelist.ip_address == client_ip,
            UserIPWhitelist.is_active == True
        ).first()
        
        return whitelist_entry is not None
        
    except Exception as e:
        print(f"Error checking IP whitelist: {str(e)}")
        return False


class ConvertRequest(BaseModel):
    supplier_code: str
    hotel_id: str


def validate_hotel_id(hotel_id):
    """
    Validate hotel_id. If None or empty, return error dict.
    """
    if not hotel_id:
        return {"error": "Hotel ID is required and cannot be None."}
    return None


def safe_get(d, keys, default=None):
    """Safely traverse nested dicts and lists."""
    for key in keys:
        if isinstance(d, dict):
            d = d.get(key, default)
        elif isinstance(d, list) and isinstance(key, int):
            if 0 <= key < len(d):
                d = d[key]
            else:
                return default
        else:
            return default
    return d


def map_to_our_format(supplier_code: str, data: dict) -> dict:

    if supplier_code == "hotelbeds":
        createdAt = datetime.now()
        createdAt_str = createdAt.strftime("%Y-%m-%dT%H:%M:%S")
        created_at_dt = datetime.strptime(createdAt_str, "%Y-%m-%dT%H:%M:%S")
        timeStamp = int(created_at_dt.timestamp())

        def safe_get(d, keys, default=None):
            """Safely traverse nested dictionaries."""
            for key in keys:
                if isinstance(d, dict):
                    d = d.get(key, default)
                else:
                    return default
            return d

        hotel = data.get("hotel", {})
        if not isinstance(hotel, dict):
            hotel = {}

        # ---- Check if hotel_id is valid ----
        hotel_id = safe_get(hotel, ["code"], None)

        result = validate_hotel_id(hotel_id)
        if result:
            return result

        # --- Address ---
        address = safe_get(hotel, ["address", "content"], None)
        google_map_site_link = (
            f"http://maps.google.com/maps?q={address.replace(' ', '+')}"
            if address
            else None
        )

        # --- Phone Numbers ---
        phones = hotel.get("phones", [])
        phone_numbers = []
        if isinstance(phones, list):
            for phone in phones:
                if isinstance(phone, dict):
                    phone_number = phone.get("phoneNumber")
                    if phone_number:
                        phone_numbers.append(phone_number)

        # --- Base URL ---
        base_url_for_room_images = "https://photos.hotelbeds.com/giata/original/"

        # --- Get All Images ---
        images = hotel.get("images", [])
        if not isinstance(images, list):
            images = []

        # Build a dict: roomCode -> image URL (only one per roomCode)
        room_images_map = {}
        for img in images:
            if not isinstance(img, dict):
                continue
            room_code = img.get("roomCode")
            path = img.get("path")
            if room_code and path and room_code not in room_images_map:
                room_images_map[room_code] = f"{base_url_for_room_images}{path}"

        # --- Room Type ---
        room_type = []
        rooms = hotel.get("rooms", [])
        if not isinstance(rooms, list):
            rooms = []

        for room in rooms:
            if not isinstance(room, dict):
                continue

            room_code = safe_get(room, ["roomCode"], None)
            characteristic_desc = safe_get(
                room, ["characteristic", "description", "content"], None
            )

            # --- Extract amenities ---
            amenities = []
            for fac in safe_get(room, ["roomFacilities"], []):
                desc = safe_get(fac, ["description", "content"], None)
                if desc:
                    amenities.append(desc)

            # --- Extract room size (first matching 'roomStayFacilities' -> 'description' content) ---
            room_size = None
            room_stays = safe_get(room, ["roomStays"], [])
            for stay in room_stays:
                for fac in safe_get(stay, ["roomStayFacilities"], []):
                    desc = safe_get(fac, ["description", "content"], None)
                    if desc:
                        room_size = desc
                        break
                if room_size:
                    break

            room_data = {
                "room_id": room_code,
                "title": safe_get(room, ["description"], None),
                "title_lang": None,
                "room_pic": room_images_map.get(room_code),
                "description": safe_get(room, ["description"], None),
                "max_allowed": {
                    "total": safe_get(room, ["maxPax"], None),
                    "adults": safe_get(room, ["maxAdults"], None),
                    "children": safe_get(room, ["maxChildren"], None),
                    "infant": None,
                },
                "no_of_room": None,
                "room_size": room_size,
                "bed_type": [
                    {
                        "description": characteristic_desc,
                        "configuration": [],
                        "max_extrabeds": None,
                    }
                ],
                "shared_bathroom": None,
                "amenities": amenities,
            }

            room_type.append(room_data)

        # --- Facilities ---
        facilities = []
        check_in = None
        check_out = None
        for f in hotel.get("facilities", []):
            if isinstance(f, dict):
                desc = safe_get(f, ["description", "content"], None)
                facilities.append(
                    {"type": desc, "title": desc, "icon": "mdi mdi-translate-variant"}
                )

                # Extract Check-in time if available
                if desc == "Check-in hour":
                    check_in = f.get("timeFrom", None)

                # Extract Check-out time if available
                if desc == "Check-out hour":
                    check_out = f.get("timeTo", None)

        # --- Images ---
        base_url = "http://photos.hotelbeds.com/giata/original/"
        hotel_photo = []
        images = hotel.get("images", [])
        if not isinstance(images, list):
            images = []

        for img in images:
            if not isinstance(img, dict):
                continue
            picture_id = img.get("order", None)
            title = safe_get(img, ["type", "description", "content"], None)
            path = img.get("path", None)
            url = f"{base_url}{path}" if path else None

            hotel_photo.append({"picture_id": picture_id, "title": title, "url": url})

        # --- Images ---
        base_url_for_primary_photo = "http://photos.hotelbeds.com/giata/original/"
        hotel_photo_for_primary_img = []
        images_for_primary_photo = hotel.get("images", [])
        if not isinstance(images_for_primary_photo, list):
            images_for_primary_photo = []

        for img in images_for_primary_photo:
            if not isinstance(img, dict):
                continue
            title = safe_get(img, ["type", "description", "content"], None)
            path = img.get("path", None)
            url = f"{base_url_for_primary_photo}{path}" if path else None

            hotel_photo_for_primary_img.append({"title": title, "url": url})

        # --- Primary Photo (first with 'General view') ---
        primary_photo = None
        for photo in hotel_photo_for_primary_img:
            if photo["title"] == "General view":
                primary_photo = photo["url"]
                break

        # Only keep the required fields
        raw_star = hotel.get("category", {}).get("description", {}).get("content", None)
        star_rating = None
        if raw_star:
            match = re.search(r"\d+", raw_star)
            if match:
                star_rating = match.group(0)

        # Chain section
        chain = safe_get(hotel, ["chain", "description", "content"], None)

        # nearest_airports
        nearest_airports = []
        for airport in hotel.get("terminals", []):
            airport_data = {
                "code": safe_get(airport, ["terminalCode"], None),
                "name": safe_get(airport, ["name", "content"], None),
            }
            nearest_airports.append(airport_data)

        # Point of Interests
        point_of_interests = []

        for poi in hotel.get("interestPoints", []):
            poi_data = {
                "code": safe_get(poi, ["facilityCode"], None),
                "name": safe_get(poi, ["poiName"], None),
            }
            point_of_interests.append(poi_data)

        return {
            "created": createdAt_str,
            "timestamp": timeStamp,
            "hotel_id": hotel_id,
            "name": safe_get(hotel, ["name", "content"], None),
            "name_local": safe_get(hotel, ["name", "content"], None),
            "hotel_formerly_name": safe_get(hotel, ["name", "content"], None),
            "destination_code": safe_get(hotel, ["destination", "code"], None),
            "country_code": safe_get(hotel, ["country", "isoCode"], None),
            "brand_text": None,
            "property_type": safe_get(
                hotel, ["accommodationType", "typeDescription"], None
            ),
            "star_rating": star_rating,
            "chain": chain,
            "brand": None,
            "logo": None,
            "primary_photo": primary_photo,
            "review_rating": {
                "source": None,
                "number_of_reviews": None,
                "rating_average": None,
                "popularity_score": None,
            },
            "policies": {
                "checkin": {
                    "begin_time": check_in,
                    "end_time": check_out,
                    "instructions": None,
                    "min_age": None,
                },
                "checkout": {"time": check_out},
                "fees": {"optional": None},
                "know_before_you_go": None,
                "pets": None,
                "remark": None,
                "child_and_extra_bed_policy": {
                    "infant_age": None,
                    "children_age_from": None,
                    "children_age_to": None,
                    "children_stay_free": None,
                    "min_guest_age": None,
                },
                "nationality_restrictions": None,
            },
            "address": {
                "latitude": safe_get(hotel, ["coordinates", "latitude"], None),
                "longitude": safe_get(hotel, ["coordinates", "longitude"], None),
                "address_line_1": address,
                "address_line_2": None,
                "city": safe_get(hotel, ["city", "content"], None),
                "state": safe_get(hotel, ["state", "name"], None),
                "country": safe_get(hotel, ["country", "description", "content"], None),
                "country_code": safe_get(hotel, ["country", "isoCode"], None),
                "postal_code": safe_get(hotel, ["postalCode"], None),
                "full_address": f"{address}, {safe_get(hotel, ['city', 'content'], None)}, {safe_get(hotel, ['country', 'description', 'content'], None)}",
                "google_map_site_link": google_map_site_link,
                "local_lang": {
                    "latitude": safe_get(hotel, ["coordinates", "latitude"], None),
                    "longitude": safe_get(hotel, ["coordinates", "longitude"], None),
                    "address_line_1": address,
                    "address_line_2": None,
                    "city": safe_get(hotel, ["city", "content"], None),
                    "state": safe_get(hotel, ["state", "name"], None),
                    "country": safe_get(
                        hotel, ["country", "description", "content"], None
                    ),
                    "country_code": safe_get(hotel, ["country", "isoCode"], None),
                    "postal_code": safe_get(hotel, ["postalCode"], None),
                    "full_address": f"{address}, {safe_get(hotel, ['city', 'content'], None)}, {safe_get(hotel, ['country', 'description', 'content'], None)}",
                    "google_map_site_link": google_map_site_link,
                },
                "mapping": {
                    "continent_id": None,
                    "country_id": None,
                    "province_id": None,
                    "state_id": None,
                    "city_id": None,
                    "area_id": None,
                },
            },
            "contacts": {
                "phone_numbers": phone_numbers,
                "fax": None,
                "email_address": [safe_get(hotel, ["email"], None)],
                "website": [safe_get(hotel, ["web"], None)],
            },
            "descriptions": [
                {
                    "title": None,
                    "text": safe_get(hotel, ["description", "content"], None),
                }
            ],
            "room_type": room_type,
            "spoken_languages": [
                {
                    "type": "spoken_languages",
                    "title": "English",
                    "icon": "mdi mdi-translate-variant",
                }
            ],
            "amenities": None,
            "facilities": facilities,
            "hotel_photo": hotel_photo,
            "point_of_interests": point_of_interests,
            "nearest_airports": nearest_airports,
            "train_stations": None,
            "connected_locations": None,
            "stadiums": None,
        }

    elif supplier_code == "paximum":
        createdAt = datetime.now()
        createdAt_str = createdAt.strftime("%Y-%m-%dT%H:%M:%S")
        created_at_dt = datetime.strptime(createdAt_str, "%Y-%m-%dT%H:%M:%S")
        timeStamp = int(created_at_dt.timestamp())

        def safe_get(d, keys, default=None):
            """Safely access nested dictionary keys."""
            for key in keys:
                if isinstance(d, dict):
                    d = d.get(key, default)
                else:
                    return default
            return d

        # -------- Hotel Data Safe Extraction --------
        hotel = safe_get(data, ["body", "hotel"], {})

        # -------- Address Processing --------
        address_lines = hotel.get("address", {}).get("addressLines", [])
        if not isinstance(address_lines, list):
            address_lines = []

        address1 = address_lines[0] if len(address_lines) > 0 else ""
        address2 = ", ".join(address_lines[1:]) if len(address_lines) > 1 else ""

        full_address = f"{address1}, {address2}" if address2 else address1
        google_map_site_link = (
            f"http://maps.google.com/maps?q={full_address.replace(' ', '+')}"
            if full_address
            else None
        )

        # -------- Room Type Processing --------
        room_type = []
        rooms = hotel.get("rooms", [])
        if not isinstance(rooms, list):
            rooms = []

        for room in rooms:
            if not isinstance(room, dict):
                continue

            characteristic_desc = safe_get(
                room, ["characteristic", "description", "content"], None
            )

            room_data = {
                "room_id": room.get("roomCode", None),
                "title": room.get("description", None),
                "title_lang": None,
                "room_pic": None,
                "description": room.get("description", None),
                "max_allowed": {
                    "total": room.get("maxPax", None),
                    "adults": room.get("maxAdults", None),
                    "children": room.get("maxChildren", None),
                    "infant": None,
                },
                "no_of_room": None,
                "room_size": None,
                "bed_type": [
                    {
                        "description": characteristic_desc,
                        "configuration": [],
                        "max_extrabeds": None,
                    }
                ],
                "shared_bathroom": None,
            }
            room_type.append(room_data)

        # -------- Facilities --------
        facilities = []
        seasons = hotel.get("seasons", [])
        if not isinstance(seasons, list):
            seasons = []

        for season in seasons:
            if not isinstance(season, dict):
                continue

            for category in season.get("facilityCategories", []):
                if not isinstance(category, dict):
                    continue
                for facility in category.get("facilities", []):
                    if not isinstance(facility, dict):
                        continue
                    name = facility.get("name", None)
                    facilities.append(
                        {
                            "type": name,
                            "title": name,
                            "icon": "mdi mdi-translate-variant",
                        }
                    )

        # -------- Pictures / Media --------
        pictures = []
        for season in seasons:
            if not isinstance(season, dict):
                continue
            for media in season.get("mediaFiles", []):
                if not isinstance(media, dict):
                    continue
                pictures.append(
                    {
                        "picture_id": None,
                        "title": None,
                        "url": media.get("urlFull", None),
                    }
                )

        return {
            "created": createdAt_str,
            "timestamp": timeStamp,
            "hotel_id": hotel.get("id", None),
            "name": hotel.get("name", None),
            "name_local": hotel.get("name", None),
            "hotel_formerly_name": hotel.get("name", None),
            "destination_code": None,
            "country_code": hotel.get("country", {}).get("id", None),
            "brand_text": None,
            "property_type": None,
            "star_rating": hotel.get("stars", None),
            "chain": None,
            "brand": None,
            "logo": None,
            "primary_photo": hotel.get("thumbnailFull", None),
            "review_rating": {
                "source": None,
                "number_of_reviews": None,
                "rating_average": hotel.get("rating", None),
                "popularity_score": None,
            },
            "policies": {
                "checkin": {
                    "begin_time": None,
                    "end_time": None,
                    "instructions": None,
                    "min_age": None,
                },
                "checkout": {"time": None},
                "fees": {"optional": None},
                "know_before_you_go": None,
                "pets": None,
                "remark": None,
                "child_and_extra_bed_policy": {
                    "infant_age": None,
                    "children_age_from": None,
                    "children_age_to": None,
                    "children_stay_free": None,
                    "min_guest_age": None,
                },
                "nationality_restrictions": None,
            },
            "address": {
                "latitude": hotel.get("address", {})
                .get("geolocation", {})
                .get("latitude", None),
                "longitude": hotel.get("address", {})
                .get("geolocation", {})
                .get("longitude", None),
                "address_line_1": address1,
                "address_line_2": address2,
                "city": hotel.get("address", {}).get("city", {}).get("name", None),
                "state": None,
                "country": hotel.get("country", {}).get("name", None),
                "country_code": hotel.get("country", {}).get("id", None),
                "postal_code": hotel.get("address", {}).get("zipCode", None),
                "full_address": full_address,
                "google_map_site_link": google_map_site_link,
                "local_lang": {
                    "latitude": hotel.get("address", {})
                    .get("geolocation", {})
                    .get("latitude", None),
                    "longitude": hotel.get("address", {})
                    .get("geolocation", {})
                    .get("longitude", None),
                    "address_line_1": address1,
                    "address_line_2": address2,
                    "city": hotel.get("address", {}).get("city", {}).get("name", None),
                    "state": None,
                    "country": hotel.get("country", {}).get("name", None),
                    "country_code": hotel.get("country", {}).get("id", None),
                    "postal_code": hotel.get("address", {}).get("zipCode", None),
                    "full_address": full_address,
                    "google_map_site_link": google_map_site_link,
                },
                "mapping": {
                    "continent_id": None,
                    "country_id": None,
                    "province_id": None,
                    "state_id": None,
                    "city_id": None,
                    "area_id": None,
                },
            },
            "contacts": {
                "phone_numbers": [hotel.get("phoneNumber", None)],
                "fax": [hotel.get("faxNumber", None)],
                "email_address": [hotel.get("email", None)],
                "website": [hotel.get("homePage", None)],
            },
            "descriptions": [
                {"title": None, "text": hotel.get("description", {}).get("text", None)}
            ],
            "room_type": [
                {
                    "room_id": None,
                    "title": None,
                    "title_lang": None,
                    "room_pic": None,
                    "description": None,
                    "max_allowed": {
                        "total": None,
                        "adults": None,
                        "children": None,
                        "infant": None,
                    },
                    "no_of_room": None,
                    "room_size": None,
                    "bed_type": [
                        {
                            "description": None,
                            "configuration": [],
                            "max_extrabeds": None,
                        }
                    ],
                    "shared_bathroom": None,
                }
            ],
            "spoken_languages": [
                {
                    "type": "spoken_languages",
                    "title": "English",
                    "icon": "mdi mdi-translate-variant",
                }
            ],
            "amenities": None,
            "facilities": facilities,
            "hotel_photo": pictures,
            "point_of_interests": None,
            "nearest_airports": None,
            "train_stations": None,
            "connected_locations": None,
            "stadiums": None,
        }

    elif supplier_code == "stuba":
        # Time add
        createdAt = datetime.now()
        createdAt_str = createdAt.strftime("%Y-%m-%dT%H:%M:%S")
        created_at_dt = datetime.strptime(createdAt_str, "%Y-%m-%dT%H:%M:%S")
        timeStamp = int(created_at_dt.timestamp())

        def safe_get(d, keys, default=None):
            """Safely access nested dictionary keys."""
            for key in keys:
                if isinstance(d, dict):
                    d = d.get(key, default)
                else:
                    return default
            return d

        # Base path
        hotel = data.get("HotelElement", {})

        # Address section
        address1 = safe_get(hotel, ["Address", "Address1"], None)
        address2 = safe_get(hotel, ["Address", "Address2"], None)
        address3 = safe_get(hotel, ["Address", "Address3"], None)
        full_address = ", ".join(filter(None, [address1, address2, address3])) or None

        google_map_site_link = (
            f"http://maps.google.com/maps?q={full_address.replace(' ', '+')}"
            if full_address
            else None
        )

        # Description list
        description_items = hotel.get("Description", [])
        description_data = []

        for item in description_items:
            title = item.get("Type")
            text = item.get("Text")
            description_data.append({"title": title, "text": text})

        # Photos
        photos = hotel.get("Photo", [])
        base_url = "https://api.stuba.com"

        pictures = []
        primary_photo = None

        for index, photo in enumerate(photos):
            url_path = photo.get("Url", "")
            title = photo.get("Caption", None)
            full_url = f"{base_url}{url_path}" if url_path else None

            if full_url:
                if index == 0:
                    primary_photo = full_url
                pictures.append({"picture_id": None, "title": title, "url": full_url})

        # Amenities
        amenities_raw = hotel.get("Amenity", [])
        amenities = []

        for item in amenities_raw:
            code = item.get("Code", None)
            text = item.get("Text", None)
            if code or text:
                amenities.append(
                    {"type": code, "title": text, "icon": "mdi mdi-translate-variant"}
                )

        return {
            "created": createdAt_str,
            "timestamp": timeStamp,
            "hotel_id": hotel.get("Id", None),
            "name": hotel.get("Name", None),
            "name_local": hotel.get("Name", None),
            "hotel_formerly_name": hotel.get("Name", None),
            "destination_code": None,
            "country_code": None,
            "brand_text": None,
            "property_type": hotel.get("Type", None),
            "star_rating": hotel.get("Stars", None),
            "chain": None,
            "brand": None,
            "logo": None,
            "primary_photo": primary_photo,
            "review_rating": {
                "source": None,
                "number_of_reviews": None,
                "rating_average": hotel.get("Rating", {}).get("Score", None),
                "popularity_score": None,
            },
            "policies": {
                "checkin": {
                    "begin_time": None,
                    "end_time": None,
                    "instructions": None,
                    "min_age": None,
                },
                "checkout": {"time": None},
                "fees": {"optional": None},
                "know_before_you_go": None,
                "pets": None,
                "remark": None,
                "child_and_extra_bed_policy": {
                    "infant_age": None,
                    "children_age_from": None,
                    "children_age_to": None,
                    "children_stay_free": None,
                    "min_guest_age": None,
                },
                "nationality_restrictions": None,
            },
            "address": {
                "latitude": hotel.get("GeneralInfo", {}).get("Latitude", None),
                "longitude": hotel.get("GeneralInfo", {}).get("Longitude", None),
                "address_line_1": address1,
                "address_line_2": f"{address2},{address3}",
                "city": hotel.get("Address", {}).get("City", None),
                "state": hotel.get("Address", {}).get("State", None),
                "country": hotel.get("Address", {}).get("Country", None),
                "country_code": hotel.get("Address", {}).get("CountryCode", None),
                "postal_code": hotel.get("Address", {}).get("Zip", None),
                "full_address": full_address,
                "google_map_site_link": google_map_site_link,
                "local_lang": {
                    "latitude": hotel.get("GeneralInfo", {}).get("Latitude", None),
                    "longitude": hotel.get("GeneralInfo", {}).get("Longitude", None),
                    "address_line_1": address1,
                    "address_line_2": f"{address2},{address3}",
                    "city": hotel.get("Address", {}).get("City", None),
                    "state": hotel.get("Address", {}).get("State", None),
                    "country": hotel.get("Address", {}).get("Country", None),
                    "country_code": hotel.get("Address", {}).get("CountryCode", None),
                    "postal_code": hotel.get("Address", {}).get("Zip", None),
                    "full_address": full_address,
                    "google_map_site_link": google_map_site_link,
                },
                "mapping": {
                    "continent_id": None,
                    "country_id": None,
                    "province_id": None,
                    "state_id": None,
                    "city_id": None,
                    "area_id": None,
                },
            },
            "contacts": {
                "phone_numbers": [hotel.get("Address", {}).get("Tel", None)],
                "fax": [hotel.get("Address", {}).get("Fax", None)],
                "email_address": [hotel.get("Address", {}).get("Email", None)],
                "website": [hotel.get("Address", {}).get("Url", None)],
            },
            "descriptions": description_data,
            "room_type": {
                "room_id": None,
                "title": None,
                "title_lang": None,
                "room_pic": None,
                "description": None,
                "max_allowed": {
                    "total": None,
                    "adults": None,
                    "children": None,
                    "infant": None,
                },
                "no_of_room": None,
                "room_size": None,
                "bed_type": [
                    {"description": None, "configuration": [], "max_extrabeds": None}
                ],
                "shared_bathroom": None,
            },
            "spoken_languages": [
                {
                    "type": "spoken_languages",
                    "title": "English",
                    "icon": "mdi mdi-translate-variant",
                }
            ],
            "amenities": amenities,
            "facilities": None,
            "hotel_photo": pictures,
            "point_of_interests": None,
            "nearest_airports": None,
            "train_stations": None,
            "connected_locations": None,
            "stadiums": None,
        }

    elif supplier_code == "dotw":
        hotel = data

        # Time section.
        createdAt = datetime.now()
        createdAt_str = createdAt.strftime("%Y-%m-%dT%H:%M:%S")
        created_at_dt = datetime.strptime(createdAt_str, "%Y-%m-%dT%H:%M:%S")
        timeStamp = int(created_at_dt.timestamp())

        def safe_get(data, path, default=None):
            """Safely navigate nested dictionaries."""
            for key in path:
                if isinstance(data, dict):
                    data = data.get(key, default)
                else:
                    return default
            return data

        def get_dotw_location_info(hotel_code):
            filepath = os.path.join(DOTW_STATIC_DIR, "dotw_raw.txt")

            with open(filepath, newline="", encoding="utf-8-sig") as csvfile:
                reader = csv.DictReader(csvfile)

                for row in reader:
                    dotw_val = row.get("dotw", "").strip('"')
                    dotw_a_val = row.get("dotw_a", "").strip('"')
                    dotw_b_val = row.get("dotw_b", "").strip('"')

                    if (
                        dotw_val == str(hotel_code)
                        or dotw_a_val == str(hotel_code)
                        or dotw_b_val == str(hotel_code)
                    ):
                        return {
                            "CityName": row["CityName"] if row["CityName"] else None,
                            "CountryName": (
                                row["CountryName"] if row["CountryName"] else None
                            ),
                            "CountryCode": (
                                row["CountryCode"] if row["CountryCode"] else None
                            ),
                            "StateName": (
                                row["StateName"] if row["StateName"] else None
                            ),
                            "PropertyType": (
                                row["PropertyType"] if row["PropertyType"] else None
                            ),
                            "Rating": (row["Rating"] if row["Rating"] else None),
                        }
            return None

        # 1. Address block
        address1 = safe_get(hotel, ["address", "_text"])
        hotel_name = safe_get(hotel, ["hotelName", "_text"])
        full_address = address1
        if full_address and hotel_name:
            address_query = f"{full_address}, {hotel_name}"
            google_map_site_link = (
                f"http://maps.google.com/maps?q={address_query.replace(' ', '+')}"
            )
        elif full_address:
            google_map_site_link = (
                f"http://maps.google.com/maps?q={full_address.replace(' ', '+')}"
            )
        else:
            google_map_site_link = None

        # 2. Room data
        # ── Step A: Build a runno→url lookup from your hotelImages ──
        images_raw = safe_get(data, ["images", "hotelImages", "image"], [])
        if isinstance(images_raw, dict):
            images_raw = [images_raw]

        runno_to_url = {}
        for img in images_raw:
            if not isinstance(img, dict):
                continue
            runno = safe_get(img, ["runno"], None)
            url = safe_get(img, ["url", "_text"])
            if runno is not None and url:
                runno_to_url[str(runno)] = url

        # ── Step B: Loop your roomType entries and inject the matching URL ──
        output = []
        room_types = []
        rooms_group = safe_get(data, ["rooms", "room"], {})

        if isinstance(rooms_group, dict):
            room_types = rooms_group.get("roomType", [])

        if isinstance(room_types, dict):
            room_types = [room_types]
        elif not isinstance(room_types, list):
            room_types = []

        for room in room_types:
            if not isinstance(room, dict):
                continue

            room_name = safe_get(room, ["name", "_text"])
            runno = safe_get(room, ["runno"], None)
            room_code = safe_get(room, ["roomtypecode"], None)
            max_adult = int(safe_get(room, ["roomInfo", "maxAdult", "_text"], 0))
            max_child = int(safe_get(room, ["roomInfo", "maxChildren", "_text"], 0))
            max_pax = int(
                safe_get(room, ["roomCapacityInfo", "roomPaxCapacity", "_text"], 0)
            )
            max_extrabed = int(
                safe_get(room, ["roomCapacityInfo", "maxExtraBed", "_text"], 0)
            )

            # find the image URL by runno (or None if not found)
            room_pic = runno_to_url.get(str(runno))

            # amenities as before…
            room_amenities = []
            amen_list = safe_get(room, ["roomAmenities", "amenity"], [])
            if isinstance(amen_list, dict):
                amen_list = [amen_list]
            for amen in amen_list or []:
                if isinstance(amen, dict):
                    name = amen.get("_text")
                    if name:
                        room_amenities.append(name)

            output.append(
                {
                    "room_id": room_code,
                    "title": room_name,
                    "title_lang": None,
                    "room_pic": room_pic,  # ← now filled if runno matched
                    "description": None,
                    "max_allowed": {
                        "total": max_pax,
                        "adults": max_adult,
                        "children": max_child,
                        "infant": None,
                    },
                    "no_of_room": None,
                    "room_size": None,
                    "bed_type": [
                        {
                            "description": None,
                            "configuration": [],
                            "max_extrabeds": max_extrabed,
                        }
                    ],
                    "shared_bathroom": None,
                    "amenities": room_amenities or [],
                }
            )

        # 3. Hotel-level amenities
        amenities_raw = safe_get(data, ["amenitie", "language", "amenitieItem"], [])
        if isinstance(amenities_raw, dict):
            amenities_raw = [amenities_raw]

        amenities_data = []
        for item in amenities_raw:
            title = item.get("_text") if isinstance(item, dict) else None
            if title:
                amenities_data.append(
                    {"type": title, "title": title, "icon": "mdi mdi-translate-variant"}
                )

        # 4. Images
        images_raw = safe_get(data, ["images", "hotelImages", "image"], [])
        if isinstance(images_raw, dict):
            images_raw = [images_raw]

        pictures = []
        for img in images_raw:
            if isinstance(img, dict):
                url = safe_get(img, ["url", "_text"])
                title = safe_get(img, ["alt", "_text"])
                if url:
                    pictures.append({"picture_id": None, "title": title, "url": url})

        # 5. Nearest Airports
        airports = safe_get(data, ["transportation", "airports", "airport"], [])
        if isinstance(airports, dict):
            airports = [airports]

        nearest_airports = []
        for ap in airports:
            if isinstance(ap, dict):
                name = safe_get(ap, ["name", "_text"])
                if name:
                    nearest_airports.append({"code": None, "name": name})

        # 6. Train Stations
        rails = safe_get(data, ["transportation", "rails", "rail"], [])
        if isinstance(rails, dict):
            rails = [rails]

        train_stations = []
        for rail in rails:
            if isinstance(rail, dict):
                name = safe_get(rail, ["name", "_text"])
                if name:
                    train_stations.append({"code": None, "name": name})

        # 7. Point of Interests
        pois = safe_get(data, ["geoLocations", "geoLocation"], [])
        if isinstance(pois, dict):
            pois = [pois]

        point_of_interests = []
        for poi in pois:
            if isinstance(poi, dict):
                name = safe_get(poi, ["name", "_text"])
                code = poi.get("id")
                if name:
                    point_of_interests.append({"code": code, "name": name})

        hotel_code = hotel.get("hotelid", None)

        # print(hotel_code)

        # Here get location info from txt file.
        if hotel_code:
            location_info = get_dotw_location_info(hotel_code)

            if location_info:
                CountryCode = location_info["CountryCode"]
                CountryName = location_info["CountryName"]
                CityName = location_info["CityName"]
                StateName = location_info["StateName"]
                PropertyType = location_info["PropertyType"]
                Rating = location_info["Rating"]
            else:
                CountryCode = None
                CountryName = None
                CityName = None
                StateName = None
                PropertyType = None
                Rating = None

        return {
            "created": createdAt_str,
            "timestamp": timeStamp,
            "hotel_id": hotel.get("hotelid", None),
            "name": hotel.get("hotelName", {}).get("_text", None),
            "name_local": hotel.get("hotelName", {}).get("_text", None),
            "hotel_formerly_name": hotel.get("hotelName", {}).get("_text", None),
            "destination_code": None,
            "country_code": CountryCode,
            "brand_text": None,
            "property_type": PropertyType,
            "star_rating": Rating,
            "chain": None,
            "brand": None,
            "logo": None,
            "primary_photo": hotel.get("images", {})
            .get("hotelImages", {})
            .get("thumb", {})
            .get("_text", None),
            "review_rating": {
                "source": None,
                "number_of_reviews": None,
                "rating_average": hotel.get("rating", {}).get("_text", None),
                "popularity_score": None,
            },
            "policies": {
                "checkin": {
                    "begin_time": hotel.get("hotelCheckIn", {}).get("_text", None),
                    "end_time": hotel.get("hotelCheckOut", {}).get("_text", None),
                    "instructions": None,
                    "min_age": hotel.get("minAge", {}).get("_text", None),
                },
                "checkout": {"time": hotel.get("hotelCheckOut", {}).get("_text", None)},
                "fees": {"optional": None},
                "know_before_you_go": None,
                "pets": None,
                "remark": None,
                "child_and_extra_bed_policy": {
                    "infant_age": None,
                    "children_age_from": None,
                    "children_age_to": None,
                    "children_stay_free": None,
                    "min_guest_age": None,
                },
                "nationality_restrictions": None,
            },
            "address": {
                "latitude": safe_get(hotel, ["geoPoint", "lat", "_text"]),
                "longitude": safe_get(hotel, ["geoPoint", "lng", "_text"]),
                "address_line_1": address1,
                "address_line_2": None,
                "city": CityName,
                "state": StateName,
                "country": CountryName,
                "country_code": CountryCode,
                "postal_code": safe_get(hotel, ["zipCode", "_text"]),
                "full_address": f"{full_address},{CityName},{CountryName}",
                "google_map_site_link": google_map_site_link,
                "local_lang": {
                    "latitude": safe_get(hotel, ["geoPoint", "lat", "_text"]),
                    "longitude": safe_get(hotel, ["geoPoint", "lng", "_text"]),
                    "address_line_1": address1,
                    "address_line_2": None,
                    "city": CityName,
                    "state": StateName,
                    "country": CountryName,
                    "country_code": CountryCode,
                    "postal_code": safe_get(hotel, ["zipCode", "_text"]),
                    "full_address": f"{full_address},{CityName},{CountryName}",
                    "google_map_site_link": google_map_site_link,
                },
                "mapping": {
                    "continent_id": None,
                    "country_id": safe_get(hotel, ["countryCode", "_text"]),
                    "province_id": None,
                    "state_id": safe_get(hotel, ["stateCode", "_text"]),
                    "city_id": safe_get(hotel, ["cityCode", "_text"]),
                    "area_id": None,
                },
            },
            "contacts": {
                "phone_numbers": [hotel.get("hotelPhone", {}).get("_text", None)],
                "fax": [hotel.get("faxNumber", {}).get("_text", None)],
                "email_address": [hotel.get("emailAddress", {}).get("_text", None)],
                "website": [hotel.get("webAddress", {}).get("_text", None)],
            },
            "descriptions": [
                {
                    "title": hotel.get("description1", {})
                    .get("language", {})
                    .get("name", None),
                    "text": hotel.get("description1", {})
                    .get("language", {})
                    .get("_text", None),
                },
                {
                    "title": hotel.get("description2", {})
                    .get("language", {})
                    .get("name", None),
                    "text": hotel.get("description2", {})
                    .get("language", {})
                    .get("_text", None),
                },
            ],
            "room_type": output,
            "spoken_languages": [
                {
                    "type": "spoken_languages",
                    "title": "English",
                    "icon": "mdi mdi-translate-variant",
                }
            ],
            "amenities": amenities_data,
            "facilities": None,
            "hotel_photo": pictures,
            "point_of_interests": point_of_interests,
            "nearest_airports": nearest_airports,
            "train_stations": train_stations,
            "connected_locations": None,
            "stadiums": None,
        }

    elif supplier_code == "amadeushotel":
        # This is time section
        createdAt = datetime.now()
        createdAt_str = createdAt.strftime("%Y-%m-%dT%H:%M:%S")
        created_at_dt = datetime.strptime(createdAt_str, "%Y-%m-%dT%H:%M:%S")
        timeStamp = int(created_at_dt.timestamp())

        # Base data field.
        def safe_get(data, path, default=None):
            """Safely navigate nested dictionaries."""
            for key in path:
                if isinstance(data, dict):
                    data = data.get(key, default)
                else:
                    return default
            return data

        # Base data field.
        hotel = (
            data.get("Body", {})
            .get("OTA_HotelDescriptiveInfoRS", {})
            .get("HotelDescriptiveContents", {})
            .get("HotelDescriptiveContent", {})
        )
        # Address section
        address1 = safe_get(
            hotel,
            ["ContactInfos", "ContactInfo", "Addresses", "Address", "AddressLine"],
            None,
        )
        if isinstance(address1, list):
            full_address = ", ".join(address1)
        else:
            full_address = address1

        google_map_site_link = (
            f"http://maps.google.com/maps?q={full_address.replace(' ', '+')}"
            if full_address
            else None
        )

        # This section for photo
        media_data = safe_get(
            hotel,
            [
                "HotelInfo",
                "Descriptions",
                "MultimediaDescriptions",
                "MultimediaDescription",
            ],
            [],
        )

        # For Photo section.
        primary_photo_url = None
        hotel_photo = []

        for item in media_data:
            if not isinstance(item, dict):
                continue
            image_items = safe_get(item, ["ImageItems", "ImageItem"], [])

            for image in image_items:
                if not isinstance(image, dict):
                    continue

                # -------- PRIMARY PHOTO EXTRACTION -------- #
                if not primary_photo_url and image.get("Category") == "1":
                    for image_format in image.get("ImageFormat", []):
                        if (
                            isinstance(image_format, dict)
                            and image_format.get("DimensionCategory") == "J"
                        ):
                            primary_photo_url = image_format.get("URL")
                            break
                    if not primary_photo_url:
                        for image_format in image.get("ImageFormat", []):
                            if (
                                isinstance(image_format, dict)
                                and image_format.get("IsOriginalIndicator") == "true"
                            ):
                                primary_photo_url = image_format.get("URL")

                # -------- ALL HOTEL PHOTOS -------- #
                image_url = None
                for image_format in image.get("ImageFormat", []):
                    if (
                        isinstance(image_format, dict)
                        and image_format.get("DimensionCategory") == "J"
                    ):
                        image_url = image_format.get("URL")
                        break
                if not image_url:
                    for image_format in image.get("ImageFormat", []):
                        if (
                            isinstance(image_format, dict)
                            and image_format.get("IsOriginalIndicator") == "true"
                        ):
                            image_url = image_format.get("URL")
                            break

                if image_url:
                    hotel_photo.append(
                        {
                            "picture_id": image_format.get("RecordID"),
                            "title": safe_get(image, ["Description", "Caption"], ""),
                            "url": image_url,
                        }
                    )

        # Fallback: try to get primary if not set
        if not primary_photo_url and hotel_photo:
            primary_photo_url = hotel_photo[0]["url"]

        # This section for policies.
        policy_list = safe_get(hotel, ["Policies", "Policy"], [])
        check_in_time = None
        check_in_checkout = None

        for policy in policy_list:
            policy_info = safe_get(policy, ["PolicyInfo"])
            if policy_info:
                check_in_time = safe_get(policy_info, ["CheckInTime"])
                check_in_checkout = safe_get(policy_info, ["CheckOutTime"])
                break

        # For content section using safe_get

        # Here for phone
        phones = safe_get(hotel, ["ContactInfos", "ContactInfo", "Phones", "Phone"], [])
        if isinstance(phones, dict):
            phones = [phones]
        phone_numbers = [
            safe_get(item, ["PhoneNumber"])
            for item in phones
            if safe_get(item, ["PhoneNumber"])
        ]

        # Here for email
        email_entry = safe_get(
            hotel, ["ContactInfos", "ContactInfo", "Emails", "Email"], {}
        )
        email = safe_get(email_entry, ["text"])
        email_list = [email] if email else []

        # Here for website
        web_url_entry = safe_get(hotel, ["ContactInfos", "ContactInfo", "URLs"], {})
        web_url = safe_get(web_url_entry, ["URL"])
        web_url_list = [web_url] if web_url else []

        # This section for photo
        description_data = safe_get(
            hotel,
            [
                "HotelInfo",
                "Descriptions",
                "MultimediaDescriptions",
                "MultimediaDescription",
            ],
            [],
        )

        descriptions = []

        for item in description_data:
            if not isinstance(item, dict):
                continue

            desc_type = item.get("InfoCode")  # <-- Extract InfoCode here
            text_items = safe_get(item, ["TextItems", "TextItem"], [])

            # Ensure text_items is a list
            if isinstance(text_items, dict):
                text_items = [text_items]

            for text_item in text_items:
                text = safe_get(text_item, ["Description", "text"])
                descriptions.append({"title": desc_type, "text": text})

        # pull the list of guest rooms

        guest_rooms = (
            hotel.get("FacilityInfo", {}).get("GuestRooms", {}).get("GuestRoom", [])
        )

        room_types = []

        for room in guest_rooms:
            image_caption = None
            image_lang = None
            first_img_url = None

            images = safe_get(
                room,
                [
                    "MultimediaDescriptions",
                    "MultimediaDescription",
                    "ImageItems",
                    "ImageItem",
                ],
                [],
            )

            if isinstance(images, dict):
                images = [images]  # wrap single dict into a list

            if images and isinstance(images, list):
                first = images[0]
                formats = first.get("ImageFormat", [])
                if isinstance(formats, dict):
                    formats = [formats]  # wrap single dict

                # Get original or fallback to first format
                original = next(
                    (f for f in formats if f.get("IsOriginalIndicator") == "true"), None
                )
                if original:
                    first_img_url = original.get("URL")
                elif formats:
                    first_img_url = formats[0].get("URL")

                image_caption = safe_get(first, ["Description", "Caption"])
                image_lang = safe_get(first, ["Description", "Language"])

            room_type = {
                "room_id": safe_get(room, ["TypeRoom", "RoomTypeCode"]),
                "title": image_caption,
                "title_lang": image_lang,
                "room_pic": first_img_url,
                "description": None,
                "max_allowed": {
                    "total": None,
                    "adults": None,
                    "children": None,
                    "infant": None,
                },
                "no_of_room": None,
                "room_size": safe_get(room, ["Dimension", "Area"]),
                "bed_type": [
                    {"description": None, "configuration": [], "max_extrabeds": None}
                ],
                "shared_bathroom": None,
            }

            room_types.append(room_type)

        return {
            "created": createdAt_str,
            "timestamp": timeStamp,
            "hotel_id": hotel.get("HotelCode", None),
            "name": hotel.get("HotelName", None),
            "name_local": hotel.get("HotelName", None),
            "hotel_formerly_name": hotel.get("HotelName", None),
            "destination_code": None,
            "country_code": hotel.get("ContactInfos", {})
            .get("ContactInfo", {})
            .get("Addresses", {})
            .get("Address", {})
            .get("CountryName", {})
            .get("Code", None),
            "brand_text": hotel.get("BrandName", None),
            "property_type": None,
            "star_rating": hotel.get("AffiliationInfo", {})
            .get("Awards", {})
            .get("Award", {})
            .get("Rating", None),
            "chain": hotel.get("ChainCode", None),
            "brand": hotel.get("BrandName", None),
            "logo": None,
            "primary_photo": primary_photo_url,
            "review_rating": {
                "source": None,
                "number_of_reviews": None,
                "rating_average": None,
                "popularity_score": None,
            },
            "policies": {
                "checkin": {
                    "begin_time": check_in_time,
                    "end_time": check_in_checkout,
                    "instructions": None,
                    "min_age": None,
                },
                "checkout": {
                    "time": check_in_checkout,
                },
                "fees": {"optional": None},
                "know_before_you_go": None,
                "pets": None,
                "remark": None,
                "child_and_extra_bed_policy": {
                    "infant_age": None,
                    "children_age_from": None,
                    "children_age_to": None,
                    "children_stay_free": None,
                    "min_guest_age": None,
                },
                "nationality_restrictions": None,
            },
            "address": {
                "latitude": hotel.get("HotelInfo", {})
                .get("Position", {})
                .get("Latitude", None),
                "longitude": hotel.get("HotelInfo", {})
                .get("Position", {})
                .get("Longitude", None),
                "address_line_1": full_address,
                "address_line_2": None,
                "city": hotel.get("ContactInfos", {})
                .get("ContactInfo", {})
                .get("Addresses", {})
                .get("Address", {})
                .get("CityName", None),
                "state": None,
                "country": None,
                "country_code": hotel.get("ContactInfos", {})
                .get("ContactInfo", {})
                .get("Addresses", {})
                .get("Address", {})
                .get("CountryName", {})
                .get("Code", None),
                "postal_code": hotel.get("ContactInfos", {})
                .get("ContactInfo", {})
                .get("Addresses", {})
                .get("Address", {})
                .get("PostalCode", None),
                "full_address": full_address,
                "google_map_site_link": google_map_site_link,
                "local_lang": {
                    "latitude": hotel.get("HotelInfo", {})
                    .get("Position", {})
                    .get("Latitude", None),
                    "longitude": hotel.get("HotelInfo", {})
                    .get("Position", {})
                    .get("Longitude", None),
                    "address_line_1": full_address,
                    "address_line_2": None,
                    "city": hotel.get("ContactInfos", {})
                    .get("ContactInfo", {})
                    .get("Addresses", {})
                    .get("Address", {})
                    .get("CityName", None),
                    "state": None,
                    "country": None,
                    "country_code": hotel.get("ContactInfos", {})
                    .get("ContactInfo", {})
                    .get("Addresses", {})
                    .get("Address", {})
                    .get("CountryName", {})
                    .get("Code", None),
                    "postal_code": hotel.get("ContactInfos", {})
                    .get("ContactInfo", {})
                    .get("Addresses", {})
                    .get("Address", {})
                    .get("PostalCode", None),
                    "full_address": full_address,
                    "google_map_site_link": google_map_site_link,
                },
                "mapping": {
                    "continent_id": None,
                    "country_id": None,
                    "province_id": None,
                    "state_id": None,
                    "city_id": None,
                    "area_id": None,
                },
            },
            "contacts": {
                "phone_numbers": phone_numbers,
                "fax": None,
                "email_address": email_list,
                "website": web_url_list,
            },
            "descriptions": descriptions,
            "room_type": room_types,
            "spoken_languages": [
                {
                    "type": "spoken_languages",
                    "title": "English",
                    "icon": "mdi mdi-translate-variant",
                }
            ],
            "amenities": [
                {"type": "", "title": "", "icon": "mdi mdi-translate-variant"}
            ],
            "facilities": [
                {"type": "", "title": "", "icon": "mdi mdi-translate-variant"}
            ],
            "hotel_photo": hotel_photo,
            "point_of_interests": [{"code": None, "name": None}],
            "nearest_airports": [{"code": None, "name": None}],
            "train_stations": [{"code": None, "name": None}],
            "connected_locations": [{"code": None, "name": None}],
            "stadiums": [{"code": None, "name": None}],
        }

    elif supplier_code == "roomerang":
        # This is time section
        createdAt = datetime.now()
        createdAt_str = createdAt.strftime("%Y-%m-%dT%H:%M:%S")
        created_at_dt = datetime.strptime(createdAt_str, "%Y-%m-%dT%H:%M:%S")
        timeStamp = int(created_at_dt.timestamp())

        # Safe entry
        def safe_get(d, keys, default=None):
            """Safely traverse nested dictionaries."""
            for key in keys:
                if isinstance(d, dict):
                    d = d.get(key, default)
                else:
                    return default
            return d

        # --- Base Data ---
        hotel = data.get("node", {}).get("hotelData", {})
        if not isinstance(hotel, dict):
            hotel = {}

        # --- Address ---
        address1 = safe_get(hotel, ["location", "address"], None)
        full_address = address1 or ""
        google_map_site_link = (
            f"http://maps.google.com/maps?q={full_address.replace(' ', '+')}"
            if full_address
            else None
        )

        # --- Descriptions ---
        descriptions = []
        descriptions_data = hotel.get("descriptions", [])
        if isinstance(descriptions_data, list):
            for item in descriptions_data:
                if not isinstance(item, dict):
                    continue
                desc_type = item.get("type")
                texts = item.get("texts", [])
                if isinstance(texts, list):
                    for text_item in texts:
                        if isinstance(text_item, dict):
                            descriptions.append(
                                {
                                    "title": desc_type,
                                    "text": text_item.get("text", None),
                                }
                            )

        # --- Amenities ---
        amenities = []
        all_amenities = hotel.get("amenities", {})
        edges = all_amenities.get("edges", [])
        if isinstance(edges, list):
            for edge in edges:
                amenity = safe_get(edge, ["node", "amenityData"], {})
                if isinstance(amenity, dict):
                    title = amenity.get("amenityCode", None)
                    if title:
                        amenities.append(
                            {
                                "type": "amenity",
                                "title": title,
                                "icon": "mdi mdi-translate-variant",
                            }
                        )

        # --- Images / Medias ---
        pictures = []
        primary_photo = None
        medias = hotel.get("medias", [])
        if isinstance(medias, list):
            for index, media in enumerate(medias):
                if not isinstance(media, dict):
                    continue
                url = media.get("url", None)
                if index == 0:
                    primary_photo = url
                pictures.append({"picture_id": None, "title": None, "url": url})

        return {
            "created": createdAt_str,
            "timestamp": timeStamp,
            "hotel_id": hotel.get("hotelCode", None),
            "name": hotel.get("hotelName", None),
            "name_local": hotel.get("hotelName", None),
            "hotel_formerly_name": hotel.get("hotelName", None),
            "destination_code": None,
            "country_code": hotel.get("location", {}).get("country", None),
            "brand_text": None,
            "property_type": hotel.get("propertyType", None),
            "star_rating": hotel.get("categoryCode", None),
            "chain": hotel.get("chainCode", None),
            "brand": None,
            "logo": None,
            "primary_photo": primary_photo,
            "review_rating": {
                "source": None,
                "number_of_reviews": None,
                "rating_average": None,
                "popularity_score": None,
            },
            "policies": {
                "checkin": {
                    "begin_time": hotel.get("checkIn", None),
                    "end_time": hotel.get("checkOut", None),
                    "instructions": None,
                    "min_age": None,
                },
                "checkout": {"time": hotel.get("checkOut", None)},
                "fees": {"optional": None},
                "know_before_you_go": None,
                "pets": None,
                "remark": None,
                "child_and_extra_bed_policy": {
                    "infant_age": None,
                    "children_age_from": None,
                    "children_age_to": None,
                    "children_stay_free": None,
                    "min_guest_age": None,
                },
                "nationality_restrictions": None,
            },
            "address": {
                "latitude": hotel.get("location", {})
                .get("coordinates", {})
                .get("latitude", None),
                "longitude": hotel.get("location", {})
                .get("coordinates", {})
                .get("longitude", None),
                "address_line_1": address1,
                "address_line_2": None,
                "city": hotel.get("location", {}).get("city", None),
                "state": None,
                "country": None,
                "country_code": hotel.get("location", {}).get("country", None),
                "postal_code": hotel.get("location", {}).get("zipCode", None),
                "full_address": full_address,
                "google_map_site_link": google_map_site_link,
                "local_lang": {
                    "latitude": hotel.get("location", {})
                    .get("coordinates", {})
                    .get("latitude", None),
                    "longitude": hotel.get("location", {})
                    .get("coordinates", {})
                    .get("longitude", None),
                    "address_line_1": address1,
                    "address_line_2": None,
                    "city": hotel.get("location", {}).get("city", None),
                    "state": None,
                    "country": hotel.get("location", {}).get("country", None),
                    "country_code": hotel.get("location", {}).get("countryCode", None),
                    "postal_code": hotel.get("location", {}).get("zipCode", None),
                    "full_address": full_address,
                    "google_map_site_link": google_map_site_link,
                },
                "mapping": {
                    "continent_id": None,
                    "country_id": None,
                    "province_id": None,
                    "state_id": None,
                    "city_id": None,
                    "area_id": None,
                },
            },
            "contacts": {
                "phone_numbers": [hotel.get("contact", {}).get("telephone", None)],
                "fax": [hotel.get("contact", {}).get("fax", None)],
                "email_address": [hotel.get("contact", {}).get("email", None)],
                "website": [hotel.get("contact", {}).get("web", None)],
            },
            "descriptions": descriptions,
            "room_type": [
                {
                    "room_id": None,
                    "title": None,
                    "title_lang": None,
                    "room_pic": None,
                    "description": None,
                    "max_allowed": {
                        "total": None,
                        "adults": None,
                        "children": None,
                        "infant": None,
                    },
                    "no_of_room": None,
                    "room_size": None,
                    "bed_type": [
                        {
                            "description": None,
                            "configuration": [],
                            "max_extrabeds": None,
                        }
                    ],
                    "shared_bathroom": None,
                }
            ],
            "spoken_languages": [
                {
                    "type": "spoken_languages",
                    "title": "English",
                    "icon": "mdi mdi-translate-variant",
                }
            ],
            "amenities": amenities,
            "facilities": None,
            "hotel_photo": pictures,
            "point_of_interests": None,
            "nearest_airports": None,
            "train_stations": None,
            "connected_locations": None,
            "stadiums": None,
        }

    elif supplier_code == "rakuten":
        # This is time section
        createdAt = datetime.now()
        createdAt_str = createdAt.strftime("%Y-%m-%dT%H:%M:%S")
        created_at_dt = datetime.strptime(createdAt_str, "%Y-%m-%dT%H:%M:%S")
        timeStamp = int(created_at_dt.timestamp())

        # Safe entry
        def safe_get(d, keys, default=None):
            """Safely traverse nested dictionaries."""
            for key in keys:
                if isinstance(d, dict):
                    d = d.get(key, default)
                else:
                    return default
            return d

        # --- Base Data ---
        hotel = data.get("node", {}).get("hotelData", {})
        if not isinstance(hotel, dict):
            hotel = {}

        # --- Address ---
        address1 = safe_get(hotel, ["location", "address"], None)
        full_address = address1 or ""
        google_map_site_link = (
            f"http://maps.google.com/maps?q={full_address.replace(' ', '+')}"
            if full_address
            else None
        )

        # --- Descriptions ---
        descriptions = []
        descriptions_data = hotel.get("descriptions", [])
        if isinstance(descriptions_data, list):
            for item in descriptions_data:
                if not isinstance(item, dict):
                    continue
                desc_type = item.get("type")
                texts = item.get("texts", [])
                if isinstance(texts, list):
                    for text_item in texts:
                        if isinstance(text_item, dict):
                            descriptions.append(
                                {
                                    "title": desc_type,
                                    "text": text_item.get("text", None),
                                }
                            )

        # --- Amenities ---
        amenities = []
        all_amenities = hotel.get("amenities", {})
        edges = all_amenities.get("edges", [])
        if isinstance(edges, list):
            for edge in edges:
                amenity = safe_get(edge, ["node", "amenityData"], {})
                if isinstance(amenity, dict):
                    title = amenity.get("amenityCode", None)
                    if title:
                        amenities.append(
                            {
                                "type": "amenity",
                                "title": title,
                                "icon": "mdi mdi-translate-variant",
                            }
                        )

        # --- Images / Medias ---
        pictures = []
        primary_photo = None
        medias = hotel.get("medias", [])
        if isinstance(medias, list):
            for index, media in enumerate(medias):
                if not isinstance(media, dict):
                    continue
                url = media.get("url", None)
                if index == 0:
                    primary_photo = url
                pictures.append({"picture_id": None, "title": None, "url": url})

        return {
            "created": createdAt_str,
            "timestamp": timeStamp,
            "hotel_id": safe_get(hotel, ["hotelCode"], None),
            "name": safe_get(hotel, ["hotelName"], None),
            "name_local": safe_get(hotel, ["hotelName"], None),
            "hotel_formerly_name": safe_get(hotel, ["hotelName"], None),
            "destination_code": None,
            "country_code": safe_get(hotel, ["location", "country"], None),
            "brand_text": None,
            "property_type": safe_get(hotel, ["propertyType", "name"], None),
            "star_rating": safe_get(hotel, ["categoryCode"], None),
            "chain": safe_get(hotel, ["chainCode"], None),
            "brand": None,
            "logo": None,
            "primary_photo": primary_photo,
            "review_rating": {
                "source": None,
                "number_of_reviews": None,
                "rating_average": None,
                "popularity_score": None,
            },
            "policies": {
                "checkin": {
                    "begin_time": safe_get(hotel, ["checkIn"], None),
                    "end_time": safe_get(hotel, ["checkOut"], None),
                    "instructions": None,
                    "min_age": None,
                },
                "checkout": {"time": safe_get(hotel, ["checkOut"], None)},
                "fees": {"optional": None},
                "know_before_you_go": None,
                "pets": None,
                "remark": None,
                "child_and_extra_bed_policy": {
                    "infant_age": None,
                    "children_age_from": None,
                    "children_age_to": None,
                    "children_stay_free": None,
                    "min_guest_age": None,
                },
                "nationality_restrictions": None,
            },
            "address": {
                "latitude": safe_get(
                    hotel, ["location", "coordinates", "latitude"], None
                ),
                "longitude": safe_get(
                    hotel, ["location", "coordinates", "longitude"], None
                ),
                "address_line_1": address1,
                "address_line_2": None,
                "city": safe_get(hotel, ["location", "city"], None),
                "state": None,
                "country": None,
                "country_code": safe_get(hotel, ["location", "country"], None),
                "postal_code": safe_get(hotel, ["location", "zipCode"], None),
                "full_address": full_address,
                "google_map_site_link": google_map_site_link,
                "local_lang": {
                    "latitude": safe_get(
                        hotel, ["location", "coordinates", "latitude"], None
                    ),
                    "longitude": safe_get(
                        hotel, ["location", "coordinates", "longitude"], None
                    ),
                    "address_line_1": address1,
                    "address_line_2": None,
                    "city": safe_get(hotel, ["location", "city"], None),
                    "state": None,
                    "country": safe_get(hotel, ["location", "country"], None),
                    "country_code": safe_get(hotel, ["location", "countryCode"], None),
                    "postal_code": safe_get(hotel, ["location", "zipCode"], None),
                    "full_address": full_address,
                    "google_map_site_link": google_map_site_link,
                },
                "mapping": {
                    "continent_id": None,
                    "country_id": None,
                    "province_id": None,
                    "state_id": None,
                    "city_id": None,
                    "area_id": None,
                },
            },
            "contacts": {
                "phone_numbers": [safe_get(hotel, ["contact", "telephone"], None)],
                "fax": [safe_get(hotel, ["contact", "fax"], None)],
                "email_address": [safe_get(hotel, ["contact", "email"], None)],
                "website": [safe_get(hotel, ["contact", "web"], None)],
            },
            "descriptions": descriptions,
            "room_type": [
                {
                    "room_id": None,
                    "title": None,
                    "title_lang": None,
                    "room_pic": None,
                    "description": None,
                    "max_allowed": {
                        "total": None,
                        "adults": None,
                        "children": None,
                        "infant": None,
                    },
                    "no_of_room": None,
                    "room_size": None,
                    "bed_type": [
                        {
                            "description": None,
                            "configuration": [],
                            "max_extrabeds": None,
                        }
                    ],
                    "shared_bathroom": None,
                }
            ],
            "spoken_languages": [
                {
                    "type": "spoken_languages",
                    "title": "English",
                    "icon": "mdi mdi-translate-variant",
                }
            ],
            "amenities": amenities,
            "facilities": None,
            "hotel_photo": pictures,
            "point_of_interests": None,
            "nearest_airports": None,
            "train_stations": None,
            "connected_locations": None,
            "stadiums": None,
        }

    elif supplier_code == "illusionshotel":
        # This is time section
        createdAt = datetime.now()
        createdAt_str = createdAt.strftime("%Y-%m-%dT%H:%M:%S")
        created_at_dt = datetime.strptime(createdAt_str, "%Y-%m-%dT%H:%M:%S")
        timeStamp = int(created_at_dt.timestamp())

        # Safe entry
        def safe_get(d, keys, default=None):
            """Safely traverse nested dictionaries."""
            for key in keys:
                if isinstance(d, dict):
                    d = d.get(key, default)
                else:
                    return default
            return d

        # Base data field.
        hotel = data.get("node", {}).get("hotelData", {}) or {}
        # Address section
        address1 = safe_get(hotel, ["location", "address"], None)
        full_address = address1
        google_map_site_link = (
            f"http://maps.google.com/maps?q={full_address.replace(' ', '+')}"
            if full_address
            else None
        )

        # Final descriptions structure
        descriptions_data = safe_get(hotel, ["descriptions"], [])
        descriptions = []
        for item in descriptions_data:
            desc_type = item.get("type", None)
            for text_item in item.get("texts", []):
                descriptions.append(
                    {"title": desc_type, "text": text_item.get("text", None)}
                )

        # Amenities sections
        all_amenities = safe_get(hotel, ["allAmenities"], {}) or {}
        amenities = []

        for edge in all_amenities.get("edges", []):
            amenity = edge.get("node", {}).get("amenityData", {}) or {}
            title = amenity.get("amenityCode")
            if title:
                amenities.append(
                    {
                        "type": "amenity",
                        "title": title,
                        "icon": "mdi mdi-translate-variant",
                    }
                )

        # This is image sections.
        medias = safe_get(hotel, ["medias"], [])
        if not medias:
            pictures = []
            primary_photo = None
        else:
            pictures = []
            primary_photo = None

            for index, media in enumerate(medias):
                url = media.get("url")
                if index == 0:
                    primary_photo = url

                pictures.append({"picture_id": None, "title": None, "url": url})

        return {
            "created": createdAt_str,
            "timestamp": timeStamp,
            "hotel_id": safe_get(hotel, ["hotelCode"], None),
            "name": safe_get(hotel, ["hotelName"], None),
            "name_local": safe_get(hotel, ["hotelName"], None),
            "hotel_formerly_name": safe_get(hotel, ["hotelName"], None),
            "destination_code": None,
            "country_code": safe_get(hotel, ["location", "country"], None),
            "brand_text": None,
            "property_type": safe_get(hotel, ["propertyType"], None),
            "star_rating": safe_get(hotel, ["categoryCode"], None),
            "chain": safe_get(hotel, ["chainCode"], None),
            "brand": None,
            "logo": None,
            "primary_photo": primary_photo,
            "review_rating": {
                "source": None,
                "number_of_reviews": None,
                "rating_average": None,
                "popularity_score": None,
            },
            "policies": {
                "checkin": {
                    "begin_time": safe_get(hotel, ["checkIn"], None),
                    "end_time": safe_get(hotel, ["checkOut"], None),
                    "instructions": None,
                    "min_age": None,
                },
                "checkout": {"time": safe_get(hotel, ["checkOut"], None)},
                "fees": {"optional": None},
                "know_before_you_go": None,
                "pets": None,
                "remark": None,
                "child_and_extra_bed_policy": {
                    "infant_age": None,
                    "children_age_from": None,
                    "children_age_to": None,
                    "children_stay_free": None,
                    "min_guest_age": None,
                },
                "nationality_restrictions": None,
            },
            "address": {
                "latitude": safe_get(
                    hotel, ["location", "coordinates", "latitude"], None
                ),
                "longitude": safe_get(
                    hotel, ["location", "coordinates", "longitude"], None
                ),
                "address_line_1": address1,
                "address_line_2": None,
                "city": safe_get(hotel, ["location", "city"], None),
                "state": None,
                "country": None,
                "country_code": safe_get(hotel, ["location", "country"], None),
                "postal_code": safe_get(hotel, ["location", "zipCode"], None),
                "full_address": full_address,
                "google_map_site_link": google_map_site_link,
                "local_lang": {
                    "latitude": safe_get(
                        hotel, ["location", "coordinates", "latitude"], None
                    ),
                    "longitude": safe_get(
                        hotel, ["location", "coordinates", "longitude"], None
                    ),
                    "address_line_1": address1,
                    "address_line_2": None,
                    "city": safe_get(hotel, ["location", "city"], None),
                    "state": None,
                    "country": safe_get(hotel, ["location", "country"], None),
                    "country_code": safe_get(hotel, ["location", "countryCode"], None),
                    "postal_code": safe_get(hotel, ["location", "zipCode"], None),
                    "full_address": full_address,
                    "google_map_site_link": google_map_site_link,
                },
                "mapping": {
                    "continent_id": None,
                    "country_id": None,
                    "province_id": None,
                    "state_id": None,
                    "city_id": None,
                    "area_id": None,
                },
            },
            "contacts": {
                "phone_numbers": [safe_get(hotel, ["contact", "telephone"], None)],
                "fax": [safe_get(hotel, ["contact", "fax"], None)],
                "email_address": [safe_get(hotel, ["contact", "email"], None)],
                "website": [safe_get(hotel, ["contact", "web"], None)],
            },
            "descriptions": descriptions,
            "room_type": [
                {
                    "room_id": None,
                    "title": None,
                    "title_lang": None,
                    "room_pic": None,
                    "description": None,
                    "max_allowed": {
                        "total": None,
                        "adults": None,
                        "children": None,
                        "infant": None,
                    },
                    "no_of_room": None,
                    "room_size": None,
                    "bed_type": [
                        {
                            "description": None,
                            "configuration": [],
                            "max_extrabeds": None,
                        }
                    ],
                    "shared_bathroom": None,
                }
            ],
            "spoken_languages": [
                {
                    "type": "spoken_languages",
                    "title": "English",
                    "icon": "mdi mdi-translate-variant",
                }
            ],
            "amenities": amenities,
            "facilities": None,
            "hotel_photo": pictures,
            "point_of_interests": None,
            "nearest_airports": None,
            "train_stations": None,
            "connected_locations": None,
            "stadiums": None,
        }

    elif supplier_code == "hotelston":
        # This is time section
        createdAt = datetime.now()
        createdAt_str = createdAt.strftime("%Y-%m-%dT%H:%M:%S")
        created_at_dt = datetime.strptime(createdAt_str, "%Y-%m-%dT%H:%M:%S")
        timeStamp = int(created_at_dt.timestamp())

        # Safe pass get data.
        def safe_get(d, keys, default=None):
            """Safely navigate through nested dictionaries."""
            for key in keys:
                if isinstance(d, dict):
                    d = d.get(key, default)
                else:
                    return default
            return d

        # --- Base Data ---
        hotel = data.get("node", {}).get("hotelData", {})
        if not isinstance(hotel, dict):
            hotel = {}

        # --- Address Section ---
        address1 = safe_get(hotel, ["location", "address"], "")
        full_address = address1 or ""
        google_map_site_link = (
            f"http://maps.google.com/maps?q={full_address.replace(' ', '+')}"
            if full_address
            else None
        )

        # --- Descriptions Section ---
        descriptions = []
        descriptions_data = hotel.get("descriptions", [])
        if isinstance(descriptions_data, list):
            for item in descriptions_data:
                if not isinstance(item, dict):
                    continue
                desc_type = item.get("type", None)
                texts = item.get("texts", [])
                if isinstance(texts, list):
                    for text_item in texts:
                        if isinstance(text_item, dict):
                            descriptions.append(
                                {
                                    "title": desc_type,
                                    "text": text_item.get("text", None),
                                }
                            )

        # --- Amenities Section ---
        amenities = []
        all_amenities = hotel.get("allAmenities", {})
        edges = all_amenities.get("edges", [])
        if isinstance(edges, list):
            for edge in edges:
                amenity = safe_get(edge, ["node", "amenityData"], {})
                title = (
                    amenity.get("amenityCode") if isinstance(amenity, dict) else None
                )
                if title:
                    amenities.append(
                        {
                            "type": "amenity",
                            "title": title,
                            "icon": "mdi mdi-translate-variant",
                        }
                    )

        # --- Images Section ---
        pictures = []
        primary_photo = None
        medias = hotel.get("medias", [])
        if isinstance(medias, list):
            for index, media in enumerate(medias):
                if not isinstance(media, dict):
                    continue
                url = media.get("url")
                if index == 0:
                    primary_photo = url
                pictures.append({"picture_id": None, "title": None, "url": url})

        return {
            "created": createdAt_str,
            "timestamp": timeStamp,
            "hotel_id": hotel.get("hotelCode", None),
            "name": hotel.get("hotelName", None),
            "name_local": hotel.get("hotelName", None),
            "hotel_formerly_name": hotel.get("hotelName", None),
            "destination_code": None,
            "country_code": hotel.get("location", {}).get("country", None),
            "brand_text": None,
            "property_type": hotel.get("propertyType", None),
            "star_rating": hotel.get("categoryCode", None),
            "chain": hotel.get("chainCode", None),
            "brand": None,
            "logo": None,
            "primary_photo": primary_photo,
            "review_rating": {
                "source": None,
                "number_of_reviews": None,
                "rating_average": None,
                "popularity_score": None,
            },
            "policies": {
                "checkin": {
                    "begin_time": hotel.get("checkIn", None),
                    "end_time": hotel.get("checkOut", None),
                    "instructions": None,
                    "min_age": None,
                },
                "checkout": {"time": hotel.get("checkOut", None)},
                "fees": {"optional": None},
                "know_before_you_go": None,
                "pets": None,
                "remark": None,
                "child_and_extra_bed_policy": {
                    "infant_age": None,
                    "children_age_from": None,
                    "children_age_to": None,
                    "children_stay_free": None,
                    "min_guest_age": None,
                },
                "nationality_restrictions": None,
            },
            "address": {
                "latitude": hotel.get("location", {})
                .get("coordinates", {})
                .get("latitude", None),
                "longitude": hotel.get("location", {})
                .get("coordinates", {})
                .get("longitude", None),
                "address_line_1": address1,
                "address_line_2": None,
                "city": hotel.get("location", {}).get("city", None),
                "state": None,
                "country": None,
                "country_code": hotel.get("location", {}).get("country", None),
                "postal_code": hotel.get("location", {}).get("zipCode", None),
                "full_address": full_address,
                "google_map_site_link": google_map_site_link,
                "local_lang": {
                    "latitude": hotel.get("location", {})
                    .get("coordinates", {})
                    .get("latitude", None),
                    "longitude": hotel.get("location", {})
                    .get("coordinates", {})
                    .get("longitude", None),
                    "address_line_1": address1,
                    "address_line_2": None,
                    "city": hotel.get("location", {}).get("city", None),
                    "state": None,
                    "country": hotel.get("location", {}).get("country", None),
                    "country_code": hotel.get("location", {}).get("countryCode", None),
                    "postal_code": hotel.get("location", {}).get("zipCode", None),
                    "full_address": full_address,
                    "google_map_site_link": google_map_site_link,
                },
                "mapping": {
                    "continent_id": None,
                    "country_id": None,
                    "province_id": None,
                    "state_id": None,
                    "city_id": None,
                    "area_id": None,
                },
            },
            "contacts": {
                "phone_numbers": [safe_get(hotel, ["contact", "telephone"], None)],
                "fax": [safe_get(hotel, ["contact", "fax"], None)],
                "email_address": [safe_get(hotel, ["contact", "email"], None)],
                "website": [safe_get(hotel, ["contact", "web"], None)],
            },
            "descriptions": descriptions,
            "room_type": [
                {
                    "room_id": None,
                    "title": None,
                    "title_lang": None,
                    "room_pic": None,
                    "description": None,
                    "max_allowed": {
                        "total": None,
                        "adults": None,
                        "children": None,
                        "infant": None,
                    },
                    "no_of_room": None,
                    "room_size": None,
                    "bed_type": [
                        {
                            "description": None,
                            "configuration": [],
                            "max_extrabeds": None,
                        }
                    ],
                    "shared_bathroom": None,
                }
            ],
            "spoken_languages": [
                {
                    "type": "spoken_languages",
                    "title": "English",
                    "icon": "mdi mdi-translate-variant",
                }
            ],
            "amenities": amenities,
            "facilities": None,
            "hotel_photo": pictures,
            "point_of_interests": None,
            "nearest_airports": None,
            "train_stations": None,
            "connected_locations": None,
            "stadiums": None,
        }

    elif supplier_code == "letsfly":
        # This is time section
        createdAt = datetime.now()
        createdAt_str = createdAt.strftime("%Y-%m-%dT%H:%M:%S")
        created_at_dt = datetime.strptime(createdAt_str, "%Y-%m-%dT%H:%M:%S")
        timeStamp = int(created_at_dt.timestamp())

        # Safe pass get data.
        def safe_get(d, keys, default=None):
            """Safely navigate through nested dictionaries."""
            for key in keys:
                if isinstance(d, dict):
                    d = d.get(key, default)
                else:
                    return default
            return d

        # --- Base Data ---
        hotel = safe_get(data, ["node", "hotelData"], {})
        if not isinstance(hotel, dict):
            hotel = {}

        # --- Address Section ---
        address1 = safe_get(hotel, ["location", "address"], "")
        full_address = address1 or ""
        google_map_site_link = (
            f"http://maps.google.com/maps?q={full_address.replace(' ', '+')}"
            if full_address
            else None
        )

        # --- Descriptions Section ---
        descriptions = []
        descriptions_data = safe_get(hotel, ["descriptions"], [])
        if isinstance(descriptions_data, list):
            for item in descriptions_data:
                if not isinstance(item, dict):
                    continue
                desc_type = safe_get(item, ["type"], None)
                texts = safe_get(item, ["texts"], [])
                if isinstance(texts, list):
                    for text_item in texts:
                        if isinstance(text_item, dict):
                            descriptions.append(
                                {
                                    "title": desc_type,
                                    "text": text_item.get("text", None),
                                }
                            )

        # --- Amenities Section ---
        amenities = []
        all_amenities = safe_get(hotel, ["allAmenities"], {})
        edges = safe_get(all_amenities, ["edges"], [])
        if isinstance(edges, list):
            for edge in edges:
                amenity = safe_get(edge, ["node", "amenityData"], {})
                title = (
                    safe_get(amenity, ["amenityCode"])
                    if isinstance(amenity, dict)
                    else None
                )
                if title:
                    amenities.append(
                        {
                            "type": "amenity",
                            "title": title,
                            "icon": "mdi mdi-translate-variant",
                        }
                    )

        # --- Images Section ---
        pictures = []
        primary_photo = None
        medias = safe_get(hotel, ["medias"], [])
        if isinstance(medias, list):
            for index, media in enumerate(medias):
                if not isinstance(media, dict):
                    continue
                url = media.get("url")
                if index == 0:
                    primary_photo = url
                pictures.append({"picture_id": None, "title": None, "url": url})

        return {
            "created": createdAt_str,
            "timestamp": timeStamp,
            "hotel_id": hotel.get("hotelCode", None),
            "name": hotel.get("hotelName", None),
            "name_local": hotel.get("hotelName", None),
            "hotel_formerly_name": hotel.get("hotelName", None),
            "destination_code": None,
            "country_code": hotel.get("location", {}).get("country", None),
            "brand_text": None,
            "property_type": hotel.get("propertyType", None),
            "star_rating": hotel.get("categoryCode", None),
            "chain": hotel.get("chainCode", None),
            "brand": None,
            "logo": None,
            "primary_photo": primary_photo,
            "review_rating": {
                "source": None,
                "number_of_reviews": None,
                "rating_average": None,
                "popularity_score": None,
            },
            "policies": {
                "checkin": {
                    "begin_time": hotel.get("checkIn", None),
                    "end_time": hotel.get("checkOut", None),
                    "instructions": None,
                    "min_age": None,
                },
                "checkout": {"time": hotel.get("checkOut", None)},
                "fees": {"optional": None},
                "know_before_you_go": None,
                "pets": None,
                "remark": None,
                "child_and_extra_bed_policy": {
                    "infant_age": None,
                    "children_age_from": None,
                    "children_age_to": None,
                    "children_stay_free": None,
                    "min_guest_age": None,
                },
                "nationality_restrictions": None,
            },
            "address": {
                "latitude": hotel.get("location", {})
                .get("coordinates", {})
                .get("latitude", None),
                "longitude": hotel.get("location", {})
                .get("coordinates", {})
                .get("longitude", None),
                "address_line_1": address1,
                "address_line_2": None,
                "city": hotel.get("location", {}).get("city", None),
                "state": None,
                "country": None,
                "country_code": hotel.get("location", {}).get("country", None),
                "postal_code": hotel.get("location", {}).get("zipCode", None),
                "full_address": full_address,
                "google_map_site_link": google_map_site_link,
                "local_lang": {
                    "latitude": hotel.get("location", {})
                    .get("coordinates", {})
                    .get("latitude", None),
                    "longitude": hotel.get("location", {})
                    .get("coordinates", {})
                    .get("longitude", None),
                    "address_line_1": address1,
                    "address_line_2": None,
                    "city": hotel.get("location", {}).get("city", None),
                    "state": None,
                    "country": hotel.get("location", {}).get("country", None),
                    "country_code": hotel.get("location", {}).get("countryCode", None),
                    "postal_code": hotel.get("location", {}).get("zipCode", None),
                    "full_address": full_address,
                    "google_map_site_link": google_map_site_link,
                },
                "mapping": {
                    "continent_id": None,
                    "country_id": None,
                    "province_id": None,
                    "state_id": None,
                    "city_id": None,
                    "area_id": None,
                },
            },
            "contacts": {
                "phone_numbers": [safe_get(hotel, ["contact", "telephone"], None)],
                "fax": [safe_get(hotel, ["contact", "fax"], None)],
                "email_address": [safe_get(hotel, ["contact", "email"], None)],
                "website": [safe_get(hotel, ["contact", "web"], None)],
            },
            "descriptions": descriptions,
            "room_type": [
                {
                    "room_id": None,
                    "title": None,
                    "title_lang": None,
                    "room_pic": None,
                    "description": None,
                    "max_allowed": {
                        "total": None,
                        "adults": None,
                        "children": None,
                        "infant": None,
                    },
                    "no_of_room": None,
                    "room_size": None,
                    "bed_type": [
                        {
                            "description": None,
                            "configuration": [],
                            "max_extrabeds": None,
                        }
                    ],
                    "shared_bathroom": None,
                }
            ],
            "spoken_languages": [
                {
                    "type": "spoken_languages",
                    "title": "English",
                    "icon": "mdi mdi-translate-variant",
                }
            ],
            "amenities": amenities,
            "facilities": None,
            "hotel_photo": pictures,
            "point_of_interests": None,
            "nearest_airports": None,
            "train_stations": None,
            "connected_locations": None,
            "stadiums": None,
        }

    elif supplier_code == "goglobal":
        # This is time section
        createdAt = datetime.now()
        createdAt_str = createdAt.strftime("%Y-%m-%dT%H:%M:%S")
        created_at_dt = datetime.strptime(createdAt_str, "%Y-%m-%dT%H:%M:%S")
        timeStamp = int(created_at_dt.timestamp())

        # Safe pass get data.
        def safe_get(d, keys, default=None):
            """Safely navigate through nested dictionaries."""
            for key in keys:
                if isinstance(d, dict):
                    d = d.get(key, default)
                else:
                    return default
            return d

        # --- Base Data ---
        hotel = safe_get(data, ["node", "hotelData"], {})
        if not isinstance(hotel, dict):
            hotel = {}

        # --- Address Section ---
        address1 = safe_get(hotel, ["location", "address"], "")
        full_address = address1 or ""
        google_map_site_link = (
            f"http://maps.google.com/maps?q={full_address.replace(' ', '+')}"
            if full_address
            else None
        )

        # --- Descriptions Section ---
        descriptions = []
        descriptions_data = safe_get(hotel, ["descriptions"], [])
        if isinstance(descriptions_data, list):
            for item in descriptions_data:
                if not isinstance(item, dict):
                    continue
                desc_type = item.get("type", None)
                texts = item.get("texts", [])
                if isinstance(texts, list):
                    for text_item in texts:
                        if isinstance(text_item, dict):
                            descriptions.append(
                                {
                                    "title": desc_type,
                                    "text": text_item.get("text", None),
                                }
                            )
        amenities_list_data = []
        for desc in descriptions_data:
            if desc.get("type") == "AMENITY":
                texts = desc.get("texts", [])
                for text_item in texts:
                    if text_item.get("language") == "en":
                        text = text_item.get("text", "")
                        # Split by <BR /> and strip each item
                        amenities_list = [
                            item.strip()
                            for item in text.split("<BR />")
                            if item.strip()
                        ]
                        for amenity in amenities_list:
                            amenities_list_data.append(
                                {
                                    "type": "amenity",
                                    "title": amenity,
                                    "icon": "mdi mdi-translate-variant",
                                }
                            )

        # --- Images Section ---
        pictures = []
        primary_photo = None
        medias = safe_get(hotel, ["medias"], [])
        if isinstance(medias, list):
            for index, media in enumerate(medias):
                if not isinstance(media, dict):
                    continue
                url = media.get("url")
                if index == 0:
                    primary_photo = url
                pictures.append({"picture_id": None, "title": None, "url": url})

        return {
            "created": createdAt_str,
            "timestamp": timeStamp,
            "hotel_id": hotel.get("hotelCode", None),
            "name": hotel.get("hotelName", None),
            "name_local": hotel.get("hotelName", None),
            "hotel_formerly_name": hotel.get("hotelName", None),
            "destination_code": None,
            "country_code": hotel.get("location", {}).get("country", None),
            "brand_text": None,
            "property_type": hotel.get("propertyType", None),
            "star_rating": hotel.get("categoryCode", None),
            "chain": hotel.get("chainCode", None),
            "brand": None,
            "logo": None,
            "primary_photo": primary_photo,
            "review_rating": {
                "source": None,
                "number_of_reviews": None,
                "rating_average": None,
                "popularity_score": None,
            },
            "policies": {
                "checkin": {
                    "begin_time": hotel.get("checkIn", None),
                    "end_time": hotel.get("checkOut", None),
                    "instructions": None,
                    "min_age": None,
                },
                "checkout": {"time": hotel.get("checkOut", None)},
                "fees": {"optional": None},
                "know_before_you_go": None,
                "pets": None,
                "remark": None,
                "child_and_extra_bed_policy": {
                    "infant_age": None,
                    "children_age_from": None,
                    "children_age_to": None,
                    "children_stay_free": None,
                    "min_guest_age": None,
                },
                "nationality_restrictions": None,
            },
            "address": {
                "latitude": hotel.get("location", {})
                .get("coordinates", {})
                .get("latitude", None),
                "longitude": hotel.get("location", {})
                .get("coordinates", {})
                .get("longitude", None),
                "address_line_1": address1,
                "address_line_2": None,
                "city": hotel.get("location", {}).get("city", None),
                "state": None,
                "country": None,
                "country_code": hotel.get("location", {}).get("country", None),
                "postal_code": hotel.get("location", {}).get("zipCode", None),
                "full_address": full_address,
                "google_map_site_link": google_map_site_link,
                "local_lang": {
                    "latitude": hotel.get("location", {})
                    .get("coordinates", {})
                    .get("latitude", None),
                    "longitude": hotel.get("location", {})
                    .get("coordinates", {})
                    .get("longitude", None),
                    "address_line_1": address1,
                    "address_line_2": None,
                    "city": hotel.get("location", {}).get("city", None),
                    "state": None,
                    "country": hotel.get("location", {}).get("country", None),
                    "country_code": hotel.get("location", {}).get("countryCode", None),
                    "postal_code": hotel.get("location", {}).get("zipCode", None),
                    "full_address": full_address,
                    "google_map_site_link": google_map_site_link,
                },
                "mapping": {
                    "continent_id": None,
                    "country_id": None,
                    "province_id": None,
                    "state_id": None,
                    "city_id": None,
                    "area_id": None,
                },
            },
            "contacts": {
                "phone_numbers": [hotel.get("contact", {}).get("telephone", None)],
                "fax": [hotel.get("contact", {}).get("fax", None)],
                "email_address": [hotel.get("contact", {}).get("email", None)],
                "website": [hotel.get("contact", {}).get("web", None)],
            },
            "descriptions": descriptions,
            "room_type": [
                {
                    "room_id": None,
                    "title": None,
                    "title_lang": None,
                    "room_pic": None,
                    "description": None,
                    "max_allowed": {
                        "total": None,
                        "adults": None,
                        "children": None,
                        "infant": None,
                    },
                    "no_of_room": None,
                    "room_size": None,
                    "bed_type": [
                        {
                            "description": None,
                            "configuration": [],
                            "max_extrabeds": None,
                        }
                    ],
                    "shared_bathroom": None,
                }
            ],
            "spoken_languages": [
                {
                    "type": "spoken_languages",
                    "title": "English",
                    "icon": "mdi mdi-translate-variant",
                }
            ],
            "amenities": amenities_list_data,
            "facilities": None,
            "hotel_photo": pictures,
            "point_of_interests": None,
            "nearest_airports": None,
            "train_stations": None,
            "connected_locations": None,
            "stadiums": None,
        }

    elif supplier_code == "juniperhotel":
        createdAt = datetime.now()
        createdAt_str = createdAt.strftime("%Y-%m-%dT%H:%M:%S")
        created_at_dt = datetime.strptime(createdAt_str, "%Y-%m-%dT%H:%M:%S")
        timeStamp = int(created_at_dt.timestamp())

        def safe_get(d, keys, default=None):
            """Safely navigate through nested dicts."""
            for key in keys:
                if isinstance(d, dict):
                    d = d.get(key, default)
                else:
                    return default
            return d

        # --- Extract base hotel data ---
        hotel = safe_get(
            data,
            [
                "soap:Envelope",
                "soap:Body",
                "HotelContentResponse",
                "ContentRS",
                "Contents",
                "HotelContent",
            ],
            {},
        )

        # --- Address section ---
        address_obj = safe_get(hotel, ["Address"], {})
        full_address = address_obj.get("Address", "")
        google_map_site_link = (
            f"http://maps.google.com/maps?q={full_address.replace(' ', '+')}"
            if full_address
            else None
        )

        # --- Extract room list ---
        room_details = safe_get(
            data,
            [
                "soap:Envelope",
                "soap:Body",
                "HotelContentResponse",
                "ContentRS",
                "Contents",
                "HotelContent",
                "HotelRooms",
                "HotelRoom",
            ],
            [],
        )

        room_type = []
        for idx, room in enumerate(
            room_details if isinstance(room_details, list) else []
        ):
            name = room.get("Name", "")
            description = room.get("Description", "")
            occupancy = room.get("RoomOccupancy", {})

            max_adults = (
                int(occupancy.get("@MaxAdults", 0))
                if isinstance(occupancy, dict)
                else 0
            )
            max_children = (
                int(occupancy.get("@MaxChildren", 0))
                if isinstance(occupancy, dict)
                else 0
            )

            # Try to extract room size from description (e.g. "size_room:25")
            room_size = None
            if isinstance(description, str) and "size_room:" in description:
                try:
                    room_size = int(description.split("size_room:")[-1].strip())
                except:
                    room_size = None

            room_type.append(
                {
                    "room_id": None,
                    "title": name,
                    "title_lang": None,
                    "room_pic": None,
                    "description": description,
                    "max_allowed": {
                        "total": max_adults + max_children,
                        "adults": max_adults,
                        "children": max_children,
                        "infant": None,
                    },
                    "no_of_room": None,
                    "room_size": room_size,
                    "bed_type": [
                        {
                            "description": None,
                            "configuration": [],
                            "max_extrabeds": None,
                        }
                    ],
                    "shared_bathroom": None,
                }
            )

        # --- Remove duplicates ---
        unique_rooms = []
        seen = set()
        for room in room_type:
            room_str = json.dumps(room, sort_keys=True)
            if room_str not in seen:
                seen.add(room_str)
                unique_rooms.append(room)

        # --- Descriptions section ---
        description_all = safe_get(
            data,
            [
                "soap:Envelope",
                "soap:Body",
                "HotelContentResponse",
                "ContentRS",
                "Contents",
                "HotelContent",
                "Descriptions",
                "Description",
            ],
            [],
        )

        description_text = []
        for desc in description_all if isinstance(description_all, list) else []:
            description_text.append(
                {"title": desc.get("@Type", None), "text": desc.get("#text", None)}
            )

        # --- Facilities section ---
        room_facilities = safe_get(
            data,
            [
                "soap:Envelope",
                "soap:Body",
                "HotelContentResponse",
                "ContentRS",
                "Contents",
                "HotelContent",
                "Features",
                "Feature",
            ],
            [],
        )

        facilities = []
        for feature in room_facilities if isinstance(room_facilities, list) else []:
            facilities.append(
                {
                    "type": feature.get("@Type", None),
                    "title": feature.get("#text", None),
                    "icon": "mdi mdi-translate-variant",
                }
            )

        # --- Image section ---
        images_all = safe_get(
            data,
            [
                "soap:Envelope",
                "soap:Body",
                "HotelContentResponse",
                "ContentRS",
                "Contents",
                "HotelContent",
                "Images",
                "Image",
            ],
            [],
        )

        pictures = []
        primary_photo = None
        for image in images_all if isinstance(images_all, list) else []:
            url = safe_get(image, ["FileName"], "")
            pictures.append(
                {"picture_id": None, "title": image.get("Title", ""), "url": url}
            )
            if not primary_photo and image.get("@Type") == "BIG":
                primary_photo = url

        star_rating = safe_get(hotel, ["HotelCategory"], None)

        star_rating = safe_get(hotel, ["HotelCategory"], None)

        if isinstance(star_rating, dict):
            # Try different possible keys
            star_rating = star_rating.get("@Code") or star_rating.get("#text")

        if isinstance(star_rating, str):
            match = re.search(r"\d+", star_rating)
            star_rating = match.group(0) if match else None
        else:
            star_rating = None

        def extract_text_list(obj):
            """
            Normalize SOAP-style dict/list into a list of #text values.
            Accepts dict, list, or plain string.
            """
            if isinstance(obj, dict):
                if "#text" in obj:
                    return [obj["#text"]]
                return []
            elif isinstance(obj, list):
                return [
                    item.get("#text")
                    for item in obj
                    if isinstance(item, dict) and item.get("#text")
                ]
            elif isinstance(obj, str):
                return [obj]
            return []

        # --- Contacts section ---
        contact_info = safe_get(hotel, ["ContactInfo"], {})

        phone_numbers = extract_text_list(
            safe_get(contact_info, ["PhoneNumbers", "PhoneNumber"], [])
        )
        fax_numbers = extract_text_list(safe_get(contact_info, ["Faxes", "Fax"], []))
        emails = extract_text_list(safe_get(contact_info, ["Emails", "Email"], []))
        websites = extract_text_list(
            safe_get(contact_info, ["Websites", "Website"], [])
        )

        return {
            "created": createdAt_str,
            "timestamp": timeStamp,
            "hotel_id": safe_get(hotel, ["@JPCode"], None),
            "name": safe_get(hotel, ["HotelName"], None),
            "name_local": safe_get(hotel, ["HotelName"], None),
            "hotel_formerly_name": safe_get(hotel, ["HotelName"], None),
            "destination_code": None,
            "country_code": None,
            "brand_text": None,
            "property_type": None,
            "star_rating": star_rating,
            "chain": safe_get(hotel, ["HotelChain", "Name"], None),
            "brand": None,
            "logo": None,
            "primary_photo": primary_photo,
            "review_rating": {
                "source": None,
                "number_of_reviews": None,
                "rating_average": None,
                "popularity_score": None,
            },
            "policies": {
                "checkin": {
                    "begin_time": safe_get(
                        hotel, ["TimeInformation", "CheckTime", "@CheckIn"], None
                    ),
                    "end_time": safe_get(
                        hotel, ["TimeInformation", "CheckTime", "@CheckOut"], None
                    ),
                    "instructions": None,
                    "min_age": None,
                },
                "checkout": {
                    "time": safe_get(
                        hotel, ["TimeInformation", "CheckTime", "@CheckOut"], None
                    ),
                },
                "fees": {"optional": None},
                "know_before_you_go": None,
                "pets": None,
                "remark": None,
                "child_and_extra_bed_policy": {
                    "infant_age": None,
                    "children_age_from": None,
                    "children_age_to": None,
                    "children_stay_free": None,
                    "min_guest_age": None,
                },
                "nationality_restrictions": None,
            },
            "address": {
                "latitude": safe_get(hotel, ["Address", "Latitude"], None),
                "longitude": safe_get(hotel, ["Address", "Longitude"], None),
                "address_line_1": safe_get(hotel, ["Address", "Address"], None),
                "address_line_2": None,
                "city": None,
                "state": None,
                "country": None,
                "country_code": None,
                "postal_code": safe_get(hotel, ["Address", "PostalCode"], None),
                "full_address": full_address,
                "google_map_site_link": google_map_site_link,
                "local_lang": {
                    "latitude": safe_get(hotel, ["Address", "Latitude"], None),
                    "longitude": safe_get(hotel, ["Address", "Longitude"], None),
                    "address_line_1": safe_get(hotel, ["Address", "Address"], None),
                    "address_line_2": None,
                    "city": None,
                    "state": None,
                    "country": None,
                    "country_code": None,
                    "postal_code": safe_get(hotel, ["Address", "PostalCode"], None),
                    "full_address": full_address,
                    "google_map_site_link": google_map_site_link,
                },
                "mapping": {
                    "continent_id": None,
                    "country_id": None,
                    "province_id": None,
                    "state_id": None,
                    "city_id": None,
                    "area_id": None,
                },
            },
            "contacts": {
                "phone_numbers": phone_numbers,
                "fax": fax_numbers,
                "email_address": emails,
                "website": websites,
            },
            "descriptions": description_text,
            "room_type": unique_rooms,
            "spoken_languages": [
                {
                    "type": "spoken_languages",
                    "title": "English",
                    "icon": "mdi mdi-translate-variant",
                }
            ],
            "amenities": None,
            "facilities": facilities,
            "hotel_photo": pictures,
            "point_of_interests": None,
            "nearest_airports": None,
            "train_stations": None,
            "connected_locations": None,
            "stadiums": None,
        }

    elif supplier_code == "innstant":
        createdAt = datetime.now()
        createdAt_str = createdAt.strftime("%Y-%m-%dT%H:%M:%S")
        created_at_dt = datetime.strptime(createdAt_str, "%Y-%m-%dT%H:%M:%S")
        timeStamp = int(created_at_dt.timestamp())

        # Base data path
        hotel = data[0] if isinstance(data, list) and data else {}

        def get_innstanttravel_location_info(hotel_code):
            filepath = os.path.join(INSTANTTRAVEL_STATIC_DIR, "innstanttravel_raw.txt")

            with open(filepath, newline="", encoding="utf-8-sig") as csvfile:
                reader = csv.DictReader(csvfile)

                for row in reader:
                    innstanttravel_val = row.get("innstanttravel", "").strip('"')
                    innstanttravel_a_val = row.get("innstanttravel_a", "").strip('"')
                    innstanttravel_b_val = row.get("innstanttravel_b", "").strip('"')
                    innstanttravel_c_val = row.get("innstanttravel_c", "").strip('"')
                    innstanttravel_d_val = row.get("innstanttravel_d", "").strip('"')
                    innstanttravel_e_val = row.get("innstanttravel_e", "").strip('"')

                    if (
                        innstanttravel_val == str(hotel_code)
                        or innstanttravel_a_val == str(hotel_code)
                        or innstanttravel_b_val == str(hotel_code)
                        or innstanttravel_c_val == str(hotel_code)
                        or innstanttravel_d_val == str(hotel_code)
                        or innstanttravel_e_val == str(hotel_code)
                    ):
                        return {
                            "CityName": row["CityName"] if row["CityName"] else None,
                            "CountryName": (
                                row["CountryName"] if row["CountryName"] else None
                            ),
                            "CountryCode": (
                                row["CountryCode"] if row["CountryCode"] else None
                            ),
                            "StateName": (
                                row["StateName"] if row["StateName"] else None
                            ),
                            "PropertyType": (
                                row["PropertyType"] if row["PropertyType"] else None
                            ),
                            "Rating": (row["Rating"] if row["Rating"] else None),
                        }
            return None

        hotel_code = hotel.get("id", None)

        # Here get location info from txt file.
        if hotel_code:
            location_info = get_innstanttravel_location_info(hotel_code)

            if location_info:
                CountryCode = location_info["CountryCode"]
                CountryName = location_info["CountryName"]
                CityName = location_info["CityName"]
                StateName = location_info["StateName"]
                PropertyType = location_info["PropertyType"]
                Rating = location_info["Rating"]
            else:
                CountryCode = None
                CountryName = None
                CityName = None
                StateName = None
                PropertyType = None
                Rating = None

        # --- Address ---
        address1 = hotel.get("address") if isinstance(hotel, dict) else None
        full_address = address1 if isinstance(address1, str) else None
        google_map_site_link = (
            f"http://maps.google.com/maps?q={full_address.replace(' ', '+')}"
            if full_address
            else None
        )

        # --- Facilities Section ---
        facilities = []
        facility_data = hotel.get("facilities", {}) if isinstance(hotel, dict) else {}
        tags = facility_data.get("tags", []) if isinstance(facility_data, dict) else []
        titles = (
            facility_data.get("list", []) if isinstance(facility_data, dict) else []
        )

        # Safely match tags and titles
        for idx in range(min(len(tags), len(titles))):
            facilities.append(
                {
                    "type": tags[idx],
                    "title": titles[idx],
                    "icon": "mdi mdi-translate-variant",
                }
            )

        # --- Pictures Section ---
        pictures = []
        images = hotel.get("images", []) if isinstance(hotel, dict) else []
        main_image_id = hotel.get("mainImageId") if isinstance(hotel, dict) else None

        primary_photo = None
        for image in images if isinstance(images, list) else []:
            if not isinstance(image, dict):
                continue
            image_id = image.get("id")
            width = image.get("width", 800)
            height = image.get("height", 600)
            image_url = image.get("url", "")

            url = (
                f"https://cdn-images.innstant-servers.com/{width}x{height}/{image_url}"
                if image_url
                else None
            )

            if image_id == main_image_id:
                primary_photo = url

            pictures.append(
                {"picture_id": image_id, "title": image.get("title"), "url": url}
            )

        return {
            "created": createdAt_str,
            "timestamp": timeStamp,
            "hotel_id": hotel.get("id", None),
            "name": hotel.get("name", None),
            "name_local": hotel.get("name", None),
            "hotel_formerly_name": hotel.get("name", None),
            "destination_code": None,
            "country_code": CountryCode,
            "brand_text": None,
            "property_type": PropertyType,
            "star_rating": hotel.get("stars", None),
            "chain": None,
            "brand": None,
            "logo": None,
            "primary_photo": primary_photo,
            "review_rating": {
                "source": None,
                "number_of_reviews": None,
                "rating_average": None,
                "popularity_score": None,
            },
            "policies": {
                "checkin": {
                    "begin_time": None,
                    "end_time": None,
                    "instructions": None,
                    "min_age": None,
                },
                "checkout": {"time": None},
                "fees": {"optional": None},
                "know_before_you_go": None,
                "pets": None,
                "remark": None,
                "child_and_extra_bed_policy": {
                    "infant_age": None,
                    "children_age_from": None,
                    "children_age_to": None,
                    "children_stay_free": None,
                    "min_guest_age": None,
                },
                "nationality_restrictions": None,
            },
            "address": {
                "latitude": hotel.get("lat", None),
                "longitude": hotel.get("lon", None),
                "address_line_1": address1,
                "address_line_2": None,
                "city": CityName,
                "state": StateName,
                "country": CountryName,
                "country_code": CountryCode,
                "postal_code": hotel.get("zip", None),
                "full_address": f"{full_address}, {CityName}, {CountryName}",
                "google_map_site_link": google_map_site_link,
                "local_lang": {
                    "latitude": hotel.get("lat", None),
                    "longitude": hotel.get("lon", None),
                    "address_line_1": address1,
                    "address_line_2": None,
                    "city": CityName,
                    "state": StateName,
                    "country": CountryName,
                    "country_code": CountryCode,
                    "postal_code": hotel.get("zip", None),
                    "full_address": f"{full_address}, {CityName}, {CountryName}",
                    "google_map_site_link": google_map_site_link,
                },
                "mapping": {
                    "continent_id": None,
                    "country_id": None,
                    "province_id": None,
                    "state_id": None,
                    "city_id": None,
                    "area_id": None,
                },
            },
            "contacts": {
                "phone_numbers": [hotel.get("phone", None)],
                "fax": [hotel.get("fax", None)],
                "email_address": [hotel.get("email", None)],
                "website": [hotel.get("web", None)],
            },
            "descriptions": [{"title": None, "text": hotel.get("description", None)}],
            "room_type": None,
            "spoken_languages": [
                {
                    "type": "spoken_languages",
                    "title": "English",
                    "icon": "mdi mdi-translate-variant",
                }
            ],
            "amenities": None,
            "facilities": facilities,
            "hotel_photo": pictures,
            "point_of_interests": None,
            "nearest_airports": None,
            "train_stations": None,
            "connected_locations": None,
            "stadiums": None,
        }

    elif supplier_code == "restel":
        createdAt = datetime.now()
        createdAt_str = createdAt.strftime("%Y-%m-%dT%H:%M:%S")
        created_at_dt = datetime.strptime(createdAt_str, "%Y-%m-%dT%H:%M:%S")
        timeStamp = int(created_at_dt.timestamp())

        # Base path
        hotel = data.get("respuesta", {}) if isinstance(data, dict) else {}
        parametros = hotel.get("parametros", {}) if isinstance(hotel, dict) else {}
        hotel_data = parametros.get("hotel", {}) if isinstance(parametros, dict) else {}

        # Address and Google Map Link
        address1 = hotel_data.get("direccion") if isinstance(hotel_data, dict) else None
        full_address = address1 if isinstance(address1, str) else None
        google_map_site_link = (
            f"http://maps.google.com/maps?q={full_address.replace(' ', '+')}"
            if full_address
            else None
        )

        # Photo URLs
        foto_urls = (
            hotel_data.get("fotos", {}).get("foto", [])
            if isinstance(hotel_data.get("fotos", {}), dict)
            else []
        )

        # Ensure foto_urls is always a list
        if isinstance(foto_urls, str):
            foto_urls = [foto_urls]
        elif not isinstance(foto_urls, list):
            foto_urls = []

        # Build the hotel_photo list
        hotel_photo = []
        for url in foto_urls:
            if isinstance(url, str):
                hotel_photo.append({"picture_id": None, "title": None, "url": url})

        # Pick the primary photo (first in the list)
        primary_photo = hotel_photo[0]["url"] if hotel_photo else None

        # Extract service list safely
        facilities_urls = (
            hotel_data.get("servicios", {}).get("servicio", [])
            if isinstance(hotel_data.get("servicios", {}), dict)
            else []
        )

        # Format facilities
        facilities = []
        for service in facilities_urls:
            desc = service.get("desc_serv")
            if desc:
                facilities.append(
                    {"type": desc, "title": desc, "icon": "mdi mdi-translate-variant"}
                )

        return {
            "created": createdAt_str,
            "timestamp": timeStamp,
            "hotel_id": hotel_data.get("codigo_hotel", None),
            "name": hotel_data.get("nombre_h", None),
            "name_local": hotel_data.get("nombre_h", None),
            "hotel_formerly_name": hotel_data.get("nombre_h", None),
            "destination_code": hotel_data.get("coddestino", None),
            "country_code": hotel_data.get("pais", None),
            "brand_text": None,
            "property_type": hotel_data.get("tipo", None),
            "star_rating": hotel_data.get("categoria", None),
            "chain": None,
            "brand": None,
            "logo": None,
            "primary_photo": primary_photo,
            "review_rating": {
                "source": None,
                "number_of_reviews": None,
                "rating_average": None,
                "popularity_score": None,
            },
            "policies": {
                "checkin": {
                    "begin_time": hotel_data.get("checkin", None),
                    "end_time": hotel_data.get("checkout", None),
                    "instructions": None,
                    "min_age": None,
                },
                "checkout": {"time": hotel_data.get("checkout", None)},
                "fees": {"optional": None},
                "know_before_you_go": None,
                "pets": None,
                "remark": None,
                "child_and_extra_bed_policy": {
                    "infant_age": None,
                    "children_age_from": None,
                    "children_age_to": None,
                    "children_stay_free": None,
                    "min_guest_age": None,
                },
                "nationality_restrictions": None,
            },
            "address": {
                "latitude": hotel_data.get("latitud", None),
                "longitude": hotel_data.get("longitud", None),
                "address_line_1": address1,
                "address_line_2": None,
                "city": hotel_data.get("poblacion", None),
                "state": hotel_data.get("provincia", None),
                "country": None,
                "country_code": hotel_data.get("pais", None),
                "postal_code": hotel_data.get("cp", None),
                "full_address": f"{full_address}, {hotel_data.get('poblacion', None)}",
                "google_map_site_link": google_map_site_link,
                "local_lang": {
                    "latitude": hotel_data.get("latitud", None),
                    "longitude": hotel_data.get("longitud", None),
                    "address_line_1": address1,
                    "address_line_2": None,
                    "city": hotel_data.get("poblacion", None),
                    "state": hotel_data.get("provincia", None),
                    "country": None,
                    "country_code": hotel_data.get("pais", None),
                    "postal_code": hotel_data.get("cp", None),
                    "full_address": f"{full_address}, {hotel_data.get('poblacion', None)}",
                    "google_map_site_link": google_map_site_link,
                },
                "mapping": {
                    "continent_id": None,
                    "country_id": None,
                    "province_id": None,
                    "state_id": None,
                    "city_id": None,
                    "area_id": None,
                },
            },
            "contacts": {
                "phone_numbers": [hotel_data.get("telefono", None)],
                "fax": [hotel_data.get("fax", None)],
                "email_address": [hotel_data.get("mail", None)],
                "website": [hotel_data.get("web", None)],
            },
            "descriptions": [
                {"title": None, "text": hotel_data.get("desc_hotel", None)}
            ],
            "room_type": [],
            "spoken_languages": [],
            "amenities": [],
            "facilities": facilities,
            "hotel_photo": hotel_photo,
            "point_of_interests": [],
            "nearest_airports": [],
            "train_stations": [],
            "connected_locations": [],
            "stadiums": [],
        }

    elif supplier_code == "ratehawkhotel":
        createdAt = datetime.now()
        createdAt_str = createdAt.strftime("%Y-%m-%dT%H:%M:%S")
        created_at_dt = datetime.strptime(createdAt_str, "%Y-%m-%dT%H:%M:%S")
        timeStamp = int(created_at_dt.timestamp())

        # Safe pass get data.
        def safe_get(d, keys, default=None):
            """Safely navigate through nested dictionaries."""
            for key in keys:
                if isinstance(d, dict):
                    d = d.get(key, default)
                else:
                    return default
            return d

        # Base URL
        hotel = safe_get(data, ["hotel_info"], {})

        # This is address section.add()
        address1 = safe_get(hotel, ["address"], None)
        full_address = address1
        google_map_site_link = (
            f"http://maps.google.com/maps?q={full_address.replace(' ', '+')}"
            if full_address
            else None
        )

        # This is image section.
        images = ast.literal_eval(safe_get(hotel, ["images_ext"], "[]"))

        # 2â€“4. Build pictures list and pick primary_photo
        size_str = "1024x768"
        pictures = []
        primary_photo = None

        for img in images:
            url = img["url"].replace("{size}", size_str)
            title = img["category_slug"]
            pic_dict = {"picture_id": None, "title": title, "url": url}
            pictures.append(pic_dict)
            # pick first 'hotel_front' as primary
            if primary_photo is None and title == "hotel_front":
                primary_photo = url

        # if no 'hotel_front', fallback to first image URL (if any)
        if primary_photo is None and pictures:
            primary_photo = pictures[0]["url"]

        # Safely parse the string to a dictionary
        region_str = safe_get(hotel, ["region"], "{}")
        region_dict = ast.literal_eval(region_str)

        # This is for amenities grouping.
        groups = ast.literal_eval(safe_get(hotel, ["amenity_groups"], "[]"))

        amenities = []
        for grp in groups:
            for amen in grp["amenities"]:
                amenities.append(
                    {"type": amen, "title": amen, "icon": "mdi mdi-translate-variant"}
                )

        # Description
        sections = ast.literal_eval(safe_get(hotel, ["description_struct"], "[]"))

        description_flat = []
        for sec in sections:
            title = sec["title"]
            # join paragraphs with double-newlines (or however you like)
            text = "\n\n".join(sec["paragraphs"])
            description_flat.append({"title": title, "text": text})

        # Facilities
        serp_list = ast.literal_eval(safe_get(hotel, ["serp_filters"], "[]"))

        facilities = []
        for fac in serp_list:
            facilities.append(
                {"title": fac, "text": fac, "icon": "mdi mdi-translate-variant"}
            )

        return {
            "created": createdAt_str,
            "timestamp": timeStamp,
            "hotel_id": safe_get(hotel, ["hotel_code"], None),
            "name": safe_get(hotel, ["name"], None),
            "name_local": safe_get(hotel, ["name"], None),
            "hotel_formerly_name": safe_get(hotel, ["name"], None),
            "destination_code": None,
            "country_code": safe_get(region_dict, ["country_code"], None),
            "brand_text": None,
            "property_type": safe_get(hotel, ["kind"], None),
            "star_rating": safe_get(hotel, ["star_rating"], None),
            "chain": safe_get(hotel, ["hotel_chain"], None),
            "brand": None,
            "logo": None,
            "primary_photo": primary_photo,
            "review_rating": {
                "source": None,
                "number_of_reviews": None,
                "rating_average": None,
                "popularity_score": None,
            },
            "policies": {
                "checkin": {
                    "begin_time": safe_get(hotel, ["check_in_time"], None),
                    "end_time": safe_get(hotel, ["check_out_time"], None),
                    "instructions": None,
                    "min_age": None,
                },
                "checkout": {"time": safe_get(hotel, ["check_out_time"], None)},
                "fees": {"optional": None},
                "know_before_you_go": None,
                "pets": [],
                "remark": None,
                "child_and_extra_bed_policy": {
                    "infant_age": None,
                    "children_age_from": None,
                    "children_age_to": None,
                    "children_stay_free": None,
                    "min_guest_age": None,
                },
                "nationality_restrictions": None,
            },
            "address": {
                "latitude": safe_get(hotel, ["latitude"], None),
                "longitude": safe_get(hotel, ["longitude"], None),
                "address_line_1": address1,
                "address_line_2": None,
                "city": safe_get(region_dict, ["name"], None),
                "state": None,
                "country": None,
                "country_code": safe_get(region_dict, ["country_code"], None),
                "postal_code": safe_get(hotel, ["postal_code"], None),
                "full_address": full_address,
                "google_map_site_link": google_map_site_link,
                "local_lang": {
                    "latitude": safe_get(hotel, ["latitude"], None),
                    "longitude": safe_get(hotel, ["longitude"], None),
                    "address_line_1": address1,
                    "address_line_2": None,
                    "city": safe_get(region_dict, ["name"], None),
                    "state": None,
                    "country": None,
                    "country_code": safe_get(region_dict, ["country_code"], None),
                    "postal_code": safe_get(hotel, ["postal_code"], None),
                    "full_address": full_address,
                    "google_map_site_link": google_map_site_link,
                },
                "mapping": {
                    "continent_id": None,
                    "country_id": None,
                    "province_id": None,
                    "state_id": None,
                    "city_id": None,
                    "area_id": None,
                },
            },
            "contacts": {
                "phone_numbers": [safe_get(hotel, ["phone"], None)],
                "fax": [safe_get(hotel, ["fax"], None)],
                "email_address": [safe_get(hotel, ["email"], None)],
                "website": [safe_get(hotel, ["web"], None)],
            },
            "descriptions": description_flat,
            "room_type": [
                {
                    "room_id": None,
                    "title": None,
                    "title_lang": None,
                    "room_pic": None,
                    "description": None,
                    "max_allowed": {
                        "total": None,
                        "adults": None,
                        "children": None,
                        "infant": None,
                    },
                    "no_of_room": None,
                    "room_size": None,
                    "bed_type": [
                        {
                            "description": None,
                            "configuration": [],
                            "max_extrabeds": None,
                        }
                    ],
                    "shared_bathroom": None,
                }
            ],
            "spoken_languages": [
                {
                    "type": "spoken_languages",
                    "title": "English",
                    "icon": "mdi mdi-translate-variant",
                }
            ],
            "amenities": amenities,
            "facilities": facilities,
            "hotel_photo": pictures,
            "point_of_interests": None,
            "nearest_airports": None,
            "train_stations": None,
            "connected_locations": None,
            "stadiums": None,
        }

    elif supplier_code == "ratehawk_new":
        createdAt = datetime.now()
        createdAt_str = createdAt.strftime("%Y-%m-%dT%H:%M:%S")
        created_at_dt = datetime.strptime(createdAt_str, "%Y-%m-%dT%H:%M:%S")
        timeStamp = int(created_at_dt.timestamp())

        # Safe pass get data.
        def safe_get(d, keys, default=None):
            """Safely navigate through nested dictionaries."""
            for key in keys:
                if isinstance(d, dict):
                    d = d.get(key, default)
                else:
                    return default
            return d

        # Base URL
        hotel = safe_get(data, ["data"], {})

        # This is address section.add()
        address1 = safe_get(hotel, ["address"], None)
        full_address = address1
        google_map_site_link = (
            f"http://maps.google.com/maps?q={full_address.replace(' ', '+')}"
            if full_address
            else None
        )

        # This is image section.
        images = safe_get(hotel, ["images_ext"], "[]")

        # 2â€“4. Build pictures list and pick primary_photo
        size_str = "1024x768"
        pictures = []
        primary_photo = None

        for img in images:
            url = img["url"].replace("{size}", size_str)
            title = img["category_slug"]
            pic_dict = {"picture_id": None, "title": title, "url": url}
            pictures.append(pic_dict)
            # pick first 'hotel_front' as primary
            if primary_photo is None and title == "hotel_front":
                primary_photo = url

        # if no 'hotel_front', fallback to first image URL (if any)
        if primary_photo is None and pictures:
            primary_photo = pictures[0]["url"]

        # Safely parse the string to a dictionary
        region_str = safe_get(hotel, ["region"], "{}")

        # This is for amenities grouping.
        groups = safe_get(hotel, ["amenity_groups"], [])

        amenities = []
        spoken_languages = []

        for grp in groups:
            group_name = safe_get(grp, ["group_name"], "")
            for amen in safe_get(grp, ["amenities"], []):
                item = {
                    "type": group_name,
                    "title": amen,
                    "icon": "mdi mdi-translate-variant",
                }

                if group_name == "Languages Spoken":
                    # Special case → goes into spoken_languages
                    spoken_languages.append(
                        {
                            "type": "spoken_languages",
                            "title": amen,
                            "icon": "mdi mdi-translate-variant",
                        }
                    )
                else:
                    amenities.append(item)

        # Description
        sections = safe_get(hotel, ["description_struct"], []) or []

        description_flat = []
        for sec in sections:
            title = safe_get(sec, ["title"], "")
            # join paragraphs with double-newlines (or however you like)
            text = "\n\n".join(safe_get(sec, ["paragraphs"], []))
            description_flat.append({"title": title, "text": text})

        # Facilities
        serp_list = safe_get(hotel, ["serp_filters"], "[]") or []

        facilities = [
            {"title": fac, "text": fac, "icon": "mdi mdi-translate-variant"}
            for fac in serp_list
        ]

        room_data = safe_get(hotel, ["room_groups"], []) or []

        room_types = []

        for idx, room in enumerate(room_data):
            room_id = str(room.get("room_group_id", idx)).zfill(
                12
            )  # 12-digit padded ID
            title = safe_get(room, ["name"], "n/a")
            title_lang = safe_get(room, ["name_struct", "main_name"], title)
            description = title

            # First image → main picture
            room_pic = None
            if safe_get(room, ["images"]):
                room_pic = safe_get(room, ["images", 0], "").replace(
                    "{size}", "1024x768"
                )

            # Additional images
            additional_images = []
            for img in safe_get(room, ["images"], []) or []:
                additional_images.append(
                    {"title": None, "url": img.replace("{size}", "1024x768")}
                )

            # Shared bathroom (if flagged in name_struct / rg_ext)
            shared_bathroom = safe_get(room, ["name_struct", "bathroom"], "n/a")

            room_obj = {
                "room_id": room_id,
                "title": title,
                "title_lang": title_lang,
                "room_pic": room_pic,
                "description": description,
                "max_allowed": {
                    "total": "n/a",
                    "adults": "n/a",
                    "children": "n/a",
                    "infant": "n/a",
                },
                "no_of_room": "n/a",
                "room_size": "n/a",
                "shared_bathroom": shared_bathroom,
                "views": [None],
                "additional_images": additional_images,
            }

            # If amenities exist → include them
            if room.get("room_amenities"):
                room_obj["amenities"] = room["room_amenities"]

            room_types.append(room_obj)

        return {
            "created": createdAt_str,
            "timestamp": timeStamp,
            "hotel_id": safe_get(hotel, ["id"], None),
            "name": safe_get(hotel, ["name"], None),
            "name_local": safe_get(hotel, ["name"], None),
            "hotel_formerly_name": safe_get(hotel, ["name"], None),
            "destination_code": None,
            "country_code": safe_get(region_str, ["country_code"], None),
            "brand_text": None,
            "property_type": safe_get(hotel, ["kind"], None),
            "star_rating": str(safe_get(hotel, ["star_rating"], "")),
            "chain": safe_get(hotel, ["hotel_chain"], None),
            "brand": None,
            "logo": None,
            "primary_photo": primary_photo,
            "review_rating": {
                "source": None,
                "number_of_reviews": None,
                "rating_average": None,
                "popularity_score": None,
            },
            "policies": {
                "checkin": {
                    "begin_time": safe_get(hotel, ["check_in_time"], None),
                    "end_time": safe_get(hotel, ["check_out_time"], None),
                    "instructions": None,
                    "min_age": None,
                },
                "checkout": {"time": safe_get(hotel, ["check_out_time"], None)},
                "fees": {"optional": None},
                "know_before_you_go": None,
                "pets": [None],
                "remark": safe_get(hotel, ["metapolicy_extra_info"], None),
                "child_and_extra_bed_policy": {
                    "infant_age": None,
                    "children_age_from": None,
                    "children_age_to": None,
                    "children_stay_free": None,
                    "min_guest_age": None,
                },
                "nationality_restrictions": None,
            },
            "address": {
                "latitude": safe_get(hotel, ["latitude"], None),
                "longitude": safe_get(hotel, ["longitude"], None),
                "address_line_1": address1,
                "address_line_2": None,
                "city": safe_get(region_str, ["name"], None),
                "state": None,
                "country": None,
                "country_code": safe_get(region_str, ["country_code"], None),
                "postal_code": safe_get(hotel, ["postal_code"], None),
                "full_address": full_address,
                "google_map_site_link": google_map_site_link,
                "local_lang": {
                    "latitude": safe_get(hotel, ["latitude"], None),
                    "longitude": safe_get(hotel, ["longitude"], None),
                    "address_line_1": address1,
                    "address_line_2": None,
                    "city": safe_get(region_str, ["name"], None),
                    "state": None,
                    "country": None,
                    "country_code": safe_get(region_str, ["country_code"], None),
                    "postal_code": safe_get(hotel, ["postal_code"], None),
                    "full_address": full_address,
                    "google_map_site_link": google_map_site_link,
                },
                "mapping": {
                    "continent_id": None,
                    "country_id": None,
                    "province_id": None,
                    "state_id": None,
                    "city_id": None,
                    "area_id": None,
                },
            },
            "contacts": {
                "phone_numbers": [safe_get(hotel, ["phone"], None)],
                "fax": [safe_get(hotel, ["fax"], None)],
                "email_address": [safe_get(hotel, ["email"], "").strip("<>")],
                "website": [safe_get(hotel, ["web"], None)],
            },
            "descriptions": description_flat,
            "room_type": room_types,
            "spoken_languages": spoken_languages,
            "amenities": amenities,
            "facilities": facilities,
            "hotel_photo": pictures,
            "point_of_interests": None,
            "nearest_airports": None,
            "train_stations": None,
            "connected_locations": None,
            "stadiums": None,
        }

    elif supplier_code == "goglobal_main_supplier":
        createdAt = datetime.now()
        createdAt_str = createdAt.strftime("%Y-%m-%dT%H:%M:%S")
        created_at_dt = datetime.strptime(createdAt_str, "%Y-%m-%dT%H:%M:%S")
        timeStamp = int(created_at_dt.timestamp())

        # Safe pass get data.
        def safe_get(d, keys, default=None):
            """Safely navigate through nested dictionaries."""
            for key in keys:
                if isinstance(d, dict):
                    d = d.get(key, default)
                else:
                    return default
            return d

        # 1) Extract the MakeRequestResult XML
        resp = safe_get(data, ["soap:Envelope", "soap:Body", "MakeRequestResponse"], {})
        xml_str = safe_get(resp, ["MakeRequestResult"], "")
        if not xml_str:
            raise HTTPException(
                status_code=400, detail="Missing MakeRequestResult XML payload"
            )

        # 2) Parse the XML
        try:
            root = ET.fromstring(xml_str)
        except ET.ParseError as e:
            raise HTTPException(status_code=400, detail=f"Invalid XML: {e}")

        # 3) Extract <Main> children into a dict
        main = root.find(".//Main")
        if main is None:
            raise HTTPException(
                status_code=400, detail="<Main> element not found in XML payload"
            )

        result = {}
        for elem in main:
            key = re.sub(r"(?<!^)(?=[A-Z])", "_", elem.tag).lower()
            result[key] = (elem.text or "").strip()

        # 4) Transform hotel facilities into list of objects
        raw_hfac = result.get("hotel_facilities", "")
        hotel_facilities = []
        for item in re.split(r"<br\s*/?>", raw_hfac, flags=re.IGNORECASE):
            clean = re.sub(r"<.*?>", "", item).strip()
            if clean:
                hotel_facilities.append(
                    {"type": clean, "title": clean, "icon": "mdi mdi-translate-variant"}
                )

        # 5) Extract and transform pictures into list of objects
        pics_node = root.find(".//Pictures")
        picture_objs = []
        if pics_node is not None:
            for pic in pics_node.findall("Picture"):
                url = (pic.text or "").strip()
                if url:
                    picture_objs.append({"picture_id": None, "title": None, "url": url})
        # Primary photo: first picture if available
        primary_photo = picture_objs[0]["url"] if picture_objs else None

        # 6) Transform room facilities into list of objects
        raw_rfac = safe_get(result, ["room_facilities"], "")
        amenities = []
        for item in re.split(r"<br\s*/?>", raw_rfac, flags=re.IGNORECASE):
            clean = re.sub(r"<.*?>", "", item).strip()
            if clean:
                amenities.append(
                    {"type": clean, "title": clean, "icon": "mdi mdi-translate-variant"}
                )

        address1 = safe_get(result, ["address"], None)
        google_map_site_link = (
            f"http://maps.google.com/maps?q={address1.replace(' ', '+')}"
            if address1
            else None
        )

        # @TODO: Country_code, latitude, longitude, city, Country name add this follow database.

        return {
            "created": createdAt_str,
            "timestamp": timeStamp,
            "hotel_id": safe_get(result, ["hotel_id"], None),
            "name": safe_get(result, ["hotel_name"], None),
            "name_local": safe_get(result, ["hotel_name"], None),
            "hotel_formerly_name": safe_get(result, ["hotel_name"], None),
            "destination_code": None,
            "country_code": None,
            "brand_text": None,
            "property_type": None,
            "star_rating": safe_get(result, ["category"], None),
            "chain": None,
            "brand": None,
            "logo": None,
            "primary_photo": primary_photo,
            "review_rating": {
                "source": None,
                "number_of_reviews": None,
                "rating_average": None,
                "popularity_score": None,
            },
            "policies": {
                "checkin": {
                    "begin_time": None,
                    "end_time": None,
                    "instructions": None,
                    "min_age": None,
                },
                "checkout": {"time": None},
                "fees": {"optional": None},
                "know_before_you_go": None,
                "pets": None,
                "remark": None,
                "child_and_extra_bed_policy": {
                    "infant_age": None,
                    "children_age_from": None,
                    "children_age_to": None,
                    "children_stay_free": None,
                    "min_guest_age": None,
                },
                "nationality_restrictions": None,
            },
            "address": {
                "latitude": None,
                "longitude": None,
                "address_line_1": safe_get(result, ["address"], None),
                "address_line_2": None,
                "city": None,
                "state": None,
                "country": None,
                "country_code": None,
                "postal_code": None,
                "full_address": safe_get(result, ["address"], None),
                "google_map_site_link": google_map_site_link,
                "local_lang": {
                    "latitude": None,
                    "longitude": None,
                    "address_line_1": safe_get(result, ["address"], None),
                    "address_line_2": None,
                    "city": None,
                    "state": None,
                    "country": None,
                    "country_code": None,
                    "postal_code": None,
                    "full_address": safe_get(result, ["address"], None),
                    "google_map_site_link": google_map_site_link,
                },
                "mapping": {
                    "continent_id": None,
                    "country_id": None,
                    "province_id": None,
                    "state_id": None,
                    "city_id": None,
                    "area_id": None,
                },
            },
            "contacts": {
                "phone_numbers": [safe_get(result, ["phone"], None)],
                "fax": [safe_get(result, ["fax"], None)],
                "email_address": [safe_get(result, ["email"], None)],
                "website": [safe_get(result, ["homePage"], None)],
            },
            "descriptions": [
                {"title": None, "text": safe_get(result, ["description"], None)}
            ],
            "room_type": [
                {
                    "room_id": None,
                    "title": None,
                    "title_lang": None,
                    "room_pic": None,
                    "description": None,
                    "max_allowed": {
                        "total": None,
                        "adults": None,
                        "children": None,
                        "infant": None,
                    },
                    "no_of_room": None,
                    "room_size": None,
                    "bed_type": [
                        {
                            "description": None,
                            "configuration": [],
                            "max_extrabeds": None,
                        }
                    ],
                    "shared_bathroom": None,
                }
            ],
            "spoken_languages": [
                {
                    "type": "spoken_languages",
                    "title": "English",
                    "icon": "mdi mdi-translate-variant",
                }
            ],
            "amenities": amenities,
            "facilities": hotel_facilities,
            "hotel_photo": picture_objs,
            "point_of_interests": None,
            "nearest_airports": None,
            "train_stations": None,
            "connected_locations": None,
            "stadiums": None,
        }

    elif supplier_code == "agoda":
        createdAt = datetime.now()
        createdAt_str = createdAt.strftime("%Y-%m-%dT%H:%M:%S")
        created_at_dt = datetime.strptime(createdAt_str, "%Y-%m-%dT%H:%M:%S")
        timeStamp = int(created_at_dt.timestamp())

        def safe_get(d, keys, default=None):
            """Safely traverse nested dicts and lists."""
            for key in keys:
                if isinstance(d, dict):
                    d = d.get(key, default)
                elif isinstance(d, list) and isinstance(key, int):
                    if 0 <= key < len(d):
                        d = d[key]
                    else:
                        return default
                else:
                    return default
            return d

        # Base data paths
        hotel = safe_get(data, ["Hotel_feed_full", "hotels", "hotel"], {})
        address = safe_get(data, ["Hotel_feed_full"], {})
        hotel_descriptions = safe_get(
            data, ["Hotel_feed_full", "hotel_descriptions"], {}
        )
        facilities_data = safe_get(
            data, ["Hotel_feed_full", "facilities", "facility"], []
        )
        pictures_data = safe_get(data, ["Hotel_feed_full", "pictures", "picture"], [])
        roomtypes = safe_get(data, ["Hotel_feed_full", "roomtypes", "roomtype"], [])

        # Room types
        room_type = []
        for room in roomtypes:
            room_data = {
                "room_id": safe_get(room, ["hotel_room_type_id"]),
                "title": safe_get(room, ["standard_caption"]),
                "title_lang": safe_get(room, ["standard_caption_translated"]),
                "room_pic": safe_get(room, ["hotel_room_type_picture"]),
                "description": None,
                "max_allowed": {
                    "total": safe_get(room, ["max_occupancy_per_room"]),
                    "adults": None,
                    "children": None,
                    "infant": safe_get(room, ["max_infant_in_room"]),
                },
                "no_of_room": safe_get(room, ["no_of_room"]),
                "room_size": safe_get(room, ["size_of_room"]),
                "bed_type": [
                    {
                        "description": safe_get(room, ["bed_type"]),
                        "configuration": [],
                        "max_extrabeds": safe_get(room, ["max_extrabeds"]),
                    }
                ],
                "shared_bathroom": safe_get(room, ["shared_bathroom"]),
            }
            room_type.append(room_data)

        # Facilities
        facilities = []
        for item in facilities_data:
            facilities.append(
                {
                    "type": safe_get(item, ["property_group_description"], ""),
                    "title": safe_get(item, ["property_name"], ""),
                    "icon": "mdi mdi-translate-variant",
                }
            )

        # Pictures
        pictures = []
        for item in pictures_data:
            pictures.append(
                {
                    "picture_id": safe_get(item, ["picture_id"]),
                    "title": safe_get(item, ["caption"]),
                    "url": safe_get(item, ["URL"]),
                }
            )

        # Google Maps link
        address_entry = safe_get(address, ["addresses", "address"], [])

        # Take the first dictionary if it exists
        first_address = address_entry[0] if address_entry else {}
        address_line_1 = safe_get(first_address, ["address_line_1"])
        address_line_2 = safe_get(first_address, ["address_line_2"])
        hotel_name = safe_get(hotel, ["hotel_name"])
        city = safe_get(first_address, ["city"])
        postal_code = safe_get(first_address, ["postal_code"])
        country = safe_get(first_address, ["country"])
        address_query = f"{address_line_1}, {address_line_2}, {hotel_name}, {city}, {postal_code}, {country}"
        google_map_site_link = (
            f"http://maps.google.com/maps?q={address_query.replace(' ', '+')}"
            if address_line_1
            else None
        )

        return {
            "created": createdAt_str,
            "timestamp": timeStamp,
            "hotel_id": safe_get(hotel, ["hotel_id"]),
            "name": safe_get(hotel, ["hotel_name"]),
            "name_local": safe_get(hotel, ["hotel_formerly_name"]),
            "hotel_formerly_name": safe_get(hotel, ["translated_name"]),
            "destination_code": None,
            "country_code": None,
            "brand_text": None,
            "property_type": safe_get(hotel, ["accommodation_type"]),
            "star_rating": safe_get(hotel, ["star_rating"]),
            "chain": None,
            "brand": None,
            "logo": None,
            "primary_photo": safe_get(pictures, [0, "url"]),
            "review_rating": {
                "source": None,
                "number_of_reviews": safe_get(hotel, ["number_of_reviews"]),
                "rating_average": safe_get(hotel, ["rating_average"]),
                "popularity_score": safe_get(hotel, ["popularity_score"]),
            },
            "policies": {
                "checkin": {
                    "begin_time": None,
                    "end_time": None,
                    "instructions": None,
                    "min_age": None,
                },
                "checkout": {
                    "time": None,
                },
                "fees": {
                    "optional": None,
                },
                "know_before_you_go": None,
                "pets": [],
                "remark": None,
                "child_and_extra_bed_policy": {
                    "infant_age": safe_get(
                        hotel, ["child_and_extra_bed_policy", "infant_age"]
                    ),
                    "children_age_from": safe_get(
                        hotel, ["child_and_extra_bed_policy", "children_age_from"]
                    ),
                    "children_age_to": safe_get(
                        hotel, ["child_and_extra_bed_policy", "children_age_to"]
                    ),
                    "children_stay_free": safe_get(
                        hotel, ["child_and_extra_bed_policy", "children_stay_free"]
                    ),
                    "min_guest_age": safe_get(
                        hotel, ["child_and_extra_bed_policy", "min_guest_age"]
                    ),
                },
                "nationality_restrictions": hotel.get("nationality_restrictions", None),
            },
            "address": {
                "latitude": safe_get(hotel, ["latitude"]),
                "longitude": safe_get(hotel, ["longitude"]),
                "address_line_1": safe_get(
                    address, ["addresses", "address", 0, "address_line_1"]
                ),
                "address_line_2": safe_get(
                    address, ["addresses", "address", 0, "address_line_2"]
                ),
                "city": safe_get(address, ["addresses", "address", 0, "city"]),
                "state": safe_get(address, ["addresses", "address", 0, "state"]),
                "country": safe_get(address, ["addresses", "address", 0, "country"]),
                "country_code": None,
                "postal_code": safe_get(
                    address, ["addresses", "address", 0, "postal_code"]
                ),
                "full_address": f"{safe_get(address, ['addresses', 'address', 0, 'address_line_1'])}, {safe_get(address, ['addresses', 'address', 0, 'address_line_2'])}",
                "google_map_site_link": google_map_site_link,
                "local_lang": {
                    "latitude": safe_get(hotel, ["latitude"]),
                    "longitude": safe_get(hotel, ["longitude"]),
                    "address_line_1": safe_get(
                        address, ["addresses", "address", 0, "address_line_1"]
                    ),
                    "address_line_2": safe_get(
                        address, ["addresses", "address", 0, "address_line_2"]
                    ),
                    "city": safe_get(address, ["addresses", "address", 0, "city"]),
                    "state": safe_get(address, ["addresses", "address", 0, "state"]),
                    "country": safe_get(
                        address, ["addresses", "address", 0, "country"]
                    ),
                    "country_code": None,
                    "postal_code": safe_get(
                        address, ["addresses", "address", 0, "postal_code"]
                    ),
                    "full_address": f"{safe_get(address, ['addresses', 'address', 0, 'address_line_1'])}, {safe_get(address, ['addresses', 'address', 0, 'address_line_2'])}",
                    "google_map_site_link": google_map_site_link,
                },
                "mapping": {
                    "continent_id": None,
                    "country_id": None,
                    "province_id": None,
                    "state_id": None,
                    "city_id": None,
                    "area_id": None,
                },
            },
            "contacts": {
                "phone_numbers": [
                    safe_get(hotel, ["company_traceability_info", "phone_no"])
                ],
                "fax": [safe_get(hotel, ["company_traceability_info", "fax_no"])],
                "email_address": [
                    safe_get(hotel, ["company_traceability_info", "email"])
                ],
                "website": [safe_get(hotel, ["company_traceability_info", "website"])],
            },
            "descriptions": [
                {
                    "title": None,
                    "text": safe_get(
                        hotel_descriptions, ["hotel_description", "overview"]
                    ),
                }
            ],
            "room_type": room_type,
            "spoken_languages": [
                {
                    "type": "spoken_languages",
                    "title": "English",
                    "icon": "mdi mdi-translate-variant",
                }
            ],
            "amenities": None,
            "facilities": facilities,
            "hotel_photo": pictures,
            "point_of_interests": None,
            "nearest_airports": None,
            "train_stations": None,
            "connected_locations": None,
            "stadiums": None,
        }

    elif supplier_code == "tbohotel":
        createdAt = datetime.now()
        createdAt_str = createdAt.strftime("%Y-%m-%dT%H:%M:%S")
        created_at_dt = datetime.strptime(createdAt_str, "%Y-%m-%dT%H:%M:%S")
        timeStamp = int(created_at_dt.timestamp())

        def safe_get(d, keys, default=None):
            """Safely traverse nested dicts and lists."""
            for key in keys:
                if isinstance(d, dict):
                    d = d.get(key, default)
                elif isinstance(d, list) and isinstance(key, int):
                    if 0 <= key < len(d):
                        d = d[key]
                    else:
                        return default
                else:
                    return default
            return d

        # Main
        hotel = data.get("HotelDetails", {})[0]
        # print(hotel)
        # hotel = safe_get(data, ["HotelDetails", 0])
        # print(hotel)

        # Address and Google Maps link
        address1 = safe_get(hotel, ["Address"])
        google_map_site_link = (
            f"http://maps.google.com/maps?q={urllib.parse.quote(address1)}"
            if address1
            else None
        )

        # Facilities
        facility_data_main = safe_get(hotel, ["HotelFacilities"], [])
        facility_data = [
            {"type": item, "title": item, "icon": "mdi mdi-translate-variant"}
            for item in facility_data_main
        ]

        # Images
        image_data_main = safe_get(hotel, ["Images"], [])
        image_data = [
            {"picture_id": None, "title": None, "url": item} for item in image_data_main
        ]
        # print(image_data)
        primar = safe_get(image_data, [0, "url"])

        print(primar)

        # Map coordinates
        map_data = safe_get(hotel, ["Map"], "")
        latitude = None
        longitude = None

        if map_data and "|" in map_data:
            parts = map_data.split("|")
            if len(parts) == 2:
                try:
                    latitude = float(parts[0])
                    longitude = float(parts[1])
                except ValueError:
                    latitude = longitude = None

        return {
            "created": createdAt_str,
            "timestamp": timeStamp,
            "hotel_id": safe_get(hotel, ["HotelCode"]),
            "name": safe_get(hotel, ["HotelName"]),
            "name_local": safe_get(hotel, ["HotelName"]),
            "hotel_formerly_name": safe_get(hotel, ["HotelName"]),
            "destination_code": None,
            "country_code": safe_get(hotel, ["CountryCode"]),
            "brand_text": None,
            "property_type": None,
            "star_rating": safe_get(hotel, ["HotelRating"]),
            "chain": None,
            "brand": None,
            "logo": None,
            "primary_photo": safe_get(image_data, [0, "url"]),
            "review_rating": {
                "source": None,
                "number_of_reviews": None,
                "rating_average": None,
                "popularity_score": None,
            },
            "policies": {
                "checkin": {
                    "begin_time": safe_get(hotel, ["CheckInTime"]),
                    "end_time": safe_get(hotel, ["CheckOutTime"]),
                    "instructions": None,
                    "min_age": None,
                },
                "checkout": {"time": safe_get(hotel, ["CheckOutTime"])},
                "fees": {"optional": None},
                "know_before_you_go": None,
                "pets": None,
                "remark": None,
                "child_and_extra_bed_policy": {
                    "infant_age": None,
                    "children_age_from": None,
                    "children_age_to": None,
                    "children_stay_free": None,
                    "min_guest_age": None,
                },
                "nationality_restrictions": None,
            },
            "address": {
                "latitude": latitude,
                "longitude": longitude,
                "address_line_1": safe_get(hotel, ["Address"]),
                "address_line_2": None,
                "city": safe_get(hotel, ["CityName"]),
                "state": None,
                "country": safe_get(hotel, ["CountryName"]),
                "country_code": safe_get(hotel, ["CountryCode"]),
                "postal_code": safe_get(hotel, ["PostalCode"]),
                "full_address": safe_get(hotel, ["Address"]),
                "google_map_site_link": google_map_site_link,
                "local_lang": {
                    "latitude": latitude,
                    "longitude": longitude,
                    "address_line_1": safe_get(hotel, ["Address"]),
                    "address_line_2": None,
                    "city": safe_get(hotel, ["CityName"]),
                    "state": None,
                    "country": safe_get(hotel, ["CountryName"]),
                    "country_code": safe_get(hotel, ["CountryCode"]),
                    "postal_code": safe_get(hotel, ["PostalCode"]),
                    "full_address": safe_get(hotel, ["Address"]),
                    "google_map_site_link": google_map_site_link,
                },
                "mapping": {
                    "continent_id": None,
                    "country_id": None,
                    "province_id": None,
                    "state_id": None,
                    "city_id": safe_get(hotel, ["CityId"]),
                    "area_id": None,
                },
            },
            "contacts": {
                "phone_numbers": [safe_get(hotel, ["PhoneNumber"])],
                "fax": [safe_get(hotel, ["FaxNumber"])],
                "email_address": [safe_get(hotel, ["Email"])],
                "website": [safe_get(hotel, ["Website"])],
            },
            "descriptions": [{"title": None, "text": safe_get(hotel, ["Description"])}],
            "room_type": [],
            "spoken_languages": [
                {
                    "type": "spoken_languages",
                    "title": "English",
                    "icon": "mdi mdi-translate-variant",
                }
            ],
            "amenities": [],
            "facilities": facility_data,
            "hotel_photo": image_data,
            "point_of_interests": [],
            "nearest_airports": [],
            "train_stations": [],
            "connected_locations": [],
            "stadiums": [],
        }

    elif supplier_code == "ean":

        createdAt = datetime.now()
        createdAt_str = createdAt.strftime("%Y-%m-%dT%H:%M:%S")
        created_at_dt = datetime.strptime(createdAt_str, "%Y-%m-%dT%H:%M:%S")
        timeStamp = int(created_at_dt.timestamp())

        def safe_get(d, keys, default=None):
            """Safely access nested dictionary keys."""
            for key in keys:
                if isinstance(d, dict):
                    d = d.get(key, default)
                else:
                    return default
            return d

        # Main data
        hotel = data
        # hotel = next(iter(property_data.values()))

        # Pets
        attributes_data = safe_get(hotel, ["attributes"], {})
        pets_data = [
            {"id": safe_get(pet_info, ["id"]), "name": safe_get(pet_info, ["name"])}
            for pet_info in attributes_data.get("pets", {}).values()
        ]

        # Descriptions
        raw_descriptions = hotel.get("descriptions", {})
        descriptions_data = (
            [{"title": title, "text": text} for title, text in raw_descriptions.items()]
            if raw_descriptions
            else None
        )

        # Google Map Link
        address_line_1 = safe_get(hotel, ["address", "line_1"])
        address_line_2 = safe_get(hotel, ["address", "line_2"])
        hotel_name = safe_get(hotel, ["name"])
        city = safe_get(hotel, ["address", "city"])
        postal_code = safe_get(hotel, ["address", "postal_code"])
        country = safe_get(hotel, ["address", "country_code"])

        address_query = f"{address_line_1}, {address_line_2}, {hotel_name}, {city}, {postal_code}, {country}"
        google_map_site_link = (
            f"http://maps.google.com/maps?q={address_query.replace(' ', '+')}"
            if address_line_1
            else None
        )

        # Rooms
        room_ids = hotel.get("rooms", {})
        structured_room_types = []

        for room_id, room_info in room_ids.items():
            bed_types = []
            for bed_group in room_info.get("bed_groups", {}).values():
                bed_type_entry = {
                    "description": bed_group.get("description"),
                    "configuration": [
                        {
                            "quantity": config["quantity"],
                            "size": config["size"],
                            "type": config["type"],
                        }
                        for config in bed_group.get("configuration", [])
                    ],
                    "max_extrabeds": bed_group.get("max_extrabeds"),
                }
                bed_types.append(bed_type_entry)

            images = room_info.get("images", [])
            image_url = "No Image Available"
            if images:
                links = images[0].get("links", {})
                image_url = (
                    links.get("1000px", {}).get("href")
                    or links.get("350px", {}).get("href")
                    or image_url
                )

            room_data = {
                "room_id": room_info.get("id"),
                "title": room_info.get("name", "No title available"),
                "title_lang": room_info.get("name", "No title available"),
                "room_pic": image_url,
                "description": safe_get(room_info, ["descriptions", "overview"]),
                "max_allowed": {
                    "total": safe_get(room_info, ["occupancy", "max_allowed", "total"]),
                    "adults": safe_get(
                        room_info, ["occupancy", "max_allowed", "adults"]
                    ),
                    "children": safe_get(
                        room_info, ["occupancy", "max_allowed", "children"]
                    ),
                    "infant": None,
                },
                "no_of_room": None,
                "room_size": safe_get(room_info, ["area", "square_feet"]),
                "bed_type": bed_types,
                "shared_bathroom": False,
            }

            structured_room_types.append(room_data)

        # Languages
        spoken_languages = hotel.get("spoken_languages", {})
        transformed_spoken_languages = [
            {
                "type": "spoken_languages",
                "title": safe_get(value, ["name"]),
                "icon": "mdi mdi-translate-variant",
            }
            for key, value in spoken_languages.items()
        ]

        # Amenities
        amenities = hotel.get("amenities", {})
        hotel_room_amenities = [
            {
                "type": safe_get(value, ["name"]),
                "title": safe_get(value, ["name"]),
                "icon": "mdi mdi-alpha-f-circle-outline",
            }
            for key, value in amenities.items()
        ]

        # General Attributes
        general_attributes = safe_get(hotel, ["attributes", "general"], {})
        hotel_amenities = [
            {
                "type": safe_get(value, ["name"]),
                "title": safe_get(value, ["name"]),
                "icon": "mdi mdi-alpha-f-circle-outline",
            }
            for key, value in general_attributes.items()
        ]

        # Hotel Images
        images = hotel.get("images", [])
        hotel_photo_data = [
            {
                "picture_id": image.get("category"),
                "title": image.get("caption"),
                "url": safe_get(
                    image, ["links", "1000px", "href"], "No Image Available"
                ),
            }
            for image in images
        ]

        primary_photo = (
            safe_get(images[0], ["links", "1000px", "href"]) if images else None
        )

        return {
            "created": createdAt_str,
            "timestamp": timeStamp,
            "hotel_id": hotel.get("property_id", None),
            "name": hotel.get("name", None),
            "name_local": hotel.get("name", None),
            "hotel_formerly_name": hotel.get("name", None),
            "destination_code": None,
            "country_code": hotel.get("address", {}).get("country_code", None),
            "brand_text": None,
            "property_type": hotel.get("category", {}).get("name", None),
            "star_rating": hotel.get("ratings", {})
            .get("property", {})
            .get("rating", None),
            "chain": hotel.get("chain", {}).get("name", None),
            "brand": hotel.get("brand", {}).get("name", None),
            "logo": None,
            "primary_photo": primary_photo,
            "review_rating": {
                "source": "Expedia.com",
                "number_of_reviews": hotel.get("ratings", {})
                .get("guest", {})
                .get("count", None),
                "rating_average": hotel.get("rank", None),
                "popularity_score": hotel.get("ratings", {})
                .get("guest", {})
                .get("overall", None),
            },
            "policies": {
                "checkin": {
                    "begin_time": hotel.get("checkin", {}).get("begin_time", None),
                    "end_time": hotel.get("checkin", {}).get("end_time", None),
                    "instructions": hotel.get("checkin", {}).get("instructions", None),
                    "special_instructions": hotel.get("checkin", {}).get(
                        "special_instructions", None
                    ),
                    "min_age": hotel.get("checkin", {}).get("min_age", None),
                },
                "checkout": {
                    "time": hotel.get("checkout", {}).get("time", None),
                },
                "fees": {
                    "optional": hotel.get("fees", {}).get("optional", None),
                    "mandatory": hotel.get("fees", {}).get("mandatory", None),
                },
                "know_before_you_go": hotel.get("policies", {}).get(
                    "know_before_you_go", None
                ),
                "pets": pets_data,
                "remark": None,
                "child_and_extra_bed_policy": {
                    "infant_age": None,
                    "children_age_from": None,
                    "children_age_to": None,
                    "children_stay_free": None,
                    "min_guest_age": None,
                },
                "nationality_restrictions": None,
            },
            "address": {
                "latitude": hotel.get("location", {})
                .get("coordinates", {})
                .get("latitude", None),
                "longitude": hotel.get("location", {})
                .get("coordinates", {})
                .get("longitude", None),
                "address_line_1": hotel.get("address", {}).get("line_1", None),
                "address_line_2": hotel.get("address", {}).get("line_2", None),
                "city": hotel.get("address", {}).get("city", None),
                "state": hotel.get("address", {}).get("state_province_name", None),
                "country": hotel.get("address", {}).get("country_code", None),
                "country_code": hotel.get("address", {}).get("country_code", None),
                "postal_code": hotel.get("address", {}).get("postal_code", None),
                "full_address": f"{hotel.get('address', {}).get('line_1', None)}, {hotel.get('address', {}).get('line_2', None)}",
                "google_map_site_link": google_map_site_link,
                "local_lang": {
                    "latitude": hotel.get("location", {})
                    .get("coordinates", {})
                    .get("latitude", None),
                    "longitude": hotel.get("location", {})
                    .get("coordinates", {})
                    .get("longitude", None),
                    "address_line_1": hotel.get("address", {}).get("line_1", None),
                    "address_line_2": hotel.get("address", {}).get("line_2", None),
                    "city": hotel.get("address", {}).get("city", None),
                    "state": hotel.get("address", {}).get("state_province_name", None),
                    "country": hotel.get("address", {}).get("country_code", None),
                    "country_code": hotel.get("address", {}).get("country_code", None),
                    "postal_code": hotel.get("address", {}).get("postal_code", None),
                    "full_address": f"{hotel.get('address', {}).get('line_1', None)}, {hotel.get('address', {}).get('line_2', None)}",
                    "google_map_site_link": google_map_site_link,
                },
                "mapping": {
                    "continent_id": None,
                    "country_id": hotel.get("address", {}).get("country_code", None),
                    "province_id": None,
                    "state_id": None,
                    "city_id": None,
                    "area_id": None,
                },
            },
            "contacts": {
                "phone_numbers": [hotel.get("phone", None)],
                "fax": [hotel.get("fax", None)],
                "email_address": [hotel.get("email", None)],
                "website": [hotel.get("website", None)],
            },
            "descriptions": descriptions_data,
            "room_type": structured_room_types,
            "spoken_languages": transformed_spoken_languages,
            "amenities": hotel_room_amenities,
            "facilities": hotel_amenities,
            "hotel_photo": hotel_photo_data,
            "point_of_interests": [{"code": None, "name": None}],
            "nearest_airports": [
                {
                    "code": hotel.get("airports", {})
                    .get("preferred", {})
                    .get("iata_airport_code", None),
                    "name": hotel.get("airports", {})
                    .get("preferred", {})
                    .get("iata_airport_code", None),
                }
            ],
            "train_stations": [{"code": None, "name": None}],
            "connected_locations": [
                {"code": None, "name": None},
            ],
            "stadiums": [{"code": None, "name": None}],
        }

    elif supplier_code == "grnconnect":
        createdAt = datetime.now()
        createdAt_str = createdAt.strftime("%Y-%m-%dT%H:%M:%S")
        created_at_dt = datetime.strptime(createdAt_str, "%Y-%m-%dT%H:%M:%S")
        timeStamp = int(created_at_dt.timestamp())

        def safe_get(d, keys, default=None):
            """Safely access nested dictionary keys."""
            for key in keys:
                if isinstance(d, dict):
                    d = d.get(key, default)
                else:
                    return default
            return d

        # Main data point
        hotel = data

        # Address
        address = safe_get(hotel, ["hotel", "address"])
        google_map_site_link = (
            f"http://maps.google.com/maps?q={address.replace(' ', '+')}"
            if address
            else None
        )

        # Description
        description = safe_get(hotel, ["description"])
        if description:
            descriptions_data = [{"title": "Description", "text": description}]
        else:
            descriptions_data = None

        # Facilities
        facilities = safe_get(hotel, ["hotel", "facilities"])
        hotel_facilities = []

        if facilities:
            facilities_list = facilities.split(" ; ")
            for facility in facilities_list:
                hotel_facilities.append(
                    {
                        "type": facility,
                        "title": facility,
                        "icon": "mdi mdi-alpha-f-circle-outline",
                    }
                )
        else:
            hotel_facilities = [{"type": None, "title": None, "icon": None}]

        # Images
        images = safe_get(hotel, ["images"], [])
        hotel_images = []
        primary_photo = None

        if images:
            primary_photo = safe_get(images[0], ["url"])
            for image in images:
                hotel_images.append(
                    {
                        "picture_id": None,
                        "title": safe_get(image, ["caption"]),
                        "url": safe_get(image, ["url"]),
                    }
                )
        else:
            hotel_images = [{"picture_id": None, "title": None, "url": None}]

        return {
            "created": createdAt_str,
            "timestamp": timeStamp,
            "hotel_id": safe_get(hotel, ["hotel_code"]),
            "name": safe_get(hotel, ["hotel", "name"]),
            "name_local": safe_get(hotel, ["hotel", "name"]),
            "hotel_formerly_name": safe_get(hotel, ["hotel", "name"]),
            "destination_code": safe_get(hotel, ["hotel", "dest_code"]),
            "country_code": safe_get(hotel, ["country", "code"]),
            "brand_text": None,
            "property_type": safe_get(hotel, ["hotel", "acc_name"]),
            "star_rating": safe_get(hotel, ["hotel", "category"]),
            "chain": safe_get(hotel, ["hotel", "chain_name"]),
            "brand": None,
            "logo": None,
            "primary_photo": primary_photo,
            "review_rating": {
                "source": None,
                "number_of_reviews": None,
                "rating_average": None,
                "popularity_score": None,
            },
            "policies": {
                "checkin": {
                    "begin_time": None,
                    "end_time": None,
                    "instructions": None,
                    "min_age": None,
                },
                "checkout": {"time": None},
                "fees": {"optional": None},
                "know_before_you_go": None,
                "pets": None,
                "remark": None,
                "child_and_extra_bed_policy": {
                    "infant_age": None,
                    "children_age_from": None,
                    "children_age_to": None,
                    "children_stay_free": None,
                    "min_guest_age": None,
                },
                "nationality_restrictions": None,
            },
            "address": {
                "latitude": safe_get(hotel, ["hotel", "latitude"]),
                "longitude": safe_get(hotel, ["hotel", "longitude"]),
                "address_line_1": safe_get(hotel, ["hotel", "address"]),
                "address_line_2": None,
                "city": safe_get(hotel, ["city", "name"]),
                "state": None,
                "country": safe_get(hotel, ["country", "name"]),
                "country_code": safe_get(hotel, ["country", "code"]),
                "postal_code": safe_get(hotel, ["hotel", "postal_code"]),
                "full_address": f"{safe_get(hotel, ["hotel", "address"])},{safe_get(hotel, ["country", "name"])}",
                "google_map_site_link": google_map_site_link,
                "local_lang": {
                    "latitude": safe_get(hotel, ["hotel", "latitude"]),
                    "longitude": safe_get(hotel, ["hotel", "longitude"]),
                    "address_line_1": safe_get(hotel, ["hotel", "address"]),
                    "address_line_2": None,
                    "city": safe_get(hotel, ["city", "name"]),
                    "state": None,
                    "country": safe_get(hotel, ["country", "name"]),
                    "country_code": safe_get(hotel, ["country", "code"]),
                    "postal_code": safe_get(hotel, ["hotel", "postal_code"]),
                    "full_address": f"{safe_get(hotel, ["hotel", "address"])},{safe_get(hotel, ["country", "name"])}",
                    "google_map_site_link": google_map_site_link,
                },
                "mapping": {
                    "continent_id": None,
                    "country_id": None,
                    "province_id": None,
                    "state_id": None,
                    "city_id": None,
                    "area_id": None,
                },
            },
            "contacts": {
                "phone_numbers": [safe_get(hotel, ["Phone"])],
                "fax": [safe_get(data, ["fax"])],
                "email_address": [safe_get(data, ["email"])],
                "website": [safe_get(data, ["website"])],
            },
            "descriptions": descriptions_data,
            "room_type": [],
            "spoken_languages": [
                {
                    "type": "spoken_languages",
                    "title": "English",
                    "icon": "mdi mdi-translate-variant",
                }
            ],
            "amenities": [],
            "facilities": hotel_facilities,
            "hotel_photo": hotel_images,
            "point_of_interests": [],
            "nearest_airports": [],
            "train_stations": [],
            "connected_locations": [],
            "stadiums": [],
        }

    elif supplier_code == "hyperguestdirect":

        createdAt = datetime.now()
        createdAt_str = createdAt.strftime("%Y-%m-%dT%H:%M:%S")
        created_at_dt = datetime.strptime(createdAt_str, "%Y-%m-%dT%H:%M:%S")
        timeStamp = int(created_at_dt.timestamp())

        def safe_get(d, keys, default=None):
            """Safely access nested dictionary keys."""
            for key in keys:
                if isinstance(d, dict):
                    d = d.get(key, default)
                else:
                    return default
            return d

        # Base Url
        hotel = data

        hotel_setting = safe_get(hotel, ["settings"], {})
        hotel_type = safe_get(hotel_setting, ["hotelType", "name"])
        maxInfantAge = safe_get(hotel_setting, ["maxInfantAge"])
        maxChildAge = safe_get(hotel_setting, ["maxChildAge"])
        checkIn = safe_get(hotel_setting, ["checkIn"], {})
        checkOut = safe_get(hotel_setting, ["checkOut"], {})
        chain = safe_get(hotel_setting, ["chain", "name"])

        hotel_geo = safe_get(hotel, ["coordinates"], {})
        longitude = hotel_geo.get("longitude")
        latitude = hotel_geo.get("latitude")

        rating = safe_get(hotel, ["rating"], {})

        location = safe_get(hotel, ["location"], {})
        countryCode = safe_get(location, ["countryCode"])
        address = safe_get(location, ["address"])
        postcode = safe_get(location, ["postcode"])
        city = safe_get(location, ["city", "name"])

        address_query = f"{address}, {longitude}, {latitude}, {city}, {countryCode}"
        google_map_site_link = (
            f"http://maps.google.com/maps?q={address_query.replace(' ', '+')}"
            if address
            else None
        )

        hotel_rooms = safe_get(hotel, ["rooms"], [])

        rooms_data = []

        for room in hotel_rooms:
            room_id = safe_get(room, ["id"], None)
            title = safe_get(room, ["name"], "")
            title_lang = None  # No explicit language for title, only descriptions
            descriptions = safe_get(room, ["descriptions"], [])
            description = descriptions[0].get("description") if descriptions else None

            # Collect all image URIs
            images = [img.get("uri") for img in safe_get(room, ["images"], [])]

            # Max occupancy details
            settings = safe_get(room, ["settings"], {})
            max_allowed = {
                "total": safe_get(settings, ["maxOccupancy"], None),
                "adults": safe_get(settings, ["adultsNumber"], None),
                "children": safe_get(settings, ["childrenNumber"], None),
                "infant": safe_get(settings, ["infantsNumber"], None),
            }

            # Bed details
            beds = []
            for bed in safe_get(room, ["beds"], []):
                beds.append(
                    {
                        "description": safe_get(bed, ["type"], None),
                        "configuration": [safe_get(bed, ["size"], None)],
                        "quantity": safe_get(bed, ["quantity"], None),
                    }
                )

            # Facilities
            facilities = []
            for fac in safe_get(room, ["facilities"], []):
                facilities.append(safe_get(fac, ["name"], None))

            room_obj = {
                "room_id": room_id,
                "title": title,
                "title_lang": title_lang,
                "room_pic": images,
                "description": description,
                "max_allowed": max_allowed,
                "no_of_room": None,
                "room_size": safe_get(settings, ["roomSize"], None),
                "bed_type": beds,
                "amenities": facilities,
            }

            rooms_data.append(room_obj)

        # Content section
        contact = safe_get(hotel, ["contact"], {})
        logo = safe_get(hotel, ["logo"])

        # Facilities section
        facilities_data = safe_get(hotel, ["facilities"], [])

        transformed_facilities = [
            {
                "type": safe_get(item, ["type"], ""),
                "title": safe_get(item, ["category"], ""),
                "icon": "mdi mdi-translate-variant",
            }
            for item in facilities_data
        ]

        # Descriptions section
        descriptions = safe_get(hotel, ["descriptions"], [])
        descriptions_data = [
            {"title": safe_get(item, ["type"]), "text": safe_get(item, ["description"])}
            for item in descriptions
        ]

        # Image section
        images = safe_get(hotel, ["images"], [])
        primary_photo_url = None
        hotel_photo = []

        if images:
            primary_photo = images[0]
            primary_photo_url = safe_get(primary_photo, ["uri"])

            hotel_photo = [
                {
                    "url": safe_get(img, ["uri"]),
                    "caption": safe_get(img, ["description"], ""),
                    "type": safe_get(img, ["type"]),
                }
                for img in images
            ]

        return {
            "created": createdAt_str,
            "timestamp": timeStamp,
            "hotel_id": safe_get(hotel, ["id"]),
            "name": safe_get(hotel, ["name"]),
            "name_local": safe_get(hotel, ["name"]),
            "hotel_formerly_name": safe_get(hotel, ["name"]),
            "destination_code": None,
            "country_code": countryCode,
            "brand_text": None,
            "property_type": hotel_type,
            "star_rating": rating,
            "chain": chain,
            "brand": None,
            "logo": None,
            "primary_photo": primary_photo_url,
            "review_rating": {
                "source": None,
                "number_of_reviews": None,
                "rating_average": None,
                "popularity_score": None,
            },
            "policies": {
                "check_in": {
                    "begin_time": checkIn,
                    "end_time": checkOut,
                    "instructions": None,
                    "min_age": None,
                },
                "checkout": {
                    "time": checkOut,
                },
                "fees": {"optional": None},
                "know_before_you_go": None,
                "pets": [],
                "remark": None,
                "child_and_extra_bed_policy": {
                    "infant_age": maxInfantAge,
                    "children_age_from": maxChildAge,
                    "children_age_to": None,
                    "children_stay_free": None,
                    "min_guest_age": None,
                },
                "nationality_restrictions": None,
            },
            "address": {
                "latitude": latitude,
                "longitude": longitude,
                "address_line_1": address,
                "address_line_2": None,
                "city": city,
                "state": None,
                "country": None,
                "country_code": countryCode,
                "postal_code": postcode,
                "full_address": address,
                "google_map_site_link": google_map_site_link,
                "local_lang": {
                    "latitude": latitude,
                    "longitude": longitude,
                    "address_line_1": address,
                    "address_line_2": None,
                    "city": city,
                    "state": None,
                    "country": None,
                    "country_code": countryCode,
                    "postal_code": postcode,
                    "full_address": address,
                    "google_map_site_link": google_map_site_link,
                },
                "mapping": {
                    "continent_id": None,
                    "country_id": None,
                    "province_id": None,
                    "state_id": None,
                    "city_id": None,
                    "area_id": None,
                },
            },
            "contacts": {
                "phone_numbers": [safe_get(contact, ["phone"])],
                "fax": [safe_get(contact, ["fax"])],
                "email_address": [safe_get(contact, ["email"])],
                "website": [safe_get(contact, ["website"])],
            },
            "descriptions": descriptions_data,
            "room_type": rooms_data,
            "spoken_languages": [
                {
                    "type": "spoken_languages",
                    "title": "English",
                    "icon": "mdi mdi-translate-variant",
                }
            ],
            "amenities": [],
            "facilities": transformed_facilities,
            "hotel_photo": hotel_photo,
            "point_of_interests": [],
            "nearest_airports": [],
            "train_stations": [],
            "connected_locations": [],
            "stadiums": [],
        }

    elif supplier_code == "rnrhotel":

        createdAt = datetime.now()
        createdAt_str = createdAt.strftime("%Y-%m-%dT%H:%M:%S")
        created_at_dt = datetime.strptime(createdAt_str, "%Y-%m-%dT%H:%M:%S")
        timeStamp = int(created_at_dt.timestamp())

        def safe_get(d, keys, default=None):
            """Safely access nested dictionary keys."""
            for key in keys:
                if isinstance(d, dict):
                    d = d.get(key, default)
                else:
                    return default
            return d

        # Main base
        hotel = data

        address = safe_get(hotel, ["address"])
        google_map_site_link = (
            f"http://maps.google.com/maps?q={address.replace(' ', '+')}"
            if address
            else None
        )

        # Room types
        room_type = []
        for room in safe_get(hotel, ["rooms"], []):
            room_pic = safe_get(room, ["images"], [])
            room_data = {
                "room_id": safe_get(room, ["id"]),
                "title": safe_get(room, ["name"]),
                "title_lang": None,
                "room_pic": safe_get(room_pic[0], ["url"]) if room_pic else None,
                "description": safe_get(room, ["description"]),
                "max_allowed": {
                    "total": safe_get(room, ["occupancy"], 0),
                    "adults": safe_get(room, ["occupancy"], 0),
                    "children": 0,
                    "infant": 0,
                },
                "no_of_room": 1,
                "room_size": safe_get(room, ["area"]),
                "bed_type": [],
                "shared_bathroom": False,
            }

            for group in safe_get(room, ["bed_groups"], []):
                for bed in safe_get(group, ["bed_types"], []):
                    bed_info = {
                        "description": safe_get(bed, ["name"]),
                        "configuration": f"{safe_get(bed, ['quantity'], 1)} x {safe_get(bed, ['name'])}",
                        "max_extrabeds": 0,
                    }
                    room_data["bed_type"].append(bed_info)

            room_type.append(room_data)

        # Hotel photos
        hotel_photo = []
        for img in safe_get(hotel, ["images"], []):
            photo = {
                "picture_id": None,
                "title": safe_get(img, ["category"]),
                "url": safe_get(img, ["url"]),
            }
            hotel_photo.append(photo)

        # Primary photo
        primary_photo = safe_get(hotel_photo[0], ["url"]) if hotel_photo else None

        # Amenities
        raw_amenities = safe_get(hotel, ["amenities"], [])
        structured_amenities = [
            {"type": amenity, "title": amenity, "icon": "mdi mdi-translate-variant"}
            for amenity in raw_amenities
        ]

        return {
            "created": createdAt_str,
            "timestamp": timeStamp,
            "hotel_id": safe_get(hotel, ["id"]),
            "name": safe_get(hotel, ["name"]),
            "name_local": safe_get(hotel, ["name"]),
            "hotel_formerly_name": safe_get(hotel, ["name"]),
            "destination_code": None,
            "country_code": "BD",
            "brand_text": None,
            "property_type": None,
            "star_rating": hotel.get("stars", None),
            "chain": None,
            "brand": None,
            "logo": None,
            "primary_photo": primary_photo,
            "review_rating": {
                "source": None,
                "number_of_reviews": None,
                "rating_average": None,
                "popularity_score": None,
            },
            "policies": {
                "checkin": {
                    "begin_time": hotel.get("check_in_time", None),
                    "end_time": hotel.get("check_in_before_time", None),
                    "instructions": None,
                    "min_age": None,
                },
                "checkout": {
                    "time": hotel.get("check_out_time", None),
                },
                "fees": {"optional": None},
                "know_before_you_go": None,
                "pets": None,
                "remark": None,
                "child_and_extra_bed_policy": {
                    "infant_age": None,
                    "children_age_from": None,
                    "children_age_to": None,
                    "children_stay_free": None,
                    "min_guest_age": None,
                },
                "nationality_restrictions": None,
            },
            "address": {
                "latitude": safe_get(hotel, ["geo_coordinates", "latitude"]),
                "longitude": safe_get(hotel, ["geo_coordinates", "longitude"]),
                "address_line_1": address,
                "address_line_2": None,
                "city": None,
                "state": None,
                "country": "Bangladesh",
                "country_code": "BD",
                "postal_code": safe_get(hotel, ["post_code"]),
                "full_address": address,
                "google_map_site_link": google_map_site_link,
                "local_lang": {
                    "latitude": safe_get(hotel, ["geo_coordinates", "latitude"]),
                    "longitude": safe_get(hotel, ["geo_coordinates", "longitude"]),
                    "address_line_1": address,
                    "address_line_2": None,
                    "city": None,
                    "state": None,
                    "country": "Bangladesh",
                    "country_code": "BD",
                    "postal_code": safe_get(hotel, ["post_code"]),
                    "full_address": address,
                    "google_map_site_link": google_map_site_link,
                },
                "mapping": {
                    "continent_id": None,
                    "country_id": None,
                    "province_id": None,
                    "state_id": None,
                    "city_id": None,
                    "area_id": None,
                },
            },
            "contacts": {
                "phone_numbers": [safe_get(hotel, ["contacts", "phone"])],
                "fax": None,
                "email_address": [safe_get(hotel, ["contacts", "email"])],
                "website": [safe_get(hotel, ["contacts", "webpage"])],
            },
            "descriptions": [{"title": None, "text": hotel.get("description", None)}],
            "room_type": room_type,
            "spoken_languages": [
                {
                    "type": "spoken_languages",
                    "title": "English",
                    "icon": "mdi mdi-translate-variant",
                }
            ],
            "amenities": structured_amenities,
            "facilities": None,
            "hotel_photo": hotel_photo,
            "point_of_interests": None,
            "nearest_airports": None,
            "train_stations": None,
            "connected_locations": None,
            "stadiums": None,
        }

    elif supplier_code == "irixhotel":
        createdAt = datetime.now()
        createdAt_str = createdAt.strftime("%Y-%m-%dT%H:%M:%S")
        created_at_dt = datetime.strptime(createdAt_str, "%Y-%m-%dT%H:%M:%S")
        timeStamp = int(created_at_dt.timestamp())

        def safe_get(d, keys, default=None):
            """Safely access nested dictionary keys."""
            for key in keys:
                if isinstance(d, dict):
                    d = d.get(key, default)
                else:
                    return default
            return d

        def get_country_details(xml_path, target_country_id):
            try:
                tree = ET.parse(xml_path)
                root = tree.getroot()
                for country in root.findall("Country"):
                    if country.attrib.get("ID") == str(target_country_id):
                        return {
                            "country": country.attrib.get("Name"),
                            "country_code": country.attrib.get("ISO"),
                        }
            except ET.ParseError:
                print(f"âŒ Failed to parse XML file: {xml_path}")
            return None

        def get_city_details(xml_path, target_city_id):
            try:
                tree = ET.parse(xml_path)
                root = tree.getroot()
                for city in root.findall("City"):
                    if city.attrib.get("ID") == str(target_city_id):
                        return {
                            "city": city.attrib.get("Name"),
                            "city_code": city.attrib.get("Code"),
                        }
            except ET.ParseError:
                print(f"âŒ Failed to parse XML file: {xml_path}")
            return None

        # Base hotel
        hotel = safe_get(data, ["HotelDetails"], {})

        address_line_1 = safe_get(hotel, ["Address"], None)
        hotel_name = safe_get(hotel, ["Name"], None)
        address_query = f"{address_line_1}, {hotel_name}"
        google_map_site_link = (
            f"http://maps.google.com/maps?q={address_query.replace(' ', '+')}"
            if address_line_1
            else None
        )

        # Here we get value form xml file.
        countryId = safe_get(hotel, ["CountryID"], None)
        input_country_xml_path = os.path.join(IRIX_STATIC_DIR, "Countries.xml")
        cityId = safe_get(hotel, ["CityID"], None)
        input_city_xml_path = os.path.join(IRIX_STATIC_DIR, "Cities.xml")

        # Get country details from XML
        country_details = get_country_details(input_country_xml_path, countryId)

        if country_details:
            country = country_details["country"]
            country_code = country_details["country_code"]
            # print(f"âœ… Country Found: {country} ({country_code})")
        else:
            country = None
            country_code = None

        # Get city details from XML
        city_details = get_city_details(input_city_xml_path, cityId)

        if city_details:
            city = city_details["city"]
            city_code = city_details["city_code"]
            # print(f"âœ… City Found: {city} ({city_code})")
        else:
            city = None
            city_code = None

        # Extract image list
        gallery_data = safe_get(hotel, ["Gallery", "GalleryImage"], [])

        pictures = []
        primary_photo = None

        for index, img in enumerate(gallery_data):
            url = img.get("URL", None)
            if url:
                if index == 0:
                    primary_photo = url

                pictures.append({"picture_id": None, "title": None, "url": url})

        # Extracted structured facilities
        facility_data = safe_get(hotel, ["Facilities", "Facility"], [])
        facilities = []

        for item in facility_data:
            title = item.get("Text", "")
            if title:
                facilities.append(
                    {"type": title, "title": title, "icon": "mdi mdi-translate-variant"}
                )

        # Descriptions Section
        desc = safe_get(data, ["Descriptions"], {})
        descriptions_data = []

        # Short Description
        short_text = desc.get("ShortDescription", "").strip()
        if short_text:
            descriptions_data.append({"title": "Short Description", "text": short_text})

        # Full Description
        full_text = desc.get("FullDescription", "").strip()
        if full_text:
            descriptions_data.append({"title": "Full Description", "text": full_text})

        return {
            "created": createdAt_str,
            "timestamp": timeStamp,
            "hotel_id": safe_get(hotel, ["ID"]),
            "name": safe_get(hotel, ["Name"], None),
            "name_local": safe_get(hotel, ["Name"], None),
            "hotel_formerly_name": safe_get(hotel, ["Name"], None),
            "destination_code": None,
            "country_code": country_code,
            "brand_text": None,
            "property_type": safe_get(hotel, ["Type"], None),
            "star_rating": safe_get(hotel, ["Stars"], None),
            "chain": None,
            "brand": None,
            "logo": None,
            "primary_photo": primary_photo,
            "review_rating": {
                "source": None,
                "number_of_reviews": None,
                "rating_average": None,
                "popularity_score": None,
            },
            "policies": {
                "check_in": {
                    "begin_time": None,
                    "end_time": None,
                    "instructions": None,
                    "min_age": None,
                },
                "checkout": {"time": None},
                "fees": {"optional": None},
                "know_before_you_go": None,
                "pets": [],
                "remark": None,
                "child_and_extra_bed_policy": {
                    "infant_age": None,
                    "children_age_from": None,
                    "children_age_to": None,
                    "children_stay_free": None,
                    "min_guest_age": None,
                },
                "nationality_restrictions": None,
            },
            "address": {
                "latitude": safe_get(hotel, ["Position", "Latitude"], None),
                "longitude": safe_get(hotel, ["Position", "Longitude"], None),
                "address_line_1": safe_get(hotel, ["Address"], None),
                "address_line_2": None,
                "city": city,
                "state": None,
                "country": country,
                "country_code": country_code,
                "postal_code": None,
                "full_address": safe_get(hotel, ["Address"], None),
                "google_map_site_link": google_map_site_link,
                "local_lang": {
                    "latitude": safe_get(hotel, ["Position", "Latitude"], None),
                    "longitude": safe_get(hotel, ["Position", "Longitude"], None),
                    "address_line_1": safe_get(hotel, ["Address"], None),
                    "address_line_2": None,
                    "city": city,
                    "state": None,
                    "country": country,
                    "country_code": country_code,
                    "postal_code": None,
                    "full_address": safe_get(hotel, ["Address"], None),
                    "google_map_site_link": google_map_site_link,
                },
                "mapping": {
                    "continent_id": None,
                    "country_id": safe_get(hotel, ["CountryID"], None),
                    "province_id": None,
                    "state_id": None,
                    "city_id": safe_get(hotel, ["CityID"], None),
                    "area_id": None,
                },
            },
            "contacts": {
                "phone_numbers": [safe_get(hotel, ["Contact", "Phone"], None)],
                "fax": [safe_get(hotel, ["Contact", "Fax"], None)],
                "email_address": [safe_get(hotel, ["Contact", "Email"], None)],
                "website": [safe_get(hotel, ["Contact", "Website"], None)],
            },
            "descriptions": [{"title": None, "text": None}],
            "room_type": None,
            "spoken_languages": [
                {
                    "type": "spoken_languages",
                    "title": "English",
                    "icon": "mdi mdi-translate-variant",
                }
            ],
            "amenities": None,
            "facilities": facilities,
            "hotel_photo": pictures,
            "point_of_interests": None,
            "nearest_airports": None,
            "train_stations": None,
            "connected_locations": None,
            "stadiums": None,
        }

    elif supplier_code == "kiwihotel":
        createdAt = datetime.now()
        createdAt_str = createdAt.strftime("%Y-%m-%dT%H:%M:%S")
        created_at_dt = datetime.strptime(createdAt_str, "%Y-%m-%dT%H:%M:%S")
        timeStamp = int(created_at_dt.timestamp())

        def safe_get(d, keys, default=None):
            """Safely access nested dictionary keys."""
            for key in keys:
                if isinstance(d, dict):
                    d = d.get(key, default)
                else:
                    return default
            return d

        # Base hotel
        hotel = safe_get(data, ["PropertyDetailResponse", "PropertyInfo"], {})

        hotel_code = safe_get(hotel, ["@Code"], None)

        hotel_provider_details = safe_get(
            data, ["PropertyDetailResponse", "PropertyInfo", "PropertyDetails"], {}
        )
        hotel_name = safe_get(hotel_provider_details, ["@Title"], None)
        website = safe_get(hotel_provider_details, ["@WebsiteURL"], None)
        logo = safe_get(hotel_provider_details, ["@PropertyLogoURL"], None)
        brand = safe_get(hotel_provider_details, ["@Brand"], None)
        dreamTextdescription = safe_get(hotel_provider_details, ["DreamText"], None)

        description = safe_get(hotel_provider_details, ["Description"], None)

        star_rating = safe_get(hotel_provider_details, ["Rating", "StarRating"], None)

        location_info = safe_get(hotel_provider_details, ["LocationInfo"], None)

        kiwi_rating = safe_get(hotel_provider_details, ["Rating", "KiwiRating"], None)

        review_rating = None

        if kiwi_rating:
            # Extract all @attribute values
            attrs = {k[1:]: v for k, v in kiwi_rating.items() if k.startswith("@")}

            # Build the source string (key=value#key=value...)
            source_str = "#".join([f"{k}={v}" for k, v in attrs.items()])

            # Extract rating average (#text)
            rating_avg = kiwi_rating.get("#text", None)

        longitude = safe_get(location_info, ["@Longitude"], None)
        latitude = safe_get(location_info, ["@Latitude"], None)

        location_info_address = safe_get(
            hotel_provider_details, ["LocationInfo", "Address"], None
        )
        addressLine1 = safe_get(location_info_address, ["@AddressLine1"], None)
        addressLine2 = safe_get(location_info_address, ["@AddressLine2"], None)
        addressLine3 = safe_get(location_info_address, ["@AddressLine3"], None)
        city = safe_get(location_info_address, ["@City"], None)
        region = safe_get(location_info_address, ["@Region"], None)
        regionCode = safe_get(location_info_address, ["@RegionIsoCode"], None)
        country = safe_get(location_info_address, ["@Country"], None)
        country_code = safe_get(location_info_address, ["@CountryIsoCode"], None)
        area = safe_get(location_info_address, ["@Area"], None)
        zone = safe_get(location_info_address, ["@Zone"], None)
        zip_code = safe_get(location_info_address, ["@ZipCode"], None)

        address_line_1 = addressLine1
        hotel_name = hotel_name
        address_query = f"{address_line_1}, {hotel_name}"
        google_map_site_link = (
            f"http://maps.google.com/maps?q={address_query.replace(' ', '+')}"
            if address_line_1
            else None
        )

        airport_info = safe_get(
            hotel_provider_details,
            ["LocationInfo", "NearbyAirports", "NearbyAirport"],
            None,
        )

        # This is nearest airport section.
        nearest_airport = []
        if airport_info:
            # Normalize to list (because xmltodict may return dict if only one airport exists)
            if isinstance(airport_info, dict):
                airport_info = [airport_info]

            for a in airport_info:
                code = a.get("@Code")
                name = a.get("@Name")
                if code and name:
                    nearest_airport.append({"code": code, "name": name})

        # This is contacts section.
        phone_info = safe_get(
            hotel_provider_details, ["PhoneNumbers", "PhoneNumber"], None
        )

        phone_number = []
        if phone_info:
            if isinstance(phone_info, dict):
                phone_info = [phone_info]

            for p in phone_info:
                num = p.get("@Number")
                if num and num.strip():
                    phone_number.append(num.strip())

        # This is all photo section.
        image_info = safe_get(hotel_provider_details, ["ImageUrls", "ImageURL"], None)

        hotel_photo = []
        primary_photo = None

        if image_info:
            if isinstance(image_info, dict):
                image_info = [image_info]

            for img in image_info:
                img_size = img.get("@Size")
                img_url = img.get("#text")

                if img_size == "xxl" and img_url and img_url.strip():
                    hotel_photo.append(
                        {"picture_id": None, "title": None, "url": img_url.strip()}
                    )

            if hotel_photo:
                primary_photo = hotel_photo[0]["url"]

        amenities_info = safe_get(
            hotel_provider_details, ["Features", "Amenities", "Amenity"], None
        )

        amenities = []
        if amenities_info:
            # Normalize to list (xmltodict returns str if only one item)
            if isinstance(amenities_info, str):
                amenities_info = [amenities_info]

            for a in amenities_info:
                if a and isinstance(a, str):
                    amenities.append(
                        {
                            "type": a.strip(),
                            "title": a.strip(),
                            "icon": "mdi mdi-translate-variant",
                        }
                    )

        return {
            "created": createdAt_str,
            "timestamp": timeStamp,
            "hotel_id": hotel_code,
            "name": hotel_name,
            "name_local": hotel_name,
            "hotel_formerly_name": hotel_name,
            "destination_code": None,
            "country_code": country_code,
            "brand_text": None,
            "property_type": None,
            "star_rating": star_rating,
            "chain": None,
            "brand": brand,
            "logo": logo,
            "primary_photo": primary_photo,
            "review_rating": {
                "source": source_str,
                "number_of_reviews": None,
                "rating_average": float(rating_avg) if rating_avg else None,
                "popularity_score": None,
            },
            "policies": {
                "check_in": {
                    "begin_time": None,
                    "end_time": "12:00",
                    "instructions": None,
                    "min_age": None,
                },
                "checkout": {"time": "12:00"},
                "fees": {"optional": None},
                "know_before_you_go": None,
                "pets": "The Peninsula London welcomes small domestic pets/emotional support animals/service animals. All service animals require a document of authentication at time of check-in. Pets are not permitted in any of the hotels restaurants.",
                "remark": None,
                "child_and_extra_bed_policy": {
                    "infant_age": None,
                    "children_age_from": None,
                    "children_age_to": 12,
                    "children_stay_free": None,
                    "min_guest_age": None,
                },
                "nationality_restrictions": None,
            },
            "address": {
                "latitude": latitude,
                "longitude": longitude,
                "address_line_1": addressLine1,
                "address_line_2": f"{addressLine2},{addressLine3}",
                "city": city,
                "state": zone,
                "country": country,
                "country_code": country_code,
                "postal_code": zip_code,
                "full_address": f"{addressLine1},{addressLine2},{addressLine3},{city},{country}",
                "google_map_site_link": google_map_site_link,
                "local_lang": {
                    "latitude": latitude,
                    "longitude": longitude,
                    "address_line_1": addressLine1,
                    "address_line_2": f"{addressLine2},{addressLine3}",
                    "city": city,
                    "state": zone,
                    "country": country,
                    "country_code": country_code,
                    "postal_code": zip_code,
                    "full_address": f"{addressLine1},{addressLine2},{addressLine3},{city},{country}",
                    "google_map_site_link": google_map_site_link,
                },
                "mapping": {
                    "continent_id": None,
                    "country_id": None,
                    "province_id": None,
                    "state_id": None,
                    "city_id": None,
                    "area_id": None,
                },
            },
            "contacts": {
                "phone_numbers": phone_number,
                "fax": [safe_get(hotel, ["Contact", "Fax"], None)],
                "email_address": [safe_get(hotel, ["Contact", "Email"], None)],
                "website": [website],
            },
            "descriptions": [
                {"title": "DreamTextdescription", "text": f"{dreamTextdescription}"},
                {"title": "Description", "text": f"{description}"},
            ],
            "room_type": None,
            "spoken_languages": [
                {
                    "type": "spoken_languages",
                    "title": "English",
                    "icon": "mdi mdi-translate-variant",
                }
            ],
            "amenities": amenities,
            "facilities": None,
            "hotel_photo": hotel_photo,
            "point_of_interests": None,
            "nearest_airports": nearest_airport,
            "train_stations": None,
            "connected_locations": None,
            "stadiums": None,
        }

    # Add more mappings for other suppliers as needed
    else:
        raise HTTPException(status_code=400, detail="Unknown provider mapping")


@router.post("/details", status_code=status.HTTP_200_OK)
async def convert_row_to_our_formate(
    request_body: ConvertRequest,
    request: Request,
    current_user: Annotated[models.User, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
):
    """
    **Get Hotel Details & Convert to Standard Format**
    
    Retrieve and convert raw hotel data from suppliers to standardized format.
    
    **SECURITY:** Requires authentication, IP whitelist validation, and supplier permission checks.
    
    **Use Cases:**
    - Get formatted hotel information for display
    - Convert supplier-specific data to unified format
    - Retrieve hotel details for booking systems
    - Data integration and normalization
    - Hotel comparison across suppliers
    
    **Access Control:**
    - **SUPER_USER**: Access to all suppliers
    - **ADMIN_USER**: Access to all suppliers  
    - **GENERAL_USER**: Access only to permitted suppliers
    - **IP Whitelist**: User's IP address must be whitelisted
    
    **Supported Suppliers:**
    - `hotelbeds`: HotelBeds API data
    - `paximum`: Paximum supplier data
    - `stuba`: Stuba API integration
    
    **Request Body:**
    ```json
    {
      "supplier_code": "hotelbeds",
      "hotel_id": "12345"
    }
    ```
    
    **Example Usage:**
    ```bash
    curl -X POST "/v1.0/hotel/details" \
         -H "Authorization: Bearer your_token" \
         -H "Content-Type: application/json" \
         -d '{
           "supplier_code": "hotelbeds",
           "hotel_id": "HTL123456"
         }'
    ```
    
    **Response Format:**
    ```json
    {
      "created": "2024-01-15T10:30:00",
      "timestamp": 1705312200,
      "hotel_id": "HTL123456",
      "name": "Grand Hotel Example",
      "star_rating": "5",
      "address": {
        "latitude": 40.7128,
        "longitude": -74.0060,
        "full_address": "123 Main St, New York, USA"
      },
      "room_type": [...],
      "facilities": [...],
      "hotel_photo": [...]
    }
    ```
    
    **Security Features:**
    - IP whitelist validation
    - Supplier permission validation
    - Comprehensive audit logging
    - Role-based access control
    - Unauthorized access attempt tracking
    
    **Error Responses:**
    - `403 Forbidden`: IP not whitelisted OR no permission for supplier
    - `404 Not Found`: Hotel data not found
    - `500 Internal Error`: JSON parsing or file issues
    """

    supplier_code = request_body.supplier_code
    hotel_id = request_body.hotel_id

    # 🔒 IP WHITELIST VALIDATION
    print(f"🚀 IP whitelist check for user: {current_user.id} in /v1.0/hotel/details")
    if not check_ip_whitelist(current_user.id, request, db):
        client_ip = get_client_ip(request) or "unknown"
        
        # 📝 AUDIT LOG: Record IP whitelist violation
        audit_logger = AuditLogger(db)
        audit_logger.log_security_event(
            activity_type=ActivityType.UNAUTHORIZED_ACCESS_ATTEMPT,
            user_id=current_user.id,
            request=request,
            details={
                "endpoint": "/v1.0/hotel/details",
                "action": "access_denied_ip_not_whitelisted",
                "client_ip": client_ip,
                "supplier_code": supplier_code,
                "hotel_id": hotel_id,
                "reason": "IP address not in whitelist",
            },
            security_level=SecurityLevel.HIGH,
        )
        
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={
                "error": True,
                "message": "Access denied: IP address not whitelisted",
                "error_code": "IP_NOT_WHITELISTED",
                "details": {
                    "status_code": 403,
                    "client_ip": client_ip,
                    "user_id": current_user.id,
                    "message": "Your IP address is not in the whitelist. Please contact your administrator to add your IP address to the whitelist."
                },
                "timestamp": datetime.utcnow().isoformat()
            }
        )

    # 🔒 SUPPLIER PERMISSION CHECK: Verify user has access to this supplier
    # Super users and admin users have access to all suppliers
    if current_user.role not in [
        models.UserRole.SUPER_USER,
        models.UserRole.ADMIN_USER,
    ]:
        # Check if general user has permission for this supplier
        user_supplier_permission = (
            db.query(models.UserProviderPermission)
            .filter(
                models.UserProviderPermission.user_id == current_user.id,
                models.UserProviderPermission.provider_name == supplier_code,
            )
            .first()
        )

        if not user_supplier_permission:
            # 📝 AUDIT LOG: Record unauthorized supplier access attempt
            audit_logger = AuditLogger(db)
            audit_logger.log_security_event(
                activity_type=ActivityType.UNAUTHORIZED_ACCESS_ATTEMPT,
                user_id=current_user.id,
                request=request,
                details={
                    "endpoint": "/v1.0/hotel/details",
                    "action": "access_denied_supplier_not_active",
                    "supplier_code": supplier_code,
                    "hotel_id": hotel_id,
                    "reason": "User does not have permission for this supplier",
                },
                security_level=SecurityLevel.HIGH,
            )

            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Access denied. You do not have permission to access data from supplier '{supplier_code}'. Please contact your administrator to activate this supplier.",
            )

    # 📝 AUDIT LOG: Record successful hotel details access
    audit_logger = AuditLogger(db)
    audit_logger.log_activity(
        activity_type=ActivityType.API_ACCESS,
        user_id=current_user.id,
        details={
            "endpoint": "/v1.0/hotel/details",
            "action": "access_hotel_details",
            "supplier_code": supplier_code,
            "hotel_id": hotel_id,
            "user_role": current_user.role,
        },
        request=request,
        security_level=SecurityLevel.MEDIUM,
        success=True,
    )

    # Process the hotel data
    file_path = os.path.join(RAW_BASE_DIR, supplier_code, f"{hotel_id}.json")
    try:
        with open(file_path, "r", encoding="utf-8") as f:
            content = json.load(f)
        formatted = map_to_our_format(supplier_code, content)
        return formatted
    except FileNotFoundError:
        raise HTTPException(
            status_code=404,
            detail=f"Hotel data not found for supplier '{supplier_code}' and hotel ID '{hotel_id}'",
        )
    except json.JSONDecodeError:
        raise HTTPException(status_code=500, detail="Invalid JSON file")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
