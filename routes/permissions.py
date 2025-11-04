from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from database import get_db
from models import User, UserRole, UserProviderPermission
from typing import List, Annotated
from routes.auth import get_current_user
from pydantic import BaseModel
import models

router = APIRouter(
    prefix="/v1.0/permissions",
    tags=["User Permissions"],
    responses={404: {"description": "Not found"}},
)

class ProviderPermissionRequest(BaseModel):
    provider_activision_list: List[str]

class SupplierActivationRequest(BaseModel):
    supplier_name: List[str]


@router.post("/admin/check_activate_supplier", status_code=status.HTTP_200_OK, include_in_schema=False)
def grant_provider_permissions(
    user_id: str,
    request: ProviderPermissionRequest, 
    current_user: Annotated[User, Depends(get_current_user)],
    db: Session = Depends(get_db)
):
    """Grant provider permissions to a general user."""
    provider_names = request.provider_activision_list 

    # Check if the current user is a super_user or admin_user
    if current_user.role not in [UserRole.SUPER_USER, UserRole.ADMIN_USER]:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only super_user or admin_user can grant permissions."
        )

    # Find the user by ID
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found."
        )

    # Ensure the user is a general user
    if user.role != UserRole.GENERAL_USER:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Can only grant permissions to general users."
        )

    for provider_name in provider_names:
        existing_permission = db.query(UserProviderPermission).filter_by(
            user_id=user_id, provider_name=provider_name
        ).first()

        if not existing_permission:
            # Create new permission
            new_permission = UserProviderPermission(user_id=user_id, provider_name=provider_name)
            db.add(new_permission)
        else:
            # Optionally update fields here if needed
            # For now we do nothing, just skip to avoid duplicate
            pass

    db.commit()

    return {"message": f"Successfully updated permissions for user {user_id} with providers: {provider_names}"}


class ProviderDeactivationRequest(BaseModel):
    provider_deactivation_list: List[str]


@router.post(
    "/admin/deactivate_supplier/{user_id}",
    status_code=status.HTTP_200_OK,
    include_in_schema=False,
)
def remove_provider_permissions(
    user_id: str,
    request: ProviderDeactivationRequest,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Session = Depends(get_db),
):
    """Remove provider permissions from a general user."""
    provider_names = request.provider_deactivation_list

    # Check if the current user is a super_user or admin_user
    if current_user.role not in [UserRole.SUPER_USER, UserRole.ADMIN_USER]:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only super_user or admin_user can remove permissions.",
        )

    # Find the user by ID
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="User not found."
        )

    # Ensure the user is a general user
    if user.role != UserRole.GENERAL_USER:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Can only remove permissions from general users.",
        )

    removed = []
    for provider_name in provider_names:
        permission = (
            db.query(UserProviderPermission)
            .filter_by(user_id=user_id, provider_name=provider_name)
            .first()
        )
        if permission:
            db.delete(permission)
            removed.append(provider_name)

    db.commit()

    return {
        "message": f"Successfully removed permissions for user {user_id} for providers: {removed}"
    }


class SupplierToggleRequest(BaseModel):
    supplier_name: List[str]


@router.post("/turn-off-supplier", status_code=status.HTTP_200_OK)
def deactivate_suppliers_temporarily(
    request: SupplierToggleRequest,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Session = Depends(get_db)
):
    """
    Temporarily deactivate suppliers for the current user.
    
    This endpoint allows any authenticated user to temporarily hide specific suppliers
    from their active supplier list. The suppliers remain in their permissions but
    are marked as temporarily inactive.
    
    Body:
    - supplier_name: List of supplier names to deactivate
    
    Returns:
    - Success message with deactivated suppliers
    
    Raises:
    - 400: Invalid supplier names or user doesn't have access to suppliers
    - 500: Database error
    """
    try:
        supplier_names = request.supplier_name
        
        if not supplier_names:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="At least one supplier name is required."
            )
        
        # For super users and admin users, we'll create a temporary deactivation record
        # For general users, we need to check if they have permission for these suppliers
        if current_user.role not in [models.UserRole.ADMIN_USER, models.UserRole.SUPER_USER]:
            # Check if general user has permissions for these suppliers
            user_suppliers = [
                perm.provider_name
                for perm in db.query(models.UserProviderPermission)
                .filter(models.UserProviderPermission.user_id == current_user.id)
                .all()
            ]
            
            invalid_suppliers = [name for name in supplier_names if name not in user_suppliers]
            if invalid_suppliers:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"You don't have access to these suppliers: {invalid_suppliers}"
                )
        
        # Store temporarily deactivated suppliers in user session/cache
        # Since we can't modify the database schema, we'll use a simple approach
        # by creating temporary deactivation records
        
        deactivated = []
        for supplier_name in supplier_names:
            # Check if already deactivated
            existing = db.query(models.UserProviderPermission).filter(
                models.UserProviderPermission.user_id == current_user.id,
                models.UserProviderPermission.provider_name == f"TEMP_DEACTIVATED_{supplier_name}"
            ).first()
            
            if not existing:
                # Create a temporary deactivation record
                temp_deactivation = models.UserProviderPermission(
                    user_id=current_user.id,
                    provider_name=f"TEMP_DEACTIVATED_{supplier_name}"
                )
                db.add(temp_deactivation)
                deactivated.append(supplier_name)
        
        db.commit()
        
        return {
            "message": f"Successfully deactivated suppliers: {deactivated}",
            "deactivated_suppliers": deactivated
        }
        
    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"An error occurred while deactivating suppliers: {str(e)}"
        )


@router.post("/turn-on-supplier", status_code=status.HTTP_200_OK)
def activate_suppliers(
    request: SupplierActivationRequest,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Session = Depends(get_db)
):
    """
    Turn On Specific Suppliers
    
    Reactivates specified temporarily deactivated suppliers for the current user.
    Checks if suppliers are turned off before attempting to turn them on.
    
    Request Body:
    - supplier_name: List of supplier names to activate
    
    Returns:
    - Success message with activated suppliers
    - Error if suppliers are not turned off or don't exist
    
    Raises:
    - 400: Suppliers not turned off or invalid request
    - 500: Database error
    """
    try:
        if not request.supplier_name:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="At least one supplier name is required"
            )
        
        # Check which suppliers are currently turned off (temp deactivated)
        temp_deactivated_names = [f"TEMP_DEACTIVATED_{name}" for name in request.supplier_name]
        
        temp_deactivations = db.query(models.UserProviderPermission).filter(
            models.UserProviderPermission.user_id == current_user.id,
            models.UserProviderPermission.provider_name.in_(temp_deactivated_names)
        ).all()
        
        # Create mapping of deactivated suppliers
        deactivated_suppliers = {
            deactivation.provider_name.replace("TEMP_DEACTIVATED_", ""): deactivation 
            for deactivation in temp_deactivations
        }
        
        # Check which suppliers are not turned off
        not_turned_off = []
        for supplier in request.supplier_name:
            if supplier not in deactivated_suppliers:
                not_turned_off.append(supplier)
        
        # If some suppliers are not turned off, show error
        if not_turned_off:
            if len(not_turned_off) == len(request.supplier_name):
                # All suppliers are already active
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"All suppliers are already active: {', '.join(not_turned_off)}"
                )
            else:
                # Some suppliers are not turned off
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"These suppliers are not turned off: {', '.join(not_turned_off)}. Only turned off suppliers can be activated."
                )
        
        # All suppliers are turned off, proceed to activate them
        activated = []
        for supplier_name in request.supplier_name:
            deactivation_record = deactivated_suppliers[supplier_name]
            db.delete(deactivation_record)
            activated.append(supplier_name)
        
        db.commit()
        
        return {
            "message": f"Successfully activated suppliers: {', '.join(activated)}",
            "activated_suppliers": activated,
            "total_activated": len(activated)
        }
        
    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"An error occurred while activating suppliers: {str(e)}"
        )
