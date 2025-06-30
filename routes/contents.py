from fastapi import APIRouter, Depends, HTTPException, status, Query, Body
from sqlalchemy.orm import Session, joinedload
from database import get_db
from models import Hotel, ProviderMapping, Location, Contact, UserProviderPermission, UserRole
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
        print("Allowed providers for user:", allowed_providers)
        print("Requested identities:", [vars(i) for i in request.provider_hotel_identity])
  

    # now you know GENERAL_USER has at least one allowed_provider
    # (or everyone else is None → full access)

    result = []
    for identity in request.provider_hotel_identity:
        name = identity.provider_name
        pid = identity.provider_id
        if allowed_providers and name not in allowed_providers:
            print(f"User not allowed for provider: {name}")
            continue

        mapping = (
            db.query(ProviderMapping)
            .filter_by(provider_id=pid, provider_name=name)
            .first()
        )
        if not mapping:
            print(f"No mapping found for provider_id={pid}, provider_name={name}")
            continue

        hotel = db.query(Hotel).filter(Hotel.ittid == mapping.ittid).first()
        if not hotel:
            print(f"No hotel found for ittid={mapping.ittid}")
            continue

        locations = db.query(Location).filter(Location.ittid == hotel.ittid).all()
        contacts  = db.query(Contact).filter(Contact.ittid == hotel.ittid).all()

        # Build hotel dict with only the required fields and order
        hotel_dict = {
            "ittid": hotel.ittid,
            "id": hotel.id,
            "name": hotel.name,
            "property_type": hotel.property_type,
            "longitude": hotel.longitude,
            "latitude": hotel.latitude,
            "address_line1": hotel.address_line1,
            "address_line2": hotel.address_line2,
            "postal_code": hotel.postal_code,
            "rating": hotel.rating,
            "primary_photo": hotel.primary_photo,
            "map_status": hotel.map_status,
            "updated_at": hotel.updated_at.isoformat() if hotel.updated_at else None,
            "created_at": hotel.created_at.isoformat() if hotel.created_at else None,
        }

        # Build provider_mappings list with only the required fields and order
        provider_mappings_list = [{
            "id": mapping.id,
            "provider_id": mapping.provider_id,
            "provider_name": mapping.provider_name,
            "system_type": mapping.system_type,
            "giata_code": mapping.giata_code,
            "vervotech_id": mapping.vervotech_id,
            "updated_at": mapping.updated_at.isoformat() if mapping.updated_at else None,
            "created_at": mapping.created_at.isoformat() if mapping.created_at else None,
        }]

        # Build locations list with only the required fields and order
        locations_list = [{
            "id": loc.id,
            "city_name": loc.city_name,
            "city_code": loc.city_code,
            "city_code": loc.city_code,
            "master_city_name": loc.master_city_name,
            "state_name": loc.state_name,
            "state_code": loc.state_code,
            "country_name": loc.country_name,
            "country_code": loc.country_code,
            "created_at": loc.created_at.isoformat() if loc.created_at else None,
            "updated_at": loc.updated_at.isoformat() if loc.updated_at else None,
        } for loc in locations]

        # Build contacts list with only the required fields and order
        contacts_list = [{
            "id": c.id,
            "contact_type": c.contact_type,
            "value": c.value
        } for c in contacts]

        result.append({
            "hotel": hotel_dict,
            "provider_mappings": provider_mappings_list,
            "locations": locations_list,
            "contacts": contacts_list
        })

    if not result:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Cannot mapping supplier in our system."
        )

    return result


class ITTIDRequest(BaseModel):
    ittid: List[str]



@router.post("/get_hotel_with_ittid", status_code=status.HTTP_200_OK)
def get_hotels_using_ittid_list(
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
                    "name": hotel.name,
                    "latitude": hotel.latitude,
                    "longitude": hotel.longitude,
                    "address_line1": hotel.address_line1,
                    "address_line2": hotel.address_line2,
                    "postal_code": hotel.postal_code,
                    "primary_photo": hotel.primary_photo,
                    "property_type": hotel.property_type,
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
                "name": hotel.name,
                "latitude": hotel.latitude,
                "longitude": hotel.longitude,
                "address_line1": hotel.address_line1,
                "address_line2": hotel.address_line2,
                "postal_code": hotel.postal_code,
                "property_type": hotel.property_type,
                "primary_photo": hotel.primary_photo,
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
def get_hotel_using_ittid(
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
    return {"hotel": hotel,
            "provider_mappings": provider_mappings, 
            "locations": locations, 
            "chains": chains, 
            "contacts": contacts
            }



@router.get("/get_all_hotel_info", status_code=status.HTTP_200_OK)
def get_all_hotels(
    current_user: Annotated[models.User, Depends(get_current_user)],
    page: int = Query(1, ge=1, description="Page number, starting from 1"),
    limit: int = Query(50, ge=1, le=1000, description="Number of hotels per page (max 1000)"),
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
            "name": hotel.name,
            "property_type": hotel.property_type,
            "rating": hotel.rating,
            "address_line1": hotel.address_line1,
            "address_line2": hotel.address_line2,
            "postal_code": hotel.postal_code,
            "map_status": hotel.map_status,
            "geocode": {
                "latitude": hotel.latitude,
                "longitude": hotel.longitude
            },

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






class ProviderProperty(BaseModel):
    provider_name: str

class ProviderPropertyRequest(BaseModel):
    provider_property: List[ProviderProperty]










@router.get(
    "/get_all_hotel_only_supplier/",
    response_model=GetAllHotelResponse,
    status_code=status.HTTP_200_OK
)
@cache(expire=600)
async def get_all_hotel_only_supplier(
    request: ProviderProperty,
    current_user: Annotated[models.User, Depends(get_current_user)],
    db: Session = Depends(get_db),
    limit_per_page: int = Query(50, ge=1, le=100),
    resume_key: Optional[str] = Query(None),
):
    # print("Hello")
    # --- Authorization & points deduction ---
    if current_user.role == models.UserRole.GENERAL_USER:
        deduct_points_for_general_user(current_user, db)
        allowed = [
            p.provider_name
            for p in db.query(models.UserProviderPermission)
                      .filter_by(user_id=current_user.id)
        ]
        if request.provider_name not in allowed:
            raise HTTPException(status_code=403, detail="No permission for this supplier")

    # --- Decode resume_key ---
    last_id = 0
    if resume_key:
        try:
            last_id = int(resume_key.split("_", 1)[0])
        except ValueError:
            raise HTTPException(status_code=400, detail="Invalid resume_key")

    # --- Single eager‐loaded query ---
    query = (
        db.query(models.ProviderMapping)
          .options(
              # load mapping → hotel → locations & contacts
              joinedload(models.ProviderMapping.hotel)
                .joinedload(models.Hotel.locations),
              joinedload(models.ProviderMapping.hotel)
                .joinedload(models.Hotel.contacts),
          )
          .filter(models.ProviderMapping.provider_name == request.provider_name)
          .order_by(models.ProviderMapping.id)
    )
    if last_id:
        query = query.filter(models.ProviderMapping.id > last_id)

    mappings = query.limit(limit_per_page).all()

    # --- Total count for pagination info ---
    total = (
        db.query(models.ProviderMapping)
          .filter(models.ProviderMapping.provider_name == request.provider_name)
          .count()
    )

    # --- Build grouped result by ittid ---
    hotels_by_ittid = {}
    for m in mappings:
        hotels_by_ittid.setdefault(m.ittid, []).append(m)

    result = []
    for ittid, group in hotels_by_ittid.items():
        hotel = group[0].hotel  # already loaded
        if not hotel:
            continue

        providers = [
            {"name": m.provider_name, "provider_id": m.provider_id, "status": "update"}
            for m in group
        ]

        # locations and contacts are eager-loaded on hotel
        location_list = [
            {
                "id": loc.id,
                "name": loc.city_name,
                "location_id": loc.city_location_id,
                "status": "update",
                "latitude": hotel.latitude,
                "longitude": hotel.longitude,
                "address": f"{hotel.address_line1 or ''} {hotel.address_line2 or ''}".strip(),
                "postal_code": hotel.postal_code,
                "city_id": loc.id,
                "city_name": loc.city_name,
                "city_code": loc.city_code,
                "state": loc.state_name,
                "country_name": loc.country_name,
                "country_code": loc.country_code,
            }
            for loc in hotel.locations
        ]

        contact = {"id": hotel.id, "phone": [], "email": [], "website": [], "fax": []}
        for c in hotel.contacts:
            if c.contact_type == "phone":
                contact["phone"].append(c.value)
            elif c.contact_type == "email":
                contact["email"].append(c.value)
            elif c.contact_type == "website":
                contact["website"].append(c.value)
            elif c.contact_type == "fax":
                contact["fax"].append(c.value)

        result.append({
            "ittid": hotel.ittid,
            "name": hotel.name,
            "country_name": location_list[0]["country_name"] if location_list else "",
            "country_code": location_list[0]["country_code"] if location_list else "",
            "type": "hotel",
            "provider": providers,
            "location": location_list,
            "contract": [contact],
        })

    # --- Next resume_key generation ---
    if len(mappings) == limit_per_page:
        last_map_id = mappings[-1].id
        rand = ''.join(secrets.choice(string.ascii_letters + string.digits) for _ in range(50))
        next_resume = f"{last_map_id}_{rand}"
    else:
        next_resume = None

    return {
        "resume_key": next_resume,
        "total_hotel": total,
        "show_hotels_this_page": len(result),
        "hotel": result,
    }



@router.get("/get_update_provider_info")
def get_update_provider_info(
    current_user: Annotated[models.User, Depends(get_current_user)],
    limit_per_page: int = Query(50, ge=1, le=500, description="Number of records per page"),
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






