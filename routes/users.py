from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from database import get_db
from schemas import UserResponse, UserCreate, User, GivePointsRequest, SuperUserResponse, AdminUserResponse
from typing import Annotated
import models
from passlib.context import CryptContext
import secrets
from datetime import datetime, timedelta
from utils import get_current_user, deduct_points_for_general_user
from models import PointAllocationType





# Use bcrypt for password hashing
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

router = APIRouter(
    prefix="/v1.0/user",
    tags=["Users Integrations"],
    responses={404: {"description": "Not found"}},
)



@router.get("/me", response_model=UserResponse)
async def read_user_me(
    current_user: Annotated[models.User, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)]
):
    """Get the current user's details."""
    user_points = db.query(models.UserPoint).filter(models.UserPoint.user_id == current_user.id).first()
    print("This Is User Point.", user_points)
    available_points = user_points.current_points if user_points else 0
    total_points = user_points.total_points if user_points else 0

    suppliers = [
        perm.provider_name
        for perm in db.query(models.UserProviderPermission)
                       .filter(models.UserProviderPermission.user_id == current_user.id)
                       .all()
    ]
    active_supplier = list(set(suppliers))

    # Return the user's details
    return {
        "id": current_user.id,
        "username": current_user.username,
        "email": current_user.email,
        "user_status": current_user.role,
        "available_points": available_points,
        "total_points": total_points,
        "active_supplier": active_supplier,
        "created_at": current_user.created_at,
        "updated_at": current_user.updated_at,
        "need_to_next_upgrade": "It function is not implemented yet",
    }




@router.post("/create_super_user", response_model=SuperUserResponse)
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
    created_by = f'super_user: {current_user.email}' 


    super_user = models.User(
        id=unique_id,
        username=user_data["username"],
        email=user_data["email"],
        hashed_password=hashed_password,
        role=models.UserRole.SUPER_USER,
        is_active=True,
        created_by=created_by,
    )
    db.add(super_user)
    db.commit()
    db.refresh(super_user)

    return {
        "id": super_user.id,
        "username": super_user.username,
        "email": super_user.email,
        "role": super_user.role,
        "created_by": [
            {
                "title": "super_user",
                "email": current_user.email
            }
        ]
    }



@router.post("/create_admin_user", response_model=AdminUserResponse)
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
    if not admin_data.get("username") or not admin_data.get("email") or not admin_data.get("business_id") or not admin_data.get("password"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid input. 'username', 'email', 'business_id', and 'password' are required."
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
        username=admin_data["username"],
        email=admin_data["email"],
        hashed_password=hashed_password,
        role=models.UserRole.ADMIN_USER,
        api_key=None,  
        is_active=True,
        created_by=f'super_user: {current_user.email}',  # Set created_by to super_user
    )
    db.add(admin_user)
    db.commit()
    db.refresh(admin_user)

    return {
        "id": admin_user.id,
        "username": admin_user.username,
        "email": admin_user.email,
        "role": admin_user.role,
        "created_by": [
            {
                "title": "super_user",
                "email": current_user.email
            }
        ]
    }

@router.post("/create_general_user", response_model=User)
def create_general_user(
    user_data: dict,  
    current_user: Annotated[models.User, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)]
):
    """Create a general user (only accessible by super_user or admin_user)."""
    # Check if the current user is a super_user or admin_user
    if current_user.role not in [models.UserRole.SUPER_USER, models.UserRole.ADMIN_USER]:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only super_user or admin_user can create general users."
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

    # Generate a unique ID for the general user
    unique_id = secrets.token_hex(5)
    hashed_password = pwd_context.hash(user_data["password"])

    # Set created_by based on creator's role
    if current_user.role == models.UserRole.SUPER_USER:
        created_by = f"super_user: {current_user.email}"
    elif current_user.role == models.UserRole.ADMIN_USER:
        created_by = f"admin_user: {current_user.email}"
    else:
        created_by = "self"

    # Create the general user
    general_user = models.User(
        id=unique_id,
        username=user_data["username"],
        email=user_data["email"],
        hashed_password=hashed_password,
        role=models.UserRole.GENERAL_USER,
        api_key=None,
        is_active=True,
        created_by=created_by
    )
    db.add(general_user)
    db.commit()
    db.refresh(general_user)
    return {
        "id": general_user.id,
        "username": general_user.username,
        "email": general_user.email,
        "role": general_user.role,
        "created_by": [
            {
                "title": current_user.role,
                "email": current_user.email
            }
        ]
    }





@router.delete("/delete/delete_user/{user_id}")
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




@router.delete("/delete/delete_super_user/{user_id}")
def delete_supper_user(
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








@router.post("/points/give")
def give_points(
    request: GivePointsRequest,
    current_user: Annotated[models.User, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)]
):
    """Give points to another user based on allocation type."""
    # Validate giver's role
    if current_user.role not in [models.UserRole.SUPER_USER, models.UserRole.ADMIN_USER]:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only super_user or admin_user can give points."
        )

    # Find the receiver by email
    receiver = db.query(models.User).filter(models.User.email == request.receiver_email).first()
    if not receiver or not receiver.email:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Receiver not found or receiver does not have a valid email."
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
        receiver_points = models.UserPoint(
            user_id=receiver.id,
            user_email=receiver.email,  # Set email when creating
            total_points=0,
            current_points=0,
            total_used_points=0
        )
        db.add(receiver_points)
    # Always ensure email is set for existing records
    receiver_points.user_email = receiver.email

    # Determine points based on allocation type
    if request.allocation_type == models.PointAllocationType.ONE_YEAR_PACKAGE:
        points = 1000000
    elif request.allocation_type == models.PointAllocationType.ONE_MONTH_PACKAGE:
        points = 100000
    elif request.allocation_type == models.PointAllocationType.PER_REQUEST_POINT:
        points = 10000
    elif request.allocation_type == models.PointAllocationType.GUEST_POINT:
        points = 1000
    else:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid allocation type."
        )

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
        transaction_type=request.allocation_type.value,
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
    """Get point details for the current user, grouped by received and used points."""
    user_points = db.query(models.UserPoint).filter(models.UserPoint.user_id == current_user.id).first()
    total = user_points.total_points if user_points else 0
    current = user_points.current_points if user_points else 0
    used = user_points.total_used_points if user_points else 0
    user_email = getattr(user_points, "user_email", None) if user_points else None

    # Get all transactions for the user
    transactions = db.query(models.PointTransaction).filter(
        (models.PointTransaction.giver_id == current_user.id) |
        (models.PointTransaction.receiver_id == current_user.id)
    ).all()

    # Group transactions
    get_point_history = []
    uses_request_history = []

    total_used_point = 0
    for t in transactions:
        # Points received (current user is receiver)
        if t.receiver_id == current_user.id and t.transaction_type != "deduction":
            get_point_history.append({
                "id": t.id,
                "giver_id": t.giver_id,
                "giver_email": t.giver_email,
                "receiver_id": t.receiver_id,
                "receiver_email": t.receiver_email,
                "points": t.points,
                "transaction_type": t.transaction_type,
                "created_at": t.created_at,
            })
            total_used_point += t.points
        # Points used (current user is giver and type is deduction)
        elif t.giver_id == current_user.id and t.transaction_type == "deduction":
            uses_request_history.append({
                "id": t.id,
                "user_id": t.giver_id,
                "user_email": t.giver_email,
                "point_used": t.points,
                "totla_request": t.points // 10 if t.points else 0,  # Assuming 10 points per request
                "transaction_type": t.transaction_type,
                "created_at": t.created_at,
            })

    data = {
        "user_mail": user_email,
        "total_points": total,
        "current_points": current,
        "total_points_used": used,
        "transactions": [
            {
                "user_name": current_user.username,
                "user_id": current_user.id,
                "total_used_point": total_used_point,
                "get_point_history": get_point_history
            },
            {
                "uses_request_history": uses_request_history
            }
        ]
    }

    return data

@router.get("/super/check/all")
def super_check_all(
    current_user: Annotated[models.User, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)]
):
    """Get details of all users created by the current super_user, including super users."""
    if current_user.role != models.UserRole.SUPER_USER:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only super_user can access this endpoint."
        )

    # Only get users created by this super_user
    created_by_str = f"super_user: {current_user.email}"
    users = db.query(models.User).filter(models.User.created_by == created_by_str).all()

    response = {
        "total_super_user": 0,
        "total_admin_users": 0,
        "total_general_users": 0,
        "super_users": [],        # <-- Add this line
        "admin_users": [],
        "general_users": []
    }

    for user in users:
        user_points = db.query(models.UserPoint).filter(models.UserPoint.user_id == user.id).first()
        if user.role == models.UserRole.SUPER_USER:
            paid_status = "I am super user, I have unlimited points."
        else:
            paid_status = "Paid" if user_points and user_points.current_points > 0 else "Unpaid"

        points_info = {
            "total_points": user_points.total_points if user_points else 0,
            "current_points": user_points.current_points if user_points else 0,
            "paid_status": paid_status,
            "total_rq": db.query(models.PointTransaction).filter(
                models.PointTransaction.giver_id == user.id
            ).count() 
        }
        last_7_days = datetime.utcnow() - timedelta(days=7)
        recent_transactions = db.query(models.PointTransaction).filter(
            (models.PointTransaction.giver_id == user.id) |
            (models.PointTransaction.receiver_id == user.id),
            models.PointTransaction.created_at >= last_7_days
        ).count()

        using_rq_status = "Active" if recent_transactions > 0 else "Inactive"

        user_info = {
            "id": user.id,
            "username": user.username,
            "email": user.email,
            "points": points_info,
            "created_at": user.created_at,
            "user_status": user.role,
            "is_active": user.is_active,
            "using_rq_status": using_rq_status
        }
        if user.role == models.UserRole.SUPER_USER:
            response["super_users"].append(user_info)   # <-- Add to super_users list
            response["total_super_user"] += 1
        elif user.role == models.UserRole.ADMIN_USER:
            response["admin_users"].append(user_info)
            response["total_admin_users"] += 1
        elif user.role == models.UserRole.GENERAL_USER:
            response["general_users"].append(user_info)
            response["total_general_users"] += 1

    return response


@router.get("/active_my_supplier")
def active_my_supplier(
    current_user: Annotated[models.User, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)]
):
    """
    Return a list of active suppliers (provider names) for the current user.
    """
    suppliers = [
        perm.provider_name
        for perm in db.query(models.UserProviderPermission)
                      .filter(models.UserProviderPermission.user_id == current_user.id)
                      .all()
    ]
    unique_suppliers = list(set(suppliers))
    if not unique_suppliers:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No active suppliers found. Please contact your admin."
        )
    return {"my_supplier": unique_suppliers}



@router.get("/get_list_of_available_suppliers")
def get_list_of_available_suppliers(
    current_user: Annotated[models.User, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)]
):
    """
    Return a list of all unique supplier (provider_name) values from provider_mappings.
    """
    suppliers = [
        row.provider_name
        for row in db.query(models.ProviderMapping.provider_name).distinct().all()
    ]
    if not suppliers:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No suppliers found. Please contact your admin."
        )
    return {
        "total_supplier": len(suppliers),
        "supplier_list": suppliers
    }