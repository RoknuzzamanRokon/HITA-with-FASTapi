from fastapi import FastAPI, Depends, HTTPException
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.orm import Session
from database import engine, SessionLocal, get_db, Base
import models
from schemas import UserCreate, Token, User
from utils import create_user, authenticate_user, create_access_token, get_current_user
from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import JSONResponse
from fastapi.encoders import jsonable_encoder
from typing import List, Annotated
import schemas
import logging
from passlib.context import CryptContext
import secrets

# Use bcrypt for password hashing
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


def get_password_hash(password):
    return pwd_context.hash(password)



logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)
logger.info("Starting FastAPI application...")

models.Base.metadata.create_all(bind=engine)
app = FastAPI()




@app.post("/create-super-admin", response_model=User)
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





@app.post("/token", response_model=Token)
async def login_for_access_token(form_data: Annotated[OAuth2PasswordRequestForm, Depends()], db: Annotated[Session, Depends(get_db)]):
    """Login and get an access token."""
    user = authenticate_user(db, form_data.username, form_data.password)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect username or password",
            headers={"WWW-Authenticate": "Bearer"},
        )
    access_token = create_access_token(data={"sub": user.username})
    return {"access_token": access_token, "token_type": "bearer"}



@app.post("/create-admin-user", response_model=User)
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


@app.delete("/delete-user/{user_id}")
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





@app.post("/register", response_model=User)
def register_user(user: UserCreate, db: Annotated[Session, Depends(get_db)]):
    """Register a new user."""

    existing_user = db.query(models.User).filter(
        (models.User.username == user.username) | (models.User.email == user.email)
    ).first()
    if existing_user:
        return JSONResponse(
            status_code=status.HTTP_400_BAD_REQUEST,
            content={"message_from_system": "User Already exist."}
        )
    try:
        db_user = create_user(db, user)
        return jsonable_encoder(db_user)
    except Exception as e:
        return JSONResponse(
            status_code=status.HTTP_400_BAD_REQUEST,
            content={"message_from_system": "cannot input valid field."}
        )





@app.get("/user/me", response_model=User)
async def read_user_me(current_user: Annotated[User, Depends(get_current_user)]):
    """Get details of the current user."""
    return current_user




# Placeholder for registration URL
@app.get("/registration")
async def registration():
    return {"message": "Registration URL"}

# Placeholder for login URL
@app.get("/login")
async def login():
    return {"message": "Login URL"}

# Placeholder for logout URL
@app.get("/logout")
async def logout():
    return {"message": "Logout URL"}

# Hotels Routes
router = APIRouter(
    prefix="/hotels",
    tags=["hotels"],
    responses={404: {"description": "Not found"}},
)

@router.post("/")
async def create_hotel(hotel: schemas.HotelCreate, db: Annotated[Session, Depends(get_db)]):
    db_hotel = models.Hotel(**hotel.dict())
    db.add(db_hotel)
    db.commit()
    db.refresh(db_hotel)
    return db_hotel
