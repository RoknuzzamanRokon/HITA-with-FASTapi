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
from typing import List
from fastapi.responses import JSONResponse





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
    Add a provider mapping and rate type information for an existing hotel.
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
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Rate type already exists for the given provider mapping."
        )
    
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


from sqlalchemy import select

@router.get(
    "/get_basic_mapping_with_info",
    response_model=List[BasicMappingResponse],
    status_code=status.HTTP_200_OK,
)
def get_basic_mapping_with_info(
    supplier_name: List[str] = Query(..., description="List of provider names to filter by"),
    country_iso:   List[str] = Query(..., description="List of country codes to filter by"),
    db:            Session    = Depends(get_db),
    current_user:  User       = Depends(get_current_user),
):
    require_role(["super_user", "admin_user"], current_user)

    # Step 1: Find all ittid for hotels with a location in the requested country
    ittid_subq = (
        db.query(Location.ittid)
        .filter(Location.country_code.in_(country_iso))
        .distinct()
        .subquery()
    )

    # Step 2: Query ProviderMapping for those hotels and supplier_name
    mappings: List[ProviderMapping] = (
        db.query(ProviderMapping)
        .join(Hotel, ProviderMapping.ittid == Hotel.ittid)
        .options(
            joinedload(ProviderMapping.hotel).joinedload(Hotel.locations),
            joinedload(ProviderMapping.rate_types)
        )
        .filter(
            ProviderMapping.provider_name.in_(supplier_name),
            ProviderMapping.ittid.in_(select(ittid_subq.c.ittid))
        )
        .all()
    )

    print("Mappings found:", len(mappings))

    results = []
    for mapping in mappings:
        hotel = mapping.hotel
        locations = [
            {
                "id": loc.id,
                "city_name": loc.city_name,
                "country_code": loc.country_code,
                "state_code": loc.state_code,
                "address": loc.city_location_id,
            }
            for loc in hotel.locations if loc.country_code in country_iso
        ]
        if mapping.rate_types:
            for rt in mapping.rate_types:
                results.append({
                    mapping.provider_name: [mapping.provider_id],
                    "hotel_name":    hotel.name,
                    "lon":           float(hotel.longitude) if hotel.longitude else None,
                    "lat":           float(hotel.latitude)  if hotel.latitude  else None,
                    "room_title":    rt.room_title,
                    "rate_type":     rt.rate_name,
                    "star_rating":   hotel.rating,
                    "primary_photo": hotel.primary_photo,
                    "address":       " ".join(filter(None, [hotel.address_line1, hotel.address_line2])),
                    "sell_per_night":rt.sell_per_night,
                    "vervotech":     mapping.vervotech_id,
                    "giata":         mapping.giata_code,
                    "ittid":        mapping.ittid,
                    # "locations":     locations,
                })
        else:
            # Add a result even if there are no rate_types
            results.append({
                mapping.provider_name: [mapping.provider_id],
                "hotel_name":    hotel.name,
                "lon":           float(hotel.longitude) if hotel.longitude else None,
                "lat":           float(hotel.latitude)  if hotel.latitude  else None,
                "room_title":    None,
                "rate_type":     None,
                "star_rating":   hotel.rating,
                "primary_photo": hotel.primary_photo,
                "address":       " ".join(filter(None, [hotel.address_line1, hotel.address_line2])),
                "sell_per_night":None,
                "vervotech":     mapping.vervotech_id,
                "giata":         mapping.giata_code,
                "ittid":        mapping.ittid,

                # "locations":     locations,
            })
    print("Results sample:", results[:2])  # Print first 2 results for debug

    return JSONResponse(
        content=results,
        media_type="application/json",
        headers={
            "Content-Disposition": "attachment; filename=basic_mapping.json"
        },
    
    )