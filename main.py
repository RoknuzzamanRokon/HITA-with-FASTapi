from fastapi import FastAPI, Depends, HTTPException
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.orm import Session
from database import engine, SessionLocal, get_db, Base
import models
from schemas import UserCreate, Token, User, UserResponse
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

# Include routers
from routes.auth import router as auth_router
from routes.users import router as users_router
from routes.hotels import router as hotels_router

app.include_router(auth_router)
app.include_router(users_router)
app.include_router(hotels_router)





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
