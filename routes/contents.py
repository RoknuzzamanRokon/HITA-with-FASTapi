from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.orm import Session
from database import get_db
from models import Hotel, ProviderMapping, Location, Contact, UserProviderPermission, UserRole
from pydantic import BaseModel
from typing import List, Optional, Annotated
from datetime import datetime
from utils import get_current_user, deduct_points_for_general_user, require_role
import models
import secrets
import string



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
    # Deduct points for general_user
    if current_user.role == models.UserRole.GENERAL_USER:
        deduct_points_for_general_user(current_user, db)

        # load permissions
        allowed_providers = [
            p.provider_name
            for p in db.query(UserProviderPermission)
                      .filter(UserProviderPermission.user_id == current_user.id)
                      .all()
        ]
        # **early error if truly no permissions**
        if not allowed_providers:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="you have not any permission for this request."
            )
    else:
        # if you really want _everyone else_ blocked until you grant, 
        # you could also force them into the same error here.
        allowed_providers = None  

    # now you know GENERAL_USER has at least one allowed_provider
    # (or everyone else is None → full access)

    result = []
    for identity in request.provider_hotel_identity:
        name = identity.provider_name
        if allowed_providers and name not in allowed_providers:
            continue

        mapping = (
            db.query(ProviderMapping)
              .filter_by(provider_id=identity.provider_id,
                         provider_name=name)
              .first()
        )
        if not mapping:
            continue

        hotel = db.query(Hotel).filter(Hotel.ittid == mapping.ittid).first()
        if not hotel:
            continue

        locations = db.query(Location).filter(Location.ittid == hotel.ittid).all()
        contacts  = db.query(Contact).filter(Contact.ittid == hotel.ittid).all()

        result.append({
            "hotel": hotel,
            "provider_mappings": [mapping],
            "locations": locations,
            "contacts": contacts
        })

    if not result:
        # either they had permissions but none matched the request
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Cannot add any supplier."
        )

    return result


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
    # Check user permissions
    if current_user.role == models.UserRole.GENERAL_USER:
        allowed_providers = [
            permission.provider_name
            for permission in db.query(UserProviderPermission).filter(UserProviderPermission.user_id == current_user.id).all()
        ]
        for hotel in hotels:
            provider_mappings = db.query(models.ProviderMapping).filter(models.ProviderMapping.ittid == hotel.ittid, models.ProviderMapping.provider_name.in_(allowed_providers)).all()
            if provider_mappings:
                # Fetch related data
                locations = db.query(models.Location).filter(models.Location.ittid == hotel.ittid).all()
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
    else:
        hotels = db.query(models.Hotel).filter(models.Hotel.ittid.in_(request.ittid)).all()
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

    # Check user permissions
    if current_user.role == models.UserRole.GENERAL_USER:
        allowed_providers = [
            permission.provider_name
            for permission in db.query(UserProviderPermission).filter(UserProviderPermission.user_id == current_user.id).all()
        ]
        if not allowed_providers:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Do not have permission or not active"
            )
        provider_mappings = db.query(models.ProviderMapping).filter(models.ProviderMapping.ittid == ittid, models.ProviderMapping.provider_name.in_(allowed_providers)).all()
        if not provider_mappings:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Do not have permission or not active"
            )
    else:
        provider_mappings = db.query(models.ProviderMapping).filter(models.ProviderMapping.ittid == ittid).all()

    locations = db.query(models.Location).filter(models.Location.ittid == hotel.ittid).all()
    chains = db.query(models.Chain).filter(models.Chain.ittid == hotel.ittid).all()
    contacts = db.query(models.Contact).filter(models.Contact.ittid == hotel.ittid).all()
    return {"hotel": hotel, "provider_mappings": provider_mappings, "locations": locations, "chains": chains, "contacts": contacts}



@router.get("/get_all_hotel_info", status_code=status.HTTP_200_OK)
def get_all_hotels(
    current_user: Annotated[models.User, Depends(get_current_user)],
    page: int = Query(1, ge=1, description="Page number, starting from 1"),
    limit: int = Query(50, ge=1, le=100, description="Number of hotels per page (max 100)"),
    resume_key: Optional[str] = Query(None, description="Resume key for pagination"),
    db: Session = Depends(get_db)
):
    """
    Get a paginated list of hotels. Use 'limit' to set page size (max 1000).
    Use 'resume_key' to get the next page (opaque random string).
    Only hotels accessible by the user's provider permissions are returned.
    Deduct points for general users.
    """

    # Deduct points and filter for general users
    if current_user.role == UserRole.GENERAL_USER:
        deduct_points_for_general_user(current_user, db)
        allowed_providers = [
            p.provider_name
            for p in db.query(UserProviderPermission)
                      .filter(UserProviderPermission.user_id == current_user.id)
                      .all()
        ]
        if not allowed_providers:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="You do not have any permission for this request."
            )
    else:
        allowed_providers = None

    # Decode resume_key if present (assume it's the last hotel id, encoded)
    last_id = 0
    if resume_key:
        try:
            last_id = int(resume_key.split("_")[0])
        except Exception:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid resume_key."
            )

    query = db.query(Hotel).order_by(Hotel.id)
    if last_id:
        query = query.filter(Hotel.id > last_id)

    # Filter by allowed providers for general users
    if allowed_providers is not None:
        hotel_ids = db.query(ProviderMapping.ittid).filter(
            ProviderMapping.provider_name.in_(allowed_providers)
        ).distinct().all()
        hotel_ids = [h[0] for h in hotel_ids]
        query = query.filter(Hotel.ittid.in_(hotel_ids))

    hotels = query.limit(limit).all()

    # Prepare next resume_key (random string + last hotel id)
    if hotels and len(hotels) == limit:
        last_hotel_id = hotels[-1].id
        rand_str = ''.join(secrets.choice(string.ascii_letters + string.digits) for _ in range(50))
        next_resume_key = f"{last_hotel_id}_{rand_str}"
    else:
        next_resume_key = None

    hotel_list = [
        {
            "ittid": hotel.ittid,
            "geocode": {
                "latitude": hotel.latitude,
                "longitude": hotel.longitude
            },
            "address_line1": hotel.address_line1,
            "address_line2": hotel.address_line2,
            "postal_code": hotel.postal_code,
            "property_type": hotel.property_type,
            "name": hotel.name,
            "rating": hotel.rating,
            "updated_at": hotel.updated_at,
            "created_at": hotel.created_at,
        }
        for hotel in hotels
    ]

    total_hotel = db.query(Hotel).count()
    return {
        "resume_key": next_resume_key,
        "page": page,
        "limit": limit,
        "total_hotel": total_hotel,
        "hotels": hotel_list
    }






@router.get("/get_update_provider_info")
def get_update_provider_info(
    current_user: Annotated[models.User, Depends(get_current_user)],
    limit_per_page: int = Query(50, ge=1, le=100, description="Number of records per page"),
    from_date: str = Query(..., description="Start date (YYYY-MM-DD)"),
    to_date: str = Query(..., description="End date (YYYY-MM-DD)"),
    resume_key: Optional[str] = Query(None, description="Resume key for pagination"),
    db: Session = Depends(get_db)
):
    """
    Get all new and updated provider mapping data for the user's active suppliers,
    filtered by date range and paginated.
    Super users see all mappings.
    """
    try:
        from_dt = datetime.strptime(from_date, "%Y-%m-%d")
        to_dt = datetime.strptime(to_date, "%Y-%m-%d")
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid date format. Use YYYY-MM-DD.")

    # Super users see all, others see only their allowed providers
    if current_user.role == UserRole.SUPER_USER:
        allowed_providers = None
    else:
        allowed_providers = [
            perm.provider_name
            for perm in db.query(UserProviderPermission)
                          .filter(UserProviderPermission.user_id == current_user.id)
                          .all()
        ]
        if not allowed_providers:
            return {"message": "Please contact your admin."}

    query = db.query(ProviderMapping).filter(
        ProviderMapping.updated_at >= from_dt,
        ProviderMapping.updated_at <= to_dt
    ).order_by(ProviderMapping.id)

    if allowed_providers is not None:
        query = query.filter(ProviderMapping.provider_name.in_(allowed_providers))

    # Pagination with resume_key (id)
    last_id = 0
    if resume_key:
        try:
            last_id = int(resume_key.split("_")[0])
        except Exception:
            raise HTTPException(status_code=400, detail="Invalid resume_key.")
        query = query.filter(ProviderMapping.id > last_id)

    mappings = query.limit(limit_per_page).all()

    # Prepare next resume_key (random string + last id)
    if mappings and len(mappings) == limit_per_page:
        last_hotel_id = mappings[-1].id
        rand_str = ''.join(secrets.choice(string.ascii_letters + string.digits) for _ in range(50))
        next_resume_key = f"{last_hotel_id}_{rand_str}"
    else:
        next_resume_key = None

    result = [
        {
            "ittid": m.ittid,
            "provider_name": m.provider_name,
            "provider_id": m.provider_id,
            "system_type": m.system_type,
        }
        for m in mappings
    ]

    return {
        "resume_key": next_resume_key,
        "count": len(result),
        "provider_mappings": result
    }








@router.delete("/delete/delete_hotel_by_ittid/{ittid}", status_code=status.HTTP_200_OK)
def delete_hotel_by_ittid(
    ittid: str,
    current_user: Annotated[models.User, Depends(get_current_user)],
    db: Session = Depends(get_db)
):
    """
    Delete a hotel and all related information by ittid.
    Only SUPER_USER can access this endpoint.
    """
    if current_user.role != UserRole.SUPER_USER:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only super users can delete hotels."
        )

    hotel = db.query(Hotel).filter(Hotel.ittid == ittid).first()
    if not hotel:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Hotel with ittid '{ittid}' not found."
        )

    # Delete related data
    db.query(ProviderMapping).filter(ProviderMapping.ittid == ittid).delete()
    db.query(Location).filter(Location.ittid == ittid).delete()
    db.query(Contact).filter(Contact.ittid == ittid).delete()
    db.query(models.Chain).filter(models.Chain.ittid == ittid).delete()

    db.delete(hotel)
    db.commit()

    return {"message": f"Hotel with ittid '{ittid}' and all related data deleted successfully."}



@router.delete("/delete/delete_a_hotel_mapping", status_code=status.HTTP_200_OK)
def delete_a_hotel_mapping(
    current_user: Annotated[models.User, Depends(get_current_user)],
    provider_name: str = Query(..., description="Provider name"),
    provider_id: str = Query(..., description="Provider ID"),
    db: Session = Depends(get_db)
):
    """
    Delete a specific provider mapping for a hotel by ittid, provider_name, and provider_id.
    Only SUPER_USER can access this endpoint.
    """
    if current_user.role != UserRole.SUPER_USER:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only super users can delete hotel mappings."
        )

    mapping = db.query(ProviderMapping).filter(
        ProviderMapping.provider_name == provider_name,
        ProviderMapping.provider_id == provider_id
    ).first()

    if not mapping:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Provider mapping not found."
        )

    db.delete(mapping)
    db.commit()

    return {"message": f"Mapping for provider '{provider_name}', provider_id '{provider_id}' deleted successfully."}