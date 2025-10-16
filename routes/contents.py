from fastapi import APIRouter, Depends, HTTPException, status, Query, Body
from sqlalchemy.orm import Session, joinedload
from sqlalchemy import func
from database import get_db
from models import Hotel, ProviderMapping, Location, Contact, UserProviderPermission, UserRole
from pydantic import BaseModel
from typing import List, Optional, Annotated, Dict, Any
from datetime import datetime
from utils import deduct_points_for_general_user, require_role
import models
import secrets
import string
from fastapi_cache.decorator import cache
import csv
import redis
import json

def serialize_datetime_objects(obj):
    """Convert datetime objects to ISO format strings for JSON serialization."""
    if hasattr(obj, '__dict__'):
        result = {}
        for key, value in obj.__dict__.items():
            if key.startswith('_'):
                continue
            if isinstance(value, datetime):
                result[key] = value.isoformat() if value else None
            else:
                result[key] = value
        return result
    return obj
import os
from routes.auth import get_current_user

from schemas import ProviderProperty, GetAllHotelResponse

router = APIRouter()


router = APIRouter(
    prefix="/v1.0/content",
    tags=["Hotel Content"],
    responses={404: {"description": "Not found"}},
)


class ProviderHotelIdentity(BaseModel):
    provider_id: str
    provider_name: str

class ProviderHotelRequest(BaseModel):
    provider_hotel_identity: List[ProviderHotelIdentity]


class CountryInfoRequest(BaseModel):
    supplier: str
    country_iso: str


@router.post("/get_basic_country_info", status_code=status.HTTP_200_OK)
def get_basic_country_info(
    request: CountryInfoRequest,
    current_user: Annotated[models.User, Depends(get_current_user)],
) -> Dict[str, Any]:
    try:
        # Construct the file path
        base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))  # Go up to backend directory
        file_path = os.path.join(
            base_dir, 
            "static", 
            "countryJson", 
            request.supplier, 
            f"{request.country_iso}.json"
        )
        
        # Check if file exists
        if not os.path.exists(file_path):
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Country data not found for supplier '{request.supplier}' and country '{request.country_iso}'"
            )
        
        # Read and parse JSON file
        with open(file_path, 'r', encoding='utf-8') as file:
            country_data = json.load(file)
        
        # Calculate total hotel count
        total_hotel = len(country_data) if isinstance(country_data, list) else 0
        
        return {
            "success": True,
            "supplier": request.supplier,
            "country_iso": request.country_iso,
            "total_hotel": total_hotel,
            "data": country_data
        }
        
    except json.JSONDecodeError as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Invalid JSON format in country data file: {str(e)}"
        )
    except FileNotFoundError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Country data not found for supplier '{request.supplier}' and country '{request.country_iso}'"
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error reading country data: {str(e)}"
        )


@router.post("/get_hotel_data_provider_name_and_id", status_code=status.HTTP_200_OK)
def get_hotel_data_provider_name_and_id(
    request: ProviderHotelRequest,
    current_user: Annotated[models.User, Depends(get_current_user)],
    db: Session = Depends(get_db)
):
    # Deduct points for general_user
    if current_user.role == models.UserRole.GENERAL_USER:
        deduct_points_for_general_user(current_user, db)

        # load permissions
        allowed_providers = [
            p.provider_name
            for p in db.query(UserProviderPermission)
                      .filter(UserProviderPermission.user_id == current_user.id)
                      .all()
        ]
        # **early error if truly no permissions**
        if not allowed_providers:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="you have not any permission for this request."
            )
    else:
        # if you really want _everyone else_ blocked until you grant, 
        # you could also force them into the same error here.
        allowed_providers = None
        print("Allowed providers for user:", allowed_providers)
        print("Requested identities:", [vars(i) for i in request.provider_hotel_identity])
  

    # now you know GENERAL_USER has at least one allowed_provider
    # (or everyone else is None → full access)

    result = []
    for identity in request.provider_hotel_identity:
        name = identity.provider_name
        pid = identity.provider_id
        if allowed_providers and name not in allowed_providers:
            print(f"User not allowed for provider: {name}")
            continue

        mapping = (
            db.query(ProviderMapping)
            .filter_by(provider_id=pid, provider_name=name)
            .first()
        )
        if not mapping:
            print(f"No mapping found for provider_id={pid}, provider_name={name}")
            continue

        hotel = db.query(Hotel).filter(Hotel.ittid == mapping.ittid).first()
        if not hotel:
            print(f"No hotel found for ittid={mapping.ittid}")
            continue

        locations = db.query(Location).filter(Location.ittid == hotel.ittid).all()
        contacts  = db.query(Contact).filter(Contact.ittid == hotel.ittid).all()

        # Build hotel dict with only the required fields and order
        hotel_dict = {
            "ittid": hotel.ittid,
            "id": hotel.id,
            "name": hotel.name,
            "property_type": hotel.property_type,
            "longitude": hotel.longitude,
            "latitude": hotel.latitude,
            "address_line1": hotel.address_line1,
            "address_line2": hotel.address_line2,
            "postal_code": hotel.postal_code,
            "rating": hotel.rating,
            "primary_photo": hotel.primary_photo,
            "map_status": hotel.map_status,
            "updated_at": hotel.updated_at.isoformat() if hotel.updated_at else None,
            "created_at": hotel.created_at.isoformat() if hotel.created_at else None,
        }

        # Build provider_mappings list with only the required fields and order
        provider_mappings_list = [{
            "id": mapping.id,
            "provider_id": mapping.provider_id,
            "provider_name": mapping.provider_name,
            "system_type": mapping.system_type,
            "giata_code": mapping.giata_code,
            "vervotech_id": mapping.vervotech_id,
            # "updated_at": mapping.updated_at.isoformat() if mapping.updated_at else None,
            # "created_at": mapping.created_at.isoformat() if mapping.created_at else None,
        }]

        # Build locations list with only the required fields and order
        locations_list = [{
            "id": loc.id,
            "city_name": loc.city_name,
            "city_code": loc.city_code,
            "city_code": loc.city_code,
            "master_city_name": loc.master_city_name,
            "state_name": loc.state_name,
            "state_code": loc.state_code,
            "country_name": loc.country_name,
            "country_code": loc.country_code,
            # "created_at": loc.created_at.isoformat() if loc.created_at else None,
            # "updated_at": loc.updated_at.isoformat() if loc.updated_at else None,
        } for loc in locations]

        # Build contacts list with only the required fields and order
        contacts_list = [{
            "id": c.id,
            "contact_type": c.contact_type,
            "value": c.value
        } for c in contacts]

        result.append({
            "hotel": hotel_dict,
            "provider_mappings": provider_mappings_list,
            "locations": locations_list,
            "contacts": contacts_list
        })

    if not result:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Cannot mapping supplier in our system."
        )

    return result


class ProviderHotelIdentity(BaseModel):
    provider_id: str
    provider_name: str

class ProviderHotelRequest(BaseModel):
    provider_hotel_identity: List[ProviderHotelIdentity]


@router.post("/get_hotel_mapping_data_using_provider_name_and_id", status_code=status.HTTP_200_OK)
def get_hotel_mapping_data_using_provider_name_and_id(
    request: ProviderHotelRequest,
    current_user: Annotated[models.User, Depends(get_current_user)],
    db: Session = Depends(get_db)
):
    # Deduct points for general_user
    if current_user.role == models.UserRole.GENERAL_USER:
        deduct_points_for_general_user(current_user, db)

        # load permissions
        allowed_providers = [
            p.provider_name
            for p in db.query(UserProviderPermission)
                      .filter(UserProviderPermission.user_id == current_user.id)
                      .all()
        ]
        # **early error if truly no permissions**
        if not allowed_providers:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="you have not any permission for this request."
            )
    else:
        # if you really want _everyone else_ blocked until you grant, 
        # you could also force them into the same error here.
        allowed_providers = None
        print("Allowed providers for user:", allowed_providers)
        print("Requested identities:", [vars(i) for i in request.provider_hotel_identity])
  

    # now you know GENERAL_USER has at least one allowed_provider
    # (or everyone else is None → full access)

    result = []
    for identity in request.provider_hotel_identity:
        name = identity.provider_name
        pid = identity.provider_id
        if allowed_providers and name not in allowed_providers:
            print(f"User not allowed for provider: {name}")
            continue

        mapping = (
            db.query(ProviderMapping)
            .filter_by(provider_id=pid, provider_name=name)
            .first()
        )
        if not mapping:
            print(f"No mapping found for provider_id={pid}, provider_name={name}")
            continue

        hotel = db.query(Hotel).filter(Hotel.ittid == mapping.ittid).first()
        if not hotel:
            print(f"No hotel found for ittid={mapping.ittid}")
            continue


        # Build provider_mappings list with only the required fields and order
        provider_mappings_list = [{
            "ittid": hotel.ittid,
            "provider_mapping_id": mapping.id,
            "provider_id": mapping.provider_id,
            "provider_name": mapping.provider_name,
            "system_type": mapping.system_type,
            # "giata_code": mapping.giata_code,
            # "vervotech_id": mapping.vervotech_id,
            # "updated_at": mapping.updated_at.isoformat() if mapping.updated_at else None,
            "created_at": mapping.created_at.isoformat() if mapping.created_at else None,
        }]



        result.append({
            "provider_mappings": provider_mappings_list
        })

    if not result:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Cannot mapping supplier in our system."
        )

    return result


class ITTIDRequest(BaseModel):
    ittid: List[str]

# Get provider mapping
@router.post("/get_hotel_with_ittid", status_code=status.HTTP_200_OK)
def get_hotels_using_ittid_list(
    request: ITTIDRequest,
    current_user: Annotated[models.User, Depends(get_current_user)],
    db: Session = Depends(get_db)
):
    """Get only provider_mappings by ITTID list."""

    # 🚫 NO POINT DEDUCTION for super_user and admin_user
    if current_user.role == models.UserRole.GENERAL_USER:
        deduct_points_for_general_user(current_user, db)
    elif current_user.role in [models.UserRole.SUPER_USER, models.UserRole.ADMIN_USER]:
        print(f"🔓 Point deduction skipped for {current_user.role}: {current_user.email}")

    # Fetch hotels
    hotels = db.query(models.Hotel).filter(models.Hotel.ittid.in_(request.ittid)).all()
    if not hotels:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No hotels found for the provided ittid values."
        )

    result = []

    # For General Users: only allowed providers
    if current_user.role == models.UserRole.GENERAL_USER:
        allowed_providers = [
            permission.provider_name
            for permission in db.query(UserProviderPermission)
            .filter(UserProviderPermission.user_id == current_user.id)
            .all()
        ]
        for hotel in hotels:
            provider_mappings = db.query(models.ProviderMapping).filter(
                models.ProviderMapping.ittid == hotel.ittid,
                models.ProviderMapping.provider_name.in_(allowed_providers)
            ).all()

            formatted_provider_mappings = [
                {
                    "id": mapping.id,
                    "provider_id": mapping.provider_id,
                    "provider_name": mapping.provider_name,
                    "system_type": mapping.system_type,
                    "vervotech_id": mapping.vervotech_id,
                    "giata_code": mapping.giata_code,
                }
                for mapping in provider_mappings
            ]

            result.append({
                "ittid": hotel.ittid,
                "provider_mappings": formatted_provider_mappings
            })
    else:
        # For SUPER/ADMIN users – return all mappings
        for hotel in hotels:
            provider_mappings = db.query(models.ProviderMapping).filter(
                models.ProviderMapping.ittid == hotel.ittid
            ).all()

            formatted_provider_mappings = [
                {
                    "id": mapping.id,
                    "provider_id": mapping.provider_id,
                    "provider_name": mapping.provider_name,
                    "system_type": mapping.system_type,
                    "vervotech_id": mapping.vervotech_id,
                    "giata_code": mapping.giata_code,
                }
                for mapping in provider_mappings
            ]

            result.append({
                "ittid": hotel.ittid,
                "provider_mappings": formatted_provider_mappings
            })

    return result

@router.get("/get_hotel_with_ittid/{ittid}", status_code=status.HTTP_200_OK)
def get_hotel_using_ittid(
    ittid: str,
    current_user: Annotated[models.User, Depends(get_current_user)],
    db: Session = Depends(get_db)
):
    """Get hotel details by ITTID. Points deducted only for successful requests. Requires active suppliers."""
    
    # Get hotel first (no point deduction yet)
    hotel = db.query(models.Hotel).filter(models.Hotel.ittid == ittid).first()
    if not hotel:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Hotel with id '{ittid}' not found."
        )

    # 🔍 CHECK FOR ACTIVE SUPPLIERS (Provider Mappings)
    # First check if there are ANY provider mappings for this ITTID
    all_provider_mappings = db.query(models.ProviderMapping).filter(
        models.ProviderMapping.ittid == ittid
    ).all()
    
    if not all_provider_mappings:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Cannot active supplier with this ittid '{ittid}'. No supplier mappings found for this hotel."
        )

    # Check user-specific permissions for general users
    if current_user.role == models.UserRole.GENERAL_USER:
        allowed_providers = [
            permission.provider_name
            for permission in db.query(UserProviderPermission)
            .filter(UserProviderPermission.user_id == current_user.id)
            .all()
        ]
        if not allowed_providers:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Do not have permission or not active"
            )
        
        # Check if user has access to any of the suppliers for this hotel
        accessible_provider_mappings = db.query(models.ProviderMapping).filter(
            models.ProviderMapping.ittid == ittid,
            models.ProviderMapping.provider_name.in_(allowed_providers)
        ).all()
        
        if not accessible_provider_mappings:
            # Hotel exists and has suppliers, but user doesn't have access to any of them
            available_suppliers = [pm.provider_name for pm in all_provider_mappings]
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Cannot access suppliers for this ittid '{ittid}'. Available suppliers: {', '.join(available_suppliers)}. Contact admin for access."
            )
    
    print(f"✅ Active suppliers found for ITTID {ittid}: {len(all_provider_mappings)} suppliers")

    # Get related data
    locations = db.query(models.Location).filter(models.Location.ittid == hotel.ittid).all()
    chains = db.query(models.Chain).filter(models.Chain.ittid == hotel.ittid).all()
    contacts = db.query(models.Contact).filter(models.Contact.ittid == hotel.ittid).all()

    # Get provider mappings for response (based on user role)
    if current_user.role == models.UserRole.GENERAL_USER:
        # For general users, only show accessible provider mappings
        allowed_providers = [
            permission.provider_name
            for permission in db.query(UserProviderPermission)
            .filter(UserProviderPermission.user_id == current_user.id)
            .all()
        ]
        provider_mappings = db.query(models.ProviderMapping).filter(
            models.ProviderMapping.ittid == ittid,
            models.ProviderMapping.provider_name.in_(allowed_providers)
        ).all()
    else:
        # For super/admin users, show all provider mappings
        provider_mappings = all_provider_mappings

    # Serialize the response with provider mappings
    response_data = {
        "hotel": serialize_datetime_objects(hotel),
        "provider_mappings": [serialize_datetime_objects(pm) for pm in provider_mappings],
        "locations": [serialize_datetime_objects(loc) for loc in locations],
        "chains": [serialize_datetime_objects(chain) for chain in chains],
        "contacts": [serialize_datetime_objects(contact) for contact in contacts],
        "supplier_info": {
            "total_active_suppliers": len(all_provider_mappings),
            "accessible_suppliers": len(provider_mappings),
            "supplier_names": [pm.provider_name for pm in provider_mappings]
        }
    }

    # 💸 POINT DEDUCTION ONLY ON SUCCESSFUL REQUEST
    # Points are deducted only when the request is successful and data is returned
    if current_user.role == models.UserRole.GENERAL_USER:
        deduct_points_for_general_user(current_user, db)
        print(f"💸 Points deducted for successful request by general user: {current_user.email}")
    elif current_user.role in [models.UserRole.SUPER_USER, models.UserRole.ADMIN_USER]:
        print(f"🔓 Point deduction skipped for {current_user.role}: {current_user.email}")

    return response_data




@router.get("/get_all_hotel_info", status_code=status.HTTP_200_OK)
def get_all_hotels(
    current_user: Annotated[models.User, Depends(get_current_user)],
    page: int = Query(1, ge=1, description="Page number, starting from 1"),
    limit: int = Query(50, ge=1, le=1000, description="Number of hotels per page (max 1000)"),
    resume_key: Optional[str] = Query(None, description="Resume key for pagination - REQUIRED for pages after the first"),
    first_request: bool = Query(False, description="Set to true for the very first request to start pagination"),
    db: Session = Depends(get_db)
):
    """
    Get a paginated list of hotels with smart resume_key validation.
    
    PAGINATION LOGIC:
    - FIRST request: No resume_key needed (automatically detected)
    - SUBSEQUENT requests: Must provide valid resume_key from previous response
    
    Resume key format: {hotel_id}_{50_character_random_string}
    Only hotels accessible by the user's provider permissions are returned.
    Points deducted only for general users (super/admin users are exempt).
    Total hotel count shows actual database count using: SELECT COUNT(ittid) FROM hotels
    """

    # 🚫 NO POINT DEDUCTION for super_user and admin_user
    # Only deduct points for general_user
    if current_user.role == UserRole.GENERAL_USER:
        deduct_points_for_general_user(current_user, db)
        allowed_providers = [
            p.provider_name
            for p in db.query(UserProviderPermission)
                      .filter(UserProviderPermission.user_id == current_user.id)
                      .all()
        ]
        if not allowed_providers:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="You do not have any permission for this request."
            )
    elif current_user.role in [UserRole.SUPER_USER, UserRole.ADMIN_USER]:
        print(f"🔓 Point deduction skipped for {current_user.role}: {current_user.email}")
        allowed_providers = None
    else:
        allowed_providers = None

    # 🔒 SMART RESUME KEY VALIDATION
    # Determine if this is a first request or subsequent request
    is_first_request = not resume_key  # If no resume_key provided, treat as first request
    
    # If resume_key is provided, it must be valid (subsequent request)
    if resume_key:
        is_first_request = False
        print(f"📄 Subsequent request detected with resume_key: {resume_key[:20]}...")
    else:
        is_first_request = True
        print("📄 First request detected (no resume_key provided)")
    
    # Validate conflicting parameters (optional - can remove if not needed)
    if first_request and resume_key:
        print("⚠️  Warning: Both first_request=true and resume_key provided. Using resume_key logic.")
        is_first_request = False

    # 🔍 Enhanced resume_key validation (required for non-first requests)
    last_id = 0
    if resume_key:
        try:
            # Validate resume_key is not empty or just whitespace
            if not resume_key.strip():
                raise ValueError("Resume key cannot be empty")
            
            # Extract the ID from resume_key format: "id_randomstring"
            parts = resume_key.split("_", 1)
            if len(parts) != 2:
                raise ValueError("Invalid resume key format. Expected format: 'id_randomstring'")
            
            # Validate the ID part is a valid integer
            try:
                last_id = int(parts[0])
                if last_id <= 0:
                    raise ValueError("Invalid hotel ID in resume key")
            except ValueError:
                raise ValueError("Resume key must start with a valid hotel ID")
            
            random_part = parts[1]
            
            # Validate that the random part has expected length and characters
            if len(random_part) != 50:
                raise ValueError(f"Invalid random part length. Expected 50 characters, got {len(random_part)}")
            
            # Validate random part contains only alphanumeric characters
            if not random_part.isalnum():
                raise ValueError("Random part must contain only alphanumeric characters")
            
            # Check if the hotel ID actually exists in the database
            hotel_exists = db.query(models.Hotel).filter(
                models.Hotel.id == last_id
            ).first()
            
            if not hotel_exists:
                raise ValueError(f"Resume key references non-existent hotel record (ID: {last_id})")
            
            # For general users, also check if they have access to this hotel through their providers
            if allowed_providers is not None:
                hotel_accessible = db.query(models.ProviderMapping).filter(
                    models.ProviderMapping.ittid == hotel_exists.ittid,
                    models.ProviderMapping.provider_name.in_(allowed_providers)
                ).first()
                
                if not hotel_accessible:
                    raise ValueError(f"Resume key references hotel not accessible to user (ITTID: {hotel_exists.ittid})")
            
            print(f"✅ Valid resume_key: Starting from hotel ID {last_id}")
                
        except ValueError as e:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Invalid resume_key: {str(e)}. Please use a valid resume_key from a previous response or omit it to start from the beginning."
            )
        except Exception as e:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Error processing resume_key: {str(e)}. Please use a valid resume_key from a previous response."
            )

    query = db.query(Hotel).order_by(Hotel.id)
    if last_id:
        query = query.filter(Hotel.id > last_id)

    # Filter by allowed providers for general users
    if allowed_providers is not None:
        hotel_ids = db.query(ProviderMapping.ittid).filter(
            ProviderMapping.provider_name.in_(allowed_providers)
        ).distinct().all()
        hotel_ids = [h[0] for h in hotel_ids]
        query = query.filter(Hotel.ittid.in_(hotel_ids))

    hotels = query.limit(limit).all()

    # 🔑 Generate next resume_key with enhanced validation
    if hotels and len(hotels) == limit:
        last_hotel_id = hotels[-1].id
        # Generate cryptographically secure random string
        rand_str = ''.join(secrets.choice(string.ascii_letters + string.digits) for _ in range(50))
        next_resume_key = f"{last_hotel_id}_{rand_str}"
        print(f"📄 Generated resume_key for next page: {last_hotel_id}_[50-char-random]")
    else:
        next_resume_key = None
        print("📄 No more pages available - resume_key is null")

    # 🏨 Build hotel list with proper datetime serialization
    hotel_list = [
        {
            "ittid": hotel.ittid,
            "name": hotel.name,
            "property_type": hotel.property_type,
            "rating": hotel.rating,
            "address_line1": hotel.address_line1,
            "address_line2": hotel.address_line2,
            "postal_code": hotel.postal_code,
            "map_status": hotel.map_status,
            "geocode": {
                "latitude": hotel.latitude,
                "longitude": hotel.longitude
            },
            "updated_at": hotel.updated_at.isoformat() if hotel.updated_at else None,
            "created_at": hotel.created_at.isoformat() if hotel.created_at else None,
        }
        for hotel in hotels
    ]

    # 📊 Get ACTUAL total hotel count using: SELECT COUNT(ittid) FROM hotels
    # This shows the real total number of hotels in the database
    total_hotel = db.query(func.count(Hotel.ittid)).scalar()
    
    # Get accessible hotel count for user (for reference)
    if allowed_providers is not None:
        # Count only hotels accessible to general user
        accessible_hotel_ids = db.query(ProviderMapping.ittid).filter(
            ProviderMapping.provider_name.in_(allowed_providers)
        ).distinct().all()
        accessible_hotel_ids = [h[0] for h in accessible_hotel_ids]
        accessible_hotel_count = db.query(Hotel).filter(Hotel.ittid.in_(accessible_hotel_ids)).count()
    else:
        # Super/admin users can access all hotels
        accessible_hotel_count = total_hotel

    print(f"📊 Returning {len(hotel_list)} hotels out of {accessible_hotel_count} accessible hotels (Total in DB: {total_hotel})")

    return {
        "resume_key": next_resume_key,
        "page": page,
        "limit": limit,
        "total_hotel": total_hotel,  # Actual count from database: SELECT COUNT(ittid) FROM hotels
        "accessible_hotel_count": accessible_hotel_count,  # Hotels user can access
        "hotels": hotel_list,
        "pagination_info": {
            "current_page_count": len(hotel_list),
            "has_next_page": next_resume_key is not None,
            "user_role": current_user.role,
            "point_deduction_applied": current_user.role == UserRole.GENERAL_USER,
            "is_first_request": is_first_request,
            "resume_key_required_for_next": next_resume_key is not None
        },
        "usage_instructions": {
            "first_request": "No resume_key needed for the first request",
            "subsequent_requests": "Must provide valid resume_key from previous response for next pages",
            "resume_key_format": "{hotel_id}_{50_character_random_string}",
            "note": "resume_key is automatically required for subsequent requests"
        }
    }


class ProviderProperty(BaseModel):
    provider_name: str

class ProviderPropertyRequest(BaseModel):
    provider_property: List[ProviderProperty]


@router.get(
    "/get_all_hotel_only_supplier/",
    response_model=GetAllHotelResponse,
    status_code=status.HTTP_200_OK
)
@cache(expire=600)
async def get_all_hotel_only_supplier(
    request: ProviderProperty,
    current_user: Annotated[models.User, Depends(get_current_user)],
    db: Session = Depends(get_db),
    limit_per_page: int = Query(50, ge=1, le=500),
    resume_key: Optional[str] = Query(None),
):
    # print("Hello")
    # --- Authorization & points deduction ---
    if current_user.role == models.UserRole.GENERAL_USER:
        deduct_points_for_general_user(current_user, db)
        allowed = [
            p.provider_name
            for p in db.query(models.UserProviderPermission)
                      .filter_by(user_id=current_user.id)
        ]
        if request.provider_name not in allowed:
            raise HTTPException(status_code=403, detail="No permission for this supplier")

    # --- Decode and validate resume_key ---
    last_id = 0
    if resume_key:
        try:
            # Extract the ID from resume_key format: "id_randomstring"
            parts = resume_key.split("_", 1)
            if len(parts) != 2:
                raise ValueError("Invalid format")
            
            last_id = int(parts[0])
            random_part = parts[1]
            
            # Validate that the random part has expected length and characters
            if len(random_part) != 50:
                raise ValueError("Invalid random part length")
            
            # Check if the ID actually exists in the database for this provider
            id_exists = db.query(models.ProviderMapping).filter(
                models.ProviderMapping.id == last_id,
                models.ProviderMapping.provider_name == request.provider_name
            ).first()
            
            if not id_exists:
                raise ValueError("Resume key references non-existent record")
                
        except ValueError as e:
            raise HTTPException(
                status_code=400, 
                detail=f"Invalid resume_key: {str(e)}. Please use a valid resume_key from a previous response or omit it to start from the beginning."
            )

    # --- Single eager‐loaded query ---
    query = (
        db.query(models.ProviderMapping)
          .options(
              # load mapping → hotel → locations & contacts
              joinedload(models.ProviderMapping.hotel)
                .joinedload(models.Hotel.locations),
              joinedload(models.ProviderMapping.hotel)
                .joinedload(models.Hotel.contacts),
          )
          .filter(models.ProviderMapping.provider_name == request.provider_name)
          .order_by(models.ProviderMapping.id)
    )
    if last_id:
        query = query.filter(models.ProviderMapping.id > last_id)

    mappings = query.limit(limit_per_page).all()

    # --- Total count for pagination info ---
    total = (
        db.query(models.ProviderMapping)
          .filter(models.ProviderMapping.provider_name == request.provider_name)
          .count()
    )

    # --- Build grouped result by ittid ---
    hotels_by_ittid = {}
    for m in mappings:
        hotels_by_ittid.setdefault(m.ittid, []).append(m)

    result = []
    for ittid, group in hotels_by_ittid.items():
        hotel = group[0].hotel  # already loaded
        if not hotel:
            continue

        providers = [
            {"id": m.id, "name": m.provider_name, "provider_id": m.provider_id, "status": "update"}
            for m in group
        ]

        # locations and contacts are eager-loaded on hotel
        location_list = [
            {
                "id": loc.id,
                "name": loc.city_name,
                "location_id": loc.city_location_id,
                "status": "update",
                "latitude": hotel.latitude,
                "longitude": hotel.longitude,
                "address": f"{hotel.address_line1 or ''} {hotel.address_line2 or ''}".strip(),
                "postal_code": hotel.postal_code,
                "city_id": loc.id,
                "city_name": loc.city_name,
                "city_code": loc.city_code,
                "state": loc.state_name,
                "country_name": loc.country_name,
                "country_code": loc.country_code,
            }
            for loc in hotel.locations
        ]

        contact = {"id": hotel.id, "phone": [], "email": [], "website": [], "fax": []}
        for c in hotel.contacts:
            if c.contact_type == "phone":
                contact["phone"].append(c.value)
            elif c.contact_type == "email":
                contact["email"].append(c.value)
            elif c.contact_type == "website":
                contact["website"].append(c.value)
            elif c.contact_type == "fax":
                contact["fax"].append(c.value)

        result.append({
            "ittid": hotel.ittid,
            "name": hotel.name,
            "country_name": location_list[0]["country_name"] if location_list else "",
            "country_code": location_list[0]["country_code"] if location_list else "",
            "type": "hotel",
            "provider": providers,
            "location": location_list,
            "contract": [contact],
        })

    # --- Next resume_key generation ---
    if len(mappings) == limit_per_page:
        last_map_id = mappings[-1].id
        rand = ''.join(secrets.choice(string.ascii_letters + string.digits) for _ in range(50))
        next_resume = f"{last_map_id}_{rand}"
    else:
        next_resume = None

    return {
        "resume_key": next_resume,
        "total_hotel": total,
        "show_hotels_this_page": len(result),
        "hotel": result,
    }


@router.get("/get_update_provider_info")
def get_update_provider_info(
    current_user: Annotated[models.User, Depends(get_current_user)],
    limit_per_page: int = Query(50, ge=1, le=500, description="Number of records per page"),
    from_date: str = Query(..., description="Start date (YYYY-MM-DD)"),
    to_date: str = Query(..., description="End date (YYYY-MM-DD)"),
    resume_key: Optional[str] = Query(None, description="Resume key for pagination"),
    db: Session = Depends(get_db)
):
    try:
        from_dt = datetime.strptime(from_date, "%Y-%m-%d")
        to_dt = datetime.strptime(to_date, "%Y-%m-%d")
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid date format. Use YYYY-MM-DD.")

    # Super users see all, others see only their allowed providers
    if current_user.role == UserRole.SUPER_USER:
        allowed_providers = None
    else:
        allowed_providers = [
            perm.provider_name
            for perm in db.query(UserProviderPermission)
                          .filter(UserProviderPermission.user_id == current_user.id)
                          .all()
        ]
        if not allowed_providers:
            return {"message": "Please contact your admin."}

    # Base query for filtering
    base_query = db.query(ProviderMapping).filter(
        ProviderMapping.updated_at >= from_dt,
        ProviderMapping.updated_at <= to_dt
    )

    if allowed_providers is not None:
        base_query = base_query.filter(ProviderMapping.provider_name.in_(allowed_providers))

    # Count total BEFORE applying resume_key/pagination
    total = base_query.count()

    # Apply ordering and resume_key filter
    last_id = 0
    if resume_key:
        try:
            last_id = int(resume_key.split("_")[0])
        except Exception:
            raise HTTPException(status_code=400, detail="Invalid resume_key.")
        base_query = base_query.filter(ProviderMapping.id > last_id)

    base_query = base_query.order_by(ProviderMapping.id)

    # Apply pagination
    mappings = base_query.limit(limit_per_page).all()

    # Prepare next resume_key (random string + last id)
    if mappings and len(mappings) == limit_per_page:
        last_hotel_id = mappings[-1].id
        rand_str = ''.join(secrets.choice(string.ascii_letters + string.digits) for _ in range(50))
        next_resume_key = f"{last_hotel_id}_{rand_str}"
    else:
        next_resume_key = None

    result = [
        {
            "ittid": m.ittid,
            "provider_name": m.provider_name,
            "provider_id": m.provider_id,
            "system_type": m.system_type,
        }
        for m in mappings
    ]

    return {
        "resume_key": next_resume_key,
        "total_hotel": total, 
        "show_hotels_this_page": len(result),
        "provider_mappings": result
    }


class HotelNameRequest(BaseModel):
    hotel_name: str

@router.post("/search_with_hotel_name", status_code=status.HTTP_200_OK)
def search_hotel_with_name(
    request: HotelNameRequest = Body(...),
):
    csv_path = "static/hotelcontent/itt_hotel_basic_info.csv"
    try:
        with open(csv_path, newline='', encoding='utf-8') as csvfile:
            reader = csv.DictReader(csvfile)
            for row in reader:
                if row["Name"].strip().lower() == request.hotel_name.strip().lower():
                    return {
                        "ittid": row.get("ittid"),
                        "name": row.get("Name"),
                        "addressline1": row.get("AddressLine1"),
                        "addressline2": row.get("AddressLine2"),
                        "city": row.get("CityName"),
                        "country": row.get("CountryName"),
                        "latitude": row.get("Latitude"),
                        "longitude": row.get("Longitude"),
                        "postalcode": row.get("PostalCode"),
                        "chainname": row.get("ChainName"),
                        "propertytype": row.get("PropertyType")
                    }

    except FileNotFoundError:
        raise HTTPException(status_code=404, detail="CSV file not found.")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error reading CSV file: {str(e)}")

    raise HTTPException(status_code=404, detail="Hotel not found.")


@router.get("/autocomplete", status_code=status.HTTP_200_OK)
def autocomplete_hotel_name(query: str = Query(..., description="Partial hotel name")):
    csv_path = "static/hotelcontent/itt_hotel_basic_info.csv"
    suggestions = []
    try:
        with open(csv_path, newline="", encoding="utf-8") as csvfile:
            reader = csv.DictReader(csvfile)
            for row in reader:
                hotel_name = row["Name"].strip()
                if hotel_name.lower().startswith(query.lower()):
                    suggestions.append(hotel_name)
                # Optional: limit results for speed
                if len(suggestions) >= 20:
                    break
        if not suggestions:
            return {"results": []}
        return {"results": suggestions}

    except FileNotFoundError:
        raise HTTPException(status_code=404, detail="CSV file not found.")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error reading CSV file: {str(e)}")
