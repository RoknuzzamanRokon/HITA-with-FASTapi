from pydantic import BaseModel, EmailStr
from typing import Optional
from datetime import datetime

# Schema for creating a new user
class UserCreate(BaseModel):
    username: str
    email: EmailStr
    password: str

# Schema for returning user details
class User(BaseModel):
    id: str
    username: str
    email: EmailStr

    class Config:
        from_attributes = True

# Schema for token response
class Token(BaseModel):
    access_token: str
    token_type: str

class HotelCreate(BaseModel):
    name: str
    location: str
    price: int

class UserResponse(BaseModel):
    id: str
    username: str
    email: EmailStr
    user_status: str
    created_at: datetime

    class Config:
        from_attributes = True


# Rebuild forward references
UserCreate.model_rebuild()
HotelCreate.model_rebuild()
User.model_rebuild()
Token.model_rebuild()
UserResponse.model_rebuild()