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

load_dotenv()
blacklist = redis.Redis(host="localhost", port=6379, db=0)

PER_REQUEST_POINT_DEDUCTION = os.getenv("PER_REQUEST_POINT_DEDUCTION")

def is_exempt_from_point_deduction(user: models.User) -> bool:
    """Check if user is exempt from point deductions (super_user and admin_user)."""
    return user.role in [models.UserRole.SUPER_USER, models.UserRole.ADMIN_USER]


# Password hashing
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

# JWT settings
SECRET_KEY = "your_secret_key_your_secret_key_your_secret_key_your_secret_key_your_secret_key"
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
        hashed_password=hashed_password
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
    expire = datetime.utcnow() + (expires_delta or timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES))
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
        current_user: models.User, db: Session,
        points: int = PER_REQUEST_POINT_DEDUCTION
    ):
    """Deduct points for general_user only. Super users and admin users are exempt."""
    
    # 🚫 NO POINT DEDUCTION for super_user and admin_user
    if current_user.role in [models.UserRole.SUPER_USER, models.UserRole.ADMIN_USER]:
        # Log the exemption for monitoring
        print(f"🔓 Point deduction skipped for {current_user.role}: {current_user.email}")
        return  # Exit early, no deduction for privileged users
    
    # Only deduct points for general_user
    if current_user.role != models.UserRole.GENERAL_USER:
        return  # No deduction for other roles
    
    # Get the user's points
    user_points = db.query(models.UserPoint).filter(models.UserPoint.user_id == current_user.id).first()
    if not user_points or user_points.current_points < points:
        raise HTTPException(
            status_code=400,
            detail="Insufficient points to access this endpoint."
        )

    # Deduct points only for general users
    user_points.current_points -= points
    user_points.total_used_points += points

    # Check if a deduction transaction already exists for the user
    existing_transaction = db.query(models.PointTransaction).filter(
        models.PointTransaction.giver_id == current_user.id,
        models.PointTransaction.transaction_type == "deduction"
    ).first()

    if existing_transaction:
        # Update the existing transaction
        existing_transaction.giver_email = current_user.email
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
