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
        """
        Get the authenticated user's profile and account details.

        Returns:
        - Basic info (ID, username, email, role)
        - Point balance (available & total points)
        - Active supplier permissions
        - Account creation & update timestamps

        Notes:
        - Requires valid JWT authentication
        - Only returns data for the logged-in user

        Raises:
        - 401: Unauthorized (invalid or missing token)
        - 500: Database or internal error
        """

    try:
        # Get user points information
        user_points = (
            db.query(models.UserPoint)
            .filter(models.UserPoint.user_id == current_user.id)
            .first()
        )
        available_points = user_points.current_points if user_points else 0
        total_points = user_points.total_points if user_points else 0

        # Get active supplier permissions
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
        
    except Exception as e:
        # Handle any unexpected database or other errors
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"An error occurred while retrieving user information: {str(e)}"
        )


@router.post("/", response_model=UserResponse)
async def create_user(
    user_data: UserCreateRequest,
    current_user: Annotated[models.User, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
):
    """
    Create a new user account with role-based permissions.

    Only authorized users can create new accounts:
    - Super User → can create any role
    - Admin User → can create General Users only
    - General User → cannot create users

    Features:
    - Validates duplicate email/username
    - Hashes password securely (bcrypt)
    - Enforces role-based creation rules
    - Initializes user point account (0 points)
    - Tracks creator info for audit

    Raises:
    - 400: Invalid input
    - 403: Permission denied
    - 409: User already exists
    - 500: Database error
    """

    try:
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
        
    except HTTPException:
        # Re-raise HTTP exceptions as they are already properly formatted
        raise
    except Exception as e:
        # Handle any unexpected database or other errors
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"An error occurred while creating the user: {str(e)}"
        )


@router.post(
    "/create_super_user", response_model=SuperUserResponse
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
    "/create_admin_user", response_model=AdminUserResponse
)
def create_admin_user(
    admin_data: dict,
    current_user: Annotated[models.User, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
):
    """
    Create a new Admin User (Super User only).

    This endpoint allows Super Users to create new Admin accounts with 
    validated credentials and secure password hashing.

    Features:
    - Accessible only by Super Users
    - Validates duplicate username/email
    - Hashes password securely
    - Supports both service-based and fallback creation logic

    Raises:
    - 400: Invalid input or duplicate user
    - 403: Unauthorized (not a Super User)
    - 500: Unexpected database or internal error
    """

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


@router.post("/create_general_user", response_model=User)
def create_general_user(
    user_data: dict,
    current_user: Annotated[models.User, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
):
    """
    Create a new General User (Super User or Admin User only).

    This endpoint lets Super or Admin users create General User accounts 
    with proper validation and secure password hashing.

    Features:
    - Accessible by Super Users and Admin Users
    - Validates unique email and username
    - Hashes password securely
    - Tracks creator role and email

    Raises:
    - 400: Invalid input or duplicate user
    - 403: Unauthorized (not Super/Admin User)
    - 500: Internal or database error
    """

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


@router.post("/points/give")
def give_points(
    request: GivePointsRequest,
    current_user: Annotated[models.User, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
):
    """
    Allocate points from one user to another based on predefined packages.

    Authorized Roles:
    - Super User: Can give points to anyone (unlimited balance)
    - Admin User: Can give points only to General Users (deducts from balance)
    - General User: Cannot give points

    Point Packages:
    - ADMIN_USER_PACKAGE → 4,000,000
    - ONE_YEAR_PACKAGE → 1,000,000
    - ONE_MONTH_PACKAGE → 80,000
    - PER_REQUEST_POINT → 10,000
    - GUEST_POINT → 1,000

    Business Rules:
    - Admin → General only
    - Super Users → No point deduction
    - All transactions logged with audit trail

    Raises:
    - 400: Invalid package or insufficient balance
    - 403: Unauthorized role or permission
    - 404: Receiver not found
    - 500: Database error
    """

    
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
        
    except HTTPException:
        # Re-raise HTTP exceptions as they are already properly formatted
        raise
    except Exception as e:
        # Handle any unexpected database or other errors
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"An error occurred while allocating points: {str(e)}"
        )


@router.post("/reset_point/{user_id}/")
def reset_user_point(
    user_id: str,
    current_user: Annotated[models.User, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
):
    """
    Reset a user's points to zero.

    Roles Allowed:
        - super_user
        - admin_user

    Effects:
        - total_points → 0
        - current_points → 0
        - total_used_points → 0

    Raises:
        403 → Unauthorized role
        404 → User points not found
        500 → DB error
    """
    try:
        # Validate user permissions
        if current_user.role not in [
            models.UserRole.SUPER_USER,
            models.UserRole.ADMIN_USER,
        ]:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Only super_user or admin_user can reset points.",
            )

        # Find user points record
        user_points = (
            db.query(models.UserPoint).filter(models.UserPoint.user_id == user_id).first()
        )
        if not user_points:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="User points not found.",
            )

        # Reset all point values to zero
        user_points.total_points = 0
        user_points.current_points = 0
        user_points.total_used_points = 0
        db.commit()

        return {"message": f"Points for user {user_id} have been reset to 0."}
        
    except HTTPException:
        # Re-raise HTTP exceptions as they are already properly formatted
        raise
    except Exception as e:
        # Handle any unexpected database or other errors
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"An error occurred while resetting user points: {str(e)}"
        )


@router.get("/points/check/me")
def check_point_details(
    current_user: Annotated[models.User, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
):
    """
    Get the current user's point balance and transaction history.

    Returns:
        - total_points: Total earned points
        - current_points: Available points
        - total_points_used: Points spent
        - transactions:
            - get_point_history → Points received
            - uses_request_history → Points used for requests

    Roles:
        - All authenticated users

    Raises:
        401 → Unauthorized
        500 → Internal server/database error
    """
        # Get user points information
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

        # Group transactions by type
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
        
    except Exception as e:
        # Handle any unexpected database or other errors
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"An error occurred while retrieving point details: {str(e)}"
        )


@router.get("/check/all")
def check_all_users(
    page: Optional[int] = Query(None, ge=1, description="Page number for pagination"),
    limit: Optional[int] = Query(None, ge=1, le=100, description="Items per page"),
    search: Optional[str] = Query(None, description="Search by username or email"),
    current_user: Annotated[models.User, Depends(get_current_user)] = None,
    db: Annotated[Session, Depends(get_db)] = None,
):
    """
    Get all users created by the current user.

    Supports:
        - Pagination (page, limit)
        - Search (username/email)
        - Role filtering (SUPER_USER, ADMIN_USER)

    Returns:
        - root_user: Requesting user's info
        - super_users, admin_users, general_users
        - pagination: Page info (page, total, total_pages, etc.)

    Roles:
        - super_user
        - admin_user

    Raises:
        403 → Access denied for general users
        500 → Internal error
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


@router.get("/check/user_info/{user_id}")
def check_user_info(
    user_id: str,
    current_user: Annotated[models.User, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
):
    """
    Retrieve detailed info for a specific user.

    - Access restricted to SUPER_USER or ADMIN_USER.
    - Only returns info for users created by the current user.

    Returns:
    - User ID, username, email
    - Role, active status, created_by
    - Points summary (total, current, paid status, total RQ)
    - Recent activity status (using_rq_status)
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
    Retrieve the list of active suppliers accessible to the current user.

    - Admin/Super Users have access to all suppliers.
    - General Users get only their assigned suppliers.

    Returns:
    - Admin/Super Users: {"my_supplier": "Active all supplier."}
    - General Users: {"my_supplier": ["supplier1", "supplier2", ...]}

    Raises:
    - 404: If a General User has no suppliers assigned
    - 500: On unexpected errors (e.g., database issues)

    Role-Based Access:
    - SUPER_USER / ADMIN_USER: All suppliers
    - General User: Only assigned suppliers
    """

    try:
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
        
    except HTTPException:
        # Re-raise HTTP exceptions as they are already properly formatted
        raise
    except Exception as e:
        # Handle any unexpected database or other errors
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"An error occurred while retrieving supplier information: {str(e)}"
        )


@router.get("/get_list_of_available_suppliers")
def get_list_of_available_suppliers(
    current_user: Annotated[models.User, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
):
    """
    Retrieve a list of all available suppliers in the system.

    - Returns unique supplier names from provider mappings.
    - Useful for system overview, admin tasks, and UI supplier selection.

    Returns:
    - dict with:
        - total_supplier: Total count of unique suppliers
        - supplier_list: List of supplier names

    Raises:
    - 404: If no suppliers are found
    - 500: On unexpected errors (e.g., database issues)

    Access:
    - Any authenticated user can access this endpoint.
    """

    try:
        # Get all unique supplier names from provider mappings
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
        
    except HTTPException:
        # Re-raise HTTP exceptions as they are already properly formatted
        raise
    except Exception as e:
        # Handle any unexpected database or other errors
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"An error occurred while retrieving supplier list: {str(e)}"
        )


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
    Retrieve a paginated list of users with filtering and sorting.

    - Only accessible by SUPER_USER or ADMIN_USER.
    - Supports pagination, keyword search, role and active status filtering, and sorting.

    Parameters:
    - page (int): Page number (≥1)
    - limit (int): Items per page (1–100)
    - search (str, optional): Search by username or email
    - role (UserRole, optional): Filter by user role
    - is_active (bool, optional): Filter by active status
    - sort_by (str, optional): Field to sort by (default: "created_at")
    - sort_order (str, optional): "asc" or "desc" (default: "desc")
    - current_user (User): Authenticated user
    - db (Session): Database session

    Returns:
    - PaginatedUserResponse: Users list with pagination metadata

    Raises:
    - 403: If user is not SUPER_USER or ADMIN_USER
    - 400: Invalid query parameters
    - 500: Server error
    """

    
    # 🔒 SECURITY CHECK: Only super users and admin users can access user list
    if current_user.role not in [models.UserRole.SUPER_USER, models.UserRole.ADMIN_USER]:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access denied. Only super users and admin users can view user list."
        )
    
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
    Retrieve comprehensive user statistics for dashboard metrics.

    - Returns counts grouped by role, active status, and points distribution.
    - Useful for admin dashboards and reporting.

    Access:
    - Requires authentication.

    Returns:
    - UserStatistics: Aggregated statistics for all users.

    Raises:
    - 500: If an unexpected error occurs during data retrieval.
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
    Retrieve detailed information for a specific user.

    - Includes points summary, activity status, and recent transactions.
    - Access restricted to authorized users with permission to view the target user.

    Parameters:
    - user_id (str): The ID of the user to retrieve
    - current_user (User): Authenticated user
    - db (Session): Database session

    Returns:
    - UserDetailResponse: Detailed user information

    Raises:
    - 404: If user is not found or access is denied
    - 500: On unexpected server or database errors
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
    Retrieve user activity and analytics for a specified time period.

    - Returns activity data for the past `days` (default 30), including relevant metrics.
    - Access restricted to users authorized to view the target user's activity.

    Parameters:
    - user_id (str): ID of the user
    - days (int, optional): Number of days to look back (1–365, default 30)
    - current_user (User): Authenticated user
    - db (Session): Database session

    Returns:
    - UserActivityResponse: Activity data and analytics

    Raises:
    - 404: If user is not found or access is denied
    - 500: On unexpected server or database errors
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
    Perform bulk user operations (create, update, delete) in a single request.

    - Only SUPER_USER or ADMIN_USER can perform these operations.
    - Supports multiple operations with individual success/error tracking.

    Parameters:
    - operations (BulkUserOperationRequest): List of operations to perform
    - current_user (User): Authenticated user performing the operations
    - db (Session): Database session

    Returns:
    - dict: Summary of operations, including:
        - total_operations: Total requested
        - successful_operations: Count of successful operations
        - failed_operations: Count of failed operations
        - results: Details of successful operations
        - errors: Details of failed operations

    Raises:
    - 403: If current user lacks sufficient permissions
    - 500: On unexpected server or database errors
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
    Update an existing user with validation and partial updates.

    - Supports updating username, email, password, role, and active status.
    - Validates permissions and data before applying changes.

    Parameters:
    - user_id (str): ID of the user to update
    - user_updates (UserUpdateRequest): Fields to update
    - current_user (User): Authenticated user performing the update
    - db (Session): Database session

    Returns:
    - UserListResponse: The updated user information

    Raises:
    - 403: If current user lacks permission to update
    - 400: If input data is invalid
    - 404: If the user does not exist
    - 500: On unexpected server or database errors
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
    Delete a user and clean up all related data.

    - Removes user points, permissions, sessions, and other related records.
    - Access controlled: only authorized users can delete.

    Parameters:
    - user_id (str): ID of the user to delete
    - current_user (User): Authenticated user performing the deletion
    - db (Session): Database session

    Returns:
    - dict: Confirmation of deletion, including:
        - deleted_user_id
        - deleted_by
        - deleted_at
        - message

    Raises:
    - 403: If current user lacks permission
    - 400: If input data is invalid
    - 404: If the user does not exist
    - 500: On unexpected server or database errors
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
    Create a new user with enhanced validation and role checks.

    - Validates input data, role permissions, and uniqueness.
    - Provides detailed error handling for common issues.

    Parameters:
    - user_data (UserCreateRequest): Data for the new user
    - current_user (User): Authenticated user performing the creation
    - db (Session): Database session

    Returns:
    - UserListResponse: The newly created user information

    Raises:
    - 403: If current user lacks permission to create the user
    - 409: If a user with the same email or username already exists
    - 400: If input data is invalid
    - 500: On unexpected server or database errors
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

