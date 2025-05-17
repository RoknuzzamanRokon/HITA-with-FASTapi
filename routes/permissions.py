from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from database import get_db
from models import User, UserRole, UserProviderPermission
from schemas import UserResponse
from typing import List, Annotated
from utils import get_current_user

router = APIRouter(
    prefix="/v1.0/permissions",
    tags=["User Permissions"],
    responses={404: {"description": "Not found"}},
)


@router.post("/for_supplier", status_code=status.HTTP_200_OK)
def grant_provider_permissions(
    user_id: str,
    provider_names: List[str],
    current_user: Annotated[User, Depends(get_current_user)],
    db: Session = Depends(get_db)
):
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

    # Remove existing permissions for the user
    existing_permissions = db.query(UserProviderPermission).filter(UserProviderPermission.user_id == user_id).all()
    for permission in existing_permissions:
        db.delete(permission)

    # Add new permissions
    for provider_name in provider_names:
        permission = UserProviderPermission(user_id=user_id, provider_name=provider_name)
        db.add(permission)

    db.commit()

    return {"message": f"Successfully granted permissions to user {user_id} for providers: {provider_names}"}
