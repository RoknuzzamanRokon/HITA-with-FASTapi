from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordRequestForm
from fastapi.responses import JSONResponse
from fastapi.encoders import jsonable_encoder
from sqlalchemy.orm import Session
from utils import authenticate_user, create_access_token, create_user
from database import get_db
from schemas import Token, UserCreate, User
from typing import Annotated
import models

router = APIRouter(
    prefix="/auth",
    tags=["auth"],
    responses={404: {"description": "Not found"}},
)

@router.post("/token", response_model=Token)
async def login_for_access_token(
    form_data: Annotated[OAuth2PasswordRequestForm, Depends()],
    db: Annotated[Session, Depends(get_db)]
):
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





@router.post("/register", response_model=User)
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



@router.get("/login")
async def login():
    """Placeholder for login URL."""
    return {"message": "Use the /auth/token endpoint to log in with your username and password."}



@router.get("/logout")
async def logout():
    """Placeholder for logout URL."""
    return {"message": "Logout URL"}