from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from database import get_db
from schemas import HotelCreateDemo, HotelReadDemo
from typing import Annotated, Optional, Dict, List
import models
from datetime import datetime
from utils import require_role
from models import User, Hotel, ProviderMapping
from routes.auth import get_current_user
import os
import json
from routes.path import RAW_BASE_DIR
from routes.hotelFormattingData import map_to_our_format
from pydantic import BaseModel


def serialize_datetime_objects(obj):
    """Convert datetime objects to ISO format strings for JSON serialization."""
    if hasattr(obj, "__dict__"):
        result = {}
        for key, value in obj.__dict__.items():
            if key.startswith("_"):
                continue
            if isinstance(value, datetime):
                result[key] = value.isoformat() if value else None
            else:
                result[key] = value
        return result
    return obj


router = APIRouter(
    prefix="/v1.0/demo",
    tags=["Hotels Demo"],
    responses={404: {"description": "Not found"}},
)


# Check active suppliers - demo version (shows first 3 suppliers only)
@router.get("/check-active-my-supplier")
def check_active_my_supplier_demo(
    current_user: Annotated[models.User, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
):
    """
    Check My Active Suppliers (Demo Version)

    Returns first 3 suppliers from the system regardless of user permissions.
    This is a demo endpoint to showcase the supplier management functionality.

    Returns:
    - active_supplier: Total suppliers (always 3 for demo)
    - total_on_supplier: Currently active suppliers count (3)
    - total_off_supplier: Temporarily deactivated suppliers count (0)
    - off_supplier_list: List of turned off supplier names (empty)
    - on_supplier_list: List of active supplier names (first 3 from system)

    Demo Restrictions:
    - Always shows first 3 suppliers from the system
    - Ignores user permissions (demo mode)
    - Works for all authenticated users
    """
    try:
        # DEMO MODE: Get first 3 suppliers from the system regardless of user permissions
        all_system_suppliers = [
            row.provider_name
            for row in db.query(models.ProviderMapping.provider_name)
            .distinct()
            .limit(3)
            .all()
        ]

        if not all_system_suppliers:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="No suppliers found in the system.",
            )

        # Sort suppliers alphabetically
        demo_suppliers = sorted(all_system_suppliers)

        # For demo, all suppliers are active (no deactivated ones)
        return {
            "active_supplier": len(demo_suppliers),
            "total_on_supplier": len(demo_suppliers),
            "total_off_supplier": 0,
            "off_supplier_list": [],
            "on_supplier_list": demo_suppliers,
        }

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"An error occurred while retrieving supplier statistics: {str(e)}",
        )


# Pydantic models for the mapping endpoint
class ProviderHotelIdentity(BaseModel):
    provider_id: str
    provider_name: str


class ProviderHotelRequest(BaseModel):
    provider_hotel_identity: List[ProviderHotelIdentity]


# Get hotel mapping info - demo version
@router.post(
    "/content/get-hotel-mapping-info-using-provider-name-and-id",
    status_code=status.HTTP_200_OK,
)
def get_hotel_mapping_data_demo(
    request: ProviderHotelRequest,
    current_user: Annotated[models.User, Depends(get_current_user)],
    db: Session = Depends(get_db),
):
    """
    Get Hotel Mapping Data by Provider Name and ID (Demo Version)

    Retrieves provider mapping information for hotels based on provider name and ID combinations.
    Demo restrictions apply: only works with demo hotel IDs and demo suppliers.

    Demo Restrictions:
    - Only works with hotels from the demo list (offset 354125, limit 100)
    - Only works with first 3 suppliers from the system
    - No point deduction
    - No IP whitelist check

    Args:
        request (ProviderHotelRequest): Request containing list of provider identities
        current_user: Currently authenticated user (injected by dependency)
        db (Session): Database session (injected by dependency)

    Returns:
        List[dict]: List of provider mapping data with ITTID and creation timestamps

    Example Request:
        {
            "provider_hotel_identity": [
                {
                    "provider_name": "booking",
                    "provider_id": "12345"
                }
            ]
        }
    """
    try:
        # Get demo hotel IDs (first 100 from offset 354125)
        demo_hotels = db.query(models.Hotel.ittid).offset(354125).limit(100).all()
        allowed_hotel_ids = [hotel.ittid for hotel in demo_hotels]

        # Get demo suppliers (first 3 from system)
        demo_suppliers_query = (
            db.query(models.ProviderMapping.provider_name).distinct().limit(3).all()
        )
        allowed_suppliers = sorted([row.provider_name for row in demo_suppliers_query])

        if not allowed_suppliers:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="No suppliers found in the system.",
            )

        result = []
        for identity in request.provider_hotel_identity:
            name = identity.provider_name
            pid = identity.provider_id

            # Check if supplier is in demo list
            if name not in allowed_suppliers:
                print(
                    f"Supplier '{name}' not in demo list. Allowed: {allowed_suppliers}"
                )
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

            # Check if hotel is in demo list
            if mapping.ittid not in allowed_hotel_ids:
                print(f"Hotel '{mapping.ittid}' not in demo list")
                continue

            # Verify hotel exists
            hotel = db.query(Hotel).filter(Hotel.ittid == mapping.ittid).first()
            if not hotel:
                print(f"No hotel found for ittid={mapping.ittid}")
                continue

            # Build provider_mappings list
            provider_mappings_list = [
                {
                    "ittid": hotel.ittid,
                    "provider_mapping_id": mapping.id,
                    "provider_id": mapping.provider_id,
                    "provider_name": mapping.provider_name,
                    "created_at": (
                        mapping.created_at.isoformat() if mapping.created_at else None
                    ),
                }
            ]

            result.append({"provider_mappings": provider_mappings_list})

        if not result:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Cannot find mapping for any of the requested suppliers in our demo system. Please ensure you're using demo hotel IDs and demo suppliers.",
            )

        return result

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error processing mapping data request: {str(e)}",
        )


# Get full hotel with ITT mapping ID - demo version
@router.get(
    "/content/get-full-hotel-with-itt-mapping-id/{ittid}",
    status_code=status.HTTP_200_OK,
)
async def get_full_hotel_with_itt_mapping_id_demo(
    ittid: str,
    current_user: Annotated[models.User, Depends(get_current_user)],
    db: Session = Depends(get_db),
):
    """
    Get Full Hotel Details with ITT Mapping ID (Demo Version)

    Retrieves comprehensive hotel information with provider mappings that have primary photos.
    Demo restrictions apply: only works with demo hotel IDs and demo suppliers.

    Demo Restrictions:
    - Only works with hotels from the demo list (offset 354125, limit 100)
    - Only shows first 3 suppliers from the system
    - Limits to first 5 provider mappings per hotel
    - Only includes providers with primary_photo in full_details
    - No point deduction
    - No IP whitelist check

    Args:
        ittid (str): The ITT hotel identifier
        current_user: Currently authenticated user (injected by dependency)
        db (Session): Database session (injected by dependency)

    Returns:
        dict: Hotel data with filtered provider mappings including:
            - total_supplier: Count of demo suppliers
            - have_provider_list: List of available provider names with IDs
            - give_data_supplier: Count of providers that returned data
            - give_data_supplier_list: List of provider names that returned data
            - hotel: Basic hotel information
            - provider_mappings: Only providers with primary_photo in full_details
            - locations: Hotel location information
            - contacts: Hotel contact information
    """
    try:
        # Get demo hotel IDs (first 100 from offset 354125)
        demo_hotels = db.query(models.Hotel.ittid).offset(354125).limit(100).all()
        allowed_hotel_ids = [hotel.ittid for hotel in demo_hotels]

        # Check if requested hotel is in demo list
        if ittid not in allowed_hotel_ids:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Access denied. This hotel ID is not available in the demo. Only the first 100 hotels are accessible.",
            )

        # Get hotel
        hotel = db.query(models.Hotel).filter(models.Hotel.ittid == ittid).first()
        if not hotel:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Hotel with id '{ittid}' not found.",
            )

        # Get all provider mappings for this hotel
        all_provider_mappings = (
            db.query(models.ProviderMapping)
            .filter(models.ProviderMapping.ittid == ittid)
            .all()
        )

        if not all_provider_mappings:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"No supplier mappings found for hotel '{ittid}'",
            )

        # Get demo suppliers (first 3 from system)
        demo_suppliers_query = (
            db.query(models.ProviderMapping.provider_name).distinct().limit(3).all()
        )
        allowed_suppliers = sorted([row.provider_name for row in demo_suppliers_query])

        if not allowed_suppliers:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="No suppliers found in the system.",
            )

        # Filter provider mappings to only demo suppliers
        provider_mappings = [
            pm for pm in all_provider_mappings if pm.provider_name in allowed_suppliers
        ][
            :5
        ]  # Limit to first 5

        if not provider_mappings:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"No demo suppliers available for this hotel. Available demo suppliers: {', '.join(allowed_suppliers)}",
            )

        # Get related data
        locations = (
            db.query(models.Location).filter(models.Location.ittid == hotel.ittid).all()
        )
        contacts = (
            db.query(models.Contact).filter(models.Contact.ittid == hotel.ittid).all()
        )

        # Build have_provider_list with provider IDs grouped by provider name
        have_provider_dict = {}
        for pm in provider_mappings:
            provider_name = str(pm.provider_name) if pm.provider_name else "unknown"
            provider_id = str(pm.provider_id) if pm.provider_id else "unknown"

            if provider_name not in have_provider_dict:
                have_provider_dict[provider_name] = []
            have_provider_dict[provider_name].append(provider_id)

        # Convert to list of dicts format
        have_provider_list = [
            {provider: ids} for provider, ids in sorted(have_provider_dict.items())
        ]

        # Enhanced provider mappings with full details
        enhanced_provider_mappings = []
        give_data_supplier_list = []

        for pm in provider_mappings:
            # Get hotel details from raw data files
            hotel_details = await get_hotel_details_internal_demo(
                supplier_code=pm.provider_name, hotel_id=pm.provider_id
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

        # Serialize the response - same format as get-full-hotel-with-itt-mapping-id
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

        return response_data

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error processing hotel data request: {str(e)}",
        )


# Read hotels list - returns first 100 hotel IDs
@router.get("/hotel/get-all-demo-id")
async def read_hotels(db: Session = Depends(get_db)):
    """
    Get the first 100 hotel IDs from the demo hotels table.
    This endpoint is accessible to everyone.
    """
    try:
        # Query the first 50 hotel IDs from DemoHotel table
        hotels = (
            db.query(models.Hotel.ittid)
            .offset(354125)  # skip first 354125 rows
            .limit(100)  # then take next 100 rows
            .all()
        )

        # Extract just the ittid values from the query result
        hotel_ids = [hotel.ittid for hotel in hotels]

        return {"status": "success", "count": len(hotel_ids), "hotel_ids": hotel_ids}

    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error retrieving hotel IDs: {str(e)}",
        )


# Get hotel details by ID - only for first 100 hotels (requires login)
@router.get("/hotel/{hotel_id}")
async def get_hotel_details(
    hotel_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Get detailed information for a specific hotel by ID.
    Only works for the first 100 hotels in the demo database.
    Returns same format as /v1.0/content/get-full-hotel-with-itt-mapping-id/{ittid}
    but with demo permission rules applied.
    """
    try:
        # First, get the first 100 hotel IDs to check if the requested ID is allowed
        only_100_hotels = db.query(models.Hotel.ittid).offset(354125).limit(100).all()
        allowed_hotel_ids = [hotel.ittid for hotel in only_100_hotels]

        # Check if the requested hotel_id is in the demo 100
        if hotel_id not in allowed_hotel_ids:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Access denied. This hotel ID is not available in the demo. Only the first 100 hotels are accessible.",
            )

        # Query the hotel details with all related data
        hotel = db.query(models.Hotel).filter(models.Hotel.ittid == hotel_id).first()

        if not hotel:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail="Hotel not found"
            )

        # Get all provider mappings for this hotel
        all_provider_mappings = (
            db.query(models.ProviderMapping)
            .filter(models.ProviderMapping.ittid == hotel_id)
            .all()
        )

        if not all_provider_mappings:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"No supplier mappings found for hotel '{hotel_id}'",
            )

        # For demo, limit to first 5 provider mappings
        provider_mappings = all_provider_mappings[:5]

        # Get locations for this hotel
        locations = (
            db.query(models.Location).filter(models.Location.ittid == hotel_id).all()
        )

        # Get contacts for this hotel
        contacts = (
            db.query(models.Contact).filter(models.Contact.ittid == hotel_id).all()
        )

        # Build have_provider_list with provider IDs grouped by provider name
        have_provider_dict = {}
        for pm in provider_mappings:
            provider_name = str(pm.provider_name) if pm.provider_name else "unknown"
            provider_id = str(pm.provider_id) if pm.provider_id else "unknown"

            if provider_name not in have_provider_dict:
                have_provider_dict[provider_name] = []
            have_provider_dict[provider_name].append(provider_id)

        # Convert to list of dicts format
        have_provider_list = [
            {provider: ids} for provider, ids in sorted(have_provider_dict.items())
        ]

        # Enhanced provider mappings with full details
        enhanced_provider_mappings = []
        give_data_supplier_list = []

        for pm in provider_mappings:
            # Get hotel details from raw data files
            hotel_details = await get_hotel_details_internal_demo(
                supplier_code=pm.provider_name, hotel_id=pm.provider_id
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

        # Serialize the response - same format as get-full-hotel-with-itt-mapping-id
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

        return response_data

    except HTTPException:
        # Re-raise HTTP exceptions (like 403, 404)
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error retrieving hotel details: {str(e)}",
        )


async def get_hotel_details_internal_demo(
    supplier_code: str, hotel_id: str
) -> Optional[Dict]:
    """
    Internal function to get hotel details for demo endpoint.
    No permission checks - demo endpoint handles access control.
    """
    try:
        # Get the raw data file path
        file_path = os.path.join(RAW_BASE_DIR, supplier_code, f"{hotel_id}.json")

        # Load and process the hotel data
        if os.path.exists(file_path):
            with open(file_path, "r", encoding="utf-8") as f:
                content = json.load(f)

            # Format the data
            formatted_data = map_to_our_format(supplier_code, content)
            return formatted_data
        else:
            return None

    except Exception as e:
        print(f"Error getting hotel details for {supplier_code}/{hotel_id}: {str(e)}")
        return None
