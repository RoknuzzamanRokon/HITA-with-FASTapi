from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from database import get_db
from schemas import HotelCreateDemo, HotelReadDemo
from typing import Annotated
import models
from datetime import datetime
from utils import require_role, get_current_user 
from models import User


router = APIRouter(
    prefix="/v1.0/hotels/demo",
    tags=["Hotels Demo"],
    responses={404: {"description": "Not found"}},
)


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
@router.post("/input", response_model=HotelReadDemo, status_code=status.HTTP_201_CREATED)
async def create_hotel(
    hotel: HotelCreateDemo,
    db: Annotated[Session, Depends(get_db)],
    current_user: User = Depends(get_current_user)
):
    """Create a new hotel (deducts points for general users)."""
    
    require_role(["super_user", "admin_user"], current_user)

    try: 
        # Create and persist hotel
        db_hotel = models.DemoHotel(**hotel.dict())
        db.add(db_hotel)
        db.commit()
        db.refresh(db_hotel)
        return db_hotel
    except Exception as e:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST
        )

# Read hotels list
@router.get("/getAll", response_model=list[HotelReadDemo])
async def read_hotels(
    db: Annotated[Session, Depends(get_db)],
    skip: int = 0,
    limit: int = 10,
    current_user: models.User = Depends(get_current_user)
):
    # Deduct points if necessary
    """Get a list of hotels."""
    hotels = db.query(models.DemoHotel).offset(skip).limit(limit).all()
    return hotels

# Read specific hotel
@router.get("/getAHotel/{hotel_id}", response_model=HotelReadDemo)
async def read_hotel(
    hotel_id: int,
    db: Annotated[Session, Depends(get_db)],
    current_user: models.User = Depends(get_current_user)
):

    """Get a specific hotel by ID."""
    hotel = db.query(models.DemoHotel).filter(models.DemoHotel.id == hotel_id).first()
    if not hotel:
        raise HTTPException(status_code=404, detail="Hotel not found")
    return hotel


