from fastapi import FastAPI, Depends, HTTPException, status
from fastapi.security import APIKeyHeader, OAuth2PasswordBearer, OAuth2PasswordRequestForm
from typing import Optional, List
from enum import Enum
from datetime import datetime, timedelta
from jose import JWTError, jwt
from passlib.context import CryptContext
import secrets

from sqlalchemy import create_engine, Column, Integer, String, DateTime, Enum as SQLEnum, Boolean
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, Session
from sqlalchemy import MetaData

from models import Base, User, UserRole, SessionLocal, BlacklistedToken
from schemas import Token, TokenData
from utils import create_access_token, verify_password, get_password_hash, generate_api_key

# Database Configuration
DATABASE_URL = "sqlite:///./hotel.db"  # SQLite database
engine = create_engine(DATABASE_URL)
Base.metadata.create_all(bind=engine)

# Password Hashing
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

# JWT Configuration
SECRET_KEY = "YOUR_SECRET_KEY_SUPER_SAFE"  # Change this in production
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 30

# API Key Configuration
API_KEY_NAME = "X-API-Key"
api_key_header = APIKeyHeader(name=API_KEY_NAME, auto_error=True)

# FastAPI App
app = FastAPI()

# OAuth2 scheme for JWT authentication
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="token")

# Dependency to get the database session
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

# Utility functions (moved to utils.py)
def create_access_token(data: dict, expires_delta: Optional[timedelta] = None):
    to_encode = data.copy()
    if expires_delta:
        expire = datetime.utcnow() + expires_delta
    else:
        expire = datetime.utcnow() + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
    return encoded_jwt

def verify_password(plain_password: str, hashed_password: str):
    return pwd_context.verify(plain_password, hashed_password)

def get_password_hash(password: str):
    return pwd_context.hash(password)

def generate_api_key():
    return secrets.token_urlsafe(32)

# Function to authenticate user
def authenticate_user(db: Session, username: str, password: str):
    user = db.query(User).filter(User.username == username).first()
    if not user:
        return None
    if not verify_password(password, user.password_hash):
        return None
    return user

# Dependency to get the current user from a JWT token
async def get_current_user(
    token: str = Depends(oauth2_scheme), db: Session = Depends(get_db)
):
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        user_id: str = payload.get("sub")
        if user_id is None:
            raise credentials_exception
    except JWTError:
        raise credentials_exception
    user = db.query(User).filter(User.id == int(user_id)).first()
    if user is None:
        raise credentials_exception
    return user

# Dependency to get the current active user
async def get_current_active_user(current_user: User = Depends(get_current_user)):
    if not current_user.is_active:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Inactive user")
    return current_user

# Dependency to check if the user has a specific role
def has_role(role: UserRole):
    def dependency(current_user: User = Depends(get_current_active_user)):
        if current_user.role != role:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN, detail="Insufficient permissions"
            )
        return current_user
    return dependency

# Endpoint to generate a token for authentication
@app.post("/token", response_model=Token)
async def login_for_access_token(
    form_data: OAuth2PasswordRequestForm = Depends(), db: Session = Depends(get_db)
):
    user = authenticate_user(db, form_data.username, form_data.password)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect username or password",
            headers={"WWW-Authenticate": "Bearer"},
        )
    access_token_expires = timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    access_token = create_access_token(
        data={"sub": user.username}, expires_delta=access_token_expires
    )
    return {"access_token": access_token, "token_type": "bearer"}

# Example endpoint (requires authentication)
@app.get("/hotels/", dependencies=[Depends(get_current_active_user)])
async def read_hotels():
    return [{"name": "Hotel California"}, {"name": "Grand Budapest Hotel"}]

# Example admin endpoint (requires Admin role)
@app.get("/admin/", dependencies=[Depends(has_role(UserRole.ADMIN_USER))])
async def admin_route():
    return {"message": "Admin access granted"}

# Example superuser endpoint (requires Superuser role)
@app.get("/superuser/", dependencies=[Depends(has_role(UserRole.SUPER_USER))])
async def superuser_route():
    return {"message": "Superuser access granted"}

# Create a superuser
def create_superuser(db: Session):
    superuser = db.query(User).filter(User.username == "superuser").first()
    if not superuser:
        hashed_password = get_password_hash("superuser")
        superuser = User(
            username="superuser",
            password_hash=hashed_password,
            role=UserRole.SUPER_USER,
            is_active=True,
        )
        db.add(superuser)
        db.commit()
        db.refresh(superuser)
        print("Superuser created")

# Call create_superuser when the application starts
@app.on_event("startup")
def startup_event():
    db = SessionLocal()
    create_superuser(db)
    db.close()
