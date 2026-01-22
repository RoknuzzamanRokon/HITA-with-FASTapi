from passlib.context import CryptContext
from jose import JWTError, jwt
from datetime import datetime, timedelta
from sqlalchemy.orm import Session
from models import User
from schemas import UserCreate
from fastapi import Depends, HTTPException, status, Request
from fastapi.security import OAuth2PasswordBearer
from typing import Annotated
from database import get_db
import secrets
import models
import redis
from dotenv import load_dotenv
import os
import logging

load_dotenv()

logger = logging.getLogger(__name__)

# Lazy Redis connection - only connects when needed
_redis_client = None
_redis_available = False

def get_redis_client():
    """Get Redis client with lazy initialization and error handling"""
    global _redis_client, _redis_available
    
    if _redis_client is None:
        try:
            _redis_client = redis.Redis(
                host=os.getenv('REDIS_HOST', 'localhost'),
                port=int(os.getenv('REDIS_PORT', 6379)),
                db=int(os.getenv('REDIS_DB', 0)),
                password=os.getenv('REDIS_PASSWORD', None),
                socket_timeout=2,
                socket_connect_timeout=2,
                decode_responses=True
            )
            # Test connection
            _redis_client.ping()
            _redis_available = True
            logger.info("Redis connection established successfully")
        except Exception as e:
            logger.warning(f"Redis not available: {e}. Application will continue without Redis.")
            _redis_available = False
            _redis_client = None
    
    return _redis_client if _redis_available else None

# Create a wrapper class for backward compatibility
class RedisBlacklistWrapper:
    """Wrapper for Redis blacklist operations that handles connection errors gracefully"""
    
    def get(self, key: str):
        """Get value from Redis (returns None if Redis unavailable)"""
        client = get_redis_client()
        if client:
            try:
                return client.get(key)
            except Exception as e:
                logger.warning(f"Redis get failed: {e}")
                return None
        return None
    
    def setex(self, key: str, time: int, value: str):
        """Set value in Redis with expiration (silently fails if Redis unavailable)"""
        client = get_redis_client()
        if client:
            try:
                return client.setex(key, time, value)
            except Exception as e:
                logger.warning(f"Redis setex failed: {e}")
                return False
        return False
    
    def exists(self, key: str):
        """Check if key exists in Redis (returns 0 if Redis unavailable)"""
        client = get_redis_client()
        if client:
            try:
                return client.exists(key)
            except Exception as e:
                logger.warning(f"Redis exists failed: {e}")
                return 0
        return 0

# Backward compatibility - create wrapper instance
blacklist = RedisBlacklistWrapper()

PER_REQUEST_POINT_DEDUCTION = os.getenv("PER_REQUEST_POINT_DEDUCTION")


def is_exempt_from_point_deduction(user: models.User) -> bool:
    """Check if user is exempt from point deductions (super_user and admin_user)."""
    return user.role in [models.UserRole.SUPER_USER, models.UserRole.ADMIN_USER]


# Password hashing
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

# JWT settings
SECRET_KEY = (
    "your_secret_key_your_secret_key_your_secret_key_your_secret_key_your_secret_key"
)
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 424440

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="token")


def create_user(db: Session, user: UserCreate, created_by=None):
    hashed_password = pwd_context.hash(user.password)
    unique_id = secrets.token_hex(5)
    db_user = User(
        id=unique_id,
        username=user.username,
        email=user.email,
        hashed_password=hashed_password,
    )
    db.add(db_user)
    db.commit()
    db.refresh(db_user)
    return db_user


def generate_unique_id(length: int = 10) -> str:
    """Generate a unique ID with the specified length."""
    return secrets.token_hex(length // 2)


def generate_user_id() -> str:
    """Generate a unique user ID."""
    return secrets.token_hex(5)


def hash_password(password: str) -> str:
    """Hash a password using bcrypt."""
    return pwd_context.hash(password)


def authenticate_user(db: Session, username: str, password: str):
    user = db.query(User).filter(User.username == username).first()
    if not user or not pwd_context.verify(password, user.hashed_password):
        return None
    return user


def create_access_token(data: dict, expires_delta: timedelta = None):
    to_encode = data.copy()
    expire = datetime.utcnow() + (
        expires_delta or timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    )
    to_encode.update({"exp": expire})
    return jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)


def require_role(required_roles: list, current_user: User):
    if current_user.role not in required_roles:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You do not have permission to perform this action",
        )
    return current_user


def deduct_points_for_general_user(
    current_user: models.User, db: Session, points: int = PER_REQUEST_POINT_DEDUCTION
):
    """Deduct points for general_user only. Super users and admin users are exempt."""

    # 🚫 NO POINT DEDUCTION for super_user and admin_user
    if current_user.role in [models.UserRole.SUPER_USER, models.UserRole.ADMIN_USER]:
        # Log the exemption for monitoring
        print(
            f"🔓 Point deduction skipped for {current_user.role}: {current_user.email}"
        )
        return  # Exit early, no deduction for privileged users

    # Only deduct points for general_user
    if current_user.role != models.UserRole.GENERAL_USER:
        return  # No deduction for other roles

    # Get the user's points
    user_points = (
        db.query(models.UserPoint)
        .filter(models.UserPoint.user_id == current_user.id)
        .first()
    )

    # Convert to int for comparison (handle both string and int types)
    current_points_value = (
        int(user_points.current_points)
        if user_points and user_points.current_points
        else 0
    )
    points_to_deduct = int(points) if points else 0

    if not user_points or current_points_value < points_to_deduct:
        raise HTTPException(
            status_code=400, detail="Insufficient points to access this endpoint."
        )

    # Deduct points only for general users (ensure integer arithmetic)
    user_points.current_points = current_points_value - points_to_deduct
    user_points.total_used_points = (
        int(user_points.total_used_points or 0) + points_to_deduct
    )

    # Check if a deduction transaction already exists for the user
    existing_transaction = (
        db.query(models.PointTransaction)
        .filter(
            models.PointTransaction.giver_id == current_user.id,
            models.PointTransaction.transaction_type == "deduction",
        )
        .first()
    )

    if existing_transaction:
        # Update the existing transaction
        existing_transaction.giver_email = current_user.email
        existing_transaction.points += points_to_deduct
        existing_transaction.created_at = datetime.utcnow()  # Update the timestamp
    else:
        # Create a new transaction if none exists
        transaction = models.PointTransaction(
            giver_id=current_user.id,
            points=points_to_deduct,
            transaction_type="deduction",
            created_at=datetime.utcnow(),
        )
        db.add(transaction)

    db.commit()
