from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from utils import get_current_user
from database import get_db
from schemas import UserResponse, UserCreate, User
from typing import Annotated
import models
from passlib.context import CryptContext
import secrets
from datetime import datetime, timedelta

    
# Use bcrypt for password hashing
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

router = APIRouter(
    prefix="/v1.0/user",
    tags=["Users Integrations"],
    responses={404: {"description": "Not found"}},
)


def deduct_points_for_general_user(current_user: models.User, db: Session, points: int = 10):
    """Deduct points for general_user."""
    # Get the user's points
    user_points = db.query(models.UserPoint).filter(models.UserPoint.user_id == current_user.id).first()
    if not user_points or user_points.current_points < points:
        raise HTTPException(
            status_code=400,
            detail="Insufficient points to access this endpoint."
        )

    # Deduct points
    user_points.current_points -= points
    user_points.total_used_points += points

    # Check if a deduction transaction already exists for the user
    existing_transaction = db.query(models.PointTransaction).filter(
        models.PointTransaction.giver_id == current_user.id,
        models.PointTransaction.transaction_type == "deduction"
    ).first()

    if existing_transaction:
        # Update the existing transaction
        existing_transaction.points += points
        existing_transaction.created_at = datetime.utcnow()  # Update the timestamp
    else:
        # Create a new transaction if none exists
        transaction = models.PointTransaction(
            giver_id=current_user.id,
            points=points,
            transaction_type="deduction",
            created_at=datetime.utcnow()
        )
        db.add(transaction)

    db.commit()


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
async def read_user_me(
    current_user: Annotated[models.User, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)]
):
    """Get details of the current user and deduct 10 points for general_user."""
    # Deduct points for general_user
    if current_user.role == models.UserRole.GENERAL_USER:
        deduct_points_for_general_user(current_user, db)

    # Return the user's details
    return {
        "id": current_user.id,
        "username": current_user.username,
        "email": current_user.email,
        "user_status": current_user.role.value,
        "created_at": current_user.created_at,
    }


@router.post("/points/give")
def give_points(
    receiver_email: str,
    points: int,
    current_user: Annotated[models.User, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)]
):
    """Give points to another user and deduct from giver."""
    # Validate giver's role
    if current_user.role not in [models.UserRole.SUPER_USER, models.UserRole.ADMIN_USER]:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only super_user or admin_user can give points."
        )

    # Find the receiver by email
    receiver = db.query(models.User).filter(models.User.email == receiver_email).first()
    if not receiver:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Receiver not found."
        )

    # Ensure admin_user can only give points to general_user
    if current_user.role == models.UserRole.ADMIN_USER and receiver.role != models.UserRole.GENERAL_USER:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin users can only give points to general users."
        )

    # Get or create user points for receiver
    receiver_points = db.query(models.UserPoint).filter(models.UserPoint.user_id == receiver.id).first()
    if not receiver_points:
        receiver_points = models.UserPoint(user_id=receiver.id, total_points=0, current_points=0, total_used_points=0)
        db.add(receiver_points)

    # Super users have unlimited points, skip deduction
    if current_user.role != models.UserRole.SUPER_USER:
        giver_points = db.query(models.UserPoint).filter(models.UserPoint.user_id == current_user.id).first()
        if not giver_points or giver_points.current_points < points:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Insufficient points to give."
            )
        # Deduct from giver
        giver_points.current_points -= points
        giver_points.total_used_points += points

    # Add to receiver
    receiver_points.total_points += points
    receiver_points.current_points += points

    # Log the transaction with emails
    transaction = models.PointTransaction(
        giver_id=current_user.id,
        receiver_id=receiver.id,
        giver_email=current_user.email,
        receiver_email=receiver.email,
        points=points,
        transaction_type="give",
        created_at=datetime.utcnow()
    )
    db.add(transaction)
    db.commit()

    return {"message": f"Successfully gave {points} points to {receiver.username}."}


@router.get("/points/check/me")
def get_point_details(
    current_user: Annotated[models.User, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)]
):
    """Get point details for the current user."""
    user_points = db.query(models.UserPoint).filter(models.UserPoint.user_id == current_user.id).first()
    total = user_points.total_points if user_points else 0
    current = user_points.current_points if user_points else 0
    used = user_points.total_used_points if user_points else 0

    # Rename total_used_points to total_points_used
    data = {
        "total_points": total,
        "current_points": current,
        "total_points_used": used,
        "transactions": []
    }

    # Get transaction history
    transactions = db.query(models.PointTransaction).filter(
        (models.PointTransaction.giver_id == current_user.id) |
        (models.PointTransaction.receiver_id == current_user.id)
    ).all()

    for t in transactions:
        data["transactions"].append({
            "id": t.id,
            "giver_id": t.giver_id,
            "giver_email": t.giver_email,
            "receiver_id": t.receiver_id,
            "receiver_email": t.receiver_email,
            "points": t.points,
            "transaction_type": t.transaction_type,
            "created_at": t.created_at,
        })

    return data




@router.get("/super/check/all")
def super_check_all(
    current_user: Annotated[models.User, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)]
):
    """Get details of all users (only accessible by super_user)."""
    # Ensure the current user is a super_user
    if current_user.role != models.UserRole.SUPER_USER:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only super_user can access this endpoint."
        )

    # Query all users
    users = db.query(models.User).all()

    # Prepare the response
    response = {
        "admin_users": [],
        "general_users": []
    }

    for user in users:
        # Get user points
        user_points = db.query(models.UserPoint).filter(models.UserPoint.user_id == user.id).first()
        points_info = {
            "total_points": user_points.total_points if user_points else 0,
            "current_points": user_points.current_points if user_points else 0,
            "paid_status": "Paid" if user_points and user_points.current_points > 0 else "Unpaid",
            "total_rq": db.query(models.PointTransaction).filter(
                models.PointTransaction.giver_id == user.id
            ).count() 
        }

        # Check if the user has transactions in the last 7 days
        last_7_days = datetime.utcnow() - timedelta(days=7)
        recent_transactions = db.query(models.PointTransaction).filter(
            (models.PointTransaction.giver_id == user.id) |
            (models.PointTransaction.receiver_id == user.id),
            models.PointTransaction.created_at >= last_7_days
        ).count()

        # Determine using_rq_status
        using_rq_status = "Active" if recent_transactions > 0 else "Inactive"

        # Add user details to the appropriate list
        user_info = {
            "id": user.id,
            "email": user.email,
            "points": points_info,
            "created_at": user.created_at,
            "user_status": user.role.value,
            "is_active": user.is_active,
            "using_rq_status": using_rq_status
        }
        if user.role == models.UserRole.ADMIN_USER:
            response["admin_users"].append(user_info)
        elif user.role == models.UserRole.GENERAL_USER:
            response["general_users"].append(user_info)

    return response