from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from database import get_db
from schemas import HotelCreate, HotelRead
import models
from utils import require_role
from pydantic import BaseModel
from typing import List, Optional, Annotated
from models import User, Hotel, ProviderMapping, Location, Contact, UserProviderPermission, UserRole
from routes.auth import get_current_user


router = APIRouter(
    prefix="/v1.0/hotels",
    tags=["Hotels Integrations & Mapping"],
    responses={404: {"description": "Not found"}},
)

# Create hotel
@router.post("/input_hotel_all_details", response_model=HotelRead, status_code=status.HTTP_201_CREATED, include_in_schema = False)
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

# Create 
@router.post(
    "/add_provider_all_details_with_ittid",
    status_code=status.HTTP_201_CREATED,
    include_in_schema=False,
)
def add_provider(
    provider_data: dict,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Add a provider mapping for an existing hotel."""
    require_role(["super_user", "admin_user"], current_user)

    ittid = provider_data.get("ittid")
    provider_name = provider_data.get("provider_name")
    provider_id = provider_data.get("provider_id")

    # 1️⃣ Verify hotel exists
    hotel = db.query(models.Hotel).filter(models.Hotel.ittid == ittid).first()
    if not hotel:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Hotel with ittid '{ittid}' not found.",
        )

    # 2️⃣ Skip if provider_name + provider_id already exist
    existing = (
        db.query(models.ProviderMapping)
        .filter(
            models.ProviderMapping.provider_name == provider_name,
            models.ProviderMapping.provider_id == provider_id,
        )
        .first()
    )
    if existing:
        print(
            f"⏩ Skipping: provider_name={provider_name}, provider_id={provider_id}, ittid={ittid} (already exists)"
        )
        existing_dict = existing.__dict__.copy()
        existing_dict.pop("_sa_instance_state", None)
        return {
            "message": "Provider mapping already exists; skipping.",
            "provider_mapping": existing_dict,
        }

    # 3️⃣ Otherwise, create a new mapping
    try:
        provider_mapping = models.ProviderMapping(**provider_data)
        db.add(provider_mapping)
        db.commit()
        db.refresh(provider_mapping)

        provider_dict = provider_mapping.__dict__.copy()
        provider_dict.pop("_sa_instance_state", None)

        return {
            "message": "Provider mapping added successfully.",
            "provider_mapping": provider_dict,
        }

    except Exception as e:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Error adding provider mapping: {str(e)}",
        )

# Get
@router.get("/get_supplier_info")
def get_supplier_info(
    supplier: str = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Get total hotel count for a supplier. 
    - super_user and admin_user can access any supplier
    - general_user can only access suppliers they have permissions for
    """
    if not supplier:
        raise HTTPException(status_code=400, detail="Supplier name is required.")

    # Check user permissions
    if current_user.role in ["super_user", "admin_user"]:
        # Super users and admin users can access any supplier
        pass
    elif current_user.role == "general_user":
        # General users can only access suppliers they have permissions for
        user_permission = db.query(models.UserProviderPermission).filter(
            models.UserProviderPermission.user_id == current_user.id,
            models.UserProviderPermission.provider_name == supplier
        ).first()
        
        if not user_permission:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"You don't have permission to access supplier '{supplier}'. Contact your administrator to request access."
            )
    else:
        # Unknown role
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Insufficient permissions to access supplier information."
        )

    # Get total hotel count for the supplier
    total_hotel = db.query(models.ProviderMapping).filter(
        models.ProviderMapping.provider_name == supplier
    ).count()

    return {
        "supplier_name": supplier,
        "total_hotel": total_hotel,
        "user_role": current_user.role,
        "access_granted": True
    }

# Get
@router.get("/get_user_accessible_suppliers")
def get_user_accessible_suppliers(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Get list of suppliers that the current user has access to.
    - super_user and admin_user get all available suppliers
    - general_user gets only suppliers they have permissions for
    """
    if current_user.role in ["super_user", "admin_user"]:
        # Super users and admin users can access all suppliers
        # Get all unique supplier names from ProviderMapping
        suppliers = db.query(models.ProviderMapping.provider_name).distinct().all()
        accessible_suppliers = [supplier[0] for supplier in suppliers if supplier[0]]
        
        # Get hotel counts for each supplier
        supplier_info = []
        for supplier_name in accessible_suppliers:
            hotel_count = db.query(models.ProviderMapping).filter(
                models.ProviderMapping.provider_name == supplier_name
            ).count()
            supplier_info.append({
                "supplier_name": supplier_name,
                "total_hotels": hotel_count,
                "access_type": "full_access"
            })
            
    elif current_user.role == "general_user":
        # General users get only suppliers they have permissions for
        user_permissions = db.query(models.UserProviderPermission).filter(
            models.UserProviderPermission.user_id == current_user.id
        ).all()
        
        supplier_info = []
        for permission in user_permissions:
            hotel_count = db.query(models.ProviderMapping).filter(
                models.ProviderMapping.provider_name == permission.provider_name
            ).count()
            supplier_info.append({
                "supplier_name": permission.provider_name,
                "total_hotels": hotel_count,
                "access_type": "permission_granted"
            })
    else:
        supplier_info = []

    return {
        "user_id": current_user.id,
        "user_role": current_user.role,
        "accessible_suppliers": supplier_info,
        "total_accessible_suppliers": len(supplier_info)
    }
