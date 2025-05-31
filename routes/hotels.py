from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from database import get_db
from schemas import HotelCreate, HotelRead
import models
from utils import require_role, get_current_user  
from pydantic import BaseModel
from typing import List, Optional, Annotated
from models import User, Hotel, ProviderMapping, Location, Contact, UserProviderPermission, UserRole



router = APIRouter(
    prefix="/v1.0/hotels",
    tags=["Hotels Integrations & Mapping"],
    responses={404: {"description": "Not found"}},
)

@router.post("/mapping/input_hotel_all_details", response_model=HotelRead, status_code=status.HTTP_201_CREATED)
def create_hotel_with_details(
    hotel: HotelCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user) 
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
    

    
@router.post(
    "/mapping/add_provider_all_details_with_ittid",
    status_code=status.HTTP_201_CREATED
)
def add_provider(
    provider_data: dict,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Add a provider mapping for an existing hotel."""
    require_role(["super_user", "admin_user"], current_user)

    ittid          = provider_data.get("ittid")
    provider_name  = provider_data.get("provider_name")
    provider_id    = provider_data.get("provider_id")

    # 1️⃣  Verify hotel exists
    hotel = db.query(models.Hotel).filter(models.Hotel.ittid == ittid).first()
    if not hotel:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Hotel with ittid '{ittid}' not found."
        )

    # 2️⃣  Skip if provider_name + provider_id already exist
    existing = (
        db.query(models.ProviderMapping)
          .filter(
              models.ProviderMapping.provider_name == provider_name,
              models.ProviderMapping.provider_id   == provider_id
          )
          .first()
    )
    if existing:
        print(
            f"⏩ Skipping: provider_name={provider_name}, provider_id={provider_id}, ittid={ittid} (already exists)"
        )
        # 200 OK but indicate no new row was created
        return {
            "message": "Provider mapping already exists; skipping.",
            "provider_mapping": existing
        }

    # 3️⃣  Otherwise, create a new mapping
    try:
        provider_mapping = models.ProviderMapping(**provider_data)
        db.add(provider_mapping)
        db.commit()
        db.refresh(provider_mapping)
        return {
            "message": "Provider mapping added successfully.",
            "provider_mapping": provider_mapping
        }
    except Exception as e:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Error adding provider mapping: {str(e)}"
        )


@router.get("/get_supplier_info")
def get_supplier_info(
    supplier: str = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Get total hotel count for a supplier. Only super_user and admin_user can use this endpoint.
    """
    require_role(["super_user", "admin_user"], current_user)

    if not supplier:
        raise HTTPException(status_code=400, detail="Supplier name is required.")

    total_hotel = db.query(models.ProviderMapping).filter(
        models.ProviderMapping.provider_name == supplier
    ).count()

    return {
        "supplier_name": supplier,
        "total_hotel": total_hotel
    }