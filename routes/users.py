from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from utils import get_current_user
from database import get_db
from schemas import UserResponse, UserCreate, User
from typing import Annotated
import models
from passlib.context import CryptContext
import secrets

# Use bcrypt for password hashing
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

router = APIRouter(
    prefix="/users",
    tags=["users"],
    responses={404: {"description": "Not found"}},
)





@router.post("/create-super-admin", response_model=User)
def create_super_admin(
    user_data: dict,  
    current_user: Annotated[models.User, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)]
):
    """Create a super user (only accessible by another super_user)."""
    # Check if the current user is a super_user
    if current_user.role != models.UserRole.SUPER_USER:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only super_user can create another super_user."
        )

    # Validate input data
    if not user_data.get("username") or not user_data.get("email") or not user_data.get("password"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid input. 'username', 'email', and 'password' are required."
        )

    # Check if email already exists
    existing_user = db.query(models.User).filter(models.User.email == user_data["email"]).first()
    if existing_user:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="User with this email already exists."
        )

    # Generate a unique ID for the super_user
    unique_id = secrets.token_hex(5)

    # Hash the password
    hashed_password = pwd_context.hash(user_data["password"])

    # Create the super_user
    super_user = models.User(
        id=unique_id,
        username=user_data["username"],
        email=user_data["email"],
        hashed_password=hashed_password,
        role=models.UserRole.SUPER_USER,
        is_active=True
    )
    db.add(super_user)
    db.commit()
    db.refresh(super_user)

    return super_user




@router.post("/create-admin-user", response_model=User)
def create_admin_user(
    admin_data: dict,  
    current_user: Annotated[models.User, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)]
):
    """Create an admin user (only accessible by super_user)."""
    # Check if the current user is a super_user
    if current_user.role != models.UserRole.SUPER_USER:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only super_user can create admin users."
        )

    # Validate input data
    if not admin_data.get("name") or not admin_data.get("email") or not admin_data.get("business_id") or not admin_data.get("password"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid input. 'name', 'email', 'business_id', and 'password' are required."
        )

    # Check if email already exists
    existing_user = db.query(models.User).filter(models.User.email == admin_data["email"]).first()
    if existing_user:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="User with this email already exists."
        )

    # Generate a unique ID for the admin user
    unique_id = secrets.token_hex(5)

    hashed_password = pwd_context.hash(admin_data["password"]) # Hash the email as a placeholder password

    # Create the admin user
    admin_user = models.User(
        id=unique_id,
        username=admin_data["name"],
        email=admin_data["email"],
        hashed_password=hashed_password,
        role=models.UserRole.ADMIN_USER,
        api_key=None,  
        is_active=True
    )
    db.add(admin_user)
    db.commit()
    db.refresh(admin_user)
    return admin_user




@router.delete("/delete-user/{user_id}")
def delete_user(
    user_id: str,
    current_user: Annotated[models.User, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)]
):
    """Delete a user by ID (only accessible by super_user)."""
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



@router.get("/me", response_model=UserResponse)
async def read_user_me(current_user: Annotated[models.User, Depends(get_current_user)]):
    """Get details of the current user."""
    return {
        "id": current_user.id,
        "username": current_user.username,
        "email": current_user.email,
        "user_status": current_user.role.value,
        "created_at": current_user.created_at,
    }


