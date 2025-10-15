from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.orm import Session
from sqlalchemy import func, or_
from database import get_db
from schemas import (
    UserResponse,
    UserCreate,
    User,
    GivePointsRequest,
    SuperUserResponse,
    AdminUserResponse,
)
from user_schemas import (
    UserListResponse,
    PaginatedUserResponse,
    UserDetailResponse,
    UserStatistics,
    UserSearchParams,
    UserCreateRequest,
    UserUpdateRequest,
    BulkUserOperationRequest,
    UserActivityResponse,
    APIError,
    ValidationError
)
from services.user_service import UserService
from typing import Annotated, Optional
import models
from passlib.context import CryptContext
import secrets
from datetime import datetime, timedelta
from models import PointAllocationType
from routes.auth import get_current_user
from error_handlers import (
    UserAlreadyExistsError,
    InsufficientPermissionsError,
    DataValidationError,
    BusinessRuleViolationError
)

# Use bcrypt for password hashing
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

router = APIRouter(
    prefix="/v1.0/user",
    tags=["Users Activity"],
    responses={404: {"description": "Not found"}},
)


@router.get("/me", response_model=UserResponse)
async def self_info(
    current_user: Annotated[models.User, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
):
    """Get the current user's details."""
    user_points = (
        db.query(models.UserPoint)
        .filter(models.UserPoint.user_id == current_user.id)
        .first()
    )
    # print("This Is User Point.", user_points)
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


@router.post("/", response_model=UserResponse)
async def create_user(
    user_data: UserCreateRequest,
    current_user: Annotated[models.User, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
):
    """Create a new user (general endpoint that routes to appropriate creation method)."""
    
    # Validate permissions based on the role being created
    if user_data.role == models.UserRole.SUPER_USER:
        if current_user.role != models.UserRole.SUPER_USER:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Only super users can create super users"
            )
    elif user_data.role == models.UserRole.ADMIN_USER:
        if current_user.role not in [models.UserRole.SUPER_USER]:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Only super users can create admin users"
            )
    # General users can be created by super users and admin users
    elif user_data.role == models.UserRole.GENERAL_USER:
        if current_user.role not in [models.UserRole.SUPER_USER, models.UserRole.ADMIN_USER]:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Insufficient permissions to create users"
            )
    
    # Check if user already exists
    existing_user = db.query(models.User).filter(
        (models.User.email == user_data.email) | 
        (models.User.username == user_data.username)
    ).first()
    
    if existing_user:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="User with this email or username already exists"
        )
    
    # Create the user
    hashed_password = pwd_context.hash(user_data.password)
    new_user = models.User(
        id=secrets.token_hex(5),
        username=user_data.username,
        email=user_data.email,
        hashed_password=hashed_password,
        role=user_data.role,
        is_active=True,
        created_by=f"{current_user.role.value}: {current_user.email}",
        created_at=datetime.utcnow()
    )
    
    db.add(new_user)
    db.commit()
    db.refresh(new_user)
    
    # Create initial user points
    user_points = models.UserPoint(
        user_id=new_user.id,
        current_points=0,
        total_points=0,
        paid_status="Unpaid"
    )
    db.add(user_points)
    db.commit()
    
    return {
        "id": new_user.id,
        "username": new_user.username,
        "email": new_user.email,
        "user_status": new_user.role,
        "available_points": 0,
        "total_points": 0,
        "active_supplier": [],
        "created_at": new_user.created_at,
        "updated_at": new_user.updated_at,
        "need_to_next_upgrade": "It function is not implemented yet",
    }


@router.post(
    "/create_super_user", response_model=SuperUserResponse, include_in_schema=False
)
def create_super_admin(
    user_data: dict,
    current_user: Annotated[models.User, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
):
    """Create a super user (only accessible by another super_user)."""
    try:
        # Use the enhanced user service for better validation and error handling
        user_service = UserService(db)
        
        # Convert dict to UserCreateRequest for validation
        create_request = UserCreateRequest(
            username=user_data.get("username", ""),
            email=user_data.get("email", ""),
            password=user_data.get("password", ""),
            role=models.UserRole.SUPER_USER
        )
        
        # Additional check for super user creation
        if current_user.role != models.UserRole.SUPER_USER:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Only super_user can create another super_user.",
            )
        
        # Create user using service
        created_user = user_service.create_user_with_validation(create_request, current_user)
        
        # Return in legacy format for backward compatibility
        return {
            "id": created_user.id,
            "username": created_user.username,
            "email": created_user.email,
            "role": created_user.role,
            "created_by": [{"title": "super_user", "email": current_user.email}],
        }
        
    except ValueError as e:
        # Handle validation errors
        if "email already exists" in str(e).lower():
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="User with this email already exists.",
            )
        elif "username already exists" in str(e).lower():
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Username already exists.",
            )
        else:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=str(e)
            )
    except HTTPException:
        raise
    except Exception as e:
        # Fallback to legacy implementation
        # Check if the current user is a super_user
        if current_user.role != models.UserRole.SUPER_USER:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Only super_user can create another super_user.",
            )

        # Validate input data
        if (
            not user_data.get("username")
            or not user_data.get("email")
            or not user_data.get("password")
        ):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid input. 'username', 'email', and 'password' are required.",
            )

        # Check if email already exists
        existing_user = (
            db.query(models.User).filter(models.User.email == user_data["email"]).first()
        )
        if existing_user:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="User with this email already exists.",
            )

        # Generate a unique ID for the super_user
        unique_id = secrets.token_hex(5)

        # Hash the password
        hashed_password = pwd_context.hash(user_data["password"])
        created_by = f"super_user: {current_user.email}"

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
            "created_by": [{"title": "super_user", "email": current_user.email}],
        }


@router.post(
    "/create_admin_user", response_model=AdminUserResponse, include_in_schema=False
)
def create_admin_user(
    admin_data: dict,
    current_user: Annotated[models.User, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
):
    """Create an admin user (only accessible by super_user)."""
    try:
        # Use the enhanced user service for better validation and error handling
        user_service = UserService(db)
        
        # Additional check for admin user creation
        if current_user.role != models.UserRole.SUPER_USER:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Only super_user can create admin users.",
            )
        
        # Convert dict to UserCreateRequest for validation
        create_request = UserCreateRequest(
            username=admin_data.get("username", ""),
            email=admin_data.get("email", ""),
            password=admin_data.get("password", ""),
            role=models.UserRole.ADMIN_USER
        )
        
        # Create user using service
        created_user = user_service.create_user_with_validation(create_request, current_user)
        
        # Return in legacy format for backward compatibility
        return {
            "id": created_user.id,
            "username": created_user.username,
            "email": created_user.email,
            "role": created_user.role,
            "created_by": [{"title": "super_user", "email": current_user.email}],
        }
        
    except ValueError as e:
        # Handle validation errors
        if "email already exists" in str(e).lower():
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="User with this email already exists.",
            )
        elif "username already exists" in str(e).lower():
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Username already exists.",
            )
        else:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=str(e)
            )
    except HTTPException:
        raise
    except Exception as e:
        # Fallback to legacy implementation
        # Check if the current user is a super_user
        if current_user.role != models.UserRole.SUPER_USER:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Only super_user can create admin users.",
            )

        # Validate input data
        if (
            not admin_data.get("username")
            or not admin_data.get("email")
            or not admin_data.get("business_id")
            or not admin_data.get("password")
        ):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid input. 'username', 'email', 'business_id', and 'password' are required.",
            )

        # Check if email already exists
        existing_user = (
            db.query(models.User).filter(models.User.email == admin_data["email"]).first()
        )
        if existing_user:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="User with this email already exists.",
            )

        # Generate a unique ID for the admin user
        unique_id = secrets.token_hex(5)

        hashed_password = pwd_context.hash(
            admin_data["password"]
        )  # Hash the password properly

        # Create the admin user
        admin_user = models.User(
            id=unique_id,
            username=admin_data["username"],
            email=admin_data["email"],
            hashed_password=hashed_password,
            role=models.UserRole.ADMIN_USER,
            api_key=None,
            is_active=True,
            created_by=f"super_user: {current_user.email}",  # Set created_by to super_user
        )
        db.add(admin_user)
        db.commit()
        db.refresh(admin_user)

        return {
            "id": admin_user.id,
            "username": admin_user.username,
            "email": admin_user.email,
            "role": admin_user.role,
            "created_by": [{"title": "super_user", "email": current_user.email}],
        }


@router.post("/create_general_user", response_model=User, include_in_schema=False)
def create_general_user(
    user_data: dict,
    current_user: Annotated[models.User, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
):
    """Create a general user (only accessible by super_user or admin_user)."""
    try:
        # Use the enhanced user service for better validation and error handling
        user_service = UserService(db)
        
        # Convert dict to UserCreateRequest for validation
        create_request = UserCreateRequest(
            username=user_data.get("username", ""),
            email=user_data.get("email", ""),
            password=user_data.get("password", ""),
            role=models.UserRole.GENERAL_USER
        )
        
        # Create user using service
        created_user = user_service.create_user_with_validation(create_request, current_user)
        
        # Return in legacy format for backward compatibility
        return {
            "id": created_user.id,
            "username": created_user.username,
            "email": created_user.email,
            "role": created_user.role,
            "created_by": [{"title": current_user.role, "email": current_user.email}],
        }
        
    except ValueError as e:
        # Handle validation errors
        if "email already exists" in str(e).lower():
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="User with this email already exists.",
            )
        elif "username already exists" in str(e).lower():
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Username already exists.",
            )
        elif "only super_user or admin_user" in str(e).lower():
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Only super_user or admin_user can create general users.",
            )
        else:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=str(e)
            )
    except Exception as e:
        # Fallback to legacy implementation
        # Check if the current user is a super_user or admin_user
        if current_user.role not in [
            models.UserRole.SUPER_USER,
            models.UserRole.ADMIN_USER,
        ]:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Only super_user or admin_user can create general users.",
            )

        # Validate input data
        if (
            not user_data.get("username")
            or not user_data.get("email")
            or not user_data.get("password")
        ):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid input. 'username', 'email', and 'password' are required.",
            )

        # Check if email already exists
        existing_user = (
            db.query(models.User).filter(models.User.email == user_data["email"]).first()
        )
        if existing_user:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="User with this email already exists.",
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
            created_by = f"own: {current_user.email}"

        # Create the general user
        general_user = models.User(
            id=unique_id,
            username=user_data["username"],
            email=user_data["email"],
            hashed_password=hashed_password,
            role=models.UserRole.GENERAL_USER,
            api_key=None,
            is_active=True,
            created_by=created_by,
        )
        db.add(general_user)
        db.commit()
        db.refresh(general_user)
        return {
            "id": general_user.id,
            "username": general_user.username,
            "email": general_user.email,
            "role": general_user.role,
            "created_by": [{"title": current_user.role, "email": current_user.email}],
        }


@router.post("/points/give", include_in_schema=False)
def give_points(
    request: GivePointsRequest,
    current_user: Annotated[models.User, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
):
    """Give points to another user based on allocation type."""
    # Validate giver's role
    if current_user.role not in [
        models.UserRole.SUPER_USER,
        models.UserRole.ADMIN_USER,
    ]:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only super_user or admin_user can give points.",
        )

    # Find the receiver by email
    receiver = (
        db.query(models.User)
        .filter(
            models.User.email == request.receiver_email,
            models.User.id == request.receiver_id,
        )
        .first()
    )
    if not receiver or not receiver.email:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Receiver not found or receiver does not have a valid email.",
        )

    # Ensure admin_user can only give points to general_user
    if (
        current_user.role == models.UserRole.ADMIN_USER
        and receiver.role != models.UserRole.GENERAL_USER
    ):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin users can only give points to general users.",
        )

    # Get or create user points for receiver
    receiver_points = (
        db.query(models.UserPoint)
        .filter(models.UserPoint.user_id == receiver.id)
        .first()
    )
    if not receiver_points:
        receiver_points = models.UserPoint(
            user_id=receiver.id,
            user_email=receiver.email,  # Set email when creating
            total_points=0,
            current_points=0,
            total_used_points=0,
        )
        db.add(receiver_points)
    # Always ensure email is set for existing records
    receiver_points.user_email = receiver.email

    # Determine points based on allocation type
    if request.allocation_type == models.PointAllocationType.ADMIN_USER_PACKAGE:
        points = 4000000
    elif request.allocation_type == models.PointAllocationType.ONE_YEAR_PACKAGE:
        points = 1000000
    elif request.allocation_type == models.PointAllocationType.ONE_MONTH_PACKAGE:
        points = 80000
    elif request.allocation_type == models.PointAllocationType.PER_REQUEST_POINT:
        points = 10000
    elif request.allocation_type == models.PointAllocationType.GUEST_POINT:
        points = 1000
    else:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid allocation type."
        )

    # Super users have unlimited points, skip deduction
    if current_user.role != models.UserRole.SUPER_USER:
        giver_points = (
            db.query(models.UserPoint)
            .filter(models.UserPoint.user_id == current_user.id)
            .first()
        )
        if not giver_points or giver_points.current_points < points:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Insufficient points to give.",
            )
        # Deduct from giver
        giver_points.current_points -= points
        giver_points.total_used_points += points

    # Add to receiver
    receiver_points.total_points += points
    receiver_points.current_points += points

    # Update receiver's created_by field based on giver's role
    if current_user.role == models.UserRole.ADMIN_USER:
        receiver.created_by = f"admin_user: {current_user.email}"
    elif current_user.role == models.UserRole.SUPER_USER:
        receiver.created_by = f"super_user: {current_user.email}"

    # Log the transaction with emails
    transaction = models.PointTransaction(
        giver_id=current_user.id,
        receiver_id=receiver.id,
        giver_email=current_user.email,
        receiver_email=receiver.email,
        points=points,
        transaction_type=request.allocation_type.value,
        created_at=datetime.utcnow(),
    )
    db.add(transaction)
    db.commit()

    return {"message": f"Successfully gave {points} points to {receiver.username}."}


@router.post("/reset_point/{user_id}/", include_in_schema=False)
def reset_user_point(
    user_id: str,
    current_user: Annotated[models.User, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
):
    """
    Reset all points for the specified user to 0.
    Only super_user or admin_user can reset points.
    """
    if current_user.role not in [
        models.UserRole.SUPER_USER,
        models.UserRole.ADMIN_USER,
    ]:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only super_user or admin_user can reset points.",
        )

    user_points = (
        db.query(models.UserPoint).filter(models.UserPoint.user_id == user_id).first()
    )
    if not user_points:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User points not found.",
        )

    user_points.total_points = 0
    user_points.current_points = 0
    user_points.total_used_points = 0
    db.commit()

    return {"message": f"Points for user {user_id} have been reset to 0."}


@router.get("/points/check/me")
def check_point_details(
    current_user: Annotated[models.User, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
):
    """Get point details for the current user, grouped by received and used points."""
    user_points = (
        db.query(models.UserPoint)
        .filter(models.UserPoint.user_id == current_user.id)
        .first()
    )
    total = user_points.total_points if user_points else 0
    current = user_points.current_points if user_points else 0
    used = user_points.total_used_points if user_points else 0
    user_email = getattr(user_points, "user_email", None) if user_points else None

    # Get all transactions for the user
    transactions = (
        db.query(models.PointTransaction)
        .filter(
            (models.PointTransaction.giver_id == current_user.id)
            | (models.PointTransaction.receiver_id == current_user.id)
        )
        .all()
    )

    # Group transactions
    get_point_history = []
    uses_request_history = []

    total_used_point = 0
    for t in transactions:
        # Points received (current user is receiver)
        if t.receiver_id == current_user.id and t.transaction_type != "deduction":
            get_point_history.append(
                {
                    "id": t.id,
                    "giver_id": t.giver_id,
                    "giver_email": t.giver_email,
                    "receiver_id": t.receiver_id,
                    "receiver_email": t.receiver_email,
                    "points": t.points,
                    "transaction_type": t.transaction_type,
                    "created_at": t.created_at,
                }
            )
            total_used_point += t.points
        # Points used (current user is giver and type is deduction)
        elif t.giver_id == current_user.id and t.transaction_type == "deduction":
            uses_request_history.append(
                {
                    "id": t.id,
                    "user_id": t.giver_id,
                    "user_email": t.giver_email,
                    "point_used": t.points,
                    "total_request": (
                        t.points // 10 if t.points else 0
                    ),  # Assuming 10 points per request
                    "transaction_type": t.transaction_type,
                    "created_at": t.created_at,
                }
            )

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
                "get_point_history": get_point_history,
            },
            {"uses_request_history": uses_request_history},
        ],
    }

    return data


@router.get("/check/all", include_in_schema=False)
def check_all_users(
    page: Optional[int] = Query(None, ge=1, description="Page number for pagination"),
    limit: Optional[int] = Query(None, ge=1, le=100, description="Items per page"),
    search: Optional[str] = Query(None, description="Search by username or email"),
    current_user: Annotated[models.User, Depends(get_current_user)] = None,
    db: Annotated[Session, Depends(get_db)] = None,
):
    """
    Get all users created by the current user.
    Works for both SUPER_USER and ADMIN_USER.
    Includes user points, activity, and active suppliers.
    Now supports optional pagination and search for enhanced functionality.
    """

    # --- Access control ---
    if current_user.role not in [
        models.UserRole.SUPER_USER,
        models.UserRole.ADMIN_USER,
    ]:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only super_user or admin_user can access this endpoint.",
        )

    # If pagination parameters are provided, use the new enhanced endpoint
    if page is not None or limit is not None or search is not None:
        try:
            # Use the enhanced user service for paginated results
            user_service = UserService(db)
            search_params = UserSearchParams(
                page=page or 1,
                limit=limit or 25,
                search=search,
                sort_by="created_at",
                sort_order="desc"
            )
            
            paginated_result = user_service.get_users_paginated(search_params, current_user)
            
            # Convert to legacy format for backward compatibility
            response = {
                "total_super_user": paginated_result.statistics.super_users,
                "total_admin_users": paginated_result.statistics.admin_users,
                "total_general_users": paginated_result.statistics.general_users,
                "root_user": {},
                "super_users": [],
                "admin_users": [],
                "general_users": [],
                # Add pagination info for enhanced functionality
                "pagination": {
                    "page": paginated_result.pagination.page,
                    "limit": paginated_result.pagination.limit,
                    "total": paginated_result.pagination.total,
                    "total_pages": paginated_result.pagination.total_pages,
                    "has_next": paginated_result.pagination.has_next,
                    "has_prev": paginated_result.pagination.has_prev
                }
            }
            
            # Build root user info
            response["root_user"] = build_user_info_legacy(current_user, db)
            
            # Convert enhanced user responses to legacy format
            for user_response in paginated_result.users:
                legacy_user_info = convert_to_legacy_format(user_response)
                
                if user_response.role == models.UserRole.SUPER_USER:
                    response["super_users"].append(legacy_user_info)
                elif user_response.role == models.UserRole.ADMIN_USER:
                    response["admin_users"].append(legacy_user_info)
                elif user_response.role == models.UserRole.GENERAL_USER:
                    response["general_users"].append(legacy_user_info)
            
            return response
            
        except Exception as e:
            # Fall back to legacy implementation if enhanced version fails
            pass

    # --- Legacy implementation for backward compatibility ---
    created_by_str = f"{current_user.role.lower()}: {current_user.email}"
    users = db.query(models.User).filter(models.User.created_by == created_by_str).all()

    response = {
        "total_super_user": 0,
        "total_admin_users": 0,
        "total_general_users": 0,
        "root_user": {},
        "super_users": [],
        "admin_users": [],
        "general_users": [],
    }

    # --- Root user info (the requester) ---
    response["root_user"] = build_user_info_legacy(current_user, db)

    # --- Loop through created users ---
    for user in users:
        user_info = build_user_info_legacy(user, db)

        if user.role == models.UserRole.SUPER_USER:
            response["super_users"].append(user_info)
            response["total_super_user"] += 1
        elif user.role == models.UserRole.ADMIN_USER:
            response["admin_users"].append(user_info)
            response["total_admin_users"] += 1
        elif user.role == models.UserRole.GENERAL_USER:
            response["general_users"].append(user_info)
            response["total_general_users"] += 1

    return response


def build_user_info_legacy(user: models.User, db: Session):
    """Helper function to build user info in legacy format"""
    user_points = (
        db.query(models.UserPoint)
        .filter(models.UserPoint.user_id == user.id)
        .first()
    )

    if user.role == models.UserRole.SUPER_USER:
        paid_status = "I am super user, I have unlimited points."
    else:
        paid_status = (
            "Paid" if user_points and user_points.current_points > 0 else "Unpaid"
        )

    points_info = {
        "total_points": user_points.total_points if user_points else 0,
        "current_points": user_points.current_points if user_points else 0,
        "paid_status": paid_status,
        "total_rq": db.query(models.PointTransaction)
        .filter(models.PointTransaction.giver_id == user.id)
        .count(),
    }

    last_7_days = datetime.utcnow() - timedelta(days=7)
    recent_transactions = (
        db.query(models.PointTransaction)
        .filter(
            (models.PointTransaction.giver_id == user.id)
            | (models.PointTransaction.receiver_id == user.id),
            models.PointTransaction.created_at >= last_7_days,
        )
        .count()
    )
    using_rq_status = "Active" if recent_transactions > 0 else "Inactive"

    suppliers = [
        perm.provider_name
        for perm in db.query(models.UserProviderPermission)
        .filter(models.UserProviderPermission.user_id == user.id)
        .all()
    ]
    active_supplier = list(set(suppliers))

    return {
        "id": user.id,
        "username": user.username,
        "email": user.email,
        "points": points_info,
        "active_supplier": active_supplier,
        "created_at": user.created_at,
        "user_status": user.role,
        "is_active": user.is_active,
        "using_rq_status": using_rq_status,
        "created_by": user.created_by,
    }


def convert_to_legacy_format(user_response: UserListResponse):
    """Convert enhanced UserListResponse to legacy format"""
    points_info = {
        "total_points": user_response.total_points,
        "current_points": user_response.point_balance,
        "paid_status": user_response.paid_status,
        "total_rq": user_response.total_requests,
    }

    return {
        "id": user_response.id,
        "username": user_response.username,
        "email": user_response.email,
        "points": points_info,
        "active_supplier": user_response.active_suppliers,
        "created_at": user_response.created_at,
        "user_status": user_response.role,
        "is_active": user_response.is_active,
        "using_rq_status": user_response.activity_status,
        "created_by": user_response.created_by,
    }


# @router.get("/check/all", include_in_schema=False)
# def check_all(
#     current_user: Annotated[models.User, Depends(get_current_user)],
#     db: Annotated[Session, Depends(get_db)],
# ):
#     """
#     Show only users created by the current user (super or admin).
#     """
#     if current_user.role not in [
#         models.UserRole.SUPER_USER,
#         models.UserRole.ADMIN_USER,
#     ]:
#         raise HTTPException(
#             status_code=status.HTTP_403_FORBIDDEN,
#             detail="Only super_user or admin_user can access this endpoint.",
#         )

#     created_by_str = f"{current_user.role.lower()}: {current_user.email}"
#     # Only users created by current user
#     created_users = (
#         db.query(models.User).filter(models.User.created_by == created_by_str).all()
#     )

#     response = {"total_users": len(created_users), "users": []}

#     for user in created_users:
#         user_points = (
#             db.query(models.UserPoint)
#             .filter(models.UserPoint.user_id == user.id)
#             .first()
#         )
#         paid_status = (
#             "Paid" if user_points and user_points.current_points > 0 else "Unpaid"
#         )
#         points_info = {
#             "total_points": user_points.total_points if user_points else 0,
#             "current_points": user_points.current_points if user_points else 0,
#             "paid_status": paid_status,
#             "total_rq": db.query(models.PointTransaction)
#             .filter(models.PointTransaction.giver_id == user.id)
#             .count(),
#         }
#         last_7_days = datetime.utcnow() - timedelta(days=7)
#         recent_transactions = (
#             db.query(models.PointTransaction)
#             .filter(
#                 (models.PointTransaction.giver_id == user.id)
#                 | (models.PointTransaction.receiver_id == user.id),
#                 models.PointTransaction.created_at >= last_7_days,
#             )
#             .count()
#         )
#         using_rq_status = "Active" if recent_transactions > 0 else "Inactive"

#         response["users"].append(
#             {
#                 "id": user.id,
#                 "username": user.username,
#                 "email": user.email,
#                 "points": points_info,
#                 "created_at": user.created_at,
#                 "user_status": user.role,
#                 "is_active": user.is_active,
#                 "using_rq_status": using_rq_status,
#                 "created_by": user.created_by,
#             }
#         )

#     return response


@router.get("/check/user_info/{user_id}", include_in_schema=False)
def check_user_info(
    user_id: str,
    current_user: Annotated[models.User, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
):
    """
    Only show user info if the user was created by the current user (super or admin).
    """
    if current_user.role not in [
        models.UserRole.SUPER_USER,
        models.UserRole.ADMIN_USER,
    ]:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only super_user or admin_user can access this endpoint.",
        )

    created_by_str = f"{current_user.role.lower()}: {current_user.email}"
    user = db.query(models.User).filter(models.User.id == user_id).first()
    if not user or user.created_by != created_by_str:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found or you do not have permission to view this user.",
        )

    user_points = (
        db.query(models.UserPoint).filter(models.UserPoint.user_id == user.id).first()
    )
    paid_status = "Paid" if user_points and user_points.current_points > 0 else "Unpaid"
    points_info = {
        "total_points": user_points.total_points if user_points else 0,
        "current_points": user_points.current_points if user_points else 0,
        "paid_status": paid_status,
        "total_rq": db.query(models.PointTransaction)
        .filter(models.PointTransaction.giver_id == user.id)
        .count(),
    }
    last_7_days = datetime.utcnow() - timedelta(days=7)
    recent_transactions = (
        db.query(models.PointTransaction)
        .filter(
            (models.PointTransaction.giver_id == user.id)
            | (models.PointTransaction.receiver_id == user.id),
            models.PointTransaction.created_at >= last_7_days,
        )
        .count()
    )
    using_rq_status = "Active" if recent_transactions > 0 else "Inactive"

    return {
        "id": user.id,
        "username": user.username,
        "email": user.email,
        "points": points_info,
        "created_at": user.created_at,
        "user_status": user.role,
        "is_active": user.is_active,
        "using_rq_status": using_rq_status,
        "created_by": user.created_by,
    }


@router.get("/active_my_supplier")
def active_my_supplier(
    current_user: Annotated[models.User, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
):
    """
    Return a list of active suppliers (provider names) for the current user.
    Admin and super users have access to all suppliers.
    """
    # Admin and super users have access to all suppliers
    if current_user.role in [models.UserRole.ADMIN_USER, models.UserRole.SUPER_USER]:
        return {"my_supplier": "Active all supplier."}
    
    # Regular users get their specific supplier permissions
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
            detail="No active suppliers found. Please contact your admin.",
        )
    return {"my_supplier": unique_suppliers}


@router.get("/get_list_of_available_suppliers")
def get_list_of_available_suppliers(
    current_user: Annotated[models.User, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
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
            detail="No suppliers found. Please contact your admin.",
        )
    return {"total_supplier": len(suppliers), "supplier_list": suppliers}


# ===== ENHANCED USER MANAGEMENT ENDPOINTS =====

@router.get("/list", response_model=PaginatedUserResponse)
async def get_users_paginated(
    page: int = Query(1, ge=1, description="Page number"),
    limit: int = Query(25, ge=1, le=100, description="Items per page"),
    search: Optional[str] = Query(None, description="Search by username or email"),
    role: Optional[models.UserRole] = Query(None, description="Filter by user role"),
    is_active: Optional[bool] = Query(None, description="Filter by active status"),
    sort_by: Optional[str] = Query("created_at", description="Sort field"),
    sort_order: Optional[str] = Query("desc", description="Sort order (asc/desc)"),
    current_user: Annotated[models.User, Depends(get_current_user)] = None,
    db: Annotated[Session, Depends(get_db)] = None,
):
    """
    Get paginated list of users with comprehensive filtering and sorting.
    Supports search, role filtering, active status filtering, and multi-field sorting.
    """
    try:
        # Create search parameters
        search_params = UserSearchParams(
            page=page,
            limit=limit,
            search=search,
            role=role,
            is_active=is_active,
            sort_by=sort_by,
            sort_order=sort_order
        )
        
        # Get user service and fetch paginated results
        user_service = UserService(db)
        result = user_service.get_users_paginated(search_params, current_user)
        
        return result
        
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An error occurred while fetching users"
        )


@router.get("/stats", response_model=UserStatistics)
async def get_user_statistics(
    current_user: Annotated[models.User, Depends(get_current_user)] = None,
    db: Annotated[Session, Depends(get_db)] = None,
):
    """
    Get comprehensive user statistics for dashboard metrics.
    Returns counts by role, activity status, and point distribution.
    """
    try:
        user_service = UserService(db)
        statistics = user_service.get_user_statistics(current_user)
        return statistics
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An error occurred while fetching user statistics"
        )


@router.get("/{user_id}/details", response_model=UserDetailResponse)
async def get_user_details(
    user_id: str,
    current_user: Annotated[models.User, Depends(get_current_user)] = None,
    db: Annotated[Session, Depends(get_db)] = None,
):
    """
    Get detailed user information including points, activity, and recent transactions.
    """
    try:
        user_service = UserService(db)
        user_details = user_service.get_user_with_details(user_id, current_user)
        
        if not user_details:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="User not found or you don't have permission to view this user"
            )
        
        return user_details
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An error occurred while fetching user details"
        )


@router.get("/{user_id}/activity", response_model=UserActivityResponse)
async def get_user_activity(
    user_id: str,
    days: int = Query(30, ge=1, le=365, description="Number of days to look back"),
    current_user: Annotated[models.User, Depends(get_current_user)] = None,
    db: Annotated[Session, Depends(get_db)] = None,
):
    """
    Get user activity and analytics for specified time period.
    """
    try:
        user_service = UserService(db)
        activity = user_service.get_user_activity(user_id, days, current_user)
        
        if not activity:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="User not found or you don't have permission to view this user's activity"
            )
        
        return activity
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An error occurred while fetching user activity"
        )


@router.post("/bulk", response_model=dict)
async def bulk_user_operations(
    operations: BulkUserOperationRequest,
    current_user: Annotated[models.User, Depends(get_current_user)] = None,
    db: Annotated[Session, Depends(get_db)] = None,
):
    """
    Perform bulk user operations for administrative tasks.
    Supports create, update, and delete operations in batch.
    """
    # Check permissions
    if current_user.role not in [models.UserRole.SUPER_USER, models.UserRole.ADMIN_USER]:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only super_user or admin_user can perform bulk operations"
        )
    
    try:
        user_service = UserService(db)
        results = []
        errors = []
        
        for operation in operations.operations:
            try:
                if operation.operation == "create" and operation.user_data:
                    # Convert dict to UserCreateRequest
                    create_request = UserCreateRequest(**operation.user_data)
                    result = user_service.create_user_with_validation(create_request, current_user)
                    results.append({"operation": "create", "success": True, "user": result})
                    
                elif operation.operation == "update" and operation.user_id and operation.user_data:
                    # Convert dict to UserUpdateRequest
                    update_request = UserUpdateRequest(**operation.user_data)
                    result = user_service.update_user_with_validation(operation.user_id, update_request, current_user)
                    if result:
                        results.append({"operation": "update", "success": True, "user": result})
                    else:
                        errors.append({"operation": "update", "user_id": operation.user_id, "error": "User not found"})
                        
                elif operation.operation == "delete" and operation.user_id:
                    success = user_service.delete_user_with_cleanup(operation.user_id, current_user)
                    if success:
                        results.append({"operation": "delete", "success": True, "user_id": operation.user_id})
                    else:
                        errors.append({"operation": "delete", "user_id": operation.user_id, "error": "User not found"})
                        
                else:
                    errors.append({"operation": operation.operation, "error": "Invalid operation or missing data"})
                    
            except (UserAlreadyExistsError, InsufficientPermissionsError, DataValidationError, BusinessRuleViolationError) as e:
                errors.append({"operation": operation.operation, "error": str(e)})
            except ValueError as e:
                errors.append({"operation": operation.operation, "error": str(e)})
            except HTTPException as e:
                errors.append({"operation": operation.operation, "error": e.detail})
            except Exception as e:
                print(f"Bulk operation error: {str(e)}")  # For debugging
                import traceback
                print(f"Traceback: {traceback.format_exc()}")  # Full traceback for debugging
                errors.append({"operation": operation.operation, "error": str(e)})
        
        return {
            "total_operations": len(operations.operations),
            "successful_operations": len(results),
            "failed_operations": len(errors),
            "results": results,
            "errors": errors
        }
        
    except Exception as e:
        print(f"Bulk operations outer error: {str(e)}")  # For debugging
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"An error occurred while performing bulk operations: {str(e)}"
        )


@router.put("/{user_id}", response_model=UserListResponse)
async def update_user(
    user_id: str,
    user_updates: UserUpdateRequest,
    current_user: Annotated[models.User, Depends(get_current_user)] = None,
    db: Annotated[Session, Depends(get_db)] = None,
):
    """
    Update user with enhanced validation and partial update support.
    Supports updating username, email, password, role, and active status.
    """
    try:
        user_service = UserService(db)
        updated_user = user_service.update_user_with_validation(user_id, user_updates, current_user)
        
        if not updated_user:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="User not found"
            )
        
        return updated_user
        
    except ValueError as e:
        if "permission" in str(e).lower():
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=str(e)
            )
        else:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=str(e)
            )
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An error occurred while updating the user"
        )


@router.delete("/{user_id}")
async def delete_user(
    user_id: str,
    current_user: Annotated[models.User, Depends(get_current_user)] = None,
    db: Annotated[Session, Depends(get_db)] = None,
):
    """
    Delete user with proper cleanup and confirmation.
    Removes all related data including points, permissions, and sessions.
    """
    try:
        user_service = UserService(db)
        success = user_service.delete_user_with_cleanup(user_id, current_user)
        
        if not success:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="User not found"
            )
        
        return {
            "message": f"User {user_id} has been successfully deleted",
            "deleted_user_id": user_id,
            "deleted_by": current_user.email,
            "deleted_at": datetime.utcnow()
        }
        
    except ValueError as e:
        if "permission" in str(e).lower():
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=str(e)
            )
        else:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=str(e)
            )
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An error occurred while deleting the user"
        )


@router.post("/enhanced/create", response_model=UserListResponse)
async def create_user_enhanced(
    user_data: UserCreateRequest,
    current_user: Annotated[models.User, Depends(get_current_user)] = None,
    db: Annotated[Session, Depends(get_db)] = None,
):
    """
    Enhanced user creation endpoint with comprehensive validation.
    Supports creating users with proper role validation and error handling.
    """
    try:
        user_service = UserService(db)
        created_user = user_service.create_user_with_validation(user_data, current_user)
        
        return created_user
        
    except ValueError as e:
        if "permission" in str(e).lower() or "only super_user" in str(e).lower():
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=str(e)
            )
        elif "already exists" in str(e).lower():
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=str(e)
            )
        else:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=str(e)
            )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An error occurred while creating the user"
        )


@router.get("/health")
async def health_check():
    """
    Health check endpoint for user management service monitoring.
    """
    return {
        "status": "healthy",
        "service": "user_management",
        "timestamp": datetime.utcnow(),
        "version": "1.0.0"
    }


@router.get("/analytics/dashboard")
async def get_dashboard_analytics(
    current_user: Annotated[models.User, Depends(get_current_user)] = None,
    db: Annotated[Session, Depends(get_db)] = None,
):
    """
    Get comprehensive analytics for dashboard display.
    Includes user statistics, activity trends, and point distribution.
    """
    try:
        print("Hi")
        user_service = UserService(db)
        print("Hi")
        # Get basic statistics
        statistics = user_service.get_user_statistics(current_user)
        print("Hi")
        # Get additional analytics
        # Recent activity (last 30 days)
        thirty_days_ago = datetime.utcnow() - timedelta(days=30)

        # Build base query for users in current user's scope
        if current_user.role in [models.UserRole.SUPER_USER, models.UserRole.ADMIN_USER]:
            created_by_str = f"{current_user.role.lower()}: {current_user.email}"
            base_query = db.query(models.User).filter(models.User.created_by == created_by_str)
        else:
            created_by_str = None
            base_query = db.query(models.User).filter(models.User.id == current_user.id)

        # User creation trend (last 30 days)
        user_creation_trend = []
        for i in range(30):
            date = datetime.utcnow() - timedelta(days=i)
            start_of_day = date.replace(hour=0, minute=0, second=0, microsecond=0)
            end_of_day = start_of_day + timedelta(days=1)

            count = base_query.filter(
                models.User.created_at >= start_of_day,
                models.User.created_at < end_of_day
            ).count()

            user_creation_trend.append({
                "date": start_of_day.strftime("%Y-%m-%d"),
                "count": count
            })

        # Point distribution by role
        point_distribution = db.query(
            models.User.role,
            func.sum(models.UserPoint.current_points).label('total_points'),
            func.count(models.User.id).label('user_count')
        ).join(
            models.UserPoint, models.User.id == models.UserPoint.user_id, isouter=True
        ).filter(
            models.User.created_by == created_by_str if created_by_str else models.User.id == current_user.id
        ).group_by(models.User.role).all()

        point_dist_data = []
        for role, total_points, user_count in point_distribution:
            point_dist_data.append({
                "role": role,
                "total_points": total_points or 0,
                "user_count": user_count,
                "average_points": (total_points or 0) / user_count if user_count > 0 else 0
            })

        # Activity summary
        active_users_last_7_days = base_query.join(
            models.PointTransaction,
            or_(
                models.PointTransaction.giver_id == models.User.id,
                models.PointTransaction.receiver_id == models.User.id
            )
        ).filter(
            models.PointTransaction.created_at >= datetime.utcnow() - timedelta(days=7)
        ).distinct().count()

        return {
            "statistics": statistics,
            "user_creation_trend": user_creation_trend,
            "point_distribution": point_dist_data,
            "activity_summary": {
                "active_users_last_7_days": active_users_last_7_days,
                "total_transactions_last_30_days": db.query(models.PointTransaction).filter(
                    models.PointTransaction.created_at >= thirty_days_ago
                ).count()
            },
            "generated_at": datetime.utcnow()
        }

    except Exception as e:
        print(f"Dashboard analytics error: {str(e)}")  # For debugging
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"An error occurred while fetching dashboard analytics: {str(e)}"
        )


@router.get("/analytics/points")
async def get_point_analytics(
    current_user: Annotated[models.User, Depends(get_current_user)] = None,
    db: Annotated[Session, Depends(get_db)] = None,
):
    """
    Get detailed point analytics and distribution metrics.
    """
    try:
        # Check permissions
        if current_user.role not in [models.UserRole.SUPER_USER, models.UserRole.ADMIN_USER]:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Only super_user or admin_user can access point analytics"
            )
        
        created_by_str = f"{current_user.role.lower()}: {current_user.email}"
        
        # Point allocation by type
        allocation_stats = db.query(
            models.PointTransaction.transaction_type,
            func.sum(models.PointTransaction.points).label('total_points'),
            func.count(models.PointTransaction.id).label('transaction_count')
        ).join(
            models.User, models.PointTransaction.receiver_id == models.User.id
        ).filter(
            models.User.created_by == created_by_str
        ).group_by(models.PointTransaction.transaction_type).all()
        
        allocation_data = []
        for transaction_type, total_points, count in allocation_stats:
            allocation_data.append({
                "allocation_type": transaction_type,
                "total_points": total_points or 0,
                "transaction_count": count,
                "average_per_transaction": (total_points or 0) / count if count > 0 else 0
            })
        
        # Top users by points
        top_users = db.query(
            models.User.username,
            models.User.email,
            models.UserPoint.current_points,
            models.UserPoint.total_points
        ).join(
            models.UserPoint, models.User.id == models.UserPoint.user_id
        ).filter(
            models.User.created_by == created_by_str
        ).order_by(models.UserPoint.current_points.desc()).limit(10).all()
        
        top_users_data = []
        for username, email, current_points, total_points in top_users:
            top_users_data.append({
                "username": username,
                "email": email,
                "current_points": current_points,
                "total_points": total_points
            })
        
        # Point usage trends (last 30 days)
        usage_trend = []
        for i in range(30):
            date = datetime.utcnow() - timedelta(days=i)
            start_of_day = date.replace(hour=0, minute=0, second=0, microsecond=0)
            end_of_day = start_of_day + timedelta(days=1)
            
            points_used = db.query(func.sum(models.PointTransaction.points)).join(
                models.User, models.PointTransaction.giver_id == models.User.id
            ).filter(
                models.User.created_by == created_by_str,
                models.PointTransaction.created_at >= start_of_day,
                models.PointTransaction.created_at < end_of_day,
                models.PointTransaction.transaction_type == "deduction"
            ).scalar() or 0
            
            usage_trend.append({
                "date": start_of_day.strftime("%Y-%m-%d"),
                "points_used": points_used
            })
        
        return {
            "allocation_statistics": allocation_data,
            "top_users": top_users_data,
            "usage_trend": usage_trend,
            "generated_at": datetime.utcnow()
        }
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An error occurred while fetching point analytics"
        )
