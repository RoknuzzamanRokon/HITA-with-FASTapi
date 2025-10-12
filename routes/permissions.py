from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from database import get_db
from models import User, UserRole, UserProviderPermission
from typing import List, Annotated
from routes.auth import get_current_user
from pydantic import BaseModel

router = APIRouter(
    prefix="/v1.0/permissions",
    tags=["User Permissions"],
    responses={404: {"description": "Not found"}},
)

class ProviderPermissionRequest(BaseModel):
    provider_activation_list: List[str]


@router.post("/activate_supplier", status_code=status.HTTP_200_OK, include_in_schema=False)
def grant_provider_permissions(
    user_id: str,
    request: ProviderPermissionRequest, 
    current_user: Annotated[User, Depends(get_current_user)],
    db: Session = Depends(get_db)
):
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
    "/deactivate_supplier/{user_id}",
    status_code=status.HTTP_200_OK,
    include_in_schema=False,
)
def remove_provider_permissions(
    user_id: str,
    request: ProviderDeactivationRequest,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Session = Depends(get_db),
):
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
