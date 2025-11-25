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

        return {
            "status": "success",
            "count": len(hotel_ids),
            "hotel_ids": hotel_ids
        }

    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error retrieving hotel IDs: {str(e)}"
        )

# Get hotel details by ID - only for first 50 hotels (requires login)
@router.get("/{hotel_id}")
async def get_hotel_details(
    hotel_id: str, 
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Get detailed information for a specific hotel by ID.
    Only works for the first 100 hotels in the demo database.
    """
    try:
        # First, get the first 100 hotel IDs to check if the requested ID is allowed
        only_100_hotels = db.query(models.Hotel.ittid).offset(354125).limit(100).all()
        allowed_hotel_ids = [hotel.ittid for hotel in only_100_hotels]

        # Check if the requested hotel_id is in the for demo 100.
        if hotel_id not in allowed_hotel_ids:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Access denied. This hotel ID is not available in the demo. Only the first 50 hotels are accessible."
            )

        # Query the hotel details with all related data
        hotel = db.query(models.Hotel).filter(models.Hotel.ittid == hotel_id).first()

        if not hotel:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Hotel not found"
            )

        # Get all provider mappings for this hotel
        all_provider_mappings = db.query(models.ProviderMapping).filter(
            models.ProviderMapping.ittid == hotel_id
        ).all()

        # For demo, limit to first 5 provider mappings
        provider_mappings = all_provider_mappings[:5]

        # Get locations for this hotel
        locations = db.query(models.Location).filter(
            models.Location.ittid == hotel_id
        ).all()

        # Get contacts for this hotel
        contacts = db.query(models.Contact).filter(
            models.Contact.ittid == hotel_id
        ).all()

        # Get chains for this hotel
        chains = db.query(models.Chain).filter(
            models.Chain.ittid == hotel_id
        ).all()

        # Create enhanced provider mappings with additional info
        enhanced_provider_mappings = []
        for pm in provider_mappings:
            enhanced_pm = serialize_datetime_objects(pm)
            enhanced_pm['status'] = 'active'  # Demo status
            enhanced_provider_mappings.append(enhanced_pm)

        # Serialize the response with enhanced provider mappings
        response_data = {
            "total_supplier": len(provider_mappings),
            "provider_list": [pm.provider_name for pm in provider_mappings],
            "hotel": serialize_datetime_objects(hotel),
            "provider_mappings": enhanced_provider_mappings,
            "locations": [serialize_datetime_objects(loc) for loc in locations],
            "chains": [serialize_datetime_objects(chain) for chain in chains],
            "contacts": [serialize_datetime_objects(contact) for contact in contacts],
            "supplier_info": {
                "total_active_suppliers": len(all_provider_mappings),
                "accessible_suppliers": len(provider_mappings),
                "supplier_names": [pm.provider_name for pm in provider_mappings]
            }
        }

        return response_data

    except HTTPException:
        # Re-raise HTTP exceptions (like 403, 404)
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error retrieving hotel details: {str(e)}"
        )
