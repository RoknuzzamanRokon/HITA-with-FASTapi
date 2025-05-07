from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from database import get_db
from schemas import HotelCreate
from typing import Annotated
import models

router = APIRouter(
    prefix="/hotels",
    tags=["hotels"],
    responses={404: {"description": "Not found"}},
)

@router.post("/")
async def create_hotel(hotel: HotelCreate, db: Annotated[Session, Depends(get_db)]):
    db_hotel = models.Hotel(**hotel.dict())
    db.add(db_hotel)
    db.commit()
    db.refresh(db_hotel)
    return db_hotel

# @router.get("/")
# async def read_hotels(skip: int = 0, limit: int = 10, db: Annotated[Session, Depends(get_db)]):
#     hotels = db.query(models.Hotel).offset(skip).limit(limit).all()
#     return hotels