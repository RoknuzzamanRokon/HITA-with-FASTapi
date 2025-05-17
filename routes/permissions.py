from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from database import get_db
from models import User, UserRole, UserProviderPermission
from typing import List, Annotated
from utils import get_current_user
from pydantic import BaseModel

router = APIRouter(
    prefix="/v1.0/permissions",
    tags=["User Permissions"],
    responses={404: {"description": "Not found"}},
)

class ProviderPermissionRequest(BaseModel):
    provider_activision_list: List[str]


@router.post("/for_supplier", status_code=status.HTTP_200_OK)
def grant_provider_permissions(
    user_id: str,
    request: ProviderPermissionRequest, 
    current_user: Annotated[User, Depends(get_current_user)],
    db: Session = Depends(get_db)
):
    provider_names = request.provider_activision_list 
    
    """Grant provider permissions to a general user (only accessible by super_user or admin_user)."""
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
    
    existing_permissions = db.query(UserProviderPermission).filter(UserProviderPermission.user_id == user_id).all()
    existing_provider_names = {perm.provider_name for perm in existing_permissions}

    # Remove existing permissions for the user
    # Add only new permissions
    for provider_name in provider_names:
        if provider_name not in existing_provider_names:
            permission = UserProviderPermission(user_id=user_id, provider_name=provider_name)
            db.add(permission)

    db.commit()

    # Add new permissions
    for provider_name in provider_names:
        permission = UserProviderPermission(user_id=user_id, provider_name=provider_name)
        db.add(permission)

    db.commit()

    return {"message": f"Successfully granted permissions to user {user_id} for providers: {provider_names}"}
    