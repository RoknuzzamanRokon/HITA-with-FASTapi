from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from database import get_db
from models import User, UserRole, UserProviderPermission, UserIPWhitelist
from typing import List, Annotated
from routes.auth import get_current_user
from pydantic import BaseModel
import models
from security.input_validation import validate_ip_address
from datetime import datetime

router = APIRouter(
    prefix="/v1.0/permissions",
    tags=["User Permissions"],
    responses={404: {"description": "Not found"}},
)

class ProviderPermissionRequest(BaseModel):
    provider_activision_list: List[str]

class SupplierActivationRequest(BaseModel):
    supplier_name: List[str]

class IPWhitelistRequest(BaseModel):
    id: str  # User ID
    ip: List[str]  # List of IP addresses


@router.post("/admin/give-supplier-active", status_code=status.HTTP_200_OK, include_in_schema=False)
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
    "/admin/give-supplier-deactivate",
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

@router.post("/ip/active-permission", status_code=status.HTTP_200_OK)
def activate_ip_permission(
    request: IPWhitelistRequest,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Session = Depends(get_db)
):
    """
    IP Whitelist Management
    
    Allows super users and admin users to whitelist IP addresses for specific users.
    Users can only access APIs from whitelisted IP addresses once this is configured.
    
    Request Body:
    - id: Target user ID to whitelist IPs for
    - ip: List of IP addresses to whitelist (IPv4/IPv6 supported)
    
    Access Control:
    - Super User: Can whitelist IPs for any user
    - Admin User: Can whitelist IPs for any user
    - General User: Not allowed
    
    Features:
    - IP address format validation (IPv4/IPv6)
    - Duplicate IP prevention for same user
    - Audit logging for security tracking
    - Bulk IP address management
    
    Security:
    - Only super users and admins can manage IP whitelists
    - All changes are logged for audit purposes
    - Invalid IP addresses are rejected
    - User existence validation
    
    Returns:
    - Success message with whitelisted IPs
    - Count of newly added vs existing IPs
    - Detailed status for each IP address
    """
    try:
        # Validate user authentication and role
        if not current_user:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="User authentication required"
            )
        
        # Check if the current user has admin or super user role
        if current_user.role not in [UserRole.SUPER_USER, UserRole.ADMIN_USER]:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Only super users and admin users can manage IP whitelists"
            )
        
        # Validate request data
        if not request.id:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="User ID is required"
            )
        
        if not request.ip or len(request.ip) == 0:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="At least one IP address is required"
            )
        
        # Validate target user exists
        target_user = db.query(User).filter(User.id == request.id).first()
        if not target_user:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"User with ID '{request.id}' not found"
            )
        
        # Validate all IP addresses
        invalid_ips = []
        valid_ips = []
        
        for ip_addr in request.ip:
            if not ip_addr or not ip_addr.strip():
                invalid_ips.append(ip_addr)
                continue
                
            ip_addr = ip_addr.strip()
            if validate_ip_address(ip_addr):
                valid_ips.append(ip_addr)
            else:
                invalid_ips.append(ip_addr)
        
        if invalid_ips:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Invalid IP addresses: {', '.join(invalid_ips)}"
            )
        
        # Check for existing IP addresses for this user
        existing_ips = db.query(UserIPWhitelist).filter(
            UserIPWhitelist.user_id == request.id,
            UserIPWhitelist.ip_address.in_(valid_ips),
            UserIPWhitelist.is_active == True
        ).all()
        
        existing_ip_addresses = {ip.ip_address for ip in existing_ips}
        new_ips = [ip for ip in valid_ips if ip not in existing_ip_addresses]
        
        # Add new IP addresses
        added_ips = []
        for ip_addr in new_ips:
            whitelist_entry = UserIPWhitelist(
                user_id=request.id,
                ip_address=ip_addr,
                created_by=current_user.id,
                created_at=datetime.utcnow(),
                is_active=True
            )
            db.add(whitelist_entry)
            added_ips.append(ip_addr)
        
        db.commit()
        
        # Prepare response
        response = {
            "message": f"Successfully processed IP whitelist for user '{target_user.username}'",
            "target_user": {
                "id": target_user.id,
                "username": target_user.username,
                "email": target_user.email
            },
            "ip_summary": {
                "total_requested": len(valid_ips),
                "newly_added": len(added_ips),
                "already_existing": len(existing_ip_addresses),
                "total_active_ips": len(valid_ips)
            },
            "ip_details": {
                "newly_added": added_ips,
                "already_existing": list(existing_ip_addresses),
                "all_active_ips": valid_ips
            },
            "created_by": {
                "id": current_user.id,
                "username": getattr(current_user, 'username', 'unknown'),
                "role": current_user.role
            },
            "timestamp": datetime.utcnow().isoformat()
        }
        
        return response
        
    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"An error occurred while managing IP whitelist: {str(e)}"
        )

@router.get("/ip/list/{user_id}", status_code=status.HTTP_200_OK)
def get_user_ip_whitelist(
    user_id: str,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Session = Depends(get_db)
):
    """
    Get IP Whitelist for User
    
    Retrieves all active IP whitelist entries for a specific user.
    Only super users and admin users can view IP whitelists.
    
    Args:
        user_id: Target user ID to get IP whitelist for
        current_user: Currently authenticated user (must be super/admin)
        db: Database session
    
    Returns:
        dict: User information and their IP whitelist entries
    
    Access Control:
        - SUPER_USER: Can view any user's IP whitelist
        - ADMIN_USER: Can view any user's IP whitelist
        - GENERAL_USER: Access denied
    """
    try:
        # Check permissions
        if current_user.role not in [UserRole.SUPER_USER, UserRole.ADMIN_USER]:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Only super users and admin users can view IP whitelists"
            )
        
        # Check if target user exists
        target_user = db.query(User).filter(User.id == user_id).first()
        if not target_user:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"User with ID '{user_id}' not found"
            )
        
        # Get active IP whitelist entries
        ip_entries = db.query(UserIPWhitelist).filter(
            UserIPWhitelist.user_id == user_id,
            UserIPWhitelist.is_active == True
        ).all()
        
        # Format response
        ip_list = []
        for entry in ip_entries:
            ip_list.append({
                "id": entry.id,
                "ip_address": entry.ip_address,
                "created_at": entry.created_at.isoformat() if entry.created_at else None,
                "updated_at": entry.updated_at.isoformat() if entry.updated_at else None
            })
        
        return {
            "success": True,
            "user": {
                "id": target_user.id,
                "username": target_user.username,
                "email": target_user.email
            },
            "ip_whitelist": {
                "total_entries": len(ip_list),
                "entries": ip_list
            },
            "managed_by": {
                "id": current_user.id,
                "username": current_user.username
            }
        }
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"An error occurred while retrieving IP whitelist: {str(e)}"
        )


class IPRemovalRequest(BaseModel):
    user_id: str
    ip_addresses: List[str]


@router.delete("/ip/remove", status_code=status.HTTP_200_OK)
def remove_ip_whitelist(
    request: IPRemovalRequest,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Session = Depends(get_db)
):
    """
    Remove IP Addresses from Whitelist
    
    Removes specific IP addresses from a user's whitelist.
    Only super users and admin users can manage IP whitelists.
    
    Request Body:
        - user_id: Target user ID to remove IPs from
        - ip_addresses: List of IP addresses to remove
    
    Args:
        request: IPRemovalRequest containing user_id and ip_addresses
        current_user: Currently authenticated user (must be super/admin)
        db: Database session
    
    Returns:
        dict: Success message and details of removed IPs
    
    Access Control:
        - SUPER_USER: Can remove any user's IP whitelist entries
        - ADMIN_USER: Can remove any user's IP whitelist entries
        - GENERAL_USER: Access denied
    """
    try:
        # Check permissions
        if current_user.role not in [UserRole.SUPER_USER, UserRole.ADMIN_USER]:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Only super users and admin users can manage IP whitelists"
            )
        
        # Check if target user exists
        target_user = db.query(User).filter(User.id == request.user_id).first()
        if not target_user:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"User with ID '{request.user_id}' not found"
            )
        
        # Validate IP addresses
        import ipaddress
        valid_ips = []
        invalid_ips = []
        
        for ip in request.ip_addresses:
            try:
                ipaddress.ip_address(ip.strip())
                valid_ips.append(ip.strip())
            except ValueError:
                invalid_ips.append(ip)
        
        if invalid_ips:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Invalid IP addresses: {', '.join(invalid_ips)}"
            )
        
        # Find existing entries to remove
        entries_to_remove = db.query(UserIPWhitelist).filter(
            UserIPWhitelist.user_id == request.user_id,
            UserIPWhitelist.ip_address.in_(valid_ips),
            UserIPWhitelist.is_active == True
        ).all()
        
        if not entries_to_remove:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="No matching IP addresses found in whitelist"
            )
        
        # Remove entries (soft delete by setting is_active = False)
        removed_ips = []
        for entry in entries_to_remove:
            entry.is_active = False
            entry.updated_at = datetime.utcnow()
            removed_ips.append(entry.ip_address)
        
        db.commit()
        
        return {
            "success": True,
            "message": f"Successfully removed {len(removed_ips)} IP address(es) from whitelist",
            "target_user": {
                "id": target_user.id,
                "username": target_user.username
            },
            "removed_ips": removed_ips,
            "managed_by": {
                "id": current_user.id,
                "username": current_user.username
            }
        }
        
    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"An error occurred while removing IP whitelist: {str(e)}"
        )


@router.delete("/ip/clear/{user_id}", status_code=status.HTTP_200_OK)
def clear_user_ip_whitelist(
    user_id: str,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Session = Depends(get_db)
):
    """
    Clear All IP Whitelist Entries for User
    
    Removes all IP whitelist entries for a specific user.
    Only super users and admin users can manage IP whitelists.
    
    Args:
        user_id: Target user ID to clear IP whitelist for
        current_user: Currently authenticated user (must be super/admin)
        db: Database session
    
    Returns:
        dict: Success message and count of cleared entries
    
    Access Control:
        - SUPER_USER: Can clear any user's IP whitelist
        - ADMIN_USER: Can clear any user's IP whitelist
        - GENERAL_USER: Access denied
    """
    try:
        # Check permissions
        if current_user.role not in [UserRole.SUPER_USER, UserRole.ADMIN_USER]:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Only super users and admin users can manage IP whitelists"
            )
        
        # Check if target user exists
        target_user = db.query(User).filter(User.id == user_id).first()
        if not target_user:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"User with ID '{user_id}' not found"
            )
        
        # Find all active entries for this user
        active_entries = db.query(UserIPWhitelist).filter(
            UserIPWhitelist.user_id == user_id,
            UserIPWhitelist.is_active == True
        ).all()
        
        if not active_entries:
            return {
                "success": True,
                "message": "No active IP whitelist entries found for user",
                "target_user": {
                    "id": target_user.id,
                    "username": target_user.username
                },
                "cleared_count": 0
            }
        
        # Clear all entries (soft delete)
        cleared_ips = []
        for entry in active_entries:
            entry.is_active = False
            entry.updated_at = datetime.utcnow()
            cleared_ips.append(entry.ip_address)
        
        db.commit()
        
        return {
            "success": True,
            "message": f"Successfully cleared {len(cleared_ips)} IP whitelist entries",
            "target_user": {
                "id": target_user.id,
                "username": target_user.username
            },
            "cleared_ips": cleared_ips,
            "cleared_count": len(cleared_ips),
            "managed_by": {
                "id": current_user.id,
                "username": current_user.username
            }
        }
        
    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"An error occurred while clearing IP whitelist: {str(e)}"
        )