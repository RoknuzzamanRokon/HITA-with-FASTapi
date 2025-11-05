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
    Turn Off Suppliers
    
    Temporarily deactivates specified suppliers for the current user.
    Checks supplier existence and current status before deactivation.
    
    Body:
    - supplier_name: List of supplier names to deactivate
    
    Returns:
    - Success message with deactivated suppliers
    - Error if suppliers already off or not found
    
    Raises:
    - 400: Suppliers already off, not found, or no access
    - 500: Database error
    """
    try:
        supplier_names = request.supplier_name
        
        if not supplier_names:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="At least one supplier name is required."
            )
        
        # Get user's available suppliers based on role
        if current_user.role in [models.UserRole.ADMIN_USER, models.UserRole.SUPER_USER]:
            # Super/Admin users can access all system suppliers
            all_system_suppliers = [
                row.provider_name
                for row in db.query(models.ProviderMapping.provider_name).distinct().all()
            ]
            user_accessible_suppliers = set(all_system_suppliers)
        else:
            # General users - get their assigned suppliers (excluding temp deactivated)
            user_permissions = [
                perm.provider_name
                for perm in db.query(models.UserProviderPermission)
                .filter(models.UserProviderPermission.user_id == current_user.id)
                .all()
            ]
            
            # Filter out temp deactivated to get base permissions
            user_accessible_suppliers = set([
                perm for perm in user_permissions 
                if not perm.startswith("TEMP_DEACTIVATED_")
            ])
        
        # Check which suppliers are not found/accessible
        not_found_suppliers = [name for name in supplier_names if name not in user_accessible_suppliers]
        if not_found_suppliers:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Cannot find supplier: {', '.join(not_found_suppliers)}"
            )
        
        # Check which suppliers are already deactivated
        already_deactivated = []
        for supplier_name in supplier_names:
            existing = db.query(models.UserProviderPermission).filter(
                models.UserProviderPermission.user_id == current_user.id,
                models.UserProviderPermission.provider_name == f"TEMP_DEACTIVATED_{supplier_name}"
            ).first()
            
            if existing:
                already_deactivated.append(supplier_name)
        
        # If all suppliers are already deactivated, show error
        if already_deactivated:
            if len(already_deactivated) == len(supplier_names):
                # All suppliers already off
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="This hotel already off"
                )
            else:
                # Some suppliers already off
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"These suppliers are already off: {', '.join(already_deactivated)}"
                )
        
        # Deactivate suppliers that are not already deactivated
        deactivated = []
        for supplier_name in supplier_names:
            if supplier_name not in already_deactivated:
                # Create a temporary deactivation record
                temp_deactivation = models.UserProviderPermission(
                    user_id=current_user.id,
                    provider_name=f"TEMP_DEACTIVATED_{supplier_name}"
                )
                db.add(temp_deactivation)
                deactivated.append(supplier_name)
        
        db.commit()
        
        return {
            "message": f"Successfully deactivated suppliers: {', '.join(deactivated)}",
            "deactivated_suppliers": deactivated,
            "total_deactivated": len(deactivated)
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
