from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from database import get_db
from schemas import HotelCreateDemo, HotelReadDemo
from typing import Annotated, Optional, Dict
import models
from datetime import datetime
from utils import require_role
from models import User
from routes.auth import get_current_user
import os
import json
from routes.path import RAW_BASE_DIR
from routes.hotelFormattingData import map_to_our_format


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
    prefix="/v1.0/demo/hotel",
    tags=["Hotels Demo"],
    responses={404: {"description": "Not found"}},
)


# Read hotels list - returns first 50 hotel IDs
@router.get("/get-all-demo-id")
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


# Get hotel details by ID - only for first 50 hotels (requires login)
@router.get("/{hotel_id}")
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
