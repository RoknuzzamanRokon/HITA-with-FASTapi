from fastapi import APIRouter, Depends, HTTPException, status, Query, Body
from sqlalchemy.orm import Session, joinedload
from database import get_db
from models import Hotel, ProviderMapping, Location, RateTypeInfo, User
from datetime import datetime
from utils import get_current_user, require_role
import models
from fastapi_cache.decorator import cache
from schemas import AddRateTypeRequest, UpdateRateTypeRequest, BasicMappingResponse
from pydantic import BaseModel
from typing import List, Optional
from fastapi.responses import JSONResponse
from sqlalchemy import select
import secrets, string



router = APIRouter(
    prefix="/v1.0/mapping",
    tags=["Hotel mapping"],
    responses={404: {"description": "Not found"}},
)



@router.post("/add_rate_type_with_ittid_and_pid", status_code=status.HTTP_201_CREATED, include_in_schema=False)
def add_rate_type(
    provider_data: AddRateTypeRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Add or update a provider mapping and rate type information for an existing hotel.
    """
    require_role(["super_user", "admin_user"], current_user)

    # Check if the hotel exists
    hotel = db.query(models.Hotel).filter_by(ittid=provider_data.ittid).first()
    if not hotel:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Hotel not found."
        )

    # Check if the provider mapping exists
    provider_mapping = db.query(models.ProviderMapping).filter_by(id=provider_data.provider_mapping_id).first()
    if not provider_mapping:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Provider mapping not found."
        )

    # Check if a rate type for this hotel and provider already exists
    existing_rate_type = db.query(models.RateTypeInfo).filter_by(
        ittid=provider_data.ittid,
        provider_mapping_id=provider_data.provider_mapping_id
    ).first()
    if existing_rate_type:
        # Update the existing rate type
        existing_rate_type.room_title = provider_data.room_title
        existing_rate_type.rate_name = provider_data.rate_name
        existing_rate_type.sell_per_night = provider_data.sell_per_night
        existing_rate_type.updated_at = datetime.utcnow()
        db.commit()
        db.refresh(existing_rate_type)
        return {
            "message": "Rate type information updated successfully.",
            "rate_type_id": existing_rate_type.id
        }
    
    # Create new rate type info
    new_rate_type = models.RateTypeInfo(
        ittid=provider_data.ittid,
        provider_mapping_id=provider_data.provider_mapping_id,
        room_title=provider_data.room_title,
        rate_name=provider_data.rate_name,
        sell_per_night=provider_data.sell_per_night,
        created_at=datetime.utcnow()
    )
    db.add(new_rate_type)
    db.commit()
    db.refresh(new_rate_type)

    return {
        "message": "Rate type information added successfully.",
        "rate_type_id": new_rate_type.id
    }



@router.put("/update_rate_type", status_code=status.HTTP_200_OK, include_in_schema=False)
def update_rate_type(
    update_data: UpdateRateTypeRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    require_role(["super_user", "admin_user"], current_user)

    # Find the rate type record
    rate_type = db.query(models.RateTypeInfo).filter_by(
        ittid=update_data.ittid,
        provider_mapping_id=update_data.provider_mapping_id
    ).first()

    if not rate_type:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Rate type record not found."
        )

    # Update fields
    rate_type.room_title = update_data.room_title
    rate_type.rate_name = update_data.rate_name
    rate_type.sell_per_night = update_data.sell_per_night
    rate_type.updated_at = datetime.utcnow()  

    db.commit()
    db.refresh(rate_type)

    return {
        "message": "Rate type updated successfully.",
        "updated_rate_type_id": rate_type.id
    }



@router.get(
    "/get_basic_mapping_with_info",
    status_code=status.HTTP_200_OK,
)
@cache(expire=7200)
def get_basic_mapping_with_info(
    supplier_name: List[str] = Query(..., description="List of provider names to filter by"),
    country_iso:   List[str] = Query(..., description="List of country codes to filter by"),
    limit_per_page: int = Query(50, ge=1, le=500, description="Number of records per page"),
    resume_key: Optional[str] = Query(None, description="Pagination key"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    require_role(["super_user", "admin_user"], current_user)

    # Step 1: Decode resume_key
    last_id = 0
    if resume_key:
        try:
            last_id = int(resume_key.split("_", 1)[0])
        except Exception:
            raise HTTPException(status_code=400, detail="Invalid resume_key.")

    # Step 2: Get ittid for locations in given countries
    ittid_subq = (
        db.query(Location.ittid)
        .filter(Location.country_code.in_(country_iso))
        .distinct()
        .subquery()
    )

    # Step 3: Shared filter
    base_query = (
        db.query(ProviderMapping)
        .join(Hotel, ProviderMapping.ittid == Hotel.ittid)
        .filter(
            ProviderMapping.provider_name.in_(supplier_name),
            ProviderMapping.ittid.in_(select(ittid_subq.c.ittid))
        )
    )

    # Count total results (before pagination)
    total = base_query.count()

    # Apply options and pagination
    query = (
        base_query
        .options(
            joinedload(ProviderMapping.hotel).joinedload(Hotel.locations),
            joinedload(ProviderMapping.rate_types)
        )
        .order_by(ProviderMapping.id)
    )

    if last_id:
        query = query.filter(ProviderMapping.id > last_id)

    mappings: List[ProviderMapping] = query.limit(limit_per_page).all()
    

    # Step 4: Build result
    results = []
    for mapping in mappings:
        hotel = mapping.hotel
        if mapping.rate_types:
            for rt in mapping.rate_types:
                results.append({
                    mapping.provider_name: [mapping.provider_id],
                    "hotel_name": hotel.name,
                    "longitude": float(hotel.longitude) if hotel.longitude else None,
                    "latitude": float(hotel.latitude) if hotel.latitude else None,
                    "room_title": rt.room_title,
                    "rate_type": rt.rate_name,
                    "star_rating": hotel.rating,
                    "primary_photo": hotel.primary_photo,
                    "address": " ".join(filter(None, [hotel.address_line1, hotel.address_line2])),
                    "sell_per_night": rt.sell_per_night,
                    "vervotech_id": mapping.vervotech_id,
                    "giata_code": mapping.giata_code,
                    "ittid": mapping.ittid,
                })
        else:
            results.append({
                mapping.provider_name: [mapping.provider_id],
                "hotel_name": hotel.name,
                "longitude": float(hotel.longitude) if hotel.longitude else None,
                "latitude": float(hotel.latitude) if hotel.latitude else None,
                "room_title": None,
                "rate_type": None,
                "star_rating": hotel.rating,
                "primary_photo": hotel.primary_photo,
                "address": " ".join(filter(None, [hotel.address_line1, hotel.address_line2])),
                "sell_per_night": None,
                "vervotech_id": mapping.vervotech_id,
                "giata_code": mapping.giata_code,
                "ittid": mapping.ittid,
            })

    # Step 5: Generate new resume_key
    if len(mappings) == limit_per_page:
        last_map_id = mappings[-1].id
        rand = ''.join(secrets.choice(string.ascii_letters + string.digits) for _ in range(30))
        next_resume_key = f"{last_map_id}_{rand}"
    else:
        next_resume_key = None

    # Step 6: Return result with resume_key
    return JSONResponse(
        content={
            "resume_key": next_resume_key,
            "total_hotel": total,
            "show_hotels_this_page": len(results),
            "provider_mappings": results
        },
        media_type="application/json",
        headers={"Content-Disposition": "attachment; filename=basic_mapping.json"},
    )