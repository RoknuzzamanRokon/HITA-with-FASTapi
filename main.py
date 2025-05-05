from fastapi import FastAPI, Depends, HTTPException
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.orm import Session
from database import engine, SessionLocal
import models
from schemas import UserCreate, Token, User
from utils import create_user, authenticate_user, create_access_token, get_current_user
from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import JSONResponse
from fastapi.encoders import jsonable_encoder
from typing import List

models.Base.metadata.create_all(bind=engine)

app = FastAPI()

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

@app.post("/register", response_model=User)
def register_user(user: UserCreate, db: Session = Depends(get_db)):
    """Register a new user."""
    db_user = create_user(db, user)
    return db_user

@app.post("/token", response_model=Token)
async def login_for_access_token(form_data: OAuth2PasswordRequestForm = Depends(), db: Session = Depends(get_db)):
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

@app.get("/users/me", response_model=User)
async def read_users_me(current_user: User = Depends(get_current_user)):
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
async def create_hotel(hotel: schemas.HotelCreate, db: Session = Depends(get_db)):
    db_hotel = models.Hotel(**hotel.dict())
    db.add(db_hotel)
    db.commit()
    db.refresh(db_hotel)
    return db_hotel

@router.get("/", response_model=List[schemas.Hotel])
async def read_hotels(skip: int = 0, limit: int = 100, db: Session = Depends(get_db)):
    hotels = db.query(models.Hotel).offset(skip).limit(limit).all()
    return hotels

@router.get("/{hotel_id}", response_model=schemas.Hotel)
async def read_hotel(hotel_id: int, db: Session = Depends(get_db)):
    hotel = db.query(models.Hotel).filter(models.Hotel.id == hotel_id).first()
    if hotel is None:
        raise HTTPException(status_code=404, detail="Hotel not found")
    return hotel

app.include_router(router)
