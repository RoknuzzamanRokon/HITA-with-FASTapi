from fastapi import APIRouter, Depends, HTTPException, status, Query, Body
from sqlalchemy.orm import Session, joinedload
from database import get_db
from models import Hotel, ProviderMapping, Location, RateTypeInfo, User
from datetime import datetime
from utils import require_role
import models
from fastapi_cache.decorator import cache
from schemas import AddRateTypeRequest, UpdateRateTypeRequest, BasicMappingResponse
from pydantic import BaseModel
from typing import List, Optional
from fastapi.responses import JSONResponse
from sqlalchemy import select
import secrets, string
from routes.auth import get_current_user


router = APIRouter(
    prefix="/v1.0/mapping",
    tags=["Hotel mapping"],
    responses={404: {"description": "Not found"}},
)


@router.post("/add_rate_type_with_ittid_and_pid", status_code=status.HTTP_201_CREATED)
def add_rate_type(
    provider_data: AddRateTypeRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Add or update a provider mapping and rate type information for an existing hotel.
    
    This endpoint allows authorized users to create new rate type information or update existing
    rate type data for a specific hotel and provider mapping combination.
    
    Args:
        provider_data (AddRateTypeRequest): The rate type data including hotel ID, provider mapping ID,
                                          room title, rate name, and sell per night price
        db (Session): Database session dependency
        current_user (User): Current authenticated user
    
    Returns:
        dict: Success message with rate type ID
    
    Raises:
        HTTPException: 
            - 401: If user is not authenticated
            - 403: If user doesn't have required permissions (super_user or admin_user)
            - 404: If hotel or provider mapping not found
            - 500: If database operation fails
    
    Required Roles:
        - super_user
        - admin_user
    """
    try:
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
        
    except HTTPException:
        # Re-raise HTTP exceptions as they are already properly formatted
        raise
    except Exception as e:
        # Handle any unexpected database or other errors
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"An error occurred while processing the rate type: {str(e)}"
        )


@router.put("/update_rate_type", status_code=status.HTTP_200_OK)
def update_rate_type(
    update_data: UpdateRateTypeRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Update existing rate type information for a hotel and provider mapping.
    
    This endpoint allows authorized users to modify rate type details including
    room title, rate name, and sell per night price for an existing rate type record.
    
    Args:
        update_data (UpdateRateTypeRequest): Updated rate type data including hotel ID,
                                           provider mapping ID, and new rate information
        db (Session): Database session dependency
        current_user (User): Current authenticated user
    
    Returns:
        dict: Success message with updated rate type ID
    
    Raises:
        HTTPException:
            - 401: If user is not authenticated
            - 403: If user doesn't have required permissions (super_user or admin_user)
            - 404: If rate type record not found
            - 500: If database operation fails
    
    Required Roles:
        - super_user
        - admin_user
    """
    try:
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
        
    except HTTPException:
        # Re-raise HTTP exceptions as they are already properly formatted
        raise
    except Exception as e:
        # Handle any unexpected database or other errors
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"An error occurred while updating the rate type: {str(e)}"
        )


@router.get(
    "/get_basic_mapping_with_info",
    status_code=status.HTTP_200_OK,
)
@cache(expire=7200)
def get_basic_mapping_with_info(
    supplier_name: List[str] = Query(..., description="List of provider names to filter by"),
    country_iso: List[str] = Query(..., description="List of country codes to filter by"),
    limit_per_page: int = Query(50, ge=1, le=500, description="Number of records per page"),
    resume_key: Optional[str] = Query(None, description="Pagination key"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Retrieve basic hotel mapping information with filtering and pagination.
    
    This endpoint provides comprehensive hotel mapping data including provider mappings,
    rate types, and hotel details. Results are filtered by supplier names and country codes,
    with support for pagination using resume keys. The response is cached for 2 hours.
    
    Args:
        supplier_name (List[str]): List of provider/supplier names to filter results by
        country_iso (List[str]): List of ISO country codes to filter hotels by location
        limit_per_page (int): Number of records to return per page (1-500, default: 50)
        resume_key (Optional[str]): Pagination token for retrieving next page of results
        db (Session): Database session dependency
        current_user (User): Current authenticated user
    
    Returns:
        JSONResponse: Paginated hotel mapping data including:
            - resume_key: Token for next page (null if last page)
            - total_hotel: Total number of hotels matching filters
            - show_hotels_this_page: Number of hotels in current response
            - provider_mappings: Array of hotel mapping objects with details
    
    Raises:
        HTTPException:
            - 400: If resume_key format is invalid
            - 401: If user is not authenticated
            - 403: If user doesn't have required permissions (super_user or admin_user)
            - 422: If query parameters are invalid (e.g., limit_per_page out of range)
            - 500: If database query fails or other internal error occurs
    
    Required Roles:
        - super_user
        - admin_user
    
    Cache:
        Results are cached for 7200 seconds (2 hours) to improve performance
    
    Response Format:
        The response is returned as a JSON file attachment with comprehensive hotel data
        including coordinates, ratings, photos, addresses, and rate information.
    """
    try:
        require_role(["super_user", "admin_user"], current_user)

        # Step 1: Decode resume_key
        last_id = 0
        if resume_key:
            try:
                last_id = int(resume_key.split("_", 1)[0])
            except (ValueError, IndexError) as e:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Invalid resume_key format. Expected format: 'id_randomstring'"
                )

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
            if not hotel:
                continue  # Skip if hotel data is missing
                
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
        next_resume_key = None
        if len(mappings) == limit_per_page and mappings:
            last_map_id = mappings[-1].id
            rand = ''.join(secrets.choice(string.ascii_letters + string.digits) for _ in range(30))
            next_resume_key = f"{last_map_id}_{rand}"

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
        
    except HTTPException:
        # Re-raise HTTP exceptions as they are already properly formatted
        raise
    except Exception as e:
        # Handle any unexpected database or other errors
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"An error occurred while retrieving mapping data: {str(e)}"
        )


class ITTIDMappingRequest(BaseModel):
    ittid: str


@router.post("/get_mapping_with_ittid", status_code=status.HTTP_200_OK)
def get_mapping_with_ittid(
    request: ITTIDMappingRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Get Provider Mappings for Specific ITTID
    
    Retrieves all provider mappings for a specific hotel ITTID with permission validation.
    Only returns mappings for suppliers the user has active access to.
    
    Features:
    - Fast ITTID-based mapping retrieval
    - Role-based access control with supplier permission validation
    - Temporary deactivation support
    - Comprehensive mapping information with timestamps
    
    Args:
        request: ITTIDMappingRequest containing the hotel ITTID
        current_user: Currently authenticated user
        db: Database session
    
    Returns:
        dict: Mapping data including:
            - ittid: The hotel ITTID
            - total_supplier: Number of accessible suppliers for this hotel
            - provider_list: List of accessible provider names
            - provider_mappings: List of mapping objects with details
    
    Raises:
        400: Invalid ITTID format
        403: User doesn't have permission for any suppliers of this hotel
        404: Hotel not found or no accessible mappings
        500: Database or processing errors
    """
    try:
        # Validate ITTID
        if not request.ittid or not request.ittid.strip():
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="ITTID cannot be empty"
            )
        
        # Check if hotel exists
        hotel_exists = db.query(models.Hotel).filter(
            models.Hotel.ittid == request.ittid
        ).first()
        
        if not hotel_exists:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Hotel with ITTID '{request.ittid}' not found"
            )
        
        # Get all provider mappings for this ITTID
        all_mappings = db.query(models.ProviderMapping).filter(
            models.ProviderMapping.ittid == request.ittid
        ).all()
        
        if not all_mappings:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"No provider mappings found for ITTID '{request.ittid}'"
            )
        
        # FAST PERMISSION CHECK - Check user permissions for suppliers
        if current_user.role not in [models.UserRole.SUPER_USER, models.UserRole.ADMIN_USER]:
            # Get user permissions efficiently
            user_permissions = db.query(models.UserProviderPermission.provider_name).filter(
                models.UserProviderPermission.user_id == current_user.id
            ).all()
            
            if not user_permissions:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="You do not have permission to access any suppliers."
                )
            
            # Fast set operations for permission checking
            permission_names = {perm[0] for perm in user_permissions}
            temp_deactivated = {
                name.replace("TEMP_DEACTIVATED_", "") 
                for name in permission_names 
                if name.startswith("TEMP_DEACTIVATED_")
            }
            active_suppliers = {
                name for name in permission_names 
                if not name.startswith("TEMP_DEACTIVATED_")
            }
            final_active = active_suppliers - temp_deactivated
            
            # Filter mappings to only include accessible suppliers
            accessible_mappings = [
                mapping for mapping in all_mappings 
                if mapping.provider_name in final_active
            ]
            
            if not accessible_mappings:
                available_suppliers = [mapping.provider_name for mapping in all_mappings]
                temp_deactivated_for_hotel = [
                    supplier for supplier in available_suppliers 
                    if supplier in temp_deactivated
                ]
                
                if temp_deactivated_for_hotel:
                    raise HTTPException(
                        status_code=status.HTTP_403_FORBIDDEN,
                        detail=f"All suppliers for this hotel are temporarily deactivated: {', '.join(temp_deactivated_for_hotel)}"
                    )
                else:
                    raise HTTPException(
                        status_code=status.HTTP_403_FORBIDDEN,
                        detail=f"You don't have permission for any suppliers of this hotel. Available: {', '.join(available_suppliers)}"
                    )
        else:
            # For super/admin users, check for temporary deactivations
            user_permissions = db.query(models.UserProviderPermission.provider_name).filter(
                models.UserProviderPermission.user_id == current_user.id,
                models.UserProviderPermission.provider_name.like("TEMP_DEACTIVATED_%")
            ).all()
            
            temp_deactivated = {
                perm[0].replace("TEMP_DEACTIVATED_", "") 
                for perm in user_permissions
            }
            
            # Filter out temporarily deactivated suppliers
            accessible_mappings = [
                mapping for mapping in all_mappings 
                if mapping.provider_name not in temp_deactivated
            ]
            
            if not accessible_mappings:
                temp_deactivated_for_hotel = [
                    mapping.provider_name for mapping in all_mappings 
                    if mapping.provider_name in temp_deactivated
                ]
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail=f"All suppliers for this hotel are temporarily deactivated: {', '.join(temp_deactivated_for_hotel)}"
                )
        
        # Build response with accessible mappings
        provider_mappings = []
        provider_list = []
        
        for mapping in accessible_mappings:
            provider_mappings.append({
                "provider_name": mapping.provider_name,
                "provider_id": mapping.provider_id,
                "updated_at": mapping.updated_at.isoformat() if mapping.updated_at else None
            })
            
            if mapping.provider_name not in provider_list:
                provider_list.append(mapping.provider_name)
        
        return {
            "ittid": request.ittid,
            "total_supplier": len(provider_list),
            "provider_list": provider_list,
            "provider_mappings": provider_mappings
        }
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error retrieving mapping data: {str(e)}"
        )




