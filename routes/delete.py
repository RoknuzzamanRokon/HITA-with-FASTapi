from fastapi import APIRouter, Depends, HTTPException, Query, status
from typing import Annotated
from sqlalchemy.orm import Session
import models
from database import get_db
from utils import deduct_points_for_general_user, require_role
from models import UserRole, Hotel, ProviderMapping, Location, Contact
from routes.auth import get_current_user

router = APIRouter(
    prefix="/v1.0/delete",
    tags=["Delete user & hotel"],
    responses={404: {"description": "Not found"}},
)


@router.delete("/delete_user/{user_id}", include_in_schema = False)
def delete_user(
    user_id: str,
    current_user: Annotated[models.User, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)]
):
    """
    **Delete User Account**
    
    Permanently remove user account from system. Super Admin only.
    
    **Use Cases:**
    - Remove inactive accounts
    - Compliance with data deletion requests
    - Clean up test accounts
    - Account termination
    
    **Example:**
    ```bash
    curl -X DELETE "/v1.0/delete/delete_user/abc123def4" \
         -H "Authorization: Bearer your_super_admin_token"
    ```
    
    **Response:**
    ```json
    {
      "message": "User with ID abc123def4 has been deleted."
    }
    ```
    
    **⚠️ Warning:** This action is irreversible. All user data will be permanently lost.
    """
    # Check if the current user is a super_user
    if current_user.role != models.UserRole.SUPER_USER:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only super_user can delete users."
        )

    # Find the user by ID
    user = db.query(models.User).filter(models.User.id == user_id).first()
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found."
        )

    # Delete the user
    db.delete(user)
    db.commit()

    return {"message": f"User with ID {user_id} has been deleted."}


@router.delete("/delete_super_user/{user_id}", include_in_schema = False)
def delete_supper_user(
    user_id: str,
    current_user: Annotated[models.User, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)]
):
    """
    **Delete Super User Account**
    
    Permanently remove super user account from system. Super Admin only.
    
    **Use Cases:**
    - Remove former super admin accounts
    - System cleanup and maintenance
    - Security incident response
    - Administrative restructuring
    
    **Example:**
    ```bash
    curl -X DELETE "/v1.0/delete/delete_super_user/xyz789abc1" \
         -H "Authorization: Bearer your_super_admin_token"
    ```
    
    **Response:**
    ```json
    {
      "message": "User with ID xyz789abc1 has been deleted."
    }
    ```
    
    **⚠️ Critical Warning:** Deleting super users affects system administration capabilities.
    """
    # Check if the current user is a super_user
    if current_user.role != models.UserRole.SUPER_USER:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only super_user can delete users."
        )

    # Find the user by ID
    user = db.query(models.User).filter(models.User.id == user_id).first()
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found."
        )

    # Delete the user
    db.delete(user)
    db.commit()

    return {"message": f"User with ID {user_id} has been deleted."}


@router.delete("/delete_hotel_by_ittid/{ittid}", status_code=status.HTTP_200_OK, include_in_schema = False)
def delete_hotel_by_ittid(
    ittid: str,
    current_user: Annotated[models.User, Depends(get_current_user)],
    db: Session = Depends(get_db)
):
    """
    **Delete Hotel & Related Data**
    
    Permanently remove hotel and all associated information by ITT ID. Super Admin only.
    
    **Use Cases:**
    - Remove outdated hotel listings
    - Clean up duplicate entries
    - Data quality maintenance
    - Compliance with removal requests
    
    **Deletes:**
    - Hotel record
    - Provider mappings
    - Location data
    - Contact information
    - Chain associations
    
    **Example:**
    ```bash
    curl -X DELETE "/v1.0/delete/delete_hotel_by_ittid/HTL123456" \
         -H "Authorization: Bearer your_super_admin_token"
    ```
    
    **Response:**
    ```json
    {
      "message": "Hotel with ittid 'HTL123456' and all related data deleted successfully."
    }
    ```
    
    **⚠️ Warning:** This cascades to delete ALL related hotel data permanently.
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


@router.delete("/delete_a_hotel_mapping", status_code=status.HTTP_200_OK, include_in_schema = False)
def delete_a_hotel_mapping(
    current_user: Annotated[models.User, Depends(get_current_user)],
    provider_name: str = Query(..., description="Provider name"),
    provider_id: str = Query(..., description="Provider ID"),
    db: Session = Depends(get_db)
):
    """
    **Delete Hotel Provider Mapping**
    
    Remove specific provider mapping for a hotel. Super Admin only.
    
    **Use Cases:**
    - Remove incorrect provider mappings
    - Clean up duplicate mappings
    - Update provider relationships
    - Data quality maintenance
    
    **Parameters:**
    - provider_name: Name of the provider (e.g., "Booking.com")
    - provider_id: Provider's unique ID for the hotel
    
    **Example:**
    ```bash
    curl -X DELETE "/v1.0/delete/delete_a_hotel_mapping?provider_name=Booking.com&provider_id=12345" \
         -H "Authorization: Bearer your_super_admin_token"
    ```
    
    **Response:**
    ```json
    {
      "message": "Mapping for provider 'Booking.com', provider_id '12345' deleted successfully."
    }
    ```
    
    **Note:** Only removes the specific mapping, hotel data remains intact.
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
