from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from database import get_db
from schemas import HotelCreate, HotelRead
import models
from models import User  # Import the User model
from utils import require_role, get_current_user  # Import get_current_user

router = APIRouter(
    prefix="/v1/hotels",
    tags=["hotels"],
    responses={404: {"description": "Not found"}},
)

@router.post("/create_with_details", response_model=HotelRead)
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