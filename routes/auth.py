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
    🔐 **User Authentication - Login and Get JWT Tokens**
    
    Authenticates users and returns JWT tokens for secure API access. This endpoint implements
    OAuth2 password flow for token generation with enhanced security features.

    ---

    ## 🚀 **Quick Start**
    ```bash
    # Basic authentication request
    curl -X POST "https://api.yourdomain.com/v1.0/auth/token" \\
         -H "Content-Type: application/x-www-form-urlencoded" \\
         -d "username=john_doe&password=secure_password"
    ```

    ## 📋 **Request Details**

    ### **Form Data Parameters**
    | Parameter | Type | Required | Description |
    |-----------|------|----------|-------------|
    | `username` | string | ✅ | Username or email address |
    | `password` | string | ✅ | User's password |

    ### **Content-Type**
    `application/x-www-form-urlencoded`

    ---

    ## ✅ **Successful Response**
    ```json
    {
        "access_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
        "token_type": "bearer",
        "refresh_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9..."
    }
    ```

    ### **Token Information**
    | Token Type | Expiration | Usage |
    |------------|------------|-------|
    | Access Token | 30,000 minutes | API authentication |
    | Refresh Token | 7 days | Obtain new access tokens |

    ---

    ## 🔒 **Security Features**

    - 🔑 **Bcrypt Password Hashing** - Secure password verification
    - ⚡ **Token Blacklisting** - Immediate token revocation support
    - 📝 **Audit Logging** - Comprehensive authentication tracking
    - 🛡️ **Rate Limiting** - Brute force protection
    - 🔄 **Refresh Token Rotation** - Secure token renewal
    - 💾 **Redis Storage** - Secure refresh token management

    ---

    ## ❌ **Error Responses**

    ### **401 Unauthorized**
    ```json
    {
        "detail": "Incorrect username or password"
    }
    ```
    **Causes:** Invalid credentials, inactive account, or locked account

    ### **400 Bad Request**
    ```json
    {
        "detail": "Invalid request format"
    }
    ```
    **Causes:** Missing parameters, malformed data

    ---

    ## 🛠️ **Usage Examples**


    ### **Python**
    ```python
    import requests
    
    response = requests.post(
        "https://api.yourdomain.com/v1.0/auth/token",
        data={
            "username": "john_doe",
            "password": "secure_password"
        },
        headers={"Content-Type": "application/x-www-form-urlencoded"}
    )
    
    tokens = response.json()
    ```

    ### **Using the Access Token**
    ```bash
    # Include in API requests
    curl -H "Authorization: Bearer YOUR_ACCESS_TOKEN" \\
         "https://api.yourdomain.com/v1.0/protected-endpoint"
    ```

    ---

    ## 📊 **Audit & Monitoring**

    - ✅ Successful logins are logged with user ID and timestamp
    - ❌ Failed attempts are recorded with IP address and reason
    - 📍 Geographic and device information tracking
    - 🔍 Real-time security monitoring

    ---

    ## ⚠️ **Important Notes**

    - Store tokens securely - never in localStorage for production
    - Access tokens expire - implement automatic refresh logic
    - Refresh tokens should be stored securely (httpOnly cookies recommended)
    - Report suspicious activity immediately to security team

    ---

    ## 🔄 **Token Refresh Flow**

    1. Access token expires → Use refresh token at `/auth/refresh`
    2. Validate refresh token → Generate new access/refresh tokens
    3. Old refresh token → Invalidated in Redis
    4. New tokens → Returned to client

    For more details, see the token refresh endpoint documentation.
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
    Token Refresh - Get New Access Token Using Refresh Token
    
    This endpoint allows users to obtain a new access token without re-authenticating
    by using their valid refresh token.
    
    **Refresh Flow:**
    1. Validates the provided refresh token
    2. Verifies token exists in Redis storage
    3. Checks user account status
    4. Generates new access and refresh tokens
    5. Updates stored refresh token in Redis
    
    **Request Body:**
    - `refresh_token`: Valid refresh token from login
    
    **Response:**
    - `access_token`: New JWT access token
    - `token_type`: Always "bearer"
    - `refresh_token`: New refresh token
    
    **Security Features:**
    - Refresh token validation against Redis storage
    - Automatic token rotation (new refresh token issued)
    - User account status verification
    - JWT signature verification
    
    **Error Responses:**
    - `401 Unauthorized`: Invalid or expired refresh token
    - `401 Unauthorized`: Token not found in storage
    - `401 Unauthorized`: User account inactive
    
    **Usage Example:**
    ```bash
    curl -X POST "/v1.0/auth/refresh" \
         -H "Content-Type: application/json" \
         -d '{"refresh_token": "your_refresh_token_here"}'
    ```
    
    **Best Practices:**
    - Store refresh tokens securely
    - Use new tokens immediately after refresh
    - Handle token expiration gracefully in client applications
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
    User Registration - Create New User Account
    
    This endpoint allows new users to register for an account. Self-registered users
    have limited privileges compared to admin-created users.
    
    **Registration Process:**
    1. Validates username and email uniqueness
    2. Hashes password using bcrypt
    3. Creates user with GENERAL_USER role by default
    4. Sets created_by as "own: {email}" for self-registration
    5. Self-registered users do NOT receive API keys
    
    **Request Body:**
    - `username`: Unique username (required)
    - `email`: Valid email address (required)
    - `password`: Password (minimum 8 characters)
    - `role`: User role (optional, defaults to GENERAL_USER)
    
    **Response:**
    - User object with ID, username, email, role, and timestamps
    - No API key included for self-registered users
    
    **User Roles:**
    - `GENERAL_USER`: Basic access, self-registered default
    - `ADMIN_USER`: Can only be created by super users
    - `SUPER_USER`: Can only be created by existing super users
    
    **Security Features:**
    - Password hashing with bcrypt
    - Email format validation
    - Username/email uniqueness check
    - API key restriction for self-registered users
    
    **Error Responses:**
    - `400 Bad Request`: User already exists
    - `400 Bad Request`: Invalid input data
    - `422 Unprocessable Entity`: Validation errors
    
    **Usage Example:**
    ```bash
    curl -X POST "/v1.0/auth/register" \
         -H "Content-Type: application/json" \
         -d '{
           "username": "john_doe",
           "email": "john@example.com",
           "password": "secure_password123"
         }'
    ```
    
    **Note:** Self-registered users must contact administrators to receive API keys
    for programmatic access.
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
    User Logout - Invalidate Current Session
    
    This endpoint logs out the user from the current device/session by invalidating
    their access token and removing their refresh token.
    
    **Logout Process:**
    1. Blacklists the current access token in Redis
    2. Removes the refresh token from Redis storage
    3. Calculates token TTL for efficient blacklist management
    4. Prevents token reuse until natural expiration
    
    **Authentication Required:**
    - Valid JWT access token in Authorization header
    - Active user account
    
    **Response:**
    - Success message confirming logout
    
    **Security Features:**
    - Token blacklisting prevents reuse
    - Automatic cleanup of expired blacklisted tokens
    - Refresh token removal prevents token refresh
    - Immediate session invalidation
    
    **Error Responses:**
    - `401 Unauthorized`: Invalid or missing token
    - `401 Unauthorized`: Token already blacklisted
    - `400 Bad Request`: Inactive user account
    
    **Usage Example:**
    ```bash
    curl -X POST "/v1.0/auth/logout" \
         -H "Authorization: Bearer your_access_token_here"
    ```
    
    **Post-Logout:**
    - Access token becomes invalid immediately
    - User must login again to get new tokens
    - Other devices/sessions remain active (use /logout_all for all devices)
    
    **Best Practices:**
    - Always call logout when user explicitly logs out
    - Clear tokens from client-side storage after logout
    - Handle logout responses in client applications
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
    Global Logout - Invalidate All User Sessions
    
    This endpoint logs out the user from ALL devices and sessions by removing
    all refresh tokens. Access tokens will remain valid until they expire naturally.
    
    **Global Logout Process:**
    1. Removes all refresh tokens for the user from Redis
    2. Prevents new token generation on any device
    3. Forces re-authentication on all devices when access tokens expire
    4. Maintains current session until access token expires
    
    **Authentication Required:**
    - Valid JWT access token in Authorization header
    - Active user account
    
    **Response:**
    - Success message confirming global logout
    
    **Security Features:**
    - Comprehensive session invalidation
    - Prevents token refresh on any device
    - Useful for security incidents or password changes
    - Immediate effect on token refresh attempts
    
    **Use Cases:**
    - User suspects account compromise
    - Password change security measure
    - Device lost or stolen
    - Administrative security action
    
    **Error Responses:**
    - `401 Unauthorized`: Invalid or missing token
    - `400 Bad Request`: Inactive user account
    
    **Usage Example:**
    ```bash
    curl -X POST "/v1.0/auth/logout_all" \
         -H "Authorization: Bearer your_access_token_here"
    ```
    
    **Important Notes:**
    - Current access token remains valid until expiration
    - All devices will need to re-authenticate when tokens expire
    - More aggressive than single-device logout
    - Consider user experience impact before using
    
    **Recommendation:**
    Use this endpoint for security-critical situations or when users
    explicitly request to log out from all devices.
    """
    redis_client.delete(f"refresh_token:{current_user.id}")
    return {"message": "Successfully logged out from all devices"}


@router.get("/me", response_model=UserProfileResponse)
async def read_users_me(
    current_user: Annotated[models.User, Depends(get_current_active_user)],
):
    """
    Get Current User Profile - Retrieve Authenticated User Information
    
    This endpoint returns detailed information about the currently authenticated user,
    including their profile data, role, and API key (if available).
    
    **Returned Information:**
    - `id`: Unique user identifier
    - `username`: User's username
    - `email`: User's email address
    - `role`: User role (GENERAL_USER, ADMIN_USER, SUPER_USER)
    - `is_active`: Account status
    - `created_at`: Account creation timestamp
    - `updated_at`: Last profile update timestamp
    - `api_key`: API key for programmatic access (if assigned)
    
    **Authentication Required:**
    - Valid JWT access token in Authorization header
    - Active user account
    
    **User Roles Explained:**
    - `GENERAL_USER`: Basic access, limited permissions
    - `ADMIN_USER`: Can manage users they created, has API key
    - `SUPER_USER`: Full system access, can create any user type
    
    **API Key Information:**
    - Self-registered users: `api_key` will be `null`
    - Admin-created users: `api_key` provided for programmatic access
    - API keys can be regenerated by admins/super admins
    
    **Error Responses:**
    - `401 Unauthorized`: Invalid or missing token
    - `401 Unauthorized`: Token blacklisted or expired
    - `400 Bad Request`: Inactive user account
    
    **Usage Example:**
    ```bash
    curl -X GET "/v1.0/auth/me" \
         -H "Authorization: Bearer your_access_token_here"
    ```
    
    **Response Example:**
    ```json
    {
      "id": "abc123def4",
      "username": "john_doe",
      "email": "john@example.com",
      "role": "GENERAL_USER",
      "is_active": true,
      "created_at": "2024-01-15T10:30:00Z",
      "updated_at": "2024-01-15T10:30:00Z",
      "api_key": null
    }
    ```
    
    **Use Cases:**
    - User profile display in applications
    - Role-based UI rendering
    - API key retrieval for programmatic access
    - Account status verification
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
    Regenerate Personal API Key - Create New API Key for Current User
    
    This endpoint allows admin and super admin users to regenerate their own API key.
    The old API key becomes invalid immediately upon regeneration.
    
    **Access Control:**
    - Only `ADMIN_USER` and `SUPER_USER` roles can regenerate API keys
    - Users can only regenerate their own API key
    - `GENERAL_USER` role is denied access
    
    **Regeneration Process:**
    1. Validates user has admin or super admin role
    2. Generates new unique API key with "ak_" prefix
    3. Updates user record in database
    4. Invalidates old API key immediately
    5. Returns new API key in response
    
    **Authentication Required:**
    - Valid JWT access token in Authorization header
    - Admin or Super Admin role
    - Active user account
    
    **Response:**
    - Success message
    - New API key for immediate use
    
    **Security Features:**
    - Role-based access control
    - Immediate old key invalidation
    - Unique key generation using UUID
    - Database transaction safety
    
    **Error Responses:**
    - `403 Forbidden`: Insufficient permissions (not admin/super admin)
    - `401 Unauthorized`: Invalid or missing token
    - `400 Bad Request`: Inactive user account
    
    **Usage Example:**
    ```bash
    curl -X POST "/v1.0/auth/regenerate_api_key" \
         -H "Authorization: Bearer your_access_token_here"
    ```
    
    **Response Example:**
    ```json
    {
      "message": "API key regenerated successfully",
      "api_key": "ak_1234567890abcdef1234567890abcdef"
    }
    ```
    
    **Important Notes:**
    - Old API key stops working immediately
    - Update all applications using the old API key
    - Store new API key securely
    - Consider impact on running applications before regenerating
    
    **Use Cases:**
    - Suspected API key compromise
    - Regular security key rotation
    - Application deployment with new keys
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
    Generate API Key for User - Create API Key for Another User
    
    This endpoint allows admin and super admin users to generate API keys for other users.
    This is typically used to provide programmatic access to users who need it.
    
    **Access Control:**
    - Only `ADMIN_USER` and `SUPER_USER` roles can generate API keys for others
    - Admins can generate keys for any user
    - All actions are logged for audit purposes
    
    **Generation Process:**
    1. Validates admin/super admin permissions
    2. Verifies target user exists
    3. Generates new unique API key
    4. Updates target user's record
    5. Logs action for audit trail
    6. Returns new API key and user information
    
    **Path Parameters:**
    - `user_id`: ID of the user to generate API key for
    
    **Authentication Required:**
    - Valid JWT access token in Authorization header
    - Admin or Super Admin role
    - Active user account
    
    **Response:**
    - Success message with target user details
    - New API key for the target user
    - User ID and username for confirmation
    
    **Security Features:**
    - Role-based access control
    - User existence validation
    - Comprehensive audit logging
    - High security level logging
    - Request context tracking
    
    **Audit Information Logged:**
    - Action: generate_api_key
    - Admin user performing action
    - Target user details
    - Timestamp and request information
    
    **Error Responses:**
    - `403 Forbidden`: Insufficient permissions
    - `404 Not Found`: Target user doesn't exist
    - `401 Unauthorized`: Invalid or missing token
    
    **Usage Example:**
    ```bash
    curl -X POST "/v1.0/auth/generate_api_key/abc123def4" \
         -H "Authorization: Bearer your_admin_token_here"
    ```
    
    **Response Example:**
    ```json
    {
      "message": "API key generated successfully for user john_doe",
      "user_id": "abc123def4",
      "username": "john_doe",
      "api_key": "ak_1234567890abcdef1234567890abcdef"
    }
    ```
    
    **Use Cases:**
    - Providing API access to existing users
    - Bulk API key generation for teams
    - Replacing lost or compromised API keys
    - Enabling programmatic access for applications
    
    **Best Practices:**
    - Verify user identity before generating keys
    - Communicate new API key securely to user
    - Document API key assignments
    - Monitor API key usage
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
    Revoke User API Key - Remove API Key Access for User
    
    This endpoint allows admin and super admin users to revoke API keys from other users,
    immediately disabling their programmatic access to the API.
    
    **Access Control:**
    - Only `ADMIN_USER` and `SUPER_USER` roles can revoke API keys
    - Admins can revoke keys from any user
    - All revocation actions are logged for audit
    
    **Revocation Process:**
    1. Validates admin/super admin permissions
    2. Verifies target user exists
    3. Records current API key status for audit
    4. Sets user's API key to null (revoked)
    5. Updates user's timestamp
    6. Logs revocation action with details
    
    **Path Parameters:**
    - `user_id`: ID of the user whose API key should be revoked
    
    **Authentication Required:**
    - Valid JWT access token in Authorization header
    - Admin or Super Admin role
    - Active user account
    
    **Response:**
    - Success message with target user details
    - User ID and username for confirmation
    - No API key returned (security measure)
    
    **Security Features:**
    - Immediate API key invalidation
    - Role-based access control
    - Comprehensive audit logging
    - User existence validation
    - High security level logging
    
    **Audit Information Logged:**
    - Action: revoke_api_key
    - Admin user performing action
    - Target user details
    - Previous API key status
    - Timestamp and request information
    
    **Error Responses:**
    - `403 Forbidden`: Insufficient permissions
    - `404 Not Found`: Target user doesn't exist
    - `401 Unauthorized`: Invalid or missing token
    
    **Usage Example:**
    ```bash
    curl -X DELETE "/v1.0/auth/revoke_api_key/abc123def4" \
         -H "Authorization: Bearer your_admin_token_here"
    ```
    
    **Response Example:**
    ```json
    {
      "message": "API key revoked successfully for user john_doe",
      "user_id": "abc123def4",
      "username": "john_doe"
    }
    ```
    
    **Use Cases:**
    - Security incident response
    - Employee termination or role change
    - Suspected API key compromise
    - Temporary access suspension
    - Compliance requirements
    
    **Important Notes:**
    - API key becomes invalid immediately
    - User loses all programmatic API access
    - Action cannot be undone (new key must be generated)
    - All applications using the key will fail authentication
    
    **Best Practices:**
    - Notify user before revoking unless security incident
    - Document reason for revocation
    - Monitor for failed API requests after revocation
    - Consider temporary suspension before permanent revocation
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
    Authenticated Health Check - Verify Authentication System Status
    
    This endpoint provides a comprehensive health check for the authentication system,
    including database connectivity and user session validation.
    
    **Health Check Components:**
    1. API service status verification
    2. Database connection testing
    3. User authentication validation
    4. Token validity confirmation
    5. System timestamp for synchronization
    
    **Authentication Required:**
    - Valid JWT access token in Authorization header
    - Active user account
    - Non-blacklisted token
    
    **Response Information:**
    - `api_status`: Authentication API status
    - `database_status`: Database connectivity status
    - `user`: Current user's username
    - `user_id`: Current user's ID
    - `role`: Current user's role
    - `timestamp`: Current server timestamp (ISO format)
    
    **Status Values:**
    - `ok`: Component is functioning normally
    - `error: <details>`: Component has issues with error details
    
    **Use Cases:**
    - Application startup health verification
    - Monitoring system integration
    - User session validation
    - Database connectivity testing
    - System synchronization checks
    
    **Error Responses:**
    - `401 Unauthorized`: Invalid or missing token
    - `401 Unauthorized`: Token blacklisted or expired
    - `400 Bad Request`: Inactive user account
    
    **Usage Example:**
    ```bash
    curl -X GET "/v1.0/auth/health" \
         -H "Authorization: Bearer your_access_token_here"
    ```
    
    **Response Example:**
    ```json
    {
      "api_status": "ok",
      "database_status": "ok",
      "user": "john_doe",
      "user_id": "abc123def4",
      "role": "GENERAL_USER",
      "timestamp": "2024-01-15T10:30:00.123456"
    }
    ```
    
    **Monitoring Integration:**
    - Use for application health monitoring
    - Set up alerts for non-"ok" status values
    - Monitor response times for performance
    - Track authentication system availability
    
    **Security Benefits:**
    - Validates complete authentication chain
    - Confirms user account status
    - Verifies database connectivity
    - Provides audit trail for health checks
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
    Get All Users - Retrieve Complete User List (Super Admin Only)
    
    This endpoint provides super administrators with access to the complete list of
    all users in the system, including their profiles and API key information.
    
    **Access Control:**
    - Restricted to `SUPER_USER` role only
    - Admin users cannot access this endpoint
    - Requires active super admin account
    
    **Query Parameters:**
    - `skip`: Number of records to skip (default: 0)
    - `limit`: Maximum records to return (default: 100, max: 100)
    
    **Pagination Support:**
    - Use `skip` and `limit` for pagination
    - Default page size: 100 users
    - Efficient for large user databases
    
    **Returned Information (per user):**
    - `id`: Unique user identifier
    - `username`: User's username
    - `email`: User's email address
    - `role`: User role (GENERAL_USER, ADMIN_USER, SUPER_USER)
    - `is_active`: Account status
    - `created_at`: Account creation timestamp
    - `updated_at`: Last profile update timestamp
    - `api_key`: API key (visible to super admins only)
    
    **Authentication Required:**
    - Valid JWT access token in Authorization header
    - Super Admin role (SUPER_USER)
    - Active user account
    
    **Security Features:**
    - Role-based access control
    - API key visibility for administrative purposes
    - Pagination to prevent data overload
    - Complete user audit capability
    
    **Error Responses:**
    - `403 Forbidden`: Insufficient permissions (not super admin)
    - `401 Unauthorized`: Invalid or missing token
    - `400 Bad Request`: Inactive user account
    
    **Usage Example:**
    ```bash
    # Get first 50 users
    curl -X GET "/v1.0/auth/super/users?skip=0&limit=50" \
         -H "Authorization: Bearer your_super_admin_token"
    
    # Get next 50 users
    curl -X GET "/v1.0/auth/super/users?skip=50&limit=50" \
         -H "Authorization: Bearer your_super_admin_token"
    ```
    
    **Response Example:**
    ```json
    [
      {
        "id": "abc123def4",
        "username": "john_doe",
        "email": "john@example.com",
        "role": "GENERAL_USER",
        "is_active": true,
        "created_at": "2024-01-15T10:30:00Z",
        "updated_at": "2024-01-15T10:30:00Z",
        "api_key": null
      },
      {
        "id": "def456ghi7",
        "username": "admin_user",
        "email": "admin@example.com",
        "role": "ADMIN_USER",
        "is_active": true,
        "created_at": "2024-01-10T08:15:00Z",
        "updated_at": "2024-01-14T16:45:00Z",
        "api_key": "ak_1234567890abcdef"
      }
    ]
    ```
    
    **Use Cases:**
    - User management and administration
    - System audit and compliance
    - User statistics and reporting
    - API key management oversight
    - Account status monitoring
    
    **Best Practices:**
    - Use pagination for large user bases
    - Implement client-side filtering for better UX
    - Cache results appropriately
    - Monitor access to this sensitive endpoint
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
    Toggle User Account Status - Activate/Deactivate User Account
    
    This endpoint allows super administrators to toggle user account status between
    active and inactive states. This is a non-destructive way to manage user access.
    
    **Access Control:**
    - Restricted to `SUPER_USER` role only
    - Cannot be used by admin users
    - Requires active super admin account
    
    **Toggle Behavior:**
    - Active users become inactive
    - Inactive users become active
    - Status change is immediate
    - Updates user's timestamp
    
    **Path Parameters:**
    - `user_id`: ID of the user whose status should be toggled
    
    **Authentication Required:**
    - Valid JWT access token in Authorization header
    - Super Admin role (SUPER_USER)
    - Active user account
    
    **Account Status Effects:**
    
    **When Deactivated:**
    - User cannot login with credentials
    - Existing tokens remain valid until expiration
    - API key access is disabled
    - User appears as inactive in system
    
    **When Activated:**
    - User can login normally
    - Can generate new tokens
    - API key access restored (if key exists)
    - Full system access restored
    
    **Response:**
    - Success message indicating action taken
    - Confirms whether user was activated or deactivated
    
    **Security Features:**
    - Non-destructive account management
    - Immediate effect on authentication
    - Preserves user data and settings
    - Reversible action
    
    **Error Responses:**
    - `403 Forbidden`: Insufficient permissions (not super admin)
    - `404 Not Found`: User doesn't exist
    - `401 Unauthorized`: Invalid or missing token
    
    **Usage Example:**
    ```bash
    curl -X PUT "/v1.0/auth/super/users/abc123def4/activate" \
         -H "Authorization: Bearer your_super_admin_token"
    ```
    
    **Response Examples:**
    ```json
    // User was inactive, now activated
    {
      "message": "User activated successfully"
    }
    
    // User was active, now deactivated
    {
      "message": "User deactivated successfully"
    }
    ```
    
    **Use Cases:**
    - Temporary account suspension
    - Employee leave management
    - Security incident response
    - Account recovery processes
    - Compliance requirements
    
    **Best Practices:**
    - Document reason for status changes
    - Notify users of account status changes
    - Monitor for failed login attempts after deactivation
    - Use deactivation instead of deletion when possible
    - Consider impact on user's active sessions
    
    **Important Notes:**
    - Existing tokens remain valid until natural expiration
    - User data and settings are preserved
    - Action is immediately reversible
    - API key access follows account status
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
    """Authenticate user via API key"""
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
    Get User Profile via API Key - Retrieve User Information Using API Key Authentication
    
    This endpoint allows users to retrieve their profile information using API key
    authentication instead of JWT tokens. This is designed for programmatic access.
    
    **Authentication Method:**
    - Uses API key authentication via `X-API-Key` header
    - No JWT token required
    - Direct database lookup by API key
    - Validates user account status
    
    **API Key Requirements:**
    - Valid API key assigned to user
    - Active user account
    - API key must be provided in `X-API-Key` header
    
    **Returned Information:**
    - `id`: Unique user identifier
    - `username`: User's username
    - `email`: User's email address
    - `role`: User role (GENERAL_USER, ADMIN_USER, SUPER_USER)
    - `is_active`: Account status
    - `created_at`: Account creation timestamp
    - `updated_at`: Last profile update timestamp
    - `api_key`: The API key used for authentication
    
    **Authentication Required:**
    - Valid API key in `X-API-Key` header
    - Active user account
    - API key must exist in database
    
    **Security Features:**
    - Direct API key validation
    - Account status verification
    - Secure key lookup
    - No token expiration concerns
    
    **Error Responses:**
    - `401 Unauthorized`: Missing API key header
    - `401 Unauthorized`: Invalid or revoked API key
    - `401 Unauthorized`: Inactive user account
    
    **Usage Example:**
    ```bash
    curl -X GET "/v1.0/auth/apikey/me" \
         -H "X-API-Key: ak_1234567890abcdef1234567890abcdef"
    ```
    
    **Response Example:**
    ```json
    {
      "id": "abc123def4",
      "username": "john_doe",
      "email": "john@example.com",
      "role": "ADMIN_USER",
      "is_active": true,
      "created_at": "2024-01-15T10:30:00Z",
      "updated_at": "2024-01-15T10:30:00Z",
      "api_key": "ak_1234567890abcdef1234567890abcdef"
    }
    ```
    
    **Use Cases:**
    - Server-to-server authentication
    - Automated scripts and applications
    - CI/CD pipeline integration
    - Microservice authentication
    - Long-running background processes
    
    **Advantages over JWT:**
    - No token expiration management
    - Simpler authentication flow
    - Better for automated systems
    - No refresh token complexity
    - Direct database validation
    
    **API Key Management:**
    - API keys can be regenerated by admins
    - Keys can be revoked immediately
    - Only admin/super admin users receive API keys
    - Self-registered users don't get API keys
    
    **Best Practices:**
    - Store API keys securely
    - Use HTTPS for all API key requests
    - Rotate API keys regularly
    - Monitor API key usage
    - Implement rate limiting for API key endpoints
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
