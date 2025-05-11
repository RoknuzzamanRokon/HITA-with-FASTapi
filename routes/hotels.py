from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from database import get_db
from schemas import HotelCreate, HotelRead
import models
from models import User  # Import the User model
from utils import require_role, get_current_user  # Import get_current_user

from pydantic import BaseModel
from typing import List



router = APIRouter(
    prefix="/v1.0/hotels",
    tags=["Hotels Integrations"],
    responses={404: {"description": "Not found"}},
)

@router.post("/input_hotel/create_with_details", response_model=HotelRead, status_code=status.HTTP_201_CREATED)
def create_hotel_with_details(
    hotel: HotelCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)  # Use get_current_user to fetch the user
):
    """Create a new hotel with all related details."""
    # Check if the user has the required role
    require_role(["super_user", "admin_user"], current_user)

    try:
        db_hotel = models.Hotel(**hotel.dict(exclude={"locations", "provider_mappings", "contacts", "chains"}))
        db.add(db_hotel)
        db.commit()
        db.refresh(db_hotel)

        # Add related data (locations, provider_mappings, contacts, chains)
        for location in hotel.locations:
            db_location = models.Location(**location.dict(), ittid=db_hotel.ittid)
            db.add(db_location)

        for provider_mapping in hotel.provider_mappings:
            db_provider_mapping = models.ProviderMapping(**provider_mapping.dict(), ittid=db_hotel.ittid)
            db.add(db_provider_mapping)

        for contact in hotel.contacts:
            db_contact = models.Contact(**contact.dict(), ittid=db_hotel.ittid)
            db.add(db_contact)

        for chain in hotel.chains:
            db_chain = models.Chain(**chain.dict(), ittid=db_hotel.ittid)
            db.add(db_chain)

        db.commit()
        return db_hotel

    except Exception as e:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Error creating hotel: {str(e)}"
        )
    


@router.post("/mapping/add_provider", status_code=status.HTTP_201_CREATED)
def add_provider(
    provider_data: dict,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)  # Use get_current_user to fetch the user
):
    """Add a provider mapping for an existing hotel."""
    # Check if the user has the required role
    require_role(["super_user", "admin_user"], current_user)

    # Extract the `ittid` from the request body
    ittid = provider_data.get("ittid")

    # Check if the hotel with the given `ittid` exists
    hotel = db.query(models.Hotel).filter(models.Hotel.ittid == ittid).first()
    if not hotel:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Hotel with ittid '{ittid}' not found."
        )

    # Create a new provider mapping
    try:
        provider_mapping = models.ProviderMapping(**provider_data)
        db.add(provider_mapping)
        db.commit()
        db.refresh(provider_mapping)
        return {"message": "Provider mapping added successfully.", "provider_mapping": provider_mapping}
    except Exception as e:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Error adding provider mapping: {str(e)}"
        )
    

@router.get("/get_hotel_with_ittid/{ittid}", status_code=status.HTTP_200_OK)
def get_hotel_with_provider(
    ittid: str,
    db: Session = Depends(get_db)
):
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
    db: Session = Depends(get_db)
):
    """Get hotels along with their provider mappings based on a list of ittid values."""
    hotels = db.query(models.Hotel).filter(models.Hotel.ittid.in_(request.ittid)).all()
    if not hotels:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No hotels found for the provided ittid values."
        )

    result = []
    for hotel in hotels:
        locations = db.query(models.Location).filter(models.Location.ittid == hotel.ittid).all()
        provider_mappings = db.query(models.ProviderMapping).filter(models.ProviderMapping.ittid == hotel.ittid).all()
        chains = db.query(models.Chain).filter(models.Chain.ittid == hotel.ittid).all()
        contacts = db.query(models.Contact).filter(models.Contact.ittid == hotel.ittid).all()
        result.append({
            "hotel": hotel,
            "provider_mappings": provider_mappings,
            "locations": locations,
            "contacts": contacts,
            "chains": chains
        })

    return result