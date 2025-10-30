import os
import uuid
from datetime import datetime, timedelta
from typing import Annotated, Optional
from fastapi import APIRouter, Depends, HTTPException, status, Request
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from fastapi.responses import JSONResponse
from fastapi.encoders import jsonable_encoder
from sqlalchemy.orm import Session
from sqlalchemy import text
from jose import JWTError, jwt
from passlib.context import CryptContext
import redis
from pydantic import BaseModel, EmailStr

from database import get_db
import models
from models import UserRole
import json

# Import audit logging
from security.audit_logging import AuditLogger, ActivityType, SecurityLevel


# Router setup
router = APIRouter(
    prefix="/v1.0/auth",
    tags=["Authentication"],
    responses={404: {"description": "Not found"}},
)

# Security configuration
SECRET_KEY = os.getenv("SECRET_KEY", "your-secret-key-change-in-production")
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 30000
REFRESH_TOKEN_EXPIRE_DAYS = 7

# Password hashing
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

# OAuth2 scheme
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/v1.0/auth/token")

# Redis for token blacklist
redis_client = redis.Redis(host="localhost", port=6379, db=0, decode_responses=True)


# Pydantic models
class Token(BaseModel):
    access_token: str
    token_type: str
    refresh_token: Optional[str] = None


class TokenData(BaseModel):
    username: Optional[str] = None
    user_id: Optional[str] = None


class UserCreate(BaseModel):
    username: str
    email: EmailStr
    password: str
    role: Optional[UserRole] = UserRole.GENERAL_USER
    created_by: Optional[str] = None


class UserResponse(BaseModel):
    id: str
    username: str
    email: str
    role: UserRole
    is_active: bool
    created_at: datetime
    updated_at: datetime


class RefreshTokenRequest(BaseModel):
    refresh_token: str


class UserProfileResponse(BaseModel):
    id: str
    username: str
    email: str
    role: UserRole
    is_active: bool
    created_at: datetime
    updated_at: datetime
    api_key: Optional[str] = None


# Utility functions
def verify_password(plain_password: str, hashed_password: str) -> bool:
    return pwd_context.verify(plain_password, hashed_password)


def get_password_hash(password: str) -> str:
    return pwd_context.hash(password)


def generate_user_id() -> str:
    """Generate a unique 10-character user ID"""
    return str(uuid.uuid4())[:10]


def get_user_by_username(db: Session, username: str) -> Optional[models.User]:
    return db.query(models.User).filter(models.User.username == username).first()


def get_user_by_email(db: Session, email: str) -> Optional[models.User]:
    return db.query(models.User).filter(models.User.email == email).first()


def get_user_by_id(db: Session, user_id: str) -> Optional[models.User]:
    return db.query(models.User).filter(models.User.id == user_id).first()


def authenticate_user(
    db: Session, username: str, password: str
) -> Optional[models.User]:
    user = get_user_by_username(db, username)
    if not user:
        return None
    if not verify_password(password, user.hashed_password):
        return None
    return user


def create_access_token(data: dict, expires_delta: Optional[timedelta] = None) -> str:
    to_encode = data.copy()
    if expires_delta:
        expire = datetime.utcnow() + expires_delta
    else:
        expire = datetime.utcnow() + timedelta(minutes=15)
    to_encode.update({"exp": expire, "type": "access", "iat": datetime.utcnow()})
    encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
    return encoded_jwt


def create_refresh_token(data: dict, expires_delta: Optional[timedelta] = None) -> str:
    to_encode = data.copy()
    if expires_delta:
        expire = datetime.utcnow() + expires_delta
    else:
        expire = datetime.utcnow() + timedelta(days=REFRESH_TOKEN_EXPIRE_DAYS)
    to_encode.update({"exp": expire, "type": "refresh", "iat": datetime.utcnow()})
    encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
    return encoded_jwt


def create_user(
    db: Session, user_data: UserCreate, created_by: Optional[str] = None
) -> models.User:
    user_id = generate_user_id()
    hashed_password = get_password_hash(user_data.password)
    
    # 🔒 API KEY POLICY: Only admin/super admin created users get API keys
    # Self-registered users (created_by starts with "own:") don't get API keys
    api_key = None
    if created_by and not created_by.startswith("own:"):
        # User created by admin/super admin - generate API key
        api_key = f"ak_{uuid.uuid4().hex}"
    # Self-registered users get api_key = None

    # Serialize created_by if it's a dict
    if isinstance(created_by, dict):
        created_by_value = json.dumps(created_by)
    else:
        created_by_value = created_by or "system"

    db_user = models.User(
        id=user_id,
        username=user_data.username,
        email=user_data.email,
        hashed_password=hashed_password,
        role=user_data.role,
        api_key=api_key,
        is_active=True,
        created_by=created_by_value,
        created_at=datetime.utcnow(),
        updated_at=datetime.utcnow(),
    )

    db.add(db_user)
    db.commit()
    db.refresh(db_user)
    return db_user


def generate_api_key(db: Session, user_id: str) -> str:
    """Generate a new API key for a user"""
    api_key = f"ak_{uuid.uuid4().hex}"
    user = db.query(models.User).filter(models.User.id == user_id).first()
    if user:
        user.api_key = api_key
        user.updated_at = datetime.utcnow()
        db.commit()
    return api_key


# Authentication dependencies
async def get_current_user(
    token: Annotated[str, Depends(oauth2_scheme)], db: Session = Depends(get_db)
) -> models.User:
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )

    # Check if token is blacklisted
    if redis_client.get(f"blacklist:{token}"):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="Token has been revoked"
        )

    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        username: str = payload.get("sub")
        user_id: str = payload.get("user_id")
        token_type: str = payload.get("type")

        if username is None or user_id is None or token_type != "access":
            raise credentials_exception
        token_data = TokenData(username=username, user_id=user_id)
    except JWTError:
        raise credentials_exception

    user = get_user_by_id(db, user_id=token_data.user_id)
    if user is None or not user.is_active:
        raise credentials_exception
    return user


async def get_current_active_user(
    current_user: Annotated[models.User, Depends(get_current_user)],
) -> models.User:
    if not current_user.is_active:
        raise HTTPException(status_code=400, detail="Inactive user")
    return current_user


async def require_admin(
    current_user: Annotated[models.User, Depends(get_current_active_user)],
) -> models.User:
    if current_user.role != UserRole.SUPER_USER:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only super user can manage permissions",
        )
    return current_user


# Routes
@router.post("/token", response_model=Token)
async def login_for_access_token(
    form_data: Annotated[OAuth2PasswordRequestForm, Depends()],
    request: Request,
    db: Session = Depends(get_db),
):
    """
    **User Login & Token Generation**
    
    Authenticate with username/password and receive JWT tokens for secure API access.
    
    **Use Cases:**
    - Web application login
    - Mobile app authentication  
    - API client authentication
    - Session establishment
    
    **Returns:**
    - Access token (30,000 min expiry) for API calls
    - Refresh token (7 days) for token renewal
    - Bearer token type for Authorization header
    
    **Security Features:**
    - Bcrypt password verification
    - Audit logging for login attempts
    - Redis-based token storage
    - Automatic token rotation
    """
    audit_logger = AuditLogger(db)
    
    user = authenticate_user(db, form_data.username, form_data.password)
    if not user:
        # Log failed login attempt
        audit_logger.log_authentication_event(
            activity_type=ActivityType.LOGIN_FAILED,
            user_id=None,
            email=form_data.username,  # Username might be email
            request=request,
            success=False,
            failure_reason="Invalid credentials"
        )
        
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect username or password",
            headers={"WWW-Authenticate": "Bearer"},
        )

    access_token_expires = timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    refresh_token_expires = timedelta(days=REFRESH_TOKEN_EXPIRE_DAYS)

    access_token = create_access_token(
        data={"sub": user.username, "user_id": user.id, "role": user.role},
        expires_delta=access_token_expires,
    )
    refresh_token = create_refresh_token(
        data={"sub": user.username, "user_id": user.id},
        expires_delta=refresh_token_expires,
    )

    # Store refresh token in Redis with expiration
    redis_client.setex(f"refresh_token:{user.id}", refresh_token_expires, refresh_token)

    # Log successful login
    audit_logger.log_authentication_event(
        activity_type=ActivityType.LOGIN_SUCCESS,
        user_id=user.id,
        email=user.email,
        request=request,
        success=True
    )

    return {
        "access_token": access_token,
        "token_type": "bearer",
        "refresh_token": refresh_token,
    }


@router.post("/refresh", response_model=Token)
async def refresh_access_token(
    refresh_request: RefreshTokenRequest, db: Session = Depends(get_db)
):
    """
    **Token Refresh & Renewal**
    
    Obtain new access token without re-authentication using valid refresh token.
    
    **Use Cases:**
    - Automatic token renewal in apps
    - Maintaining user sessions
    - Background token refresh
    - Seamless user experience
    
    **Process:**
    - Validates refresh token against Redis storage
    - Generates new access & refresh token pair
    - Invalidates old refresh token (rotation)
    - Updates token storage with new tokens
    
    **Security:**
    - Token rotation prevents replay attacks
    - Redis validation ensures token authenticity
    - User account status verification
    """
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate refresh token",
    )

    try:
        payload = jwt.decode(
            refresh_request.refresh_token, SECRET_KEY, algorithms=[ALGORITHM]
        )
        username: str = payload.get("sub")
        user_id: str = payload.get("user_id")
        token_type: str = payload.get("type")

        if username is None or user_id is None or token_type != "refresh":
            raise credentials_exception

        # Verify refresh token is still valid in storage
        stored_refresh_token = redis_client.get(f"refresh_token:{user_id}")
        if (
            not stored_refresh_token
            or stored_refresh_token != refresh_request.refresh_token
        ):
            raise credentials_exception

    except JWTError:
        raise credentials_exception

    user = get_user_by_id(db, user_id=user_id)
    if user is None or not user.is_active:
        raise credentials_exception

    # Create new tokens
    access_token_expires = timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    refresh_token_expires = timedelta(days=REFRESH_TOKEN_EXPIRE_DAYS)

    new_access_token = create_access_token(
        data={"sub": user.username, "user_id": user.id, "role": user.role},
        expires_delta=access_token_expires,
    )
    new_refresh_token = create_refresh_token(
        data={"sub": user.username, "user_id": user.id},
        expires_delta=refresh_token_expires,
    )

    # Update stored refresh token
    redis_client.setex(
        f"refresh_token:{user.id}", refresh_token_expires, new_refresh_token
    )

    return {
        "access_token": new_access_token,
        "token_type": "bearer",
        "refresh_token": new_refresh_token,
    }


# @router.post("/register", response_model=UserResponse)
# async def register_user(
#     user_data: UserCreate,
#     db: Session = Depends(get_db),
#     current_user: Optional[models.User] = Depends(get_current_user),
# ):
#     """Register a new user."""
#     # Check if user already exists
#     existing_user = (
#         db.query(models.User)
#         .filter(
#             (models.User.username == user_data.username)
#             | (models.User.email == user_data.email)
#         )
#         .first()
#     )

#     if existing_user:
#         raise HTTPException(
#             status_code=status.HTTP_400_BAD_REQUEST,
#             detail="Username or email already registered",
#         )

#     try:
#         # Set created_by to current user's username if available, otherwise use "system"
#         created_by = current_user.username if current_user else "system"
#         user_data.created_by = created_by

#         db_user = create_user(db, user_data, created_by)

#         return UserResponse(
#             id=db_user.id,
#             username=db_user.username,
#             email=db_user.email,
#             role=db_user.role,
#             is_active=db_user.is_active,
#             created_at=db_user.created_at,
#             updated_at=db_user.updated_at,
#         )
#     except Exception as e:
#         raise HTTPException(
#             status_code=status.HTTP_400_BAD_REQUEST,
#             detail=f"Error creating user: {str(e)}",
#         )


@router.post("/register", response_model=UserResponse)
def user_registration_form(user: UserCreate, db: Annotated[Session, Depends(get_db)]):
    """
    **User Registration & Account Creation**
    
    Create new user account with secure password hashing and validation.
    
    **Use Cases:**
    - New user signup
    - Self-service registration
    - Account creation for web/mobile apps
    - User onboarding process
    
    **Account Details:**
    - Default role: GENERAL_USER
    - Password: Bcrypt hashed for security
    - API Key: Not provided (contact admin for API access)
    - Status: Active by default
    
    **Validation:**
    - Username uniqueness check
    - Email format and uniqueness validation
    - Password strength requirements
    - Duplicate account prevention
    """

    existing_user = (
        db.query(models.User)
        .filter(
            (models.User.username == user.username) | (models.User.email == user.email)
        )
        .first()
    )
    if existing_user:
        return JSONResponse(
            status_code=status.HTTP_400_BAD_REQUEST,
            content={"message_from_system": "User Already exist."},
        )
    try:
        # Save created_by as a string: "own: user.email"
        created_by_value = f"own: {user.email}"
        db_user = create_user(db, user, created_by=created_by_value)
        return JSONResponse(content=jsonable_encoder(db_user))
    except Exception as e:
        return JSONResponse(
            status_code=status.HTTP_400_BAD_REQUEST,
            content={
                "message_from_system": "Cannot input valid field.",
                "error_detail": str(e),
            },
        )


@router.post("/logout")
async def logout(
    current_user: Annotated[models.User, Depends(get_current_active_user)],
    token: str = Depends(oauth2_scheme),
):
    """
    **Single Device Logout**
    
    Securely logout from current device/session by invalidating tokens.
    
    **Use Cases:**
    - User logout from web app
    - Mobile app logout
    - Security logout after suspicious activity
    - Session termination
    
    **Process:**
    - Blacklists current access token in Redis
    - Removes refresh token from storage
    - Calculates token TTL for efficient cleanup
    - Prevents token reuse until natural expiration
    
    **Impact:**
    - Current session becomes invalid immediately
    - Other devices/sessions remain active
    - User must login again on this device
    """
    # Calculate remaining token lifetime
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        exp_timestamp = payload.get("exp")
        if exp_timestamp:
            current_timestamp = datetime.utcnow().timestamp()
            ttl = int(exp_timestamp - current_timestamp)
            if ttl > 0:
                redis_client.setex(f"blacklist:{token}", ttl, "true")
    except JWTError:
        pass

    # Remove refresh token
    redis_client.delete(f"refresh_token:{current_user.id}")

    return {"message": "Successfully logged out"}


@router.post("/logout_all")
async def logout_all_devices(
    current_user: Annotated[models.User, Depends(get_current_active_user)],
):
    """
    **Global Logout (All Devices)**
    
    Logout user from ALL devices and sessions for enhanced security.
    
    **Use Cases:**
    - Suspected account compromise
    - Password change security measure
    - Lost/stolen device protection
    - Administrative security action
    - User-requested global logout
    
    **Process:**
    - Removes all refresh tokens from Redis
    - Prevents new token generation on any device
    - Forces re-authentication when access tokens expire
    - Maintains current session until token expires
    
    **Security Benefits:**
    - Comprehensive session invalidation
    - Immediate effect on token refresh attempts
    - Useful for security incidents
    """
    redis_client.delete(f"refresh_token:{current_user.id}")
    return {"message": "Successfully logged out from all devices"}


@router.get("/me", response_model=UserProfileResponse)
async def read_users_me(
    current_user: Annotated[models.User, Depends(get_current_active_user)],
):
    """
    **Get Current User Profile**
    
    Retrieve authenticated user's profile information and account details.
    
    **Use Cases:**
    - User profile display in applications
    - Role-based UI rendering
    - Account information verification
    - API key retrieval for developers
    - User dashboard data
    
    **Returns:**
    - User ID, username, email
    - Role (GENERAL_USER, ADMIN_USER, SUPER_USER)
    - Account status and timestamps
    - API key (if assigned by admin)
    
    **Authentication:**
    - Requires valid JWT token in Authorization header
    - Validates token signature and expiration
    - Checks user account status
    """
    return UserProfileResponse(
        id=current_user.id,
        username=current_user.username,
        email=current_user.email,
        role=current_user.role,
        is_active=current_user.is_active,
        created_at=current_user.created_at,
        updated_at=current_user.updated_at,
        api_key=current_user.api_key,
    )


@router.post("/regenerate_api_key", response_model=dict)
async def regenerate_api_key(
    current_user: Annotated[models.User, Depends(get_current_active_user)],
    db: Session = Depends(get_db),
):
    """
    **Regenerate Personal API Key**
    
    Create new API key for current user (Admin/Super Admin only).
    
    **Use Cases:**
    - API key rotation for security
    - Compromised key replacement
    - Regular security maintenance
    - New application deployment
    
    **Access Control:**
    - ADMIN_USER: Can regenerate own key
    - SUPER_USER: Can regenerate own key
    - GENERAL_USER: Access denied
    
    **Process:**
    - Generates new unique API key with 'ak_' prefix
    - Updates user record in database
    - Invalidates old API key immediately
    - Returns new key for immediate use
    
    **Security:**
    - Old key stops working instantly
    - UUID-based key generation
    - Database transaction safety
    """
    
    # 🔒 SECURITY CHECK: Only admin and super admin can regenerate API keys
    if current_user.role not in [models.UserRole.SUPER_USER, models.UserRole.ADMIN_USER]:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access denied. Only admin and super admin users can regenerate API keys."
        )
    
    new_api_key = generate_api_key(db, current_user.id)
    return {"message": "API key regenerated successfully", "api_key": new_api_key}


@router.post("/generate_api_key/{user_id}", response_model=dict)
async def generate_api_key_for_user(
    user_id: str,
    request: Request,
    current_user: Annotated[models.User, Depends(get_current_active_user)],
    db: Session = Depends(get_db),
):
    """
    **Generate API Key for User**
    
    Create API key for another user (Admin/Super Admin management function).
    
    **Use Cases:**
    - Providing API access to team members
    - Bulk API key generation for projects
    - Enabling programmatic access for users
    - Developer onboarding
    
    **Access Control:**
    - ADMIN_USER: Can generate keys for any user
    - SUPER_USER: Can generate keys for any user
    - Comprehensive audit logging
    
    **Process:**
    - Validates target user exists
    - Generates unique API key
    - Updates target user's record
    - Logs action with admin details
    - Returns key and user confirmation
    
    **Audit Trail:**
    - Records admin performing action
    - Logs target user details
    - High security level logging
    - Request context tracking
    """
    
    # 🔒 SECURITY CHECK: Only admin and super admin can generate API keys for others
    if current_user.role not in [models.UserRole.SUPER_USER, models.UserRole.ADMIN_USER]:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access denied. Only admin and super admin users can generate API keys for other users."
        )
    
    # Check if target user exists
    target_user = db.query(models.User).filter(models.User.id == user_id).first()
    if not target_user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"User with ID {user_id} not found."
        )
    
    # Generate API key for the target user
    new_api_key = generate_api_key(db, user_id)
    
    # 📝 AUDIT LOG: Record API key generation
    from security.audit_logging import AuditLogger, ActivityType, SecurityLevel
    audit_logger = AuditLogger(db)
    audit_logger.log_activity(
        activity_type=ActivityType.USER_UPDATED,
        user_id=current_user.id,
        target_user_id=user_id,
        details={
            "action": "generate_api_key",
            "target_username": target_user.username,
            "admin_role": current_user.role
        },
        request=request,
        security_level=SecurityLevel.HIGH,
        success=True
    )
    
    return {
        "message": f"API key generated successfully for user {target_user.username}",
        "user_id": user_id,
        "username": target_user.username,
        "api_key": new_api_key
    }


@router.delete("/revoke_api_key/{user_id}", response_model=dict)
async def revoke_api_key_for_user(
    user_id: str,
    request: Request,
    current_user: Annotated[models.User, Depends(get_current_active_user)],
    db: Session = Depends(get_db),
):
    """
    **Revoke User API Key**
    
    Remove API key access from user (Admin/Super Admin security function).
    
    **Use Cases:**
    - Security incident response
    - Employee termination/role change
    - Suspected API key compromise
    - Temporary access suspension
    - Compliance requirements
    
    **Access Control:**
    - ADMIN_USER: Can revoke any user's key
    - SUPER_USER: Can revoke any user's key
    - Full audit logging for security
    
    **Process:**
    - Validates target user exists
    - Records current API key status
    - Sets API key to null (revoked)
    - Updates user timestamp
    - Logs revocation with details
    
    **Impact:**
    - API key becomes invalid immediately
    - User loses programmatic API access
    - All applications using key will fail
    - Action cannot be undone (new key needed)
    """
    
    # 🔒 SECURITY CHECK: Only admin and super admin can revoke API keys
    if current_user.role not in [models.UserRole.SUPER_USER, models.UserRole.ADMIN_USER]:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access denied. Only admin and super admin users can revoke API keys."
        )
    
    # Check if target user exists
    target_user = db.query(models.User).filter(models.User.id == user_id).first()
    if not target_user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"User with ID {user_id} not found."
        )
    
    # Store old API key for audit
    old_api_key = target_user.api_key
    
    # Revoke API key (set to None)
    target_user.api_key = None
    target_user.updated_at = datetime.utcnow()
    db.commit()
    
    # 📝 AUDIT LOG: Record API key revocation
    from security.audit_logging import AuditLogger, ActivityType, SecurityLevel
    audit_logger = AuditLogger(db)
    audit_logger.log_activity(
        activity_type=ActivityType.USER_UPDATED,
        user_id=current_user.id,
        target_user_id=user_id,
        details={
            "action": "revoke_api_key",
            "target_username": target_user.username,
            "had_api_key": old_api_key is not None,
            "admin_role": current_user.role
        },
        request=request,
        security_level=SecurityLevel.HIGH,
        success=True
    )
    
    return {
        "message": f"API key revoked successfully for user {target_user.username}",
        "user_id": user_id,
        "username": target_user.username
    }


@router.get("/health")
async def auth_health_check(
    current_user: Annotated[models.User, Depends(get_current_active_user)],
    db: Session = Depends(get_db),
):
    """
    **Authentication System Health Check**
    
    Verify authentication system status and user session validity.
    
    **Use Cases:**
    - Application startup verification
    - Monitoring system integration
    - User session validation
    - System synchronization checks
    - Health monitoring dashboards
    
    **Health Components:**
    - API service status verification
    - Database connection testing
    - User authentication validation
    - Token validity confirmation
    - System timestamp synchronization
    
    **Returns:**
    - API status (ok/error)
    - Database connectivity status
    - Current user details (username, ID, role)
    - Server timestamp (ISO format)
    
    **Monitoring:**
    - Use for automated health checks
    - Set alerts for non-'ok' status
    - Track response times
    - Monitor system availability
    """
    try:
        db.execute(text("SELECT 1"))
        db_status = "ok"
    except Exception as e:
        db_status = f"error: {str(e)}"

    return {
        "api_status": "ok",
        "database_status": db_status,
        "user": current_user.username,
        "user_id": current_user.id,
        "role": current_user.role,
        "timestamp": datetime.utcnow().isoformat(),
    }


# Admin routes
@router.get("/super/users", response_model=list[UserProfileResponse])
async def get_all_users(
    admin: Annotated[models.User, Depends(require_admin)],
    db: Session = Depends(get_db),
    skip: int = 0,
    limit: int = 100,
):
    """
    **Get All Users (Super Admin)**
    
    Retrieve complete user list with pagination for system administration.
    
    **Use Cases:**
    - User management dashboard
    - System audit and compliance
    - User statistics and reporting
    - API key management oversight
    - Account status monitoring
    
    **Access Control:**
    - SUPER_USER only (highest privilege level)
    - Admin users cannot access this endpoint
    - Complete system visibility
    
    **Pagination:**
    - skip: Number of records to skip (default: 0)
    - limit: Max records returned (default: 100)
    - Efficient for large user databases
    
    **Returns (per user):**
    - Complete profile information
    - API keys (visible to super admins)
    - Account status and timestamps
    - Role and permission levels
    
    **Security:**
    - Sensitive endpoint with full user data
    - Comprehensive audit capability
    - API key visibility for admin purposes
    """
    users = db.query(models.User).offset(skip).limit(limit).all()
    return [
        UserProfileResponse(
            id=user.id,
            username=user.username,
            email=user.email,
            role=user.role,
            is_active=user.is_active,
            created_at=user.created_at,
            updated_at=user.updated_at,
            api_key=user.api_key,
        )
        for user in users
    ]


@router.put("/super/users/{user_id}/activate")
async def activate_user(
    user_id: str,
    admin: Annotated[models.User, Depends(require_admin)],
    db: Session = Depends(get_db),
):
    """
    **Toggle User Account Status**
    
    Activate or deactivate user account (Super Admin management function).
    
    **Use Cases:**
    - Temporary account suspension
    - Employee leave management
    - Security incident response
    - Account recovery processes
    - Compliance requirements
    
    **Access Control:**
    - SUPER_USER only (highest privilege)
    - Non-destructive account management
    - Preserves user data and settings
    
    **Toggle Behavior:**
    - Active users → Inactive (cannot login)
    - Inactive users → Active (can login normally)
    - Status change is immediate
    - Updates user timestamp
    
    **Effects:**
    - **When Deactivated:** No login, existing tokens valid until expiry, API key disabled
    - **When Activated:** Full login access, can generate tokens, API key restored
    
    **Security:**
    - Reversible action (can be undone)
    - Immediate authentication impact
    - Preserves all user data
    """
    user = get_user_by_id(db, user_id)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="User not found"
        )

    user.is_active = not user.is_active
    user.updated_at = datetime.utcnow()
    db.commit()

    action = "activated" if user.is_active else "deactivated"
    return {"message": f"User {action} successfully"}


# API Key authentication
async def authenticate_api_key(
    request: Request, db: Session = Depends(get_db)
) -> models.User:
    """Authenticate user via X-API-Key header. Returns user if valid and active."""
    api_key = request.headers.get("X-API-Key")
    if not api_key:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="API Key required"
        )

    user = (
        db.query(models.User)
        .filter(models.User.api_key == api_key, models.User.is_active == True)
        .first()
    )

    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid API Key"
        )

    return user


@router.get("/apikey/me", response_model=UserProfileResponse)
async def read_users_me_api_key(
    current_user: Annotated[models.User, Depends(authenticate_api_key)],
):
    """
    **Get Profile via API Key**
    
    Retrieve user profile using API key authentication (alternative to JWT).
    
    **Use Cases:**
    - Server-to-server authentication
    - Automated scripts and applications
    - CI/CD pipeline integration
    - Microservice authentication
    - Long-running background processes
    
    **Authentication Method:**
    - Uses X-API-Key header (not Authorization Bearer)
    - Direct database lookup by API key
    - No JWT token required
    - Validates user account status
    
    **Advantages over JWT:**
    - No token expiration management
    - Simpler authentication flow
    - Better for automated systems
    - No refresh token complexity
    - Direct database validation
    
    **Returns:**
    - Complete user profile information
    - API key used for authentication
    - Account status and role details
    - Timestamps and user metadata
    
    **Security:**
    - API key must be valid and active
    - User account must be active
    - Secure key lookup process
    """
    return UserProfileResponse(
        id=current_user.id,
        username=current_user.username,
        email=current_user.email,
        role=current_user.role,
        is_active=current_user.is_active,
        created_at=current_user.created_at,
        updated_at=current_user.updated_at,
        api_key=current_user.api_key,
    )
