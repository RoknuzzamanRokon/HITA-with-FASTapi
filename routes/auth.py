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
    """Create a new user in the database"""
    user_id = generate_user_id()
    hashed_password = get_password_hash(user_data.password)

    # Generate API key for the user
    api_key = f"ak_{uuid.uuid4().hex}"

    db_user = models.User(
        id=user_id,
        username=user_data.username,
        email=user_data.email,
        hashed_password=hashed_password,
        role=user_data.role,
        api_key=api_key,
        is_active=True,
        created_by=created_by or "system",
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
            status_code=status.HTTP_403_FORBIDDEN, detail="Insufficient permissions"
        )
    return current_user


# Routes
@router.post("/token", response_model=Token)
async def login_for_access_token(
    form_data: Annotated[OAuth2PasswordRequestForm, Depends()],
    db: Session = Depends(get_db),
):
    """Login and get access/refresh tokens."""
    user = authenticate_user(db, form_data.username, form_data.password)
    if not user:
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

    return {
        "access_token": access_token,
        "token_type": "bearer",
        "refresh_token": refresh_token,
    }


@router.post("/refresh", response_model=Token)
async def refresh_access_token(
    refresh_request: RefreshTokenRequest, db: Session = Depends(get_db)
):
    """Refresh access token using refresh token."""
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
    """Register a new user."""

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
        db_user = create_user(db, user)
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
    """Logout user by blacklisting token."""
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
    """Logout user from all devices by removing all refresh tokens."""
    redis_client.delete(f"refresh_token:{current_user.id}")
    return {"message": "Successfully logged out from all devices"}


@router.get("/me", response_model=UserProfileResponse)
async def read_users_me(
    current_user: Annotated[models.User, Depends(get_current_active_user)],
):
    """Get current user information."""
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
    """Regenerate API key for current user."""
    new_api_key = generate_api_key(db, current_user.id)
    return {"message": "API key regenerated successfully", "api_key": new_api_key}


@router.get("/health")
async def auth_health_check(
    current_user: Annotated[models.User, Depends(get_current_active_user)],
    db: Session = Depends(get_db),
):
    """Authenticated health check endpoint."""
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
    """Get all users (super_user only)."""
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
    """Activate/deactivate a user (admin only)."""
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


@router.get("/api-key/me", response_model=UserProfileResponse)
async def read_users_me_api_key(
    current_user: Annotated[models.User, Depends(authenticate_api_key)],
):
    """Get current user information using API key authentication."""
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
