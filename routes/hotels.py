from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from database import get_db
from schemas import HotelCreate, HotelRead
from typing import Annotated
import models
from utils import get_current_user
from datetime import datetime

router = APIRouter(
    prefix="/hotels",
    tags=["hotels"],
    responses={404: {"description": "Not found"}},
)


# def deduct_points_for_general_user(current_user: models.User, db: Session):
#     """Deduct 10 points for general_user."""
#     if current_user.role == models.UserRole.GENERAL_USER:
#         user_points = db.query(models.UserPoint).filter(models.UserPoint.user_id == current_user.id).first()
#         if not user_points or user_points.current_points < 10:
#             raise HTTPException(
#                 status_code=400,
#                 detail="Insufficient points to access this endpoint."
#             )

#         user_points.current_points -= 10
#         user_points.total_used_points += 10

#         transaction = models.PointTransaction(
#             giver_id=current_user.id,
#             points=10,
#             transaction_type="deduction",
#             created_at=datetime.utcnow()
#         )
#         db.add(transaction)
#         db.commit()


def deduct_points_for_general_user(current_user: models.User, db: Session):
    """Deduct 10 points for general_user and update the same row for the user."""
    if current_user.role == models.UserRole.GENERAL_USER:
        # Get the user's points
        user_points = db.query(models.UserPoint).filter(models.UserPoint.user_id == current_user.id).first()
        if not user_points or user_points.current_points < 10:
            raise HTTPException(
                status_code=400,
                detail="Insufficient points to access this endpoint."
            )

        # Deduct points
        user_points.current_points -= 10
        user_points.total_used_points += 10

        # Check if a deduction transaction already exists for the user
        existing_transaction = db.query(models.PointTransaction).filter(
            models.PointTransaction.giver_id == current_user.id,
            models.PointTransaction.transaction_type == "deduction"
        ).first()

        if existing_transaction:
            # Update the existing transaction
            existing_transaction.points += 10  # Add the deducted points to the existing row
            existing_transaction.created_at = datetime.utcnow()  # Update the timestamp
        else:
            # Create a new transaction if none exists
            transaction = models.PointTransaction(
                giver_id=current_user.id,
                points=10,
                transaction_type="deduction",
                created_at=datetime.utcnow()
            )
            db.add(transaction)

        db.commit()

# Create hotel endpoint with point deduction and response model
@router.post("/input/", response_model=HotelRead)
async def create_hotel(
    hotel: HotelCreate,
    db: Annotated[Session, Depends(get_db)],
    
):
    """Create a new hotel (deducts points for general users)."""
    

    # Create and persist hotel
    db_hotel = models.DemoHotel(**hotel.dict())
    db.add(db_hotel)
    db.commit()
    db.refresh(db_hotel)
    return db_hotel

# Read hotels list
@router.get("/getAll/", response_model=list[HotelRead])
async def read_hotels(
    db: Annotated[Session, Depends(get_db)],
    skip: int = 0,
    limit: int = 10,
    current_user: models.User = Depends(get_current_user)
):
    # Deduct points if necessary
    deduct_points_for_general_user(current_user, db)
    """Get a list of hotels."""
    hotels = db.query(models.DemoHotel).offset(skip).limit(limit).all()
    return hotels

# Read specific hotel
@router.get("/getAHotel/{hotel_id}", response_model=HotelRead)
async def read_hotel(
    hotel_id: int,
    db: Annotated[Session, Depends(get_db)],
    current_user: models.User = Depends(get_current_user)
):
    deduct_points_for_general_user(current_user, db)
    """Get a specific hotel by ID."""
    hotel = db.query(models.DemoHotel).filter(models.DemoHotel.id == hotel_id).first()
    if not hotel:
        raise HTTPException(status_code=404, detail="Hotel not found")
    return hotel


