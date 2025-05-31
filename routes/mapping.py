from fastapi import APIRouter, Depends, HTTPException, status, Query, Body
from sqlalchemy.orm import Session, joinedload
from database import get_db
from models import User
from pydantic import BaseModel
from typing import List, Optional, Annotated
from datetime import datetime
from utils import get_current_user, deduct_points_for_general_user, require_role
import models
import secrets
import string
from fastapi_cache.decorator import cache


from schemas import ProviderProperty, GetAllHotelResponse

router = APIRouter()



router = APIRouter(
    prefix="/v1.0/mapping",
    tags=["Hotel mapping"],
    responses={404: {"description": "Not found"}},
)




@router.post(
    "/mapping/add_rate_type_with_ittid_pid",
    status_code=status.HTTP_201_CREATED
)
def add_rate_type(
    provider_data: dict,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Add a provider mapping and rate type information for an existing hotel.
    """
    require_role(["super_user", "admin_user"], current_user)

    # Validate required fields
    required_fields = [
        "ittid", "provider_mapping_id", "provider_name", "provider_id",
        "room_title", "rate_name", "sell_per_night"
    ]
    for field in required_fields:
        if field not in provider_data:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Missing required field: {field}"
            )

    ittid = provider_data["ittid"]
    provider_mapping_id = provider_data["provider_mapping_id"]
    provider_name = provider_data["provider_name"]
    provider_id = provider_data["provider_id"]
    room_title = provider_data["room_title"]
    rate_name = provider_data["rate_name"]
    sell_per_night = provider_data["sell_per_night"]

    # Check if the hotel exists
    hotel = db.query(models.Hotel).filter_by(ittid=ittid).first()
    if not hotel:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Hotel not found."
        )

    # Check if the provider mapping exists
    provider_mapping = db.query(models.ProviderMapping).filter_by(id=provider_mapping_id).first()
    if not provider_mapping:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Provider mapping not found."
        )

    # Create new rate type info
    new_rate_type = models.RateTypeInfo(
        ittid=ittid,
        provider_mapping_id=provider_mapping_id,
        room_title=room_title,
        rate_name=rate_name,
        sell_per_night=sell_per_night,
        created_at=datetime.utcnow()
    )
    db.add(new_rate_type)
    db.commit()
    db.refresh(new_rate_type)

    return {
        "message": "Rate type information added successfully.",
        "rate_type_id": new_rate_type.id
    }