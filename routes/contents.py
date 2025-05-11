from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from database import get_db
from models import Hotel, ProviderMapping, Location, Contact
from pydantic import BaseModel
from typing import List

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
    db: Session = Depends(get_db)
):
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
