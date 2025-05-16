from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from database import get_db
from models import Hotel, ProviderMapping, Location, Contact
from pydantic import BaseModel
from typing import List, Optional, Annotated
from datetime import datetime
from utils import get_current_user, deduct_points_for_general_user
import models



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

@router.post("/get_hotel_data_provider_name_and_id", status_code=status.HTTP_200_OK)
def get_hotel_data_provider_name_and_id(
    request: ProviderHotelRequest,
    current_user: Annotated[models.User, Depends(get_current_user)],
    db: Session = Depends(get_db)
):
    
    """Get details of the current user and deduct 10 points for general_user."""
    # Deduct points for general_user
    if current_user.role == models.UserRole.GENERAL_USER:
        deduct_points_for_general_user(current_user, db)


    """Fetch hotel details based on provider name and supplier ID."""
    result = []
    for identity in request.provider_hotel_identity:
        provider_mapping = db.query(ProviderMapping).filter(
            ProviderMapping.provider_id == identity.provider_id,
            ProviderMapping.provider_name == identity.provider_name
        ).first()

        if not provider_mapping:
            continue

        hotel = db.query(Hotel).filter(Hotel.ittid == provider_mapping.ittid).first()
        if not hotel:
            continue

        locations = db.query(Location).filter(Location.ittid == hotel.ittid).all()
        contacts = db.query(Contact).filter(Contact.ittid == hotel.ittid).all()

        result.append({
            "hotel": hotel,
            "provider_mappings": [provider_mapping],
            "locations": locations,
            "contacts": contacts
        })

    if not result:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No matching hotels found for the provided provider identities."
        )

    return result



import models


@router.get("/get_hotel_with_ittid/{ittid}", status_code=status.HTTP_200_OK)
def get_hotel_with_provider(
    ittid: str,
    current_user: Annotated[models.User, Depends(get_current_user)],
    db: Session = Depends(get_db)
):
    
    """Get details of the current user and deduct 10 points for general_user."""
    # Deduct points for general_user
    if current_user.role == models.UserRole.GENERAL_USER:
        deduct_points_for_general_user(current_user, db)
    """Get a hotel along with its provider mappings."""
    hotel = db.query(models.Hotel).filter(models.Hotel.ittid == ittid).first()
    if not hotel:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Hotel with id '{ittid}' not found."
        )

    locations = db.query(models.Location).filter(models.Location.ittid == hotel.ittid).all()
    provider_mappings = db.query(models.ProviderMapping).filter(models.ProviderMapping.ittid == hotel.ittid).all()
    chains = db.query(models.Chain).filter(models.Chain.ittid == hotel.ittid).all()
    contacts = db.query(models.Contact).filter(models.Contact.ittid == hotel.ittid).all()
    return {"hotel": hotel, "provider_mappings": provider_mappings, "locations": locations, "chains": chains, "contacts": contacts}


class ITTIDRequest(BaseModel):
    ittid: List[str]


@router.post("/get_hotel_with_ittid", status_code=status.HTTP_200_OK)
def get_hotels_with_providers(
    request: ITTIDRequest,
    current_user: Annotated[models.User, Depends(get_current_user)],
    db: Session = Depends(get_db)
):
    
    """Get details of the current user and deduct 10 points for general_user."""
    # Deduct points for general_user
    if current_user.role == models.UserRole.GENERAL_USER:
        deduct_points_for_general_user(current_user, db)

    """Get hotels along with their provider mappings based on a list of ittid values."""
    hotels = db.query(models.Hotel).filter(models.Hotel.ittid.in_(request.ittid)).all()
    if not hotels:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No hotels found for the provided ittid values."
        )

    result = []
    for hotel in hotels:
        # Fetch related data
        locations = db.query(models.Location).filter(models.Location.ittid == hotel.ittid).all()
        provider_mappings = db.query(models.ProviderMapping).filter(models.ProviderMapping.ittid == hotel.ittid).all()
        contacts = db.query(models.Contact).filter(models.Contact.ittid == hotel.ittid).all()

        # Transform data into the desired format
        formatted_hotel = {
            "id": hotel.id,
            "ittid": hotel.ittid,
            "latitude": hotel.latitude,
            "longitude": hotel.longitude,
            "address_line1": hotel.address_line1,
            "address_line2": hotel.address_line2,
            "postal_code": hotel.postal_code,
            "property_type": hotel.property_type,
            "name": hotel.name,
            "rating": hotel.rating,
            "map_status": hotel.map_status,
            "content_update_status": hotel.content_update_status,
            "updated_at": hotel.updated_at,
            "created_at": hotel.created_at,
        }

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

        formatted_locations = [
            {
                "id": location.id,
                "city_name": location.city_name,
                "city_location_id": location.city_location_id,
                "city_code": location.city_code,
                "master_city_name": location.master_city_name,
                "state_name": location.state_name,
                "state_code": location.state_code,
                "country_name": location.country_name,
                "country_code": location.country_code,
            }
            for location in locations
        ]

        formatted_contacts = [
            {
                "id": contact.id,
                "contact_type": contact.contact_type,
                "value": contact.value,
            }
            for contact in contacts
        ]

        result.append({
            "hotel": formatted_hotel,
            "provider_mappings": formatted_provider_mappings,
            "locations": formatted_locations,
            "contacts": formatted_contacts,
        })

    return result