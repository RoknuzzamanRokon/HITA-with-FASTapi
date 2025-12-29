from fastapi import APIRouter, Depends, HTTPException, status, Query, Body, Request
from sqlalchemy.orm import Session, joinedload
from sqlalchemy import func
from database import get_db
from models import (
    Hotel,
    ProviderMapping,
    Location,
    Contact,
    UserProviderPermission,
    UserRole,
    UserIPWhitelist,
)
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
import os
from routes.auth import get_current_user
from middleware.ip_middleware import get_client_ip
from rapidfuzz import fuzz, process

from schemas import ProviderProperty, GetAllHotelResponse

# Import activity logging decorator
from utils.activity_logging import log_content_activity
from security.audit_logging import SecurityLevel


router = APIRouter(
    prefix="/v1.0/content",
    tags=["Hotel Content"],
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
        whitelist_entry = (
            db.query(UserIPWhitelist)
            .filter(
                UserIPWhitelist.user_id == user_id,
                UserIPWhitelist.ip_address == client_ip,
                UserIPWhitelist.is_active == True,
            )
            .first()
        )

        return whitelist_entry is not None

    except Exception as e:
        print(f"Error checking IP whitelist: {str(e)}")
        return False


def serialize_datetime_objects(obj):
    """Convert datetime objects to ISO format strings for JSON serialization."""
    if hasattr(obj, "__dict__"):
        result = {}
        try:
            # Sort items by key (as string) to avoid comparison issues
            items = sorted(obj.__dict__.items(), key=lambda x: str(x[0]))
        except Exception:
            # Fallback to unsorted if sorting fails
            items = list(obj.__dict__.items())

        for key, value in items:
            if key.startswith("_"):
                continue
            if isinstance(value, datetime):
                result[key] = value.isoformat() if value else None
            else:
                result[key] = value
        return result
    return obj


async def get_hotel_details_internal(
    supplier_code: str, hotel_id: str, current_user, db: Session
) -> Optional[Dict]:
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


class ProviderHotelIdentity(BaseModel):
    provider_id: str
    provider_name: str


class ProviderHotelRequest(BaseModel):
    provider_hotel_identity: List[ProviderHotelIdentity]


class CountryInfoRequest(BaseModel):
    supplier: str
    country_iso: str


class ProviderProperty(BaseModel):
    provider_name: str


class ProviderPropertyRequest(BaseModel):
    provider_property: List[ProviderProperty]


class ITTIDRequest(BaseModel):
    ittid: List[str]


@router.post("/get-basic-info-follow-countryCode", status_code=status.HTTP_200_OK)
def get_basic_country_info(
    http_request: Request,
    request: CountryInfoRequest,
    current_user: Annotated[models.User, Depends(get_current_user)],
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """
    Get Country Hotel Data by Supplier

    Retrieves hotel data for a specific country and supplier combination.
    Fast file-based lookup with role-based access control.

    Request Body:
        - supplier: Supplier/provider name (e.g., "booking", "expedia")
        - country_iso: ISO country code (e.g., "US", "GB", "FR")

    Features:
        - ✅ IP whitelist validation
        - ✅ Role-based supplier access control
        - ✅ Temporary supplier deactivation support
        - ✅ Fast file-based data retrieval
        - ✅ JSON validation and error handling

    Access Control:
        - GENERAL_USER: Only permitted suppliers
        - SUPER_USER/ADMIN_USER: All suppliers (except temp deactivated)

    Returns:
        dict: {
            "success": True,
            "supplier": "booking",
            "country_iso": "US",
            "total_hotel": 12345,
            "data": [hotel_data_array]
        }

    Errors:
        - 403: IP not whitelisted / No supplier permission / Supplier deactivated
        - 404: Country data file not found
        - 500: File read error / Invalid JSON format
    """

    # 🔒 IP WHITELIST VALIDATION
    print(
        f"🚀 About to call IP whitelist check for user: {current_user.id} in get-basic-info-follow-countryCode"
    )
    if not check_ip_whitelist(current_user.id, http_request, db):
        # Extract client IP for error message using middleware
        client_ip = get_client_ip(http_request) or "unknown"

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
                    "message": "Your IP address is not in the whitelist. Please contact your administrator to add your IP address to the whitelist.",
                },
                "timestamp": datetime.utcnow().isoformat(),
            },
        )

    try:
        # FAST PERMISSION CHECK - Check user permissions for the requested supplier
        if current_user.role not in [UserRole.SUPER_USER, UserRole.ADMIN_USER]:
            # Get user permissions efficiently (single query)
            user_permissions = (
                db.query(UserProviderPermission.provider_name)
                .filter(UserProviderPermission.user_id == current_user.id)
                .all()
            )

            if not user_permissions:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="You do not have permission to access any suppliers. Please contact your administrator.",
                )

            # Extract permission names and check for temporary deactivations
            permission_names = [perm.provider_name for perm in user_permissions]
            temp_deactivated_suppliers = []
            active_suppliers = []

            for perm_name in permission_names:
                if perm_name.startswith("TEMP_DEACTIVATED_"):
                    original_name = perm_name.replace("TEMP_DEACTIVATED_", "")
                    temp_deactivated_suppliers.append(original_name)
                else:
                    active_suppliers.append(perm_name)

            # Remove temporarily deactivated suppliers from active list
            final_active_suppliers = [
                supplier
                for supplier in active_suppliers
                if supplier not in temp_deactivated_suppliers
            ]

            # Check if user has permission for the requested supplier
            if request.supplier not in final_active_suppliers:
                if request.supplier in temp_deactivated_suppliers:
                    raise HTTPException(
                        status_code=status.HTTP_403_FORBIDDEN,
                        detail=f"Supplier '{request.supplier}' is temporarily deactivated. Please reactivate it to access data.",
                    )
                else:
                    raise HTTPException(
                        status_code=status.HTTP_403_FORBIDDEN,
                        detail=f"You do not have permission to access supplier '{request.supplier}'. Available suppliers: {', '.join(final_active_suppliers)}",
                    )
        else:
            # For super/admin users, check for temporary deactivations
            user_permissions = (
                db.query(UserProviderPermission.provider_name)
                .filter(
                    UserProviderPermission.user_id == current_user.id,
                    UserProviderPermission.provider_name.like("TEMP_DEACTIVATED_%"),
                )
                .all()
            )

            temp_deactivated_suppliers = [
                perm.provider_name.replace("TEMP_DEACTIVATED_", "")
                for perm in user_permissions
            ]

            if request.supplier in temp_deactivated_suppliers:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail=f"Supplier '{request.supplier}' is temporarily deactivated. Please reactivate it to access data.",
                )

        # FAST FILE ACCESS - Construct the file path
        base_dir = os.path.dirname(
            os.path.dirname(os.path.abspath(__file__))
        )  # Go up to backend directory
        file_path = os.path.join(
            base_dir,
            "static",
            "countryJson",
            request.supplier,
            f"{request.country_iso}.json",
        )

        # Check if file exists
        if not os.path.exists(file_path):
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Country data not found for supplier '{request.supplier}' and country '{request.country_iso}'",
            )

        # Read and parse JSON file efficiently
        with open(file_path, "r", encoding="utf-8") as file:
            country_data = json.load(file)

        # Calculate total hotel count
        total_hotel = len(country_data) if isinstance(country_data, list) else 0

        return {
            "success": True,
            "supplier": request.supplier,
            "country_iso": request.country_iso,
            "total_hotel": total_hotel,
            "data": country_data,
        }

    except HTTPException:
        # Re-raise HTTP exceptions as they are already properly formatted
        raise
    except json.JSONDecodeError as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Invalid JSON format in country data file: {str(e)}",
        )
    except FileNotFoundError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Country data not found for supplier '{request.supplier}' and country '{request.country_iso}'",
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error reading country data: {str(e)}",
        )


@router.post(
    "/get-hotel-data-with-provider-name-and-id", status_code=status.HTTP_200_OK
)
async def get_hotel_data_provider_name_and_id(
    http_request: Request,
    request: ProviderHotelRequest,
    current_user: Annotated[models.User, Depends(get_current_user)],
    db: Session = Depends(get_db),
):
    """
    Get Hotel Data by Provider Identity

    Retrieves comprehensive hotel information with full details for specific supplier mappings.
    Supports batch processing with mixed results - returns successful data while reporting issues.

    Request Body:
    - provider_hotel_identity: Array of {provider_name, provider_id} objects

    Response Types:
    - Success: Hotel data with locations, contacts, and enhanced provider mappings
    - Partial: Successful results + status info for inactive/not found suppliers
    - Error: All suppliers inactive or not found

    Access Control:
    - General users: Only permitted suppliers (points deducted)
    - Super/Admin: All suppliers except temporarily deactivated

    Smart Features:
    - Mixed status handling (some succeed, some fail)
    - Detailed status reporting for each supplier
    - Full hotel details integration via internal API
    """
    # 🔒 IP WHITELIST VALIDATION
    print(
        f"🚀 About to call IP whitelist check for user: {current_user.id} in get-basic-info-follow-countryCode"
    )
    if not check_ip_whitelist(current_user.id, http_request, db):
        # Extract client IP for error message using middleware
        client_ip = get_client_ip(http_request) or "unknown"

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
                    "message": "Your IP address is not in the whitelist. Please contact your administrator to add your IP address to the whitelist.",
                },
                "timestamp": datetime.utcnow().isoformat(),
            },
        )

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
                    detail="You do not have any permission for this request. Please contact your administrator.",
                )
        else:
            # if you really want _everyone else_ blocked until you grant,
            # you could also force them into the same error here.
            allowed_providers = None
            print("Allowed providers for user:", allowed_providers)
            print(
                "Requested identities:",
                [vars(i) for i in request.provider_hotel_identity],
            )
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error processing user permissions: {str(e)}",
        )

    # now you know GENERAL_USER has at least one allowed_provider
    # (or everyone else is None → full access)

    try:
        result = []
        supplier_off_list = []
        not_found_list = []

        for identity in request.provider_hotel_identity:
            name = identity.provider_name
            pid = identity.provider_id

            # Check if user has permission for the requested supplier
            supplier_is_off = False

            # For general users, check if they have active permission for this specific supplier
            if current_user.role == models.UserRole.GENERAL_USER:
                # Get all user permissions
                all_permissions = [
                    perm.provider_name
                    for perm in db.query(models.UserProviderPermission)
                    .filter(models.UserProviderPermission.user_id == current_user.id)
                    .all()
                ]

                # Check for temporary deactivation
                temp_deactivated_name = f"TEMP_DEACTIVATED_{name}"
                is_temp_deactivated = temp_deactivated_name in all_permissions
                has_base_permission = name in all_permissions

                if not has_base_permission:
                    print(f"User has no permission for supplier: {name}")
                    not_found_list.append(f"{name}:{pid}")
                    continue

                if is_temp_deactivated:
                    print(f"Supplier is temporarily deactivated: {name}")
                    supplier_is_off = True
                    supplier_off_list.append(name)
                    continue
            else:
                # For super/admin users, check for temporary deactivation only
                temp_deactivated_permissions = [
                    perm.provider_name
                    for perm in db.query(models.UserProviderPermission)
                    .filter(
                        models.UserProviderPermission.user_id == current_user.id,
                        models.UserProviderPermission.provider_name
                        == f"TEMP_DEACTIVATED_{name}",
                    )
                    .all()
                ]

                if temp_deactivated_permissions:
                    print(
                        f"Supplier is temporarily deactivated for admin/super user: {name}"
                    )
                    supplier_is_off = True
                    supplier_off_list.append(name)
                    continue

            # Find provider mapping
            mapping = (
                db.query(ProviderMapping)
                .filter_by(provider_id=pid, provider_name=name)
                .first()
            )
            if not mapping:
                print(f"No mapping found for provider_id={pid}, provider_name={name}")
                not_found_list.append(f"{name}:{pid}")
                continue

            # Find hotel
            hotel = db.query(Hotel).filter(Hotel.ittid == mapping.ittid).first()
            if not hotel:
                print(f"No hotel found for ittid={mapping.ittid}")
                not_found_list.append(f"{name}:{pid}")
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
                "updated_at": (
                    hotel.updated_at.isoformat() if hotel.updated_at else None
                ),
                "created_at": (
                    hotel.created_at.isoformat() if hotel.created_at else None
                ),
            }

            # Enhanced provider mappings with full details - only for the requested supplier
            enhanced_provider_mappings = []

            # Get full hotel details for the requested supplier mapping only
            hotel_details = await get_hotel_details_internal(
                supplier_code=mapping.provider_name,
                hotel_id=mapping.provider_id,
                current_user=current_user,
                db=db,
            )

            # Create enhanced provider mapping for the requested supplier only
            pm_data = {
                "id": mapping.id,
                "content_mapper": {
                    "ittid": mapping.ittid,
                    "giata_code": mapping.giata_code,
                    "vervotech_id": mapping.vervotech_id,
                },
                "provider_name": mapping.provider_name,
                "provider_id": mapping.provider_id,
                "full_details": hotel_details,
            }
            enhanced_provider_mappings.append(pm_data)

            # Build locations list with only the required fields and order
            locations_list = [
                {
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
                }
                for loc in locations
            ]

            # Build contacts list with only the required fields and order
            contacts_list = [
                {"id": c.id, "contact_type": c.contact_type, "value": c.value}
                for c in contacts
            ]

            result.append(
                {
                    "hotel": hotel_dict,
                    "provider_mappings": enhanced_provider_mappings,
                    "locations": locations_list,
                    "contacts": contacts_list,
                }
            )

        # Prepare response with both results and status information
        response = {
            "success_count": len(result),
            "total_requested": len(request.provider_hotel_identity),
            "hotels": result,
            "status_info": {"timestamp": datetime.utcnow().isoformat()},
        }

        # Add status information for inactive/not found suppliers
        if supplier_off_list or not_found_list:
            response["status_info"]["issues"] = {}

            if supplier_off_list:
                response["status_info"]["issues"]["inactive_suppliers"] = {
                    "count": len(supplier_off_list),
                    "suppliers": supplier_off_list,
                    "message": f"Supplier(s) are temporarily deactivated: {', '.join(supplier_off_list)}",
                }

            if not_found_list:
                response["status_info"]["issues"]["not_found"] = {
                    "count": len(not_found_list),
                    "suppliers": not_found_list,
                    "message": f"Cannot find mapping for: {', '.join(not_found_list)}",
                }

        # If no results at all, return error
        if not result:
            if supplier_off_list and not not_found_list:
                # All suppliers are off
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail={
                        "error": True,
                        "message": f"All suppliers are off: {', '.join(supplier_off_list)}",
                        "error_code": "ALL_SUPPLIERS_OFF",
                        "details": {
                            "status_code": 400,
                            "off_suppliers": supplier_off_list,
                        },
                        "timestamp": datetime.utcnow().isoformat(),
                    },
                )
            elif not_found_list and not supplier_off_list:
                # All suppliers not found
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail={
                        "error": True,
                        "message": "Cannot find mapping for any of the requested suppliers in our system.",
                        "error_code": "HTTP_404",
                        "details": {"status_code": 404},
                        "timestamp": datetime.utcnow().isoformat(),
                    },
                )
            else:
                # Mixed issues but no results
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail={
                        "error": True,
                        "message": "No active suppliers found for the requested identities.",
                        "error_code": "NO_ACTIVE_SUPPLIERS",
                        "details": {
                            "status_code": 400,
                            "off_suppliers": supplier_off_list,
                            "not_found": not_found_list,
                        },
                        "timestamp": datetime.utcnow().isoformat(),
                    },
                )

        return response

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error processing hotel data request: {str(e)}",
        )


@router.post(
    "/get-hotel-mapping-info-using-provider-name-and-id", status_code=status.HTTP_200_OK
)
def get_hotel_mapping_data_using_provider_name_and_id(
    http_request: Request,
    request: ProviderHotelRequest,
    current_user: Annotated[models.User, Depends(get_current_user)],
    db: Session = Depends(get_db),
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
    # 🔒 IP WHITELIST VALIDATION
    print(
        f"🚀 About to call IP whitelist check for user: {current_user.id} in get-hotel-mapping-info-using-provider-name-and-id"
    )
    if not check_ip_whitelist(current_user.id, http_request, db):
        # Extract client IP for error message using middleware
        client_ip = get_client_ip(http_request) or "unknown"

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
                    "message": "Your IP address is not in the whitelist. Please contact your administrator to add your IP address to the whitelist.",
                },
                "timestamp": datetime.utcnow().isoformat(),
            },
        )

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
                    detail="You do not have any permission for this request. Please contact your administrator.",
                )
        else:
            # if you really want _everyone else_ blocked until you grant,
            # you could also force them into the same error here.
            allowed_providers = None
            print("Allowed providers for user:", allowed_providers)
            print(
                "Requested identities:",
                [vars(i) for i in request.provider_hotel_identity],
            )
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error processing user permissions: {str(e)}",
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
            provider_mappings_list = [
                {
                    "ittid": hotel.ittid,
                    "provider_mapping_id": mapping.id,
                    "provider_id": mapping.provider_id,
                    "provider_name": mapping.provider_name,
                    # "system_type": mapping.system_type,
                    # "giata_code": mapping.giata_code,
                    # "vervotech_id": mapping.vervotech_id,
                    # "updated_at": mapping.updated_at.isoformat() if mapping.updated_at else None,
                    "created_at": (
                        mapping.created_at.isoformat() if mapping.created_at else None
                    ),
                }
            ]

            result.append({"provider_mappings": provider_mappings_list})

        if not result:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Cannot find mapping for any of the requested suppliers in our system.",
            )

        return result

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error processing mapping data request: {str(e)}",
        )


# Get provider mapping
@router.post("/get-hotel-with-ittid", status_code=status.HTTP_200_OK)
async def get_hotels_using_ittid_list(
    http_request: Request,
    request: ITTIDRequest,
    current_user: Annotated[models.User, Depends(get_current_user)],
    db: Session = Depends(get_db),
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
    - Automatic filtering of mappings with null full_details

    Args:
        request (ITTIDRequest): Request containing list of ITTID values
        current_user: Currently authenticated user (injected by dependency)
        db (Session): Database session (injected by dependency)

    Returns:
        List[dict]: List of hotels with provider mappings and full details
                   (only includes mappings where full_details is not null)

    Access Control:
        - GENERAL_USER: Only sees providers they have permission for
        - SUPER_USER/ADMIN_USER: Can see all provider mappings

    Filtering:
        - Provider mappings with null full_details are automatically excluded
        - Hotels with no valid provider mappings are excluded from results
    """
    # 🔒 IP WHITELIST VALIDATION
    print(
        f"🚀 About to call IP whitelist check for user: {current_user.id} in get-basic-info-follow-countryCode"
    )
    if not check_ip_whitelist(current_user.id, http_request, db):
        # Extract client IP for error message using middleware
        client_ip = get_client_ip(http_request) or "unknown"

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
                    "message": "Your IP address is not in the whitelist. Please contact your administrator to add your IP address to the whitelist.",
                },
                "timestamp": datetime.utcnow().isoformat(),
            },
        )
    try:
        # 🚫 NO POINT DEDUCTION for super_user and admin_user
        if current_user.role == models.UserRole.GENERAL_USER:
            deduct_points_for_general_user(current_user, db)
        elif current_user.role in [
            models.UserRole.SUPER_USER,
            models.UserRole.ADMIN_USER,
        ]:
            print(
                f"🔓 Point deduction skipped for {current_user.role}: {current_user.email}"
            )

        # Fetch hotels
        hotels = (
            db.query(models.Hotel).filter(models.Hotel.ittid.in_(request.ittid)).all()
        )
        if not hotels:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="No hotels found for the provided ittid values.",
            )

        result = []

        # For General Users: only allowed providers (excluding temp deactivated)
        if current_user.role == models.UserRole.GENERAL_USER:
            # Get all user permissions (including temp deactivated ones)
            all_permissions = [
                permission.provider_name
                for permission in db.query(UserProviderPermission)
                .filter(UserProviderPermission.user_id == current_user.id)
                .all()
            ]

            # Separate active and temporarily deactivated suppliers
            temp_deactivated_suppliers = []
            allowed_providers = []

            for perm in all_permissions:
                if perm.startswith("TEMP_DEACTIVATED_"):
                    original_name = perm.replace("TEMP_DEACTIVATED_", "")
                    temp_deactivated_suppliers.append(original_name)
                else:
                    allowed_providers.append(perm)

            # Remove temporarily deactivated suppliers from allowed providers
            final_allowed_providers = [
                provider
                for provider in allowed_providers
                if provider not in temp_deactivated_suppliers
            ]

            for hotel in hotels:
                provider_mappings = (
                    db.query(models.ProviderMapping)
                    .filter(
                        models.ProviderMapping.ittid == hotel.ittid,
                        models.ProviderMapping.provider_name.in_(
                            final_allowed_providers
                        ),
                    )
                    .all()
                )

                formatted_provider_mappings = []
                for mapping in provider_mappings:
                    # Get full hotel details for this provider mapping
                    hotel_details = await get_hotel_details_internal(
                        supplier_code=mapping.provider_name,
                        hotel_id=mapping.provider_id,
                        current_user=current_user,
                        db=db,
                    )

                    # FILTER: Only include mappings with non-null full_details
                    if hotel_details is not None:
                        mapping_data = {
                            "id": mapping.id,
                            "ittid": mapping.ittid,
                            "provider_name": mapping.provider_name,
                            "provider_id": mapping.provider_id,
                            "updated_at": mapping.updated_at,
                            "full_details": hotel_details,
                        }
                        formatted_provider_mappings.append(mapping_data)

                # Only include hotel in result if it has valid provider mappings
                if formatted_provider_mappings:
                    result.append(
                        {
                            "ittid": hotel.ittid,
                            "provider_mappings": formatted_provider_mappings,
                        }
                    )
        else:
            # For SUPER/ADMIN users – return all mappings with full details (excluding temp deactivated)
            # Get temporarily deactivated suppliers for super/admin users
            all_permissions = [
                permission.provider_name
                for permission in db.query(UserProviderPermission)
                .filter(UserProviderPermission.user_id == current_user.id)
                .all()
            ]

            temp_deactivated_suppliers = []
            for perm in all_permissions:
                if perm.startswith("TEMP_DEACTIVATED_"):
                    original_name = perm.replace("TEMP_DEACTIVATED_", "")
                    temp_deactivated_suppliers.append(original_name)

            for hotel in hotels:
                all_provider_mappings = (
                    db.query(models.ProviderMapping)
                    .filter(models.ProviderMapping.ittid == hotel.ittid)
                    .all()
                )

                # Filter out temporarily deactivated suppliers
                if temp_deactivated_suppliers:
                    provider_mappings = [
                        pm
                        for pm in all_provider_mappings
                        if pm.provider_name not in temp_deactivated_suppliers
                    ]
                else:
                    provider_mappings = all_provider_mappings

                formatted_provider_mappings = []
                for mapping in provider_mappings:
                    # Get full hotel details for this provider mapping
                    hotel_details = await get_hotel_details_internal(
                        supplier_code=mapping.provider_name,
                        hotel_id=mapping.provider_id,
                        current_user=current_user,
                        db=db,
                    )

                    # FILTER: Only include mappings with non-null full_details
                    if hotel_details is not None:
                        mapping_data = {
                            "id": mapping.id,
                            "ittid": mapping.ittid,
                            "provider_name": mapping.provider_name,
                            "provider_id": mapping.provider_id,
                            "updated_at": mapping.updated_at,
                            "full_details": hotel_details,
                        }
                        formatted_provider_mappings.append(mapping_data)

                # Only include hotel in result if it has valid provider mappings
                if formatted_provider_mappings:
                    result.append(
                        {
                            "ittid": hotel.ittid,
                            "provider_mappings": formatted_provider_mappings,
                        }
                    )
        return result
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error processing mapping data request: {str(e)}",
        )


@router.get("/get-hotel-with-ittid/{ittid}", status_code=status.HTTP_200_OK)
async def get_hotel_using_ittid(
    http_request: Request,
    ittid: str,
    current_user: Annotated[models.User, Depends(get_current_user)],
    db: Session = Depends(get_db),
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
    # 🔒 IP WHITELIST VALIDATION
    print(
        f"🚀 About to call IP whitelist check for user: {current_user.id} in get-hotel-with-ittid"
    )
    if not check_ip_whitelist(current_user.id, http_request, db):
        # Extract client IP for error message using middleware
        client_ip = get_client_ip(http_request) or "unknown"

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
                    "message": "Your IP address is not in the whitelist. Please contact your administrator to add your IP address to the whitelist.",
                },
                "timestamp": datetime.utcnow().isoformat(),
            },
        )

    try:
        # Get hotel first (no point deduction yet)
        hotel = db.query(models.Hotel).filter(models.Hotel.ittid == ittid).first()
        if not hotel:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Hotel with id '{ittid}' not found.",
            )

        # 🔍 CHECK FOR ACTIVE SUPPLIERS (Provider Mappings)
        # First check if there are ANY provider mappings for this ITTID
        all_provider_mappings = (
            db.query(models.ProviderMapping)
            .filter(models.ProviderMapping.ittid == ittid)
            .all()
        )

        if not all_provider_mappings:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Cannot active supplier with this ittid '{ittid}'. No supplier mappings found for this hotel.",
            )

        # Check user-specific permissions for general users
        if current_user.role == models.UserRole.GENERAL_USER:
            # Get all user permissions (including temp deactivated ones)
            all_permissions = [
                permission.provider_name
                for permission in db.query(UserProviderPermission)
                .filter(UserProviderPermission.user_id == current_user.id)
                .all()
            ]

            # Separate active and temporarily deactivated suppliers
            temp_deactivated_suppliers = []
            allowed_providers = []

            for perm in all_permissions:
                if perm.startswith("TEMP_DEACTIVATED_"):
                    # Extract original supplier name
                    original_name = perm.replace("TEMP_DEACTIVATED_", "")
                    temp_deactivated_suppliers.append(original_name)
                else:
                    allowed_providers.append(perm)

            # Remove temporarily deactivated suppliers from allowed providers
            final_allowed_providers = [
                provider
                for provider in allowed_providers
                if provider not in temp_deactivated_suppliers
            ]

            if not final_allowed_providers:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="Do not have permission or not active",
                )

            # Check if user has access to any of the suppliers for this hotel
            accessible_provider_mappings = (
                db.query(models.ProviderMapping)
                .filter(
                    models.ProviderMapping.ittid == ittid,
                    models.ProviderMapping.provider_name.in_(final_allowed_providers),
                )
                .all()
            )

            if not accessible_provider_mappings:
                # Hotel exists and has suppliers, but user doesn't have access to any of them
                available_suppliers = [pm.provider_name for pm in all_provider_mappings]
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail=f"Cannot access suppliers for this ittid '{ittid}'. Available suppliers: {', '.join(available_suppliers)}. Contact admin for access.",
                )

        print(
            f"✅ Active suppliers found for ITTID {ittid}: {len(all_provider_mappings)} suppliers"
        )

        # Get related data
        locations = (
            db.query(models.Location).filter(models.Location.ittid == hotel.ittid).all()
        )
        # chains = db.query(models.Chain).filter(models.Chain.ittid == hotel.ittid).all()
        contacts = (
            db.query(models.Contact).filter(models.Contact.ittid == hotel.ittid).all()
        )

        # Get provider mappings for response (based on user role)
        if current_user.role == models.UserRole.GENERAL_USER:
            # For general users, only show accessible provider mappings (excluding temp deactivated)
            # Use the same logic as above to get final allowed providers
            all_permissions = [
                permission.provider_name
                for permission in db.query(UserProviderPermission)
                .filter(UserProviderPermission.user_id == current_user.id)
                .all()
            ]

            # Separate active and temporarily deactivated suppliers
            temp_deactivated_suppliers = []
            allowed_providers = []

            for perm in all_permissions:
                if perm.startswith("TEMP_DEACTIVATED_"):
                    original_name = perm.replace("TEMP_DEACTIVATED_", "")
                    temp_deactivated_suppliers.append(original_name)
                else:
                    allowed_providers.append(perm)

            # Remove temporarily deactivated suppliers from allowed providers
            final_allowed_providers = [
                provider
                for provider in allowed_providers
                if provider not in temp_deactivated_suppliers
            ]

            provider_mappings = (
                db.query(models.ProviderMapping)
                .filter(
                    models.ProviderMapping.ittid == ittid,
                    models.ProviderMapping.provider_name.in_(final_allowed_providers),
                )
                .all()
            )
        else:
            # For super/admin users, check for temporarily deactivated suppliers
            all_permissions = [
                permission.provider_name
                for permission in db.query(UserProviderPermission)
                .filter(UserProviderPermission.user_id == current_user.id)
                .all()
            ]

            # Get temporarily deactivated suppliers for super/admin users
            temp_deactivated_suppliers = []
            for perm in all_permissions:
                if perm.startswith("TEMP_DEACTIVATED_"):
                    original_name = perm.replace("TEMP_DEACTIVATED_", "")
                    temp_deactivated_suppliers.append(original_name)

            # Filter out temporarily deactivated suppliers from all provider mappings
            if temp_deactivated_suppliers:
                provider_mappings = [
                    pm
                    for pm in all_provider_mappings
                    if pm.provider_name not in temp_deactivated_suppliers
                ]
            else:
                provider_mappings = all_provider_mappings

        # Enhanced provider mappings with full details
        enhanced_provider_mappings = []
        for pm in provider_mappings:
            # Get full hotel details for this provider mapping
            hotel_details = await get_hotel_details_internal(
                supplier_code=pm.provider_name,
                hotel_id=pm.provider_id,
                current_user=current_user,
                db=db,
            )

            # Create simplified provider mapping with only essential fields
            pm_data = {
                "id": pm.id,
                "ittid": pm.ittid,
                "giata_code": pm.giata_code,
                "provider_name": pm.provider_name,
                "provider_id": pm.provider_id,
                "updated_at": pm.updated_at,
                "full_details": hotel_details,
            }
            enhanced_provider_mappings.append(pm_data)

        # Serialize the response with enhanced provider mappings
        response_data = {
            "total_supplier": len(provider_mappings),
            "provider_list": [pm.provider_name for pm in provider_mappings],
            "hotel": serialize_datetime_objects(hotel),
            "provider_mappings": enhanced_provider_mappings,
            "locations": [serialize_datetime_objects(loc) for loc in locations],
            # "chains": [serialize_datetime_objects(chain) for chain in chains],
            "contacts": [serialize_datetime_objects(contact) for contact in contacts],
        }

        # 💸 POINT DEDUCTION ONLY ON SUCCESSFUL REQUEST
        # Points are deducted only when the request is successful and data is returned
        if current_user.role == models.UserRole.GENERAL_USER:
            deduct_points_for_general_user(current_user, db)
            print(
                f"💸 Points deducted for successful request by general user: {current_user.email}"
            )
        elif current_user.role in [
            models.UserRole.SUPER_USER,
            models.UserRole.ADMIN_USER,
        ]:
            print(
                f"🔓 Point deduction skipped for {current_user.role}: {current_user.email}"
            )
        return response_data

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error processing mapping data request: {str(e)}",
        )


@router.get(
    "/get-full-hotel-with-itt-mapping-id/{ittid}", status_code=status.HTTP_200_OK
)
@log_content_activity(
    security_level=SecurityLevel.LOW,
    content_type="hotel_data",
    operation="get_hotel_with_ittid",
)
async def get_full_hotel_with_primary_photo(
    http_request: Request,
    ittid: str,
    current_user: Annotated[models.User, Depends(get_current_user)],
    db: Session = Depends(get_db),
):
    """
    Get Hotel Details with Provider Mappings Having Primary Photo

    Retrieves comprehensive hotel information but only includes provider mappings
    where the full_details contains a primary_photo. This filters out providers
    without complete image data.

    Features:
    - Filters provider mappings to only those with primary_photo in full_details
    - Role-based access control for provider data
    - Active supplier validation and permission checks
    - Point deduction only on successful data retrieval
    - Returns have_provider_list showing all available providers

    Args:
        ittid (str): The ITT hotel identifier
        current_user: Currently authenticated user (injected by dependency)
        db (Session): Database session (injected by dependency)

    Returns:
        dict: Hotel data with filtered provider mappings including:
            - total_supplier: Count of providers with primary_photo
            - have_provider_list: List of all available provider names
            - hotel: Basic hotel information
            - provider_mappings: Only providers with primary_photo in full_details
            - locations: Hotel location information
            - contacts: Hotel contact information

    Access Control:
        - GENERAL_USER: Only sees providers they have permission for
        - SUPER_USER/ADMIN_USER: Can see all provider mappings

    HTTP Status Codes:
        200: Hotel data retrieved successfully
        403: Forbidden - No access to suppliers for this hotel
        404: Hotel not found or no supplier mappings with primary_photo
    """
    # 🔒 IP WHITELIST VALIDATION
    print(
        f"🚀 About to call IP whitelist check for user: {current_user.id} in get-full-hotel-with-itt-mapping-id"
    )
    if not check_ip_whitelist(current_user.id, http_request, db):
        client_ip = get_client_ip(http_request) or "unknown"

        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"Access denied. Your IP address {client_ip} is not whitelisted for this user account.",
        )

    # 📝 MANUAL ACTIVITY LOGGING
    try:
        from security.audit_logging import AuditLogger, ActivityType, SecurityLevel

        audit_logger = AuditLogger(db)
        audit_logger.log_activity(
            activity_type=ActivityType.API_ACCESS,
            user_id=current_user.id,
            details={
                "action": "get_full_hotel_with_primary_photo",
                "ittid": ittid,
                "endpoint": f"/get-full-hotel-with-itt-mapping-id/{ittid}",
                "method": "GET",
                "category": "content",
                "content_type": "hotel_data",
                "operation": "get_hotel_with_ittid",
                "user_role": current_user.role.value,
                "user_email": current_user.email,
            },
            request=http_request,
            security_level=SecurityLevel.LOW,
            success=True,
        )
        print(f"✅ LOGGED ACTIVITY: User {current_user.id} accessed hotel {ittid}")
    except Exception as e:
        print(f"❌ LOGGING ERROR: {e}")
        # Don't fail the request if logging fails
        pass

    try:
        # Get hotel first
        hotel = db.query(models.Hotel).filter(models.Hotel.ittid == ittid).first()
        if not hotel:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Hotel with id '{ittid}' not found.",
            )

        # Check for provider mappings
        all_provider_mappings = (
            db.query(models.ProviderMapping)
            .filter(models.ProviderMapping.ittid == ittid)
            .all()
        )

        if not all_provider_mappings:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Cannot active supplier with this ittid '{ittid}'. No supplier mappings found for this hotel.",
            )

        # Check user permissions
        if current_user.role == models.UserRole.GENERAL_USER:
            try:
                all_permissions = [
                    str(permission.provider_name) if permission.provider_name else ""
                    for permission in db.query(UserProviderPermission)
                    .filter(UserProviderPermission.user_id == current_user.id)
                    .all()
                ]

                temp_deactivated_suppliers = []
                allowed_providers = []

                for perm in all_permissions:
                    if perm and perm.startswith("TEMP_DEACTIVATED_"):
                        original_name = perm.replace("TEMP_DEACTIVATED_", "")
                        temp_deactivated_suppliers.append(original_name)
                    elif perm:
                        allowed_providers.append(perm)

                final_allowed_providers = [
                    provider
                    for provider in allowed_providers
                    if provider not in temp_deactivated_suppliers
                ]
            except Exception as perm_error:
                print(f"❌ Permission processing error: {perm_error}")
                raise HTTPException(
                    status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                    detail=f"Error processing user permissions: {str(perm_error)}",
                )

            if not final_allowed_providers:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="Do not have permission or not active",
                )

            accessible_provider_mappings = (
                db.query(models.ProviderMapping)
                .filter(
                    models.ProviderMapping.ittid == ittid,
                    models.ProviderMapping.provider_name.in_(final_allowed_providers),
                )
                .all()
            )

            if not accessible_provider_mappings:
                available_suppliers = [pm.provider_name for pm in all_provider_mappings]
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail=f"Cannot access suppliers for this ittid '{ittid}'. Available suppliers: {', '.join(available_suppliers)}. Contact admin for access.",
                )

        # Get related data
        locations = (
            db.query(models.Location).filter(models.Location.ittid == hotel.ittid).all()
        )
        contacts = (
            db.query(models.Contact).filter(models.Contact.ittid == hotel.ittid).all()
        )

        # Get provider mappings based on user role
        if current_user.role == models.UserRole.GENERAL_USER:
            try:
                all_permissions = [
                    str(permission.provider_name) if permission.provider_name else ""
                    for permission in db.query(UserProviderPermission)
                    .filter(UserProviderPermission.user_id == current_user.id)
                    .all()
                ]

                temp_deactivated_suppliers = []
                allowed_providers = []

                for perm in all_permissions:
                    if perm and perm.startswith("TEMP_DEACTIVATED_"):
                        original_name = perm.replace("TEMP_DEACTIVATED_", "")
                        temp_deactivated_suppliers.append(original_name)
                    elif perm:
                        allowed_providers.append(perm)

                final_allowed_providers = [
                    provider
                    for provider in allowed_providers
                    if provider not in temp_deactivated_suppliers
                ]

                provider_mappings = (
                    db.query(models.ProviderMapping)
                    .filter(
                        models.ProviderMapping.ittid == ittid,
                        models.ProviderMapping.provider_name.in_(
                            final_allowed_providers
                        ),
                    )
                    .all()
                )
            except Exception as perm_error:
                print(f"❌ Permission processing error for general user: {perm_error}")
                raise HTTPException(
                    status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                    detail=f"Error processing user permissions: {str(perm_error)}",
                )
        else:
            try:
                all_permissions = [
                    str(permission.provider_name) if permission.provider_name else ""
                    for permission in db.query(UserProviderPermission)
                    .filter(UserProviderPermission.user_id == current_user.id)
                    .all()
                ]

                temp_deactivated_suppliers = []
                for perm in all_permissions:
                    if perm and perm.startswith("TEMP_DEACTIVATED_"):
                        original_name = perm.replace("TEMP_DEACTIVATED_", "")
                        temp_deactivated_suppliers.append(original_name)

                if temp_deactivated_suppliers:
                    provider_mappings = [
                        pm
                        for pm in all_provider_mappings
                        if str(pm.provider_name) not in temp_deactivated_suppliers
                    ]
                else:
                    provider_mappings = all_provider_mappings
            except Exception as perm_error:
                print(
                    f"❌ Permission processing error for admin/super user: {perm_error}"
                )
                raise HTTPException(
                    status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                    detail=f"Error processing user permissions: {str(perm_error)}",
                )

        # Build have_provider_list with provider IDs grouped by provider name
        have_provider_dict = {}
        for pm in provider_mappings:
            provider_name = str(pm.provider_name) if pm.provider_name else "unknown"
            provider_id = str(pm.provider_id) if pm.provider_id else "unknown"

            if provider_name not in have_provider_dict:
                have_provider_dict[provider_name] = []
            have_provider_dict[provider_name].append(provider_id)

        # Convert to list of dicts format - sort by provider name for consistency
        try:
            have_provider_list = [
                {provider: ids}
                for provider, ids in sorted(
                    have_provider_dict.items(), key=lambda x: str(x[0])
                )
            ]
        except Exception as sort_error:
            print(f"⚠️ Sorting error in have_provider_list: {sort_error}")
            # Fallback without sorting
            have_provider_list = [
                {provider: ids} for provider, ids in have_provider_dict.items()
            ]

        # Enhanced provider mappings with full details - FILTER by primary_photo
        enhanced_provider_mappings = []
        give_data_supplier_list = []

        for pm in provider_mappings:
            hotel_details = await get_hotel_details_internal(
                supplier_code=pm.provider_name,
                hotel_id=pm.provider_id,
                current_user=current_user,
                db=db,
            )

            # Only include if full_details exists and has primary_photo
            if (
                hotel_details
                and isinstance(hotel_details, dict)
                and hotel_details.get("primary_photo")
            ):
                pm_data = {
                    "id": pm.id,
                    "ittid": pm.ittid,
                    "provider_name": pm.provider_name,
                    "provider_id": pm.provider_id,
                    "updated_at": pm.updated_at,
                    "full_details": hotel_details,
                }
                enhanced_provider_mappings.append(pm_data)

                # Track suppliers that provided data
                if pm.provider_name not in give_data_supplier_list:
                    give_data_supplier_list.append(pm.provider_name)

        # Serialize the response
        response_data = {
            "total_supplier": len(have_provider_dict),
            "have_provider_list": have_provider_list,
            "give_data_supplier": len(give_data_supplier_list),
            "give_data_supplier_list": give_data_supplier_list,
            "hotel": serialize_datetime_objects(hotel),
            "provider_mappings": enhanced_provider_mappings,
            "locations": [serialize_datetime_objects(loc) for loc in locations],
            "contacts": [serialize_datetime_objects(contact) for contact in contacts],
        }

        # Point deduction only on successful request
        if current_user.role == models.UserRole.GENERAL_USER:
            deduct_points_for_general_user(current_user, db)
            print(
                f"💸 Points deducted for successful request by general user: {current_user.email}"
            )
        elif current_user.role in [
            models.UserRole.SUPER_USER,
            models.UserRole.ADMIN_USER,
        ]:
            print(
                f"🔓 Point deduction skipped for {current_user.role}: {current_user.email}"
            )

        return response_data

    except HTTPException:
        raise
    except Exception as e:
        import traceback

        error_traceback = traceback.format_exc()
        print(
            f"❌ Full error in get-full-hotel-with-itt-mapping-id:\n{error_traceback}"
        )
        print(f"❌ Error type: {type(e).__name__}")
        print(f"❌ Error message: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error processing mapping data request: {str(e)}",
        )


@router.get("/get-all-basic-hotel-info", status_code=status.HTTP_200_OK)
def get_all_hotels(
    http_request: Request,
    current_user: Annotated[models.User, Depends(get_current_user)],
    page: int = Query(1, ge=1, description="Page number, starting from 1"),
    limit: int = Query(
        50, ge=1, le=1000, description="Number of hotels per page (max 1000)"
    ),
    resume_key: Optional[str] = Query(
        None,
        description="Resume key for pagination - REQUIRED for pages after the first",
    ),
    first_request: bool = Query(
        False, description="Set to true for the very first request to start pagination"
    ),
    db: Session = Depends(get_db),
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
    # 🔒 IP WHITELIST VALIDATION
    print(
        f"🚀 About to call IP whitelist check for user: {current_user.id} in get-all-basic-hotel-info"
    )
    if not check_ip_whitelist(current_user.id, http_request, db):
        # Extract client IP for error message using middleware
        client_ip = get_client_ip(http_request) or "unknown"

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
                    "message": "Your IP address is not in the whitelist. Please contact your administrator to add your IP address to the whitelist.",
                },
                "timestamp": datetime.utcnow().isoformat(),
            },
        )

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
                    detail="You do not have any permission for this request. Please contact your administrator.",
                )
        elif current_user.role in [UserRole.SUPER_USER, UserRole.ADMIN_USER]:
            print(
                f"🔓 Point deduction skipped for {current_user.role}: {current_user.email}"
            )
            allowed_providers = None
        else:
            allowed_providers = None
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error processing user permissions: {str(e)}",
        )

    # 🔒 SMART RESUME KEY VALIDATION
    # Determine if this is a first request or subsequent request
    is_first_request = (
        not resume_key
    )  # If no resume_key provided, treat as first request

    # If resume_key is provided, it must be valid (subsequent request)
    if resume_key:
        is_first_request = False
        print(f"📄 Subsequent request detected with resume_key: {resume_key[:20]}...")
    else:
        is_first_request = True
        print("📄 First request detected (no resume_key provided)")

    # Validate conflicting parameters (optional - can remove if not needed)
    if first_request and resume_key:
        print(
            "⚠️  Warning: Both first_request=true and resume_key provided. Using resume_key logic."
        )
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
                raise ValueError(
                    "Invalid resume key format. Expected format: 'id_randomstring'"
                )

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
                raise ValueError(
                    f"Invalid random part length. Expected 50 characters, got {len(random_part)}"
                )

            # Validate random part contains only alphanumeric characters
            if not random_part.isalnum():
                raise ValueError(
                    "Random part must contain only alphanumeric characters"
                )

            # Check if the hotel ID actually exists in the database
            hotel_exists = (
                db.query(models.Hotel).filter(models.Hotel.id == last_id).first()
            )

            if not hotel_exists:
                raise ValueError(
                    f"Resume key references non-existent hotel record (ID: {last_id})"
                )

            # For general users, also check if they have access to this hotel through their providers
            if allowed_providers is not None:
                hotel_accessible = (
                    db.query(models.ProviderMapping)
                    .filter(
                        models.ProviderMapping.ittid == hotel_exists.ittid,
                        models.ProviderMapping.provider_name.in_(allowed_providers),
                    )
                    .first()
                )

                if not hotel_accessible:
                    raise ValueError(
                        f"Resume key references hotel not accessible to user (ITTID: {hotel_exists.ittid})"
                    )

            print(f"✅ Valid resume_key: Starting from hotel ID {last_id}")

        except ValueError as e:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Invalid resume_key: {str(e)}. Please use a valid resume_key from a previous response or omit it to start from the beginning.",
            )
        except Exception as e:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Error processing resume_key: {str(e)}. Please use a valid resume_key from a previous response.",
            )

    try:
        query = db.query(Hotel).order_by(Hotel.id)
        if last_id:
            query = query.filter(Hotel.id > last_id)

        # Filter by allowed providers for general users
        if allowed_providers is not None:
            hotel_ids = (
                db.query(ProviderMapping.ittid)
                .filter(ProviderMapping.provider_name.in_(allowed_providers))
                .distinct()
                .all()
            )
            hotel_ids = [h[0] for h in hotel_ids]
            query = query.filter(Hotel.ittid.in_(hotel_ids))

        hotels = query.limit(limit).all()
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error querying hotel data: {str(e)}",
        )

    # 🔑 Generate next resume_key with enhanced validation
    if hotels and len(hotels) == limit:
        last_hotel_id = hotels[-1].id
        # Generate cryptographically secure random string
        rand_str = "".join(
            secrets.choice(string.ascii_letters + string.digits) for _ in range(50)
        )
        next_resume_key = f"{last_hotel_id}_{rand_str}"
        print(
            f"📄 Generated resume_key for next page: {last_hotel_id}_[50-char-random]"
        )
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
            "geocode": {"latitude": hotel.latitude, "longitude": hotel.longitude},
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
        accessible_hotel_ids = (
            db.query(ProviderMapping.ittid)
            .filter(ProviderMapping.provider_name.in_(allowed_providers))
            .distinct()
            .all()
        )
        accessible_hotel_ids = [h[0] for h in accessible_hotel_ids]
        accessible_hotel_count = (
            db.query(Hotel).filter(Hotel.ittid.in_(accessible_hotel_ids)).count()
        )
    else:
        # Super/admin users can access all hotels
        accessible_hotel_count = total_hotel

    print(
        f"📊 Returning {len(hotel_list)} hotels out of {accessible_hotel_count} accessible hotels (Total in DB: {total_hotel})"
    )

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
            "resume_key_required_for_next": next_resume_key is not None,
        },
        "usage_instructions": {
            "first_request": "No resume_key needed for the first request",
            "subsequent_requests": "Must provide valid resume_key from previous response for next pages",
            "resume_key_format": "{hotel_id}_{50_character_random_string}",
            "note": "resume_key is automatically required for subsequent requests",
        },
    }


def check_ip_whitelist(user_id: str, request: Request, db: Session) -> bool:
    """
    Check if the user's IP is whitelisted

    Args:
        user_id: User ID to check whitelist for
        request: FastAPI request object to extract IP
        db: Database session

    Returns:
        bool: True if IP is whitelisted or no whitelist exists, False if blocked
    """
    print(f"🚀 IP Whitelist Function Called - Starting check for user: {user_id}")
    try:
        print(f"🔍 IP Whitelist Check - User ID: {user_id}")

        # Extract client IP using the middleware helper function
        client_ip = get_client_ip(request)

        print(f"🌐 Detected Client IP: {client_ip}")

        if not client_ip:
            print("⚠️ Could not determine client IP, allowing access (fail open)")
            return True

        # Check if user has any IP whitelist entries
        whitelist_entries = (
            db.query(models.UserIPWhitelist)
            .filter(
                models.UserIPWhitelist.user_id == user_id,
                models.UserIPWhitelist.is_active == True,
            )
            .all()
        )

        print(f"📋 Found {len(whitelist_entries)} whitelist entries for user")

        # REQUIRE IP WHITELIST: If no whitelist entries exist, DENY access
        if not whitelist_entries:
            print(
                "❌ No whitelist entries found, DENYING access (IP whitelist required)"
            )
            return False

        # Check if current IP is in whitelist
        whitelisted_ips = [entry.ip_address for entry in whitelist_entries]
        print(f"🔒 Whitelisted IPs: {whitelisted_ips}")

        is_whitelisted = client_ip in whitelisted_ips
        print(f"🎯 IP {client_ip} whitelisted: {is_whitelisted}")

        return is_whitelisted

    except Exception as e:
        # If there's an error checking whitelist, fail open (allow access)
        print(f"❌ Error checking IP whitelist: {e}")
        print(f"❌ Exception type: {type(e).__name__}")
        print(f"❌ Exception details: {str(e)}")
        import traceback

        print(f"❌ Traceback: {traceback.format_exc()}")
        return True


@router.get("/get-all-ittid", status_code=status.HTTP_200_OK)
def get_all_ittid(
    request: Request,
    current_user: Annotated[models.User, Depends(get_current_user)],
    db: Session = Depends(get_db),
):
    print(f"🎯 get_all_ittid → User: {current_user.id}")

    # ---------------------------------------------------------
    # 1️⃣ IP WHITELIST CHECK
    # ---------------------------------------------------------
    print(f"🚀 Checking IP whitelist for user {current_user.id}")
    if not check_ip_whitelist(current_user.id, request, db):
        client_ip = get_client_ip(request) or "unknown"
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={
                "error": True,
                "message": "Access denied: IP address not whitelisted",
                "error_code": "IP_NOT_WHITELISTED",
                "details": {"client_ip": client_ip, "user_id": current_user.id},
                "timestamp": datetime.utcnow().isoformat(),
            },
        )

    # ---------------------------------------------------------
    # 2️⃣ PERMISSION RESOLUTION
    # ---------------------------------------------------------
    try:
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
                    status_code=403,
                    detail="No provider permissions assigned. Contact admin.",
                )

        else:  # SUPER_USER / ADMIN_USER
            print(f"🔓 No point deduction for role: {current_user.role}")
            allowed_providers = None

    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"Error processing user permissions: {str(e)}"
        )

    # ---------------------------------------------------------
    # 3️⃣ HOTEL ITTID FETCH LOGIC
    # ---------------------------------------------------------
    try:
        if allowed_providers:
            # Permissions restricted
            records = (
                db.query(ProviderMapping.ittid)
                .filter(ProviderMapping.provider_name.in_(allowed_providers))
                .distinct()
                .all()
            )
            supplier_count = len(allowed_providers)
        else:
            # Fetch all
            records = db.query(Hotel.ittid).distinct().all()
            supplier_count = db.query(ProviderMapping.provider_name).distinct().count()

        ittid_list = [row[0] for row in records if row[0]]

        print(f"📊 Found {len(ittid_list)} ITTIDs from {supplier_count} suppliers")

    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"Error retrieving database data: {str(e)}"
        )

    # ---------------------------------------------------------
    # 4️⃣ SMART CACHING LOGIC
    # ---------------------------------------------------------
    now = datetime.utcnow()
    today_key = now.strftime("%d%m%Y")  # e.g., 16112025

    base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    user_dir = os.path.join(
        base_dir, "static", "read", "itt_mapping_id", current_user.id
    )
    os.makedirs(user_dir, exist_ok=True)

    file_saved = False
    file_from_cache = False
    latest_file_path = None

    # Scan existing JSONs
    existing_files = [
        f for f in os.listdir(user_dir) if f.endswith("_itt_mapping_id.json")
    ]

    if existing_files:
        latest_file = sorted(existing_files, reverse=True)[0]
        file_date_str = latest_file[:8]  # DDMMYYYY

        # Compare file date vs today's date
        if file_date_str == today_key:
            # 🎉 Cached
            latest_file_path = os.path.join(user_dir, latest_file)
            with open(latest_file_path, "r", encoding="utf-8") as f:
                cached = json.load(f)

            ittid_list = cached.get("ittid_list", ittid_list)
            supplier_count = cached.get("total_supplier", supplier_count)
            file_from_cache = True

            print(f"📂 Using cache → {latest_file}")

        else:
            # ❗Older → must update
            latest_file_path = None

    # If no valid cache, write fresh file
    if not file_from_cache:
        timestamp = f"{today_key}{now.second:02d}"
        filename = f"{timestamp}_itt_mapping_id.json"
        latest_file_path = os.path.join(user_dir, filename)

        new_payload = {
            "total_supplier": supplier_count,
            "total_ittid": len(ittid_list),
            "ittid_list": ittid_list,
        }

        with open(latest_file_path, "w", encoding="utf-8") as f:
            json.dump(new_payload, f, indent=4)

        file_saved = True
        print(f"💾 New file saved → {filename}")

    # ---------------------------------------------------------
    # 5️⃣ FINAL RESPONSE
    # ---------------------------------------------------------
    response_path = (
        latest_file_path.replace(base_dir + os.sep, "") if latest_file_path else None
    )

    return {
        "total_supplier": supplier_count,
        "total_ittid": len(ittid_list),
        "ittid_list": ittid_list,
        "file_saved": file_saved,
        "file_from_cache": file_from_cache,
        "file_path": response_path,
    }


@router.get(
    "/get-all-basic-info-using-a-supplier",
    response_model=GetAllHotelResponse,
    status_code=status.HTTP_200_OK,
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
        GET /get-all-basic-info-using-a-supplier?provider_name=booking&limit_per_page=100
    """
    try:
        # --- Authorization & points deduction ---
        if current_user.role == models.UserRole.GENERAL_USER:
            deduct_points_for_general_user(current_user, db)
            allowed = [
                p.provider_name
                for p in db.query(models.UserProviderPermission).filter_by(
                    user_id=current_user.id
                )
            ]
            if request.provider_name not in allowed:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail=f"No permission for supplier '{request.provider_name}'. Please contact your administrator.",
                )
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error processing user permissions: {str(e)}",
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
                id_exists = (
                    db.query(models.ProviderMapping)
                    .filter(
                        models.ProviderMapping.id == last_id,
                        models.ProviderMapping.provider_name == request.provider_name,
                    )
                    .first()
                )

                if not id_exists:
                    raise ValueError("Resume key references non-existent record")

            except ValueError as e:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Invalid resume_key: {str(e)}. Please use a valid resume_key from a previous response or omit it to start from the beginning.",
                )
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error processing resume key: {str(e)}",
        )

    try:
        # --- Single eager‐loaded query ---
        query = (
            db.query(models.ProviderMapping)
            .options(
                # load mapping → hotel → locations & contacts
                joinedload(models.ProviderMapping.hotel).joinedload(
                    models.Hotel.locations
                ),
                joinedload(models.ProviderMapping.hotel).joinedload(
                    models.Hotel.contacts
                ),
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
            detail=f"Error querying supplier hotel data: {str(e)}",
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
            {
                "id": m.id,
                "name": m.provider_name,
                "provider_id": m.provider_id,
                "status": "update",
            }
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

        result.append(
            {
                "ittid": hotel.ittid,
                "name": hotel.name,
                "country_name": (
                    location_list[0]["country_name"] if location_list else ""
                ),
                "country_code": (
                    location_list[0]["country_code"] if location_list else ""
                ),
                "type": "hotel",
                "provider": providers,
                "location": location_list,
                "contract": [contact],
            }
        )

    # --- Next resume_key generation ---
    if len(mappings) == limit_per_page:
        last_map_id = mappings[-1].id
        rand = "".join(
            secrets.choice(string.ascii_letters + string.digits) for _ in range(50)
        )
        next_resume = f"{last_map_id}_{rand}"
    else:
        next_resume = None

    return {
        "resume_key": next_resume,
        "total_hotel": total,
        "show_hotels_this_page": len(result),
        "hotel": result,
    }


@router.get("/get-update-provider-info")
def get_update_provider_info(
    request: Request,
    current_user: Annotated[models.User, Depends(get_current_user)],
    limit_per_page: int = Query(
        50, ge=1, le=500, description="Number of records per page"
    ),
    from_date: str = Query(..., description="Start date (YYYY-MM-DD)"),
    to_date: str = Query(..., description="End date (YYYY-MM-DD)"),
    resume_key: Optional[str] = Query(None, description="Resume key for pagination"),
    page: Optional[int] = Query(
        None, ge=1, description="Page number to jump to (overrides resume_key)"
    ),
    db: Session = Depends(get_db),
):
    print(f"🎯 get_update_provider_info function called for user: {current_user.id}")
    """
    Get Updated Provider Information by Date Range
    
    Retrieves provider mapping information that was updated within a specified date range.
    This endpoint is useful for tracking changes and updates to hotel-provider mappings.
    
    Features:
    - Date range filtering for updated records
    - Role-based access control (Super users see all, others see permitted providers)
    - Resume key pagination for large datasets
    - Direct page navigation with page parameter
    - Comprehensive provider mapping information
    
    Args:
        current_user: Currently authenticated user (injected by dependency)
        limit_per_page (int): Number of records per page (1-500, default 50)
        from_date (str): Start date in YYYY-MM-DD format (required)
        to_date (str): End date in YYYY-MM-DD format (required)
        resume_key (Optional[str]): Resume key for pagination continuation
        page (Optional[int]): Page number to jump to (overrides resume_key if provided)
        db (Session): Database session (injected by dependency)
    
    Returns:
        dict: Paginated provider mapping data including:
            - resume_key: Key for next page (null if last page)
            - total_hotel: Total mappings in date range
            - show_hotels_this_page: Number of mappings in current response
            - total_page: Total number of pages
            - current_page: Current page number
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
        
    Example Requests:
        GET /get-update-provider-info?from_date=2023-01-01&to_date=2023-12-31&limit_per_page=100
        GET /get-update-provider-info?from_date=2023-01-01&to_date=2023-12-31&limit_per_page=500&page=200
    """

    # 🔒 IP WHITELIST VALIDATION
    print(
        f"🚀 About to call IP whitelist check for user: {current_user.id} in get-update-provider-info"
    )
    if not check_ip_whitelist(current_user.id, request, db):
        # Extract client IP for error message using middleware
        client_ip = get_client_ip(request) or "unknown"

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
                    "message": "Your IP address is not in the whitelist. Please contact your administrator to add your IP address to the whitelist.",
                },
                "timestamp": datetime.utcnow().isoformat(),
            },
        )

    try:
        # Validate and parse dates
        try:
            from_dt = datetime.strptime(from_date, "%Y-%m-%d")
            to_dt = datetime.strptime(to_date, "%Y-%m-%d")

            # Validate date range
            if from_dt > to_dt:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="from_date cannot be later than to_date",
                )
        except ValueError:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid date format. Use YYYY-MM-DD format (e.g., '2023-01-01').",
            )

        # Super users see all, others see only their allowed providers (excluding temp deactivated)
        if current_user.role == UserRole.SUPER_USER:
            # For super users, check for temporarily deactivated suppliers
            all_permissions = [
                perm.provider_name
                for perm in db.query(UserProviderPermission)
                .filter(UserProviderPermission.user_id == current_user.id)
                .all()
            ]

            # Get temporarily deactivated suppliers
            temp_deactivated_suppliers = []
            for perm in all_permissions:
                if perm.startswith("TEMP_DEACTIVATED_"):
                    original_name = perm.replace("TEMP_DEACTIVATED_", "")
                    temp_deactivated_suppliers.append(original_name)

            # Super users see all providers except temporarily deactivated ones
            if temp_deactivated_suppliers:
                # Get all provider names and exclude temp deactivated ones
                all_provider_names = [
                    row.provider_name
                    for row in db.query(models.ProviderMapping.provider_name)
                    .distinct()
                    .all()
                ]
                allowed_providers = [
                    provider
                    for provider in all_provider_names
                    if provider not in temp_deactivated_suppliers
                ]
            else:
                allowed_providers = (
                    None  # No restrictions for super users with no temp deactivations
                )
        else:
            # Get all user permissions (including temp deactivated ones)
            all_permissions = [
                perm.provider_name
                for perm in db.query(UserProviderPermission)
                .filter(UserProviderPermission.user_id == current_user.id)
                .all()
            ]

            # Separate active and temporarily deactivated suppliers
            temp_deactivated_suppliers = []
            active_providers = []

            for perm in all_permissions:
                if perm.startswith("TEMP_DEACTIVATED_"):
                    original_name = perm.replace("TEMP_DEACTIVATED_", "")
                    temp_deactivated_suppliers.append(original_name)
                else:
                    active_providers.append(perm)

            # Remove temporarily deactivated suppliers from allowed providers
            allowed_providers = [
                provider
                for provider in active_providers
                if provider not in temp_deactivated_suppliers
            ]

            if not allowed_providers:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="You do not have permission to access any providers. Please contact your administrator.",
                )
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error processing date range or permissions: {str(e)}",
        )

    try:
        # Base query for filtering
        base_query = db.query(ProviderMapping).filter(
            ProviderMapping.updated_at >= from_dt, ProviderMapping.updated_at <= to_dt
        )

        if allowed_providers is not None:
            base_query = base_query.filter(
                ProviderMapping.provider_name.in_(allowed_providers)
            )

        # Count total BEFORE applying resume_key/pagination
        total = base_query.count()

        # Apply ordering
        base_query = base_query.order_by(ProviderMapping.id)

        # Handle pagination - page parameter takes precedence over resume_key
        current_page_num = 1
        if page is not None:
            # Direct page navigation
            current_page_num = page
            offset = (page - 1) * limit_per_page
            mappings = base_query.offset(offset).limit(limit_per_page).all()
        elif resume_key:
            # Resume key pagination
            try:
                parts = resume_key.split("_", 1)
                if len(parts) != 2:
                    raise ValueError("Invalid resume key format")
                last_id = int(parts[0])

                # Validate the mapping exists
                mapping_exists = (
                    db.query(ProviderMapping)
                    .filter(ProviderMapping.id == last_id)
                    .first()
                )
                if not mapping_exists:
                    raise ValueError("Resume key references non-existent record")

            except ValueError as e:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Invalid resume_key: {str(e)}. Please use a valid resume_key from a previous response.",
                )

            # Apply resume key filter and get results
            filtered_query = base_query.filter(ProviderMapping.id > last_id)
            mappings = filtered_query.limit(limit_per_page).all()

            # Calculate current page for resume key
            records_before = db.query(ProviderMapping).filter(
                ProviderMapping.updated_at >= from_dt,
                ProviderMapping.updated_at <= to_dt,
                ProviderMapping.id <= last_id,
            )
            if allowed_providers is not None:
                records_before = records_before.filter(
                    ProviderMapping.provider_name.in_(allowed_providers)
                )

            records_before_count = records_before.count()
            current_page_num = (records_before_count // limit_per_page) + 1
        else:
            # First page (no resume_key, no page)
            mappings = base_query.limit(limit_per_page).all()

        # Prepare next resume_key (random string + last id)
        if mappings and len(mappings) == limit_per_page:
            last_hotel_id = mappings[-1].id
            rand_str = "".join(
                secrets.choice(string.ascii_letters + string.digits) for _ in range(50)
            )
            next_resume_key = f"{last_hotel_id}_{rand_str}"
        else:
            next_resume_key = None

        result = [
            {
                "ittid": m.ittid,
                "provider_name": m.provider_name,
                "provider_id": m.provider_id,
            }
            for m in mappings
        ]

        # Calculate pagination info
        import math

        total_pages = math.ceil(total / limit_per_page) if total > 0 else 1

        return {
            "resume_key": next_resume_key,
            "total_hotel": total,
            "show_hotels_this_page": len(result),
            "total_page": total_pages,
            "current_page": current_page_num,
            "provider_mappings": result,
        }

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error processing provider update information: {str(e)}",
        )


class HotelNameRequest(BaseModel):
    hotel_name: str


# Cache for hotel data - dictionary with lowercase name as key
_hotel_data_cache = None


def _load_hotel_data_cache():
    """Load all hotel data into memory cache for fast lookup by name"""
    global _hotel_data_cache
    if _hotel_data_cache is not None:
        return _hotel_data_cache

    csv_path = "static/hotelcontent/itt_hotel_basic_info.csv"
    hotel_dict = {}

    try:
        with open(csv_path, newline="", encoding="utf-8") as csvfile:
            reader = csv.DictReader(csvfile)
            for row in reader:
                if row.get("Name"):
                    name_key = row["Name"].strip().lower()
                    hotel_dict[name_key] = {
                        "ittid": row.get("ittid", ""),
                        "name": row.get("Name", ""),
                        "addressline1": row.get("AddressLine1", ""),
                        "addressline2": row.get("AddressLine2", ""),
                        "city": row.get("CityName", ""),
                        "country": row.get("CountryName", ""),
                        "countrycode": row.get("CountryCode", ""),
                        "latitude": row.get("Latitude", ""),
                        "longitude": row.get("Longitude", ""),
                        "postalcode": row.get("PostalCode", ""),
                        "chainname": row.get("ChainName", ""),
                        "propertytype": row.get("PropertyType", ""),
                    }

        _hotel_data_cache = hotel_dict
        return hotel_dict
    except Exception:
        return {}


@router.post("/search-with-hotel-name", status_code=status.HTTP_200_OK)
def search_hotel_with_name(
    request: HotelNameRequest = Body(...),
):
    """
    Search Hotel by Exact Name Match (Optimized)

    Ultra-fast hotel search using in-memory cache with O(1) lookup time.
    Performs case-insensitive exact matching with instant results.

    Features:
    - In-memory cached hotel data for instant lookup
    - O(1) dictionary lookup (constant time)
    - Case-insensitive exact name matching
    - Comprehensive hotel information

    Args:
        request (HotelNameRequest): Request containing the exact hotel name

    Returns:
        dict: Complete hotel information including location, chain, and property details

    Performance:
        - First request: ~100-200ms (loads cache)
        - Subsequent requests: <5ms (O(1) dictionary lookup)

    Example Request:
        {
            "hotel_name": "Grand Hotel Example"
        }

    Example Response:
        {
            "ittid": "ITT123456",
            "name": "Grand Hotel Example",
            "addressline1": "123 Main Street",
            "addressline2": "Street",
            "city": "Example City",
            "country": "Example Country",
            "countrycode": "BA",
            "latitude": "40.7128",
            "longitude": "-74.0060",
            "chainname": "Example Chain",
            "propertytype": "Hotel"
        }
    """
    try:
        # Validate input
        if not request.hotel_name or not request.hotel_name.strip():
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Hotel name cannot be empty",
            )

        # Load cache if not already loaded
        hotel_data = _load_hotel_data_cache()

        if not hotel_data:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Hotel database not available",
            )

        # O(1) dictionary lookup
        search_name = request.hotel_name.strip().lower()
        hotel = hotel_data.get(search_name)

        if not hotel:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Hotel with name '{request.hotel_name}' not found in database",
            )

        return hotel

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Unexpected error during hotel search: {str(e)}",
        )


# Cache for hotel names - loaded once at startup
_hotel_names_cache = None
_cache_lock = None


def _load_hotel_names_cache():
    """Load hotel names into memory cache for fast autocomplete"""
    global _hotel_names_cache
    if _hotel_names_cache is not None:
        return _hotel_names_cache

    csv_path = "static/hotelcontent/itt_hotel_basic_info.csv"
    hotel_names = []

    try:
        with open(csv_path, newline="", encoding="utf-8") as csvfile:
            reader = csv.DictReader(csvfile)
            for row in reader:
                if row.get("Name"):
                    name = row["Name"].strip()
                    if name:
                        hotel_names.append(name)

        # Sort for better user experience
        hotel_names.sort()
        _hotel_names_cache = hotel_names
        return hotel_names
    except Exception:
        return []


# Global cache for detailed hotel data
_hotel_details_cache = None


def _load_hotel_details_cache():
    """Load detailed hotel data into memory cache for autocomplete-all"""
    global _hotel_details_cache
    if _hotel_details_cache is not None:
        return _hotel_details_cache

    csv_path = "static/hotelcontent/itt_hotel_basic_info.csv"
    hotel_data = []

    try:
        with open(csv_path, newline="", encoding="utf-8") as csvfile:
            reader = csv.DictReader(csvfile)
            for row in reader:
                if row.get("Name"):
                    hotel_info = {
                        "name": row["Name"].strip(),
                        "address": row.get("AddressLine1", "").strip(),
                        "city": row.get("CityName", "").strip(),
                        "country": row.get("CountryName", "").strip(),
                        "country_code": row.get("CountryCode", "").strip(),
                        "latitude": row.get("Latitude", "").strip(),
                        "longitude": row.get("Longitude", "").strip(),
                    }
                    if hotel_info["name"]:
                        hotel_data.append(hotel_info)

        # Sort by name for better user experience
        hotel_data.sort(key=lambda x: x["name"])
        _hotel_details_cache = hotel_data
        return hotel_data
    except Exception:
        return []


@router.get("/autocomplete", status_code=status.HTTP_200_OK)
def autocomplete_hotel_name(
    query: str = Query(..., description="Partial hotel name", min_length=2)
):
    """
    Hotel Name Autocomplete Search (Optimized)

    Ultra-fast autocomplete suggestions using in-memory cache. Provides instant results
    for hotel name searches with minimal latency.

    Features:
    - In-memory cached hotel names for instant lookup
    - Case-insensitive prefix matching
    - Sorted results for better UX
    - Limited results (max 20) for performance

    Args:
        query (str): Partial hotel name to search for (min 1 character)

    Returns:
        dict: Autocomplete results containing:
            - results: List of matching hotel names (max 20 results)
            - count: Number of results returned

    Performance:
        - First request: ~100-200ms (loads cache)
        - Subsequent requests: <10ms (uses cache)

    Example Request:
        GET /autocomplete?query=Grand

    Example Response:
        {
            "results": ["Grand Hotel Central", "Grand Palace Hotel"],
            "count": 2
        }
    """
    try:
        # Validate input
        query = query.strip()
        if not query:
            return {"results": [], "count": 0}

        # Load cache if not already loaded
        hotel_names = _load_hotel_names_cache()

        if not hotel_names:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Hotel database not available",
            )

        # Fast search using list comprehension
        search_query = query.lower()
        suggestions = [
            name for name in hotel_names if name.lower().startswith(search_query)
        ][
            :20
        ]  # Limit to 20 results

        return {"results": suggestions, "count": len(suggestions)}

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Autocomplete error: {str(e)}",
        )


@router.get("/autocomplete-all", status_code=status.HTTP_200_OK)
def autocomplete_hotel_all(
    query: str = Query(
        ...,
        description="Search query for hotel name, address, city, or country",
        min_length=2,
    ),
    fuzzy: bool = Query(
        False, description="Enable fuzzy matching for more flexible search"
    ),
):
    """
    Hotel Autocomplete Search with Full Details (Optimized with Fuzzy Matching)

    Ultra-fast autocomplete suggestions with complete hotel information.
    Searches across Name, AddressLine1, CityName, and CountryName fields.

    Features:
    - In-memory cached hotel data for instant lookup
    - Case-insensitive matching across multiple fields
    - Optional fuzzy matching for typo-tolerant search
    - Returns complete hotel details (name, city, country, coordinates, etc.)
    - Limited results (max 20) for performance
    - Sorted by relevance score when fuzzy matching is enabled

    Args:
        query (str): Search query to match against hotel name, address, city, or country (min 2 characters)
        fuzzy (bool): Enable fuzzy matching (default: False). When enabled, finds results even with typos or partial matches

    Returns:
        dict: Autocomplete results containing:
            - results: List of matching hotels with full details (max 20 results)
            - count: Number of results returned
            - fuzzy_enabled: Whether fuzzy matching was used

    Performance:
        - First request: ~100-200ms (loads cache)
        - Subsequent requests: <10ms (exact match), <50ms (fuzzy match)

    Example Request:
        GET /autocomplete-all?query=Grand&fuzzy=true

    Example Response:
        {
            "results": [
                {
                    "name": "Grand Hotel Central",
                    "country_code": "ES",
                    "longitude": "2.1734",
                    "latitude": "41.3851",
                    "city": "Barcelona",
                    "country": "Spain",
                    "score": 95.5
                }
            ],
            "count": 1,
            "fuzzy_enabled": true
        }
    """
    try:
        # Validate input
        query = query.strip()
        if not query:
            return {"results": [], "count": 0, "fuzzy_enabled": fuzzy}

        # Load cache if not already loaded
        hotel_data = _load_hotel_details_cache()

        if not hotel_data:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Hotel database not available",
            )

        search_query = query.lower()
        suggestions = []

        if fuzzy:
            # Optimized fuzzy matching - use rapidfuzz's fast extractors
            # Create searchable strings for each hotel (name is most important, then city)
            hotel_search_strings = []
            for hotel in hotel_data:
                # Prioritize name and city for faster, more relevant matches
                search_str = f"{hotel['name']} {hotel['city']} {hotel['country']}"
                hotel_search_strings.append((search_str, hotel))

            # Use rapidfuzz's optimized process.extract (much faster than manual loop)
            # It uses C++ implementation under the hood
            matches = process.extract(
                search_query,
                [item[0] for item in hotel_search_strings],
                scorer=fuzz.partial_ratio,
                limit=20,
                score_cutoff=70,
            )

            # Format results with hotel data
            for match_text, score, idx in matches:
                hotel = hotel_search_strings[idx][1]
                suggestions.append(
                    {
                        "name": hotel["name"],
                        "country_code": hotel["country_code"],
                        "longitude": hotel["longitude"],
                        "latitude": hotel["latitude"],
                        "city": hotel["city"],
                        "country": hotel["country"],
                        "score": round(score, 1),
                    }
                )
        else:
            # Exact substring matching mode (original behavior)
            for hotel in hotel_data:
                # Check if query matches any of the fields
                if (
                    search_query in hotel["name"].lower()
                    or search_query in hotel["address"].lower()
                    or search_query in hotel["city"].lower()
                    or search_query in hotel["country"].lower()
                ):

                    suggestions.append(
                        {
                            "name": hotel["name"],
                            "country_code": hotel["country_code"],
                            "longitude": hotel["longitude"],
                            "latitude": hotel["latitude"],
                            "city": hotel["city"],
                            "country": hotel["country"],
                        }
                    )

                    # Limit to 20 results for performance
                    if len(suggestions) >= 20:
                        break

        return {
            "results": suggestions,
            "count": len(suggestions),
            "fuzzy_enabled": fuzzy,
        }

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Autocomplete error: {str(e)}",
        )


class SupplierHotelRequest(BaseModel):
    supplier_name: List[str]


@router.post("/get-all-hotel-basic-info-with-supplier", status_code=status.HTTP_200_OK)
def get_all_hotel_with_supplier(
    http_request: Request,
    request: SupplierHotelRequest,
    current_user: Annotated[models.User, Depends(get_current_user)],
    limit_per_page: int = Query(
        50, ge=1, le=500, description="Number of records per page"
    ),
    resume_key: Optional[str] = Query(None, description="Resume key for pagination"),
    page: Optional[int] = Query(
        None, ge=1, description="Page number to jump to (overrides resume_key)"
    ),
    db: Session = Depends(get_db),
):
    """
    Get Hotels by Supplier

    Retrieves paginated hotel data for specified suppliers with provider mappings.
    Ultra-fast performance with role-based access control.

    Request Body:
    - supplier_name: List of supplier names (required)

    Query Parameters:
    - limit_per_page: Records per page (1-500, default 50)
    - resume_key: Pagination continuation key
    - page: Direct page navigation (overrides resume_key)

    Access Control:
    - Super/Admin: All suppliers (except temp deactivated)
    - General users: Only permitted suppliers

    Returns:
    - Paginated hotel list with geocoding and provider mappings
    - Pagination metadata (total, current page, resume key)
    - Supplier analytics and counts
    """

    # 🔒 IP WHITELIST VALIDATION
    print(
        f"🚀 About to call IP whitelist check for user: {current_user.id} in get-hotel-with-ittid"
    )
    if not check_ip_whitelist(current_user.id, http_request, db):
        # Extract client IP for error message using middleware
        client_ip = get_client_ip(http_request) or "unknown"

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
                    "message": "Your IP address is not in the whitelist. Please contact your administrator to add your IP address to the whitelist.",
                },
                "timestamp": datetime.utcnow().isoformat(),
            },
        )

    try:
        # Validate request
        if not request.supplier_name:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="At least one supplier name is required",
            )

        # ULTRA-FAST PERMISSION CHECK - Single query with set operations
        if current_user.role not in [UserRole.SUPER_USER, UserRole.ADMIN_USER]:
            # Single query to get all permissions as a set for O(1) lookups
            permission_names = {
                perm[0]
                for perm in db.query(UserProviderPermission.provider_name)
                .filter(UserProviderPermission.user_id == current_user.id)
                .all()
            }

            if not permission_names:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="You do not have permission to access any suppliers.",
                )

            # Fast set operations for temp deactivated suppliers
            temp_deactivated = {
                name.replace("TEMP_DEACTIVATED_", "")
                for name in permission_names
                if name.startswith("TEMP_DEACTIVATED_")
            }
            active_suppliers = {
                name
                for name in permission_names
                if not name.startswith("TEMP_DEACTIVATED_")
            }
            final_active = active_suppliers - temp_deactivated

            # Fast set intersection checks
            requested_set = set(request.supplier_name)
            unauthorized = requested_set - final_active
            temp_deactivated_requested = requested_set & temp_deactivated

            if unauthorized:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail=f"No permission for: {', '.join(unauthorized)}",
                )

            if temp_deactivated_requested:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail=f"Temporarily deactivated: {', '.join(temp_deactivated_requested)}",
                )

            allowed_suppliers = list(final_active & requested_set)
        else:
            # Super/admin users - only check temp deactivations
            temp_deactivated = {
                perm[0].replace("TEMP_DEACTIVATED_", "")
                for perm in db.query(UserProviderPermission.provider_name)
                .filter(
                    UserProviderPermission.user_id == current_user.id,
                    UserProviderPermission.provider_name.like("TEMP_DEACTIVATED_%"),
                )
                .all()
            }

            temp_deactivated_requested = set(request.supplier_name) & temp_deactivated
            if temp_deactivated_requested:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail=f"Temporarily deactivated: {', '.join(temp_deactivated_requested)}",
                )

            allowed_suppliers = request.supplier_name

        # ULTRA-FAST: Direct query with minimal data transfer
        # Use tuple unpacking for faster iteration
        ittid_results = (
            db.query(models.ProviderMapping.ittid)
            .filter(models.ProviderMapping.provider_name.in_(allowed_suppliers))
            .all()
        )

        # Lightning-fast deduplication with set comprehension
        unique_ittids = list({ittid for ittid, in ittid_results})

        if not unique_ittids:
            # No hotels found - return empty result immediately
            return {
                "resume_key": None,
                "total_hotel": 0,
                "total_supplier": len(request.supplier_name),
                "supplier_name": request.supplier_name,
                "show_hotels_this_page": 0,
                "total_page": 1,
                "current_page": 1,
                "hotels": [],
            }

        # Direct query with IN clause - much faster than subquery
        base_query = (
            db.query(models.Hotel)
            .filter(models.Hotel.ittid.in_(unique_ittids))
            .order_by(models.Hotel.id)
        )

        # INSTANT COUNT: We already know the count from unique_ittids
        total = len(unique_ittids)

        # Handle pagination efficiently
        current_page_num = 1
        if page is not None:
            # Direct page navigation
            current_page_num = page
            offset = (page - 1) * limit_per_page
            hotels = base_query.offset(offset).limit(limit_per_page).all()
        elif resume_key:
            # Resume key pagination
            try:
                parts = resume_key.split("_", 1)
                if len(parts) != 2:
                    raise ValueError("Invalid resume key format")
                last_id = int(parts[0])

            except ValueError as e:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Invalid resume_key: {str(e)}",
                )

            # Apply resume key filter
            hotels = (
                base_query.filter(models.Hotel.id > last_id).limit(limit_per_page).all()
            )

            # Simplified current page calculation
            current_page_num = (
                1  # For resume key, we don't need exact page calculation for speed
            )
        else:
            # First page
            hotels = base_query.limit(limit_per_page).all()

        # Prepare next resume_key
        if hotels and len(hotels) == limit_per_page:
            last_hotel_id = hotels[-1].id
            rand_str = "".join(
                secrets.choice(string.ascii_letters + string.digits) for _ in range(50)
            )
            next_resume_key = f"{last_hotel_id}_{rand_str}"
        else:
            next_resume_key = None

        # ULTRA-FAST: Get mappings with minimal data transfer
        hotel_ittids = [hotel.ittid for hotel in hotels]
        if hotel_ittids:
            # Only select needed columns to reduce data transfer
            all_mappings = (
                db.query(
                    models.ProviderMapping.ittid,
                    models.ProviderMapping.provider_name,
                    models.ProviderMapping.provider_id,
                    models.ProviderMapping.created_at,
                    models.ProviderMapping.updated_at,
                )
                .filter(
                    models.ProviderMapping.ittid.in_(hotel_ittids),
                    models.ProviderMapping.provider_name.in_(allowed_suppliers),
                )
                .all()
            )

            # Ultra-fast grouping with defaultdict
            from collections import defaultdict

            mappings_by_ittid = defaultdict(list)

            for mapping in all_mappings:
                mappings_by_ittid[mapping.ittid].append(
                    {
                        "provider_name": mapping.provider_name,
                        "provider_id": mapping.provider_id,
                        "created_at": (
                            mapping.created_at.isoformat()
                            if mapping.created_at
                            else None
                        ),
                        "updated_at": (
                            mapping.updated_at.isoformat()
                            if mapping.updated_at
                            else None
                        ),
                    }
                )
        else:
            mappings_by_ittid = {}

        # ULTRA-FAST: List comprehension with minimal attribute access
        hotel_results = [
            {
                "ittid": hotel.ittid,
                "name": hotel.name or "",
                "property_type": hotel.property_type or "",
                "rating": hotel.rating or "",
                "address_line1": hotel.address_line1 or "",
                "address_line2": hotel.address_line2 or "",
                "postal_code": hotel.postal_code or "",
                "map_status": getattr(hotel, "map_status", "pending"),
                "geocode": {
                    "latitude": hotel.latitude or "",
                    "longitude": hotel.longitude or "",
                },
                "mapping_info": mappings_by_ittid.get(hotel.ittid, []),
            }
            for hotel in hotels
        ]

        # Calculate pagination info
        import math

        total_pages = math.ceil(total / limit_per_page) if total > 0 else 1

        return {
            "resume_key": next_resume_key,
            "total_hotel": total,
            "total_supplier": len(request.supplier_name),
            "supplier_name": request.supplier_name,
            "show_hotels_this_page": len(hotel_results),
            "total_page": total_pages,
            "current_page": current_page_num,
            "hotels": hotel_results,
        }

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error retrieving hotel data: {str(e)}",
        )
