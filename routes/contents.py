from fastapi import APIRouter, Depends, HTTPException, status, Query, Body, Request
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
import asyncio
import os
from routes.hotelFormattingData import map_to_our_format
from routes.path import RAW_BASE_DIR

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


async def get_hotel_details_internal(supplier_code: str, hotel_id: str, current_user, db: Session) -> Optional[Dict]:
    """
    Internal Hotel Details Retrieval Function
    
    This function replicates the logic from the /v1.0/hotel/details endpoint
    but is called internally to avoid HTTP request overhead. It provides the same
    security checks and data processing as the public endpoint.
    
    Security Features:
    - Role-based access control (same as public endpoint)
    - Supplier permission validation for general users
    - Graceful error handling without exposing internal errors
    
    Performance Benefits:
    - No HTTP overhead (direct function call)
    - Efficient file system access
    - Optimized for bulk operations
    
    Args:
        supplier_code (str): The supplier/provider code (e.g., 'hotelbeds', 'booking')
        hotel_id (str): The hotel ID from the provider system
        current_user: Current authenticated user object with role information
        db (Session): Database session for permission checks
    
    Returns:
        Optional[Dict]: Formatted hotel details dictionary or None if:
            - User lacks permission for the supplier
            - Hotel data file not found
            - JSON parsing errors occur
            - Any other processing errors
    
    Example Return Value:
        {
            "hotel_name": "Example Hotel",
            "address": "123 Main St",
            "city": "Example City",
            "country": "Example Country",
            "rating": 4.5,
            "amenities": ["WiFi", "Pool", "Gym"],
            "description": "A beautiful hotel...",
            "images": ["image1.jpg", "image2.jpg"],
            "contact": {
                "phone": "+1234567890",
                "email": "info@examplehotel.com"
            }
        }
    
    Error Handling:
        - Returns None for any errors (permission, file not found, parsing)
        - Logs errors for debugging but doesn't raise exceptions
        - Maintains system stability during bulk operations
    """
    try:
        # Check supplier permissions (same logic as hotel details endpoint)
        if current_user.role not in [models.UserRole.SUPER_USER, models.UserRole.ADMIN_USER]:
            # Check if general user has permission for this supplier
            user_supplier_permission = db.query(models.UserProviderPermission).filter(
                models.UserProviderPermission.user_id == current_user.id,
                models.UserProviderPermission.provider_name == supplier_code
            ).first()
            
            if not user_supplier_permission:
                # User doesn't have permission for this supplier
                return None
        
        # Get the raw data file path (same logic as hotel details endpoint)
        file_path = os.path.join(RAW_BASE_DIR, supplier_code, f"{hotel_id}.json")
        
        # Load and process the hotel data
        if os.path.exists(file_path):
            with open(file_path, "r", encoding="utf-8") as f:
                content = json.load(f)
            
            # Format the data using the same function as the hotel details endpoint
            formatted_data = map_to_our_format(supplier_code, content)
            return formatted_data
        else:
            # File not found
            return None
            
    except Exception as e:
        # Log the error but don't raise it - just return None
        print(f"Error getting hotel details for {supplier_code}/{hotel_id}: {str(e)}")
        return None
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
    """
    Get Hotel Data by Provider Name and ID
    
    Retrieves comprehensive hotel information including provider mappings, locations, 
    and contacts based on provider name and ID combinations.
    
    Features:
    - Role-based access control with provider permission validation
    - Point deduction for general users
    - Comprehensive hotel data with locations and contacts
    - Batch processing for multiple provider identities
    
    Args:
        request (ProviderHotelRequest): Request containing list of provider identities
        current_user: Currently authenticated user (injected by dependency)
        db (Session): Database session (injected by dependency)
    
    Returns:
        List[dict]: List of hotel data with provider mappings, locations, and contacts
    
    Access Control:
        - GENERAL_USER: Only sees providers they have permission for, points deducted
        - SUPER_USER/ADMIN_USER: Can see all provider mappings
    
    Error Handling:
        - 403: User has no provider permissions
        - 404: No mappings found for requested provider identities
        - 500: Database or internal server errors
    
    Example Request:
        {
            "provider_hotel_identity": [
                {"provider_id": "12345", "provider_name": "booking"},
                {"provider_id": "67890", "provider_name": "expedia"}
            ]
        }
    """
    try:
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
                    detail="You do not have any permission for this request. Please contact your administrator."
                )
        else:
            # if you really want _everyone else_ blocked until you grant, 
            # you could also force them into the same error here.
            allowed_providers = None
            print("Allowed providers for user:", allowed_providers)
            print("Requested identities:", [vars(i) for i in request.provider_hotel_identity])
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error processing user permissions: {str(e)}"
        )
  

    # now you know GENERAL_USER has at least one allowed_provider
    # (or everyone else is None → full access)

    try:
        result = []
        for identity in request.provider_hotel_identity:
            name = identity.provider_name
            pid = identity.provider_id
            
            # Validate provider access
            if allowed_providers and name not in allowed_providers:
                print(f"User not allowed for provider: {name}")
                continue

            # Find provider mapping
            mapping = (
                db.query(ProviderMapping)
                .filter_by(provider_id=pid, provider_name=name)
                .first()
            )
            if not mapping:
                print(f"No mapping found for provider_id={pid}, provider_name={name}")
                continue

            # Find hotel
            hotel = db.query(Hotel).filter(Hotel.ittid == mapping.ittid).first()
            if not hotel:
                print(f"No hotel found for ittid={mapping.ittid}")
                continue

            # Get related data
            locations = db.query(Location).filter(Location.ittid == hotel.ittid).all()
            contacts = db.query(Contact).filter(Contact.ittid == hotel.ittid).all()

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
                detail="Cannot find mapping for any of the requested suppliers in our system."
            )

        return result
    
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error processing hotel data request: {str(e)}"
        )


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
    """
    Get Hotel Mapping Data by Provider Name and ID
    
    Retrieves provider mapping information for hotels based on provider name and ID combinations.
    This endpoint returns simplified mapping data without full hotel details.
    
    Features:
    - Role-based access control with provider permission validation
    - Point deduction for general users
    - Simplified provider mapping data
    - Batch processing for multiple provider identities
    
    Args:
        request (ProviderHotelRequest): Request containing list of provider identities
        current_user: Currently authenticated user (injected by dependency)
        db (Session): Database session (injected by dependency)
    
    Returns:
        List[dict]: List of provider mapping data with ITTID and creation timestamps
    
    Access Control:
        - GENERAL_USER: Only sees providers they have permission for, points deducted
        - SUPER_USER/ADMIN_USER: Can see all provider mappings
    
    Error Handling:
        - 403: User has no provider permissions
        - 404: No mappings found for requested provider identities
        - 500: Database or internal server errors
    
    Example Response:
        [
            {
                "provider_mappings": [
                    {
                        "ittid": "ITT123456",
                        "provider_mapping_id": 789,
                        "provider_id": "12345",
                        "provider_name": "booking",
                        "system_type": "OTA",
                        "created_at": "2023-01-01T00:00:00"
                    }
                ]
            }
        ]
    """
    try:
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
                    detail="You do not have any permission for this request. Please contact your administrator."
                )
        else:
            # if you really want _everyone else_ blocked until you grant, 
            # you could also force them into the same error here.
            allowed_providers = None
            print("Allowed providers for user:", allowed_providers)
            print("Requested identities:", [vars(i) for i in request.provider_hotel_identity])
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error processing user permissions: {str(e)}"
        )

    try:
        # now you know GENERAL_USER has at least one allowed_provider
        # (or everyone else is None → full access)

        result = []
        for identity in request.provider_hotel_identity:
            name = identity.provider_name
            pid = identity.provider_id
            
            # Check provider access
            if allowed_providers and name not in allowed_providers:
                print(f"User not allowed for provider: {name}")
                continue

            # Find provider mapping
            mapping = (
                db.query(ProviderMapping)
                .filter_by(provider_id=pid, provider_name=name)
                .first()
            )
            if not mapping:
                print(f"No mapping found for provider_id={pid}, provider_name={name}")
                continue

            # Verify hotel exists
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
                detail="Cannot find mapping for any of the requested suppliers in our system."
            )

        return result
    
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error processing mapping data request: {str(e)}"
        )


class ITTIDRequest(BaseModel):
    ittid: List[str]

# Get provider mapping
@router.post("/get_hotel_with_ittid", status_code=status.HTTP_200_OK)
async def get_hotels_using_ittid_list(
    request: ITTIDRequest,
    current_user: Annotated[models.User, Depends(get_current_user)],
    db: Session = Depends(get_db)
):
    """
    Get Provider Mappings with Full Hotel Details by ITTID List
    
    This endpoint retrieves provider mappings for the given ITTID list and includes
    full hotel details from each provider. The hotel details are fetched from the
    internal hotel details service for each provider mapping.
    
    Features:
    - Role-based access control for provider data
    - Full hotel details integration from /v1.0/hotel/details
    - Efficient internal API calls without HTTP overhead
    - Comprehensive error handling for missing data
    
    Args:
        request (ITTIDRequest): Request containing list of ITTID values
        current_user: Currently authenticated user (injected by dependency)
        db (Session): Database session (injected by dependency)
    
    Returns:
        List[dict]: List of hotels with provider mappings and full details
    
    Access Control:
        - GENERAL_USER: Only sees providers they have permission for
        - SUPER_USER/ADMIN_USER: Can see all provider mappings
    """

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

            formatted_provider_mappings = []
            for mapping in provider_mappings:
                # Get full hotel details for this provider mapping
                hotel_details = await get_hotel_details_internal(
                    supplier_code=mapping.provider_name,
                    hotel_id=mapping.provider_id,
                    current_user=current_user,
                    db=db
                )
                
                mapping_data = {
                    "id": mapping.id,
                    "ittid": mapping.ittid,
                    "provider_name": mapping.provider_name,
                    "provider_id": mapping.provider_id,
                    "full_details": hotel_details  # Include full hotel details
                }
                formatted_provider_mappings.append(mapping_data)

            result.append({
                "ittid": hotel.ittid,
                "provider_mappings": formatted_provider_mappings
            })
    else:
        # For SUPER/ADMIN users – return all mappings with full details
        for hotel in hotels:
            provider_mappings = db.query(models.ProviderMapping).filter(
                models.ProviderMapping.ittid == hotel.ittid
            ).all()

            formatted_provider_mappings = []
            for mapping in provider_mappings:
                # Get full hotel details for this provider mapping
                hotel_details = await get_hotel_details_internal(
                    supplier_code=mapping.provider_name,
                    hotel_id=mapping.provider_id,
                    current_user=current_user,
                    db=db
                )
                
                mapping_data = {
                    "id": mapping.id,
                    "ittid": mapping.ittid,
                    "provider_name": mapping.provider_name,
                    "provider_id": mapping.provider_id,
                    "full_details": hotel_details  # Include full hotel details
                }
                formatted_provider_mappings.append(mapping_data)

            result.append({
                "ittid": hotel.ittid,
                "provider_mappings": formatted_provider_mappings
            })

    return result

@router.get("/get_hotel_with_ittid/{ittid}", status_code=status.HTTP_200_OK)
async def get_hotel_using_ittid(
    ittid: str,
    current_user: Annotated[models.User, Depends(get_current_user)],
    db: Session = Depends(get_db)
):
    """
    Get Hotel Details by ITTID with Full Provider Details
    
    Retrieves comprehensive hotel information including provider mappings with full details
    from the hotel details service. Points are deducted only for successful requests.
    
    Features:
    - Full hotel details integration for each provider mapping
    - Role-based access control for provider data
    - Active supplier validation and permission checks
    - Comprehensive response with locations, chains, and contacts
    - Point deduction only on successful data retrieval
    
    Args:
        ittid (str): The ITT hotel identifier
        current_user: Currently authenticated user (injected by dependency)
        db (Session): Database session (injected by dependency)
    
    Returns:
        dict: Comprehensive hotel data including:
            - hotel: Basic hotel information
            - provider_mappings: Provider mappings with full_details for each
            - locations: Hotel location information
            - chains: Hotel chain information
            - contacts: Hotel contact information
            - supplier_info: Summary of supplier access information
    
    Access Control:
        - GENERAL_USER: Only sees providers they have permission for
        - SUPER_USER/ADMIN_USER: Can see all provider mappings
    
    HTTP Status Codes:
        200: Hotel data retrieved successfully
        403: Forbidden - No access to suppliers for this hotel
        404: Hotel not found or no supplier mappings available
    """
    
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
    # chains = db.query(models.Chain).filter(models.Chain.ittid == hotel.ittid).all()
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

    # Enhanced provider mappings with full details
    enhanced_provider_mappings = []
    for pm in provider_mappings:
        # Get full hotel details for this provider mapping
        hotel_details = await get_hotel_details_internal(
            supplier_code=pm.provider_name,
            hotel_id=pm.provider_id,
            current_user=current_user,
            db=db
        )
        
        # Create simplified provider mapping with only essential fields
        pm_data = {
            "id": pm.id,
            "ittid": pm.ittid,
            "provider_name": pm.provider_name,
            "provider_id": pm.provider_id,
            "full_details": hotel_details
        }
        enhanced_provider_mappings.append(pm_data)

    # Serialize the response with enhanced provider mappings
    response_data = {
        "hotel": serialize_datetime_objects(hotel),
        "provider_mappings": enhanced_provider_mappings,
        "locations": [serialize_datetime_objects(loc) for loc in locations],
        # "chains": [serialize_datetime_objects(chain) for chain in chains],
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
    Get Paginated List of All Hotels
    
    Retrieves a paginated list of hotels with smart resume_key validation and role-based access control.
    This endpoint provides comprehensive pagination support with secure resume keys.
    
    Features:
    - Smart pagination with resume key validation
    - Role-based access control for provider permissions
    - Point deduction only for general users
    - Comprehensive hotel information with geocoding
    - Secure resume key generation with 50-character random strings
    
    Pagination Logic:
    - FIRST request: No resume_key needed (automatically detected)
    - SUBSEQUENT requests: Must provide valid resume_key from previous response
    
    Args:
        current_user: Currently authenticated user (injected by dependency)
        page (int): Page number, starting from 1 (for reference only)
        limit (int): Number of hotels per page (1-1000, default 50)
        resume_key (Optional[str]): Resume key for pagination continuation
        first_request (bool): Legacy parameter for first request indication
        db (Session): Database session (injected by dependency)
    
    Returns:
        dict: Paginated hotel data with metadata including:
            - resume_key: Key for next page (null if last page)
            - total_hotel: Total count in database
            - accessible_hotel_count: Hotels accessible to user
            - hotels: List of hotel objects with geocoding
            - pagination_info: Detailed pagination metadata
            - usage_instructions: How to use the pagination system
    
    Access Control:
        - GENERAL_USER: Only sees hotels from permitted providers, points deducted
        - SUPER_USER/ADMIN_USER: Can see all hotels, no point deduction
    
    Error Handling:
        - 400: Invalid resume_key format or references
        - 403: User has no provider permissions
        - 500: Database or internal server errors
    
    Resume Key Format:
        {hotel_id}_{50_character_random_string}
        
    Example: "12345_aBcDeFgHiJkLmNoPqRsTuVwXyZ1234567890AbCdEfGhIjKlMn"
    """

    try:
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
                    detail="You do not have any permission for this request. Please contact your administrator."
                )
        elif current_user.role in [UserRole.SUPER_USER, UserRole.ADMIN_USER]:
            print(f"🔓 Point deduction skipped for {current_user.role}: {current_user.email}")
            allowed_providers = None
        else:
            allowed_providers = None
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error processing user permissions: {str(e)}"
        )

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

    try:
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
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error querying hotel data: {str(e)}"
        )

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
    """
    Get All Hotels for Specific Supplier with Caching
    
    Retrieves paginated hotel data for a specific supplier/provider with comprehensive
    hotel information including locations, contacts, and provider mappings. Results are
    cached for 10 minutes to improve performance.
    
    Features:
    - Supplier-specific hotel filtering
    - Role-based access control with provider permissions
    - Point deduction for general users
    - Comprehensive hotel data with locations and contacts
    - Resume key pagination for large datasets
    - 10-minute response caching for performance
    - Eager loading to minimize database queries
    
    Args:
        request (ProviderProperty): Request containing provider name
        current_user: Currently authenticated user (injected by dependency)
        db (Session): Database session (injected by dependency)
        limit_per_page (int): Number of hotels per page (1-500, default 50)
        resume_key (Optional[str]): Resume key for pagination continuation
    
    Returns:
        GetAllHotelResponse: Paginated hotel data including:
            - resume_key: Key for next page (null if last page)
            - total_hotel: Total hotels for this supplier
            - show_hotels_this_page: Number of hotels in current response
            - hotel: List of hotel objects with provider, location, and contact data
    
    Access Control:
        - GENERAL_USER: Must have permission for requested supplier, points deducted
        - SUPER_USER/ADMIN_USER: Can access any supplier
    
    Error Handling:
        - 400: Invalid resume_key format or references
        - 403: User lacks permission for requested supplier
        - 500: Database or internal server errors
    
    Caching:
        - Response cached for 600 seconds (10 minutes)
        - Cache key includes user permissions and request parameters
        
    Example Request:
        GET /get_all_hotel_only_supplier/?provider_name=booking&limit_per_page=100
    """
    try:
        # --- Authorization & points deduction ---
        if current_user.role == models.UserRole.GENERAL_USER:
            deduct_points_for_general_user(current_user, db)
            allowed = [
                p.provider_name
                for p in db.query(models.UserProviderPermission)
                          .filter_by(user_id=current_user.id)
            ]
            if request.provider_name not in allowed:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN, 
                    detail=f"No permission for supplier '{request.provider_name}'. Please contact your administrator."
                )
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error processing user permissions: {str(e)}"
        )

    try:
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
                    status_code=status.HTTP_400_BAD_REQUEST, 
                    detail=f"Invalid resume_key: {str(e)}. Please use a valid resume_key from a previous response or omit it to start from the beginning."
                )
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error processing resume key: {str(e)}"
        )

    try:
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
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error querying supplier hotel data: {str(e)}"
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
    """
    Get Updated Provider Information by Date Range
    
    Retrieves provider mapping information that was updated within a specified date range.
    This endpoint is useful for tracking changes and updates to hotel-provider mappings.
    
    Features:
    - Date range filtering for updated records
    - Role-based access control (Super users see all, others see permitted providers)
    - Resume key pagination for large datasets
    - Comprehensive provider mapping information
    
    Args:
        current_user: Currently authenticated user (injected by dependency)
        limit_per_page (int): Number of records per page (1-500, default 50)
        from_date (str): Start date in YYYY-MM-DD format (required)
        to_date (str): End date in YYYY-MM-DD format (required)
        resume_key (Optional[str]): Resume key for pagination continuation
        db (Session): Database session (injected by dependency)
    
    Returns:
        dict: Paginated provider mapping data including:
            - resume_key: Key for next page (null if last page)
            - total_hotel: Total mappings in date range
            - show_hotels_this_page: Number of mappings in current response
            - provider_mappings: List of provider mapping objects
    
    Access Control:
        - SUPER_USER: Can see all provider mappings
        - Other roles: Only see mappings for permitted providers
    
    Error Handling:
        - 400: Invalid date format or resume_key
        - 403: User has no provider permissions (non-super users)
        - 500: Database or internal server errors
    
    Date Format:
        - Both from_date and to_date must be in YYYY-MM-DD format
        - Example: "2023-01-01" to "2023-12-31"
        
    Example Request:
        GET /get_update_provider_info?from_date=2023-01-01&to_date=2023-12-31&limit_per_page=100
    """
    try:
        # Validate and parse dates
        try:
            from_dt = datetime.strptime(from_date, "%Y-%m-%d")
            to_dt = datetime.strptime(to_date, "%Y-%m-%d")
            
            # Validate date range
            if from_dt > to_dt:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="from_date cannot be later than to_date"
                )
        except ValueError:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST, 
                detail="Invalid date format. Use YYYY-MM-DD format (e.g., '2023-01-01')."
            )

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
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="You do not have permission to access any providers. Please contact your administrator."
                )
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error processing date range or permissions: {str(e)}"
        )

    try:
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
                parts = resume_key.split("_", 1)
                if len(parts) != 2:
                    raise ValueError("Invalid resume key format")
                last_id = int(parts[0])
                
                # Validate the mapping exists
                mapping_exists = db.query(ProviderMapping).filter(
                    ProviderMapping.id == last_id
                ).first()
                if not mapping_exists:
                    raise ValueError("Resume key references non-existent record")
                    
            except ValueError as e:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST, 
                    detail=f"Invalid resume_key: {str(e)}. Please use a valid resume_key from a previous response."
                )
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
    
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error processing provider update information: {str(e)}"
        )


class HotelNameRequest(BaseModel):
    hotel_name: str

@router.post("/search_with_hotel_name", status_code=status.HTTP_200_OK)
def search_hotel_with_name(
    request: HotelNameRequest = Body(...),
):
    """
    Search Hotel by Exact Name Match
    
    Searches for a hotel by exact name match in the CSV database. This endpoint performs
    case-insensitive exact matching against hotel names in the static CSV file.
    
    Features:
    - Case-insensitive exact name matching
    - Comprehensive hotel information from CSV database
    - Fast CSV-based lookup without database queries
    - Detailed hotel information including location and chain data
    
    Args:
        request (HotelNameRequest): Request containing the exact hotel name to search
    
    Returns:
        dict: Complete hotel information including:
            - ittid: ITT hotel identifier
            - name: Hotel name
            - addressline1/addressline2: Hotel address components
            - city: City name
            - country: Country name
            - latitude/longitude: Geographic coordinates
            - postalcode: Postal/ZIP code
            - chainname: Hotel chain name
            - propertytype: Type of property (hotel, resort, etc.)
    
    Error Handling:
        - 404: Hotel not found or CSV file missing
        - 500: File reading or processing errors
    
    Data Source:
        - Static CSV file: static/hotelcontent/itt_hotel_basic_info.csv
        - Contains comprehensive hotel database information
        
    Example Request:
        {
            "hotel_name": "Grand Hotel Example"
        }
        
    Example Response:
        {
            "ittid": "ITT123456",
            "name": "Grand Hotel Example",
            "addressline1": "123 Main Street",
            "city": "Example City",
            "country": "Example Country",
            "latitude": "40.7128",
            "longitude": "-74.0060",
            "chainname": "Example Chain",
            "propertytype": "Hotel"
        }
    """
    csv_path = "static/hotelcontent/itt_hotel_basic_info.csv"
    
    try:
        # Validate input
        if not request.hotel_name or not request.hotel_name.strip():
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Hotel name cannot be empty"
            )
        
        search_name = request.hotel_name.strip().lower()
        
        try:
            with open(csv_path, newline='', encoding='utf-8') as csvfile:
                reader = csv.DictReader(csvfile)
                
                for row in reader:
                    if not row.get("Name"):
                        continue
                        
                    if row["Name"].strip().lower() == search_name:
                        return {
                            "ittid": row.get("ittid", ""),
                            "name": row.get("Name", ""),
                            "addressline1": row.get("AddressLine1", ""),
                            "addressline2": row.get("AddressLine2", ""),
                            "city": row.get("CityName", ""),
                            "country": row.get("CountryName", ""),
                            "latitude": row.get("Latitude", ""),
                            "longitude": row.get("Longitude", ""),
                            "postalcode": row.get("PostalCode", ""),
                            "chainname": row.get("ChainName", ""),
                            "propertytype": row.get("PropertyType", "")
                        }
        
        except FileNotFoundError:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, 
                detail="Hotel database file not found. Please contact administrator."
            )
        except UnicodeDecodeError:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Error reading hotel database file: encoding issue"
            )
        except csv.Error as e:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Error parsing hotel database file: {str(e)}"
            )

        # Hotel not found after searching entire file
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, 
            detail=f"Hotel with name '{request.hotel_name}' not found in database"
        )
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Unexpected error during hotel search: {str(e)}"
        )


@router.get("/autocomplete", status_code=status.HTTP_200_OK)
def autocomplete_hotel_name(query: str = Query(..., description="Partial hotel name")):
    """
    Hotel Name Autocomplete Search
    
    Provides autocomplete suggestions for hotel names based on partial input. This endpoint
    searches the CSV database for hotel names that start with the provided query string.
    
    Features:
    - Case-insensitive prefix matching
    - Fast CSV-based lookup without database queries
    - Limited results (max 20) for performance
    - Real-time autocomplete support
    
    Args:
        query (str): Partial hotel name to search for (required)
    
    Returns:
        dict: Autocomplete results containing:
            - results: List of matching hotel names (max 20 results)
    
    Search Logic:
        - Matches hotel names that START WITH the query string
        - Case-insensitive matching
        - Returns up to 20 suggestions for performance
        - Empty results if no matches found
    
    Error Handling:
        - 400: Empty or invalid query parameter
        - 404: CSV file not found
        - 500: File reading or processing errors
    
    Data Source:
        - Static CSV file: static/hotelcontent/itt_hotel_basic_info.csv
        - Searches the "Name" column for matches
        
    Example Request:
        GET /autocomplete?query=Grand
        
    Example Response:
        {
            "results": [
                "Grand Hotel Central",
                "Grand Palace Hotel",
                "Grand Resort & Spa"
            ]
        }
    """
    try:
        # Validate input
        if not query or not query.strip():
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Query parameter cannot be empty"
            )
        
        # Minimum query length for performance
        if len(query.strip()) < 2:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Query must be at least 2 characters long"
            )
        
        csv_path = "static/hotelcontent/itt_hotel_basic_info.csv"
        suggestions = []
        search_query = query.strip().lower()
        
        try:
            with open(csv_path, newline="", encoding="utf-8") as csvfile:
                reader = csv.DictReader(csvfile)
                
                for row in reader:
                    if not row.get("Name"):
                        continue
                        
                    hotel_name = row["Name"].strip()
                    if hotel_name and hotel_name.lower().startswith(search_query):
                        suggestions.append(hotel_name)
                    
                    # Limit results for performance
                    if len(suggestions) >= 20:
                        break
                        
        except FileNotFoundError:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, 
                detail="Hotel database file not found. Please contact administrator."
            )
        except UnicodeDecodeError:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Error reading hotel database file: encoding issue"
            )
        except csv.Error as e:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Error parsing hotel database file: {str(e)}"
            )
        
        return {"results": suggestions}
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Unexpected error during autocomplete search: {str(e)}"
        )
